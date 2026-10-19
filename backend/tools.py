"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import json
import re

import config
from generate import generate, loads_json
from sources import fetch_candidates


# ── Search helpers ────────────────────────────────────────────────────────────

# Kids' items are dropped unless the query asks for them. The store category is
# the reliable signal ("Girls bottoms"); titles only count on unambiguous
# markers, so "Spice Girls tee" or "Kid Cudi tee" stay in.
_KIDS_QUERY = re.compile(
    r"\b(kids?|child(ren)?|girls?|boys?|toddlers?|bab(y|ies)|infants?|youth|"
    r"newborn|\d{1,2}T)\b", re.I)
_KIDS_CATEGORY = re.compile(
    r"\b(girls?|boys?|kids?|child(ren)?|toddlers?|bab(y|ies)|infants?|youth)\b", re.I)
_KIDS_TITLE = re.compile(
    r"\b(kids|kid['’]s|children['’]?s?|toddlers?|bab(y|ies)|infants?|youth|newborn)\b"
    r"|\b(girl|boy)['’]s\b|\b(girls|boys)['’]"
    r"|\b\d{1,2}T\b|\b\d{1,2}\s?(mos|months)\b", re.I)


def wants_kids(query: str) -> bool:
    return bool(_KIDS_QUERY.search(query or ""))


def is_kids_item(item: dict) -> bool:
    return bool(_KIDS_CATEGORY.search(item.get("category") or "")
                or _KIDS_TITLE.search(item.get("title") or ""))


def _tokens(text) -> list[str]:
    return [t for t in re.split(r"[\s/(),]+", str(text or "").lower()) if t]


def size_matches(size: str, item_size: str | None) -> bool:
    """
    Whole-token match, case-insensitive: "M" matches "S/M" but not "XL" or
    "US 9"; a bare waist like "30" also matches "W30" and "30x32".
    """
    wanted = size.lower().strip()
    for token in _tokens(item_size):
        if token == wanted:
            return True
        if wanted.isdigit() and (token == f"w{wanted}" or token.startswith(f"{wanted}x")):
            return True
    return False


def closet_affinity(item: dict, wardrobe: dict | None) -> int:
    """How many of the closet's colors and style tags show up in the listing title."""
    words = set()
    for owned in (wardrobe or {}).get("items", []):
        for value in (owned.get("colors") or []) + (owned.get("style_tags") or []):
            words.update(w for w in _tokens(value) if len(w) > 2)
    title = set(_tokens(item.get("title")))
    return len(words & title)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the six US resale stores (via sources/) for items matching a
    description, and optionally a size and a price ceiling. In fixtures mode
    this reads recorded real responses from tests/fixtures/; it never reads
    mock data.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict is the FitFindr standard listing (sources/normalize.py):
        id, title, price (float, USD), size, platform, url, image_url,
        plus optional condition, updated_at. Missing values are None.

    How it works:
        1. Get candidates from every source with sources.fetch_candidates().
        2. Drop duplicates; filter by max_price and by size, when provided.
           Drop kids' items unless the description asks for kids.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, alternating stores within equal
           scores, and return at most config.SEARCH_RESULT_LIMIT listings.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    return search_with_status(description, size, max_price)[0]


def search_with_status(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
    wardrobe: dict | None = None,
    limit: int | None = None,
    keep_unsized: bool = False,
    *,
    sizes: list[str] | None = None,
    min_price: float | None = None,
    filters: dict | None = None,
    prefs: dict | None = None,
    patient: bool = True,
    info: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    search_listings() plus the per-store statuses (active, cached, paused…)
    the results page shows.

    keep_unsized: also keep listings whose store sent no size (eBay never
        does), after the ones that match. The web API uses this when the size
        came from the profile rather than the query.
    sizes:   several acceptable sizes (profile multi-select); `size` is one.
    min_price: low end of the price range.
    filters: the results-page filters (B4): conditions, colors, stores,
        within_days, gender. Each one only keeps listings whose data states
        the value; see attributes.py.
    prefs:   {gender, styles, colors, fit} from the profile. Gender is a hard
        filter (a women's shopper never sees men's items); the rest only
        nudge the order.
    patient: wait out embedding rate limits (scripts) or fall back to keyword
        ranking at once (web requests).
    info:    optional dict filled with {"ranking": "semantic"|"keyword",
        "dropped": {...}} for the trace.

    Order: dedupe → price/size/kids/gender/filters → at least one query word
    → drop clear category/colour/fabric mismatches → semantic rerank.
    """
    import attributes
    import ranking

    filters = filters or {}
    prefs = dict(prefs or {})
    wanted_sizes = [s for s in (sizes or ([size] if size else [])) if s]
    words = [w for w in _tokens(description) if len(w) > 2]
    candidates, statuses = fetch_candidates(description, max_price=max_price, min_price=min_price)
    allow_kids = wants_kids(description)
    gender = filters.get("gender") if "gender" in filters else prefs.get("gender")
    query_gender = attributes.query_gender(description)
    if query_gender:                       # "men's jacket" from a women's profile: the query wins
        gender = query_gender
    conditions = set(filters.get("conditions") or [])
    colors = set(filters.get("colors") or [])
    stores = set(filters.get("stores") or [])
    within = filters.get("within_days")

    seen, pool = set(), []
    for item in candidates:
        key = (item["platform"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        if max_price is not None and item["price"] > max_price:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if wanted_sizes and not any(size_matches(s, item["size"]) for s in wanted_sizes) \
                and not (keep_unsized and item["size"] is None):
            continue
        if not allow_kids and is_kids_item(item):
            continue
        if not attributes.gender_ok(item, gender):
            continue
        if conditions and attributes.condition_bucket(item.get("condition")) not in conditions:
            continue
        if colors and not (attributes.colors_in(item["title"]) & colors):
            continue
        if stores and item["platform"] not in stores:
            continue
        if within and not _listed_within(item, within):
            continue
        text = " ".join(filter(None, [item["title"], item.get("condition"), item.get("category")])).lower()
        if any(w in text for w in words):
            pool.append(item)

    if wardrobe and wardrobe.get("items"):
        prefs["closet_words"] = {w for owned in wardrobe["items"]
                                 for v in (owned.get("colors") or []) + (owned.get("style_tags") or [])
                                 for w in _tokens(v) if len(w) > 2}
    ranked, rank_info = ranking.rerank(description, pool, prefs=prefs, patient=patient)
    if info is not None:
        info.update(ranking=rank_info["method"], dropped=rank_info["dropped"])
    if wanted_sizes and keep_unsized:   # known size matches first; stable, so the order holds
        ranked.sort(key=lambda it: it["size"] is None)
    return ranked[:limit or config.SEARCH_RESULT_LIMIT], statuses


def _listed_within(item: dict, days: int) -> bool:
    """True if the store says it was listed in the last `days` days (False when it doesn't say)."""
    import datetime as dt
    raw = item.get("listed_at")
    if not raw:
        return False
    try:
        listed = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if listed.tzinfo is None:
        listed = listed.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc) - listed <= dt.timedelta(days=days)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> dict:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items,
                  each with an 'id'. **It may be empty.** Handle that.

    Returns:
        {"text": str, "item_ids": list[str]}
        text      — non-empty outfit suggestions, 3-5 short sentences.
        item_ids  — ids of the wardrobe items the text uses, in the order the
                    model gave them; only ids that really are in the wardrobe.
                    The results page shows those items' photos.
        With an empty wardrobe: general styling advice and item_ids == [].
        (Structured since DECISIONS.md #20; it used to be a plain string.)
    """
    items = wardrobe.get("items", [])
    details = [f"{label}: {new_item[key]}" for key, label in
               (("size", "size"), ("condition", "condition"), ("platform", "from"))
               if new_item.get(key)]
    item_text = f"{new_item['title']} (${new_item['price']:.0f}"
    item_text += f", {', '.join(details)})" if details else ")"
    if not items:
        prompt = (f"A user is thinking about buying this thrifted item: {item_text}. "
                  "They haven't shared their wardrobe. Give 1-2 general outfit "
                  "ideas for it in 3-5 short sentences.")
        return {"text": generate(prompt), "item_ids": []}

    owned = "\n".join(
        f"- id {w['id']}: {w['name']} ({w['category']}"
        + (f", {', '.join(w['colors'])}" if w.get("colors") else "") + ")"
        for w in items)
    prompt = (f"A user is thinking about buying this thrifted item: {item_text}.\n"
              f"Their wardrobe:\n{owned}\n"
              "Suggest 1-2 outfits pairing the new item with 2-4 pieces they own, "
              "naming those pieces. Keep it to 3-5 short sentences.\n"
              'Answer with JSON only: {"text": "<the suggestion>", '
              '"item_ids": ["<id of each wardrobe piece the text names>"]}')
    return _parse_outfit(generate(prompt, json_mode=True), items)


def _parse_outfit(raw: str, items: list[dict]) -> dict:
    """Model JSON → {"text", "item_ids"}; falls back to the raw text and name matching."""
    known = {str(w["id"]): w for w in items}
    text, ids = raw.strip(), []
    cleaned = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        data = loads_json(cleaned)
        if isinstance(data, dict) and str(data.get("text") or "").strip():
            text = str(data["text"]).strip()
            ids = [str(i) for i in data.get("item_ids") or []]
    except (json.JSONDecodeError, TypeError):
        pass
    ids = [i for i in dict.fromkeys(ids) if i in known]
    if not ids:   # the model skipped the ids: find the pieces the text names
        lowered = text.lower()
        ids = [i for i, w in known.items() if str(w.get("name", "")).lower() in lowered]
    return {"text": text, "item_ids": ids}


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

# The user is the buyer. A caption that sounds like the seller ("I just listed
# these…") is wrong; run_eval.py flags any card that matches this.
SELLER_VOICE = re.compile(
    r"\b(i\s+(just\s+)?listed|just\s+listed|(i['’]?m|i am|now)\s+selling|"
    r"selling\s+(these|this|it|them)|for sale|my\s+(shop|store|listing|closet sale)|"
    r"shop my|available (now )?(in|at) my|dm (me )?to (buy|purchase)|up for grabs)\b", re.I)


def seller_voice(text: str) -> list[str]:
    """Seller-sounding phrases found in a caption ([] means it reads as the buyer)."""
    return [m.group(0) for m in SELLER_VOICE.finditer(text or "")]


def create_fit_card(outfit, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   what suggest_outfit() returned (its dict, or just the text).
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe. It is written by the BUYER who found the piece ("found", "scored",
    "just bought"), never the seller ("listed", "selling", "my shop").

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from tools import search_listings; print(create_fit_card('jeans and white sneakers', search_listings('tee')[0]))"
    """
    if isinstance(outfit, dict):
        outfit = outfit.get("text") or ""
    if not outfit or not outfit.strip():
        return (f"No outfit to caption yet for {new_item.get('title', 'this item')}. "
                "Run suggest_outfit first, then try again.")
    prompt = (f"Write a 2-4 sentence social media caption about this thrift find.\n"
              f"Item: {new_item['title']}\nPrice: ${new_item['price']:.0f}\n"
              f"Platform: {new_item['platform']}\nOutfit idea: {outfit}\n"
              "You are the shopper who just found and bought this secondhand piece "
              "and are showing off the outfit. Write as the buyer: use words like "
              "'found', 'scored', 'snagged' or 'just bought'. You are NOT the seller: "
              "never say you listed it, are selling it, or mention your shop or store. "
              "Sound like a real person posting, not a product description. "
              "Use the item's exact title, word for word, once. "
              "Mention the price and platform once each, and be specific about the vibe.")
    return generate(prompt)


# ── The buyer's verdict (B1) ──────────────────────────────────────────────────
# The fit card is now a short buyer's verdict around the caption: an AI
# estimate of original retail and era (labelled as an estimate, with
# confidence; "unknown" when not confident), value, a condition check and a
# Worth it / Fair deal / Skip verdict. One model call writes all of it; the
# arithmetic (% off) and the condition grade are done in code, from the data.

VERDICTS = ("Worth it", "Fair deal", "Skip")
CONFIDENCE = ("high", "medium", "low")


def create_fit_card_full(outfit, new_item: dict) -> dict:
    """
    Returns {"caption": str, "verdict": dict | None}. `caption` is exactly what
    create_fit_card() returns (buyer voice, item + price + platform once
    each). `verdict` is None when the model's answer couldn't be read; the
    caption still stands.
    """
    if isinstance(outfit, dict):
        outfit = outfit.get("text") or ""
    if not outfit or not outfit.strip():
        return {"caption": create_fit_card(outfit, new_item), "verdict": None}
    import attributes

    condition = new_item.get("condition") or "not stated"
    prompt = (
        "You help a US shopper decide whether to buy a secondhand clothing listing.\n"
        f"Listing title: {new_item['title']}\n"
        f"Price: ${new_item['price']:.2f} on {new_item['platform']}\n"
        f"Brand (from the store): {new_item.get('brand') or 'not stated'}\n"
        f"Condition (from the store): {condition}\n"
        f"Size: {new_item.get('size') or 'not stated'}\n"
        f"Outfit idea: {outfit}\n\n"
        "Answer with JSON only, in this shape:\n"
        '{"caption": "<2-4 sentence social caption>",\n'
        ' "retail_estimate": {"low": <USD number or null>, "high": <USD number or null>, '
        '"confidence": "high|medium|low"},\n'
        ' "era": {"label": "<e.g. late 1990s, 2010s, current season, or null>", '
        '"confidence": "high|medium|low"},\n'
        ' "brand_value": "<one short sentence: how well this brand/style holds its value>",\n'
        ' "longevity": "classic|trend-driven|mixed",\n'
        ' "condition_notes": "<one short sentence from the condition and title only>",\n'
        ' "verdict": "Worth it|Fair deal|Skip",\n'
        ' "reasons": ["<short reason>", "<short reason>", "<optional third>"]}\n\n'
        "Rules:\n"
        "- The caption is written by the shopper who found and bought it: use words like "
        "'found', 'scored', 'snagged' or 'just bought'. Never the seller: never say you listed "
        "it, are selling it, or mention your shop or store. Use the item's exact title, word for "
        "word, once; mention the price and the platform once each; be specific about the vibe.\n"
        "- retail_estimate is what this item cost new at full price. If you don't recognise the "
        "brand or can't tell, use null numbers and confidence low. Never guess wildly.\n"
        "- era: only name one when the title gives real evidence (a year, 'vintage 90s', a "
        "discontinued line); otherwise label null and confidence low.\n"
        "- condition_notes: say only what the condition field and title state; if the condition "
        "isn't stated, say so.\n"
        "- verdict: Worth it = clearly good value for its condition; Fair deal = roughly what it "
        "should cost; Skip = overpriced, poor condition, or a red flag. Give 2-3 reasons, each "
        "under 12 words.")
    raw = generate(prompt, json_mode=True)
    return parse_fit_card(raw, new_item, attributes.condition_bucket(new_item.get("condition")))


def _num(value) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def parse_fit_card(raw: str, item: dict, condition_grade: str | None) -> dict:
    """Model JSON → {"caption", "verdict"}; estimates below medium confidence become unknown."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        data = loads_json(cleaned)
    except (json.JSONDecodeError, TypeError):
        data = None
    if not isinstance(data, dict):
        text = (raw or "").strip()
        return {"caption": text or f"Found {item['title']} for ${item['price']:.0f} on {item['platform']}.",
                "verdict": None}

    caption = str(data.get("caption") or "").strip()
    est = data.get("retail_estimate") or {}
    confidence = str(est.get("confidence") or "low").lower()
    low, high = _num(est.get("low")), _num(est.get("high"))
    if low and high and low > high:
        low, high = high, low
    retail = None
    if confidence in ("high", "medium") and (low or high):
        low, high = low or high, high or low
        mid = (low + high) / 2
        pct = round((1 - item["price"] / mid) * 100)
        retail = {"low": round(low), "high": round(high), "confidence": confidence,
                  "pct_off": pct if pct > 0 else None, "above_retail": pct < 0}
    era = data.get("era") or {}
    era_conf = str(era.get("confidence") or "low").lower()
    era_out = ({"label": str(era["label"]).strip()[:40], "confidence": era_conf}
               if era.get("label") and era_conf in ("high", "medium") else None)
    verdict = str(data.get("verdict") or "").strip()
    verdict = next((v for v in VERDICTS if v.lower() == verdict.lower()), None)
    reasons = [str(r).strip()[:120] for r in (data.get("reasons") or []) if str(r).strip()][:3]
    longevity = str(data.get("longevity") or "").lower()
    import attributes
    return {
        "caption": caption or f"Found {item['title']} for ${item['price']:.0f} on {item['platform']}.",
        "verdict": {
            "retail": retail,                     # None → "unknown" in the UI
            "era": era_out,                       # None → "unknown"
            "brand_value": str(data.get("brand_value") or "").strip()[:200] or None,
            "longevity": longevity if longevity in ("classic", "trend-driven", "mixed") else None,
            "condition": {
                "grade": condition_grade,         # from the store's own field, not the model
                "label": attributes.CONDITION_LABELS.get(condition_grade) if condition_grade else None,
                "stated": item.get("condition"),
                "notes": str(data.get("condition_notes") or "").strip()[:200] or None,
            },
            "verdict": verdict,
            "reasons": reasons,
        },
    }
