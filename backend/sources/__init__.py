"""
All listing sources, behind one call.

    from sources import fetch_candidates
    listings, statuses = fetch_candidates("vintage graphic tee")

fixtures mode → every tests/fixtures/<prefix>_*.json, parsed by its adapter.
live mode     → a ≤ 24 h search_cache copy if there is one, else the adapter's
                live fetch() (counted by quota.py) and the response is cached.
                A paused store with no cache is skipped and reported in
                `statuses`, never filled with fixtures.

Adapters with ENABLED = False (FB Marketplace: host not subscribed yet) are
reported as "coming_soon" in both modes.

Filtering, scoring and dedupe happen in tools.search_listings.
"""

import json
import logging

import config
from sources import cache, etsy, failures, fb_marketplace, quota, resale

log = logging.getLogger("fitfindr.sources")

# Live-call priority: Fashion Resale first (Depop, Poshmark, Mercari, eBay),
# then Etsy; FB Marketplace once its host is subscribed.
ADAPTERS = (resale, etsy, fb_marketplace)


def _from_fixtures(adapter) -> list[dict]:
    listings = []
    for path in sorted(config.FIXTURES_DIR.glob(f"{adapter.FIXTURE_PREFIX}_*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        listings.extend(adapter.parse(raw))
    return listings


def _statuses(adapter, status: str, **extra) -> list[dict]:
    return [{"platform": p, "status": status, **extra} for p in adapter.PLATFORMS]


def cache_key(adapter, query: str, max_price: float | None, min_price: float | None) -> str:
    """Adapters that don't send the price range (Etsy) share one cached response across budgets."""
    if getattr(adapter, "PRICE_IN_QUERY", True):
        return cache.query_hash(query, max_price, min_price)
    return cache.query_hash(query)


def _failed_statuses(adapter, error: failures.StoreError, attempts: int, latency_ms: int) -> list[dict]:
    """One entry per platform behind the adapter, with the plain-words reason the UI shows."""
    if error.kind == "quota_paused":
        extra = {"resumes": error.resumes} if error.resumes else {}
        return _statuses(adapter, "paused", kind=error.kind, reason=failures.plain_reason(error.kind, error.resumes),
                         attempts=attempts, latency_ms=latency_ms, source=adapter.SOURCE, **extra)
    return _statuses(adapter, "error", kind=error.kind, reason=failures.plain_reason(error.kind),
                     error=error.detail, http_status=error.http_status,
                     attempts=attempts, latency_ms=latency_ms, source=adapter.SOURCE)


def _live_fetch(adapter, query, max_price, min_price):
    """One store attempt: request, check the reply's shape, parse. Returns (raw, listings)."""
    raw = adapter.fetch(query, max_price=max_price, min_price=min_price)
    validate = getattr(adapter, "validate", None)
    if validate:
        validate(raw)
    try:
        return raw, adapter.parse(raw)
    except Exception as exc:  # noqa: BLE001 — a reply we can't parse is a malformed reply
        raise failures.StoreError("malformed", f"{type(exc).__name__} while reading the reply") from None


def fetch_candidates(query: str, max_price: float | None = None,
                     min_price: float | None = None, *,
                     live: bool = True) -> tuple[list[dict], list[dict]]:
    """
    Returns (listings, statuses). statuses has one entry per platform, e.g.
    {"platform": "ebay", "status": "paused", "resumes": "2026-11-01"}.
    status is one of: fixtures, active, cached, paused, coming_soon, error,
    skipped (live=False and nothing cached: no live call was allowed).

    A store that fails never stops the others. Its entries get status "error"
    (or "paused" at our own stop line) plus `kind`, `reason` (plain words for
    the user), `attempts` and `latency_ms`; see sources/failures.py. A
    timeout or a 429 is retried once. Every entry carries `latency_ms`.
    """
    listings, statuses = [], []
    for adapter in ADAPTERS:
        if not adapter.ENABLED:
            statuses += _statuses(adapter, "coming_soon")
            continue
        if config.DATA_MODE == "fixtures":
            done = failures.call(adapter, lambda adapter=adapter: _from_fixtures(adapter))
            if done["ok"]:
                listings.extend(done["raw"])
                statuses += _statuses(adapter, "fixtures", attempts=done["attempts"], latency_ms=done["latency_ms"])
            else:
                statuses += _failed_statuses(adapter, done["error"], done["attempts"], done["latency_ms"])
            continue

        # An injected failure (tests only) fires before the cache, so it can be seen at any time.
        injected = failures.injected_fault(adapter, 1) is not None
        key = cache_key(adapter, query, max_price, min_price)
        raw = None if injected else cache.get(key, adapter.FIXTURE_PREFIX)
        if raw is not None:
            listings.extend(adapter.parse(raw))
            statuses += _statuses(adapter, "cached", latency_ms=0)
            continue
        if not injected and (not live or (config.LIVE_SOURCES and adapter.SOURCE not in config.LIVE_SOURCES)):
            statuses += _statuses(adapter, "skipped", latency_ms=0)
            continue

        done = failures.call(adapter, lambda adapter=adapter: _live_fetch(adapter, query, max_price, min_price))
        if not done["ok"]:
            statuses += _failed_statuses(adapter, done["error"], done["attempts"], done["latency_ms"])
            continue
        raw, found = done["raw"]
        cache.put(key, adapter.FIXTURE_PREFIX, raw)     # only a reply that passed validate() is cached
        listings.extend(found)
        try:
            marks = quota.statuses(adapter.SOURCE, adapter.PLATFORMS)
        except Exception:  # noqa: BLE001 — the search worked; a counter hiccup must not hide its results
            marks = _statuses(adapter, "active")
        statuses += [{**m, "attempts": done["attempts"], "latency_ms": done["latency_ms"], "source": adapter.SOURCE}
                     for m in marks]
    return listings, statuses


def recent_pool() -> list[dict]:
    """
    Listings already on hand, for Home picks and closet-item matches: fixtures
    in fixtures mode, ≤ 24 h search_cache responses in live mode. Never makes
    a live call (DECISIONS.md #19).
    """
    listings = []
    for adapter in ADAPTERS:
        if not adapter.ENABLED:
            continue
        if config.DATA_MODE == "fixtures":
            listings.extend(_from_fixtures(adapter))
        else:
            for raw in cache.recent(adapter.FIXTURE_PREFIX):
                listings.extend(adapter.parse(raw))
    return listings
