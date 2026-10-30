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

os.environ["RAPIDAPI_KEY"] = ""                 # never reach RapidAPI, however the tests are started
os.environ["FITFINDR_DATA_MODE"] = "fixtures"   # before config is imported

import config  # noqa: E402
from sources import fetch_candidates, resale  # noqa: E402
from sources.normalize import PLATFORMS, REQUIRED_FIELDS, OPTIONAL_FIELDS, from_resale  # noqa: E402
from tools import is_kids_item, search_listings, seller_voice, wants_kids  # noqa: E402

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
        self.assertEqual(first["category"], first_raw.get("category"))

    def test_ebay_comes_through_resale(self):
        ebay = [x for p in FIXTURES for x in resale.parse(load(p)) if x["platform"] == "ebay"]
        self.assertTrue(ebay, "no eBay listings in the resale fixtures")
        for item in ebay:
            self.assertIn("ebay.com", item["url"])
            self.assertIsNone(item["category"])   # eBay sends none; we don't invent one

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
        by_platform = {s["platform"]: s["status"] for s in statuses}
        for platform in ("depop", "poshmark", "mercari", "ebay", "etsy"):
            self.assertEqual(by_platform[platform], "fixtures")
        # host not subscribed: shown as Coming soon, never filled with anything
        self.assertEqual(by_platform["fb_marketplace"], "coming_soon")
        self.assertTrue([x for x in listings if x["platform"] == "etsy"])
        self.assertFalse([x for x in listings if x["platform"] == "fb_marketplace"])

    def test_price_ceiling_respected(self):
        results = search_listings("vintage graphic tee", max_price=30)
        self.assertTrue(results)
        self.assertTrue(all(r["price"] <= 30 for r in results))

    def test_no_match_returns_empty_list(self):
        self.assertEqual(search_listings("designer ballgown", size="XXS", max_price=5), [])

    def test_more_than_one_store(self):
        results = search_listings("vintage graphic tee", max_price=30)
        self.assertGreater(len({r["platform"] for r in results}), 1)
        # the best keyword match still comes first
        self.assertEqual(results[0], search_listings("vintage graphic tee", max_price=30)[0])

    def test_kids_items_filtered_unless_asked(self):
        adult = search_listings("corduroy pants")
        self.assertTrue(adult)
        self.assertFalse([r["title"] for r in adult if is_kids_item(r)])
        kids = search_listings("girls corduroy pants")
        self.assertTrue(any(is_kids_item(r) for r in kids))

    def test_kids_detection(self):
        self.assertTrue(is_kids_item({"title": "Corduroy Pants", "category": "Boys bottoms"}))
        self.assertTrue(is_kids_item({"title": "Girl’s Corduroy Pants", "category": None}))
        self.assertTrue(is_kids_item({"title": "Toddler 3T jeans"}))
        self.assertFalse(is_kids_item({"title": "Vintage Spice Girls Tee", "category": "Shirts"}))
        self.assertFalse(is_kids_item({"title": "Kid Cudi graphic tee"}))
        self.assertTrue(wants_kids("toddler jacket"))
        self.assertFalse(wants_kids("denim jacket"))

    def test_no_duplicates(self):
        results = search_listings("corduroy pants")
        keys = [(r["platform"], r["id"]) for r in results]
        self.assertEqual(len(keys), len(set(keys)))


class BuyerVoiceTest(unittest.TestCase):
    def test_seller_phrases_flagged(self):
        for text in ("I just listed these on Mercari!", "I'm selling this for $9",
                     "Shop my closet for more", "Available now in my shop"):
            self.assertTrue(seller_voice(text), text)

    def test_buyer_phrases_pass(self):
        for text in ("Just scored these for $9 on Mercari!", "Found this gem on Poshmark",
                     "Snagged it for $10 and I just bought two more"):
            self.assertEqual(seller_voice(text), [], text)


if __name__ == "__main__":
    unittest.main()
