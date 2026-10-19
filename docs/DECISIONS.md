# FitFindr MVP — build decisions

Decided 2026-10-19 by the project owner, before the unattended MVP build.
Every question was answered "default". Read this together with `CLAUDE.md`
(rules) and `docs/PRD.md` (scope). If they disagree, CLAUDE.md wins on rules,
and this file wins on the build choices listed here.

## How the work runs

1. **Branch** — All work goes on the `mvp` branch. Never touch `main`; the owner merges.
2. **Order** — Backend API → frontend pages P1–P9 → tests and acceptance checks → summary report.
3. **Live RapidAPI calls overnight** — None. Everything runs on fixtures (`FITFINDR_DATA_MODE=fixtures`).
4. **Etsy and FB Marketplace** — Not connected yet (no request examples, no call permission). The results page shows them as "Coming soon", never with fake listings; the stores bar reads "4 stores live".
5. **Deploy** — No deploy to Vercel or Render. Only prepare the config files (`vercel.json`, `render.yaml`).
6. **When blocked** — Write it in `BLOCKERS.md`, skip it, keep going.
7. **Gemini budget** — At most 4 `run_eval.py` runs overnight (about 160 model calls).

## Accounts and data

8. **Email verification** — Required before login (Supabase default).
9. **Test account** — Create one test user with the service-role key for automated tests. Store its login in `.env` as `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` (never printed or committed).
10. **Closet photos** — Upload the 10 photos in `backend/tests/closet_photos/` to the test account's private `closet-photos` bucket only, for upload tests.
11. **HEIC and image sizes** — Convert HEIC to JPEG on the server (`pillow-heif`). Main image 1600 px, thumbnail 400 px. Strip GPS and other metadata.
12. **Account deletion** — Immediate hard delete: auth user, all rows, all photos.
13. **Data access** — The frontend uses Supabase only for auth. All data goes through FastAPI using the user's own access token, so row-level security applies. The service-role key is used only for `api_usage` and `search_cache`.
14. **Quota counter** — Move from the local `backend/.quota.json` to the Supabase `api_usage` table (`increment_api_usage` RPC).

## Search and the agent

15. **Profile filters** — The profile's size and budget are applied to every search automatically, shown as removable "from profile" chips (as in the prototype).
16. **Re-search and cache** — Removing a chip searches again. Identical searches within 24 h are served from `search_cache`.
17. **Empty results** — Show what was searched and offer one-click relax buttons: remove size; raise budget by 50%, rounded up to the next $5. No model call when nothing matches.
18. **Style cards** — Vintage / Y2K / Streetwear / Minimalist / Grunge / Cottagecore: clicking one searches that style word plus the profile filters.
19. **"Picked for your closet" (Home)** — Built only from searches already cached in the last 24 h; never triggers extra live calls. New users see "Add items to unlock".
20. **Outfit suggestions** — `suggest_outfit` returns structured output (text plus the closet item ids it used) so the UI can show those items' thumbnails. Update the eval to match.
21. **Search path** — The API calls `search_listings` directly (no MCP subprocess per request). `search_listings` stays registered in `mcp_server.py` for the agent and the eval.
22. **Rate limit** — 10 searches per minute per user (per IP for guests).
23. **Guest search** — Allowed from the Landing page, with generic styling advice and a "sign up to style with your own closet" prompt.
24. **Saved items** — Store a snapshot of the listing (`saved_items.listing`) when saved. No automatic availability checks (to save quota). Show "Saved on <date> · price may have changed". Mark "No longer available" only when a later search shows the item is gone.

## Interface

25. **Stack** — Next.js (App Router) + TypeScript + Tailwind CSS. Fonts: Space Grotesk (headings), DM Sans (body).
26. **Pages without a prototype screen** (desktop Home, Saved, Add item, Item detail, Landing) — Adapt the phone design into a multi-column desktop layout using the same tokens.
27. **Shoe sizes** — US only. (The PRD mentions US/EU/UK; CLAUDE.md says US-only users and US sizes.)
28. **Not built** — Camera button and image search show a "Coming soon" popup. AI pre-filling item details from a photo is phase 2.
29. **Legal pages** — Render `docs/legal/terms.md` and `privacy.md` at `/terms` and `/privacy` with a DRAFT banner. Placeholders such as `[CONTACT EMAIL]` stay as they are.
30. **E2E tests** — Playwright smoke tests at 375 px and 1280 px (one-time `npx playwright install`).

## Facts already established (2026-10-19)

- eBay comes through the Fashion Resale API (`RESALE_API_HOST`, `platforms=depop,poshmark,mercari,ebay`); there is no separate eBay host or quota.
- The Fashion Resale API accepts only `sort=price` or `sort=relevance`. `relevance` (the default) returns one store per page, so FitFindr searches with `sort=price`, then alternates stores within equal keyword scores.
- Fashion Resale calls used in October 2026: 8 of 40 (stop line).
- Kids' items are filtered unless the query asks for kids; fit cards are written in the buyer's voice (checked by `run_eval.py`).
