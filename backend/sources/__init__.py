"""
All listing sources, behind one call.

    from sources import fetch_candidates
    listings, statuses = fetch_candidates("vintage graphic tee")

fixtures mode → every tests/fixtures/<prefix>_*.json, parsed by its adapter.
live mode     → a ≤ 24 h search_cache copy if there is one, else the adapter's
                live fetch() (counted by quota.py) and the response is cached.
                A paused store with no cache is skipped and reported in
                `statuses`, never filled with fixtures.

Adapters with ENABLED = False (Etsy, FB Marketplace until their integration
pass) are reported as "coming_soon" in both modes.

Filtering, scoring and dedupe happen in tools.search_listings.
"""

import json
import logging

import config
from sources import cache, etsy, fb_marketplace, quota, resale

log = logging.getLogger("fitfindr.sources")

# Live-call priority: Fashion Resale first (Depop, Poshmark, Mercari, eBay);
# Etsy and FB Marketplace in one later pass.
ADAPTERS = (resale, etsy, fb_marketplace)


def _from_fixtures(adapter) -> list[dict]:
    listings = []
    for path in sorted(config.FIXTURES_DIR.glob(f"{adapter.FIXTURE_PREFIX}_*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        listings.extend(adapter.parse(raw))
    return listings


def _statuses(adapter, status: str, **extra) -> list[dict]:
    return [{"platform": p, "status": status, **extra} for p in adapter.PLATFORMS]


def fetch_candidates(query: str, max_price: float | None = None,
                     min_price: float | None = None) -> tuple[list[dict], list[dict]]:
    """
    Returns (listings, statuses). statuses has one entry per platform, e.g.
    {"platform": "ebay", "status": "paused", "resumes": "2026-11-01"}.
    status is one of: fixtures, active, cached, paused, coming_soon, error.
    """
    listings, statuses = [], []
    for adapter in ADAPTERS:
        if not adapter.ENABLED:
            statuses += _statuses(adapter, "coming_soon")
            continue
        if config.DATA_MODE == "fixtures":
            listings.extend(_from_fixtures(adapter))
            statuses += _statuses(adapter, "fixtures")
            continue

        key = cache.query_hash(query, max_price, min_price)
        raw = cache.get(key, adapter.FIXTURE_PREFIX)
        if raw is not None:
            listings.extend(adapter.parse(raw))
            statuses += _statuses(adapter, "cached")
            continue
        try:
            raw = adapter.fetch(query, max_price=max_price, min_price=min_price)
            cache.put(key, adapter.FIXTURE_PREFIX, raw)
            listings.extend(adapter.parse(raw))
            statuses += [quota.status(adapter.SOURCE, p) for p in adapter.PLATFORMS]
        except quota.QuotaPaused as paused:
            statuses += _statuses(adapter, "paused", resumes=paused.resumes)
        except Exception:  # noqa: BLE001 — one broken store must not break search
            log.exception("source %s failed", adapter.__name__)
            statuses += _statuses(adapter, "error")
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
