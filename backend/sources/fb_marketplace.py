"""
Adapter for Facebook Marketplace via RapidAPI host $FB_MARKETPLACE_HOST.

Job: turn one search query into a list of FitFindr standard listing dicts
(see normalize.py): id, title, price (float, USD), size, platform, url,
image_url, plus optional condition, updated_at. Missing values are None.

    search(query)  → live call (counted by quota.py), returns list[dict]
    parse(raw)     → raw JSON response → list[dict]; also used on fixtures

Fixtures for this adapter live in tests/fixtures/fb_<query>.json.
Wired up last. Hard quota of 50/month (stop at 40). City filtering is phase 2.
"""

SOURCE = "FB_MARKETPLACE_HOST"                 # env var holding the RapidAPI host; quota key
PLATFORMS = ("fb_marketplace",)
FIXTURE_PREFIX = "fb"


def parse(raw) -> list[dict]:
    """
    Map one raw API response to standard listing dicts, dropping unusable items.

    TODO: write once a real response is recorded in tests/fixtures/.
    """
    raise NotImplementedError("fb_marketplace.parse: no recorded response yet")


def search(query: str, max_price: float | None = None) -> list[dict]:
    """
    Live search. Must: quota.check(SOURCE) first, send RAPIDAPI_KEY and the
    host from $FB_MARKETPLACE_HOST as headers, quota.record(SOURCE, status) after,
    then return parse(response_json). Returns [] when nothing matches.

    TODO: implement in the integration pass. Never call without asking the user first.
    """
    raise NotImplementedError("fb_marketplace.search: live calls not wired up yet")
