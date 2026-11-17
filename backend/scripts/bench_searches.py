"""
Run 10 searches through the real POST /search route and report the average
cost and latency. It makes NO RapidAPI calls.

    cd backend
    $env:PYTHONUTF8=1
    python scripts/bench_searches.py                  fixtures data, real Gemini calls (costs a little Gemini quota)
    python scripts/bench_searches.py --data cache     only responses already in the 24 h search cache
    python scripts/bench_searches.py --dry-run        no model calls at all: proves the script works, cost is 0

Why no RapidAPI call can happen:
  - `--data fixtures` (default) reads tests/fixtures/ and never builds a request.
  - `--data cache` runs in live mode but with FITFINDR_LIVE_SOURCES set to a name
    no store has, so a store with nothing cached is skipped, not called.
  - RAPIDAPI_KEY is blanked in this process, so a request could not be sent anyway.
  - The script then checks the search records: any live_calls above 0 is reported as an error.

Where the numbers come from: each search writes one record (searchlog.py) to a
log file that belongs to this run; the report reads those records back. Latency
is the whole request, measured in the route. Cost is the estimated Gemini cost
of the model calls in that search: tokens counted from Gemini's own usage
metadata, times the list prices in config.PRICES_PER_M. The model response
cache is turned off so repeat runs measure real calls (`--model-cache` keeps it,
and then a repeated search costs 0). Details: RUNNING.md, "How cost is measured".

The report is printed and saved to backend/logs/ (git-ignored). Nothing is
written to the database and nothing is written into the README.
"""

import argparse
import datetime as dt
import json
import os
import statistics
import sys
from pathlib import Path
from unittest import mock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Each query matches a recorded fixture (graphic tee, denim jacket, flannel shirt, corduroy pants, white denim pants).
SEARCHES = [
    "vintage graphic tee under $30",
    "vintage graphic tee size M",
    "vintage graphic tee under $20",
    "graphic tee",
    "denim jacket",
    "denim jacket under $60",
    "flannel shirt",
    "flannel shirt size L under $40",
    "corduroy pants",
    "white denim pants",
]

CANNED_OUTFIT = {"text": "Wear it with wide-leg khakis and white sneakers.", "item_ids": [],
                 "usage": {"calls": 0}}
CANNED_CARD = {"caption": "Found this for a great price.", "written_by": "code",
               "verdict": {"verdict": "Fair deal", "reasons": ["Fair price"], "retail": None}}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p * (len(ordered) - 1)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", choices=["fixtures", "cache"], default="fixtures")
    ap.add_argument("--dry-run", action="store_true", help="no model calls: canned outfit and caption, rules planner")
    ap.add_argument("--model-cache", action="store_true", help="keep the Gemini response cache (repeat searches then cost 0)")
    ap.add_argument("--planner", choices=["gemini", "rules"], help="default: the configured planner")
    ap.add_argument("-n", type=int, default=len(SEARCHES), help="how many of the 10 searches to run")
    args = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_dir = BACKEND / "logs"
    log_path = log_dir / f"bench_{stamp}.jsonl"
    # Set before config is imported: nothing here may reach RapidAPI or the database.
    os.environ["RAPIDAPI_KEY"] = ""
    os.environ["FITFINDR_SEARCH_LOG"] = str(log_path)
    os.environ["FITFINDR_SEARCH_LOG_DB"] = "0"
    os.environ["FITFINDR_FAIL_STORE"] = ""
    if args.data == "fixtures":
        os.environ["FITFINDR_DATA_MODE"] = "fixtures"
    else:
        os.environ["FITFINDR_DATA_MODE"] = "live"
        os.environ["FITFINDR_LIVE_SOURCES"] = "NO_STORE_IS_CALLED"
    if args.dry_run or args.planner == "rules":
        os.environ["FITFINDR_PLANNER"] = "rules"
    if args.dry_run:
        os.environ["FITFINDR_EMBEDDINGS"] = "0"
    if not args.model_cache:
        os.environ["AI201_CACHE"] = "0"

    import config
    from fastapi.testclient import TestClient

    from api.main import app, search_limiter

    patches = []
    if args.dry_run:
        patches = [mock.patch("agent.suggest_outfit", return_value=CANNED_OUTFIT),
                   mock.patch("agent.create_fit_card_full", return_value=CANNED_CARD)]
    for p in patches:
        p.start()

    client = TestClient(app)
    queries = SEARCHES[: args.n]
    print(f"Running {len(queries)} searches · data={args.data} · planner={config.AGENT_PLANNER}"
          f"{' · dry run (no model calls)' if args.dry_run else ''}\n", flush=True)
    for q in queries:
        search_limiter._hits.clear()                 # the 10-a-minute limiter is for users, not for this
        r = client.post("/search", json={"q": q})
        print(f"  {r.status_code}  {q}", flush=True)
    for p in patches:
        p.stop()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    return report(records, args, stamp, log_dir)


def report(records: list[dict], args, stamp: str, log_dir: Path) -> int:
    lat = [r["total_latency_ms"] for r in records]
    cost = [r["cost_usd"] for r in records]
    toks = [r["tokens"]["prompt"] + r["tokens"]["output"] for r in records]
    calls = [r["tokens"]["model_calls"] for r in records]
    live = sum(r["live_calls"] for r in records)
    n = len(records)
    lines = [f"# Search benchmark {stamp}", "",
             f"{n} searches · data={args.data} · {'dry run, no model calls' if args.dry_run else 'real model calls'}", "",
             "| # | query | results | latency ms | model calls | tokens | cost USD | outcome |",
             "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(records, 1):
        lines.append(f"| {i} | {r['query']} | {r['result_count']} | {r['total_latency_ms']} | {r['tokens']['model_calls']} "
                     f"| {r['tokens']['prompt'] + r['tokens']['output']} | {r['cost_usd']:.6f} | {r['outcome']} |")
    lines += ["",
              f"- **Average latency:** {statistics.mean(lat):.0f} ms (median {statistics.median(lat):.0f}, "
              f"slowest {max(lat)}, p95 {percentile(lat, 0.95):.0f})",
              f"- **Average cost per search:** ${statistics.mean(cost):.6f} (total ${sum(cost):.6f})",
              f"- **Average tokens per search:** {statistics.mean(toks):.0f} · **model calls per search:** {statistics.mean(calls):.1f}",
              f"- **Store failures seen:** {sum(len(r['failed_stores']) for r in records)} "
              f"· **partial results:** {sum(1 for r in records if r['partial'])}",
              f"- **RapidAPI calls made:** {live}" + ("" if live == 0 else "  <-- SHOULD BE 0"),
              "", "Cost is an estimate from token counts and list prices (RUNNING.md, \"How cost is measured\"); "
              "it is not a bill, and the free Gemini tier charges nothing."]
    text = "\n".join(lines)
    print("\n" + text)
    out = log_dir / f"bench_{stamp}.md"
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved {out.relative_to(BACKEND.parent)} (git-ignored); raw records in bench_{stamp}.jsonl")
    return 1 if live else 0


if __name__ == "__main__":
    sys.exit(main())
