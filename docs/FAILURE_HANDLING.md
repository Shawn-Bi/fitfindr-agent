# Store failure handling (capstone, Shape B)

When a store API fails, search still returns the other stores' results, says
which store is unavailable and why in plain words, and logs the failure.
Code: `backend/sources/failures.py` (rules), `backend/sources/__init__.py`
(`fetch_candidates`, where each store is called), `backend/searchlog.py` (the
record). Tests: `backend/tests/test_failures.py`.

## What each store call does now

```
fetch_candidates, per store
  injected fault (tests only)? ──► fail as that fault
  fixtures mode  ──► read recorded files
  live mode      ──► 24 h cache hit? serve it
                     nothing cached and no live call allowed? skip
                     otherwise: request ──► reply must have the right shape ──► cache it
                                   │
                                   └─ failed: timeout or 429 → wait, try once more
                                              anything else   → stop
failed store ──► status "error" (or "paused") with kind and a plain-words reason
the other stores are untouched
```

| Kind | Cause | Retried? | What the user reads after the store name |
|---|---|---|---|
| `timeout` | no answer within `FITFINDR_STORE_TIMEOUT` (20 s) | once | took too long to answer |
| `rate_limited` | HTTP 429 | once | got too many requests and couldn't answer |
| `forbidden` | HTTP 401 or 403 | no | turned down our request (an access problem on our side) |
| `server_error` | HTTP 5xx | no | had a problem on its end |
| `http_error` | any other HTTP error | no | sent back an error |
| `network` | could not connect | no | could not be reached |
| `malformed` | reply is not JSON, or lacks the expected fields | no | sent back data we couldn't read |
| `quota_paused` | our own monthly stop line (40 of 50) | no | hit this month's free limit (back on Nov 1) |
| `not_configured` | host or key missing on the server | no | has no API access set up on this server |
| `unknown` | anything else | no | ran into an unexpected problem |

Only a timeout or a 429 is retried, once, after `FITFINDR_RETRY_BACKOFF`
seconds (1.5). Every other failure will not fix itself in a second, and each
live attempt costs monthly quota. A retry is counted in the quota like any call.

A reply that fails the shape check is rejected **before** it can be cached, so
a bad reply can't be served for 24 hours.

## What the API returns

`POST /search` keeps its old shape. Each entry in `stores` can now carry:

```json
{"platform": "etsy", "label": "Etsy", "status": "error", "count": 0,
 "kind": "timeout", "reason": "took too long to answer", "attempts": 2, "latency_ms": 20040}
```

and the response has `store_notices`, one sentence per distinct reason (the four
stores behind the Fashion Resale API fail together, so they share a sentence):
`["Etsy took too long to answer."]`, or `[]` when everything worked. If every
store failed, `empty` says "We couldn't search any store right now" rather than
"No matches yet". The error `detail` (redacted of any key) goes to the log, not
to the page.

On the results page a "Some stores couldn't be searched, so these results come
from the others" box lists the notices, and the store chips show each reason.

## Trigger a failure on purpose

```powershell
cd backend; $env:PYTHONUTF8=1; $env:FITFINDR_DATA_MODE='fixtures'
$env:FITFINDR_FAIL_STORE='etsy:timeout'
uvicorn api.main:app --port 8000
```

`FITFINDR_FAIL_STORE` is a comma-separated list of `store:fault` or
`store:fault:once`.

- **store:** `depop`, `poshmark`, `mercari`, `ebay`, `etsy`, `resale` (the Fashion
  Resale host) or `*` for all. Depop, Poshmark, Mercari and eBay share one API
  call, so naming any one of them fails all four, exactly as a real outage would.
- **fault:** `timeout`, `403`, `429`, `500`, `quota` (the stop line) or `malformed`.
- **`:once`** fails the first attempt only, so you can watch a retry succeed
  (`etsy:429:once` gives Etsy results with `attempts: 2`).

Examples: `depop:403`, `etsy:malformed,ebay:timeout`, `*:429`.

An injected fault fires before the cache is read and never makes a RapidAPI
call, so it costs no quota, in fixtures or live mode. Use fixtures mode for
`:once`, because the retry then reads fixtures instead of calling the store.
The backend refuses to start with `FITFINDR_FAIL_STORE` set when
`APP_ENV=production`. A malformed value is reported with the allowed forms.

## Where a failure shows up in the logs

- One JSON line per failed attempt on the `fitfindr.failures` logger
  (`event: store_failure`, store, platforms, kind, HTTP status, attempt, whether
  it will retry, a redacted detail). On Render these are in the service logs.
- The per-search record (`backend/logs/searches.jsonl` and the `traces` table;
  see [RUNNING.md](../RUNNING.md)) lists every store's status, kind, attempts,
  latency and error, with `partial` and `failed_stores` on top.

## Limits

- The timeout is the HTTP timeout of each request (connect, then each read), not
  a hard deadline on the whole call. Stores are called one after another, so a
  search where both stores time out and are retried can take over a minute.
- Store failures are not remembered between searches: a store that is down is
  tried again on the next search (that costs quota; the stop line still applies).
- A store with no 24-hour cache that fails shows nothing; stale cache is never
  served, because the data rules allow only a copy under 24 hours old.
- Facebook Marketplace is still "coming soon" (not subscribed), not a failure.
- The Gemini side (outfit and caption) already degrades on its own; this work
  covers the store APIs only.
