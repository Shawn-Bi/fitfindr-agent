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
from generate import generate
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


def _mix_stores(ranked: list[tuple[int, dict]], wardrobe: dict | None = None) -> list[dict]:
    """
    Keep keyword-match order, but within each tier of equal score alternate
    stores (round-robin), so one cheap store can't fill the whole page.
    Within one store, listings that share colors or styles with the user's
    closet come first. The top item overall stays first.
    """
    mixed = []
    for score in sorted({s for s, _ in ranked}, reverse=True):
        buckets: dict[str, list[dict]] = {}
        for s, item in ranked:
            if s == score:
                buckets.setdefault(item["platform"], []).append(item)
        if wardrobe and wardrobe.get("items"):
            for platform in buckets:
                buckets[platform].sort(key=lambda it: -closet_affinity(it, wardrobe))
        while buckets:
            for platform in list(buckets):
                mixed.append(buckets[platform].pop(0))
                if not buckets[platform]:
                    del buckets[platform]
    return mixed


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
) -> tuple[list[dict], list[dict]]:
    """
    search_listings() plus the per-store statuses (active, cached, paused…)
    the results page shows. `wardrobe` only changes the order within a store.
    """
    words = [w for w in _tokens(description) if len(w) > 2]
    candidates, statuses = fetch_candidates(description, max_price=max_price)
    allow_kids = wants_kids(description)

    seen, results = set(), []
    for item in candidates:
        key = (item["platform"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        if max_price is not None and item["price"] > max_price:
            continue
        if size and not size_matches(size, item["size"]):
            continue
        if not allow_kids and is_kids_item(item):
            continue
        text = " ".join(filter(None, [item["title"], item.get("condition")])).lower()
        score = sum(1 for w in words if w in text)
        if score > 0:
            results.append((score, item))
    return _mix_stores(results, wardrobe)[:limit or config.SEARCH_RESULT_LIMIT], statuses


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
        data = json.loads(cleaned)
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
