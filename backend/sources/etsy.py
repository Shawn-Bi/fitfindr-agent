"""
Adapter for Etsy via RapidAPI host $ETSY_API_HOST (etsy-api2, "Etsy API" by pintoflow).

Job: turn one search query into a list of FitFindr standard listing dicts
(see normalize.py): id, title, price (float, USD), size, platform, url,
image_url, plus optional condition, updated_at. Missing values are None.

    search(query)  → live call (counted by quota.py), returns list[dict]
    fetch(query)   → the raw JSON response (cached 24 h by sources/__init__)
    parse(raw)     → raw JSON response → list[dict]; also used on fixtures

Endpoint: GET https://$ETSY_API_HOST/product/search
    query (required), page, orderBy (mostRelevant | lowToHigh | highToLow |
    newest | topReviews), minPrice, maxPrice, currency, country, language.
Response: {"success": true, "data": {"results": [card, ...], "ads": [...]},
           "meta": {...}}; card = listingId, title, url, image,
           price {amount, currency}, shop {...}, isAd, isDigitalDownload.
Recorded proof: tests/fixtures/etsy_white_denim_pants.json (2026-10-19).

Decisions (docs/V2_REPORT.md):
- FitFindr sells secondhand, and Etsy's secondhand inventory is its vintage
  section, so the query is sent as "vintage <query>" (unless it already says
  vintage). Etsy falls back to a close variant itself when nothing matches.
- No price parameters are sent: one call per query serves every budget (the
  results are filtered in tools.py), which matters with 40 calls a month.
- Etsy search cards carry no size, condition or category; those stay None.
- Digital downloads (sewing patterns, printables) are dropped.
"""

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import config
from sources import quota
from sources.normalize import from_etsy

SOURCE = "ETSY_API_HOST"                 # env var holding the RapidAPI host; quota key
PLATFORMS = ("etsy",)
FIXTURE_PREFIX = "etsy"
ENABLED = True
PRICE_IN_QUERY = False   # the cache key ignores the price range: one response serves every budget
TIMEOUT_SECONDS = 60     # the API documents 2–5 s, sometimes more


def etsy_query(query: str) -> str:
    q = " ".join(str(query or "").split())
    return q if "vintage" in q.lower() else f"vintage {q}"


def fetch(query: str, max_price: float | None = None, min_price: float | None = None) -> dict:
    """
    One live request. Checks the stop line first, counts and logs the call
    whatever the outcome, and never retries (each retry would cost quota).
    The price range is applied after the call, not sent.
    """
    quota.check(SOURCE)
    host = os.getenv(SOURCE, "").strip()
    key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not host or not key:
        raise RuntimeError("ETSY_API_HOST and RAPIDAPI_KEY must be set in .env")

    params = {"query": etsy_query(query), "currency": "USD", "country": "US", "language": "en-US"}
    url = f"https://{host}/product/search?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"x-rapidapi-host": host, "x-rapidapi-key": key})

    status = "error"
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read()[:300].decode("utf-8", "replace")
        raise RuntimeError(config.redact(f"Etsy API returned HTTP {exc.code}: {body}")) from None
    finally:
        quota.record(SOURCE, status)
    if not isinstance(raw, dict) or not raw.get("success"):
        error = (raw or {}).get("error") if isinstance(raw, dict) else None
        raise RuntimeError(config.redact(f"Etsy API error: {json.dumps(error)[:300]}"))
    # The response has no fetch time; keep ours so updated_at can say how fresh it is.
    raw["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return raw


def parse(raw) -> list[dict]:
    """Map one raw API response to standard listing dicts, dropping unusable items."""
    if not isinstance(raw, dict):
        return []
    data = raw.get("data") or {}
    fetched_at = raw.get("fetched_at")
    cards = list(data.get("results") or []) + list(data.get("ads") or [])
    listings = (from_etsy(card, fetched_at) for card in cards)
    return [listing for listing in listings if listing]


def search(query: str, max_price: float | None = None, min_price: float | None = None) -> list[dict]:
    """Live Etsy search (vintage). Returns [] when nothing matches."""
    return parse(fetch(query))
