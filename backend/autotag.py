"""
Photo auto-tagging (A3): Gemini vision looks at a closet photo and suggests
the item's details, for the user to check and edit before saving.

    suggestion = tag_photo(jpeg_bytes, default_gender="women")
    → {"name": "Black leather moto jacket", "category": "outerwear",
       "colors": ["black"], "style_tags": ["grunge", "leather"],
       "season": ["fall", "winter"], "gender": "women"}

Every value is checked against the same vocabularies the closet form uses;
anything outside them is dropped rather than shown. Nothing is saved here.
"""

import io
import json
import re

from PIL import Image

import generate

CATEGORIES = ("tops", "bottoms", "outerwear", "dresses", "shoes", "accessories")
COLORS = ("black", "white", "cream", "beige", "grey", "navy", "denim blue", "light blue", "brown",
          "camel", "burgundy", "rust", "red", "pink", "lilac", "yellow", "olive", "green")
TAGS = ("vintage", "streetwear", "minimalist", "y2k", "grunge", "cottagecore", "classic", "preppy",
        "boho", "athleisure", "western", "romantic", "denim", "baggy", "fitted", "oversized", "knit",
        "leather", "pleated", "wide-leg", "cropped", "tailored", "linen", "silk", "wool", "graphic")
SEASONS = ("spring", "summer", "fall", "winter")
GENDERS = ("women", "men", "unisex")

PROMPT = (
    "You are tagging one clothing item from a photo for a personal closet app.\n"
    "Answer with JSON only:\n"
    '{"name": "<2-5 word plain name, colour + fabric/cut + type, e.g. Light-wash denim jacket>",\n'
    f' "category": "<one of: {", ".join(CATEGORIES)}>",\n'
    f' "colors": ["<1-3 of: {", ".join(COLORS)}>"],\n'
    f' "style_tags": ["<0-4 of: {", ".join(TAGS)}>"],\n'
    f' "season": ["<0-4 of: {", ".join(SEASONS)}>"],\n'
    f' "gender": "<one of: {", ".join(GENDERS)}: who the piece is cut for>"}}\n'
    "Describe only the main garment. If you can't tell a field, leave it out."
)


def _model_image(jpeg: bytes, max_px: int = 768) -> bytes:
    """A smaller copy for the model: fewer tokens, same answer."""
    img = Image.open(io.BytesIO(jpeg))
    img.thumbnail((max_px, max_px))
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=85)
    return out.getvalue()


def _pick(values, allowed, limit):
    out = []
    for v in values or []:
        v = str(v).strip().lower()
        v = {"gray": "grey", "tan": "camel", "ivory": "cream", "off-white": "cream", "maroon": "burgundy",
             "blue": "denim blue", "purple": "lilac", "autumn": "fall"}.get(v, v)
        if v in allowed and v not in out:
            out.append(v)
    return out[:limit]


def parse_tags(raw: str, default_gender: str | None = None) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    name = re.sub(r"\s+", " ", str(data.get("name") or "")).strip()[:80]
    category = str(data.get("category") or "").strip().lower()
    gender = str(data.get("gender") or "").strip().lower()
    out = {
        "name": name[:1].upper() + name[1:] if name else None,
        "category": category if category in CATEGORIES else None,
        "colors": _pick(data.get("colors"), COLORS, 3),
        "style_tags": _pick(data.get("style_tags"), TAGS, 4),
        "season": _pick(data.get("season"), SEASONS, 4),
        "gender": gender if gender in GENDERS else (default_gender if default_gender in GENDERS else None),
    }
    return out


def tag_photo(jpeg: bytes, default_gender: str | None = None) -> dict:
    """Suggested fields for one processed (metadata-free) JPEG. Raises ModelUnavailable on failure."""
    raw = generate.generate(PROMPT, json_mode=True, temperature=0.2,
                            image=(_model_image(jpeg), "image/jpeg"))
    return parse_tags(raw, default_gender)
