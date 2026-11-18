"""Where does one search spend its time? Wraps the main stages with timers and runs primed searches
in-process (etsy forced to time out, no live calls). A diagnosis aid, not a trial.

    cd backend; python ../capstone/profile_stages.py
"""
import collections
import functools
import os
import sys
import time
from pathlib import Path

B = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(B))
os.environ.update(FITFINDR_DATA_MODE="live", RAPIDAPI_KEY="", FITFINDR_LIVE_SOURCES="NONE",
                  FITFINDR_FAIL_STORE="etsy:timeout", AI201_CACHE="0", FITFINDR_SEARCH_LOG_DB="0",
                  FITFINDR_SEARCH_LOG=str(Path(__file__).parent / "runs" / "_profile.jsonl"))
import generate  # noqa: E402
import sources  # noqa: E402
from sources import cache, failures  # noqa: E402

T = collections.defaultdict(list)


def timed(owner, name, label):
    fn = getattr(owner, name)

    @functools.wraps(fn)
    def wrap(*a, **k):
        t = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            T[label].append((time.perf_counter() - t) * 1000)
    setattr(owner, name, wrap)


timed(generate, "generate_with_tools", "model: planner turn (generate_with_tools)")
timed(generate, "generate", "model: generate (outfit / fit card)")
timed(generate, "embed", "model: embeddings (ranking)")
timed(cache, "get", "supabase: search_cache read")

import tools  # noqa: E402
timed(tools, "fetch_candidates", "stores: fetch_candidates total")

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app, search_limiter  # noqa: E402

client = TestClient(app)
client.post("/search", json={"q": "denim jacket"})   # warm-up
T.clear()
totals = []
for q in ["vintage graphic tee", "flannel shirt", "corduroy pants"]:
    search_limiter._hits.clear()
    time.sleep(25)                                    # stay under the 15-a-minute model limit
    t = time.perf_counter()
    client.post("/search", json={"q": q})
    totals.append((time.perf_counter() - t) * 1000)
print(f"total per search (ms): {[round(x) for x in totals]}  mean {sum(totals)/3:.0f}\n")
print(f"{'stage (summed over 3 searches, then per search)':58} calls  total ms  per search")
for k, v in sorted(T.items(), key=lambda kv: -sum(kv[1])):
    print(f"{k:58} {len(v):5} {sum(v):9.0f} {sum(v)/3:10.0f}")
