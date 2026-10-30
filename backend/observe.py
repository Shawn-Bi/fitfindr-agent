"""
Traces (A2): one row per agent run in the Supabase `traces` table — steps,
tool calls, latency, tokens and an estimated cost — read back on /dev/traces.

    observe.save_trace("search", query, user_id, session)          # agent runs
    observe.save_usage("stylist", item_name, user_id, usage, steps) # other runs

Saving happens on a background thread and never fails a request. Results in
steps are shortened (titles, counts), so a trace never stores a whole listing
pool.
"""

import logging
import threading

import config

log = logging.getLogger("fitfindr.traces")


def _short(value, limit: int = 300):
    if isinstance(value, dict):
        return {k: _short(v, 160) for k, v in list(value.items())[:12]}
    if isinstance(value, list):
        return [_short(v, 160) for v in value[:6]]
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    return value


def outcome(session: dict) -> str:
    if session.get("clarify"):
        return "clarify"
    if session.get("error"):
        return "empty"
    if session.get("styling_error"):
        return "styling_unavailable"
    return "relaxed" if session.get("relaxed") else "completed"


def row(kind: str, query: str | None, user_id: str | None, usage: dict | None,
        steps: list, planner: str | None = None, result: str | None = None) -> dict:
    usage = usage or {}
    return {
        "kind": kind,
        "query": (query or "")[:300],
        "user_id": user_id,
        "planner": planner,
        "outcome": result,
        "steps": [_short(s) for s in steps][:20],
        "tool_calls": int(usage.get("tool_calls") or len(steps)),
        "model_calls": int(usage.get("calls") or 0),
        "latency_ms": int(usage.get("latency_ms") or 0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "est_cost_usd": round(float(usage.get("est_cost_usd") or 0.0), 6),
    }


def _insert(data: dict) -> None:
    import supa
    try:
        supa.service().insert("traces", data)
    except Exception as exc:  # noqa: BLE001 — observability must never break the product
        log.warning("trace not saved: %s", config.redact(exc))


def save(data: dict) -> None:
    import supa
    if not supa.configured():
        return
    threading.Thread(target=_insert, args=(data,), daemon=True).start()


def save_trace(kind: str, query: str, user_id: str | None, session: dict) -> None:
    save(row(kind, query, user_id, session.get("usage"), session.get("steps") or [],
             session.get("planner"), outcome(session)))


def save_usage(kind: str, query: str, user_id: str | None, usage: dict, steps: list,
               result: str = "completed") -> None:
    save(row(kind, query, user_id, usage, steps, None, result))
