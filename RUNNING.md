# Running FitFindr

**Path A (the way to run it): the deployed app.** Path B at the end is a local
backup if the hosted copy is down.

## Path A: the deployed app

| What | URL |
|---|---|
| App (open this) | https://fitfindr-ten.vercel.app |
| API health check | https://fitfindr-api.onrender.com/health |

The API runs on Render's free plan and sleeps after 15 idle minutes, so the
first request after a pause takes about a minute. Open the `/health` link once
and wait for `{"ok":true,"data_mode":"live","env":"production"}`, then use the app.

### How it was deployed

- **Backend on Render.** A Blueprint built from [`render.yaml`](render.yaml):
  service `fitfindr-api`, branch `v2`, root directory `backend`, free plan,
  region Oregon. Build `pip install -r requirements.txt`; start
  `uvicorn api.main:app --host 0.0.0.0 --port $PORT --proxy-headers`. Health
  check `/health`. Auto-deploy is **off**: to redeploy, open the service in the
  Render dashboard and choose Manual Deploy, then Deploy latest commit.
- **Frontend on Vercel.** Project `fitfindr`, root directory `frontend`,
  framework Next.js, built with `npm ci` and `npm run build`
  ([`frontend/vercel.json`](frontend/vercel.json) sets the security headers and
  hides `/dev/*`). `NEXT_PUBLIC_*` values are baked in at build time, so change
  one, then redeploy.
- **Database, sign-in and photos on Supabase.** Tables come from
  `supabase/schema.sql` plus `supabase/migrations/`, applied with
  `python scripts/migrate.py` from `backend/`.
- The full click-by-click guide, and what to check after a deploy, is in
  [docs/DEPLOY.md](docs/DEPLOY.md).

### Environment variable names (values are never in the repo)

Render (the API):

| Name | Purpose |
|---|---|
| `APP_ENV` | `production` (set in `render.yaml`; refuses fixtures and `FITFINDR_FAIL_STORE`) |
| `FITFINDR_DATA_MODE` | `live` (set in `render.yaml`) |
| `FITFINDR_PLANNER` | `gemini` (the model picks tools) or `rules` |
| `FITFINDR_STYLIST_LIVE_CALLS`, `FITFINDR_BROADEN_LIVE_FETCHES`, `FITFINDR_IMAGE_MODEL` | tuning, set in `render.yaml` |
| `PYTHON_VERSION`, `PYTHONUTF8` | runtime, set in `render.yaml` |
| `FRONTEND_ORIGINS` | the Vercel URL(s) allowed by CORS |
| `FRONTEND_ORIGIN_REGEX` | optional: Vercel preview URLs |
| `GEMINI_API_KEY` | Gemini |
| `RAPIDAPI_KEY` | RapidAPI (one key for all hosts) |
| `RESALE_API_HOST` | Fashion Resale API: Depop, Poshmark, Mercari, eBay |
| `ETSY_API_HOST` | Etsy API |
| `FB_MARKETPLACE_HOST` | Facebook Marketplace (not subscribed yet) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase |

Optional, for the failure handling (defaults in `backend/config.py`):
`FITFINDR_STORE_TIMEOUT` (seconds, default 20), `FITFINDR_RETRY_MAX` (default
1), `FITFINDR_RETRY_BACKOFF` (seconds, default 1.5), `FITFINDR_SEARCH_LOG`
(log file path), `FITFINDR_SEARCH_LOG_DB` (`0` = file only). `FITFINDR_FAIL_STORE`
is for testing only and must stay unset on Render.

Vercel (the app): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
`NEXT_PUBLIC_API_URL` (the Render URL, no trailing `/`).

### Before the search log reaches the database

Each search also saves its record in the `traces` table. That needs migration
`0006_traces_record.sql` (one new column). Until it is applied, rows are still
saved, just without the record, and the log file is unaffected:

```powershell
cd backend
.venv\Scripts\Activate.ps1
$env:PYTHONUTF8=1
python scripts/migrate.py --status    # 0006 should say "pending" until applied
python scripts/migrate.py             # applies it; ends with APPLIED 0006_traces_record.sql
```

## Path B: local backup

Needs Python 3.12, Node 20 and a filled-in `.env` (copy `.env.example`; setup
steps are in the [README](README.md#run-it-locally)). From the repo root, in two
PowerShell terminals:

```powershell
cd backend; .venv\Scripts\Activate.ps1; $env:PYTHONUTF8=1; $env:FITFINDR_DATA_MODE='live'; uvicorn api.main:app --reload --port 8000
```

It worked when the log says `Uvicorn running on http://127.0.0.1:8000` and
http://localhost:8000/health shows `"data_mode":"live"`.

```powershell
cd frontend; npm run dev
```

Open http://localhost:3000. With no RapidAPI quota to spend, use recorded data
instead: set `$env:FITFINDR_DATA_MODE='fixtures'` before `uvicorn`.

### Try a store failure without spending quota

```powershell
cd backend; $env:PYTHONUTF8=1; $env:FITFINDR_DATA_MODE='fixtures'; $env:FITFINDR_FAIL_STORE='etsy:timeout'; uvicorn api.main:app --port 8000
```

Search in the app: results from the other stores show, with a notice "Etsy took
too long to answer." Faults and the retry rule are in
[docs/FAILURE_HANDLING.md](docs/FAILURE_HANDLING.md).

## Logs and cost

### The search log

Every search writes one JSON record (timestamp, query, filters, stores called,
per-store status, latency and error, result count, total latency, tokens, cost),
including searches that failed or were refused. It goes to:

- `backend/logs/searches.jsonl`, one JSON object per line (git-ignored). On
  Render's free plan the disk is wiped on every deploy and restart, so use the
  table for anything you want to keep.
- the `traces` table in Supabase, column `record` (view the latest rows at
  `/dev/traces` locally).

Look at the last record locally:

```powershell
Get-Content backend\logs\searches.jsonl -Tail 1 | ConvertFrom-Json | ConvertTo-Json -Depth 6
```

A record never contains an API key, a user id or the listings themselves.

### Benchmark: 10 searches, average cost and latency

```powershell
cd backend; .venv\Scripts\Activate.ps1; $env:PYTHONUTF8=1
python scripts/bench_searches.py              # recorded data + real Gemini calls (uses a little Gemini quota)
python scripts/bench_searches.py --data cache # only what is in the 24 h search cache
python scripts/bench_searches.py --dry-run    # no model calls: checks the script works, cost is 0
```

It posts 10 queries to the real `/search` route in-process and prints a table
plus the averages; the report is also saved under `backend/logs/` (git-ignored).
It makes **no RapidAPI calls**: fixtures mode never builds a request, cache mode
skips any store with nothing cached, the RapidAPI key is blanked inside the
script, and the report fails loudly if any record shows a live call. It never
writes to the database.

### How cost is measured

- **Latency** is the full time of one `POST /search`, from the request arriving
  in the route to the response being ready, measured with `time.perf_counter`.
  It includes the store calls, ranking, the agent's model calls, the outfit
  and the fit card. The per-store `latency_ms` inside the record shows how long
  each store took.
- **Cost** is the estimated Gemini cost of that search, not a bill. Every model
  call reports its token counts in Gemini's own response metadata
  (`usage_metadata`). `backend/generate.py` adds them up per search, and cost is
  `(input tokens x input price + output tokens x output price) / 1,000,000`
  using the per-model list prices in `PRICES_PER_M` in `backend/config.py`. The
  free tier charges nothing; the number says what the same traffic would cost on
  the paid tier. A model that isn't in the price table is priced as
  `gemini-3.5-flash`, the higher of the common prices, so the estimate leans high.
- **What is not in the cost:** RapidAPI is a free plan with a monthly call cap,
  so it adds no dollars. Instead the record has `live_calls`, the number of real
  RapidAPI requests (a retry counts, a cache hit does not). Hosting (Render,
  Vercel, Supabase) is on free plans and is not counted.
- The model response cache is switched off in the benchmark, so repeating the
  run measures real calls rather than cached answers.
