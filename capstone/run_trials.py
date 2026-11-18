"""
Capstone trial runner (Milestones 5 and 6).

    cd backend; python ../capstone/run_trials.py prime  --label prime      # the only step that spends RapidAPI calls
    cd backend; python ../capstone/run_trials.py trials --label run1       # 3 trials x 10 searches, zero RapidAPI calls

`prime` starts the real server in live mode with ONLY the Fashion Resale host allowed, broadening live
fetches off, and searches 5 queries once each: at most 5 RapidAPI calls, every one counted by
sources/quota.py. It prints the api_usage count before and after.

`trials` starts the real server (uvicorn, a separate process, so latency includes HTTP) with
FITFINDR_FAIL_STORE=etsy:timeout and the RapidAPI key blanked, so no live call can happen; resale answers
come from the 24 h cache that `prime` filled. It warms the server with 2 searches, then runs 3 trials of
10 searches (the 5 primed queries, each twice), and writes per trial into capstone/runs/<label>/trial<n>/:

    search_XX.json   status, client latency, and the response fields the criteria read
    records.jsonl    the server's own search-log records for exactly those 10 searches
    server.log       the server's stderr/stdout during the run (failure log lines)

and capstone/runs/<label>/summary.json with the five criteria scored per trial.
The 10 searches of one trial serve criteria 1-5 (all are forced-etsy-timeout searches).
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
PORT = 8765
QUERIES = ["vintage graphic tee", "denim jacket", "flannel shirt", "corduroy pants", "white denim pants"]
SPACING = 30.0  # seconds between searches: one search makes ~7 model calls and the free tier allows 15 a minute, so closer spacing measures the throttle, not the app


def env_for(mode: str, log_path: Path) -> dict:
    env = dict(os.environ, PYTHONUTF8="1", FITFINDR_SEARCH_LOG=str(log_path), AI201_CACHE="0",
               FITFINDR_DATA_MODE="live", APP_ENV="development")
    if mode == "prime":
        env.update(FITFINDR_LIVE_SOURCES="RESALE_API_HOST", FITFINDR_BROADEN_LIVE_FETCHES="0",
                   FITFINDR_FAIL_STORE="etsy:timeout")
    else:
        env.update(FITFINDR_LIVE_SOURCES="NO_STORE_IS_CALLED", RAPIDAPI_KEY="",
                   FITFINDR_FAIL_STORE="etsy:timeout")
    return env


def start_server(env: dict, out_path: Path):
    fh = out_path.open("w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(PORT)],
                            cwd=BACKEND, env=env, stdout=fh, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2).read()
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(1)
    proc.kill()
    raise SystemExit("server did not start; see " + str(out_path))


def post_search(q: str, path: str = "/search", payload: dict | None = None) -> tuple[int, dict, float]:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=json.dumps(payload or {"q": q}).encode(),
                                 headers={"content-type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status, body = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        status, body = e.code, {"error": e.read().decode()[:300]}
    return status, body, (time.perf_counter() - t0) * 1000


def usage_count() -> int | None:
    sys.path.insert(0, str(BACKEND))
    import supa
    rows = supa.service().select("api_usage", {"select": "host,month,count", "host": "like.fashion-resale*",
                                               "order": "month.desc", "limit": "1"})
    return rows[0]["count"] if rows else 0


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def run_searches(queries: list[str], out_dir: Path | None, split: bool = False) -> list[dict]:
    rows, last = [], 0.0
    for i, q in enumerate(queries, 1):
        wait = SPACING - (time.perf_counter() - last)
        if last and wait > 0:
            time.sleep(wait)
        last = time.perf_counter()
        status, body, ms = post_search(q, payload={"q": q, "style": False} if split else None)
        row = {"n": i, "query": q, "http_status": status, "client_latency_ms": round(ms),
               "result_count": len(body.get("results") or []), "empty": body.get("empty"),
               "store_notices": body.get("store_notices"), "stores": body.get("stores"),
               "agent": body.get("agent"), "error": body.get("error")}
        if split and body.get("results"):   # what the page does next: styling for the best match
            st, sb, sms = post_search(q, "/search/style", {"q": q, "listing": body["results"][0]})
            row.update(style_http_status=st, style_latency_ms=round(sms), styled=bool((sb.get("styling") or {}).get("text")))
        rows.append(row)
        print(f"  {i:2}. {status} {round(ms):6} ms  results={row['result_count']:2}  notices={row['store_notices']}  {q}", flush=True)
        if out_dir:
            (out_dir / f"search_{i:02}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False), encoding="utf-8")
    return rows


def score(rows: list[dict], all_records: list[dict]) -> dict:
    n = len(rows)
    records = [r for r in all_records if r["outcome"] not in ("style", "style_error")]
    style = [r for r in all_records if r["outcome"] in ("style", "style_error")]   # empty before the improvement
    c1 = sum(1 for r in rows if r["http_status"] == 200 and r["result_count"] > 0)
    c2 = sum(1 for r in rows if any("Etsy" in s and "took too long to answer" in s for s in (r["store_notices"] or [])))
    lat = [r["client_latency_ms"] for r in rows]
    c3 = sum(1 for x in lat if x < 3000)

    def has_failure_record(rec: dict) -> bool:
        e = next((s for s in rec.get("stores", []) if s.get("platform") == "etsy" and s.get("status") == "error"), None)
        return bool(rec.get("ts") and e and e.get("kind") and e.get("latency_ms") is not None and e.get("attempts"))
    c4 = sum(1 for rec in records if has_failure_record(rec))
    # a search costs its own model calls plus (after the improvement) its styling call
    costs = [rec["cost_usd"] for rec in records]
    if style:
        costs = [c + s_["cost_usd"] for c, s_ in zip(costs, style)]
    toks = [rec["tokens"]["prompt"] + rec["tokens"]["output"] for rec in records]
    if style:
        toks = [t + s_["tokens"]["prompt"] + s_["tokens"]["output"] for t, s_ in zip(toks, style)]
    return {
        "c1_searches_with_results": f"{c1}/{n}", "c1_met": c1 >= 9,
        "c2_searches_naming_store_and_reason": f"{c2}/{n}", "c2_met": c2 >= 9,
        "c3_under_3s": f"{c3}/{n}", "c3_met": c3 >= 9,
        "latency_ms": {"mean": round(statistics.mean(lat)), "median": round(statistics.median(lat)), "max": max(lat),
                       "min": min(lat), "all": lat},
        "c4_records_complete": f"{c4}/{n}", "c4_met": c4 == n and len(records) == n,
        "c4_record_count": len(records),
        "c5_mean_cost_usd": round(statistics.mean(costs), 6) if costs else None,
        "c5_met": bool(costs) and statistics.mean(costs) < 0.01,
        "mean_tokens": round(statistics.mean(toks)) if toks else None,
        "mean_model_calls": round(statistics.mean(r["tokens"]["model_calls"] for r in records), 1) if records else None,
        "live_calls": sum(r.get("live_calls", 0) for r in records),
        "styled_ok": f"{sum(1 for r in rows if r.get('styled'))}/{n}" if style else None,
        "full_ms_mean": round(statistics.mean(r["client_latency_ms"] + r.get("style_latency_ms", 0) for r in rows)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["prime", "trials"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--split", action="store_true", help="results-first: /search with style=false, then /search/style (run 2)")
    args = ap.parse_args()
    out = HERE / "runs" / args.label
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "_server_records.jsonl"
    if log_path.exists():
        log_path.unlink()

    if args.mode == "prime":
        before = usage_count()
        print(f"resale api_usage before: {before}")
        proc = start_server(env_for("prime", log_path), out / "server.log")
        try:
            rows = run_searches(QUERIES, out)
        finally:
            proc.terminate()
        after = usage_count()
        print(f"resale api_usage after: {after}  (new live calls: {after - before})")
        (out / "prime.json").write_text(json.dumps({"before": before, "after": after, "queries": QUERIES}, indent=1))
        return 0

    proc = start_server(env_for("trials", log_path), out / "server.log")
    summary = {}
    try:
        print("warm-up (not counted):")
        run_searches(QUERIES[:2], None, args.split)
        warm = len(read_records(log_path))
        for t in range(1, args.trials + 1):
            print(f"trial {t}:")
            tdir = out / f"trial{t}"
            tdir.mkdir(exist_ok=True)
            time.sleep(SPACING)
            start = len(read_records(log_path))
            rows = run_searches(QUERIES * 2, tdir, args.split)
            recs = read_records(log_path)[start:]
            (tdir / "records.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
            summary[f"trial{t}"] = score(rows, recs)
            print("  ->", json.dumps({k: v for k, v in summary[f"trial{t}"].items() if k != "latency_ms"}), flush=True)
    finally:
        proc.terminate()
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
