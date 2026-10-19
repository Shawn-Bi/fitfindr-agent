"""
Adapter for Depop, Poshmark and Mercari (Fashion Resale API) via RapidAPI host $RESALE_API_HOST.

Job: turn one search query into a list of FitFindr standard listing dicts
(see normalize.py): id, title, price (float, USD), size, platform, url,
image_url, plus optional condition, updated_at. Missing values are None.

    search(query)     → live call (counted by quota.py), returns list[dict]
    fetch_raw(query)  → the raw JSON response (used to record fixtures)
    parse(raw)        → raw JSON response → list[dict]; also used on fixtures

Endpoint: GET https://$RESALE_API_HOST/search
    q, platforms (comma list), per_page, page,
    optional size, min_price, max_price, condition, brand, sort, order.
The API also covers Grailed; FitFindr only asks for the three stores below.

Fixtures for this adapter live in tests/fixtures/resale_<query>.json.
Priority: wire this one first. One call covers three stores.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import config
from sources import quota
from sources.normalize import from_resale

SOURCE = "RESALE_API_HOST"                 # env var holding the RapidAPI host; quota key
PLATFORMS = ("depop", "poshmark", "mercari")
FIXTURE_PREFIX = "resale"
TIMEOUT_SECONDS = 20


def fetch_raw(query: str, per_page: int = 20, page: int = 1, **filters) -> dict:
    """
    One live request. Checks the stop line first, counts and logs the call
    whatever the outcome, and never retries (each retry would cost quota).
    """
    quota.check(SOURCE)
    host = os.getenv(SOURCE, "").strip()
    key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not host or not key:
        raise RuntimeError("RESALE_API_HOST and RAPIDAPI_KEY must be set in .env")

    params = {"q": query, "platforms": ",".join(PLATFORMS),
              "per_page": per_page, "page": page}
    params.update({k: v for k, v in filters.items() if v is not None})
    url = f"https://{host}/search?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"x-rapidapi-host": host, "x-rapidapi-key": key})

    status = "error"
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        raise RuntimeError(config.redact(f"Fashion Resale API returned HTTP {exc.code}")) from None
    finally:
        quota.record(SOURCE, status)


def parse(raw) -> list[dict]:
    """Map one raw API response to standard listing dicts, dropping unusable items."""
    if not isinstance(raw, dict):
        return []
    fetched_at = (raw.get("search_metadata") or {}).get("scraped_at")
    listings = (from_resale(item, fetched_at) for item in raw.get("listings") or [])
    return [listing for listing in listings if listing]


def search(query: str) -> list[dict]:
    """Live search across Depop, Poshmark and Mercari. Returns [] when nothing matches."""
    return parse(fetch_raw(query))
