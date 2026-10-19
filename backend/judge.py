"""
LLM-as-judge (A2): scores 1–5, each with a one-line reason, from a different
and stronger model (config.JUDGE_MODEL) at temperature 0.

    judge_search(session, prefs)   one call: the outfit (5 dimensions) and the
                                   fit card (3 dimensions) of one agent run
    judge_stylist(outfit, item, prefs)   a B2 stylist outfit (5 dimensions)

Outfit dimensions: style_match, gender_match, colour_harmony, proportion,
completeness. Fit card dimensions: facts_correct, buyer_voice, verdict_present.

A judge answer that can't be read scores None (left out of averages), never 0.
"""

import json
import re

import config
import generate
from generate import loads_json

OUTFIT_DIMS = ("style_match", "gender_match", "colour_harmony", "proportion", "completeness")
CARD_DIMS = ("facts_correct", "buyer_voice", "verdict_present")

RUBRIC = {
    "style_match": "fits the shopper's chosen styles (or a polished default when none)",
    "gender_match": "every piece suits who they shop for; nothing for the wrong gender or for kids",
    "colour_harmony": "the colours work together as a deliberate palette",
    "proportion": "volumes, lengths and silhouettes balance",
    "completeness": "a wearable head-to-toe outfit, not a list of unrelated items",
    "facts_correct": "the caption's item, price and store match the listing exactly; estimates are "
                     "labelled as estimates, nothing invented",
    "buyer_voice": "written by the shopper who found it, never the seller",
    "verdict_present": "a clear Worth it / Fair deal / Skip verdict with short reasons",
}


def _ask(prompt: str) -> dict:
    raw = generate.generate(prompt, json_mode=True, temperature=0.0, model=config.JUDGE_MODEL, cache=False)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        data = loads_json(cleaned)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _scores(data: dict, dims: tuple) -> dict:
    out = {}
    for dim in dims:
        entry = data.get(dim) if isinstance(data.get(dim), dict) else {}
        score = entry.get("score")
        out[dim] = {"score": int(score) if isinstance(score, (int, float)) and 1 <= score <= 5 else None,
                    "reason": str(entry.get("reason") or "").strip()[:200] or None}
    return out


def average(scores: dict) -> float | None:
    values = [v["score"] for v in scores.values() if v.get("score")]
    return round(sum(values) / len(values), 2) if values else None


def _answer_shape(dims: tuple) -> str:
    return "{" + ", ".join(f'"{d}": {{"score": 1-5, "reason": "<one line>"}}' for d in dims) + "}"


def _shopper(prefs: dict | None) -> str:
    prefs = prefs or {}
    styles = ", ".join(prefs.get("styles") or []) or "none chosen (expect a polished, quiet-luxury default)"
    return f"Shops for: {prefs.get('gender') or 'not stated'}. Styles: {styles}. Fit: {prefs.get('fit') or 'not stated'}."


def judge_search(session: dict, prefs: dict | None = None) -> dict | None:
    """Outfit + fit card of one completed agent run. None if the run has no outfit."""
    item, outfit = session.get("selected_item"), session.get("outfit_suggestion")
    if not item or not outfit:
        return None
    closet = ", ".join(w.get("name", "") for w in (session.get("wardrobe") or {}).get("items") or []) or "empty"
    verdict = session.get("fit_verdict") or {}
    dims = OUTFIT_DIMS + CARD_DIMS
    prompt = (
        "You are a strict fashion editor grading an AI shopping assistant. Score each dimension 1-5 "
        "(5 = excellent, 3 = acceptable, 1 = wrong).\n"
        f"Shopper: {_shopper(prefs)}\nTheir closet: {closet}\n"
        f"Listing: {item['title'].splitlines()[0]} — ${item['price']:.2f} on {item['platform']}"
        f" (condition: {item.get('condition') or 'not stated'})\n\n"
        f"Outfit suggestion:\n{outfit.get('text')}\n\n"
        f"Fit card caption:\n{session.get('fit_card')}\n"
        f"Verdict: {verdict.get('verdict') or 'none'}; reasons: {verdict.get('reasons') or []}; "
        f"retail estimate: {verdict.get('retail') or 'unknown'}\n\n"
        "Rubric:\n" + "\n".join(f"- {d}: {RUBRIC[d]}" for d in dims)
        + f"\n\nAnswer with JSON only: {_answer_shape(dims)}")
    data = _ask(prompt)
    outfit_scores, card_scores = _scores(data, OUTFIT_DIMS), _scores(data, CARD_DIMS)
    return {"outfit": outfit_scores, "outfit_avg": average(outfit_scores),
            "card": card_scores, "card_avg": average(card_scores)}


def judge_stylist(outfit: dict, item: dict, prefs: dict | None = None) -> dict:
    """A B2 outfit built around one closet item: the plan and the listings it kept."""
    pieces = []
    for p in outfit.get("pieces") or []:
        found = p.get("listing")
        shown = (f"listing shown: {found['title'].splitlines()[0][:100]} (${found['price']:.0f})"
                 if found else "no listing shown (described only)")
        pieces.append(f"- {p['label']}: {p['name']} — why: {p.get('why')} — {shown}")
    prompt = (
        "You are a strict fashion editor grading an AI stylist that built an outfit around a client's "
        "own piece. Score each dimension 1-5 (5 = excellent, 3 = acceptable, 1 = wrong). A shown "
        "listing that isn't the planned piece counts against completeness.\n"
        f"Client: {_shopper(prefs)}\n"
        f"Their piece: {item.get('name')} ({item.get('category')}, colours {', '.join(item.get('colors') or [])})\n"
        f"Outfit: {outfit.get('title')} — {outfit.get('concept')}\nPalette: {outfit.get('palette')}\n"
        f"Notes: {outfit.get('notes')}\nPieces:\n" + "\n".join(pieces) + "\n\n"
        "Rubric:\n" + "\n".join(f"- {d}: {RUBRIC[d]}" for d in OUTFIT_DIMS)
        + f"\n\nAnswer with JSON only: {_answer_shape(OUTFIT_DIMS)}")
    scores = _scores(_ask(prompt), OUTFIT_DIMS)
    return {"scores": scores, "avg": average(scores)}
