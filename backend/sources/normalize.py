"""
The FitFindr standard listing dict, and helpers every adapter uses to build one.

Every adapter in this package returns a list of these:

    {
        "id":         str,          # unique within its platform
        "title":      str,
        "price":      float,        # USD
        "size":       str | None,   # US sizing as the seller wrote it
        "platform":   str,          # depop | poshmark | mercari | etsy | ebay | fb_marketplace
        "url":        str,          # link back to the original listing page
        "image_url":  str | None,
        "condition":  str | None,   # optional
        "updated_at": str | None,   # optional, ISO 8601
    }

Rule: a value the API didn't give us is None. Never invent one.
A raw item with no title, price or url is not a usable listing and is dropped.

TODO (step 8): add `from_resale(raw_item)` once real Fashion Resale API
responses are recorded and we can see the actual field names.
"""

import re

PLATFORMS = ("depop", "poshmark", "mercari", "etsy", "ebay", "fb_marketplace")

REQUIRED_FIELDS = ("id", "title", "price", "size", "platform", "url", "image_url")
OPTIONAL_FIELDS = ("condition", "updated_at")


def parse_price(value) -> float | None:
    """'$24.99', '24.99', 24.99, {'amount': '24.99'} → 24.99. Anything else → None."""
    if isinstance(value, dict):
        value = value.get("amount") or value.get("value") or value.get("price")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def clean_str(value) -> str | None:
    """Strip a string; empty or missing → None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def make_listing(*, id, title, price, platform, url,
                 size=None, image_url=None, condition=None, updated_at=None) -> dict | None:
    """
    Build one standard listing dict, or return None if it isn't usable
    (no id, title, url or price). Callers drop the Nones.
    """
    listing = {
        "id": clean_str(id),
        "title": clean_str(title),
        "price": parse_price(price),
        "size": clean_str(size),
        "platform": clean_str(platform),
        "url": clean_str(url),
        "image_url": clean_str(image_url),
        "condition": clean_str(condition),
        "updated_at": clean_str(updated_at),
    }
    if not all(listing[k] for k in ("id", "title", "url", "platform")) or listing["price"] is None:
        return None
    listing["platform"] = listing["platform"].lower()
    return listing
