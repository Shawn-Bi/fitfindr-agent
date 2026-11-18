"""
Offline tests for the v2 features: the tool-choosing agent (A1), semantic
ranking and mismatch rules (A4), the buyer's verdict (B1), the stylist (B2),
profile v2 and filters (B3, B4), auto-tagging (A3), judge parsing and traces
(A2). No network: model replies are scripted, embeddings are off or faked.

    cd backend
    python -m unittest tests.test_v2 -v
"""

import json
import os
import unittest
from unittest import mock

os.environ["RAPIDAPI_KEY"] = ""                 # never reach RapidAPI, however the tests are started
os.environ["FITFINDR_DATA_MODE"] = "fixtures"   # before config is imported
os.environ["FITFINDR_EMBEDDINGS"] = "0"
os.environ["FITFINDR_PLANNER"] = "rules"

from fastapi.testclient import TestClient  # noqa: E402
from google.genai import types  # noqa: E402

import agent  # noqa: E402
import attributes  # noqa: E402
import autotag  # noqa: E402
import judge  # noqa: E402
import observe  # noqa: E402
import ranking  # noqa: E402
import stylist  # noqa: E402
import tools  # noqa: E402
from api import catalog  # noqa: E402
from api.main import app, search_limiter  # noqa: E402
from generate import ModelUnavailable  # noqa: E402
from sources import recent_pool  # noqa: E402
from utils.data_loader import get_example_wardrobe  # noqa: E402

OUTFIT = {"text": "Wear it with your baggy jeans.", "item_ids": ["w_001"]}
CARD = {"caption": "Scored it on eBay for $12!", "verdict": {"verdict": "Fair deal", "reasons": ["ok"]}}


def direct(**args):
    return tools.search_with_status(**args)[0]


def call(name, **args):
    return types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))])


def text(t):
    return types.Content(role="model", parts=[types.Part(text=t)])


@mock.patch("agent.create_fit_card_full", return_value=CARD)
@mock.patch("agent.suggest_outfit", return_value=OUTFIT)
class AgentRulesTest(unittest.TestCase):
    def run_agent(self, q):
        return agent.run_agent(q, get_example_wardrobe(), search=direct, planner="rules")

    def test_happy_path(self, outfit, card):
        s = self.run_agent("vintage graphic tee under $30")
        self.assertEqual([st["tool"] for st in s["steps"]], ["search_listings", "suggest_outfit", "create_fit_card"])
        self.assertEqual(s["fit_card"], CARD["caption"])
        self.assertEqual(s["fit_verdict"]["verdict"], "Fair deal")
        self.assertIs(outfit.call_args[0][0], s["selected_item"])

    def test_vague_request_asks_one_question_and_never_searches(self, outfit, card):
        for q in ("something nice", "an outfit for a party", "cute stuff"):
            s = self.run_agent(q)
            self.assertEqual([st["tool"] for st in s["steps"]], ["ask_user"], q)
            self.assertTrue(s["clarify"]["question"].endswith("?"))
            self.assertEqual(s["search_results"], [])
        outfit.assert_not_called()

    def test_specific_requests_are_not_vague(self, outfit, card):
        for q in ("levi's 501", "vintage", "black", "corduroy", "something nice in black"):
            self.assertFalse(agent.is_vague(q), q)

    def test_auto_relax_drops_size_first_and_tells_the_user(self, outfit, card):
        s = self.run_agent("denim jacket size XXS under $50")
        self.assertEqual([st["tool"] for st in s["steps"]][:2], ["search_listings", "relax_search"])
        self.assertEqual(s["relaxed"]["dropped"], "size")
        self.assertIn("size XXS", s["relaxed"]["message"])
        self.assertTrue(s["search_results"])
        self.assertIsNotNone(s["fit_card"])

    def test_auto_relax_raises_budget_when_there_is_no_size(self, outfit, card):
        s = self.run_agent("denim jacket under $3")
        self.assertEqual(s["relaxed"]["dropped"], "budget")
        self.assertEqual(s["parsed"]["max_price"], 5.0)
        self.assertIn("raised the budget to $5", s["relaxed"]["message"])

    def test_relaxes_only_once_then_stops_without_styling(self, outfit, card):
        s = self.run_agent("designer ballgown size XXS under $5")
        self.assertEqual([st["tool"] for st in s["steps"]], ["search_listings", "relax_search"])
        self.assertIn("No listings matched", s["error"])
        outfit.assert_not_called()
        card.assert_not_called()

    def test_model_down_keeps_results(self, outfit, card):
        outfit.side_effect = ModelUnavailable("down")
        s = self.run_agent("flannel shirt")
        self.assertTrue(s["search_results"])
        self.assertEqual(s["styling_error"], agent.STYLING_UNAVAILABLE)


@mock.patch("agent.create_fit_card_full", return_value=CARD)
@mock.patch("agent.suggest_outfit", return_value=OUTFIT)
class AgentGeminiTest(unittest.TestCase):
    def run_scripted(self, q, replies):
        with mock.patch("generate.generate_with_tools", side_effect=list(replies)) as model:
            s = agent.run_agent(q, get_example_wardrobe(), search=direct, planner="gemini")
        return s, model

    def test_model_picks_each_tool(self, outfit, card):
        s, model = self.run_scripted("vintage graphic tee under $30", [
            call("search_listings", description="vintage graphic tee"),
            call("suggest_outfit", listing_index=2),
            call("create_fit_card"),
        ])
        self.assertEqual(s["planner"], "gemini")
        self.assertEqual([st["by"] for st in s["steps"]], ["gemini"] * 3)
        self.assertIs(s["selected_item"], s["search_results"][2])
        self.assertEqual(model.call_count, 3)

    def test_guard_refuses_out_of_order_calls(self, outfit, card):
        s, _ = self.run_scripted("flannel shirt", [
            call("suggest_outfit", listing_index=0),     # nothing searched yet
            call("ask_user", question="Which colour?"),  # request isn't vague
            call("search_listings"),
            call("suggest_outfit", listing_index=0),
            call("create_fit_card"),
        ])
        refused = [st for st in s["steps"] if "refused" in st["result"]]
        self.assertEqual(len(refused), 2)
        self.assertIsNone(s["clarify"])
        self.assertIsNotNone(s["fit_card"])

    def test_model_asks_when_vague(self, outfit, card):
        s, _ = self.run_scripted("something nice", [
            call("ask_user", question="What type of piece are you after?", suggestions=["jeans", "a coat"]),
        ])
        self.assertEqual(s["clarify"]["question"], "What type of piece are you after?")
        self.assertEqual(s["clarify"]["suggestions"], ["jeans", "a coat"])

    def test_model_stopping_early_is_finished_by_the_rules(self, outfit, card):
        s, _ = self.run_scripted("flannel shirt", [call("search_listings"), text("Here you go!")])
        self.assertEqual(s["planner"], "gemini+rules")
        self.assertEqual([st["by"] for st in s["steps"]], ["gemini", "rules (fallback)", "rules (fallback)"])
        self.assertIsNotNone(s["fit_card"])

    def test_model_failure_falls_back_to_rules(self, outfit, card):
        s, _ = self.run_scripted("flannel shirt", [ModelUnavailable("bad key")])
        self.assertEqual(s["planner"], "rules")
        self.assertIsNotNone(s["fit_card"])

    def test_step_cap(self, outfit, card):
        loop = [call("relax_search")] * 20       # always refused: nothing to relax yet
        with mock.patch("config.AGENT_MAX_STEPS", 3):
            s, model = self.run_scripted("flannel shirt", loop)
        self.assertEqual(model.call_count, 3)
        self.assertEqual(s["planner"], "gemini+rules")
        self.assertIsNotNone(s["fit_card"])


class RankingTest(unittest.TestCase):
    def test_white_denim_pants_never_returns_corduroy_or_olive(self):
        results, _ = tools.search_with_status("white denim pants", limit=20)
        for r in results:
            title = r["title"].lower()
            self.assertNotIn("corduroy", title)
            self.assertNotIn("olive", title)
            self.assertIn(attributes.listing_category(r), ("bottoms", None))   # e.g. "white denim Wranglers"

    def test_mismatch_rules(self):
        wanted = attributes.query_attributes("white denim pants")
        cases = {"Olive corduroy pants": "colour", "White corduroy pants": "fabric",
                 "White denim jacket": "category", "Ivory wide-leg denim trousers": None,
                 "Levi's 501 jeans": None}
        for title, why in cases.items():
            self.assertEqual(attributes.clear_mismatch(wanted, {"title": title}), why, title)

    def test_semantic_order_with_fake_embeddings(self):
        items = [{"id": str(i), "title": t, "platform": "ebay", "price": 10}
                 for i, t in enumerate(["Plain jeans", "White denim pants", "Denim shorts"])]

        def fake_embed(texts, **_):
            return [[1.0, 0.0] if "white" in t.lower() else [0.0, 1.0] for t in texts]
        with mock.patch("generate.embed", side_effect=fake_embed):
            ranked, info = ranking.rerank("white denim pants", items)
        self.assertEqual(info["method"], "semantic")
        self.assertEqual(ranked[0]["title"], "White denim pants")

    def test_gender_filter(self):
        mens = {"title": "Men's flannel shirt"}
        womens = {"title": "Women's flannel shirt"}
        plain = {"title": "Flannel shirt"}
        self.assertFalse(attributes.gender_ok(mens, "women"))
        self.assertTrue(attributes.gender_ok(womens, "women"))
        self.assertTrue(attributes.gender_ok(plain, "women"))
        self.assertFalse(attributes.gender_ok(womens, "men"))
        self.assertTrue(attributes.gender_ok(mens, None))
        self.assertTrue(attributes.gender_ok({"title": "Beastie Boys tee"}, "women"))
        results, _ = tools.search_with_status("flannel shirt", prefs={"gender": "women"}, limit=40)
        self.assertFalse([r for r in results if attributes.listing_gender(r) == "men"])

    def test_filters(self):
        base, _ = tools.search_with_status("vintage graphic tee", limit=60)
        self.assertTrue(base)
        nwt, _ = tools.search_with_status("vintage graphic tee", filters={"conditions": ["new_with_tags"]}, limit=60)
        self.assertTrue(nwt)
        self.assertTrue(all(attributes.condition_bucket(r["condition"]) == "new_with_tags" for r in nwt))
        black, _ = tools.search_with_status("vintage graphic tee", filters={"colors": ["black"]}, limit=60)
        self.assertTrue(all("black" in attributes.colors_in(r["title"]) for r in black))
        depop, _ = tools.search_with_status("vintage graphic tee", filters={"stores": ["depop"]}, limit=60)
        self.assertEqual({r["platform"] for r in depop}, {"depop"})
        ranged, _ = tools.search_with_status("vintage graphic tee", min_price=10, max_price=20, limit=60)
        self.assertTrue(all(10 <= r["price"] <= 20 for r in ranged))

    def test_listed_within_keeps_only_dated_listings(self):
        with mock.patch("tools._listed_within", side_effect=lambda item, days: bool(item.get("listed_at"))):
            recent, _ = tools.search_with_status("denim jacket", filters={"within_days": 30}, limit=60)
        self.assertTrue(recent)
        self.assertTrue(all(r["listed_at"] for r in recent))


class FitCardTest(unittest.TestCase):
    item = {"title": "Levi's 501 jeans", "price": 30.0, "platform": "ebay", "condition": "Pre-owned - Good"}

    def parse(self, data):
        return tools.parse_fit_card(json.dumps(data), self.item, "good")

    def test_confident_estimate_gives_percent_off(self):
        out = self.parse({"caption": "Scored these!", "retail_estimate": {"low": 60, "high": 80, "confidence": "high"},
                          "verdict": "Worth it", "reasons": ["57% under retail", "A classic"]})
        self.assertEqual(out["verdict"]["retail"]["pct_off"], 57)
        self.assertEqual(out["verdict"]["verdict"], "Worth it")

    def test_low_confidence_is_unknown_not_a_number(self):
        out = self.parse({"caption": "x", "retail_estimate": {"low": 500, "high": 900, "confidence": "low"},
                          "era": {"label": "1970s", "confidence": "low"}, "verdict": "Skip"})
        self.assertIsNone(out["verdict"]["retail"])
        self.assertIsNone(out["verdict"]["era"])

    def test_condition_comes_from_the_store_and_bad_verdict_is_dropped(self):
        out = self.parse({"caption": "x", "verdict": "Amazing!!", "condition_notes": "Light wear."})
        self.assertIsNone(out["verdict"]["verdict"])
        self.assertEqual(out["verdict"]["condition"]["label"], "Good")
        self.assertEqual(out["verdict"]["condition"]["stated"], "Pre-owned - Good")

    def test_unreadable_answer_keeps_a_caption(self):
        out = tools.parse_fit_card("not json", self.item, None)
        self.assertEqual(out["caption"], "not json")
        self.assertIsNone(out["verdict"])


class StylistTest(unittest.TestCase):
    skirt = {"id": "1", "name": "Grey pleated midi skirt", "category": "bottoms", "colors": ["grey"],
             "style_tags": ["minimalist"], "gender": "women"}

    def plan_json(self, pieces):
        return json.dumps({"title": "Soft grey", "concept": "Calm", "palette": ["grey", "cream"],
                           "occasion": "Office", "notes": {"colour": "c", "proportion": "p", "fabric": "f"},
                           "pieces": pieces})

    def test_plan_never_repeats_the_items_category(self):
        plan = stylist.parse_plan(self.plan_json([
            {"slot": "bottom", "name": "Black trousers"},             # same category: dropped
            {"slot": "top", "name": "Cream cashmere sweater", "colors": ["cream"], "material": "cashmere"},
            {"slot": "shoes", "name": "Black leather loafers", "search": "black loafers"},
        ]), self.skirt, "women")
        self.assertEqual([p["slot"] for p in plan["pieces"]], ["top", "shoes"])
        self.assertTrue(all(p["search"].startswith("women's") for p in plan["pieces"]))

    def test_unusable_plan_falls_back_to_template(self):
        self.assertIsNone(stylist.parse_plan(self.plan_json([{"slot": "bottom", "name": "x"}]), self.skirt, "women"))
        with mock.patch("generate.generate", side_effect=ModelUnavailable("down")):
            plan = stylist.plan_outfit(self.skirt, {"gender": "women"}, (None, 40))
        self.assertEqual(plan["planner"], "template")
        self.assertNotIn("bottom", [p["slot"] for p in plan["pieces"]])

    def test_dress_gets_no_top_or_bottom(self):
        dress = {**self.skirt, "category": "dresses"}
        plan = stylist.template_plan(dress, "women")
        self.assertTrue(set(p["slot"] for p in plan["pieces"]) <= {"outerwear", "shoes", "bag"})

    def test_hard_rules(self):
        piece = {"category": "tops", "colors": ["black"], "material": None, "name": "Black tee"}
        ok = {"title": "Vintage black band tee", "price": 20, "image_url": "https://x", "platform": "ebay"}
        self.assertTrue(stylist.fits_rules(ok, piece, "women", (None, 40)))
        self.assertFalse(stylist.fits_rules({**ok, "title": "Men's black band tee"}, piece, "women", (None, 40)))
        self.assertFalse(stylist.fits_rules({**ok, "title": "Black jeans"}, piece, "women", (None, 40)))
        self.assertFalse(stylist.fits_rules({**ok, "title": "Red band tee"}, piece, "women", (None, 40)))
        self.assertFalse(stylist.fits_rules({**ok, "price": 90}, piece, "women", (None, 40)))
        self.assertFalse(stylist.fits_rules({**ok, "image_url": None}, piece, "women", (None, 40)))

    def test_build_outfit_shows_only_listings_the_judge_kept(self):
        plan = stylist.parse_plan(self.plan_json([
            {"slot": "top", "name": "Vintage graphic tee", "colors": ["black"], "search": "black graphic tee"},
            {"slot": "outerwear", "name": "Blue denim jacket", "colors": ["blue"], "material": "denim"},
        ]), self.skirt, "women")
        pick = json.dumps({"choices": [{"piece": 0, "index": 0, "reason": "Right tee"},
                                       {"piece": 1, "index": None}]})
        with mock.patch("generate.generate", return_value=pick):
            out = stylist.build_outfit(self.skirt, {"gender": "women"}, (None, 60), plan=plan, pool=recent_pool())
        top, jacket = out["pieces"]
        self.assertIsNotNone(top["listing"])
        self.assertEqual(attributes.listing_category(top["listing"]), "tops")
        self.assertEqual(top["match_reason"], "Right tee")
        self.assertEqual(top["kind"], "listing")
        # not chosen → the closest real listing of the same category, gender and colour family
        self.assertEqual(jacket["kind"], "closest")
        self.assertEqual(attributes.listing_category(jacket["listing"]), "outerwear")
        self.assertIn("blue", attributes.colors_in(jacket["listing"]["title"]) | {"light blue"})
        self.assertIsNone(jacket["match_reason"])
        self.assertTrue(jacket["search"])
        self.assertEqual(out["live_calls"], 0)
        # the model sometimes drops the {"choices": ...} wrapper; the picks must survive that
        bare = json.dumps([{"piece": 0, "index": 0, "reason": "Right tee"}, {"piece": 1, "index": None}])
        with mock.patch("generate.generate", return_value=bare):
            out = stylist.build_outfit(self.skirt, {"gender": "women"}, (None, 60), plan=plan, pool=recent_pool())
        self.assertIsNotNone(out["pieces"][0]["listing"])

    def test_stale_listings_are_hidden_in_live_mode(self):
        outfit = {"pieces": [{"name": "x", "listing": {"id": "1"}, "found_at": "2020-01-01T00:00:00+00:00"}]}
        with mock.patch("config.DATA_MODE", "live"):
            hidden = stylist.hide_stale(outfit)
        self.assertIsNone(hidden["pieces"][0]["listing"])
        self.assertTrue(hidden["pieces"][0]["expired"])
        self.assertIsNotNone(stylist.hide_stale(outfit)["pieces"][0]["listing"])   # fixtures: unchanged


class ProfileAndCatalogTest(unittest.TestCase):
    def test_legacy_sizes_are_read_into_lists(self):
        sizes = catalog.normalize_sizes({"top": "M", "waist": "28", "length": "30", "shoe": "US 8"})
        self.assertEqual(sizes["tops"], ["M"])
        self.assertEqual(sizes["bottoms_waist"], ["28"])
        self.assertEqual(sizes["shoes"], ["8"])

    def test_sizes_per_category(self):
        sizes = {"tops": ["S", "4"], "bottoms_waist": ["28"], "shoes": ["8"],
                 "men_tops": ["L"], "men_neck": ["15.5"], "men_waist": ["32"], "men_shoes": ["10"]}
        self.assertEqual(catalog.sizes_for("wide leg trousers", sizes, "women"), ["28", "4"])
        self.assertEqual(catalog.sizes_for("slip dress", sizes, "women"), ["S", "4"])
        self.assertEqual(catalog.sizes_for("slip dress", sizes, "men"), [])
        self.assertEqual(catalog.sizes_for("graphic tee", sizes, "women"), ["S", "4"])
        self.assertEqual(catalog.sizes_for("oxford shirt", sizes, "men"), ["L", "15.5"])
        self.assertEqual(catalog.sizes_for("chinos", sizes, "men"), ["32"])
        self.assertEqual(catalog.sizes_for("loafers", sizes, "both"), ["8", "10"])
        self.assertEqual(catalog.sizes_for("tote bag", sizes, "women"), [])

    def test_older_size_lists_are_read_into_the_new_groups(self):
        old = {"tops": ["S"], "dresses": ["6"], "bottoms": ["M"], "bottoms_inseam": ["28", "32"]}
        sizes = catalog.normalize_sizes(old, "women")
        self.assertEqual(sizes["tops"], ["S", "6", "M"])
        self.assertEqual(sizes["bottoms_inseam"], ["Short", "Regular"])
        men = catalog.normalize_sizes({"tops": ["L"], "bottoms_waist": ["32"]}, "men")
        self.assertEqual((men["men_tops"], men["men_waist"], men["tops"]), (["L"], ["32"], []))

    def test_petite_sizes_match_petite_labels(self):
        sizes = {"size_range": ["petite"], "tops": ["S"]}
        wanted = catalog.sizes_for("turtleneck", sizes, "women")
        self.assertTrue(tools.size_matches(wanted[1], "SP") or "SP" in wanted)
        self.assertTrue(any(tools.size_matches(s, "PS") for s in wanted))

    def test_budget_range_from_profile(self):
        parsed, chips = catalog.resolve_filters("graphic tee", {"budget": 40, "budget_min": 10})
        self.assertEqual((parsed["min_price"], parsed["max_price"]), (10.0, 40.0))
        self.assertEqual(chips[1]["label"], "$10–$40")
        parsed, _ = catalog.resolve_filters("graphic tee", {"budget": 40}, sizes=["L"], max_price=25)
        self.assertEqual((parsed["sizes"], parsed["max_price"]), (["L"], 25.0))

    def test_location_filter_is_never_faked(self):
        self.assertFalse(catalog.FILTER_SUPPORT["location"]["available"])
        self.assertIn("Facebook Marketplace", catalog.FILTER_SUPPORT["location"]["note"])


class SmallPartsTest(unittest.TestCase):
    def test_autotag_keeps_only_known_values(self):
        out = autotag.parse_tags(json.dumps({"name": "black leather jacket", "category": "Outerwear",
                                             "colors": ["Black", "gray", "sparkly"], "style_tags": ["grunge", "zzz"],
                                             "season": ["autumn"], "gender": "robot"}), "women")
        self.assertEqual(out, {"name": "Black leather jacket", "category": "outerwear", "colors": ["black", "grey"],
                               "style_tags": ["grunge"], "season": ["fall"], "gender": "women"})
        self.assertIsNone(autotag.parse_tags("nope")["category"])

    def test_judge_scores_out_of_range_are_none(self):
        scores = judge._scores({"style_match": {"score": 4, "reason": "ok"}, "proportion": {"score": 9}},
                               judge.OUTFIT_DIMS)
        self.assertEqual(scores["style_match"]["score"], 4)
        self.assertIsNone(scores["proportion"]["score"])
        self.assertEqual(judge.average(scores), 4.0)

    def test_trace_row_is_short(self):
        steps = [{"tool": "search_listings", "result": {"top": list(range(50)), "note": "x" * 999}}]
        r = observe.row("search", "q", None, {"calls": 3, "est_cost_usd": 0.0001}, steps, "gemini", "completed")
        self.assertEqual(r["model_calls"], 3)
        self.assertLessEqual(len(r["steps"][0]["result"]["top"]), 6)
        self.assertLess(len(r["steps"][0]["result"]["note"]), 200)

    @mock.patch("generate._get_client")
    @mock.patch("generate._wait_for_slot")
    @mock.patch("generate._check_budget")
    @mock.patch("time.sleep")
    def test_per_day_quota_is_not_retried(self, sleep, _budget, _slot, _client):
        import generate
        err = RuntimeError("429 RESOURCE_EXHAUSTED quotaId: EmbedContentRequestsPerDayPerUserPerProjectPerModel")
        do_call = mock.Mock(side_effect=err)
        with self.assertRaises(ModelUnavailable):
            generate._request("m", do_call)
        self.assertEqual(do_call.call_count, 1)
        sleep.assert_not_called()


class ApiV2Test(unittest.TestCase):
    def setUp(self):
        search_limiter._hits.clear()
        self.client = TestClient(app)

    def test_vague_search_returns_a_question(self):
        body = self.client.post("/search", json={"q": "something nice"}).json()
        self.assertTrue(body["clarify"]["question"])
        self.assertEqual(body["results"], [])
        self.assertIsNone(body["empty"])

    @mock.patch("agent.create_fit_card_full", return_value=CARD)
    @mock.patch("agent.suggest_outfit", return_value=OUTFIT)
    def test_filters_are_applied_and_reported(self, outfit, card):
        body = self.client.post("/search", json={"q": "vintage graphic tee", "stores": ["depop", "ebay"],
                                                 "min_price": 5, "max_price": 30,
                                                 "conditions": ["new_with_tags"]}).json()
        self.assertTrue(body["results"])
        self.assertTrue({r["platform"] for r in body["results"]} <= {"depop", "ebay"})
        self.assertTrue(all(5 <= r["price"] <= 30 for r in body["results"]))
        self.assertEqual(body["filters"]["stores"], ["depop", "ebay"])
        self.assertFalse(body["filter_support"]["location"]["available"])
        self.assertEqual(body["fit_verdict"]["verdict"], "Fair deal")
        self.assertEqual(body["results"][0]["id"], outfit.call_args[0][0]["id"])

    def test_new_routes_need_login(self):
        for method, path in (("get", "/closet/items/x/outfit"), ("post", "/closet/items/x/outfit"),
                             ("get", "/dev/traces")):
            self.assertEqual(getattr(self.client, method)(path).status_code, 401, path)
        r = self.client.post("/closet/autotag", files={"photo": ("a.jpg", b"x", "image/jpeg")})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
