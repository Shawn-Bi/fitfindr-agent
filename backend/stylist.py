"""
The AI stylist (B2): a complete outfit built FOR one closet item.

    outfit = build_outfit(item, prefs, budget=(10, 40), live_calls=1)

1. plan_outfit()  — the model, as the creative director of a luxury house,
   plans 2–3 pieces from OTHER categories (top / bottom / outerwear / shoes /
   bag) with colour, proportion, fabric and occasion notes, in the user's
   styles (quiet luxury when none are chosen). Code checks the plan: no piece
   in the item's own category, no repeats, 2–3 pieces; a deterministic plan
   steps in if the model's can't be used.
2. candidates()   — real listings for each piece: listings already on hand
   first (fixtures in dev, ≤ 24 h search_cache in live mode), a live search
   only when a piece has nothing and the caller allows live calls. Hard
   rules: same category, gender, not kids, inside the budget, has a photo, no
   clear colour/fabric clash. Then semantic similarity orders them.
3. pick_listings() — one model call sees each piece's top candidates and
   keeps a listing only if it truly fits ("kind": "listing"). Pieces left
   empty get one more live search (within the budget) and a second pick.
4. Every piece gets a picture (P8 never shows an empty tile):
   - "closest": the closest real listing that still matches the piece's
     category, gender and colour family (any budget, any fabric);
   - "ai_preview": an AI-generated flat-lay of the planned piece, stored
     once in Supabase Storage (previews.py), labelled as not a real listing;
   - when image generation isn't available: the closest cached listing in
     the same category ("closest", with a note that the colour differs);
   - "idea" (colour swatches and the name) only if the pool has nothing at
     all in that category.

No listing is invented: every listing is a snapshot of a real response, with
the time it was fetched (`found_at`), and the API hides snapshots older than
24 h in live mode.
"""

import datetime as dt
import json
import re

import attributes
import config
import generate
from generate import loads_json
import ranking
from sources import fetch_candidates, recent_pool
from tools import is_kids_item, is_not_clothing

SLOTS = {"top": "tops", "bottom": "bottoms", "outerwear": "outerwear", "shoes": "shoes", "bag": "accessories"}
# Which slots may be planned around an item of each closet category.
ALLOWED_SLOTS = {
    "tops": ("bottom", "outerwear", "shoes", "bag"),
    "bottoms": ("top", "outerwear", "shoes", "bag"),
    "outerwear": ("top", "bottom", "shoes", "bag"),
    "dresses": ("outerwear", "shoes", "bag"),
    "shoes": ("top", "bottom", "outerwear", "bag"),
    "accessories": ("top", "bottom", "outerwear", "shoes"),
}
SLOT_LABELS = {"top": "Top", "bottom": "Bottom", "outerwear": "Outerwear", "shoes": "Shoes", "bag": "Bag"}
DEFAULT_STYLE = "Quiet luxury / old money"
MAX_CANDIDATES = 5


def _gender_word(gender: str | None) -> str:
    return {"women": "women's", "men": "men's"}.get(gender or "", "")


def _item_line(item: dict) -> str:
    bits = [item.get("name") or "", f"({item.get('category')})"]
    if item.get("colors"):
        bits.append("colours: " + ", ".join(item["colors"]))
    if item.get("style_tags"):
        bits.append("tags: " + ", ".join(item["style_tags"]))
    if item.get("brand"):
        bits.append("brand: " + item["brand"])
    if item.get("notes"):
        bits.append("notes: " + item["notes"])
    return " ".join(bits)


# ── 1. The plan ──────────────────────────────────────────────────────────────

def plan_prompt(item: dict, prefs: dict, budget: tuple) -> str:
    styles = prefs.get("styles") or [DEFAULT_STYLE]
    gender = prefs.get("gender")
    who = {"women": "a woman", "men": "a man"}.get(gender or "", "someone")
    allowed = ALLOWED_SLOTS.get(item.get("category"), tuple(SLOTS))
    low, high = budget
    budget_text = (f"${low:.0f}–${high:.0f} per piece" if low and high else
                   f"up to ${high:.0f} per piece" if high else "any budget")
    m = prefs.get("measurements") or {}
    body = ""
    if m.get("height"):
        body = f" Height: {m['height']} {'cm' if m.get('unit') == 'cm' else 'in'}."
    if prefs.get("sizes_text"):
        body += f" Sizes (US): {prefs['sizes_text']}."
    return (
        "You are the creative director of a luxury fashion house, styling a client's own piece.\n"
        f"The client is {who}. Their piece: {_item_line(item)}.\n"
        f"Their styles: {', '.join(styles)}"
        + (" (no styles chosen: use an elevated quiet-luxury look)" if not prefs.get("styles") else "")
        + f". Fit preference: {prefs.get('fit') or 'not stated'}.{body}\n"
        f"Secondhand budget: {budget_text}.\n\n"
        "Plan ONE complete outfit around their piece: 2 or 3 complementary pieces to find secondhand, "
        f"each from a different slot, chosen only from: {', '.join(allowed)}. Never the piece's own "
        "category. Use colour theory (a deliberate palette), proportion (balance volume and length), "
        "fabric (texture contrast, season) and a clear occasion.\n\n"
        "Answer with JSON only:\n"
        '{"title": "<3-6 word outfit name>",\n'
        ' "concept": "<one or two sentences, the creative direction>",\n'
        ' "palette": ["<colour>", "<colour>", "<colour>"],\n'
        ' "occasion": "<where to wear it, a few words>",\n'
        ' "notes": {"colour": "<one sentence>", "proportion": "<one sentence>", "fabric": "<one sentence>"},\n'
        ' "pieces": [{"slot": "<slot>", "name": "<specific piece, e.g. Cream wide-leg wool trousers>",\n'
        '             "colors": ["<main colour>"], "material": "<fabric or null>",\n'
        f'             "search": "<3-5 word store search, starting with {_gender_word(gender) or "the type"}>",\n'
        '             "why": "<one line on why it works with their piece>"}]}\n'
        "Pieces must be things resale stores really sell, described plainly (colour + fabric + type)."
    )


def _clean_piece(raw: dict, allowed: tuple, gender: str | None) -> dict | None:
    slot = str(raw.get("slot") or "").strip().lower()
    slot = {"tops": "top", "bottoms": "bottom", "shoe": "shoes", "handbag": "bag", "purse": "bag",
            "jacket": "outerwear", "coat": "outerwear"}.get(slot, slot)
    name = re.sub(r"\s+", " ", str(raw.get("name") or "")).strip()[:80]
    if slot not in allowed or not name:
        return None
    colors = [str(c).strip().lower()[:20] for c in raw.get("colors") or [] if str(c).strip()][:3]
    material = str(raw.get("material") or "").strip().lower()[:20] or None
    if material in ("null", "none"):
        material = None
    search = re.sub(r"\s+", " ", str(raw.get("search") or name)).strip()[:60]
    gw = _gender_word(gender)
    if gw and not re.search(r"\b(wo)?men['’]?s\b", search, re.I):
        search = f"{gw} {search}"
    return {"slot": slot, "category": SLOTS[slot], "label": SLOT_LABELS[slot], "name": name,
            "colors": colors, "material": material, "search": search,
            "why": re.sub(r"\s+", " ", str(raw.get("why") or "")).strip()[:160] or None}


def parse_plan(raw: str, item: dict, gender: str | None) -> dict | None:
    """Model JSON → a checked plan, or None if fewer than 2 usable pieces."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        data = loads_json(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    allowed = ALLOWED_SLOTS.get(item.get("category"), tuple(SLOTS))
    pieces, used = [], set()
    for raw_piece in data.get("pieces") or []:
        piece = _clean_piece(raw_piece if isinstance(raw_piece, dict) else {}, allowed, gender)
        if piece and piece["slot"] not in used:
            used.add(piece["slot"])
            pieces.append(piece)
    if len(pieces) < 2:
        return None
    notes = data.get("notes") if isinstance(data.get("notes"), dict) else {}
    return {
        "title": str(data.get("title") or "").strip()[:60] or f"Built around your {item.get('name', 'piece').lower()}",
        "concept": str(data.get("concept") or "").strip()[:400] or None,
        "palette": [str(c).strip()[:20] for c in data.get("palette") or [] if str(c).strip()][:5],
        "occasion": str(data.get("occasion") or "").strip()[:80] or None,
        "notes": {k: str(notes.get(k) or "").strip()[:240] or None for k in ("colour", "proportion", "fabric")},
        "pieces": pieces[:3],
        "planner": "gemini",
    }


# A plan that is always valid, for when the model's can't be used: neutral,
# elevated basics in the item's opposite slots.
_TEMPLATE = {
    "top": ("Ivory silk blouse", ["cream"], "silk"),
    "bottom": ("Camel wide-leg wool trousers", ["camel"], "wool"),
    "outerwear": ("Camel wool coat", ["camel"], "wool"),
    "shoes": ("Black leather loafers", ["black"], "leather"),
    "bag": ("Black leather shoulder bag", ["black"], "leather"),
}


def template_plan(item: dict, gender: str | None) -> dict:
    allowed = ALLOWED_SLOTS.get(item.get("category"), tuple(SLOTS))
    order = [s for s in ("bottom", "top", "shoes", "outerwear", "bag") if s in allowed][:3]
    pieces = []
    for slot in order:
        name, colors, material = _TEMPLATE[slot]
        if gender == "men" and slot == "top":
            name = "Ivory oxford shirt"
        search = " ".join(filter(None, [_gender_word(gender), colors[0], material, name.split()[-1].lower()]))
        pieces.append({"slot": slot, "category": SLOTS[slot], "label": SLOT_LABELS[slot], "name": name,
                       "colors": colors, "material": material, "search": search,
                       "why": "A neutral, well-made staple that lets your piece lead."})
    return {"title": "Elevated neutrals", "concept": "Quiet, well-made neutrals that let your piece lead.",
            "palette": ["camel", "cream", "black"], "occasion": "Everyday, polished",
            "notes": {"colour": None, "proportion": None, "fabric": None}, "pieces": pieces,
            "planner": "template"}


def plan_outfit(item: dict, prefs: dict, budget: tuple, cache_ok: bool = True) -> dict:
    try:
        raw = generate.generate(plan_prompt(item, prefs, budget), json_mode=True, cache=cache_ok)
        plan = parse_plan(raw, item, prefs.get("gender"))
    except Exception:  # noqa: BLE001 — the template keeps the page useful
        plan = None
    return plan or template_plan(item, prefs.get("gender"))


# ── 2. Candidates ────────────────────────────────────────────────────────────

def piece_text(piece: dict) -> str:
    return " ".join(filter(None, [" ".join(piece.get("colors") or []), piece.get("material"), piece["name"]]))


def fits_rules(listing: dict, piece: dict, gender: str | None, budget: tuple) -> bool:
    low, high = budget
    if not listing.get("image_url") or is_kids_item(listing) or is_not_clothing(listing):
        return False
    if high is not None and listing["price"] > high:
        return False
    if low is not None and listing["price"] < low:
        return False
    if attributes.listing_category(listing) != piece["category"]:
        return False
    if not attributes.gender_ok(listing, gender):
        return False
    wanted = {"category": piece["category"], "colors": attributes.colors_in(" ".join(piece.get("colors") or [])),
              "materials": attributes.materials_in(piece.get("material") or ""), "gender": None}
    return attributes.clear_mismatch(wanted, listing) is None


def _dedupe(listings: list[dict]) -> list[dict]:
    seen, out = set(), []
    for item in listings:
        key = (item["platform"], item["id"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def candidates(piece: dict, pool: list[dict], gender: str | None, budget: tuple,
               patient: bool = True) -> list[dict]:
    """The piece's best few listings from `pool`, by similarity, after the hard rules."""
    ok = [listing for listing in _dedupe(pool) if fits_rules(listing, piece, gender, budget)]
    if not ok:
        return []
    sims = ranking.similarity(piece_text(piece), ok, patient=patient)
    if sims is None:   # no embeddings: keyword overlap
        words = set(re.findall(r"[a-z]{3,}", piece_text(piece).lower()))
        sims = [len(words & set(re.findall(r"[a-z]{3,}", ranking.listing_text(x).lower()))) / max(1, len(words))
                for x in ok]
    scored = sorted(zip(sims, range(len(ok))), reverse=True)
    return [{**ok[i], "_sim": round(s, 4)} for s, i in scored[:MAX_CANDIDATES]]


def live_search(query: str, budget: tuple) -> tuple[list[dict], bool]:
    """
    (listings, made_a_live_call) for one store search. The ≤ 24 h cache answers
    first; otherwise one counted live call. ([], False) in fixtures mode or
    when the store is paused.
    """
    if config.DATA_MODE != "live":
        return [], False
    low, high = budget
    listings, statuses = fetch_candidates(query, max_price=high, min_price=low)
    return listings, any(s["status"] == "active" for s in statuses)


# ── 3. The final pick ────────────────────────────────────────────────────────

def pick_prompt(item: dict, plan: dict, options: list[list[dict]], gender: str | None) -> str:
    lines = [f"A stylist planned an outfit around the client's {_item_line(item)}.",
             f"Client shops {_gender_word(gender) or 'any'} clothing. Plan: {plan.get('concept') or plan['title']}.",
             "For each planned piece, choose the ONE listing that best stands in for it, or null if "
             "none fits. Required: the same type of garment (trousers for trousers, loafers for "
             "loafers), the same colour family, and cut for the client. Preferred, not required: the "
             "exact fabric and details. Loungewear, kids' sizes or a different garment never fit — a "
             "wrong item is worse than none.\n"]
    for n, (piece, cands) in enumerate(zip(plan["pieces"], options)):
        lines.append(f"Piece {n}: {piece['name']} ({piece['label']})")
        for i, c in enumerate(cands):
            lines.append(f"  [{i}] {ranking.listing_text(c)[:140]} — ${c['price']:.0f}")
        if not cands:
            lines.append("  (no listings)")
    lines.append('\nAnswer with JSON only: {"choices": [{"piece": 0, "index": <number or null>, '
                 '"reason": "<under 12 words>"}, ...]}')
    return "\n".join(lines)


def pick_listings(item: dict, plan: dict, options: list[list[dict]], gender: str | None,
                  cache_ok: bool = True) -> list[tuple[int | None, str | None]]:
    """[(index or None, reason)] per piece. Without the model, nothing is shown (never a guess)."""
    if not any(options):
        return [(None, None)] * len(options)
    try:
        raw = generate.generate(pick_prompt(item, plan, options, gender), json_mode=True,
                                temperature=0.0, cache=cache_ok)
        data = loads_json(raw)
        # The model sometimes answers with the bare list instead of {"choices": [...]}.
        rows = data if isinstance(data, list) else data.get("choices") or []
        choices = {int(c.get("piece")): c for c in rows if isinstance(c, dict)}
    except Exception:  # noqa: BLE001
        return [(None, None)] * len(options)
    out = []
    for n, cands in enumerate(options):
        c = choices.get(n) or {}
        index = c.get("index")
        if isinstance(index, int) and 0 <= index < len(cands):
            out.append((index, str(c.get("reason") or "").strip()[:120] or None))
        else:
            out.append((None, None))
    return out


# ── The whole outfit ─────────────────────────────────────────────────────────

def _found_at(listing: dict) -> str:
    return listing.get("updated_at") or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def public_listing(listing: dict) -> dict:
    keep = ("id", "title", "price", "size", "platform", "url", "image_url", "condition",
            "updated_at", "category", "brand", "listed_at")
    return {k: listing.get(k) for k in keep}


def _ranked(piece: dict, listings: list[dict], patient: bool) -> list[dict]:
    if not listings:
        return []
    sims = ranking.similarity(piece_text(piece), listings, patient=patient)
    if sims is None:   # no embeddings: keyword overlap
        words = set(re.findall(r"[a-z]{3,}", piece_text(piece).lower()))
        sims = [len(words & set(re.findall(r"[a-z]{3,}", ranking.listing_text(x).lower()))) / max(1, len(words))
                for x in listings]
    return [listings[i] for _, i in sorted(zip(sims, range(len(listings))), key=lambda t: -t[0])]


def _usable_photo(listing: dict, piece: dict, gender: str | None) -> bool:
    return (bool(listing.get("image_url")) and not is_kids_item(listing) and not is_not_clothing(listing)
            and attributes.listing_category(listing) == piece["category"]
            and attributes.gender_ok(listing, gender))


def closest_find(piece: dict, pool: list[dict], gender: str | None, patient: bool = True,
                 same_colour: bool = True) -> dict | None:
    """
    The closest real listing for a piece no listing passed the strict check
    for: same category and gender, and (same_colour) a colour of the same
    family named in the title. Any price, any fabric.
    """
    wanted = attributes.colors_in(" ".join(piece.get("colors") or []))
    families = {attributes.COLOR_FAMILY.get(c, c) for c in wanted}
    ok = []
    for listing in _dedupe(pool):
        if not _usable_photo(listing, piece, gender):
            continue
        if same_colour and families:
            found = {attributes.COLOR_FAMILY.get(c, c) for c in attributes.colors_in(listing["title"])}
            if not found & families:
                continue
        ok.append(listing)
    ranked = _ranked(piece, ok, patient)
    return ranked[0] if ranked else None


def build_outfit(item: dict, prefs: dict, budget: tuple = (None, None), *, live_calls: int = 0,
                 plan: dict | None = None, pool: list[dict] | None = None,
                 patient: bool = True, cache_ok: bool = True, previews_ok: bool = True) -> dict:
    """
    The finished outfit (see module docstring). `live_calls` caps live
    RapidAPI searches for this outfit (0 = cached/fixtures only). `plan` and
    `pool` let the overnight batch plan first and share searches.
    `previews_ok` allows AI preview images for pieces with no listing at all.
    """
    import previews

    gender = prefs.get("gender")
    with generate.meter() as m:
        plan = plan or plan_outfit(item, prefs, budget, cache_ok=cache_ok)
        pool = list(pool if pool is not None else recent_pool())
        searched, live_used = set(), 0

        def search_live(piece) -> bool:
            nonlocal live_used
            if live_used >= live_calls or piece["search"].lower() in searched:
                return False
            searched.add(piece["search"].lower())
            try:
                found, was_live = live_search(piece["search"], budget)
            except Exception:  # noqa: BLE001 — a paused or failing store just means no listing
                return False
            live_used += int(was_live)
            pool.extend(found)
            return bool(found)

        options = []
        for piece in plan["pieces"]:
            found = candidates(piece, pool, gender, budget, patient=patient)
            if not found and search_live(piece):
                found = candidates(piece, pool, gender, budget, patient=patient)
            options.append(found)
        picks = pick_listings(item, plan, options, gender, cache_ok=cache_ok)
        # Pieces the strict pick left empty: one more live search each (budget allowing), then re-pick.
        retry = [n for n, (index, _) in enumerate(picks) if index is None and search_live(plan["pieces"][n])]
        if retry:
            for n in retry:
                options[n] = candidates(plan["pieces"][n], pool, gender, budget, patient=patient)
            again = pick_listings(item, plan, options, gender, cache_ok=cache_ok)
            for n in retry:
                picks[n] = again[n]

        pieces = []
        for piece, cands, (index, reason) in zip(plan["pieces"], options, picks):
            listing = cands[index] if index is not None else None
            kind, note, preview_path = "listing", None, None
            if listing is None:
                listing = closest_find(piece, pool, gender, patient=patient)
                kind = "closest" if listing else None
            if listing is None and previews_ok:
                preview_path = previews.get_or_create(piece, gender)
                kind = "ai_preview" if preview_path else None
            if kind is None:   # no image model: the closest cached photo in the same category
                listing = closest_find(piece, pool, gender, patient=patient, same_colour=False)
                kind, note = ("closest", "Similar piece in a different colour") if listing else ("idea", None)
            pieces.append({**piece, "kind": kind,
                           "listing": public_listing(listing) if listing else None,
                           "found_at": _found_at(listing) if listing else None,
                           "match_reason": reason if kind == "listing" else None,
                           "closest_note": note,
                           "preview_path": preview_path,
                           "similarity": listing.get("_sim") if listing else None})
    return {
        "version": 2,
        "item": {k: item.get(k) for k in ("id", "name", "category", "colors")},
        **{k: plan.get(k) for k in ("title", "concept", "palette", "occasion", "notes", "planner")},
        "styles": prefs.get("styles") or [DEFAULT_STYLE],
        "default_style": not prefs.get("styles"),
        "pieces": pieces,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "data_mode": config.DATA_MODE,
        "live_calls": live_used,
        "usage": {"calls": m["calls"], "prompt_tokens": m["prompt_tokens"],
                  "output_tokens": m["output_tokens"], "est_cost_usd": round(m["est_cost_usd"], 6)},
    }


def hide_stale(outfit: dict, max_age_hours: int = config.CACHE_MAX_AGE_HOURS) -> dict:
    """
    Live mode shows only listing snapshots ≤ 24 h old (CLAUDE.md data rule 1);
    an older one becomes a "Search this" description again.
    """
    if config.DATA_MODE != "live":
        return outfit
    now = dt.datetime.now(dt.timezone.utc)
    pieces = []
    for piece in outfit.get("pieces") or []:
        found = piece.get("found_at")
        try:
            age = now - dt.datetime.fromisoformat(str(found).replace("Z", "+00:00"))
        except ValueError:
            age = None
        if piece.get("listing") and (age is None or age > dt.timedelta(hours=max_age_hours)):
            piece = {**piece, "listing": None, "match_reason": None, "expired": True,
                     "kind": "ai_preview" if piece.get("preview_path") else "idea"}
        pieces.append(piece)
    return {**outfit, "pieces": pieces}

