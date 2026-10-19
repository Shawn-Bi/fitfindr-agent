"""
All listing sources, behind one call.

    from sources import fetch_candidates
    listings = fetch_candidates("vintage graphic tee")

fixtures mode → every tests/fixtures/<prefix>_*.json, parsed by its adapter.
live mode     → each adapter's live search(); a paused or not-yet-wired store
                is skipped and reported in `statuses`, never filled with fixtures.

Filtering, scoring and dedupe happen in tools.search_listings.
"""

import json
import logging

import config
from sources import etsy, fb_marketplace, quota, resale

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


def fetch_candidates(query: str, max_price: float | None = None) -> tuple[list[dict], list[dict]]:
    """
    Returns (listings, statuses). statuses has one entry per platform, e.g.
    {"platform": "ebay", "status": "paused", "resumes": "2026-11-01"}.
    """
    listings, statuses = [], []
    for adapter in ADAPTERS:
        if config.DATA_MODE == "fixtures":
            listings.extend(_from_fixtures(adapter))
            statuses += [{"platform": p, "status": "fixtures"} for p in adapter.PLATFORMS]
            continue
        try:
            listings.extend(adapter.search(query, max_price=max_price))
            statuses += [quota.status(adapter.SOURCE, p) for p in adapter.PLATFORMS]
        except quota.QuotaPaused as paused:
            # TODO: serve this store's ≤ 24 h search_cache entry when one exists.
            statuses += [{"platform": p, "status": "paused", "resumes": paused.resumes}
                         for p in adapter.PLATFORMS]
        except NotImplementedError:
            statuses += [{"platform": p, "status": "unavailable"} for p in adapter.PLATFORMS]
        except Exception:  # noqa: BLE001 — one broken store must not break search
            log.exception("source %s failed", adapter.__name__)
            statuses += [{"platform": p, "status": "error"} for p in adapter.PLATFORMS]
    return listings, statuses
