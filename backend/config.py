"""
Settings for FitFindr.

Everything you're likely to change lives here, at the top, on purpose.

Two of these come up in the brief by name. If your fit cards come out
word-for-word identical every time, it is one of the two things below —
either the cache handed back an answer it already had, or TEMPERATURE is 0.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent          # backend/
REPO_ROOT = ROOT.parent               # FitFindr-Agent/, where .env lives
load_dotenv(REPO_ROOT / ".env")


# ─── Data mode ───────────────────────────────────────────────────────────────
# fixtures: search reads recorded real responses from backend/tests/fixtures/.
# live:     search calls RapidAPI (counted against the monthly quota).
# The product never shows mock listings, so production must be live.

DATA_MODE = os.getenv("FITFINDR_DATA_MODE", "fixtures").strip().lower() or "fixtures"
APP_ENV = os.getenv("APP_ENV", "development").strip().lower() or "development"

# ─── Secrets ─────────────────────────────────────────────────────────────────
# Never print, log or commit these. redact() scrubs their current values out of
# any text before it is shown or written to disk (error messages, run logs).

SECRET_ENV_VARS = ("GEMINI_API_KEY", "RAPIDAPI_KEY",
                   "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")


def redact(text) -> str:
    text = str(text)
    for name in SECRET_ENV_VARS:
        value = os.getenv(name, "").strip()
        if len(value) >= 8:
            text = text.replace(value, f"[REDACTED {name}]")
    return text


# The dashboard shows the REST endpoint (…supabase.co/rest/v1/); clients want the
# bare project URL, so accept either.
SUPABASE_URL = re.sub(r"/(rest/v1)?/*$", "", os.getenv("SUPABASE_URL", "").strip())


if DATA_MODE not in ("fixtures", "live"):
    raise SystemExit(
        f"FITFINDR_DATA_MODE must be 'fixtures' or 'live', got {DATA_MODE!r}."
    )
if APP_ENV == "production" and DATA_MODE == "fixtures":
    raise SystemExit(
        "Refusing to start: APP_ENV=production with FITFINDR_DATA_MODE=fixtures. "
        "Production must never serve recorded fixtures. Set FITFINDR_DATA_MODE=live."
    )


# ─── Windows console encoding ────────────────────────────────────────────────
# You should not need to touch this.
#
# On Windows the console defaults to cp1252, which cannot represent emoji. The
# model puts emoji in fit cards all the time — it is writing captions, after
# all — so printing one would crash the program with a UnicodeEncodeError,
# after the model call had already been paid for. Every entry point imports
# config, so fixing it here fixes it everywhere.

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ─── The two settings the brief tells you about ──────────────────────────────

# How much the model varies between runs. 0.0 gives you the same words every
# time; higher gives you more variation. Fit cards want variation — a caption
# that reads identically for two different items isn't a caption, it's a
# template.
TEMPERATURE = 0.9

# While you're building, identical prompts reuse the answer already received,
# so re-running the same query twenty times while debugging costs one call.
# Evaluation runs turn this off automatically — five tries have to be five
# real answers. `run_eval.py` handles that for you.
CACHE_ENABLED = os.getenv("AI201_CACHE", "1") != "0"


# ─── The agent loop ──────────────────────────────────────────────────────────

# The most common architectural failure in production agents is a missing stop
# condition — the loop runs forever, burning quota with nothing to show for it.
# Your loop this unit is short enough that you may never hit this. Keep it
# anyway; it's the habit that matters.
MAX_ITERATIONS = 10

# How many search results to consider. The agent uses the first one.
SEARCH_RESULT_LIMIT = 10


# ─── Model ───────────────────────────────────────────────────────────────────

MODEL = os.getenv("AI201_MODEL", "gemini-3.5-flash-lite")
# LLM-as-judge (run_eval.py, stylist eval): a different, stronger model than the
# one being judged, so it isn't grading its own homework.
JUDGE_MODEL = os.getenv("FITFINDR_JUDGE_MODEL", "gemini-3.5-flash")
# Semantic ranking (A4): query and listing texts are embedded and compared.
EMBED_MODEL = os.getenv("FITFINDR_EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = 256
EMBEDDINGS_ENABLED = os.getenv("FITFINDR_EMBEDDINGS", "1") != "0"

# Estimated USD per 1M tokens (input, output), for the cost column in traces.
# Paid-tier list prices as of Oct 2026; the free tier costs nothing. Update from
# ai.google.dev/pricing if they change — these are estimates, not a bill.
PRICES_PER_M = {
    "gemini-3.5-flash-lite": (0.10, 0.40),
    "gemini-3.5-flash": (0.30, 2.50),
    "gemini-embedding-001": (0.15, 0.0),
}


def estimated_cost(model: str, prompt_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES_PER_M.get(model, (0.30, 2.50))
    return (prompt_tokens * price_in + output_tokens * price_out) / 1_000_000


# ─── The tool-choosing agent (agent.py, A1) ──────────────────────────────────
# gemini: the model picks each next tool by function calling.
# rules:  the deterministic policy (also the fallback when the model fails).
AGENT_PLANNER = os.getenv("FITFINDR_PLANNER", "gemini").strip().lower()
AGENT_MAX_STEPS = 8          # tool calls per run, then the deterministic fallback finishes

# ─── The AI stylist (stylist.py, B2) ─────────────────────────────────────────
# Live RapidAPI searches one outfit may make when a planned piece has no
# cached listing (live mode only). Adding or editing a closet item rebuilds its
# outfit, so this is the per-edit cost against the 40-call monthly stop line.
STYLIST_LIVE_CALLS = int(os.getenv("FITFINDR_STYLIST_LIVE_CALLS", "1"))


# ─── Rate limiting and quota guards ──────────────────────────────────────────
# You should not need to touch these.
#
# This is the heaviest pair in the course for call volume — one agent run is
# several requests, because two of your three tools call the model. Iterating
# quickly will cross the per-minute limit. The adapter paces you and says when
# it's waiting; that pause is not a bug.
#
# REQUESTS_PER_MINUTE is 15 because that is the actual free-tier limit for
# gemini-3.5-flash-lite — the API reports it as
# GenerateRequestsPerMinutePerProjectPerModel-FreeTier, quotaValue 15. Raising
# it does not buy you more quota; it just means you hit the limit at the
# service instead of being paced here, and a paced wait is much cheaper than a
# failed run. Two model calls per agent run means about seven runs a minute.

REQUESTS_PER_MINUTE = 15
SESSION_REQUEST_BUDGET = 300
RUN_REQUEST_BUDGET = 25      # model calls inside one metered run (one search, one outfit)
MAX_RETRIES = 5

CACHE_DIR = ROOT / ".cache"


# ─── Paths ───────────────────────────────────────────────────────────────────

DATA_DIR = ROOT / "data"                       # example wardrobe only, no listings
RESULTS_DIR = ROOT / "results"
FIXTURES_DIR = ROOT / "tests" / "fixtures"     # recorded real API responses
CACHE_MAX_AGE_HOURS = 24                       # real-response cache lifetime (search_cache)
# The RapidAPI call counter lives in Supabase api_usage (sources/quota.py).


# ─── Web API (api/main.py) ───────────────────────────────────────────────────

SEARCHES_PER_MINUTE = 10                       # per signed-in user, or per IP for guests
WEB_RESULT_LIMIT = 20                          # listings on one results page
MAX_PHOTO_BYTES = 10 * 1024 * 1024             # 10 MB, PRD section 4
PHOTO_MAX_PX = 1600                            # main image, longest side
THUMB_MAX_PX = 400
# Browser origins allowed to call the API (comma-separated). The Next.js dev
# server by default; set FRONTEND_ORIGINS to the Vercel URL in production.
FRONTEND_ORIGINS = [o.strip() for o in os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
# Optional: also allow origins matching this regex, e.g. the Vercel preview
# URLs of this project: ^https://fitfindr(-[a-z0-9-]+)?\.vercel\.app$
FRONTEND_ORIGIN_REGEX = os.getenv("FRONTEND_ORIGIN_REGEX", "").strip() or None
if APP_ENV == "production" and not os.getenv("FRONTEND_ORIGINS", "").strip():
    raise SystemExit("Refusing to start: production needs FRONTEND_ORIGINS (the Vercel URL) for CORS.")
