"""
Closet photo processing (PRD section 4, DECISIONS.md #11).

    main_jpeg, thumb_jpeg = process_photo(raw_bytes)

- Accepts JPG, PNG and HEIC/HEIF, up to 10 MB. Anything else raises
  PhotoError with a message a user can act on.
- Rotates by the EXIF orientation, then drops every bit of metadata
  (GPS, camera, timestamps) by re-encoding only the pixels.
- Main image: longest side 1600 px. Thumbnail: 400 px. Both JPEG.
"""

import io

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

import config

pillow_heif.register_heif_opener()

ALLOWED_FORMATS = {"JPEG": "JPG", "PNG": "PNG", "HEIF": "HEIC", "HEIC": "HEIC"}
Image.MAX_IMAGE_PIXELS = 60_000_000   # refuse decompression bombs


class PhotoError(ValueError):
    """The upload can't be used; the message is shown to the user as-is."""


def _megabytes(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def _clean_rgb(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    # A fresh image built from pixels only: no EXIF, GPS, ICC or XMP carried over.
    return Image.frombytes("RGB", img.size, img.tobytes())


def _jpeg(img: Image.Image, max_px: int) -> bytes:
    copy = img.copy()
    copy.thumbnail((max_px, max_px), Image.LANCZOS)
    out = io.BytesIO()
    copy.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def process_photo(data: bytes) -> tuple[bytes, bytes]:
    if not data:
        raise PhotoError("The photo is empty. Choose the file again.")
    if len(data) > config.MAX_PHOTO_BYTES:
        raise PhotoError(f"That photo is {_megabytes(len(data))}. Photos must be 10 MB or smaller.")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            raise PhotoError(f"{fmt or 'This'} files aren't supported. Use a JPG, PNG or HEIC photo.")
        img.load()
    except PhotoError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise PhotoError("We couldn't read that file as a photo. Use a JPG, PNG or HEIC photo.") from None
    clean = _clean_rgb(img)
    return _jpeg(clean, config.PHOTO_MAX_PX), _jpeg(clean, config.THUMB_MAX_PX)
