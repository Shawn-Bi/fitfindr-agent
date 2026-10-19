"""
Monthly RapidAPI call counter, one per host, with the stop lines from CLAUDE.md.

Free quotas are tiny, so every live call goes through here:

    from sources import quota
    quota.check("RESALE_API_HOST")              # raises QuotaPaused at the stop line
    resp = ...make the request...
    quota.record("RESALE_API_HOST", status=resp.status_code)

Counts reset on the 1st of each month (the month is part of the key).
Every live call is also logged: host, UTC time, HTTP status.

Storage is a local JSON file for now (backend/.quota.json, git-ignored).
TODO: move to the Supabase `api_usage(host, month, count)` table so the count
survives redeploys and is shared by every backend instance.
"""

import datetime as dt
import json
import logging
import os
import threading

import config

log = logging.getLogger("fitfindr.live_calls")

# env var naming the host → (monthly quota, stop line)
LIMITS = {
    "RESALE_API_HOST":     (50, 40),   # Depop, Poshmark, Mercari
    "ETSY_API_HOST":       (50, 40),
    "FB_MARKETPLACE_HOST": (50, 40),   # hard limit
    "EBAY_API_HOST":       (20, 15),   # soft limit
}

_lock = threading.Lock()


class QuotaPaused(Exception):
    """Raised when a host has reached its stop line for this month."""

    def __init__(self, source: str, resumes: str):
        self.source = source
        self.resumes = resumes
        super().__init__(f"{source} is paused for this month; resumes {resumes}")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def month_key(now: dt.datetime | None = None) -> str:
    """'2026-10'"""
    return (now or _now()).strftime("%Y-%m")


def resumes_on(now: dt.datetime | None = None) -> str:
    """First day of next month, ISO date: '2026-11-01'."""
    now = now or _now()
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return dt.date(year, month, 1).isoformat()


def host_name(source: str) -> str:
    """The actual RapidAPI host for an env var name, or the env var name if unset."""
    if source not in LIMITS:
        raise KeyError(f"Unknown source {source!r}; expected one of {sorted(LIMITS)}")
    return os.getenv(source, "").strip() or source


def _load() -> dict:
    try:
        return json.loads(config.QUOTA_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"counts": {}, "calls": []}


def _save(data: dict) -> None:
    config.QUOTA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def count(source: str, now: dt.datetime | None = None) -> int:
    """Live calls made to this host in the current calendar month."""
    return _load()["counts"].get(month_key(now), {}).get(host_name(source), 0)


def is_paused(source: str, now: dt.datetime | None = None) -> bool:
    return count(source, now) >= LIMITS[source][1]


def check(source: str, now: dt.datetime | None = None) -> None:
    """Raise QuotaPaused if this host is at its stop line. Call before every live request."""
    if is_paused(source, now):
        raise QuotaPaused(source, resumes_on(now))


def record(source: str, status, now: dt.datetime | None = None) -> int:
    """Count one live call and log it. Returns the new monthly count."""
    now = now or _now()
    host = host_name(source)
    with _lock:
        data = _load()
        month = data["counts"].setdefault(month_key(now), {})
        month[host] = month.get(host, 0) + 1
        data["calls"].append({"host": host, "time": now.isoformat(timespec="seconds"),
                              "status": status})
        _save(data)
        new_count = month[host]
    log.info("live call host=%s status=%s count=%d/%d", host, status, new_count, LIMITS[source][1])
    return new_count


def status(source: str, platform: str, now: dt.datetime | None = None) -> dict:
    """What the UI shows for one platform: {"platform", "status": active|paused, "resumes"?}."""
    if is_paused(source, now):
        return {"platform": platform, "status": "paused", "resumes": resumes_on(now)}
    return {"platform": platform, "status": "active"}


if __name__ == "__main__":
    for src, (q, stop) in LIMITS.items():
        print(f"{src:20} {count(src):>3} / stop at {stop} (quota {q})")
