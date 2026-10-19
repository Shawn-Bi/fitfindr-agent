"""
Offline tests for the v2 hand-test fixes: Etsy adapter, soft profile sizes
and broadening, the fixtures-mode empty state, quick (filter) searches and
/search/style, closet-outfit pictures (Closest find, AI preview, fallback),
and the US-retail profile sizes. No network.

    cd backend
    python -m unittest tests.test_fixes -v
"""

import json
import os
import unittest
from unittest import mock

os.environ["FITFINDR_DATA_MODE"] = "fixtures"   # before config is imported
os.environ["FITFINDR_EMBEDDINGS"] = "0"
os.environ["FITFINDR_PLANNER"] = "rules"

from fastapi.testclient import TestClient  # noqa: E402

import attributes  # noqa: E402
import config  # noqa: E402
import previews  # noqa: E402
import stylist  # noqa: E402
import tools  # noqa: E402
from api import catalog  # noqa: E402
from api.main import app, quick_limiter, search_limiter, style_limiter  # noqa: E402
from sources import etsy, recent_pool  # noqa: E402
from sources.normalize import from_etsy, REQUIRED_FIELDS  # noqa: E402

ETSY_RAW = json.loads((config.FIXTURES_DIR / "etsy_white_denim_pants.json").read_text(encoding="utf-8"))


def listing(title, platform="depop", size=None, price=20, image="https://img/x.jpg", id_=None):
    return {"id": id_ or title, "title": title, "price": float(price), "size": size, "platform": platform,
            "url": f"https://example.com/{abs(hash(title))}", "image_url": image, "condition": None,
            "updated_at": None, "category": None, "brand": None, "listed_at": None}


class EtsyAdapterTest(unittest.TestCase):
    def test_recorded_response_maps_to_standard_listings(self):
        items = etsy.parse(ETSY_RAW)
        self.assertGreaterEqual(len(items), 40)
        for item in items:
            self.assertTrue(set(REQUIRED_FIELDS) <= set(item))
            self.assertEqual(item["platform"], "etsy")
            self.assertIsInstance(item["price"], float)
            self.assertTrue(item["url"].startswith("https://www.etsy.com/listing/"))
            self.assertNotIn("?", item["url"])
            self.assertIsNone(item["size"])          # search cards state no size: never invented
            self.assertIsNone(item["condition"])

    def test_digital_downloads_and_other_currencies_are_dropped(self):
        card = ETSY_RAW["data"]["results"][0]
        self.assertIsNotNone(from_etsy(card))
        self.assertIsNone(from_etsy({**card, "isDigitalDownload": True}))
        self.assertIsNone(from_etsy({**card, "price": {"amount": 10, "currency": "EUR"}}))
        self.assertIsNone(from_etsy({**card, "url": None}))

    def test_query_asks_for_vintage_once(self):
        self.assertEqual(etsy.etsy_query("white denim pants"), "vintage white denim pants")
        self.assertEqual(etsy.etsy_query("Vintage band tee"), "Vintage band tee")

    def test_fabric_and_patterns_are_not_clothing(self):
        self.assertTrue(tools.is_not_clothing({"title": "Cotton White Stretch Denim Fabric, Heavy Weight"}))
        self.assertTrue(tools.is_not_clothing({"title": "Wide leg pants PDF pattern, sewing pattern"}))
        self.assertFalse(tools.is_not_clothing({"title": "Vintage 90s Levis 550 White Denim Jean"}))
        self.assertFalse(tools.is_not_clothing({"title": "Linen fabric shirt, oversized"}))


class SoftSizeAndBroadeningTest(unittest.TestCase):
    def test_profile_size_orders_but_never_excludes(self):
        pool = [listing("White denim jeans", size="L"), listing("White denim jeans 2", size=None, platform="ebay"),
                listing("White denim jeans 3", size="28")]
        ranked = tools.filter_and_rank(pool, "white denim jeans", soft_sizes=["28"], patient=False)
        self.assertEqual([r["size"] for r in ranked], ["28", None, "L"])

    def test_profile_sizes_are_soft_in_resolve_filters(self):
        parsed, chips = catalog.resolve_filters("white denim pants", {"sizes": {"bottoms_waist": ["28"]},
                                                                      "gender": "women"})
        self.assertEqual(parsed["sizes"], ["28"])
        self.assertTrue(parsed["size_soft"])
        parsed, _ = catalog.resolve_filters("white denim pants", {}, sizes=["28"])
        self.assertFalse(parsed["size_soft"])

    def test_core_query_and_synonyms(self):
        self.assertEqual(tools.core_query("womens ecru ribbed turtleneck"), ("womens ecru turtleneck", ["ribbed"]))
        self.assertEqual(tools.core_query("white denim pants"), ("white denim pants", []))
        self.assertIn("white denim jeans", tools.synonym_queries("white denim pants"))
        self.assertIn("womens ecru mock neck", tools.synonym_queries("womens ecru turtleneck"))

    def test_broadening_steps_and_message_never_show_mismatches(self):
        fetched = []
        pools = {
            "womens ecru ribbed turtleneck": [listing("Ecru ribbed turtleneck sweater")],
            "womens ecru turtleneck": [listing("Women's cream turtleneck"), listing("Olive turtleneck"),
                                       listing("Ecru turtleneck dress")],
            "womens ecru mock neck": [listing("Ivory mock neck knit top"), listing("Cream mock neck"),
                                      listing("Black mock neck")],
        }

        def fake_fetch(q, max_price=None, min_price=None, live=True):
            fetched.append((q, max_price, live))
            return [dict(x) for x in pools.get(q, [])], [{"platform": "depop", "status": "fixtures"}]

        with mock.patch("tools.fetch_candidates", side_effect=fake_fetch):
            results, statuses, broadened = tools.search_broadened(
                "womens ecru ribbed turtleneck", max_price=40, patient=False)
        titles = [r["title"] for r in results]
        self.assertEqual(broadened["steps"], ["adjectives", "synonyms"])
        self.assertIn("dropped “ribbed”", broadened["message"])
        self.assertIn("“womens ecru mock neck”", broadened["message"])
        self.assertEqual(len(results), 4)
        for bad in ("Olive turtleneck", "Black mock neck", "Ecru turtleneck dress"):
            self.assertNotIn(bad, titles)            # colour and category mismatches stay out
        self.assertEqual([f[0] for f in fetched],
                         ["womens ecru ribbed turtleneck", "womens ecru turtleneck", "womens ecru mock neck"])

    def test_broadening_drops_a_set_size_then_widens_price(self):
        pool = [listing("White jeans", size="L", price=20), listing("White jeans b", size="M", price=50),
                listing("White jeans c", size="L", price=55), listing("White jeans d", size="S", price=58)]
        with mock.patch("tools.fetch_candidates",
                        side_effect=lambda q, max_price=None, min_price=None, live=True:
                        ([dict(x) for x in pool], [])):
            results, _, broadened = tools.search_broadened("white jeans", max_price=40, sizes=["XS"], patient=False)
        self.assertEqual(broadened["steps"], ["synonyms", "size", "price"])
        self.assertEqual(broadened["max_price"], 60.0)
        self.assertTrue(broadened["dropped_size"])
        self.assertEqual(len(results), 4)
        self.assertIn("raised the budget to $60", broadened["message"])

    def test_enough_results_means_no_broadening(self):
        pool = [listing(f"White denim jeans {i}") for i in range(5)]
        with mock.patch("tools.fetch_candidates", return_value=(pool, [])) as fetch:
            results, _, broadened = tools.search_broadened("white denim jeans", patient=False)
        self.assertIsNone(broadened)
        self.assertEqual(fetch.call_count, 1)

    def test_broadening_live_fetches_are_capped(self):
        calls = []

        def fake_fetch(q, max_price=None, min_price=None, live=True):
            calls.append(live)
            return [], [{"platform": "depop", "status": "active" if live else "skipped"}]

        with mock.patch("config.DATA_MODE", "live"), mock.patch("config.BROADEN_LIVE_FETCHES", 1), \
                mock.patch("tools.fetch_candidates", side_effect=fake_fetch):
            tools.search_broadened("womens ecru ribbed turtleneck", max_price=40, patient=False)
        self.assertEqual(calls[0], True)                         # the search itself
        self.assertEqual(calls[1:].count(True), 1)               # one extra live search, the rest cache-only


class SearchRouteFixesTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        for limiter in (search_limiter, quick_limiter, style_limiter):
            limiter._hits.clear()

    def test_fixtures_empty_state_says_development_data(self):
        body = self.client.post("/search", json={"q": "designer ballgown size XXS under $5"}).json()
        self.assertEqual(body["empty"]["title"], "Development data doesn't include this search")
        with mock.patch("config.DATA_MODE", "live"):
            self.assertEqual(catalog.empty_title(config.DATA_MODE), "No matches yet")

    @mock.patch("agent.suggest_outfit", side_effect=AssertionError("no model call on a filter change"))
    def test_quick_search_has_results_and_no_model_calls(self, _):
        body = self.client.post("/search", json={"q": "flannel shirt", "style": False,
                                                 "stores": ["poshmark"]}).json()
        self.assertTrue(body["results"])
        self.assertEqual({r["platform"] for r in body["results"]}, {"poshmark"})
        self.assertIsNone(body["styling"])
        self.assertTrue(body["styling_deferred"])
        self.assertEqual(body["agent"]["planner"], "none")

    def test_style_route_styles_one_listing(self):
        item = etsy.parse(ETSY_RAW)[0]
        with mock.patch("api.main.suggest_outfit", return_value={"text": "Wear it with loafers.", "item_ids": []}), \
             mock.patch("api.main.create_fit_card_full",
                        return_value={"caption": "Scored these on Etsy!", "verdict": None}):
            body = self.client.post("/search/style", json={"q": "white denim pants", "listing": item}).json()
        self.assertEqual(body["styling"]["text"], "Wear it with loafers.")
        self.assertEqual(body["fit_card"], "Scored these on Etsy!")

    def test_style_route_degrades_when_the_model_is_down(self):
        item = etsy.parse(ETSY_RAW)[0]
        with mock.patch("api.main.suggest_outfit", side_effect=RuntimeError("down")):
            body = self.client.post("/search/style", json={"q": "x", "listing": item}).json()
        self.assertTrue(body["styling"]["unavailable"])

    def test_broadened_notice_is_in_the_response(self):
        body = self.client.post("/search", json={"q": "white denim pants", "style": False}).json()
        self.assertIn("broadened", body)
        for r in body["results"]:
            self.assertNotEqual(attributes.clear_mismatch(attributes.query_attributes("white denim pants"), r),
                                "colour")


class OutfitPicturesTest(unittest.TestCase):
    skirt = {"id": "i1", "name": "Black midi skirt", "category": "bottoms", "colors": ["black"]}

    def plan(self, pieces):
        return stylist.parse_plan(json.dumps({"title": "T", "pieces": pieces}), self.skirt, "women")

    def test_closest_find_needs_category_gender_and_colour_family(self):
        piece = {"category": "outerwear", "colors": ["camel"], "name": "Camel wool coat", "material": "wool"}
        pool = [listing("Men's camel wool coat"), listing("Black wool coat"), listing("Tan trench coat"),
                listing("Camel sweater")]
        found = stylist.closest_find(piece, pool, "women", patient=False)
        self.assertEqual(found["title"], "Tan trench coat")   # tan = camel; men's, black and a sweater are out
        self.assertIsNone(stylist.closest_find(piece, pool[:2], "women", patient=False))

    def test_every_piece_gets_a_picture(self):
        plan = self.plan([{"slot": "top", "name": "Lilac silk blouse", "colors": ["lilac"], "material": "silk"},
                          {"slot": "shoes", "name": "Black leather loafers", "colors": ["black"]}])
        pool = [listing("Black leather loafers women", price=200), listing("Navy cotton tee")]
        none = json.dumps({"choices": [{"piece": 0, "index": None}, {"piece": 1, "index": None}]})
        with mock.patch("generate.generate", return_value=none), \
             mock.patch("previews.get_or_create", return_value="ai-previews/abc.png") as gen:
            out = stylist.build_outfit(self.skirt, {"gender": "women"}, (10, 40), plan=plan, pool=pool)
        blouse, loafers = out["pieces"]
        self.assertEqual(loafers["kind"], "closest")          # over budget, but same type and colour
        self.assertEqual(blouse["kind"], "ai_preview")        # nothing lilac to show
        self.assertEqual(blouse["preview_path"], "ai-previews/abc.png")
        gen.assert_called_once()
        # no image model: the closest cached photo in the same category, said honestly
        with mock.patch("generate.generate", return_value=none), \
             mock.patch("previews.get_or_create", return_value=None):
            out = stylist.build_outfit(self.skirt, {"gender": "women"}, (10, 40), plan=plan, pool=pool)
        blouse = out["pieces"][0]
        self.assertEqual(blouse["kind"], "closest")
        self.assertEqual(blouse["listing"]["title"], "Navy cotton tee")
        self.assertEqual(blouse["closest_note"], "Similar piece in a different colour")

    def test_idea_only_when_the_pool_has_nothing_in_that_category(self):
        plan = self.plan([{"slot": "bag", "name": "Black leather shoulder bag", "colors": ["black"]},
                          {"slot": "top", "name": "White tee", "colors": ["white"]}])
        with mock.patch("generate.generate", return_value="{}"), mock.patch("previews.get_or_create", return_value=None):
            out = stylist.build_outfit(self.skirt, {"gender": "women"}, (10, 40), plan=plan, pool=[])
        self.assertEqual([p["kind"] for p in out["pieces"]], ["idea", "idea"])

    def test_previews_switch_off_after_a_quota_error(self):
        piece = {"name": "Cream trousers", "colors": ["cream"], "material": "wool"}
        with mock.patch("previews.available", return_value=True), \
             mock.patch("supa.service") as service, \
             mock.patch("generate.generate_image", side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")):
            service.return_value.signed_urls.return_value = {}
            self.assertIsNone(previews.get_or_create(piece, "women"))
        self.assertGreater(previews._off_until, 0)
        previews._off_until = 0.0

    def test_preview_prompt_is_a_flat_lay_on_white(self):
        text = previews.prompt({"name": "Cream wide-leg trousers", "colors": ["cream"], "material": "wool"}, "women")
        self.assertIn("women's Cream wide-leg trousers", text)
        self.assertIn("white background", text)
        self.assertIn("No person", text)


class ProfileSizesTest(unittest.TestCase):
    def test_sizes_summary_for_the_stylist(self):
        text = catalog.sizes_summary({"size_range": ["petite"], "tops": ["S"], "bottoms_waist": ["28"],
                                      "bottoms_inseam": ["Short"]}, "women")
        self.assertEqual(text, "Petite; tops & dresses S; waist 28; inseam Short")

    def test_profile_prefs_carry_size_range(self):
        prefs = catalog.profile_prefs({"gender": "women", "sizes": {"size_range": ["plus"], "tops": ["1X"]}})
        self.assertEqual(prefs["size_range"], "plus")
        self.assertIn("1X", prefs["sizes_text"])

    def test_profile_patch_validates_new_groups(self):
        from api.main import Sizes
        sizes = Sizes(size_range=["petite"], tops=["XS", "00"], bottoms_inseam=["Short"], men_neck=["15.5"])
        self.assertEqual(sizes.tops, ["XS", "00"])
        with self.assertRaises(ValueError):
            Sizes(bottoms_inseam=["30"])                 # inseam is Short / Regular / Long now

    def test_recent_pool_includes_etsy_fixtures(self):
        self.assertTrue(any(x["platform"] == "etsy" for x in recent_pool()))


if __name__ == "__main__":
    unittest.main()
