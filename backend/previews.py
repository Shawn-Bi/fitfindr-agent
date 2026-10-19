"""
"AI preview" pictures for planned outfit pieces that have no real listing at
all (P8, after the strict pick and the "Closest find" both came up empty).

    path = previews.get_or_create(piece, gender)   # storage path or None
    urls = previews.signed(paths)                   # path → short-lived URL

One clean flat-lay product image on white per piece description, generated
once with config.IMAGE_MODEL and stored in Supabase Storage under
ai-previews/<hash>.png, so the same piece (same name, colours, fabric,
gender) is never generated twice. The UI labels it "AI preview — not a real
listing".

When the model has no image quota (the free tier answers HTTP 429), the
feature switches itself off for an hour and callers fall back to the closest
cached listing photo. Nothing here ever raises.
"""

import hashlib
import logging
import time

import config

log = logging.getLogger("fitfindr.previews")
FOLDER = "ai-previews"
_off_until = 0.0


def _key(piece: dict, gender: str | None) -> str:
    text = "|".join([piece.get("name") or "", ",".join(piece.get("colors") or []),
                     piece.get("material") or "", gender or ""]).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def prompt(piece: dict, gender: str | None) -> str:
    who = {"women": "women's ", "men": "men's "}.get(gender or "", "")
    colours = ", ".join(piece.get("colors") or [])
    return (f"A clean e-commerce product photo of one {who}{piece['name']}"
            + (f" in {colours}" if colours else "")
            + (f", {piece['material']}" if piece.get("material") else "")
            + ". Flat-lay, neatly arranged, on a plain pure white background, soft even light, "
              "seen from directly above, the whole garment in frame. No person, no mannequin, "
              "no text, no logo, no watermark, no props.")


def available() -> bool:
    import supa
    return bool(config.IMAGE_MODEL) and supa.configured() and time.monotonic() >= _off_until


def get_or_create(piece: dict, gender: str | None) -> str | None:
    """The stored preview's path (generating it the first time), or None if unavailable."""
    global _off_until
    if not available():
        return None
    import generate
    import supa

    path = f"{FOLDER}/{_key(piece, gender)}.png"
    try:
        if supa.service().signed_urls([path], expires_in=60):
            return path                                     # generated before
    except Exception as exc:  # noqa: BLE001
        log.warning("preview lookup failed: %s", config.redact(exc))
    try:
        data, mime = generate.generate_image(prompt(piece, gender))
    except Exception as exc:  # noqa: BLE001 — no quota, model off: use the listing-photo fallback
        _off_until = time.monotonic() + 3600
        log.warning("AI preview unavailable for an hour: %s", config.redact(exc)[:160])
        return None
    try:
        supa.service().upload(path, data, content_type=mime)
    except Exception as exc:  # noqa: BLE001
        log.warning("preview upload failed: %s", config.redact(exc))
        return None
    return path


def signed(paths: list[str], expires_in: int = 3600) -> dict[str, str]:
    paths = [p for p in paths if p]
    if not paths:
        return {}
    import supa
    try:
        return supa.service().signed_urls(paths, expires_in=expires_in)
    except Exception as exc:  # noqa: BLE001
        log.warning("preview signing failed: %s", config.redact(exc))
        return {}
