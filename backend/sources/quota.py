"""
Monthly RapidAPI call counter, one per host, with the stop lines from CLAUDE.md.

Free quotas are tiny, so every live call goes through here:

    from sources import quota
    quota.check("RESALE_API_HOST")              # raises QuotaPaused at the stop line
    resp = ...make the request...
    quota.record("RESALE_API_HOST", status=resp.status_code)

Counts live in the Supabase table `api_usage(host, month, count)`, one row per
host per calendar month, so they reset on the 1st, survive redeploys and are
shared by every backend instance. `record()` uses the atomic
`increment_api_usage` RPC. Every live call is also logged: host, UTC time,
HTTP status.

If the counter can't be read, check() fails closed (QuotaUnknown): a store we
can't count is a store we don't call.

    python -m sources.quota                  show this month's counts
    python -m sources.quota --migrate-local  copy the old backend/.quota.json counts in
"""

import datetime as dt
import json
import logging
import os
import sys

import config

log = logging.getLogger("fitfindr.live_calls")

# env var naming the host → (monthly quota, stop line)
LIMITS = {
    "RESALE_API_HOST":     (50, 40),   # Depop, Poshmark, Mercari, eBay
    "ETSY_API_HOST":       (50, 40),
    "FB_MARKETPLACE_HOST": (50, 40),   # hard limit
}


class QuotaPaused(Exception):
    """Raised when a host has reached its stop line for this month."""

    def __init__(self, source: str, resumes: str):
        self.source = source
        self.resumes = resumes
        super().__init__(f"{source} is paused for this month; resumes {resumes}")


class QuotaUnknown(RuntimeError):
    """The counter couldn't be read, so no live call is allowed."""


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def month_key(now: dt.datetime | None = None) -> str:
    """'2026-10'"""
    return (now or _now()).strftime("%Y-%m")


def month_start(now: dt.datetime | None = None) -> str:
    """'2026-10-01' — the api_usage.month value."""
    return f"{month_key(now)}-01"


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


# ── Storage ──────────────────────────────────────────────────────────────────

class SupabaseStore:
    """api_usage in Supabase, through the service-role key (RLS has no policies)."""

    def get(self, host: str, month: str) -> int:
        import supa
        rows = supa.service().select("api_usage", {
            "select": "count", "host": f"eq.{host}", "month": f"eq.{month}"})
        return int(rows[0]["count"]) if rows else 0

    def increment(self, host: str) -> int:
        import supa
        return int(supa.service().rpc("increment_api_usage", {"p_host": host}))

    def set_at_least(self, host: str, month: str, value: int) -> int:
        import supa
        current = self.get(host, month)
        if value > current:
            supa.service().insert("api_usage", {"host": host, "month": month, "count": value},
                                  upsert=True, on_conflict="host,month")
        return max(current, value)


class MemoryStore:
    """For unit tests: same interface, no network."""

    def __init__(self):
        self.counts: dict[tuple[str, str], int] = {}

    def get(self, host, month):
        return self.counts.get((host, month), 0)

    def increment(self, host):
        key = (host, month_start())
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


_store = SupabaseStore()


def use_store(store) -> None:
    """Swap the counter storage (tests use MemoryStore)."""
    global _store
    _store = store


# ── Public API ───────────────────────────────────────────────────────────────

def count(source: str, now: dt.datetime | None = None) -> int:
    """Live calls made to this host in the current calendar month."""
    try:
        return _store.get(host_name(source), month_start(now))
    except Exception as exc:  # noqa: BLE001
        raise QuotaUnknown(config.redact(f"can't read api_usage for {source}: {exc}")) from None


def is_paused(source: str, now: dt.datetime | None = None) -> bool:
    return count(source, now) >= LIMITS[source][1]


def check(source: str, now: dt.datetime | None = None) -> None:
    """Raise QuotaPaused at the stop line (QuotaUnknown if unreadable). Call before every live request."""
    if is_paused(source, now):
        raise QuotaPaused(source, resumes_on(now))


def record(source: str, status, now: dt.datetime | None = None) -> int:
    """Count one live call and log it. Returns the new monthly count (-1 if it couldn't be saved)."""
    now = now or _now()
    host = host_name(source)
    try:
        new_count = _store.increment(host)
    except Exception as exc:  # noqa: BLE001 — the call already happened; log loudly
        log.error("live call host=%s time=%s status=%s NOT COUNTED: %s", host,
                  now.isoformat(timespec="seconds"), status, config.redact(exc))
        return -1
    log.warning("live call host=%s time=%s status=%s count=%d/%d", host,
                now.isoformat(timespec="seconds"), status, new_count, LIMITS[source][1])
    return new_count


def status(source: str, platform: str, now: dt.datetime | None = None) -> dict:
    """What the UI shows for one platform: {"platform", "status": active|paused, "resumes"?}."""
    if is_paused(source, now):
        return {"platform": platform, "status": "paused", "resumes": resumes_on(now)}
    return {"platform": platform, "status": "active"}


def migrate_local_file() -> None:
    """One-off: copy counts from the old backend/.quota.json into api_usage (never lowers a count)."""
    path = config.ROOT / ".quota.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for month, hosts in data.get("counts", {}).items():
        for host, n in hosts.items():
            final = SupabaseStore().set_at_least(host, f"{month}-01", int(n))
            print(f"{month} {host}: local {n} → api_usage {final}")


if __name__ == "__main__":
    if "--migrate-local" in sys.argv:
        migrate_local_file()
    for src, (q, stop) in LIMITS.items():
        print(f"{src:20} {count(src):>3} / stop at {stop} (quota {q})")
