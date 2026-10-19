"""
The FitFindr agent (v2, A1): the model chooses the next tool.

    python agent.py          runs three example requests below

Five tools, declared to Gemini for function calling:

    search_listings   search the stores with the parsed query and filters
    relax_search      nothing matched: drop ONE constraint (size first, then
                      budget +50%) and search again — once per run
    suggest_outfit    style one of the top results with the user's closet
    create_fit_card   buyer's verdict + shareable caption for the styled item
    ask_user          the request is too vague to search: ask one short question

Each turn the model sees what the last tool returned and picks the next one
(planner "gemini"). The policy around it is plain code, so the agent can't go
wrong in the ways that matter:

  • guards reject a call that breaks the order (styling before a search, a
    second relax, asking about a request that already names a garment…) and
    tell the model why, so it can pick again;
  • filters the user didn't remove are always applied — the model can't
    silently drop a size or budget, only relax_search can, and it says so;
  • after AGENT_MAX_STEPS tool calls, or if the model fails, the
    deterministic policy (planner "rules") finishes the run from where it is.

The session dict is still the single source of truth; every step is also in
session["steps"] (tool, arguments, result, milliseconds) for the trace.
"""

import json
import re
import time

import config
import generate
import trace
from generate import ModelUnavailable, QuotaGuard
from tools import create_fit_card_full, search_listings, suggest_outfit  # noqa: F401

# Shown to users when the model can't be reached (PRD section 5).
STYLING_UNAVAILABLE = ("Styling suggestions are unavailable right now. "
                       "Your search results still work.")

TOP_CHOICES = 5   # suggest_outfit may pick any of the first five results


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """A fresh session for one user interaction. Every tool result goes in here."""
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one styled — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # the caption create_fit_card wrote
        "fit_verdict": None,         # the buyer's verdict around it (B1)
        "error": None,               # set when the run ended with nothing to show
        "styling_error": None,       # set when the model was unavailable
        "relaxed": None,             # {"dropped", "message"} when relax_search ran
        "clarify": None,             # {"question", "suggestions"} when ask_user ran
        "planner": None,             # "gemini" or "rules" (or "gemini+rules" after a fallback)
        "steps": [],                 # [{tool, args, result, ms, by}] for the trace
        "usage": None,               # model calls, tokens, estimated cost, latency
    }


# ── parsing and the vague-request check ───────────────────────────────────────

def parse_query(query: str) -> dict:
    """
    "vintage graphic tee under $30, size M" →
    {"description": "vintage graphic tee", "size": "M", "max_price": 30.0}
    Regex only; anything not a price or a size stays in the description.
    """
    price_m = re.search(r"(?:\b(?:under|below|max|less than|up to)\s*)?\$\s?(\d+(?:\.\d+)?)",
                        query, re.I)
    size_m = re.search(r"\bsize\s+([A-Za-z0-9/.]+)", query, re.I)
    max_price = float(price_m.group(1)) if price_m else None
    size = size_m.group(1).upper() if size_m and size_m.group(1).isalpha() else (
        size_m.group(1) if size_m else None)
    description = query
    for m in (price_m, size_m):
        if m:
            description = description.replace(m.group(0), " ")
    description = re.sub(r"^\s*(i['’]?m\s+|i am\s+)?(looking for|searching for|find me|"
                         r"show me|i want|i need)\s+(an?\s+|some\s+)?", " ", description, flags=re.I)
    description = re.sub(r"\b(in|for)\b|,", " ", description, flags=re.I)
    description = re.sub(r"\s+", " ", description).strip()
    return {"description": description, "size": size, "max_price": max_price}


# Words that say nothing about WHAT to buy. A request made only of these
# ("something nice", "an outfit for a party") gets one clarifying question.
_VAGUE_WORDS = set("""
a an the some any me my i we you to for of with and or but in on at it its this that what which
something anything everything stuff thing things item items piece pieces clothes clothing outfit
outfits look looks fashion wardrobe closet style styles new nice cute cool good great pretty
lovely beautiful fancy fun stylish trendy special different interesting unique classy chic
please help idea ideas gift present want need looking show find buy get wear wearing would like
love should could recommend suggest suggestion maybe kind sort type something's anything's
occasion party wedding date night work office event events trip vacation holiday weekend
everyday day casual dressy formal summer winter spring fall autumn season birthday
""".split())


def is_vague(query: str) -> bool:
    """True when no word in the request names a garment, colour, fabric, style or brand."""
    words = [w for w in re.split(r"[^a-z0-9'’$]+", (query or "").lower()) if w]
    words = [w for w in words if not re.fullmatch(r"\$?\d+(\.\d+)?", w) and w not in ("under", "size")]
    return not words or all(w in _VAGUE_WORDS for w in words)


CLARIFY_FALLBACK = {
    "question": "What kind of piece are you after — a type, colour or style?",
    "suggestions": ["a cream knit sweater", "straight-leg jeans", "a black midi dress", "white sneakers"],
}


def relax_plan(parsed: dict) -> tuple[dict, dict] | None:
    """
    The one constraint relax_search drops, in order: size first, then budget
    +50% (rounded up to the next $5). Returns (new parsed, note) or None.
    """
    from api.catalog import raised_budget   # local import: api.catalog imports this module

    if parsed.get("size"):
        size = parsed["size"]
        return ({**parsed, "size": None},
                {"dropped": "size", "label": f"size {size}",
                 "message": f"Nothing matched in size {size}, so I searched every size."})
    if parsed.get("max_price") is not None:
        old, new = parsed["max_price"], raised_budget(parsed["max_price"])
        return ({**parsed, "max_price": float(new)},
                {"dropped": "budget", "label": f"under ${old:.0f}", "new_max_price": new,
                 "message": f"Nothing matched under ${old:.0f}, so I raised the budget to ${new}."})
    return None


# ── tool declarations (what the model sees) ───────────────────────────────────

def _declarations():
    from google.genai import types

    def decl(name, description, properties=None, required=None):
        schema = {"type": "object", "properties": properties or {}}
        if required:
            schema["required"] = required
        return types.FunctionDeclaration(name=name, description=description, parameters_json_schema=schema)

    return [
        decl("search_listings",
             "Search Depop, Poshmark, Mercari and eBay for the user's request. Uses the parsed "
             "description, size and budget (filters the user didn't remove always apply). "
             "Returns how many listings matched and the top five (index, title, price, store).",
             {"description": {"type": "string", "description": "What to search for, in a few words."}}),
        decl("relax_search",
             "Only after a search found nothing. Drops ONE constraint — the size if there is one, "
             "otherwise raises the budget by 50% — and searches again. Can be used once per request.",
             {}),
        decl("suggest_outfit",
             "Write outfit suggestions for one of the top search results using the user's closet. "
             "Pick the result that best matches the request (index 0 is the best ranked).",
             {"listing_index": {"type": "integer", "description": "Index of the result to style, 0-4."}},
             ["listing_index"]),
        decl("create_fit_card",
             "After suggest_outfit: write the buyer's verdict and a short shareable caption for "
             "the styled item. This is the last step.", {}),
        decl("ask_user",
             "Ask ONE short clarifying question instead of searching, when the request names no type "
             "of clothing, colour, fabric, style or brand (e.g. 'something nice'). Ends the turn.",
             {"question": {"type": "string", "description": "One short question, under 15 words."},
              "suggestions": {"type": "array", "items": {"type": "string"},
                              "description": "Two to four short example answers."}},
             ["question"]),
    ]


SYSTEM = (
    "You are FitFindr's shopping agent for secondhand clothing in the US. Call exactly one tool "
    "per turn and look at what it returned before choosing the next.\n"
    "Normal path: search_listings → suggest_outfit (choose the result that best fits the "
    "request) → create_fit_card.\n"
    "If a search returns count 0 and relax_search is available, call relax_search once. "
    "If it still finds nothing, stop and reply in one sentence; don't call more tools.\n"
    "If the request is too vague to search (no garment type, colour, fabric, style or brand — "
    "e.g. 'something nice'), call ask_user with one short question instead of searching.\n"
    "Never invent listings or prices."
)


# ── the run ───────────────────────────────────────────────────────────────────

class _Run:
    """One agent run: the session, the tools and the guards around them."""

    def __init__(self, query, wardrobe, parsed, search, prefs):
        self.s = new_session(query, wardrobe)
        self.s["parsed"] = dict(parsed) if parsed is not None else parse_query(query)
        self.search_fn = search
        self.prefs = prefs or {}
        self.searched = False
        self.done = False

    # ── bookkeeping
    def record(self, tool, args, result, started, by, note=""):
        ms = int((time.monotonic() - started) * 1000)
        self.s["steps"].append({"tool": tool, "args": args, "result": result, "ms": ms, "by": by,
                                **({"note": note} if note else {})})
        label = "search_listings (via MCP)" if tool == "search_listings" and self.search_fn is None else tool
        trace.step(label, inputs=args or self.s["parsed"], returned=result,
                   note=f"{by}{': ' + note if note else ''}")

    # ── guards: why a tool can't run now (None = allowed)
    def refusal(self, tool):
        s = self.s
        if self.done:
            return "The run is finished."
        if tool == "ask_user":
            if self.searched:
                return "A search already ran; don't ask now."
            if not is_vague(s["query"]):
                return "The request already names what to look for. Call search_listings."
        if tool == "search_listings":
            if self.searched:
                return "search_listings already ran. Use relax_search if it found nothing."
            if is_vague(s["query"]):
                return "The request is too vague to search. Call ask_user with one short question."
        if tool == "relax_search":
            if not self.searched or s["search_results"]:
                return "relax_search is only for a search that found nothing."
            if s["relaxed"]:
                return "relax_search already ran once. Stop here."
            if relax_plan(s["parsed"]) is None:
                return "There is no size or budget to relax. Stop here."
        if tool == "suggest_outfit" and not s["search_results"]:
            return "There are no results to style."
        if tool == "create_fit_card" and not s["outfit_suggestion"]:
            return "Call suggest_outfit first."
        return None

    # ── the tools
    def do_search(self):
        p = self.s["parsed"]
        args = {"description": p["description"], "size": p["size"], "max_price": p["max_price"]}
        if self.search_fn is None:
            from mcp_client import call_tool
            results = call_tool("search_listings", args)
        else:
            results = self.search_fn(**args)
        self.s["search_results"] = results or []
        self.searched = True
        return self._search_summary()

    def _search_summary(self):
        res = self.s["search_results"]
        out = {"count": len(res), "top": [
            {"index": i, "title": r["title"].split("\n")[0][:90], "price": r["price"], "store": r["platform"]}
            for i, r in enumerate(res[:TOP_CHOICES])]}
        if not res:
            plan = None if self.s["relaxed"] else relax_plan(self.s["parsed"])
            out["relax_available"] = plan[1]["label"] if plan else None
        return out

    def do_relax(self):
        new_parsed, note = relax_plan(self.s["parsed"])
        self.s["parsed"] = new_parsed
        self.s["relaxed"] = note
        self.searched = False
        result = self.do_search()
        result["dropped"] = note["label"]
        return result

    def do_outfit(self, index):
        results = self.s["search_results"]
        index = index if isinstance(index, int) and 0 <= index < min(TOP_CHOICES, len(results)) else 0
        self.s["selected_item"] = results[index]
        self.s["outfit_suggestion"] = suggest_outfit(self.s["selected_item"], self.s["wardrobe"])
        return {"styled": self.s["selected_item"]["title"].split("\n")[0][:90],
                "outfit": self.s["outfit_suggestion"]["text"][:300]}

    def do_card(self):
        full = create_fit_card_full(self.s["outfit_suggestion"], self.s["selected_item"])
        self.s["fit_card"], self.s["fit_verdict"] = full["caption"], full["verdict"]
        self.done = True
        return {"caption": full["caption"][:200],
                "verdict": (full["verdict"] or {}).get("verdict")}

    def do_ask(self, question, suggestions):
        question = re.sub(r"\s+", " ", str(question or "")).strip()[:160]
        suggestions = [str(x).strip()[:40] for x in (suggestions or []) if str(x).strip()][:4]
        self.s["clarify"] = ({"question": question, "suggestions": suggestions or CLARIFY_FALLBACK["suggestions"]}
                             if question else dict(CLARIFY_FALLBACK))
        self.done = True
        return {"asked": self.s["clarify"]["question"]}

    def execute(self, tool, args, by):
        """Run one tool. Returns the result dict for the model (the session holds the rest)."""
        started = time.monotonic()
        try:
            if tool == "search_listings":
                result = self.do_search()
            elif tool == "relax_search":
                result = self.do_relax()
            elif tool == "suggest_outfit":
                result = self.do_outfit(args.get("listing_index", 0))
            elif tool == "create_fit_card":
                result = self.do_card()
            elif tool == "ask_user":
                result = self.do_ask(args.get("question"), args.get("suggestions"))
            else:
                result = {"error": f"Unknown tool {tool}."}
        except (ModelUnavailable, QuotaGuard, RuntimeError) as exc:
            if tool not in ("suggest_outfit", "create_fit_card"):
                raise
            # Results still stand; only the styling is missing.
            self.s["styling_error"] = STYLING_UNAVAILABLE
            self.done = True
            self.record(tool, args, f"model unavailable: {config.redact(exc)[:120]}", started, by)
            return {"error": "styling unavailable"}
        self.record(tool, args, result, started, by)
        if tool in ("search_listings", "relax_search") and not self.s["search_results"] \
                and (self.s["relaxed"] or relax_plan(self.s["parsed"]) is None):
            self.finish_empty()
        return result

    def finish_empty(self):
        """Nothing matched, and nothing is left to relax: say what to change. No model call."""
        p = self.s["parsed"]
        self.s["error"] = (
            f"No listings matched '{p['description']}'"
            + (f" in size {p['size']}" if p["size"] else "")
            + (f" under ${p['max_price']:.0f}" if p["max_price"] else "")
            + ". Try broader keywords, a different size, or a higher price limit.")
        self.done = True

    # ── planners
    def next_rule(self):
        """The deterministic policy: what to do next from the current state."""
        s = self.s
        if not self.searched and not s["search_results"]:
            return ("ask_user", dict(CLARIFY_FALLBACK)) if is_vague(s["query"]) else ("search_listings", {})
        if not s["search_results"]:
            return ("relax_search", {}) if self.refusal("relax_search") is None else (None, None)
        if not s["outfit_suggestion"]:
            return ("suggest_outfit", {"listing_index": 0})
        if not s["fit_card"]:
            return ("create_fit_card", {})
        return (None, None)

    def run_rules(self, by="rules"):
        while not self.done:
            tool, args = self.next_rule()
            if tool is None:
                if not self.s["search_results"] and not self.s["error"] and self.searched:
                    self.finish_empty()
                self.done = True
                break
            self.execute(tool, args, by)

    def run_gemini(self):
        from google.genai import types

        decls = _declarations()
        p = self.s["parsed"]
        wardrobe_n = len((self.s["wardrobe"] or {}).get("items") or [])
        brief = {
            "request": self.s["query"],
            "parsed": {"description": p["description"], "size": p["size"], "max_price": p["max_price"]},
            "closet_items": wardrobe_n,
            "shopping_for": self.prefs.get("gender") or "not set",
        }
        contents = [types.Content(role="user", parts=[types.Part(text=json.dumps(brief))])]
        steps = 0
        while not self.done and steps < config.AGENT_MAX_STEPS:
            reply = generate.generate_with_tools(contents, decls, system=SYSTEM)
            calls = [part.function_call for part in (reply.parts or []) if part.function_call]
            if not calls:
                return   # the model stopped talking tools: the rules finish whatever is left
            call = calls[0]
            steps += 1
            args = dict(call.args or {})
            why_not = self.refusal(call.name)
            if why_not:
                self.record(call.name, args, {"refused": why_not}, time.monotonic(), "gemini", "guard")
                result = {"error": why_not}
            else:
                result = self.execute(call.name, args, "gemini")
            reply_parts = [p for p in reply.parts if p.function_call is call or not p.function_call]
            contents.append(types.Content(role="model", parts=reply_parts))
            contents.append(types.Content(role="user", parts=[types.Part.from_function_response(
                name=call.name, response={"result": result})]))


def run_agent(query: str, wardrobe: dict, parsed: dict | None = None,
              search=None, planner: str | None = None, prefs: dict | None = None) -> dict:
    """
    Run the agent once and return the finished session.

    Args:
        query:    what the user asked for, in plain language.
        wardrobe: a wardrobe dict ({"items": [...]}, may be empty).
        parsed:   optional {"description", "size", "max_price"} to use instead
                  of parsing `query` (the web API passes profile filters and
                  removed chips this way).
        search:   optional search function with search_listings' signature.
                  Default: search_listings through MCP.
        planner:  "gemini" (default, config.AGENT_PLANNER) or "rules".
        prefs:    optional profile hints for the planner ({"gender": ...}).

    Returns:
        The session dict. Check session["clarify"] (a question for the user),
        then session["error"] (nothing matched, even after relaxing), then
        session["styling_error"].
    """
    planner = (planner or config.AGENT_PLANNER).lower()
    run = _Run(query, wardrobe, parsed, search, prefs)
    trace.step("parse_query", inputs=query, returned=run.s["parsed"])
    started = time.monotonic()
    with generate.meter() as m:
        if planner == "gemini":
            run.s["planner"] = "gemini"
            try:
                run.run_gemini()
            except (ModelUnavailable, QuotaGuard, RuntimeError) as exc:
                trace.step("planner", returned=f"gemini planner failed: {config.redact(exc)[:120]}",
                           note="falling back to the rules")
            if not run.done:
                run.s["planner"] = "gemini+rules" if run.s["steps"] else "rules"
                run.run_rules(by="rules (fallback)")
        else:
            run.s["planner"] = "rules"
            run.run_rules()
    run.s["usage"] = {**m, "latency_ms": int((time.monotonic() - started) * 1000),
                      "tool_calls": sum(1 for st in run.s["steps"]
                                        if not (isinstance(st["result"], dict) and "refused" in st["result"]))}
    return run.s


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    print(f"  planner: {session['planner']} · {len(session['steps'])} steps · "
          f"{(session['usage'] or {}).get('calls')} model calls")
    if session["clarify"]:
        print(f"  asked:    {session['clarify']['question']}  {session['clarify']['suggestions']}")
        return
    if session["relaxed"]:
        print(f"  relaxed:  {session['relaxed']['message']}")
    if session["error"]:
        print(f"  stopped: {session['error']}")
        return
    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    outfit = session["outfit_suggestion"] or {}
    print(f"  outfit:   {outfit.get('text')}  (closet items: {outfit.get('item_ids')})")
    print(f"  fit card: {session['fit_card']}")
    print(f"  verdict:  {(session['fit_verdict'] or {}).get('verdict')}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    for q in ("looking for a vintage graphic tee under $30", "denim jacket size XXS under $5",
              "something nice"):
        print(f"\n=== {q} ===")
        _show(run_agent(query=q, wardrobe=get_example_wardrobe()))
