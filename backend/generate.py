"""
The one place FitFindr talks to the model.

Two of your three tools call out to a service. Everything that does goes
through `generate()` below.

That matters more in unit 3 than it did in unit 1, because an agent run is
several requests rather than one. A student iterating on a loop will cross the
per-minute limit within a few minutes. Rather than three hundred people each
writing their own pacing code, the pacing lives here, once.

What this does for you:

  • Paces requests so you stay under the per-minute limit, and says when it's
    waiting. A pause is the limiter doing its job, not a hang.
  • Reuses answers to prompts already sent, while you're building. Turned off
    for evaluation runs.
  • Stops if a session makes an unreasonable number of calls, rather than
    silently draining your day's allowance. A runaway agent loop is the
    classic way to do that.
  • Retries when the service says you're going too fast.
  • Returns a readable message when the model can't be reached, instead of a
    stack trace. Unit 4 Milestone 2 has you trigger exactly that on purpose.
  • Counts your calls and the tokens they used, so quota — and cost — are
    numbers you can see rather than numbers you multiply off a pricing page.

The model name and the temperature live in config.py, not here.
"""

import hashlib
import json
import os
import re
import sys
import time

import config

_call_times: list[float] = []
_session_calls = 0
_cache_hits = 0
_prompt_tokens = 0
_output_tokens = 0
_client = None
_budget_warned = False


class QuotaGuard(Exception):
    """Raised when a session blows through its request budget."""


class ModelUnavailable(Exception):
    """
    Raised when the model can't be reached at all — a bad key, no network, a
    model name that doesn't resolve.

    This exists so your agent can catch one specific thing and say something
    useful, instead of showing a user a stack trace. Unit 4 Milestone 2 has you
    trigger it deliberately by changing one character of your key.
    """


# ─── Cache ───────────────────────────────────────────────────────────────────


def _cache_key(prompt: str, system: str | None, temperature: float) -> str:
    blob = json.dumps(
        [config.MODEL, system or "", prompt, temperature], sort_keys=True
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _cache_read(key: str) -> str | None:
    path = config.CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    except Exception:
        return None


def _cache_write(key: str, response: str) -> None:
    config.CACHE_DIR.mkdir(exist_ok=True)
    path = config.CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"response": response}), encoding="utf-8")


def clear_cache() -> int:
    """Delete every cached response. Returns how many were removed."""
    if not config.CACHE_DIR.exists():
        return 0
    files = list(config.CACHE_DIR.glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)


# ─── Reading JSON answers ─────────────────────────────────────────────────────


def loads_json(raw: str):
    """
    Parse a JSON answer. Tolerates a ```json fence and trailing junk after the
    first complete object (models sometimes add a stray "}"). Raises
    ValueError (json.JSONDecodeError) when there is no JSON at all.
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i >= 0]
        if not starts:
            raise
        obj, _ = json.JSONDecoder().raw_decode(cleaned[min(starts):])
        return obj


# ─── Pacing and guards ───────────────────────────────────────────────────────


def _wait_for_slot() -> None:
    """Sleep, if we've used up this minute's allowance."""
    now = time.monotonic()
    _call_times[:] = [t for t in _call_times if now - t < 60.0]

    if len(_call_times) < config.REQUESTS_PER_MINUTE:
        return

    sleep_for = 60.0 - (now - _call_times[0]) + 0.1
    if sleep_for > 0:
        # Only worth announcing if it's long enough to notice. Otherwise the
        # message reads "Waiting 0s", which looks like something went wrong.
        if sleep_for >= 1.0:
            print(
                f"  [rate limit] {config.REQUESTS_PER_MINUTE} requests used this "
                f"minute. Waiting {sleep_for:.0f}s. This is normal.",
                file=sys.stderr,
                flush=True,
            )
        time.sleep(sleep_for)
        _call_times[:] = [t for t in _call_times if time.monotonic() - t < 60.0]


def _check_budget() -> None:
    global _budget_warned
    m = _meter.get()
    if m is not None:   # inside one agent run: a per-run cap instead of the session's
        if m["calls"] < config.RUN_REQUEST_BUDGET:
            return
        raise QuotaGuard(f"One run made {m['calls']} model calls (RUN_REQUEST_BUDGET); stopping it.")
    if _session_calls < config.SESSION_REQUEST_BUDGET:
        return
    if not _budget_warned:
        _budget_warned = True
    raise QuotaGuard(
        f"This session has made {_session_calls} requests, which is the "
        f"budget set in config.py (SESSION_REQUEST_BUDGET).\n"
        f"That usually means a loop is running away rather than that you've "
        f"done {_session_calls} requests' worth of real work.\n"
        f"Stop the program and look for the loop. If you really do need more, "
        f"raise the number in config.py — but look first."
    )


def usage() -> str:
    """One line on what this session has spent. Printed by app.py on exit."""
    tokens = ""
    if _prompt_tokens or _output_tokens:
        tokens = (
            f", {_prompt_tokens} prompt + {_output_tokens} output tokens"
        )
    return (
        f"{_session_calls} model calls this session"
        f"{f', {_cache_hits} served from cache' if _cache_hits else ''}"
        f"{tokens}"
    )


def call_count() -> int:
    return _session_calls


def token_counts() -> dict:
    """
    What this session actually spent, in tokens, as reported by the service.

    Here's why this exists: a number off the pricing page is an estimate of
    what a run like yours might cost. This is what your run did cost. When you
    write down the cost of one agent run, take it from here.

    Cached answers cost nothing and so add nothing — if you want the real
    per-run numbers, run with the cache off.
    """
    return {
        "prompt": _prompt_tokens,
        "output": _output_tokens,
        "total": _prompt_tokens + _output_tokens,
    }


# ─── The call ────────────────────────────────────────────────────────────────


def _explain(exc: Exception) -> str:
    """Turn a provider exception into something a person can act on."""
    message = str(exc).lower()
    if "api key" in message or "api_key" in message or "unauthenticated" in message:
        return (
            "The model rejected your API key. Check GEMINI_API_KEY in your .env "
            "file, or create a fresh key at aistudio.google.com."
        )
    if "not found" in message or "404" in message:
        return (
            f"The model name '{config.MODEL}' did not resolve. If you changed "
            f"AI201_MODEL in your .env, put it back. Otherwise post in the help "
            f"channel — this is not something you caused."
        )
    if "connection" in message or "timeout" in message or "network" in message:
        return "Couldn't reach the model. Check your internet connection and try again."
    return config.redact(f"Couldn't reach the model: {exc}")


def _retry_delay(exc: Exception, attempt: int) -> float:
    """
    How long to wait before retrying a call the service pushed back on.

    When you cross the per-minute limit, the service usually says how long it
    wants you to wait — "Please retry in 29.7s", or a retryDelay field. Honour
    that, because the limit is per *minute* and a 1-2-4-8 backoff gives up
    about fifteen seconds in, well before the minute is over. That's the
    difference between a run that pauses and a run that dies.

    Falls back to exponential backoff when the service doesn't say.
    """
    text = str(exc)
    match = (
        re.search(r"retry in (\d+(?:\.\d+)?)\s*s", text, re.I)
        or re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s", text)
    )
    hinted = float(match.group(1)) + 1.0 if match else 0.0
    return min(65.0, max(2.0 ** attempt, hinted))


def _get_client():
    global _client
    if _client is None:
        from google import genai

        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "No GEMINI_API_KEY found.\n"
                "Copy .env.example to .env and paste your key in, then try "
                "again. `python test.py` will confirm it's working."
            )
        _client = genai.Client(api_key=key)
    return _client


# ─── Per-run meter and the call ledger ───────────────────────────────────────
#
# A meter counts the model calls, tokens and time of one agent run (one search,
# one stylist outfit), for the trace saved with it. It lives in a context
# variable, so two web requests running at once never mix their numbers.
#
# The ledger (.cache/gemini_ledger.json) counts every real call per day and
# model, so a night's spend is a number you can read rather than estimate.

import contextlib
import contextvars
import datetime as _dt
import threading

_meter: contextvars.ContextVar = contextvars.ContextVar("fitfindr_meter", default=None)
_ledger_lock = threading.Lock()
LEDGER = config.CACHE_DIR / "gemini_ledger.json"


@contextlib.contextmanager
def meter():
    """
    with generate.meter() as m:
        ...                       # every model call in here is counted in m
    m == {"calls", "prompt_tokens", "output_tokens", "by_model", "est_cost_usd"}
    """
    m = {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "by_model": {}, "est_cost_usd": 0.0}
    token = _meter.set(m)
    try:
        yield m
    finally:
        _meter.reset(token)


def _ledger_add(model: str) -> None:
    day = _dt.date.today().isoformat()
    with _ledger_lock:
        try:
            data = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — missing or unreadable: start fresh
            data = {}
        data.setdefault(day, {})
        data[day][model] = data[day].get(model, 0) + 1
        config.CACHE_DIR.mkdir(exist_ok=True)
        LEDGER.write_text(json.dumps(data, indent=1), encoding="utf-8")


def ledger(day: str | None = None) -> dict:
    """{model: calls} for one day (default today), from the ledger file."""
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return data.get(day or _dt.date.today().isoformat(), {})


def _count(model: str, prompt: int = 0, output: int = 0) -> None:
    """One real call: session totals, the active meter (if any) and the ledger."""
    global _session_calls, _prompt_tokens, _output_tokens
    _session_calls += 1
    _prompt_tokens += prompt
    _output_tokens += output
    m = _meter.get()
    if m is not None:
        m["calls"] += 1
        m["prompt_tokens"] += prompt
        m["output_tokens"] += output
        m["by_model"][model] = m["by_model"].get(model, 0) + 1
        m["est_cost_usd"] += config.estimated_cost(model, prompt, output)
    try:
        _ledger_add(model)
    except Exception:  # noqa: BLE001 — counting must never break a working call
        pass


def _tokens(response) -> tuple[int, int]:
    """(prompt, output) tokens the service reported, 0 when it didn't."""
    try:
        meta = getattr(response, "usage_metadata", None)
        prompt = getattr(meta, "prompt_token_count", None) if meta else None
        output = getattr(meta, "candidates_token_count", None) if meta else None
        return (prompt if isinstance(prompt, int) else 0, output if isinstance(output, int) else 0)
    except Exception:  # noqa: BLE001
        return 0, 0


def _request(model: str, do_call, retries: int | None = None):
    """
    The one place a request leaves this process: budget check, pacing,
    counting, retries on rate limits, readable errors. `do_call(client)`
    makes the actual SDK call and returns the response. `retries` caps the
    attempts (the web path passes 1 so a user never waits a minute for a
    nice-to-have; it falls back instead).
    """
    _check_budget()
    last_error: Exception | None = None
    attempts = config.MAX_RETRIES if retries is None else max(1, retries)
    for attempt in range(attempts):
        _wait_for_slot()
        try:
            client = _get_client()
            _call_times.append(time.monotonic())
            response = do_call(client)
            _count(model, *_tokens(response))
            return response
        except Exception as exc:  # noqa: BLE001 — surfaced below
            last_error = exc
            message = str(exc).lower()
            rate_limited = (
                "429" in message
                or "resource" in message and "exhaust" in message
                or "rate" in message and "limit" in message
                or "503" in message or "overloaded" in message or "unavailable" in message
            )
            if not rate_limited:
                raise ModelUnavailable(_explain(exc)) from exc
            # A per-day quota won't clear in a minute: retrying only wastes the run's time.
            if "perday" in message:
                raise ModelUnavailable(
                    "Daily free-tier quota used up for this model; it resets at midnight Pacific time."
                ) from exc
            if attempt + 1 >= attempts:
                break
            backoff = _retry_delay(exc, attempt)
            print(
                f"  [rate limit] service pushed back. Waiting {backoff:.0f}s "
                f"(attempt {attempt + 1} of {config.MAX_RETRIES}). This is "
                f"the limiter doing its job, not a bug.",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(backoff)

    raise RuntimeError(
        f"Still rate limited after {config.MAX_RETRIES} attempts. Wait a "
        f"minute and try again — your key is fine.\nLast error: {config.redact(last_error)}"
    )


def generate(
    prompt: str,
    system: str | None = None,
    cache: bool = True,
    temperature: float | None = None,
    json_mode: bool = False,
    model: str | None = None,
    image: tuple[bytes, str] | None = None,
) -> str:
    """
    Send a prompt and get text back.

    Args:
        prompt: what you're asking.
        system: an optional instruction about how to behave. This is the
                agent's control surface — when to do what, and what to do with
                nothing. Not a personality setting.
        cache:  reuse an identical earlier answer if there is one. Leave this
                True while building. Pass False when you're evaluating — five
                tries of the same input have to be five real answers.
        temperature: how much the model varies between runs. Defaults to
                config.TEMPERATURE. Pass 0.0 when you want the same answer
                every time.
        json_mode: ask the model for a JSON response (application/json). The
                return value is still the raw text; the caller parses it.
        model:  which model; defaults to config.MODEL. The judge uses
                config.JUDGE_MODEL.
        image:  optional (bytes, mime type) sent with the prompt (photo
                auto-tagging). Part of the cache key, by hash.

    Every call in this course goes through here. If you need to change how the
    model is called, change it in this one place.
    """
    global _cache_hits

    model = model or config.MODEL
    use_cache = cache and config.CACHE_ENABLED
    temperature = config.TEMPERATURE if temperature is None else temperature
    image_tag = f"\n[image {hashlib.sha256(image[0]).hexdigest()}]" if image else ""
    key = _cache_key(prompt + ("\n[json]" if json_mode else "") + image_tag
                     + (f"\n[model {model}]" if model != config.MODEL else ""), system, temperature)

    if use_cache:
        hit = _cache_read(key)
        if hit is not None:
            _cache_hits += 1
            return hit

    call_config = {"temperature": temperature}
    if system:
        call_config["system_instruction"] = system
    if json_mode:
        call_config["response_mime_type"] = "application/json"
    contents = prompt
    if image:
        from google.genai import types
        contents = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt]

    response = _request(model, lambda client: client.models.generate_content(
        model=model, contents=contents, config=call_config))
    text = (response.text or "").strip()
    if use_cache:
        _cache_write(key, text)
    return text


def generate_with_tools(contents: list, tools: list, system: str | None = None,
                        temperature: float = 0.2, model: str | None = None):
    """
    One function-calling turn. `contents` is the conversation so far (a list
    of google.genai Content objects), `tools` a list of FunctionDeclaration.
    Returns the model's Content (its parts hold function_call or text).
    Never cached: each turn depends on what the tools returned.
    """
    from google.genai import types

    model = model or config.MODEL
    call_config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system,
        tools=[types.Tool(function_declarations=tools)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = _request(model, lambda client: client.models.generate_content(
        model=model, contents=contents, config=call_config))
    candidates = getattr(response, "candidates", None) or []
    if not candidates or not candidates[0].content:
        return types.Content(role="model", parts=[])
    return candidates[0].content


# ─── Embeddings ──────────────────────────────────────────────────────────────
# Cached on disk by (model, text) in .cache/embeddings.sqlite, so a listing is
# embedded once no matter how many searches it shows up in.

import sqlite3

_EMBED_DB = config.CACHE_DIR / "embeddings.sqlite"
_embed_lock = threading.Lock()
EMBED_BATCH = 25


def _embed_db():
    config.CACHE_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(_EMBED_DB)
    db.execute("create table if not exists emb (k text primary key, v text)")
    return db


def embed(texts: list[str], task: str = "SEMANTIC_SIMILARITY", patient: bool = True) -> list[list[float]]:
    """
    Embedding vectors (config.EMBED_DIM floats each) for `texts`, in order.
    Raises ModelUnavailable when embeddings are off or the service fails, and
    RuntimeError when rate limited (at once if patient=False); callers fall
    back to keyword ranking.
    """
    if not config.EMBEDDINGS_ENABLED:
        raise ModelUnavailable("Embeddings are turned off (FITFINDR_EMBEDDINGS=0).")
    model = config.EMBED_MODEL
    keys = [hashlib.sha256(f"{model}|{config.EMBED_DIM}|{task}|{t}".encode("utf-8")).hexdigest()
            for t in texts]
    found: dict[str, list[float]] = {}
    with _embed_lock:
        db = _embed_db()
        try:
            for k in set(keys):
                row = db.execute("select v from emb where k = ?", (k,)).fetchone()
                if row:
                    found[k] = json.loads(row[0])
        finally:
            db.close()

    missing = [(k, t) for k, t in dict(zip(keys, texts)).items() if k not in found]
    from google.genai import types
    # The API takes ≤ 100 texts per call, but the free tier counts each text against
    # a per-minute limit, so smaller batches get through where 100 would be refused.
    for start in range(0, len(missing), EMBED_BATCH):
        batch = missing[start:start + EMBED_BATCH]
        response = _request(model, lambda client, b=batch: client.models.embed_content(
            model=model, contents=[t for _, t in b],
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=config.EMBED_DIM)),
            retries=None if patient else 1)
        vectors = [list(e.values) for e in response.embeddings]
        with _embed_lock:
            db = _embed_db()
            try:
                for (k, _), v in zip(batch, vectors):
                    found[k] = v
                    db.execute("insert or replace into emb values (?, ?)",
                               (k, json.dumps([round(x, 6) for x in v])))
                db.commit()
            finally:
                db.close()
    return [found[k] for k in keys]
