"""
Unit tests for the Fashion Resale adapter, run on recorded real responses.

    cd backend
    python -m unittest discover -s tests -t . -v

No network: everything reads tests/fixtures/resale_*.json.
"""

import copy
import json
import os
import unittest

os.environ["FITFINDR_DATA_MODE"] = "fixtures"   # before config is imported

import config  # noqa: E402
from sources import fetch_candidates, resale  # noqa: E402
from sources.normalize import PLATFORMS, REQUIRED_FIELDS, OPTIONAL_FIELDS, from_resale  # noqa: E402
from tools import search_listings  # noqa: E402

FIXTURES = sorted(config.FIXTURES_DIR.glob("resale_*.json"))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ResaleParseTest(unittest.TestCase):
    def test_fixtures_exist(self):
        self.assertGreaterEqual(len(FIXTURES), 2, "record resale fixtures first")

    def test_every_listing_is_a_standard_dict(self):
        for path in FIXTURES:
            raw = load(path)
            listings = resale.parse(raw)
            with self.subTest(fixture=path.name):
                self.assertEqual(len(listings), len(raw["listings"]),
                                 "a real USD listing was dropped")
                for item in listings:
                    self.assertEqual(set(item), set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS))
                    self.assertIsInstance(item["price"], float)
                    self.assertGreaterEqual(item["price"], 0)
                    self.assertIn(item["platform"], PLATFORMS)
                    self.assertTrue(item["url"].startswith("https://"))
                    self.assertTrue(item["image_url"].startswith("https://"))
                    self.assertTrue(item["title"])

    def test_fields_copied_not_invented(self):
        raw = load(FIXTURES[0])
        first_raw, first = raw["listings"][0], resale.parse(raw)[0]
        self.assertEqual(first["id"], first_raw["id"])
        self.assertEqual(first["title"], first_raw["title"].strip())
        self.assertEqual(first["price"], float(first_raw["price"]))
        self.assertEqual(first["url"], first_raw["url"])
        self.assertEqual(first["image_url"], first_raw["images"][0])
        self.assertEqual(first["size"], first_raw.get("size"))
        self.assertEqual(first["condition"], first_raw.get("condition"))  # None when absent
        self.assertEqual(first["updated_at"], raw["search_metadata"]["scraped_at"])

    def test_missing_size_stays_none(self):
        for path in FIXTURES:
            for raw_item in load(path)["listings"]:
                if raw_item.get("size") in (None, ""):
                    self.assertIsNone(from_resale(raw_item)["size"])

    def test_non_usd_and_unusable_items_dropped(self):
        item = copy.deepcopy(load(FIXTURES[0])["listings"][0])
        self.assertIsNone(from_resale({**item, "currency": "EUR"}))
        self.assertIsNone(from_resale({**item, "url": None}))
        self.assertIsNone(from_resale({**item, "price": None}))
        self.assertIsNone(from_resale({**item, "platform": "grailed"}))
        self.assertEqual(resale.parse({}), [])
        self.assertEqual(resale.parse(None), [])


class SearchListingsFixturesTest(unittest.TestCase):
    def test_fixtures_mode_reads_only_fixtures(self):
        listings, statuses = fetch_candidates("anything")
        self.assertTrue(listings)
        self.assertTrue(all(s["status"] == "fixtures" for s in statuses))

    def test_price_ceiling_respected(self):
        results = search_listings("vintage graphic tee", max_price=30)
        self.assertTrue(results)
        self.assertTrue(all(r["price"] <= 30 for r in results))

    def test_no_match_returns_empty_list(self):
        self.assertEqual(search_listings("designer ballgown", size="XXS", max_price=5), [])

    def test_no_duplicates(self):
        results = search_listings("corduroy pants")
        keys = [(r["platform"], r["id"]) for r in results]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
