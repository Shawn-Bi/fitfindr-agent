"""
Fill the test account's closet with the 10 photos in tests/closet_photos/
(DECISIONS.md #10), through the real API routes, so the upload path
(validation → resize → metadata strip → private bucket → row) is exercised
against Supabase.

    cd backend
    python scripts/seed_test_closet.py           # skips if the closet already has items
    python scripts/seed_test_closet.py --reset   # delete the test closet first

Only ever touches the test account from .env (TEST_USER_EMAIL / TEST_USER_PASSWORD).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FITFINDR_DATA_MODE", "fixtures")

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
from api.main import app  # noqa: E402

PHOTOS = config.ROOT / "tests" / "closet_photos"

ITEMS = {
    "02ce8d62e0f87087dd922ebd6c098f1b.jpg": dict(name="Grey pleated midi skirt", category="bottoms",
        colors=["grey"], style_tags=["minimalist", "pleated"], season=["spring", "fall"]),
    "115dc44b4f7254cba93478b7849739e3.jpg": dict(name="Lilac puff-sleeve blouse", category="tops",
        colors=["lilac"], style_tags=["cottagecore", "square neck"], season=["spring", "summer"]),
    "12fa64effa20ce9fcf45439becbbd121.jpg": dict(name="Rainbow stripe knit sweater", category="tops",
        colors=["pink", "blue", "yellow"], style_tags=["y2k", "knit"], season=["fall", "winter"]),
    "2955acd7638f64aec745982803e8d3e4.jpg": dict(name="Light-wash denim jacket", category="outerwear",
        colors=["light blue"], style_tags=["denim", "vintage"], season=["spring", "fall"], size="M"),
    "3205d3d88e64ff5e0a53c037f931eaf8.jpg": dict(name="Cream off-shoulder knit top", category="tops",
        colors=["cream"], style_tags=["minimalist", "knit"], season=["spring", "fall"]),
    "608228b92ba37751ca9a4b8a94cb2331.jpg": dict(name="Cream knit sweater dress", category="dresses",
        colors=["cream"], style_tags=["minimalist", "knit"], season=["fall", "winter"]),
    "6fb65058b860c58310c1cdd686307e40.jpg": dict(name="Camel zip-up knit jacket", category="outerwear",
        colors=["camel", "white"], style_tags=["minimalist"], season=["fall"], brand="Uniqlo"),
    "79ebdd254aebd4220d22f456a57fe383.jpg": dict(name="Black wide-leg trousers", category="bottoms",
        colors=["black"], style_tags=["minimalist", "wide-leg"], season=["spring", "fall", "winter"],
        size="W28"),
    "7bf53785634b6cce4f2412c958907013.jpg": dict(name="White puff-sleeve shirt", category="tops",
        colors=["white"], style_tags=["classic"], season=["spring", "summer"]),
    "a29c70492f84c2b51cd7a26151409efc.jpg": dict(name="Black leather jacket", category="outerwear",
        colors=["black"], style_tags=["grunge", "leather"], season=["fall", "winter"]),
}


def sign_in() -> str:
    email, password = os.getenv("TEST_USER_EMAIL"), os.getenv("TEST_USER_PASSWORD")
    if not email or not password:
        sys.exit("TEST_USER_EMAIL / TEST_USER_PASSWORD missing from .env "
                 "(run scripts/create_test_user.py first).")
    r = httpx.post(f"{config.SUPABASE_URL}/auth/v1/token?grant_type=password",
                   headers={"apikey": os.getenv("SUPABASE_ANON_KEY", "")},
                   json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        sys.exit(f"Test user sign-in failed: HTTP {r.status_code}")
    return r.json()["access_token"]


def main() -> None:
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {sign_in()}"}
    existing = client.get("/closet/items", headers=headers).json()
    if "--reset" in sys.argv:
        for item in existing["items"]:
            client.delete(f"/closet/items/{item['id']}", headers=headers)
        existing = {"items": []}
    if existing["items"]:
        print(f"Test closet already has {len(existing['items'])} items; use --reset to redo.")
        return

    for filename, fields in ITEMS.items():
        with (PHOTOS / filename).open("rb") as f:
            r = client.post("/closet/items", headers=headers,
                            data={"data": json.dumps(fields)},
                            files={"photo": (filename, f, "image/jpeg")})
        print(f"{r.status_code} {fields['name']}" + ("" if r.status_code == 201 else f" — {r.text[:200]}"))

    r = client.patch("/profile", headers=headers, json={
        "sizes": {"top": "M", "waist": "28", "length": "30", "shoe": "8"},
        "styles": ["Minimalist", "Vintage"], "colors": ["black", "cream"], "budget": 40})
    print(f"{r.status_code} profile")


if __name__ == "__main__":
    main()
