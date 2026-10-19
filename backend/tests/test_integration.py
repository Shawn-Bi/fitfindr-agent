"""
Integration tests against the real Supabase project, as the test account.
Skipped unless FITFINDR_INTEGRATION=1. Never calls RapidAPI (fixtures mode)
and never calls the model.

    cd backend
    $env:FITFINDR_INTEGRATION=1; python -m unittest tests.test_integration -v

Needs TEST_USER_EMAIL / TEST_USER_PASSWORD in .env and a seeded closet
(scripts/seed_test_closet.py).
"""

import io
import json
import os
import unittest

os.environ["FITFINDR_DATA_MODE"] = "fixtures"

import httpx  # noqa: E402
from PIL import Image  # noqa: E402

import config  # noqa: E402

ENABLED = os.getenv("FITFINDR_INTEGRATION") == "1"


@unittest.skipUnless(ENABLED, "set FITFINDR_INTEGRATION=1 to run against Supabase")
class SupabaseIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from api.main import app
        from scripts.seed_test_closet import sign_in
        cls.client = TestClient(app)
        cls.headers = {"Authorization": f"Bearer {sign_in()}"}

    def test_closet_photos_are_private_resized_and_clean(self):
        items = self.client.get("/closet/items", headers=self.headers).json()["items"]
        self.assertTrue(items, "seed the test closet first")
        item = items[0]
        self.assertTrue(item["photo_url"].startswith(item["user_id"] + "/"))
        # signed URL works and serves a clean, resized JPEG
        img_bytes = httpx.get(item["photo"], timeout=20).content
        img = Image.open(io.BytesIO(img_bytes))
        self.assertEqual(img.format, "JPEG")
        self.assertLessEqual(max(img.size), config.PHOTO_MAX_PX)
        self.assertEqual(dict(img.getexif()), {})
        thumb = Image.open(io.BytesIO(httpx.get(item["thumb"], timeout=20).content))
        self.assertLessEqual(max(thumb.size), config.THUMB_MAX_PX)
        # the bucket is private: the plain public URL doesn't serve it
        public = f"{config.SUPABASE_URL}/storage/v1/object/public/closet-photos/{item['photo_url']}"
        self.assertGreaterEqual(httpx.get(public, timeout=20).status_code, 400)

    def test_rls_hides_rows_from_anonymous_clients(self):
        anon = os.getenv("SUPABASE_ANON_KEY", "")
        r = httpx.get(f"{config.SUPABASE_URL}/rest/v1/closet_items?select=id",
                      headers={"apikey": anon, "Authorization": f"Bearer {anon}"}, timeout=20)
        self.assertEqual(r.json(), [])
        r = httpx.get(f"{config.SUPABASE_URL}/rest/v1/api_usage?select=*",
                      headers={"apikey": anon, "Authorization": f"Bearer {anon}"}, timeout=20)
        self.assertEqual(r.json(), [])

    def test_save_and_unsave(self):
        listing = json.loads((config.FIXTURES_DIR / "resale_flannel_shirt.json")
                             .read_text(encoding="utf-8"))["listings"][0]
        from sources.resale import parse
        item = parse({"listings": [listing]})[0]
        r = self.client.post("/saved", headers=self.headers, json={"listing": item})
        self.assertEqual(r.status_code, 201, r.text)
        saved = self.client.get("/saved", headers=self.headers).json()["items"]
        self.assertIn(item["id"], [s["listing_id"] for s in saved])
        r = self.client.delete(f"/saved/{item['platform']}/{item['id']}", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        saved = self.client.get("/saved", headers=self.headers).json()["items"]
        self.assertNotIn(item["id"], [s["listing_id"] for s in saved])

    def test_home_and_matches(self):
        home = self.client.get("/home", headers=self.headers).json()
        self.assertFalse(home["locked"])
        self.assertTrue(home["picks"])
        item = self.client.get("/closet/items", headers=self.headers).json()["items"][0]
        matches = self.client.get(f"/closet/items/{item['id']}/matches", headers=self.headers).json()
        self.assertIn("matches", matches)

    def test_bad_photo_rejected_with_reason(self):
        r = self.client.post("/closet/items", headers=self.headers,
                             data={"data": json.dumps({"name": "x", "category": "tops", "colors": ["red"]})},
                             files={"photo": ("notes.txt", b"hello", "text/plain")})
        self.assertEqual(r.status_code, 422)
        self.assertIn("JPG, PNG or HEIC", r.json()["detail"])

    def test_missing_color_rejected(self):
        r = self.client.post("/closet/items", headers=self.headers,
                             data={"data": json.dumps({"name": "x", "category": "tops", "colors": []})},
                             files={"photo": ("a.jpg", b"x", "image/jpeg")})
        self.assertEqual(r.status_code, 422)
        self.assertIn("color", r.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
