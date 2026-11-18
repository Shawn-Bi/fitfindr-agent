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
from generate import ModelUnavailable, QuotaGuard, generate, loads_json
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


# Things stores list next to clothes that aren't clothes: fabric by the yard,
# sewing patterns, printables (mostly Etsy).
_NOT_CLOTHING = re.compile(
    r"\b(yardage|by the yard|sewing pattern|pdf pattern|digital pattern|printable|svg|doll clothes|"
    r"fabric (?:for|by|remnant|bundle|panel)|(?:denim|cotton|linen|wool|stretch|knit) fabric\b"
    r"(?!\s+(?:\w+\s+)?(?:shirt|top|dress|pants|jeans|jacket|skirt|coat)))", re.I)


def is_not_clothing(item: dict) -> bool:
    return bool(_NOT_CLOTHING.search(item.get("title") or ""))


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


def size_rank(item: dict, sizes: list[str]) -> int:
    """For a soft (profile) size: 0 = states one of `sizes`, 1 = states no size, 2 = another size."""
    if item.get("size") is None:
        return 1
    return 0 if any(size_matches(s, item["size"]) for s in sizes) else 2


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
    # patient=False: like the web path, never wait out an embedding rate limit;
    # rank by keywords instead and answer now.
    return search_with_status(description, size, max_price, patient=False)[0]


def search_with_status(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
    wardrobe: dict | None = None,
    limit: int | None = None,
    keep_unsized: bool = False,
    *,
    sizes: list[str] | None = None,
    soft_sizes: list[str] | None = None,
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

    soft_sizes: profile sizes, a preference only: listings in those sizes
        rank first, then listings with no size, then other sizes. Nothing
        is excluded for size.

    Order: dedupe → price/size/kids/gender/filters → at least one query word
    → drop clear category/colour/fabric mismatches → semantic rerank.
    """
    candidates, statuses = fetch_candidates(description, max_price=max_price, min_price=min_price)
    ranked = filter_and_rank(
        candidates, description, size=size, max_price=max_price, wardrobe=wardrobe,
        keep_unsized=keep_unsized, sizes=sizes, soft_sizes=soft_sizes, min_price=min_price,
        filters=filters, prefs=prefs, patient=patient, info=info)
    return ranked[:limit or config.SEARCH_RESULT_LIMIT], statuses


def filter_and_rank(
    candidates: list[dict],
    description: str,
    *,
    size: str | None = None,
    max_price: float | None = None,
    wardrobe: dict | None = None,
    keep_unsized: bool = False,
    sizes: list[str] | None = None,
    soft_sizes: list[str] | None = None,
    min_price: float | None = None,
    filters: dict | None = None,
    prefs: dict | None = None,
    patient: bool = True,
    info: dict | None = None,
    words: list[str] | None = None,
    wanted: dict | None = None,
) -> list[dict]:
    """
    The filtering and ranking half of search_with_status, on listings already
    fetched. `words`: listings must contain one of these (default: the
    description's words). `wanted`: the attributes mismatches are judged
    against (default: the description's), so a broadened search still never
    shows another category or colour than the one asked for.
    """
    import attributes
    import ranking

    filters = filters or {}
    prefs = dict(prefs or {})
    wanted_sizes = [s for s in (sizes or ([size] if size else [])) if s]
    words = words if words is not None else [w for w in _tokens(description) if len(w) > 2]
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
        if is_not_clothing(item):
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
    ranked, rank_info = ranking.rerank(description, pool, prefs=prefs, patient=patient, wanted=wanted)
    if info is not None:
        info.update(ranking=rank_info["method"], dropped=rank_info["dropped"])
    if wanted_sizes and keep_unsized:   # known size matches first; stable, so the order holds
        ranked.sort(key=lambda it: it["size"] is None)
    if soft_sizes:
        ranked.sort(key=lambda it: size_rank(it, soft_sizes))
    return ranked


# ── Broadening (few results) ──────────────────────────────────────────────────
# When a search finds fewer than BROADEN_MIN results, it widens step by step,
# in this order, and stops as soon as it has enough:
#   1. drop extra adjectives (keep gender, colour, fabric and garment words):
#      "womens ecru ribbed turtleneck" → "womens ecru turtleneck"
#   2. a synonym of the garment word (pants → jeans, turtleneck → mock neck)
#   3. drop a size the user set (a profile size never excluded anything)
#   4. widen the price range +50%
# Steps 1–2 are new store searches, so the one that drops the most words goes
# first. Results are judged against the ORIGINAL request's category, colour,
# fabric and gender throughout, so broadening never shows a mismatch. New
# live store searches are capped (config.BROADEN_LIVE_FETCHES per search);
# after that the steps use the 24 h cache only.

BROADEN_MIN = 4

# Garment word → other words stores use for the same thing (same category).
SYNONYMS = {
    "pants": ["jeans", "trousers"], "jeans": ["pants", "denim pants"], "trousers": ["pants", "slacks"],
    "slacks": ["trousers"], "turtleneck": ["mock neck", "sweater"], "mock neck": ["turtleneck", "sweater"],
    "sweater": ["pullover", "knit sweater"], "jumper": ["sweater"], "pullover": ["sweater"],
    "cardigan": ["knit cardigan"], "tee": ["t-shirt", "shirt"], "t-shirt": ["tee"], "tshirt": ["tee"],
    "blouse": ["top", "shirt"], "top": ["blouse", "shirt"], "shirt": ["button down", "blouse"],
    "button down": ["shirt"], "hoodie": ["sweatshirt"], "sweatshirt": ["hoodie", "crewneck"],
    "tank": ["tank top", "cami"], "cami": ["camisole", "tank top"], "jacket": ["coat"], "coat": ["jacket"],
    "blazer": ["suit jacket"], "skirt": ["midi skirt"], "dress": ["midi dress"],
    "sneakers": ["trainers", "shoes"], "trainers": ["sneakers"], "boots": ["booties"], "booties": ["boots"],
    "loafers": ["flats"], "flats": ["loafers"], "heels": ["pumps"], "pumps": ["heels"],
    "bag": ["purse", "handbag"], "purse": ["bag"], "handbag": ["bag"], "shorts": ["denim shorts"],
}
_SYN_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, SYNONYMS), key=len, reverse=True)) + r")\b", re.I)


def synonym_queries(description: str) -> list[str]:
    """The description with its garment word swapped for each synonym, e.g. 'white denim jeans'."""
    m = None
    for m in _SYN_RE.finditer(description or ""):
        pass                                    # the last garment word is the noun
    if not m:
        return []
    word = m.group(1).lower()
    out = []
    for alt in SYNONYMS[word]:
        q = re.sub(r"\s+", " ", description[:m.start()] + alt + description[m.end():]).strip()
        if q.lower() != description.lower() and q.lower() not in [o.lower() for o in out]:
            out.append(q)
    return out


def core_query(description: str) -> tuple[str, list[str]]:
    """
    (query with only gender, colour, fabric and garment words, the words dropped).
    'womens ecru ribbed turtleneck' → ('womens ecru turtleneck', ['ribbed']).
    """
    import attributes

    keep, dropped = [], []
    for word in str(description or "").split():
        w = word.lower().strip(".,!?")
        if (attributes.colors_in(w) or attributes.materials_in(w) or attributes.query_gender(w)
                or attributes.listing_category({"title": w}) or _SYN_RE.fullmatch(w)
                or w in ("mock", "neck", "wide", "leg", "straight", "high", "waist", "midi", "maxi", "mini")):
            keep.append(word)
        else:
            dropped.append(word)
    if not keep or not dropped or not attributes.listing_category({"title": " ".join(keep)}):
        return description, []
    return " ".join(keep), dropped


def _raised(max_price: float) -> float:
    import math
    return float(math.ceil(max_price * 1.5 / 5.0) * 5)


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def search_broadened(description: str, *, max_price: float | None = None, min_price: float | None = None,
                     sizes: list[str] | None = None, keep_unsized: bool = False,
                     soft_sizes: list[str] | None = None, wardrobe: dict | None = None,
                     limit: int | None = None, filters: dict | None = None, prefs: dict | None = None,
                     patient: bool = False, info: dict | None = None,
                     min_results: int = BROADEN_MIN) -> tuple[list[dict], list[dict], dict | None]:
    """
    search_with_status, then the broadening steps above while there are fewer
    than `min_results`. Returns (results, statuses, broadened) where
    broadened is None (nothing changed) or {"steps": [...], "message": str,
    "max_price": new max or None, "dropped_size": bool}.
    """
    import attributes

    common = dict(wardrobe=wardrobe, filters=filters, prefs=prefs, patient=patient, info=info,
                  soft_sizes=soft_sizes)
    candidates, statuses = fetch_candidates(description, max_price=max_price, min_price=min_price)
    words = [w for w in _tokens(description) if len(w) > 2]
    hard_sizes = list(sizes or [])
    price = max_price

    def run():
        return filter_and_rank(candidates, description, sizes=hard_sizes, keep_unsized=keep_unsized,
                               max_price=price, min_price=min_price, words=words, wanted=wanted, **common)

    wanted = attributes.query_attributes(description)
    results = run()
    if len(results) >= min_results:
        return results[:limit or config.SEARCH_RESULT_LIMIT], statuses, None

    first = len(results)
    live_left = config.BROADEN_LIVE_FETCHES if config.DATA_MODE == "live" else 0
    steps, said = [], []

    def fetch_more(query, max_p):
        nonlocal live_left
        found, st = fetch_candidates(query, max_price=max_p, min_price=min_price, live=live_left > 0)
        if any(s["status"] == "active" for s in st):
            live_left -= 1
        candidates.extend(found)
        words.extend(w for w in _tokens(query) if len(w) > 2 and w not in words)

    # 1–2. query rewrites: without the extra adjectives, then a synonym of the
    # garment word. Each is one store search per host (cache first), so they
    # run only while results are short; live calls are capped above.
    core, dropped = core_query(description)
    rewrites = ([("adjectives", core)] if dropped else []) + \
        [("synonyms", q) for q in synonym_queries(core)[:1]]
    for step, q in rewrites:
        if len(results) >= min_results:
            break
        fetch_more(q, price)
        results = run()
        steps.append(step)
        said.append("dropped " + _join([f"“{d}”" for d in dropped]) if step == "adjectives"
                    else f"also searched “{q}”")
    # 3. drop a size the user set
    if len(results) < min_results and hard_sizes:
        hard_sizes = []
        results = run()
        steps.append("size")
        said.append("searched every size")
    # 4. widen the price range +50%
    if len(results) < min_results and price is not None:
        price = _raised(price)
        for q in [description] + [q for _, q in rewrites]:
            fetch_more(q, price)
        results = run()
        steps.append("price")
        said.append(f"raised the budget to ${price:.0f}")

    if not steps:
        return results[:limit or config.SEARCH_RESULT_LIMIT], statuses, None
    n = len(results)
    lead = (f"Only {first} exact match{'es' if first != 1 else ''}" if first else "No exact matches")
    message = f"{lead}, so I {_join(said)}." + (f" Now {n} result{'s' if n != 1 else ''}." if n != first else "")
    return results[:limit or config.SEARCH_RESULT_LIMIT], statuses, {
        "steps": steps, "message": message,
        "max_price": price if "price" in steps else None, "dropped_size": "size" in steps}


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
STORE_NAMES = {"ebay": "eBay", "etsy": "Etsy", "depop": "Depop", "poshmark": "Poshmark",
               "mercari": "Mercari", "fb_marketplace": "Facebook Marketplace"}


def code_caption(item: dict) -> str:
    """The caption written without the model: item, price and store once each, as the buyer."""
    title = item["title"].split("\n")[0].strip()
    store = STORE_NAMES.get(item["platform"], item["platform"])
    price = float(item["price"])
    shown = f"${price:.0f}" if price.is_integer() else f"${price:.2f}"
    return f"Found this {title} for {shown} on {store}."


def create_fit_card_full(outfit, new_item: dict) -> dict:
    """
    Returns {"caption": str, "verdict": dict | None, "written_by": "model" | "code"}.
    `caption` is exactly what create_fit_card() returns (buyer voice, item +
    price + platform once each). `verdict` is None when the model's answer
    couldn't be read; the caption still stands. When the model is unavailable
    (quota, outage) the caption is written in code from the listing and there
    is no verdict: the outfit the user already has must not be thrown away
    because the caption step failed.
    """
    if isinstance(outfit, dict):
        outfit = outfit.get("text") or ""
    if not outfit or not outfit.strip():
        return {"caption": create_fit_card(outfit, new_item), "verdict": None, "written_by": "code"}
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
    try:
        raw = generate(prompt, json_mode=True)
    except (ModelUnavailable, QuotaGuard, RuntimeError):
        return {"caption": code_caption(new_item), "verdict": None, "written_by": "code"}
    card = parse_fit_card(raw, new_item, attributes.condition_bucket(new_item.get("condition")))
    return {**card, "written_by": "model"}


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
