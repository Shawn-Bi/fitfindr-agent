# FitFindr — project rules for Claude Code

FitFindr is a secondhand-clothing search agent for **US users only** (US sizes, USD).
A user types what they want ("vintage graphic tee under $30"); the agent searches six
US resale stores, picks the best match, explains how to wear it with clothes from the
user's own closet, and writes a short caption.

Source of truth for scope: `docs/PRD.md` (FitFindr MVP PRD v2.2). Visual reference:
`docs/prototype/*.dc.html` (the approved prototype screens as HTML; copy their layout,
copy and colors, ignore the `<x-dc>` / `DCLogic` wrapper). If the PRD and this file disagree, ask the user.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS, one responsive codebase (phone + desktop) |
| Backend | FastAPI (Python), wraps the existing agent (`agent.py::run_agent`) |
| Database / auth / photo storage | Supabase (Postgres, Auth, Storage) |
| LLM | Gemini via the existing `generate()` adapter |
| Deploy | Vercel (frontend), Render (backend) |

## Folder layout

```
FitFindr-Agent/        # the project folder, GitHub repo fitfindr-agent (private)
  CLAUDE.md
  docs/PRD.md, docs/prototype/*.dc.html, docs/legal/terms.md, docs/legal/privacy.md
  backend/
    agent.py, tools.py, mcp_server.py, mcp_client.py, config.py, trace.py
    sources/            # one adapter per RapidAPI host
      resale.py  etsy.py  fb_marketplace.py  normalize.py  quota.py   # resale = Depop, Poshmark, Mercari, eBay
    api/main.py         # FastAPI routes from PRD section 7
    run_eval.py, scenarios.py, criteria.md
    tests/fixtures/     # recorded real API responses, dev/test only
  frontend/             # Next.js app
  public/logo.svg, public/favicon.svg
  supabase/schema.sql
  .env.example
```

## Data rules (most important)

1. **The product never shows mock, sample or invented listings.** Every listing a user
   sees comes from a live API call or a cached copy of a real response (≤ 24 h old).
2. `tests/fixtures/` holds **recorded real responses** for unit tests, the eval and
   Playwright. Load them only when `FITFINDR_DATA_MODE=fixtures`. Local development
   runs `FITFINDR_DATA_MODE=live` with the 24 h cache (run commands in `README.md`).
   If `APP_ENV=production` and the mode is `fixtures`, the backend must refuse to start.
3. **Never make a live RapidAPI call without asking the user first** in the chat, and
   say which host and how many calls. Log every live call (host, time, status).
4. Free quotas are tiny. Track calls per host per calendar month in Supabase table
   `api_usage` (reset on the 1st):

| Store(s) | Env var for host | Monthly quota | Stop at |
|---|---|---|---|
| Depop, Poshmark, Mercari, eBay | `RESALE_API_HOST` | 50 | 40 |
| Etsy | `ETSY_API_HOST` | 50 | 40 |
| Facebook Marketplace | `FB_MARKETPLACE_HOST` | 50 (hard) | 40 |

   eBay comes through the Fashion Resale API (`platforms=...,ebay`); there is no
   separate eBay host or quota. Call it with `sort=price` (only `price` and
   `relevance` exist; `relevance` returns one store per page).

5. At the stop line, that store is **paused**: serve its ≤ 24 h cache if one exists,
   otherwise skip it and tell the UI `{"platform": "ebay", "status": "paused",
   "resumes": "2026-11-01"}`. Never fill the gap with fixtures in production.
6. Live-call priority: Fashion Resale API first (4 stores per call). Wire up Etsy
   and FB Marketplace last, in one integration pass.
7. Every adapter returns the FitFindr standard listing dict:
   `id, title, price (float, USD), size, platform, url, image_url` plus optional
   `condition, updated_at, category` (the store's own category label, used to
   filter out kids' items). Missing values are `None`, never invented.
   `search_listings()` keeps its old signature and still returns `[]` when nothing
   matches; it stays registered in `mcp_server.py`.

## Secrets

- Keys live only in `.env` (git-ignored). `.env.example` lists names with empty values.
- Never print a key, put one in code, a commit, a log line or a screenshot.
- Env vars: `GEMINI_API_KEY`, `RAPIDAPI_KEY`, `ETSY_API_HOST`,
  `RESALE_API_HOST`, `FB_MARKETPLACE_HOST`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, `FITFINDR_DATA_MODE`, `APP_ENV`.

## The user's machine

- Windows + PowerShell + VS Code. Explain each command in one line: what it does and how to tell it worked.
- Before Python commands in a new terminal: `$env:PYTHONUTF8=1`.
- In PowerShell, quote queries containing `$` with single quotes.
- Activate the venv with `.venv\Scripts\Activate.ps1`.

## Quality bar

- After any change to the agent or tools, run `python run_eval.py --label <name>`
  in fixtures mode and report the five criteria.
- Phone width 375 px: no horizontal scroll. Desktop 1280 px: multi-column.
- Real `<button>`, `<a>`, `<label>`; touch targets ≥ 44 px; text contrast ≥ 4.5:1.
- Commit in small steps with clear messages.

## Design tokens (match the prototype)

- Primary `#0369A1`, hover `#075985`, logo accent `#0284C7`, light accent `#7DD3FC`, tint `#DCEFFB`
- Logo: a tilted price tag with "FF" inside (`public/logo.svg`, `public/favicon.svg`)
- Background `#F2F8FC`, surface `#FFFFFF`, ink `#1B1E1C`, muted text `#4F5551`
- Fonts: Space Grotesk (headings), DM Sans (body)
- Phone: bottom nav Home · Closet · Saved · Profile. Desktop: same items in a top bar.
