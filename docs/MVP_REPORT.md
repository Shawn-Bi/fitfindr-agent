# MVP build report — 2026-10-19 (branch `mvp`)

Built unattended from `CLAUDE.md`, `docs/PRD.md` and `docs/DECISIONS.md`.
Zero live RapidAPI calls (fixtures mode throughout). Nothing deployed, no
accounts or paid services created. Open items are in `BLOCKERS.md`.

## How to run it locally

```powershell
# backend (terminal 1)
cd backend; .venv\Scripts\Activate.ps1; $env:PYTHONUTF8=1
pip install -r requirements.txt
$env:FITFINDR_DATA_MODE='fixtures'; uvicorn api.main:app --port 8000
# worked if http://localhost:8000/health shows "data_mode":"fixtures"

# frontend (terminal 2)
cd frontend; npm install; npm run build; npm run start
# worked if http://localhost:3000 shows the landing page
```

`frontend/.env.local` (git-ignored) was generated from `../.env` and holds the
Supabase URL, the public anon key and `NEXT_PUBLIC_API_URL=http://localhost:8000`.

## What was built

| Area | Done |
|---|---|
| Backend `backend/api/main.py` | All PRD §7 routes: `POST /search`, closet CRUD + `POST /closet/items/{id}/photo` + `/matches`, `GET/POST/DELETE /saved`, `GET/PATCH /profile`; plus `/health`, `/stores`, `/home`, `DELETE /account` (hard delete) |
| Agent | `run_agent` reused; API passes profile filters and a direct `search_listings` call (MCP stays for the eval). `suggest_outfit` now returns `{text, item_ids}` |
| Quota | Counter moved to Supabase `api_usage` via `increment_api_usage`; the 8 October calls were migrated. Fails closed if the counter can't be read |
| Cache / paused stores | `search_cache` 24 h cache of live responses; a paused store serves its cache or is skipped with `{"status":"paused","resumes":…}` — never fixtures |
| Photos | JPG/PNG/HEIC ≤ 10 MB, EXIF-rotated, all metadata stripped, 1600 px + 400 px thumb, private `closet-photos/<user_id>/…`, signed URLs |
| Frontend | Next.js 15 + Tailwind 4: P1 Landing, P2 Sign up / Log in (+ forgot/reset, check-email), P3 Profile setup, P4 Home, P5 Results, P6 Closet, P7 Add/Edit item, P8 Item detail, P9 Saved, Profile, `/terms`, `/privacy` (DRAFT banner) |
| Layout | Phone bottom nav, desktop top bar with search; multi-column results, closet sidebar, item detail at 1280 px |
| Deploy prep | `render.yaml`, `frontend/vercel.json` (not deployed) |
| Test account | `scripts/create_test_user.py` (pre-confirmed, login in `.env` only); `scripts/seed_test_closet.py` uploaded the 10 photos through the API |

## Checks run before finishing

| Check | Result |
|---|---|
| Backend unit tests `python -m unittest discover -s tests -t .` | 53 run, all pass (6 integration tests skipped by default) |
| Integration tests vs. Supabase (`FITFINDR_INTEGRATION=1`) | 6/6 pass: photos private, resized, no EXIF; RLS hides rows from anon; saved round-trip; bad upload rejected with reason |
| `run_eval.py --label mvp` (fixtures) | `results/run_2026-10-19_0318_mvp.md` — see below |
| `npm run build` + `eslint` | No errors, no warnings |
| Playwright `npx playwright test` | 18/18 pass (9 flows × 375 px and 1280 px), incl. no horizontal scroll on every page checked |
| Manual click-through as the test account | Landing → log in → Home → search → empty search → Closet → item detail → Add item → Saved → Profile → Profile setup, screenshots at both widths reviewed against the prototype |

Eval, five criteria (5 tries each, cache off, 41 model calls — 1 of the 4 allowed runs):

| # | Criterion | Target | Result |
|---|---|---|---|
| 1 | Matching query completes all three tools | 4/5 | **5/5** |
| 2 | Impossible query stops before `suggest_outfit` | 5/5 | **5/5** |
| 3 | `selected_item` is the item passed to `suggest_outfit` | 5/5 | **5/5** |
| 4 | Fit card names the item, exact price and platform | 4/5 | **5/5** |
| 5 | Empty wardrobe still gets styling advice | 5/5 | **5/5** |
| auto | Buyer voice | all | 20/20 |
| auto | Outfit names ≥ 1 closet item (PRD §8: 4 of 5) | 80% | 15/15 |

## Judgment calls (not spelled out in the PRD/decisions)

1. **Profile size is lenient, typed size is strict.** A size filled in from the
   profile also keeps listings whose store sent no size (all eBay listings),
   ranked after exact matches and labelled "size not listed". Without this,
   eBay vanished from every signed-in search. A size typed in the query
   ("size M") still filters strictly.
2. **Which profile size applies** depends on the search words: waist for
   pants/jeans/skirts, US shoe size for shoes, top size otherwise.
3. **Item matches (P8) use the same no-extra-calls pool as Home picks**
   (fixtures now, ≤ 24 h cache in live mode), so opening a closet item never
   spends quota. The one-line reasons are rule-based, not model-written.
4. **"Fresh finds from each store"** is what new users see on Home; we have no
   popularity data, so it's not labelled "trending".
5. **The keyword chip's ×** leaves the search (back to Home), since a search
   without keywords can't run.
6. **Store filter** on results narrows "More matches"; the best match (the one
   the outfit and fit card were written for) always stays.
7. **Onboarding done** = the profile row was ever updated (Skip also touches
   it), so no schema change was needed.
8. **Fixtures mode shows a small note** on results ("Development mode: recorded
   responses…") so recorded data is never mistaken for a live search.
9. **Styles on Home** show all six cards (prototype showed four).
10. Agent query parser now strips lead-ins like "looking for a …".
