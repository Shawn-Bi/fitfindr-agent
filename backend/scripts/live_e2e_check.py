"""
One end-to-end check of A1 (tool-choosing agent) and A4 (semantic ranking)
against LIVE store data, through the real /search route, as a guest and as
the test account. Writes results/live_e2e_<date>.md.

    cd backend
    $env:FITFINDR_DATA_MODE='live'; python scripts/live_e2e_check.py

Live RapidAPI calls: at most 2 (guest "white denim pants" and the test
account's "white denim pants" with its $10–$40 budget); the third request
reuses the second's 24 h cache. Every call goes through the quota counter.
"""

import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FITFINDR_DATA_MODE", "live")

from fastapi.testclient import TestClient  # noqa: E402

import attributes  # noqa: E402
import config  # noqa: E402
import generate  # noqa: E402
from api.main import app, search_limiter  # noqa: E402
from scripts.seed_test_closet import sign_in  # noqa: E402
from sources import quota  # noqa: E402

CHECKS = [
    ("guest", "white denim pants"),
    ("user", "white denim pants"),
    ("user", "white denim pants size XXS"),
    ("user", "something nice"),
]


def bad_rows(results):
    """Listings that clearly aren't white/cream denim bottoms."""
    wanted = attributes.query_attributes("white denim pants")
    return [r["title"].splitlines()[0][:80] for r in results if attributes.clear_mismatch(wanted, r)]


def main() -> None:
    if config.DATA_MODE != "live":
        sys.exit("Run with FITFINDR_DATA_MODE=live")
    client = TestClient(app)
    user_headers = {"Authorization": f"Bearer {sign_in()}"}
    before_calls = quota.count("RESALE_API_HOST")
    before_model = dict(generate.ledger())
    lines = [f"# Live end-to-end check — A1 agent + A4 ranking ({dt.datetime.now():%Y-%m-%d %H:%M})", "",
             "Real `/search` route, live Fashion Resale data (Depop, Poshmark, Mercari, eBay), "
             "Gemini planner on.", ""]
    for who, q in CHECKS:
        search_limiter._hits.clear()
        r = client.post("/search", json={"q": q}, headers=user_headers if who == "user" else {})
        body = r.json()
        results = body.get("results") or []
        agent = body.get("agent") or {}
        lines += [f"## {who}: “{q}”", "",
                  f"- HTTP {r.status_code} · planner `{agent.get('planner')}` · steps {agent.get('steps')} · "
                  f"ranking `{agent.get('ranking')}`",
                  f"- chips: {[c['label'] for c in body.get('chips') or []]}",
                  f"- stores: {[(s['label'], s['status'], s['count']) for s in body.get('stores') or []]}"]
        if body.get("relaxed"):
            lines.append(f"- **relaxed:** {body['relaxed']['message']}")
        if body.get("clarify"):
            lines.append(f"- **asked:** {body['clarify']['question']} {body['clarify']['suggestions']}")
        if body.get("empty"):
            lines.append(f"- empty: {body['empty']['message']} · offers {[o['label'] for o in body['empty']['relax']]}")
        if results:
            lines.append(f"- {len(results)} results; clear mismatches shown: {bad_rows(results) or 'none'}")
            lines += [f"  {i + 1}. {x['title'].splitlines()[0][:90]} — ${x['price']:.2f} · {x['platform']}"
                      for i, x in enumerate(results[:8])]
        if body.get("fit_verdict"):
            v = body["fit_verdict"]
            lines.append(f"- verdict: **{v.get('verdict')}** {v.get('reasons')} · retail {v.get('retail') or 'unknown'}")
        if body.get("fit_card"):
            lines.append(f"- caption: {body['fit_card']}")
        lines.append("")
        print(f"{who}: {q} → {r.status_code}, {len(results)} results, steps {agent.get('steps')}")

    after = generate.ledger()
    lines += ["## Cost", "",
              f"- Live RapidAPI calls: {quota.count('RESALE_API_HOST') - before_calls} "
              f"(resale counter now {quota.count('RESALE_API_HOST')}/40)",
              f"- Model calls: { {m: after.get(m, 0) - before_model.get(m, 0) for m in after if after.get(m, 0) - before_model.get(m, 0)} }", ""]
    out = config.RESULTS_DIR / f"live_e2e_{dt.datetime.now():%Y-%m-%d_%H%M}.md"
    out.write_text(config.redact("\n".join(lines)), encoding="utf-8")
    print(f"wrote {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
