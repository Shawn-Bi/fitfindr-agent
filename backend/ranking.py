"""
Semantic ranking (A4): order listings by how close their text is to what was
asked for, after dropping clear category / colour / fabric / gender
mismatches (attributes.py).

    ranked, info = rerank("white denim pants", listings, prefs=prefs, patient=False)
    info == {"method": "semantic" | "keyword", "dropped": {"colour": 3, ...}}

Similarity comes from Gemini embeddings (generate.embed, cached on disk). When
embeddings are unavailable (off, rate limited, no key) the order falls back to
keyword overlap, so search never fails because of ranking.

Preferences nudge the order, never filter: the profile's styles, colours and
fit words in a title, and colours/styles shared with the user's closet.
"""

import math
import re

import attributes
import generate

STYLE_KEYWORDS = {
    "vintage": ("vintage", "vtg", "retro", "90s", "80s", "70s"),
    "y2k": ("y2k", "2000s", "low rise", "baby tee"),
    "streetwear": ("streetwear", "oversized", "graphic", "cargo", "hoodie"),
    "minimalist": ("minimal", "minimalist", "basic", "clean", "essential"),
    "grunge": ("grunge", "distressed", "flannel", "band"),
    "cottagecore": ("cottagecore", "floral", "prairie", "puff sleeve", "eyelet"),
    "business casual / workwear": ("blazer", "trouser", "tailored", "button down", "pleated"),
    "classic / preppy": ("preppy", "oxford", "cable knit", "polo", "ralph lauren", "j.crew"),
    "dark / goth": ("goth", "gothic", "black lace", "corset"),
    "boho": ("boho", "bohemian", "crochet", "paisley", "peasant", "fringe"),
    "athleisure": ("athletic", "lululemon", "legging", "track", "running"),
    "quiet luxury / old money": ("cashmere", "wool", "silk", "tailored", "loro piana", "max mara", "camel"),
    "romantic / feminine": ("lace", "ruffle", "floral", "satin", "bow"),
    "western": ("western", "cowboy", "fringe", "suede", "pearl snap"),
    "coastal": ("linen", "striped", "coastal", "nautical", "breton"),
    "avant-garde": ("avant", "asymmetric", "deconstructed", "rick owens", "yohji", "comme des"),
}
FIT_WORDS = {"slim": ("slim", "skinny", "fitted"), "regular": ("regular", "classic fit", "straight"),
             "relaxed": ("relaxed", "loose", "wide leg", "baggy"), "oversized": ("oversized", "boxy", "baggy")}


def listing_text(item: dict) -> str:
    """The words a listing is judged by: first title line, store category, brand, condition."""
    title = re.sub(r"(^|\s)#[\w-]+", " ", str(item.get("title") or "").split("\n")[0])
    parts = [title, item.get("category"), item.get("brand"), item.get("condition")]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9']+", text.lower()) if len(w) > 2}


def preference_boost(item: dict, prefs: dict | None) -> float:
    """Small bonus (0–0.06) for the profile's styles, colours and fit showing up in the title."""
    if not prefs:
        return 0.0
    title = str(item.get("title") or "").lower()
    boost = 0.0
    for style in prefs.get("styles") or []:
        if any(k in title for k in STYLE_KEYWORDS.get(style.lower(), (style.lower(),))):
            boost += 0.02
    liked = {attributes.COLOR_WORDS.get(c.lower(), c.lower()) for c in prefs.get("colors") or []}
    if liked & attributes.colors_in(title):
        boost += 0.02
    if any(w in title for w in FIT_WORDS.get(prefs.get("fit") or "", ())):
        boost += 0.01
    closet_words = prefs.get("closet_words") or set()
    if closet_words & _words(title):
        boost += 0.01
    size_range = prefs.get("size_range")
    if size_range in ("petite", "plus") and re.search(rf"\b{size_range}\b", title):
        boost += 0.02
    return min(boost, 0.06)


def similarity(query: str, items: list[dict], patient: bool = False) -> list[float] | None:
    """Cosine similarity of each listing to the query, or None if embeddings are unavailable."""
    if not items:
        return []
    try:
        vectors = generate.embed([query] + [listing_text(i) for i in items], patient=patient)
    except Exception:  # noqa: BLE001 — ranking falls back, search goes on
        return None
    return [_cos(vectors[0], v) for v in vectors[1:]]


def rerank(query: str, items: list[dict], prefs: dict | None = None,
           patient: bool = False, wanted: dict | None = None) -> tuple[list[dict], dict]:
    """`wanted`: the attributes mismatches are judged against (default: the query's)."""
    wanted = wanted or attributes.query_attributes(query)
    dropped: dict[str, int] = {}
    kept = []
    for item in items:
        why = attributes.clear_mismatch(wanted, item)
        if why:
            dropped[why] = dropped.get(why, 0) + 1
        else:
            kept.append({**item})   # a copy: _score must not leak into the shared pool

    words = _words(query)
    keyword = [len(words & _words(listing_text(i))) / max(1, len(words)) for i in kept]
    sims = similarity(query, kept, patient=patient)
    method = "semantic" if sims is not None else "keyword"
    if sims is None:
        sims = [0.0] * len(kept)
    scored = [(0.75 * s + 0.25 * k + preference_boost(i, prefs), i) for s, k, i in zip(sims, keyword, kept)]
    for score, item in scored:
        item["_score"] = round(score, 4)

    # Greedy pick with a small penalty per earlier pick from the same store,
    # so one cheap store can't fill the whole page.
    remaining = sorted(scored, key=lambda t: -t[0])
    ordered, per_store = [], {}
    while remaining:
        best = max(range(len(remaining)),
                   key=lambda j: remaining[j][0] - 0.015 * per_store.get(remaining[j][1]["platform"], 0))
        _, item = remaining.pop(best)
        per_store[item["platform"]] = per_store.get(item["platform"], 0) + 1
        ordered.append(item)
    return ordered, {"method": method, "dropped": dropped}
