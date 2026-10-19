"""
Adapter for eBay via RapidAPI host $EBAY_API_HOST.

Job: turn one search query into a list of FitFindr standard listing dicts
(see normalize.py): id, title, price (float, USD), size, platform, url,
image_url, plus optional condition, updated_at. Missing values are None.

    search(query)  → live call (counted by quota.py), returns list[dict]
    parse(raw)     → raw JSON response → list[dict]; also used on fixtures

Fixtures for this adapter live in tests/fixtures/ebay_<query>.json.
Wired up last. Quota is only 20/month (stop at 15). Follow eBay API terms on image display, caching and attribution.
"""

SOURCE = "EBAY_API_HOST"                 # env var holding the RapidAPI host; quota key
PLATFORMS = ("ebay",)
FIXTURE_PREFIX = "ebay"


def parse(raw) -> list[dict]:
    """
    Map one raw API response to standard listing dicts, dropping unusable items.

    TODO: write once a real response is recorded in tests/fixtures/.
    """
    raise NotImplementedError("ebay.parse: no recorded response yet")


def search(query: str) -> list[dict]:
    """
    Live search. Must: quota.check(SOURCE) first, send RAPIDAPI_KEY and the
    host from $EBAY_API_HOST as headers, quota.record(SOURCE, status) after,
    then return parse(response_json). Returns [] when nothing matches.

    TODO: implement in the integration pass. Never call without asking the user first.
    """
    raise NotImplementedError("ebay.search: live calls not wired up yet")
