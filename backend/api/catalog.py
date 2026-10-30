"""
Pure helpers behind the web routes: no network, no model, easy to test.

    resolve_filters()   query + profile + removed chips → the filters to search with, and the chips
    relax_options()     the one-click "remove size" / "raise budget" buttons for an empty search
    listing_category()  "Vintage Levi's 505 jeans" → "bottoms"
    home_picks()        "Picked for your closet" from listings already on hand
    item_matches()      "Finds that go with this" for one closet item
"""

import math

from agent import parse_query
from attributes import listing_category  # noqa: F401 — re-exported for callers and tests
from tools import closet_affinity, is_kids_item

STORE_LABELS = {
    "ebay": "eBay", "etsy": "Etsy", "depop": "Depop", "poshmark": "Poshmark",
    "mercari": "Mercari", "fb_marketplace": "FB Marketplace",
}
STORE_ORDER = ("ebay", "etsy", "depop", "poshmark", "mercari", "fb_marketplace")

CATEGORIES = ("tops", "bottoms", "outerwear", "dresses", "shoes", "accessories")

# What to look for when styling a closet item of each category.
COMPLEMENTS = {
    "tops": ("bottoms", "outerwear", "shoes"),
    "bottoms": ("tops", "outerwear", "shoes"),
    "outerwear": ("tops", "bottoms"),
    "dresses": ("outerwear", "shoes", "accessories"),
    "shoes": ("bottoms", "tops"),
    "accessories": ("tops", "outerwear", "dresses"),
}

_STYLE_WORDS = ("vintage", "y2k", "streetwear", "minimalist", "grunge", "cottagecore")


# ── Profile v2 (B3) ──────────────────────────────────────────────────────────

# Sizes follow US retail (Nordstrom / Madewell / J.Crew), per "Shopping for":
#   women: size_range (regular | petite | plus), tops (tops & dresses: letters
#          and numeric 00–20, or 1X–4X / 14W–28W for plus), bottoms_waist
#          (jeans, 23–34), bottoms_inseam (Short | Regular | Long), shoes (5–12)
#   men:   men_tops (S–XXL), men_neck (14–18) + men_sleeve (32–36) for dress
#          shirts, men_waist (28–44), men_inseam (28–36), men_shoes (7–15)
SIZE_KEYS = ("size_range", "tops", "bottoms_waist", "bottoms_inseam", "shoes",
             "men_tops", "men_neck", "men_sleeve", "men_waist", "men_inseam", "men_shoes")
WOMEN_INSEAMS = {"Short": ("28", "29"), "Regular": ("30", "31", "32"), "Long": ("33", "34", "35", "36")}
GENDERS = ("women", "men", "both")
FITS = ("slim", "regular", "relaxed", "oversized")
STYLES = ("Vintage", "Y2K", "Streetwear", "Minimalist", "Grunge", "Cottagecore",
          "Business casual / workwear", "Classic / preppy", "Dark / goth", "Boho", "Athleisure",
          "Quiet luxury / old money", "Romantic / feminine", "Western", "Coastal", "Avant-garde")


def _inseam_band(value: str) -> str | None:
    """A numeric women's inseam from an older profile → Short / Regular / Long."""
    if value in WOMEN_INSEAMS:
        return value
    try:
        n = float(value)
    except ValueError:
        return None
    return "Short" if n < 30 else "Regular" if n < 33 else "Long"


def _merge(*lists) -> list[str]:
    out = []
    for values in lists:
        for v in values or []:
            v = str(v).strip()
            if v and v not in out:
                out.append(v)
    return out


def normalize_sizes(sizes: dict | None, gender: str | None = None) -> dict:
    """
    The current size lists (SIZE_KEYS). Older profiles are read in place:
    v2 lists `dresses` and letter `bottoms` join `tops` (tops & dresses now
    share one group); numeric inseams become Short / Regular / Long; the MVP's
    single values (top, waist, length, shoe) fill empty lists. For a men's
    profile, older unprefixed values become the men's lists.
    """
    sizes = sizes or {}
    get = lambda k: [str(v).strip() for v in sizes.get(k) or [] if str(v).strip()] \
        if isinstance(sizes.get(k), list) else []
    out = {k: get(k) for k in SIZE_KEYS}
    legacy = {"top": "tops", "waist": "bottoms_waist", "length": "bottoms_inseam", "shoe": "shoes"}
    for old, new in legacy.items():
        value = str(sizes.get(old) or "").replace("US", "").strip()
        if value and not out[new]:
            out[new] = [value]
    out["tops"] = _merge(out["tops"], get("dresses"), get("bottoms"))
    if gender == "men" and not any(out[k] for k in SIZE_KEYS if k.startswith("men_")):
        out.update(men_tops=out["tops"], men_waist=out["bottoms_waist"],
                   men_inseam=[v for v in out["bottoms_inseam"] if v.replace(".", "").isdigit()],
                   men_shoes=out["shoes"])
        out.update(tops=[], bottoms_waist=[], bottoms_inseam=[], shoes=[])
    out["bottoms_inseam"] = _merge(b for b in map(_inseam_band, out["bottoms_inseam"]) if b)
    out["size_range"] = [r for r in out["size_range"] if r in ("regular", "petite", "plus")][:1]
    return out


def _petite(values: list[str]) -> list[str]:
    """Petite listings say 'SP', 'PS', 'S Petite' or '4P'; match those forms too."""
    return _merge(values, [f"{v}P" for v in values], [f"P{v}" for v in values if v.isalpha()])


def sizes_for(description: str, sizes: dict, gender: str | None = None) -> list[str]:
    """
    The profile sizes that fit what's being searched, as size strings to
    match: tops & dresses sizes for tops, dresses and outerwear; waist (and
    women's numeric sizes) for bottoms; shoe sizes for shoes; none for
    accessories. Men's lists for a men's profile, both for "both".
    """
    sizes = normalize_sizes(sizes, gender)
    category = listing_category({"title": description})
    women, men = gender != "men", gender in ("men", "both")
    out: list[str] = []
    if category == "accessories":
        return []
    if category == "bottoms":
        if women:
            out += sizes["bottoms_waist"] + [s for s in sizes["tops"] if s[:1].isdigit()]
        if men:
            out += sizes["men_waist"]
    elif category == "shoes":
        out += (sizes["shoes"] if women else []) + (sizes["men_shoes"] if men else [])
    elif category == "dresses":
        out += sizes["tops"] if women else []
    else:
        out += (sizes["tops"] if women else []) + (sizes["men_tops"] + sizes["men_neck"] if men else [])
    if women and sizes["size_range"] == ["petite"] and category != "shoes":
        out = _petite(out)
    return _merge(out)


def sizes_summary(sizes: dict | None, gender: str | None = None) -> str:
    """One line for the stylist prompt, e.g. 'Petite; tops S, 4; waist 28; inseam Short; shoes 8'."""
    s = normalize_sizes(sizes, gender)
    parts = [s["size_range"][0].title()] if s["size_range"] else []
    for key, label in (("tops", "tops & dresses"), ("bottoms_waist", "waist"), ("bottoms_inseam", "inseam"),
                       ("shoes", "shoes"), ("men_tops", "men's tops"), ("men_neck", "neck"),
                       ("men_sleeve", "sleeve"), ("men_waist", "men's waist"), ("men_inseam", "men's inseam"),
                       ("men_shoes", "men's shoes")):
        if s[key]:
            parts.append(f"{label} {', '.join(s[key])}")
    return "; ".join(parts)


def profile_prefs(profile: dict | None) -> dict:
    """What ranking and styling read from the profile."""
    profile = profile or {}
    gender = profile.get("gender")
    sizes = normalize_sizes(profile.get("sizes"), gender)
    return {"gender": gender if gender in ("women", "men") else None,
            "styles": profile.get("styles") or [], "colors": profile.get("colors") or [],
            "fit": profile.get("fit"), "measurements": profile.get("measurements") or {},
            "size_range": (sizes["size_range"] or [None])[0],
            "sizes_text": sizes_summary(profile.get("sizes"), gender)}


def _money(value: float) -> str:
    return f"${value:.0f}" if float(value).is_integer() else f"${value:.2f}"


def price_label(low: float | None, high: float | None) -> str:
    if low is not None and high is not None:
        return f"{_money(low)}–{_money(high)}"
    if high is not None:
        return f"under {_money(high)}"
    return f"over {_money(low)}"


def resolve_filters(q: str, profile: dict | None, *, no_size: bool = False,
                    no_price: bool = False, max_price: float | None = None,
                    min_price: float | None = None, sizes: list[str] | None = None,
                    use_profile: bool = True) -> tuple[dict, list[dict]]:
    """
    Returns (parsed, chips).
    parsed: {"description", "size", "sizes", "max_price", "min_price",
             "size_from_profile", "size_lenient"} for the agent and the search.
    chips:  [{"key": "q"|"size"|"price", "label", "from_profile"}] for the UI.
    The profile's sizes and budget range fill in what the query didn't say
    (DECISIONS.md #15); explicit filters (B4) beat both.
    """
    parsed = parse_query(q)
    profile = profile or {}
    size_from_profile = price_from_profile = False

    if no_size:
        parsed["sizes"] = []
    elif sizes is not None:
        parsed["sizes"] = [s for s in sizes if s]
    elif parsed["size"]:
        parsed["sizes"] = [parsed["size"]]
    elif use_profile:
        parsed["sizes"] = sizes_for(parsed["description"], profile.get("sizes") or {}, profile.get("gender"))
        size_from_profile = bool(parsed["sizes"])
    else:
        parsed["sizes"] = []
    parsed["size"] = ", ".join(parsed["sizes"]) or None

    parsed["min_price"] = None
    if no_price:
        parsed["max_price"] = None
    elif max_price is not None or min_price is not None:
        parsed["max_price"] = float(max_price) if max_price is not None else parsed["max_price"]
        parsed["min_price"] = float(min_price) if min_price is not None else None
    elif parsed["max_price"] is None and use_profile and (profile.get("budget") or profile.get("budget_min")):
        parsed["max_price"] = float(profile["budget"]) if profile.get("budget") else None
        parsed["min_price"] = float(profile["budget_min"]) if profile.get("budget_min") else None
        price_from_profile = True
    parsed["size_from_profile"] = size_from_profile
    # Profile sizes are a soft preference: they only order the results
    # (matches, then no size stated, then other sizes). The Size filter keeps
    # matches and listings whose store states no size (eBay, Etsy); a size
    # typed in the query ("size M") is strict.
    parsed["size_soft"] = size_from_profile
    parsed["size_lenient"] = size_from_profile or (sizes is not None and bool(parsed["sizes"]))

    chips = []
    if parsed["description"]:
        chips.append({"key": "q", "label": parsed["description"], "from_profile": False})
    if parsed["max_price"] is not None or parsed["min_price"] is not None:
        chips.append({"key": "price", "label": price_label(parsed["min_price"], parsed["max_price"]),
                      "from_profile": price_from_profile})
    if parsed["size"]:
        chips.append({"key": "size", "label": f"size {parsed['size']}",
                      "from_profile": size_from_profile})
    return parsed, chips


# What the results-page filters can rely on in the store data (B4). A filter
# whose field no live store sends stays visible but disabled — never faked.
FILTER_SUPPORT = {
    "price": {"available": True},
    "size": {"available": True, "note": "eBay and Etsy listings don't state a size; they stay in, after the matches."},
    "condition": {"available": True, "note": "Matched on the condition each store states."},
    "colour": {"available": True, "note": "Matched on colours named in the listing title."},
    "gender": {"available": True, "note": "Matched on Men's / Women's in the title."},
    "listed_within": {"available": True, "note": "Only Poshmark shares listing dates; other stores' "
                                                 "items are hidden while this is on."},
    "location": {"available": False, "note": "Location is for Facebook Marketplace, which isn't connected yet."},
    "store": {"available": True},
}


def raised_budget(max_price: float) -> int:
    """+50%, rounded up to the next $5 (DECISIONS.md #17)."""
    return int(math.ceil(max_price * 1.5 / 5.0) * 5)


def relax_options(parsed: dict) -> list[dict]:
    options = []
    if parsed.get("size"):
        options.append({"label": f"Remove size {parsed['size']}", "params": {"no_size": True}})
    if parsed.get("max_price") is not None:
        higher = raised_budget(parsed["max_price"])
        options.append({"label": f"Raise budget to ${higher}", "params": {"max_price": higher}})
    return options


def empty_title(data_mode: str) -> str:
    """Fixtures hold a handful of recorded searches, so an empty page there says so."""
    return "Development data doesn't include this search" if data_mode == "fixtures" else "No matches yet"


def empty_message(parsed: dict, store_count: int) -> str:
    parts = [f"“{parsed['description']}”"]
    if parsed.get("size"):
        parts.append(f"in size {parsed['size']}")
    if parsed.get("max_price") is not None or parsed.get("min_price") is not None:
        parts.append(price_label(parsed.get("min_price"), parsed.get("max_price")))
    stores = f"{store_count} store{'s' if store_count != 1 else ''}"
    return f"We searched {stores} for {' '.join(parts)} and found nothing that matches."


def store_panel(statuses: list[dict], results: list[dict]) -> list[dict]:
    """One row per store, in a fixed order, with how many results it gave."""
    counts: dict[str, int] = {}
    for item in results:
        counts[item["platform"]] = counts.get(item["platform"], 0) + 1
    by_platform = {s["platform"]: s for s in statuses}
    panel = []
    for platform in STORE_ORDER:
        s = by_platform.get(platform, {"status": "coming_soon"})
        status = "live" if s["status"] in ("fixtures", "active", "cached") else (
            "error" if s["status"] == "skipped" else s["status"])
        row = {"platform": platform, "label": STORE_LABELS[platform], "status": status,
               "count": counts.get(platform, 0)}
        if s.get("resumes"):
            row["resumes"] = s["resumes"]
        panel.append(row)
    return panel


# ── Home picks and closet-item matches (no live calls, no model) ─────────────

def _usable(pool: list[dict], max_price: float | None = None) -> list[dict]:
    seen, out = set(), []
    for item in pool:
        key = (item["platform"], item["id"])
        if key in seen or is_kids_item(item) or not item.get("image_url"):
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        seen.add(key)
        out.append(item)
    return out


def _shared_colors(item: dict, owned: dict) -> list[str]:
    title = (item.get("title") or "").lower()
    return [c for c in owned.get("colors") or [] if c and c.lower() in title]


def _pair_reason(item: dict, owned: dict) -> str:
    colors = _shared_colors(item, owned)
    if colors:
        return f"Picks up the {colors[0]} in your {owned['name'].lower()}"
    return f"Goes with your {owned['name'].lower()}"


def fresh_by_store(pool: list[dict], per_store: int = 2) -> list[dict]:
    """For new users: a couple of listings from each live store, alternating stores."""
    buckets: dict[str, list[dict]] = {}
    for item in _usable(pool):
        if len(buckets.setdefault(item["platform"], [])) < per_store:
            buckets[item["platform"]].append(item)
    picks = []
    for i in range(per_store):
        for platform in STORE_ORDER:
            if len(buckets.get(platform, [])) > i:
                picks.append({"listing": buckets[platform][i], "reason": None})
    return picks


def home_picks(pool: list[dict], closet: list[dict], profile: dict | None,
               limit: int = 8) -> list[dict]:
    """
    Listings that fill a gap in the closet or echo its colors and the
    profile's styles, each with the closet item it goes with.
    """
    profile = profile or {}
    budget = float(profile["budget"]) if profile.get("budget") else None
    wardrobe = {"items": closet}
    have = {c["category"] for c in closet}
    styles = [s.lower() for s in profile.get("styles") or []]

    scored = []
    for item in _usable(pool, budget):
        category = listing_category(item)
        if not category:
            continue
        partners = [c for c in closet if category in COMPLEMENTS.get(c["category"], ())]
        if not partners:
            continue
        title = (item.get("title") or "").lower()
        score = (2 if category not in have else 0) + closet_affinity(item, wardrobe) \
            + sum(1 for s in styles if s in title)
        partner = max(partners, key=lambda c: len(_shared_colors(item, c)))
        scored.append((score, item, partner))
    scored.sort(key=lambda t: -t[0])

    picks, per_store = [], {}
    for score, item, partner in scored:
        if per_store.get(item["platform"], 0) >= 3:   # keep stores mixed
            continue
        per_store[item["platform"]] = per_store.get(item["platform"], 0) + 1
        picks.append({"listing": item, "reason": _pair_reason(item, partner)})
        if len(picks) >= limit:
            break
    return picks


def item_matches(pool: list[dict], owned: dict, budget: float | None = None,
                 limit: int = 6) -> list[dict]:
    wanted = COMPLEMENTS.get(owned.get("category"), ())
    tags = [t.lower() for t in (owned.get("style_tags") or []) if t]
    scored = []
    for item in _usable(pool, budget):
        category = listing_category(item)
        if category not in wanted:
            continue
        title = (item.get("title") or "").lower()
        score = 2 * len(_shared_colors(item, owned)) + sum(1 for t in tags if t in title) \
            + (1 if any(s in title for s in _STYLE_WORDS) else 0)
        scored.append((score, wanted.index(category), item))
    scored.sort(key=lambda t: (-t[0], t[1]))

    picks, per_category = [], {}
    for score, rank, item in scored:
        category = listing_category(item)
        if per_category.get(category, 0) >= 3:
            continue
        per_category[category] = per_category.get(category, 0) + 1
        picks.append({"listing": item, "reason": _pair_reason(item, owned)})
        if len(picks) >= limit:
            break
    return picks
