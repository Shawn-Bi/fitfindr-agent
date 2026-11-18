"""
Adapter for Facebook Marketplace via RapidAPI host $FB_MARKETPLACE_HOST.

Status (2026-10-19): NOT CONNECTED. One probe call (GET /, counted in
api_usage) returned HTTP 403 "You are not subscribed to this API.", and the
listing's docs are not public, so there is no recorded response to write the
parser against. The store stays "Coming soon" until the owner subscribes
(BLOCKERS.md #3 says exactly what to do); then one recording call and parse()
finish it.

Job once connected: turn one search query plus a US location into a list of
FitFindr standard listing dicts (see normalize.py). Marketplace is local, so
every search needs a location; the profile's `location` (default
DEFAULT_LOCATION) and the results-page Location filter supply it, and the
cache key includes it.

Hard quota of 50/month (stop at 40), counted by quota.py like the others.
"""

SOURCE = "FB_MARKETPLACE_HOST"                 # env var holding the RapidAPI host; quota key
PLATFORMS = ("fb_marketplace",)
FIXTURE_PREFIX = "fb"
ENABLED = False      # host not subscribed (HTTP 403): shown as "Coming soon"
PRICE_IN_QUERY = True
DEFAULT_LOCATION = "New York, NY"


def parse(raw) -> list[dict]:
    """Map one raw API response to standard listing dicts. Needs a recorded response first."""
    raise NotImplementedError("fb_marketplace.parse: no recorded response yet (host not subscribed)")


def fetch(query: str, max_price: float | None = None, min_price: float | None = None,
          location: str = DEFAULT_LOCATION) -> dict:
    """One live request → raw JSON. Not wired up: the host answers 403 (not subscribed)."""
    raise NotImplementedError("fb_marketplace.fetch: host not subscribed")


def search(query: str, max_price: float | None = None, min_price: float | None = None,
           location: str = DEFAULT_LOCATION) -> list[dict]:
    """Live search near `location`. Returns [] when nothing matches."""
    return parse(fetch(query, max_price=max_price, min_price=min_price, location=location))
