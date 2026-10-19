"""
Build and save an AI-stylist outfit (B2) for every closet item of the test
account, sharing live searches between outfits, then grade each with the
LLM judge and write results/stylist_eval_<date>.md.

    cd backend
    $env:FITFINDR_DATA_MODE='live'; python scripts/generate_outfits.py --live-budget 18
    python scripts/generate_outfits.py                 # fixtures, no live calls

Steps:
  1. plan every outfit (one model call each)
  2. while live budget remains: pick the next planned piece (round-robin over
     items) that has no candidate in the pool yet, and run ONE live search
     for it — every search's listings go into the shared pool (and the
     24 h search_cache), so one "women's black leather loafers" search can
     serve several outfits
  3. build each outfit from the pool (one verification call each), save it
     to closet_outfits with the user's own token
  4. judge each outfit (one call each) and write the report

Every live call goes through sources/quota.py (stop line 40/month) and is
logged. Only touches the test account from .env.
"""

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("FITFINDR_DATA_MODE", "fixtures")

import config  # noqa: E402
import generate  # noqa: E402
import judge  # noqa: E402
import stylist  # noqa: E402
import supa  # noqa: E402
from api import catalog  # noqa: E402
from scripts.seed_test_closet import sign_in  # noqa: E402
from sources import quota, recent_pool  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-budget", type=int, default=0, help="max live RapidAPI searches (live mode only)")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="only the first N items (dry runs)")
    args = parser.parse_args()
    if args.live_budget and config.DATA_MODE != "live":
        sys.exit("--live-budget needs FITFINDR_DATA_MODE=live")

    token = sign_in()
    db = supa.as_user(token)
    user_id = db.get_user()["id"]
    profile = db.select("profiles", {"select": "*", "user_id": f"eq.{user_id}"})[0]
    closet = db.select("closet_items", {"select": "*", "user_id": f"eq.{user_id}", "order": "created_at.asc"})
    closet = closet[:args.limit] if args.limit else closet
    prefs = catalog.profile_prefs(profile)
    budget = (float(profile["budget_min"]) if profile.get("budget_min") else None,
              float(profile["budget"]) if profile.get("budget") else None)
    ledger_before = dict(generate.ledger())
    resale_before = quota.count("RESALE_API_HOST") if config.DATA_MODE == "live" else None
    print(f"{len(closet)} items · prefs {prefs} · budget {budget} · mode {config.DATA_MODE}")

    # 1. plans
    plans = {}
    for item in closet:
        item_prefs = {**prefs, "gender": item.get("gender") or prefs.get("gender")}
        plans[item["id"]] = stylist.plan_outfit(item, item_prefs, budget)   # cached: a re-run re-plans for free
        print(f"plan  {item['name']}: {plans[item['id']]['title']} → "
              + "; ".join(f"{p['label']}: {p['name']}" for p in plans[item["id"]]["pieces"]))

    # 2–3. build every outfit from the pool; then live-search only the pieces the
    # verification left empty (round-robin over items), and rebuild those outfits.
    pool = recent_pool()
    searched, live_used, outfits = set(), 0, {}
    pending = list(closet)
    while True:
        for item in pending:
            item_prefs = {**prefs, "gender": item.get("gender") or prefs.get("gender")}
            outfits[item["id"]] = stylist.build_outfit(item, item_prefs, budget, plan=plans[item["id"]],
                                                       pool=pool, live_calls=0, cache_ok=False)
            shown = sum(1 for p in outfits[item["id"]]["pieces"] if p["listing"])
            print(f"built {item['name']}: {shown}/{len(outfits[item['id']]['pieces'])} pieces with a listing")
        todo = []
        for rank in range(3):
            for item in closet:
                pieces = outfits[item["id"]]["pieces"]
                if rank < len(pieces) and not pieces[rank]["listing"]                         and pieces[rank]["search"].lower() not in searched:
                    todo.append((item, pieces[rank]))
        if not todo or live_used >= args.live_budget:
            break
        touched = set()
        for item, piece in todo:
            if live_used >= args.live_budget:
                break
            searched.add(piece["search"].lower())
            try:
                found, was_live = stylist.live_search(piece["search"], budget)
            except Exception as exc:  # noqa: BLE001
                print(f"live  “{piece['search']}” failed: {config.redact(exc)[:120]}")
                continue
            live_used += int(was_live)
            pool.extend(found)
            touched.add(item["id"])
            print(f"{'live ' if was_live else 'cache'} {live_used}/{args.live_budget} “{piece['search']}” → {len(found)} listings")
        # rebuild every outfit that still has an empty piece: one search can serve several
        pending = [it for it in closet if any(not p["listing"] for p in outfits[it["id"]]["pieces"])]
        if not touched:
            break

    report = []
    for item in closet:
        item_prefs = {**prefs, "gender": item.get("gender") or prefs.get("gender")}
        outfit = outfits[item["id"]]
        db.insert("closet_outfits", {"item_id": item["id"], "user_id": user_id, "status": "ready",
                                     "outfit": outfit, "data_mode": config.DATA_MODE,
                                     "item_version": item.get("updated_at"), "error": None},
                  upsert=True, on_conflict="item_id")
        shown = sum(1 for p in outfit["pieces"] if p["listing"])
        print(f"saved {item['name']}: {shown}/{len(outfit['pieces'])} pieces with a listing")
        report.append((item, item_prefs, outfit))

    # 4. judge
    scores = []
    lines = [f"# AI stylist outfits — LLM-as-judge ({dt.date.today().isoformat()})", "",
             f"- Account: test account · {len(closet)} closet items · data: {config.DATA_MODE}",
             f"- Planner model {config.MODEL} · judge {config.JUDGE_MODEL} (temperature 0)",
             f"- Profile: shopping for {prefs.get('gender')}, styles {prefs.get('styles') or 'none'}, "
             f"budget ${budget[0]:.0f}–${budget[1]:.0f}" if budget[0] and budget[1] else "", ""]
    judge_error = None
    for item, item_prefs, outfit in report:
        result = None
        if not args.no_judge and not judge_error:
            try:
                result = judge.judge_stylist(outfit, item, item_prefs)
            except Exception as exc:  # noqa: BLE001 — the outfits are saved; only the scores are missing
                judge_error = config.redact(exc)[:160]
                print(f"judge failed, writing the report without scores: {judge_error}")
        if result and result["avg"]:
            scores.append(result)
        lines += [f"## {item['name']} → {outfit['title']}", "",
                  f"{outfit.get('concept') or ''}", ""]
        for p in outfit["pieces"]:
            found = p["listing"]
            lines.append(f"- **{p['label']}: {p['name']}** — {p.get('why') or ''}  ")
            if found:
                title = found["title"].splitlines()[0][:90]
                lines.append(f"  Listing: {title} (${found['price']:.0f}, {found['platform']})")
            else:
                lines.append("  No listing truly fit — shown as a description with Search this")
        if result:
            lines += ["", "Judge: " + ", ".join(f"{d} {v['score']}" for d, v in result["scores"].items())
                      + f" → **{result['avg']}**", ""]
            lines += [f"- {d}: {v['reason']}" for d, v in result["scores"].items() if v.get("reason")]
        lines.append("")

    dims = judge.OUTFIT_DIMS
    if scores:
        avg = round(sum(s["avg"] for s in scores) / len(scores), 2)
        table = ["## Summary", "", "| Dimension | Average |", "|---|---|"]
        for d in dims:
            vals = [s["scores"][d]["score"] for s in scores if s["scores"][d]["score"]]
            table.append(f"| {d} | {round(sum(vals) / len(vals), 2) if vals else '—'} |")
        table += [f"| **Overall** | **{avg}** |", ""]
        lines[6:6] = table
        print(f"judge average {avg} over {len(scores)} outfits")
    if judge_error:
        lines[6:6] = [f"> **Judge unavailable** after {len(scores)} outfit(s): {judge_error}", ""]

    spent = {m: generate.ledger().get(m, 0) - ledger_before.get(m, 0) for m in generate.ledger()}
    shown = sum(1 for _, _, o in report for p in o["pieces"] if p["listing"])
    total = sum(len(o["pieces"]) for _, _, o in report)
    lines += ["## Cost", "", f"- Live RapidAPI searches: {live_used}"
              + (f" (resale counter {resale_before} → {quota.count('RESALE_API_HOST')})" if resale_before is not None else ""),
              f"- Model calls: { {m: n for m, n in spent.items() if n} }",
              f"- Pieces with a real listing: {shown} of {total}", ""]
    out = config.RESULTS_DIR / f"stylist_eval_{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    out.write_text(config.redact("\n".join(lines)), encoding="utf-8")
    print(f"wrote {out.relative_to(config.ROOT)} · live {live_used} · model calls {spent} · listings {shown}/{total}")


if __name__ == "__main__":
    main()
