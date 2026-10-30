#!/usr/bin/env python3
"""
Run the scenarios repeatedly and write the results down.

    python run_eval.py --label v2          five tries, the default, with the judge
    python run_eval.py --tries 10          more tries
    python run_eval.py --no-judge          skip the LLM-as-judge scores
    python run_eval.py --allow-fallback    let a spent daily quota switch to the fallback model

Every scenario in `scenarios.py` runs five separate times with caching off,
so five tries are five real answers. Each try is scored automatically
against its criterion in `criteria.md` (the checks are below, one function
per criterion), and every completed try is graded by the LLM judge
(judge.py): outfit quality on five dimensions and the fit card on three,
one judge call per scenario (judge_search_many).

The eval measures config.MODEL, so the fallback model is off by default: if
a daily quota runs out mid-run, the run stops, writes what it has, marked
INCOMPLETE, and exits with status 2. Rerun after midnight Pacific time.

The run log goes to results/run_<date>_<label>.md with the criteria table,
the judge averages, the model calls spent and the full output of each try.
"""

import argparse
import datetime as dt
import re
import sys
import traceback
from unittest import mock

import config
import scenarios as scenario_module
from tools import seller_voice

TARGETS = {1: 4, 2: 5, 3: 5, 4: 4, 5: 5, 6: 5, 7: 5}
STORE_NAMES = {"ebay": "ebay", "depop": "depop", "poshmark": "poshmark", "mercari": "mercari",
               "etsy": "etsy", "fb_marketplace": "facebook"}


def run_once(scenario, use_trace=True):
    """One scenario, one try. Returns everything worth recording."""
    import agent
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
    import trace as trace_module

    wardrobe = (
        get_empty_wardrobe() if scenario["wardrobe"] == "empty" else get_example_wardrobe()
    )

    if use_trace:
        trace_module.start_trace()

    record = {"error": None, "session": None, "trace": "", "crashed": None, "styled_ids": []}
    real_outfit = agent.suggest_outfit

    def spy(item, wardrobe_arg):   # criterion 3: which item really went into suggest_outfit
        record["styled_ids"].append(item.get("id"))
        return real_outfit(item, wardrobe_arg)

    try:
        with mock.patch.object(agent, "suggest_outfit", side_effect=spy):
            record["session"] = agent.run_agent(scenario["query"], wardrobe)
    except Exception as exc:  # noqa: BLE001 — a crash is a result worth logging
        record["crashed"] = f"{type(exc).__name__}: {config.redact(exc)}"
        record["traceback"] = traceback.format_exc()

    if use_trace:
        record["trace"] = trace_module.get_trace()

    return record


# ── Automatic checks, one per criterion (criteria.md) ────────────────────────

def _tools(session):
    return [s["tool"] for s in session.get("steps") or [] if "refused" not in str(s.get("result"))[:12]]


def _price_strings(price: float) -> list[str]:
    whole = f"${price:.0f}"
    return [f"${price:.2f}", whole] if float(price).is_integer() else [f"${price:.2f}"]


def check_fit_card(card: str, item: dict) -> tuple[bool, str]:
    """Criterion 4 (revised): category word + one other title word, exact price, platform."""
    import attributes
    text = (card or "").lower()
    title_words = [w for w in re.findall(r"[a-z0-9']{4,}", item["title"].lower())]
    category_hit = bool(attributes.listing_category({"title": card}))
    other = any(w in text for w in title_words)
    price = any(p.lower() in text for p in _price_strings(item["price"]))
    store = STORE_NAMES.get(item["platform"], item["platform"]) in text
    missing = [n for n, ok in (("item", category_hit and other), ("price", price), ("platform", store)) if not ok]
    return not missing, ("ok" if not missing else "missing " + ", ".join(missing))


def check(criterion, record) -> tuple[bool, str]:
    s = record["session"] or {}
    if record["crashed"]:
        return False, "crashed"
    tools_used = _tools(s)
    if criterion == 1:
        ok = all(t in tools_used for t in ("search_listings", "suggest_outfit", "create_fit_card")) and s.get("fit_card")
        return bool(ok), "all three tools" if ok else f"tools: {tools_used}"
    if criterion == 2:
        ok = "suggest_outfit" not in tools_used and bool(s.get("error")) and "Try" in s["error"]
        return ok, "stopped with a fix to try" if ok else f"tools: {tools_used}"
    if criterion == 3:
        item = s.get("selected_item") or {}
        ok = bool(item) and record["styled_ids"] == [item.get("id")]
        return ok, "same id" if ok else f"selected {item.get('id')} vs styled {record['styled_ids']}"
    if criterion == 4:
        if not s.get("fit_card"):
            return False, "no fit card"
        return check_fit_card(s["fit_card"], s["selected_item"])
    if criterion == 5:
        text = ((s.get("outfit_suggestion") or {}).get("text") or "").strip()
        return bool(text), "styling given" if text else "no styling"
    if criterion == 6:
        relaxed = s.get("relaxed") or {}
        ok = (tools_used.count("relax_search") == 1 and relaxed.get("dropped") == "size"
              and "size" in (relaxed.get("message") or "") and s["parsed"].get("max_price") == 50
              and bool(s.get("fit_card")))
        return ok, relaxed.get("message") or f"tools: {tools_used}"
    if criterion == 7:
        question = ((s.get("clarify") or {}).get("question") or "").strip()
        ok = (tools_used[:1] == ["ask_user"] and "search_listings" not in tools_used
              and question.endswith("?") and len(question.split()) <= 20)
        return ok, question or f"tools: {tools_used}"
    return False, "no check"


def main():
    parser = argparse.ArgumentParser(description="Run the scenarios and log the results.")
    parser.add_argument("--tries", "--trials", type=int, default=5, dest="tries",
                        help="tries per scenario (default 5, matching your criteria)")
    parser.add_argument("--label", default="", help="a name for this run, e.g. 'before'")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM-as-judge scores")
    parser.add_argument("--allow-fallback", action="store_true",
                        help="use config.FALLBACK_MODEL when a daily quota runs out (off: the run stops)")
    args = parser.parse_args()

    problems = scenario_module.validate()
    if problems:
        print("scenarios.py has problems:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)

    if args.tries < 5:
        print(f"⚠️  {args.tries} tries. The criteria are written out of five.\n")

    # Caching off. Five tries have to be five real answers.
    config.CACHE_ENABLED = False
    if not args.allow_fallback:
        config.FALLBACK_MODEL = ""   # grade the main model, never a stand-in
    print(f"Cache is OFF for this run — that's deliberate. Planner: {config.AGENT_PLANNER}\n")

    import generate
    import judge
    before = dict(generate.ledger())

    rows = []
    for scenario in scenario_module.SCENARIOS:
        print(f"{scenario['name']}  ({scenario['wardrobe']} wardrobe)")
        print(f"  query: {scenario['query']}")

        tries = []
        for attempt in range(1, args.tries + 1):
            record = run_once(scenario)
            record["check"] = check(scenario["criterion"], record)
            tries.append(record)
            ok, why = record["check"]
            print(f"  try {attempt}: {'PASS' if ok else 'FAIL'} — {why[:90]}")
            if generate.daily_exhausted:
                break

        if not args.no_judge and not generate.daily_exhausted:
            sessions = [r["session"] or {} for r in tries]
            if any(s.get("outfit_suggestion") for s in sessions):
                try:
                    for record, scores in zip(tries, judge.judge_search_many(sessions)):
                        record["judge"] = scores
                except Exception as exc:  # noqa: BLE001
                    print(f"    judge failed: {config.redact(exc)[:80]}")

        rows.append({"scenario": scenario, "tries": tries})
        print()
        if generate.daily_exhausted:
            stopped = ", ".join(sorted(generate.daily_exhausted))
            print(f"STOPPED: daily free-tier quota used up for {stopped}. "
                  "Rerun after midnight Pacific time; this run is INCOMPLETE.")
            args.incomplete = stopped
            break

    after = generate.ledger()
    spent = {m: after.get(m, 0) - before.get(m, 0) for m in after if after.get(m, 0) - before.get(m, 0)}
    write_report(rows, args, spent)
    if getattr(args, "incomplete", None):
        sys.exit(2)


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def write_report(rows, args, spent):
    import judge

    config.RESULTS_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    label = f"_{args.label}" if args.label else ""
    path = config.RESULTS_DIR / f"run_{stamp}{label}.md"

    n = args.tries
    headers = " | ".join(f"Try {i}" for i in range(1, n + 1))
    divider = "|".join(["---"] * n)

    lines = [
        f"# Run log{f' — {args.label}' if args.label else ''}",
        "",
    ] + ([f"> **INCOMPLETE:** the daily free-tier quota ran out for {args.incomplete}; "
          "the run stopped there. Rerun after midnight Pacific time.", ""]
         if getattr(args, "incomplete", None) else []) + [
        "- Produced by: `run_eval.py::main`",
        f"- Agent: `agent.py::run_agent`, planner `{config.AGENT_PLANNER}` · tools: `tools.py`",
        f"- Tries per scenario: {n}, caching off · data: {config.DATA_MODE}",
        f"- Temperature: {config.TEMPERATURE} · model {config.MODEL} · judge {config.JUDGE_MODEL}",
        f"- When: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Model calls this run: {spent or 'none'}",
        "",
        "Each try is checked automatically against its criterion (`run_eval.py::check`).",
        "",
        f"| Criterion | Target | {headers} | Verdict |",
        f"|---|---|{divider}|---|",
    ]

    for row in rows:
        scenario = row["scenario"]
        number = scenario.get("criterion")
        cells = ["PASS" if r["check"][0] else "FAIL" for r in row["tries"]]
        passed = cells.count("PASS")
        target = TARGETS.get(number, n)
        verdict = f"{'MET' if passed >= target else 'MISSED'} ({passed}/{n})"
        lines.append(f"| {number}. {scenario['name']} | {target} of 5 | {' | '.join(cells)} | {verdict} |")

    # Automatic check: every fit card must read as the buyer, not the seller.
    cards = [(row["scenario"]["name"], i, (r["session"] or {}).get("fit_card"))
             for row in rows for i, r in enumerate(row["tries"], 1)
             if r["session"] and (r["session"] or {}).get("fit_card")]
    bad = [(name, i, seller_voice(card)) for name, i, card in cards if seller_voice(card)]
    lines += [
        "",
        "## Automatic check: buyer voice",
        "",
        f"Fit cards written as the buyer (no 'listed', 'selling', 'my shop'…): "
        f"**{len(cards) - len(bad)} / {len(cards)}**"
        + (" — PASS" if not bad else " — FAIL"),
        "",
    ] + [f"- {name}, try {i}: {phrases}" for name, i, phrases in bad]

    # With a closet, the outfit names at least one closet item (PRD §8: 4 of 5).
    styled = [(row["scenario"]["name"], i, (r["session"] or {}).get("outfit_suggestion"))
              for row in rows if row["scenario"]["wardrobe"] == "example"
              for i, r in enumerate(row["tries"], 1)
              if r["session"] and (r["session"] or {}).get("outfit_suggestion")]
    no_closet = [(name, i) for name, i, outfit in styled if not (outfit or {}).get("item_ids")]
    lines += [
        "",
        "## Automatic check: outfit uses the closet",
        "",
        f"Outfits (example wardrobe) naming at least one closet item: "
        f"**{len(styled) - len(no_closet)} / {len(styled)}**"
        + (" — PASS" if styled and len(styled) - len(no_closet) >= 0.8 * len(styled) else " — FAIL"),
        "",
    ] + [f"- {name}, try {i}: no closet item ids" for name, i in no_closet]

    # Verdict present on every fit card (B1).
    verdicts = [(r["session"] or {}).get("fit_verdict") for row in rows for r in row["tries"]
                if (r["session"] or {}).get("fit_card")]
    with_verdict = sum(1 for v in verdicts if v and v.get("verdict"))
    lines += ["", "## Automatic check: buyer's verdict present", "",
              f"Fit cards with a Worth it / Fair deal / Skip verdict: **{with_verdict} / {len(verdicts)}**", ""]
    by_code = sum(1 for row in rows for r in row["tries"] if (r["session"] or {}).get("fit_card_by") == "code")
    lines += [f"Fit cards written in code because the model was unavailable: **{by_code}**"
              + (" (they pass the fact checks but have no verdict)" if by_code else ""), ""]

    # LLM-as-judge averages.
    judged = [r["judge"] for row in rows for r in row["tries"] if r.get("judge")]
    if judged:
        lines += ["", "## LLM-as-judge (1–5)", "",
                  f"{len(judged)} completed tries graded by `{config.JUDGE_MODEL}` at temperature 0.", "",
                  "| Dimension | Average |", "|---|---|"]
        for dim in judge.OUTFIT_DIMS:
            lines.append(f"| Outfit · {dim} | {_avg([j['outfit'][dim]['score'] for j in judged])} |")
        for dim in judge.CARD_DIMS:
            lines.append(f"| Fit card · {dim} | {_avg([j['card'][dim]['score'] for j in judged])} |")
        lines += [f"| **Outfit overall** | **{_avg([j['outfit_avg'] for j in judged])}** |",
                  f"| **Fit card overall** | **{_avg([j['card_avg'] for j in judged])}** |", ""]

    lines += ["", "---", "", "## What actually happened", ""]

    for row in rows:
        scenario = row["scenario"]
        lines += [f"### {scenario['name']}", "",
                  f"- Query: `{scenario['query']}`",
                  f"- Wardrobe: {scenario['wardrobe']}", ""]

        for i, record in enumerate(row["tries"], 1):
            ok, why = record["check"]
            lines.append(f"**Try {i}** — {'PASS' if ok else 'FAIL'}: {why}")
            lines.append("")

            if record["crashed"]:
                lines += ["Crashed:", "", "```", record["crashed"], "```", ""]
                continue

            session = record["session"] or {}
            item = session.get("selected_item") or {}
            usage = session.get("usage") or {}
            lines += [
                f"- planner: {session.get('planner')} · steps: {[s['tool'] for s in session.get('steps') or []]}"
                f" · model calls: {usage.get('calls')} · {usage.get('latency_ms')} ms",
                f"- stopped early: {'yes — ' + str(session.get('error')) if session.get('error') else 'no'}",
                f"- selected_item: {item.get('title', '(none)')}"
                + (f" (${item.get('price')}, {item.get('platform')})" if item else ""),
                f"- search_results: {len(session.get('search_results') or [])}",
                "",
            ]
            if session.get("relaxed"):
                lines += [f"- relaxed: {session['relaxed']['message']}", ""]
            if session.get("clarify"):
                lines += [f"- asked: {session['clarify']['question']} {session['clarify']['suggestions']}", ""]
            if session.get("styling_error"):
                lines += [f"- styling unavailable: {session['styling_error']}", ""]
            if session.get("outfit_suggestion"):
                outfit = session["outfit_suggestion"]
                lines += ["Outfit suggestion:", "", "```", str(outfit.get("text")), "```", "",
                          f"Closet items used: {outfit.get('item_ids') or '(none)'}", ""]
            if session.get("fit_card"):
                lines += ["Fit card:", "", "```", str(session["fit_card"]), "```", ""]
                verdict = session.get("fit_verdict") or {}
                lines += [f"Verdict: {verdict.get('verdict')} — {verdict.get('reasons')} · retail "
                          f"{verdict.get('retail') or 'unknown'} · era {verdict.get('era') or 'unknown'}", ""]
            if record.get("judge"):
                j = record["judge"]
                lines += [f"Judge: outfit {j['outfit_avg']} "
                          f"({', '.join(f'{d} {v['score']}' for d, v in j['outfit'].items())}); "
                          f"card {j['card_avg']} ({', '.join(f'{d} {v['score']}' for d, v in j['card'].items())})", ""]
            if record["trace"]:
                lines += ["Trace:", "", "```", record["trace"], "```", ""]

    # Run logs get committed: scrub any key values first.
    path.write_text(config.redact("\n".join(lines)), encoding="utf-8")

    import generate

    print(f"Wrote {path.relative_to(config.ROOT)}")
    for row in rows:
        passed = sum(1 for r in row["tries"] if r["check"][0])
        print(f"  criterion {row['scenario']['criterion']}: {passed}/{len(row['tries'])}")
    print(f"Buyer voice: {len(cards) - len(bad)}/{len(cards)} fit cards")
    print(f"Closet items named: {len(styled) - len(no_closet)}/{len(styled)} outfits")
    if judged:
        print(f"Judge: outfit {_avg([j['outfit_avg'] for j in judged])}, card {_avg([j['card_avg'] for j in judged])}")
    print(f"Model calls: {spent}")
    print(generate.usage())


if __name__ == "__main__":
    main()
