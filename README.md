# FitFindr

A secondhand-clothing search agent for US shoppers. Type what you want
("vintage graphic tee under $30"); FitFindr searches US resale stores, picks
the best match, shows how to wear it with your own closet and writes a short
caption. Scope: `docs/PRD.md`. Rules for working on it: `CLAUDE.md`.

Stores: Depop, Poshmark, Mercari and eBay (Fashion Resale API) and Etsy are
live; Facebook Marketplace is "Coming soon" (see `BLOCKERS.md`).

**Live:** https://fitfindr-ten.vercel.app (app, Vercel) ·
https://fitfindr-api.onrender.com/health (API, Render free plan — the first
request after 15 idle minutes takes about a minute).

## Run it locally (live data, 24 h cache)

Local development uses **live store data**. Every store search is cached for
24 hours in Supabase, so repeating a search costs nothing; a new search is one
counted RapidAPI call per store host (stop line 40 a month each — check with
`python -m sources.quota`).

Backend, in a PowerShell terminal in VS Code:

```powershell
cd backend
.venv\Scripts\Activate.ps1
$env:PYTHONUTF8=1
$env:FITFINDR_DATA_MODE='live'
uvicorn api.main:app --reload --port 8000
```

It worked when the log says `Uvicorn running on http://127.0.0.1:8000` and
http://localhost:8000/health shows `"data_mode":"live"`.

Frontend, in a second terminal:

```powershell
cd frontend
npm run dev
```

Open http://localhost:3000. It worked when the landing page says
"5 stores live".

## Tests (recorded fixtures, no live calls)

Recorded real responses in `backend/tests/fixtures/` are for tests only. Unit
tests can't reach RapidAPI at all (`backend/tests/__init__.py` blanks the key).

```powershell
cd backend
$env:PYTHONUTF8=1; $env:FITFINDR_DATA_MODE='fixtures'
python -m unittest discover -s tests -t .          # unit tests
python run_eval.py --label my-change               # the five-plus criteria
```

Playwright (375 px and 1280 px) runs against an API in fixtures mode:

```powershell
cd backend; $env:FITFINDR_DATA_MODE='fixtures'; uvicorn api.main:app --port 8000
cd frontend; npm run build; npm run start
cd frontend; npx playwright test
```

## Deploy

`docs/DEPLOY.md` (Render for the API, Vercel for the app, Supabase for data).
Deployed from branch `v2` on 2026-10-19; the live URLs are at the top.
