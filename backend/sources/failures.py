"""
Failure handling for store APIs (capstone, Shape B "Harden against failure").

One store failing must never take the search down. This module is the single
place that decides, for a failed store call:

    what kind of failure it was   StoreError.kind
    what to tell the user         plain_reason()   (no jargon, no codes)
    whether to try once more      RETRY_KINDS      (timeout and 429 only)
    what to write in the log      log_failure()    (one JSON line, no secrets)

and it holds the switch that triggers each failure on purpose:

    FITFINDR_FAIL_STORE=depop:timeout,etsy:403

Kinds
    timeout        the store did not answer in time
    rate_limited   HTTP 429
    forbidden      HTTP 401/403 (not subscribed, bad key)
    server_error   HTTP 5xx
    http_error     any other HTTP error
    network        could not connect
    malformed      the reply was not JSON, or not the shape we expect
    quota_paused   our own monthly stop line (CLAUDE.md data rule 4)
    not_configured host or key missing on this server
    unknown        anything else

Only `timeout` and `rate_limited` are retried, once, after a short backoff.
Everything else fails at once: a 403 or a malformed reply will not fix itself,
and every live attempt costs monthly quota.
"""

import datetime as dt
import json
import logging
import socket
import time
import urllib.error

import config

log = logging.getLogger("fitfindr.failures")

KINDS = ("timeout", "rate_limited", "forbidden", "server_error", "http_error",
         "network", "malformed", "quota_paused", "not_configured", "unknown")
RETRY_KINDS = ("timeout", "rate_limited")

# What the user reads. It follows "<Store> " (or "A, B and C "), so each phrase starts with a verb
# that reads the same for one store or several.
_PLAIN = {
    "timeout": "took too long to answer",
    "rate_limited": "got too many requests and couldn't answer",
    "forbidden": "turned down our request (an access problem on our side)",
    "server_error": "had a problem on its end",
    "http_error": "sent back an error",
    "network": "could not be reached",
    "malformed": "sent back data we couldn't read",
    "quota_paused": "hit this month's free limit",
    "not_configured": "has no API access set up on this server",
    "unknown": "ran into an unexpected problem",
}


class StoreError(Exception):
    """A store call failed. `kind` is one of KINDS; `detail` is safe to log (secrets removed)."""

    def __init__(self, kind: str, detail: str = "", http_status: int | None = None,
                 resumes: str | None = None):
        assert kind in KINDS, kind
        self.kind = kind
        self.detail = config.redact(detail)[:300]
        self.http_status = http_status
        self.resumes = resumes
        super().__init__(f"{kind}: {self.detail}" if self.detail else kind)


def plain_reason(kind: str, resumes: str | None = None) -> str:
    """The end of a sentence that starts with the store's name."""
    text = _PLAIN.get(kind, _PLAIN["unknown"])
    if kind == "quota_paused" and resumes:
        try:
            day = dt.date.fromisoformat(resumes)
            resumes = f"{day.strftime('%b')} {day.day}"      # "Nov 1"
        except ValueError:
            pass
        return f"{text} (back on {resumes})"
    return text


def http_error(api_name: str, code: int, body: str = "") -> StoreError:
    """A StoreError for an HTTP error status."""
    if code == 429:
        kind = "rate_limited"
    elif code in (401, 403):
        kind = "forbidden"
    elif code >= 500:
        kind = "server_error"
    else:
        kind = "http_error"
    return StoreError(kind, f"{api_name} returned HTTP {code}: {body}", http_status=code)


def classify(exc: BaseException) -> StoreError:
    """Turn whatever a store call raised into a StoreError."""
    if isinstance(exc, StoreError):
        return exc
    try:  # the quota module imports config only, so this cannot loop
        from sources import quota
        if isinstance(exc, quota.QuotaPaused):
            return StoreError("quota_paused", str(exc), resumes=exc.resumes)
        if isinstance(exc, quota.QuotaUnknown):
            return StoreError("unknown", f"quota counter unreadable: {exc}")
    except ImportError:  # pragma: no cover
        pass
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return StoreError("timeout", "no answer before the timeout")
    if isinstance(exc, urllib.error.HTTPError):
        return http_error("store API", exc.code)
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return StoreError("timeout", "no answer before the timeout")
        return StoreError("network", f"could not connect: {reason}")
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        return StoreError("malformed", f"reply is not valid JSON: {exc}")
    if isinstance(exc, RuntimeError) and "must be set in .env" in str(exc):
        return StoreError("not_configured", str(exc))
    return StoreError("unknown", f"{type(exc).__name__}: {exc}")


# ── Trigger a failure on purpose ─────────────────────────────────────────────
# FITFINDR_FAIL_STORE="<store>:<fault>[:once],..."   store = depop, poshmark,
# mercari, ebay, etsy, resale (the Fashion Resale host) or *.
# fault = timeout | 403 | 429 | 500 | quota | malformed.  "once" fails the
# first attempt only, so the retry can be seen to succeed.
# Depop, Poshmark, Mercari and eBay share one API call, so naming any one of
# them fails all four, exactly as a real outage would.

FAULTS = {"timeout": "timeout", "403": "forbidden", "429": "rate_limited", "500": "server_error",
          "quota": "quota_paused", "malformed": "malformed"}


def parse_injection(spec: str) -> dict[str, tuple[str, bool]]:
    """'depop:timeout,etsy:429:once' → {'depop': ('timeout', False), 'etsy': ('429', True)}."""
    rules: dict[str, tuple[str, bool]] = {}
    for part in (spec or "").split(","):
        bits = [b.strip().lower() for b in part.split(":") if b.strip()]
        if not bits:
            continue
        if len(bits) < 2 or bits[1] not in FAULTS or (len(bits) > 2 and bits[2] != "once"):
            raise ValueError(
                f"FITFINDR_FAIL_STORE: can't read {part.strip()!r}. Use store:fault or store:fault:once, "
                f"with fault one of {', '.join(FAULTS)}.")
        rules[bits[0]] = (bits[1], len(bits) > 2)
    return rules


def injected_fault(adapter, attempt: int) -> StoreError | None:
    """The fault to raise instead of calling `adapter`, if FITFINDR_FAIL_STORE names it."""
    if not config.FAIL_STORE:
        return None
    names = {"*", getattr(adapter, "FIXTURE_PREFIX", ""), *adapter.PLATFORMS}
    if adapter.__name__.rsplit(".", 1)[-1] == "resale":
        names.add("resale")
    for name, (fault, once) in parse_injection(config.FAIL_STORE).items():
        if name in names and not (once and attempt > 1):
            if fault == "quota":
                from sources import quota
                return StoreError("quota_paused", "injected (FITFINDR_FAIL_STORE)", resumes=quota.resumes_on())
            if fault == "malformed":
                return StoreError("malformed", "injected (FITFINDR_FAIL_STORE)")
            code = {"403": 403, "429": 429, "500": 500}.get(fault)
            return StoreError(FAULTS[fault], "injected (FITFINDR_FAIL_STORE)", http_status=code)
    return None


# ── Run one store call: inject, retry once, time it ──────────────────────────

def call(adapter, fn, *, sleep=time.sleep, clock=time.monotonic) -> dict:
    """
    Run fn() for `adapter` (a function that fetches and returns the raw response).

    Returns {"raw": ..., "ok": True, "attempts": n, "latency_ms": ms} on success or
    {"raw": None, "ok": False, "error": StoreError, "attempts": n, "latency_ms": ms}.
    Never raises (KeyboardInterrupt and SystemExit excepted). A timeout or a 429 is retried once after
    config.RETRY_BACKOFF_SECONDS; any other failure is final.
    """
    started = clock()
    attempts, error = 0, None
    while attempts < 1 + config.RETRY_MAX:
        attempts += 1
        error = injected_fault(adapter, attempts)
        if error is None:
            try:
                raw = fn()
            except Exception as exc:  # noqa: BLE001 — classify() sorts out what it was
                error = classify(exc)
            else:
                return {"raw": raw, "ok": True, "attempts": attempts,
                        "latency_ms": round((clock() - started) * 1000)}
        if error.kind not in RETRY_KINDS or attempts > config.RETRY_MAX:
            break
        log_failure(adapter, error, attempts, will_retry=True)
        sleep(config.RETRY_BACKOFF_SECONDS)
    log_failure(adapter, error, attempts)
    return {"raw": None, "ok": False, "error": error, "attempts": attempts,
            "latency_ms": round((clock() - started) * 1000)}


def log_failure(adapter, error: StoreError, attempts: int, will_retry: bool = False) -> None:
    """One structured log line per failed attempt. Never contains a key or a full response."""
    log.warning(json.dumps({
        "event": "store_failure", "store": adapter.__name__.rsplit(".", 1)[-1],
        "platforms": list(adapter.PLATFORMS), "kind": error.kind, "http_status": error.http_status,
        "attempt": attempts, "will_retry": will_retry, "detail": error.detail,
    }))
