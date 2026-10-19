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
        "category":   str | None,   # optional, the store's own category label
        "brand":      str | None,   # optional (v2: fit-card value check)
        "listed_at":  str | None,   # optional, ISO 8601 date the seller listed it (v2: "Listed within")
    }

Rule: a value the API didn't give us is None. Never invent one.
A raw item with no title, price or url is not a usable listing and is dropped.

Per-API mappers live here too (from_resale, ...) so every field decision is in
one file.
"""

import re

PLATFORMS = ("depop", "poshmark", "mercari", "etsy", "ebay", "fb_marketplace")

REQUIRED_FIELDS = ("id", "title", "price", "size", "platform", "url", "image_url")
OPTIONAL_FIELDS = ("condition", "updated_at", "category", "brand", "listed_at")


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
                 size=None, image_url=None, condition=None, updated_at=None,
                 category=None, brand=None, listed_at=None) -> dict | None:
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
        "category": clean_str(category),
        "brand": clean_str(brand),
        "listed_at": clean_str(listed_at),
    }
    if not all(listing[k] for k in ("id", "title", "url", "platform")) or listing["price"] is None:
        return None
    listing["platform"] = listing["platform"].lower()
    return listing


# ─── Fashion Resale API (Depop, Poshmark, Mercari, eBay) ─────────────────────────
# Raw listing fields seen in recorded responses (tests/fixtures/resale_*.json):
#   id, platform, title, price (number), currency, size, brand, images (list),
#   url, seller {id}, category, created_at, condition (sometimes)
# eBay items have no size or category (both None). Only Poshmark sends
# created_at (the listing date), which becomes listed_at.
# Response-level: search_metadata.scraped_at = when the API fetched the data.

RESALE_PLATFORMS = ("depop", "poshmark", "mercari", "ebay")


def from_resale(item: dict, fetched_at: str | None = None) -> dict | None:
    """
    One Fashion Resale API listing → standard listing dict, or None if unusable.

    - Non-USD listings are dropped (FitFindr is US-only).
    - image_url is the first photo.
    - updated_at is the listing's own updated_at if the API sends one, else the
      time the API fetched it (search_metadata.scraped_at). created_at is the
      listing date, not an update time, so it isn't used.
    """
    if not isinstance(item, dict):
        return None
    currency = clean_str(item.get("currency"))
    if currency and currency.upper() != "USD":
        return None
    platform = (clean_str(item.get("platform")) or "").lower()
    if platform not in RESALE_PLATFORMS:
        return None
    images = item.get("images") or []
    image = images[0] if isinstance(images, list) and images else None
    if isinstance(image, dict):
        image = image.get("url")
    return make_listing(
        id=item.get("id"),
        title=item.get("title"),
        price=item.get("price"),
        platform=platform,
        url=item.get("url"),
        size=item.get("size"),
        image_url=image,
        condition=item.get("condition"),
        updated_at=item.get("updated_at") or fetched_at,
        category=item.get("category"),
        brand=item.get("brand"),
        listed_at=item.get("created_at"),
    )
