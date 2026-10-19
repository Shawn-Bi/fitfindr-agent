"""
What a listing (or a query) says about itself, read from words only: category,
colours, fabric, gender and condition. No network, no model.

    query_attributes("white denim pants")
        → {"category": "bottoms", "colors": {"white"}, "materials": {"denim"}, "gender": None}
    clear_mismatch(query_attrs, listing)   → "colour" | "category" | "fabric" | "gender" | None

A "clear mismatch" needs evidence on both sides: a listing that names no
colour is never dropped for colour. Search ranking (ranking.py), the stylist
(stylist.py) and the filters (B4) all use these rules, so they agree.
"""

import re

CATEGORIES = ("tops", "bottoms", "outerwear", "dresses", "shoes", "accessories")

# Listing title keywords → closet category. Checked in this order, so
# "denim jacket" is outerwear, not bottoms, and "shirt dress" is a dress.
_CATEGORY_WORDS = (
    ("dresses", r"dress|gown|romper|jumpsuit|sundress|slip dress"),
    ("outerwear", r"jacket|coat|parka|blazer|windbreaker|anorak|puffer|vest|gilet|cardigan|fleece|"
                  r"overshirt|shacket|trench|peacoat|bomber"),
    ("shoes", r"shoes?|sneakers?|boots?|booties|heels|pumps|loafers?|sandals?|trainers?|clogs?|mules?|"
              r"flats|oxfords?|slingbacks?"),
    ("bottoms", r"pants|jeans|trousers|shorts|skirts?|slacks|joggers|sweatpants|chinos|leggings|cargos?|corduroys?|"
                r"culottes"),
    ("accessories", r"bags?|handbags?|purses?|clutch|totes?|crossbody|belts?|hats?|caps?|scarf|scarves|"
                    r"beanie|necklace|earrings|sunglasses|wallet"),
    ("tops", r"tees?|t-shirts?|tshirts?|shirts?|tops?|blouses?|tanks?|sweaters?|hoodies?|sweatshirts?|"
             r"crewnecks?|polos?|flannels?|jerseys?|camis?|henleys?|turtlenecks?|pullovers?|bodysuits?|"
             r"knit top|jumper"),
)
_CATEGORY_RES = [(c, re.compile(rf"\b({words})\b", re.I)) for c, words in _CATEGORY_WORDS]

# Colour words → a canonical colour. Families group colours that don't clash
# as a "mismatch" (asking for white and getting ivory is fine; olive is not).
COLOR_WORDS = {
    "white": "white", "off-white": "cream", "off white": "cream", "ivory": "cream", "cream": "cream",
    "ecru": "cream", "oatmeal": "beige", "beige": "beige", "sand": "beige", "taupe": "beige",
    "nude": "beige", "camel": "camel", "tan": "camel", "khaki": "khaki", "black": "black",
    "jet black": "black", "grey": "grey", "gray": "grey", "charcoal": "grey", "heather": "grey",
    "silver": "grey", "navy": "navy", "blue": "blue", "denim blue": "blue", "light blue": "light blue",
    "baby blue": "light blue", "sky blue": "light blue", "indigo": "blue", "cobalt": "blue",
    "royal blue": "blue", "teal": "teal", "turquoise": "teal", "brown": "brown", "chocolate": "brown",
    "espresso": "brown", "cognac": "brown", "mocha": "brown", "burgundy": "burgundy", "maroon": "burgundy",
    "wine": "burgundy", "oxblood": "burgundy", "red": "red", "crimson": "red", "pink": "pink",
    "blush": "pink", "rose": "pink", "fuchsia": "pink", "hot pink": "pink", "lilac": "lilac",
    "lavender": "lilac", "purple": "purple", "plum": "purple", "violet": "purple", "green": "green",
    "emerald": "green", "sage": "sage", "mint": "sage", "olive": "olive", "army green": "olive",
    "forest green": "green", "yellow": "yellow", "mustard": "yellow", "gold": "yellow",
    "orange": "orange", "rust": "rust", "terracotta": "rust", "coral": "orange",
}
COLOR_FAMILY = {
    "white": "light", "cream": "light", "beige": "light",
    "camel": "earth", "khaki": "earth", "brown": "earth", "rust": "earth",
    "black": "black", "grey": "grey", "navy": "navy",
    "blue": "blue", "light blue": "blue", "teal": "blue",
    "burgundy": "red", "red": "red", "pink": "pink", "lilac": "purple", "purple": "purple",
    "green": "green", "sage": "green", "olive": "olive", "yellow": "yellow", "orange": "orange",
}
_COLOR_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, COLOR_WORDS), key=len, reverse=True)) + r")\b", re.I)
# Words that look like colours but describe something else in clothing titles.
_NOT_COLOR = re.compile(r"\b(rose\s+gold|gold\s+(chain|buttons?|hardware|zip)|silver\s+(chain|buttons?|hardware)|"
                        r"white\s+(sole|stitch(ing)?|logo|print|graphic|lettering)|black\s+(sole|logo|lettering)|"
                        r"red\s+tab)\b", re.I)

# Fabrics that make a garment a different thing (denim pants ≠ corduroy pants).
MATERIAL_WORDS = {
    "denim": "denim", "jean": "denim", "jeans": "denim", "corduroy": "corduroy", "cord": "corduroy",
    "cords": "corduroy", "leather": "leather", "faux leather": "leather", "vegan leather": "leather",
    "pleather": "leather", "suede": "suede", "wool": "wool", "merino": "wool", "cashmere": "cashmere",
    "linen": "linen", "silk": "silk", "satin": "satin", "velvet": "velvet", "fleece": "fleece",
    "tweed": "tweed", "sherpa": "fleece", "nylon": "nylon", "knit": "knit", "crochet": "knit",
}
_MATERIAL_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, MATERIAL_WORDS), key=len, reverse=True)) + r")\b", re.I)
# Close enough to never count as a mismatch with each other.
_MATERIAL_FRIENDS = [{"wool", "cashmere", "knit", "tweed"}, {"silk", "satin"}, {"leather", "suede"}]

_MEN = re.compile(r"\b(men['’]?s|mens|for men|for him|male|gentlemen['’]?s)\b", re.I)
_WOMEN = re.compile(r"\b(women['’]?s|womens|woman['’]?s|ladies['’]?|lady|for women|for her|female|"
                    r"juniors?|maternity|misses)\b", re.I)
# Item types that are cut for women even when the title doesn't say so.
_WOMENS_TYPES = re.compile(r"\b(dress|gown|skirt|blouse|bra|bralette|camisole|cami|heels|pumps|"
                           r"slingbacks?|leggings|bodysuit|romper|maternity)\b", re.I)


def listing_category(item: dict) -> str | None:
    text = f"{item.get('title') or ''} {item.get('category') or ''}"
    for category, pattern in _CATEGORY_RES:
        if pattern.search(text):
            return category
    return None


def colors_in(text: str) -> set[str]:
    text = _NOT_COLOR.sub(" ", str(text or ""))
    return {COLOR_WORDS[m.group(1).lower()] for m in _COLOR_RE.finditer(text)}


def materials_in(text: str) -> set[str]:
    return {MATERIAL_WORDS[m.group(1).lower()] for m in _MATERIAL_RE.finditer(str(text or ""))}


def listing_gender(item: dict) -> str | None:
    """'men' | 'women' | None (not stated). Kids' items are handled by tools.is_kids_item."""
    text = f"{item.get('title') or ''} {item.get('category') or ''}"
    men, women = bool(_MEN.search(text)), bool(_WOMEN.search(text))
    if men and not women:
        return "men"
    if women and not men:
        return "women"
    if not men and not women and _WOMENS_TYPES.search(text):
        return "women"
    return None


def gender_ok(item: dict, shopping_for: str | None) -> bool:
    """A women's shopper never sees men's items and vice versa; 'both' or unset sees all."""
    if shopping_for not in ("women", "men"):
        return True
    found = listing_gender(item)
    return found is None or found == shopping_for


def query_gender(text: str) -> str | None:
    men, women = bool(_MEN.search(text or "")), bool(_WOMEN.search(text or ""))
    return "men" if men and not women else "women" if women and not men else None


CONDITIONS = ("new_with_tags", "new", "like_new", "good", "fair")
CONDITION_LABELS = {"new_with_tags": "New with tags", "new": "New", "like_new": "Like new",
                    "good": "Good", "fair": "Fair"}


def condition_bucket(condition: str | None) -> str | None:
    c = (condition or "").lower()
    if not c or "unspecified" in c:
        return None
    if "with tags" in c or c in ("nwt",):
        return "new_with_tags"
    if "like new" in c or "excellent" in c:
        return "like_new"
    if c.startswith("new") or "without tags" in c or "brand new" in c:
        return "new"
    if "good" in c or "very good" in c:
        return "good"
    if "fair" in c or "poor" in c or "worn" in c:
        return "fair"
    return None


def query_attributes(text: str) -> dict:
    return {
        "category": listing_category({"title": text}),
        "colors": colors_in(text),
        "materials": materials_in(text),
        "gender": query_gender(text),
    }


def _families(colors: set[str]) -> set[str]:
    return {COLOR_FAMILY.get(c, c) for c in colors}


def _materials_clash(wanted: set[str], found: set[str]) -> bool:
    if not wanted or not found or wanted & found:
        return False
    for friends in _MATERIAL_FRIENDS:
        if wanted & friends and found & friends:
            return False
    return True


def clear_mismatch(wanted: dict, item: dict) -> str | None:
    """
    Why `item` clearly isn't what `wanted` (query_attributes) asks for, or None.
    Only fires when the listing states the conflicting thing itself.
    """
    title = f"{item.get('title') or ''}"
    category = listing_category(item)
    if wanted.get("category") and category and category != wanted["category"]:
        return "category"
    if wanted.get("colors"):
        found = colors_in(title)
        if found and not (_families(found) & _families(wanted["colors"])):
            return "colour"
    if _materials_clash(wanted.get("materials") or set(), materials_in(title)):
        return "fabric"
    if wanted.get("gender") and not gender_ok(item, wanted["gender"]):
        return "gender"
    return None
