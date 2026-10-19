"""
Offline tests for the web API, photo processing, the quota counter and the
search helpers. No network, no model: the two model tools are patched, the
quota uses MemoryStore and Supabase is never called.

    cd backend
    python -m unittest discover -s tests -t . -v
"""

import io
import os
import unittest
from unittest import mock

os.environ["FITFINDR_DATA_MODE"] = "fixtures"   # before config is imported

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import config  # noqa: E402
import sources  # noqa: E402
from api import catalog  # noqa: E402
from api.images import PhotoError, process_photo  # noqa: E402
from api.main import app, search_limiter  # noqa: E402
from api.ratelimit import RateLimiter  # noqa: E402
from generate import ModelUnavailable  # noqa: E402
from sources import quota, resale  # noqa: E402
from tools import _parse_outfit, size_matches  # noqa: E402

OUTFIT = {"text": "Wear it with wide-leg khakis.", "item_ids": []}


def _image_bytes(fmt="JPEG", size=(2400, 1800), exif=None, mode="RGB") -> bytes:
    img = Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128))
    out = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    img.save(out, format=fmt, **kwargs)
    return out.getvalue()


class SearchRouteTest(unittest.TestCase):
    def setUp(self):
        search_limiter._hits.clear()
        self.client = TestClient(app)

    @mock.patch("agent.create_fit_card", return_value="Scored this tee for $12 on Depop!")
    @mock.patch("agent.suggest_outfit", return_value=OUTFIT)
    def test_guest_search_returns_results_styling_and_stores(self, outfit, card):
        r = self.client.post("/search", json={"q": "vintage graphic tee under $30"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["results"])
        self.assertTrue(all(x["price"] <= 30 for x in body["results"]))
        self.assertTrue(all(x["image_url"] and x["url"] for x in body["results"]))
        self.assertEqual(body["styling"]["text"], OUTFIT["text"])
        self.assertEqual(body["fit_card"], "Scored this tee for $12 on Depop!")
        self.assertFalse(body["personalized"])
        self.assertEqual([c["key"] for c in body["chips"]], ["q", "price"])
        stores = {s["platform"]: s["status"] for s in body["stores"]}
        self.assertEqual(stores["etsy"], "coming_soon")
        self.assertEqual(stores["fb_marketplace"], "coming_soon")
        self.assertEqual(stores["ebay"], "live")
        outfit.assert_called_once()

    @mock.patch("agent.create_fit_card")
    @mock.patch("agent.suggest_outfit")
    def test_empty_search_skips_model_and_offers_relax(self, outfit, card):
        r = self.client.post("/search", json={"q": "designer ballgown size XXS under $5"})
        body = r.json()
        self.assertEqual(body["results"], [])
        self.assertIn("found nothing", body["empty"]["message"])
        labels = [o["label"] for o in body["empty"]["relax"]]
        self.assertEqual(labels, ["Remove size XXS", "Raise budget to $10"])
        outfit.assert_not_called()
        card.assert_not_called()

    @mock.patch("agent.create_fit_card", return_value="card")
    @mock.patch("agent.suggest_outfit", return_value=OUTFIT)
    def test_removing_price_chip_searches_without_it(self, outfit, card):
        body = self.client.post("/search", json={"q": "vintage graphic tee under $5",
                                                 "no_price": True}).json()
        self.assertIsNone(body["parsed"]["max_price"])
        self.assertTrue(any(x["price"] > 5 for x in body["results"]))

    @mock.patch("agent.suggest_outfit", side_effect=ModelUnavailable("bad key"))
    def test_model_down_still_returns_results(self, outfit):
        body = self.client.post("/search", json={"q": "flannel shirt"}).json()
        self.assertTrue(body["results"])
        self.assertIn("Your search results still work", body["styling"]["unavailable"])
        self.assertIsNone(body["fit_card"])

    @mock.patch("agent.create_fit_card", return_value="card")
    @mock.patch("agent.suggest_outfit", return_value=OUTFIT)
    def test_rate_limit_per_ip(self, outfit, card):
        for _ in range(config.SEARCHES_PER_MINUTE):
            self.assertEqual(self.client.post("/search", json={"q": "nothing matches zzz"}).status_code, 200)
        r = self.client.post("/search", json={"q": "nothing matches zzz"})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)

    def test_validation_error_is_a_readable_string(self):
        r = self.client.post("/search", json={"q": ""})
        self.assertEqual(r.status_code, 422)
        self.assertIsInstance(r.json()["detail"], str)

    def test_user_routes_need_login(self):
        for method, path in (("get", "/closet/items"), ("get", "/saved"), ("get", "/profile"),
                             ("get", "/home"), ("delete", "/account")):
            self.assertEqual(getattr(self.client, method)(path).status_code, 401, path)

    def test_stores_endpoint(self):
        body = self.client.get("/stores").json()
        self.assertEqual(len(body["stores"]), 6)
        self.assertEqual(sum(s["status"] == "live" for s in body["stores"]), 4)


class PhotoTest(unittest.TestCase):
    def test_resizes_and_makes_thumbnail(self):
        main, thumb = process_photo(_image_bytes())
        self.assertEqual(max(Image.open(io.BytesIO(main)).size), config.PHOTO_MAX_PX)
        self.assertEqual(max(Image.open(io.BytesIO(thumb)).size), config.THUMB_MAX_PX)

    def test_strips_gps_and_other_metadata(self):
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"                           # Make
        exif[0x8825] = {1: "N", 2: (40.0, 44.0, 0.0)}           # GPSInfo
        raw = _image_bytes(exif=exif.tobytes())
        self.assertIn(b"PhoneMaker", raw)
        main, thumb = process_photo(raw)
        for out in (main, thumb):
            self.assertNotIn(b"PhoneMaker", out)
            self.assertNotIn(b"Exif", out)
            self.assertEqual(dict(Image.open(io.BytesIO(out)).getexif()), {})

    def test_png_with_transparency_becomes_jpeg(self):
        main, _ = process_photo(_image_bytes("PNG", (500, 500), mode="RGBA"))
        self.assertEqual(Image.open(io.BytesIO(main)).format, "JPEG")

    def test_rejects_too_big(self):
        with self.assertRaisesRegex(PhotoError, "10 MB or smaller"):
            process_photo(b"\xff" * (config.MAX_PHOTO_BYTES + 1))

    def test_rejects_unsupported_and_garbage(self):
        with self.assertRaisesRegex(PhotoError, "GIF files aren't supported"):
            process_photo(_image_bytes("GIF", (50, 50)))
        with self.assertRaisesRegex(PhotoError, "couldn't read"):
            process_photo(b"not an image at all")


class QuotaTest(unittest.TestCase):
    def setUp(self):
        self.store = quota.MemoryStore()
        quota.use_store(self.store)

    def tearDown(self):
        quota.use_store(quota.SupabaseStore())

    def test_pauses_at_stop_line(self):
        for _ in range(39):
            quota.record("RESALE_API_HOST", 200)
        quota.check("RESALE_API_HOST")   # 39: still fine
        quota.record("RESALE_API_HOST", 200)
        with self.assertRaises(quota.QuotaPaused) as ctx:
            quota.check("RESALE_API_HOST")
        self.assertEqual(ctx.exception.resumes, quota.resumes_on())
        self.assertEqual(quota.status("RESALE_API_HOST", "ebay")["status"], "paused")

    def test_unreadable_counter_fails_closed(self):
        broken = mock.Mock(get=mock.Mock(side_effect=OSError("down")))
        quota.use_store(broken)
        with self.assertRaises(quota.QuotaUnknown):
            quota.check("RESALE_API_HOST")

    def test_resumes_on_first_of_next_month(self):
        import datetime as dt
        self.assertEqual(quota.resumes_on(dt.datetime(2026, 12, 15)), "2027-01-01")
        self.assertEqual(quota.resumes_on(dt.datetime(2026, 10, 19)), "2026-11-01")


class LiveModeSourcesTest(unittest.TestCase):
    """Live mode with every network edge patched: no call leaves the process."""

    def setUp(self):
        self.store = quota.MemoryStore()
        quota.use_store(self.store)
        self.mode = mock.patch.object(config, "DATA_MODE", "live")
        self.mode.start()

    def tearDown(self):
        self.mode.stop()
        quota.use_store(quota.SupabaseStore())

    def test_paused_store_without_cache_is_skipped_not_filled(self):
        self.store.counts[(quota.host_name("RESALE_API_HOST"), quota.month_start())] = 40
        with mock.patch("sources.cache.get", return_value=None), \
             mock.patch("urllib.request.urlopen", side_effect=AssertionError("live call!")):
            listings, statuses = sources.fetch_candidates("vintage graphic tee")
        self.assertEqual(listings, [])
        ebay = next(s for s in statuses if s["platform"] == "ebay")
        self.assertEqual(ebay["status"], "paused")
        self.assertEqual(ebay["resumes"], quota.resumes_on())

    def test_cache_hit_serves_without_live_call(self):
        raw = __import__("json").loads(
            (config.FIXTURES_DIR / "resale_flannel_shirt.json").read_text(encoding="utf-8"))
        with mock.patch("sources.cache.get", return_value=raw), \
             mock.patch.object(resale, "fetch", side_effect=AssertionError("live call!")):
            listings, statuses = sources.fetch_candidates("flannel shirt")
        self.assertTrue(listings)
        self.assertEqual({s["status"] for s in statuses if s["platform"] == "depop"}, {"cached"})

    def test_live_fetch_is_cached(self):
        raw = {"listings": [], "search_metadata": {}}
        with mock.patch("sources.cache.get", return_value=None), \
             mock.patch("sources.cache.put") as put, \
             mock.patch.object(resale, "fetch", return_value=raw) as fetch:
            sources.fetch_candidates("flannel shirt", max_price=20)
        fetch.assert_called_once_with("flannel shirt", max_price=20)
        put.assert_called_once()


class CatalogTest(unittest.TestCase):
    profile = {"sizes": {"top": "M", "waist": "30", "shoe": "8.5"}, "budget": 40}

    def test_profile_fills_size_and_budget_as_chips(self):
        parsed, chips = catalog.resolve_filters("graphic tee", self.profile)
        self.assertEqual((parsed["size"], parsed["max_price"]), ("M", 40.0))
        self.assertEqual([(c["key"], c["from_profile"]) for c in chips],
                         [("q", False), ("price", True), ("size", True)])

    def test_query_beats_profile_and_waist_for_bottoms(self):
        parsed, _ = catalog.resolve_filters("corduroy pants under $25", self.profile)
        self.assertEqual((parsed["size"], parsed["max_price"]), ("30", 25.0))
        parsed, _ = catalog.resolve_filters("chunky boots", self.profile)
        self.assertEqual(parsed["size"], "8.5")

    def test_removed_chips_stay_removed(self):
        parsed, chips = catalog.resolve_filters("graphic tee", self.profile, no_size=True, no_price=True)
        self.assertEqual((parsed["size"], parsed["max_price"]), (None, None))
        self.assertEqual([c["key"] for c in chips], ["q"])

    def test_raised_budget(self):
        self.assertEqual(catalog.raised_budget(30), 45)
        self.assertEqual(catalog.raised_budget(25), 40)
        self.assertEqual(catalog.raised_budget(5), 10)

    def test_listing_category(self):
        cases = {"Vintage Levi's denim jacket": "outerwear", "Black corduroy pants": "bottoms",
                 "2003 tour graphic tee": "tops", "Red plaid flannel shirt": "tops",
                 "Dr Martens combat boots": "shoes", "Slip dress": "dresses"}
        for title, category in cases.items():
            self.assertEqual(catalog.listing_category({"title": title}), category, title)

    def test_home_picks_pair_with_closet(self):
        closet = [{"id": "1", "name": "Baggy jeans", "category": "bottoms", "colors": ["black"],
                   "style_tags": ["streetwear"]}]
        picks = catalog.home_picks(sources.recent_pool(), closet, {"budget": 30})
        self.assertTrue(picks)
        for p in picks:
            self.assertLessEqual(p["listing"]["price"], 30)
            self.assertIn("baggy jeans", p["reason"])
            self.assertIn(catalog.listing_category(p["listing"]), ("tops", "outerwear", "shoes"))

    def test_item_matches_are_other_categories(self):
        owned = {"id": "1", "name": "White tank", "category": "tops", "colors": ["white"],
                 "style_tags": ["minimal"]}
        for m in catalog.item_matches(sources.recent_pool(), owned):
            self.assertNotEqual(catalog.listing_category(m["listing"]), "tops")

    def test_size_matching(self):
        self.assertTrue(size_matches("M", "S/M"))
        self.assertFalse(size_matches("M", "XL"))
        self.assertFalse(size_matches("S", "US 9"))
        self.assertTrue(size_matches("30", "W30 L32"))
        self.assertTrue(size_matches("30", "30x32"))
        self.assertFalse(size_matches("30", "W32"))


class OutfitParseTest(unittest.TestCase):
    items = [{"id": "w_001", "name": "Baggy jeans"}, {"id": "w_002", "name": "White tank"}]

    def test_json(self):
        out = _parse_outfit('{"text": "Wear with jeans.", "item_ids": ["w_001", "nope"]}', self.items)
        self.assertEqual(out, {"text": "Wear with jeans.", "item_ids": ["w_001"]})

    def test_fenced_json(self):
        out = _parse_outfit('```json\n{"text": "Hi", "item_ids": ["w_002"]}\n```', self.items)
        self.assertEqual(out["item_ids"], ["w_002"])

    def test_plain_text_falls_back_to_names(self):
        out = _parse_outfit("Try it with your baggy jeans and boots.", self.items)
        self.assertEqual(out["item_ids"], ["w_001"])
        self.assertTrue(out["text"].startswith("Try it"))


class RateLimiterTest(unittest.TestCase):
    def test_window(self):
        rl = RateLimiter(2, window=60)
        self.assertTrue(rl.allow("a", now=0)[0])
        self.assertTrue(rl.allow("a", now=1)[0])
        self.assertFalse(rl.allow("a", now=2)[0])
        self.assertTrue(rl.allow("b", now=2)[0])
        self.assertTrue(rl.allow("a", now=61)[0])


if __name__ == "__main__":
    unittest.main()
