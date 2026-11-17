"""
Store failure handling (capstone, Shape B): every kind of failure, the retry
rule, the plain-words reasons, FITFINDR_FAIL_STORE, and partial results. No
test makes a network call: stores are patched or fixtures are used.
"""

import json
import os
import socket
import subprocess
import sys
import unittest
import urllib.error
from unittest import mock

os.environ["RAPIDAPI_KEY"] = ""                 # never reach RapidAPI, however the tests are started
os.environ["FITFINDR_DATA_MODE"] = "fixtures"   # before config is imported
os.environ["FITFINDR_EMBEDDINGS"] = "0"         # no network: keyword ranking
os.environ["FITFINDR_PLANNER"] = "rules"        # no network: the deterministic agent policy

import config  # noqa: E402
import sources  # noqa: E402
from api import catalog  # noqa: E402
from sources import etsy, failures, quota, resale  # noqa: E402
from sources.failures import StoreError  # noqa: E402


class FakeAdapter:
    """Stands in for a store adapter in failures.call()."""
    PLATFORMS = ("etsy",)
    FIXTURE_PREFIX = "etsy"
    __name__ = "sources.fake"


class ClassifyTest(unittest.TestCase):
    def kind(self, exc):
        return failures.classify(exc).kind

    def test_every_failure_kind_is_recognised(self):
        self.assertEqual(self.kind(socket.timeout()), "timeout")
        self.assertEqual(self.kind(TimeoutError()), "timeout")
        self.assertEqual(self.kind(urllib.error.URLError(socket.timeout())), "timeout")
        self.assertEqual(self.kind(urllib.error.URLError("dns down")), "network")
        self.assertEqual(self.kind(failures.http_error("X", 429)), "rate_limited")
        self.assertEqual(self.kind(failures.http_error("X", 403)), "forbidden")
        self.assertEqual(self.kind(failures.http_error("X", 401)), "forbidden")
        self.assertEqual(self.kind(failures.http_error("X", 503)), "server_error")
        self.assertEqual(self.kind(failures.http_error("X", 404)), "http_error")
        self.assertEqual(self.kind(json.JSONDecodeError("bad", "{", 1)), "malformed")
        self.assertEqual(self.kind(quota.QuotaPaused("ETSY_API_HOST", "2026-11-01")), "quota_paused")
        self.assertEqual(self.kind(RuntimeError("ETSY_API_HOST and RAPIDAPI_KEY must be set in .env")), "not_configured")
        self.assertEqual(self.kind(ValueError("surprise")), "unknown")

    def test_plain_reasons_have_no_codes_or_jargon(self):
        for kind in failures.KINDS:
            text = failures.plain_reason(kind)
            self.assertFalse(any(w in text for w in ("HTTP", "403", "429", "JSON", "500", "Exception")), text)
        self.assertEqual(failures.plain_reason("quota_paused", "2026-11-01"),
                         "hit this month's free limit (back on Nov 1)")

    def test_details_never_carry_a_secret(self):
        with mock.patch.dict("os.environ", {"RAPIDAPI_KEY": "not-a-real-key-123456"}):
            err = failures.http_error("Etsy API", 403, "bad key not-a-real-key-123456")
        self.assertNotIn("not-a-real-key-123456", err.detail)


class CallTest(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(config, "FAIL_STORE", ""), mock.patch.object(config, "RETRY_MAX", 1),
                  mock.patch.object(config, "RETRY_BACKOFF_SECONDS", 0.0)):
            p.start()
            self.addCleanup(p.stop)

    def run_call(self, fn):
        sleeps = []
        return failures.call(FakeAdapter, fn, sleep=sleeps.append), sleeps

    def test_success_first_time(self):
        done, sleeps = self.run_call(lambda: "raw")
        self.assertTrue(done["ok"])
        self.assertEqual((done["raw"], done["attempts"], sleeps), ("raw", 1, []))

    def test_timeout_is_retried_once_then_succeeds(self):
        calls = iter([socket.timeout(), "raw"])

        def fn():
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r

        done, sleeps = self.run_call(fn)
        self.assertTrue(done["ok"])
        self.assertEqual(done["attempts"], 2)
        self.assertEqual(len(sleeps), 1)

    def test_429_is_retried_once_and_stops_after_the_retry(self):
        fn = mock.Mock(side_effect=failures.http_error("X", 429))
        done, _ = self.run_call(fn)
        self.assertFalse(done["ok"])
        self.assertEqual(fn.call_count, 2)               # the original try and ONE retry
        self.assertEqual(done["error"].kind, "rate_limited")

    def test_other_failures_are_not_retried(self):
        for exc in (failures.http_error("X", 403), failures.http_error("X", 500),
                    StoreError("malformed", "bad"), quota.QuotaPaused("ETSY_API_HOST", "2026-11-01"),
                    urllib.error.URLError("down")):
            fn = mock.Mock(side_effect=exc)
            done, sleeps = self.run_call(fn)
            self.assertFalse(done["ok"])
            self.assertEqual((fn.call_count, sleeps), (1, []), type(exc).__name__)

    def test_a_failure_is_logged_as_one_json_line(self):
        with self.assertLogs("fitfindr.failures", "WARNING") as logs:
            self.run_call(mock.Mock(side_effect=failures.http_error("X", 403, "nope")))
        record = json.loads(logs.records[-1].getMessage())
        self.assertEqual((record["event"], record["kind"], record["http_status"]),
                         ("store_failure", "forbidden", 403))


class InjectionTest(unittest.TestCase):
    def test_spec_parsing(self):
        self.assertEqual(failures.parse_injection("depop:timeout, etsy:429:once"),
                         {"depop": ("timeout", False), "etsy": ("429", True)})
        for bad in ("depop", "depop:explode", "depop:timeout:twice"):
            with self.assertRaises(ValueError):
                failures.parse_injection(bad)

    def test_names_cover_platforms_hosts_and_wildcard(self):
        with mock.patch.object(config, "FAIL_STORE", "ebay:403"):
            self.assertEqual(failures.injected_fault(resale, 1).kind, "forbidden")
            self.assertIsNone(failures.injected_fault(etsy, 1))
        with mock.patch.object(config, "FAIL_STORE", "etsy:500"):
            self.assertEqual(failures.injected_fault(etsy, 1).kind, "server_error")
        with mock.patch.object(config, "FAIL_STORE", "*:malformed"):
            self.assertEqual(failures.injected_fault(etsy, 1).kind, "malformed")

    def test_once_fails_the_first_attempt_only(self):
        with mock.patch.object(config, "FAIL_STORE", "etsy:429:once"):
            self.assertEqual(failures.injected_fault(etsy, 1).kind, "rate_limited")
            self.assertIsNone(failures.injected_fault(etsy, 2))

    def test_production_refuses_to_start_with_it_set(self):
        env = {**os.environ, "APP_ENV": "production", "FITFINDR_DATA_MODE": "live",
               "FRONTEND_ORIGINS": "https://example.com", "FITFINDR_FAIL_STORE": "etsy:timeout"}
        out = subprocess.run([sys.executable, "-c", "import config"], cwd=str(config.ROOT), env=env,
                             capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("FITFINDR_FAIL_STORE", out.stderr)


class PartialResultsTest(unittest.TestCase):
    """fetch_candidates on fixtures: a failing store must not take the others down."""

    def setUp(self):
        for p in (mock.patch.object(config, "DATA_MODE", "fixtures"),
                  mock.patch.object(config, "RETRY_BACKOFF_SECONDS", 0.0)):
            p.start()
            self.addCleanup(p.stop)

    def search(self, spec):
        with mock.patch.object(config, "FAIL_STORE", spec):
            return sources.fetch_candidates("vintage graphic tee")

    def test_nothing_injected_is_unchanged(self):
        listings, statuses = self.search("")
        self.assertTrue({"depop", "etsy"} <= {l["platform"] for l in listings})
        self.assertEqual({s["status"] for s in statuses if s["platform"] != "fb_marketplace"}, {"fixtures"})

    def test_each_failure_kind_leaves_the_other_store_working(self):
        for fault, kind in (("timeout", "timeout"), ("403", "forbidden"), ("429", "rate_limited"),
                            ("500", "server_error"), ("malformed", "malformed")):
            with self.subTest(fault=fault):
                listings, statuses = self.search(f"etsy:{fault}")
                self.assertTrue(listings, "the other stores' results must survive")
                self.assertNotIn("etsy", {l["platform"] for l in listings})
                etsy_status = next(s for s in statuses if s["platform"] == "etsy")
                self.assertEqual((etsy_status["status"], etsy_status["kind"]), ("error", kind))
                self.assertTrue(etsy_status["reason"])
                self.assertEqual(next(s for s in statuses if s["platform"] == "depop")["status"], "fixtures")

    def test_quota_stop_line_shows_as_paused_with_a_date(self):
        _, statuses = self.search("resale:quota")
        ebay = next(s for s in statuses if s["platform"] == "ebay")
        self.assertEqual(ebay["status"], "paused")
        self.assertEqual(ebay["resumes"], quota.resumes_on())

    def test_resale_failure_takes_down_all_four_of_its_stores_and_only_those(self):
        listings, statuses = self.search("poshmark:timeout")
        down = {s["platform"] for s in statuses if s["status"] == "error"}
        self.assertEqual(down, {"depop", "poshmark", "mercari", "ebay"})
        self.assertEqual({l["platform"] for l in listings}, {"etsy"})

    def test_every_store_down_returns_no_listings_and_no_crash(self):
        listings, statuses = self.search("*:403")
        self.assertEqual(listings, [])
        self.assertEqual(len([s for s in statuses if s["status"] == "error"]), 5)

    def test_a_timeout_that_clears_on_retry_gives_results_and_two_attempts(self):
        listings, statuses = self.search("etsy:timeout:once")
        etsy_status = next(s for s in statuses if s["platform"] == "etsy")
        self.assertEqual((etsy_status["status"], etsy_status["attempts"]), ("fixtures", 2))
        self.assertIn("etsy", {l["platform"] for l in listings})


class LiveModeFailureTest(unittest.TestCase):
    """Live mode with the network patched out: the real error paths, no real call."""

    def setUp(self):
        self.store = quota.MemoryStore()
        quota.use_store(self.store)
        for p in (mock.patch.object(config, "DATA_MODE", "live"), mock.patch.object(config, "FAIL_STORE", ""),
                  mock.patch.object(config, "RETRY_BACKOFF_SECONDS", 0.0),
                  mock.patch("sources.cache.get", return_value=None)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(quota.use_store, quota.SupabaseStore())

    def test_malformed_reply_is_rejected_and_never_cached(self):
        good = {"success": True, "data": {"results": []}}
        with mock.patch.object(resale, "fetch", return_value="<html>oops</html>"), \
             mock.patch.object(etsy, "fetch", return_value=good), \
             mock.patch("sources.cache.put") as put:
            _, statuses = sources.fetch_candidates("flannel shirt")
        self.assertEqual(next(s for s in statuses if s["platform"] == "depop")["kind"], "malformed")
        self.assertEqual(put.call_count, 1)             # Etsy's good reply only

    def test_real_timeout_is_retried_once_then_reported(self):
        good = {"success": True, "data": {"results": []}}
        slow = mock.Mock(side_effect=urllib.error.URLError(socket.timeout("timed out")))
        with mock.patch.object(resale, "fetch", slow), mock.patch.object(etsy, "fetch", return_value=good), \
             mock.patch("sources.cache.put"):
            _, statuses = sources.fetch_candidates("flannel shirt")
        self.assertEqual(slow.call_count, 2)
        depop = next(s for s in statuses if s["platform"] == "depop")
        self.assertEqual((depop["status"], depop["kind"], depop["attempts"]), ("error", "timeout", 2))
        self.assertEqual(next(s for s in statuses if s["platform"] == "etsy")["status"], "active")

    def test_403_makes_one_call_only(self):
        good = {"listings": [], "search_metadata": {}}
        forbidden = mock.Mock(side_effect=failures.http_error("Etsy API", 403, "not subscribed"))
        with mock.patch.object(resale, "fetch", return_value=good), mock.patch.object(etsy, "fetch", forbidden), \
             mock.patch("sources.cache.put"):
            _, statuses = sources.fetch_candidates("flannel shirt")
        self.assertEqual(forbidden.call_count, 1)
        self.assertEqual(next(s for s in statuses if s["platform"] == "etsy")["kind"], "forbidden")

    def test_stop_line_without_cache_is_paused_not_an_error(self):
        self.store.counts[(quota.host_name("RESALE_API_HOST"), quota.month_start())] = 40
        good = {"success": True, "data": {"results": []}}
        with mock.patch.object(etsy, "fetch", return_value=good), mock.patch("sources.cache.put"), \
             mock.patch("urllib.request.urlopen", side_effect=AssertionError("live call!")):
            _, statuses = sources.fetch_candidates("flannel shirt")
        ebay = next(s for s in statuses if s["platform"] == "ebay")
        self.assertEqual((ebay["status"], ebay["kind"], ebay["resumes"]), ("paused", "quota_paused", quota.resumes_on()))


class NoticeTest(unittest.TestCase):
    def test_notices_group_stores_that_share_a_reason(self):
        statuses = [{"platform": p, "status": "error", "kind": "timeout", "reason": failures.plain_reason("timeout")}
                    for p in ("depop", "poshmark", "mercari", "ebay")]
        statuses.append({"platform": "etsy", "status": "fixtures"})
        panel = catalog.store_panel(statuses, [])
        self.assertEqual(catalog.store_notices(panel), ["eBay, Depop, Poshmark and Mercari took too long to answer."])

    def test_no_failures_no_notices_and_coming_soon_is_not_a_failure(self):
        panel = catalog.store_panel([{"platform": "etsy", "status": "fixtures"}], [])
        self.assertEqual(catalog.store_notices(panel), [])


class SearchRouteFailureTest(unittest.TestCase):
    """POST /search end to end (fixtures, rules planner, model patched out)."""

    OUTFIT = {"text": "Wear it with wide-leg khakis.", "item_ids": []}
    CARD = {"caption": "Scored this tee!", "verdict": {"verdict": "Worth it", "reasons": ["Cheap"], "retail": None}}

    def setUp(self):
        from fastapi.testclient import TestClient
        from api.main import app, search_limiter
        search_limiter._hits.clear()
        self.client = TestClient(app)
        for p in (mock.patch.object(config, "RETRY_BACKOFF_SECONDS", 0.0), mock.patch("observe.save"),
                  mock.patch("agent.create_fit_card_full", return_value=self.CARD),
                  mock.patch("agent.suggest_outfit", return_value=self.OUTFIT)):
            p.start()
            self.addCleanup(p.stop)

    def search(self, spec):
        with mock.patch.object(config, "FAIL_STORE", spec):
            r = self.client.post("/search", json={"q": "vintage graphic tee under $30"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_one_store_down_still_returns_the_others_and_says_why(self):
        body = self.search("etsy:timeout")
        self.assertTrue(body["results"])
        self.assertNotIn("etsy", {x["platform"] for x in body["results"]})
        self.assertEqual(body["store_notices"], ["Etsy took too long to answer."])
        etsy_row = next(s for s in body["stores"] if s["platform"] == "etsy")
        self.assertEqual((etsy_row["status"], etsy_row["kind"], etsy_row["reason"]),
                         ("error", "timeout", "took too long to answer"))
        self.assertEqual(next(s for s in body["stores"] if s["platform"] == "depop")["status"], "live")
        self.assertIsNone(body["empty"])

    def test_all_stores_down_says_so_instead_of_no_matches(self):
        body = self.search("*:403")
        self.assertEqual(body["results"], [])
        self.assertEqual(body["empty"]["title"], "We couldn't search any store right now")
        self.assertEqual(body["empty"]["relax"], [])
        self.assertEqual(len(body["store_notices"]), 1)     # all five share one reason

    def test_no_failures_means_no_notices(self):
        self.assertEqual(self.search("")["store_notices"], [])


class SearchRecordTest(unittest.TestCase):
    """Every search leaves one JSON record in the log file, failed ones included."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from fastapi.testclient import TestClient
        from api.main import app, search_limiter
        search_limiter._hits.clear()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "searches.jsonl"
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(config, "SEARCH_LOG_PATH", self.path), mock.patch.object(config, "SEARCH_LOG_DB", False),
                  mock.patch.object(config, "RETRY_BACKOFF_SECONDS", 0.0), mock.patch.object(config, "FAIL_STORE", ""),
                  mock.patch("agent.create_fit_card_full", return_value=SearchRouteFailureTest.CARD),
                  mock.patch("agent.suggest_outfit", return_value=SearchRouteFailureTest.OUTFIT)):
            p.start()
            self.addCleanup(p.stop)

    def records(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def test_a_good_search_writes_one_complete_record(self):
        r = self.client.post("/search", json={"q": "vintage graphic tee under $30", "max_price": 30})
        self.assertEqual(r.status_code, 200)
        (rec,) = self.records()
        for field in ("ts", "run_id", "query", "filters", "stores_called", "stores", "result_count",
                      "total_latency_ms", "tokens", "cost_usd", "outcome", "live_calls"):
            self.assertIn(field, rec)
        self.assertEqual(rec["query"], "vintage graphic tee under $30")
        self.assertEqual(rec["filters"]["max_price"], 30)
        self.assertEqual(rec["result_count"], len(r.json()["results"]))
        self.assertGreater(rec["total_latency_ms"], 0)
        self.assertIn("depop", rec["stores_called"])
        self.assertFalse(rec["partial"])
        self.assertEqual(rec["live_calls"], 0)                      # fixtures: no RapidAPI request
        depop = next(s for s in rec["stores"] if s["platform"] == "depop")
        self.assertEqual((depop["status"], depop["attempts"]), ("fixtures", 1))
        self.assertIn("latency_ms", depop)

    def test_a_partial_search_records_which_store_failed_and_why(self):
        with mock.patch.object(config, "FAIL_STORE", "etsy:403"):
            self.client.post("/search", json={"q": "vintage graphic tee"})
        (rec,) = self.records()
        self.assertTrue(rec["partial"])
        self.assertEqual(rec["failed_stores"], ["etsy"])
        etsy_row = next(s for s in rec["stores"] if s["platform"] == "etsy")
        self.assertEqual((etsy_row["status"], etsy_row["kind"], etsy_row["http_status"]), ("error", "forbidden", 403))
        self.assertGreater(rec["result_count"], 0)

    def test_all_stores_down_is_recorded_as_its_own_outcome(self):
        with mock.patch.object(config, "FAIL_STORE", "*:timeout"):
            self.client.post("/search", json={"q": "vintage graphic tee"})
        (rec,) = self.records()
        self.assertEqual((rec["outcome"], rec["result_count"]), ("all_stores_down", 0))

    def test_a_crashing_search_is_still_logged(self):
        with mock.patch("api.main.run_agent", side_effect=RuntimeError("boom")):
            r = self.client.post("/search", json={"q": "vintage graphic tee"})
        self.assertEqual(r.status_code, 500)
        (rec,) = self.records()
        self.assertEqual(rec["outcome"], "error")
        self.assertIn("boom", rec["error"])

    def test_a_refused_search_is_logged_too(self):
        r = self.client.post("/search", json={"q": "   ,  "})
        self.assertEqual(r.status_code, 422)
        (rec,) = self.records()
        self.assertEqual(rec["outcome"], "rejected")

    def test_the_record_holds_no_key_and_no_user_id(self):
        with mock.patch.dict("os.environ", {"RAPIDAPI_KEY": "not-a-real-key-123456"}),              mock.patch.object(config, "FAIL_STORE", "etsy:403"):
            self.client.post("/search", json={"q": "vintage graphic tee"})
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("not-a-real-key-123456", text)
        self.assertNotIn("user_id", text)

    def test_live_calls_counts_one_per_host_and_counts_retries(self):
        import searchlog
        statuses = [{"platform": p, "status": "error", "kind": "timeout", "attempts": 2, "source": "RESALE_API_HOST"}
                    for p in ("depop", "ebay")]
        statuses += [{"platform": "etsy", "status": "active", "attempts": 1, "source": "ETSY_API_HOST"},
                     {"platform": "x", "status": "cached"}]
        with mock.patch.object(config, "DATA_MODE", "live"):
            self.assertEqual(searchlog.build("q", {}, statuses=statuses)["live_calls"], 3)


if __name__ == "__main__":
    unittest.main()
