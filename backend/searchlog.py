"""
One structured record per search (capstone, Milestone 3).

Every call to POST /search ends in exactly one JSON record, including searches
that failed or were refused. The record goes to two places:

    backend/logs/searches.jsonl   one JSON object per line (path: FITFINDR_SEARCH_LOG)
    Supabase `traces` table       one row (kind "search"), the record in its `record` column

Fields
    ts, run_id, query, filters, signed_in, data_mode, outcome, error,
    result_count, total_latency_ms, partial, failed_stores,
    stores_called   platforms an adapter was asked to fetch from (live or fixtures)
    live_calls      real RapidAPI requests made (retries count, cache hits do not)
    stores          one entry per platform: status, kind, reason, attempts,
                    latency_ms, error (redacted), results
    tokens          {prompt, output, model_calls}
    cost_usd        estimated Gemini cost (how it is measured: RUNNING.md)

The record never holds an API key, a user id, or listing contents. Writing it
never raises: a full disk or an unreachable database must not break a search.
"""

import datetime as dt
import json
import logging
import threading
import uuid

import config

log = logging.getLogger("fitfindr.searchlog")
_lock = threading.Lock()


def _stores(statuses: list[dict], results: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for item in results or []:
        counts[item.get("platform")] = counts.get(item.get("platform"), 0) + 1
    rows = []
    for s in statuses or []:
        row = {"platform": s["platform"], "status": s["status"], "results": counts.get(s["platform"], 0)}
        for key in ("kind", "reason", "attempts", "latency_ms", "http_status", "resumes"):
            if s.get(key) is not None:
                row[key] = s[key]
        if s.get("error"):
            row["error"] = config.redact(s["error"])[:200]
        rows.append(row)
    return rows


def _live_calls(statuses: list[dict]) -> int:
    """Real RapidAPI requests: one per host per attempt. Cache hits, pauses and injected faults make none."""
    if config.DATA_MODE != "live":
        return 0
    per_host: dict[str, int] = {}
    for s in statuses or []:
        sent = s["status"] == "active" or (s["status"] == "error" and s.get("kind") not in ("not_configured",)
                                           and "injected" not in (s.get("error") or ""))
        if sent and s.get("source"):
            per_host[s["source"]] = s.get("attempts") or 1
    return sum(per_host.values())


def build(query: str, filters: dict | None, *, statuses: list[dict] | None = None,
          results: list[dict] | None = None, total_latency_ms: int = 0, usage: dict | None = None,
          outcome: str = "completed", error: str | None = None, signed_in: bool = False,
          run_id: str | None = None) -> dict:
    usage = usage or {}
    stores = _stores(statuses or [], results or [])
    failed = sorted({s["platform"] for s in stores if s["status"] in ("error", "paused")})
    return {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
        "run_id": run_id or uuid.uuid4().hex[:12],
        "query": (query or "")[:300],
        "filters": {k: v for k, v in (filters or {}).items() if v not in (None, [], "", False)},
        "signed_in": bool(signed_in),
        "data_mode": config.DATA_MODE,
        "outcome": outcome,
        "error": config.redact(error)[:300] if error else None,
        "result_count": len(results or []),
        "total_latency_ms": int(total_latency_ms),
        "partial": bool(failed) and bool(results),
        "failed_stores": failed,
        "stores_called": [s["platform"] for s in stores if s["status"] in ("active", "fixtures", "error")],
        "live_calls": _live_calls(statuses or []),
        "stores": stores,
        "tokens": {"prompt": int(usage.get("prompt_tokens") or 0), "output": int(usage.get("output_tokens") or 0),
                   "model_calls": int(usage.get("calls") or 0)},
        "cost_usd": round(float(usage.get("est_cost_usd") or 0.0), 6),
    }


def write(record: dict, *, session: dict | None = None, user_id: str | None = None, db: bool = True) -> None:
    """Append the record to the log file and save it as a `traces` row. Never raises."""
    try:
        path = config.SEARCH_LOG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("search log file not written: %s", config.redact(exc))
    log.info("search %s", json.dumps(record, ensure_ascii=False))
    if not (db and config.SEARCH_LOG_DB):
        return
    try:
        import observe
        session = session or {}
        usage = {**(session.get("usage") or {}), "latency_ms": record["total_latency_ms"],
                 "prompt_tokens": record["tokens"]["prompt"], "output_tokens": record["tokens"]["output"],
                 "calls": record["tokens"]["model_calls"], "est_cost_usd": record["cost_usd"]}
        data = observe.row("search", record["query"], user_id, usage, session.get("steps") or [],
                           session.get("planner"), record["outcome"])
        data["record"] = record
        observe.save(data)
    except Exception as exc:  # noqa: BLE001
        log.warning("search trace not saved: %s", config.redact(exc))
