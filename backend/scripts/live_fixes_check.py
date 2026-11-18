"""
Live check of the search fixes for the test account, through the real
/search route (agent, broadening, soft sizes, filters), and a report of the
result counts.

    cd backend
    $env:FITFINDR_DATA_MODE='live'
    $env:FITFINDR_LIVE_SOURCES='NONE'; python scripts/live_fixes_check.py     # cache only, no RapidAPI call
    $env:FITFINDR_LIVE_SOURCES=''; python scripts/live_fixes_check.py         # live calls allowed (counted)

Sets the test account's profile to the brief's: Women, $10–$40, tops S,
waist 28 (sizes in the US-retail groups). Only touches the test account
from .env. Every live call goes through sources/quota.py (stop line 40).
"""

import datetime as dt
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FITFINDR_DATA_MODE", "live")

from fastapi.testclient import TestClient  # noqa: E402

import attributes  # noqa: E402
import config  # noqa: E402
from api.main import app  # noqa: E402
from scripts.seed_test_closet import sign_in  # noqa: E402
from sources import quota  # noqa: E402

QUERIES = ("white denim pants", "womens ecru ribbed turtleneck")
PROFILE = {"gender": "women", "budget_min": 10, "budget": 40,
           "sizes": {"size_range": ["regular"], "tops": ["S"], "bottoms_waist": ["28"]}}


def main() -> None:
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {sign_in()}"}
    before = {s: quota.count(s) for s in quota.LIMITS} if config.DATA_MODE == "live" else {}
    r = client.patch("/profile", headers=headers, json=PROFILE)
    print(f"profile {r.status_code}: {r.json().get('gender')}, {r.json().get('sizes')}, "
          f"${r.json().get('budget_min')}–${r.json().get('budget')}")

    lines = [f"# Live search check — {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
             f"Test account: Women, $10–$40, tops S, waist 28 · data {config.DATA_MODE} · "
             f"live sources {sorted(config.LIVE_SOURCES) or 'all'}", ""]
    for q in QUERIES:
        body = client.post("/search", headers=headers, json={"q": q}).json()
        results = body.get("results") or []
        wanted = attributes.query_attributes(q)
        mismatches = [x["title"][:70] for x in results
                      if attributes.clear_mismatch(wanted, x) in ("category", "colour")]
        sized = Counter("match" if x["size"] and any(s.lower() in x["size"].lower().split() for s in
                                                     (body["parsed"].get("sizes") or []))
                        else "no size" if not x["size"] else "other" for x in results)
        stores = Counter(x["platform"] for x in results)
        lines += [f"## “{q}”", "",
                  f"- **{len(results)} results**, stores: {dict(stores)}",
                  f"- sizes (profile {body['parsed'].get('sizes')}, soft): {dict(sized)}",
                  f"- broadened: {(body.get('broadened') or {}).get('message') or 'no (enough results)'}",
                  f"- relaxed: {(body.get('relaxed') or {}).get('message') or 'no'}",
                  f"- category/colour mismatches: {mismatches or 'none'}",
                  f"- best match: {results[0]['title'][:80] if results else '—'}",
                  f"- empty state: {body.get('empty')}" if body.get("empty") else "- empty state: no", ""]
        lines += [f"  {i + 1}. {x['title'].splitlines()[0][:70]} · ${x['price']:.0f} · {x['platform']} · "
                  f"size {x['size']}" for i, x in enumerate(results[:8])] + [""]
    if before:
        after = {s: quota.count(s) for s in quota.LIMITS}
        lines += ["## Live calls", ""] + [f"- {s}: {before[s]} → {after[s]}" for s in quota.LIMITS] + [""]
    text = config.redact("\n".join(lines))
    print(text)
    out = config.RESULTS_DIR / f"live_fixes_{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
