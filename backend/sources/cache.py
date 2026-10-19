"""
24-hour cache of real API responses, in the Supabase table `search_cache`.

Only live responses are stored here. Recorded fixtures never are, so a
production backend sharing this database can't serve them by accident.

    key = cache.query_hash("vintage graphic tee", max_price=30)
    raw = cache.get(key, "resale")            # None when missing or older than 24 h
    cache.put(key, "resale", raw)
    cache.recent("resale")                    # every ≤ 24 h response for that source

The `platform` column holds the adapter's FIXTURE_PREFIX ("resale", "etsy",
"fb"): one Fashion Resale response covers four stores.
"""

import datetime as dt
import hashlib
import logging

import config

log = logging.getLogger("fitfindr.cache")


def query_hash(query: str, max_price: float | None = None) -> str:
    words = " ".join(str(query or "").lower().split())
    price = "" if max_price is None else f"{float(max_price):.2f}"
    return hashlib.sha256(f"{words}|{price}".encode("utf-8")).hexdigest()[:40]


def _cutoff() -> str:
    oldest = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=config.CACHE_MAX_AGE_HOURS)
    return oldest.isoformat(timespec="seconds")


def get(key: str, source: str) -> dict | None:
    import supa
    try:
        rows = supa.service().select("search_cache", {
            "select": "response_json,fetched_at", "query_hash": f"eq.{key}",
            "platform": f"eq.{source}", "fetched_at": f"gte.{_cutoff()}"})
    except Exception as exc:  # noqa: BLE001 — a cache miss, not an outage
        log.warning("search_cache read failed: %s", config.redact(exc))
        return None
    return rows[0]["response_json"] if rows else None


def put(key: str, source: str, raw: dict) -> None:
    import supa
    try:
        supa.service().insert("search_cache", {
            "query_hash": key, "platform": source, "response_json": raw,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
            upsert=True, on_conflict="query_hash,platform")
    except Exception as exc:  # noqa: BLE001
        log.warning("search_cache write failed: %s", config.redact(exc))


def recent(source: str, limit: int = 20) -> list[dict]:
    """Raw responses for one source fetched in the last 24 h, newest first."""
    import supa
    try:
        rows = supa.service().select("search_cache", {
            "select": "response_json", "platform": f"eq.{source}",
            "fetched_at": f"gte.{_cutoff()}", "order": "fetched_at.desc", "limit": str(limit)})
    except Exception as exc:  # noqa: BLE001
        log.warning("search_cache read failed: %s", config.redact(exc))
        return []
    return [r["response_json"] for r in rows]
