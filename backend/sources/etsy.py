"""
Adapter for Etsy via RapidAPI host $ETSY_API_HOST.

Job: turn one search query into a list of FitFindr standard listing dicts
(see normalize.py): id, title, price (float, USD), size, platform, url,
image_url, plus optional condition, updated_at. Missing values are None.

    search(query)  → live call (counted by quota.py), returns list[dict]
    parse(raw)     → raw JSON response → list[dict]; also used on fixtures

Fixtures for this adapter live in tests/fixtures/etsy_<query>.json.
Wired up last, together with eBay and FB Marketplace. Follow Etsy API terms on image display, caching and attribution.
"""

SOURCE = "ETSY_API_HOST"                 # env var holding the RapidAPI host; quota key
PLATFORMS = ("etsy",)
FIXTURE_PREFIX = "etsy"
ENABLED = False      # not wired up yet: shown as "Coming soon" (DECISIONS.md #4)


def parse(raw) -> list[dict]:
    """
    Map one raw API response to standard listing dicts, dropping unusable items.

    TODO: write once a real response is recorded in tests/fixtures/.
    """
    raise NotImplementedError("etsy.parse: no recorded response yet")


def fetch(query: str, max_price: float | None = None) -> dict:
    """One live request → raw JSON. TODO: implement in the integration pass."""
    raise NotImplementedError("etsy.fetch: live calls not wired up yet")


def search(query: str, max_price: float | None = None) -> list[dict]:
    """
    Live search. Must: quota.check(SOURCE) first, send RAPIDAPI_KEY and the
    host from $ETSY_API_HOST as headers, quota.record(SOURCE, status) after,
    then return parse(response_json). Returns [] when nothing matches.

    TODO: implement in the integration pass. Never call without asking the user first.
    """
    raise NotImplementedError("etsy.search: live calls not wired up yet")
