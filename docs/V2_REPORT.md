# v2 build report — 2026-10-19 (branch `v2`)

Built unattended from `CLAUDE.md`, `docs/PRD.md`, `docs/DECISIONS.md` and the
v2 brief. Branch `v2` was created from `mvp`, committed in small steps and
pushed; `main` and `mvp` were not touched, nothing was force-pushed, nothing was
deployed, and no accounts or paid services were created.

> **The overnight run did not finish.** Around 06:15, Claude Code stopped three
> background jobs because the machine ran critically low on memory: the second
> stylist batch run, and the local frontend and backend servers. I did not
> restart them. As a result:
> - **Not run:** the full `run_eval.py` (old + new criteria with judge
>   scores), the full Playwright suite in one pass, and the final click-through
>   of P8 against the improved outfits.
> - **What the database holds:** the outfits from batch run 1 (6 of 30 pieces
>   with a listing). Run 2's 13 live searches are already in `search_cache`
>   until about 06:10 tomorrow (Oct 20), so finishing run 2 costs no RapidAPI
>   calls if done before then.
>
> "Finish tonight's run" below lists the four commands that complete it.

## Finish tonight's run (about 30 minutes, with the machine otherwise idle)

```powershell
cd backend; .venv\Scripts\Activate.ps1; $env:PYTHONUTF8=1
# 1. Rebuild the 10 outfits. Uses the cached live searches; --live-budget 0 means no RapidAPI calls.
$env:FITFINDR_DATA_MODE='live'; python scripts/generate_outfits.py --live-budget 0
#    worked if it ends "wrote results\stylist_eval_….md" and prints the judge average
# 2. The eval, old and new criteria, with LLM-judge scores (about 180 Gemini calls)
$env:FITFINDR_DATA_MODE='fixtures'; python run_eval.py --label v2
#    worked if it prints "criterion 1..7" lines and writes results\run_…_v2.md
# 3. Servers, then Playwright at 375 px and 1280 px (two terminals)
$env:FITFINDR_DATA_MODE='fixtures'; uvicorn api.main:app --port 8000
cd frontend; npm run build; npm run start
cd frontend; npx playwright test        # worked if every test shows ✓; screenshots in frontend\e2e-shots\
```

## What's done

| Item | Status | Where |
|---|---|---|
| **A1** Tool-choosing agent | Done. Gemini function calling over `search_listings`, `relax_search`, `suggest_outfit`, `create_fit_card` and `ask_user`. Code guards refuse out-of-order calls and tell the model why. Auto-relax drops the size first, then raises the budget +50%, once, and says what it dropped. A vague request gets one question. Capped at 8 tool calls; the rules policy is the fallback. | `backend/agent.py` |
| **A2** Judge, traces, CI | Done. LLM judge (`gemini-3.5-flash`, temperature 0) scores outfits on 5 dimensions and the fit card on 3. Every search, stylist and auto-tag run is saved to `traces` (steps, tool calls, latency, tokens, estimated cost), shown on `/dev/traces` (404 in production). A GitHub Actions workflow runs the unit tests plus lint, typecheck and build on every push, with no keys; it passed on GitHub. | `judge.py`, `observe.py`, `.github/workflows/tests.yml` |
| **A3** Photo auto-tagging | Done. Choosing a photo pre-fills name, category, colours, style tags, season and gender, each with an "AI suggested" badge that disappears once you edit that field. Only values from the form's own lists are accepted. | `autotag.py`, `ClosetItemForm.tsx` |
| **A4** Semantic ranking | Done. Gemini embeddings (cached on disk) rerank results after hard drops for category, colour, fabric and gender mismatches. **Bug fixed:** "white denim pants" returned no corduroy or olive items in fixtures or on live data. | `ranking.py`, `attributes.py` |
| **A5** Outfit collage | Done. Your closet photo(s) plus the listing photo(s) on one white board, on P5 and P8. Planned pieces with no listing show as a colour-swatch "To find" tile. | `OutfitCollage.tsx` |
| **B1** Fit card verdict | Done. Outfit text unchanged. The card now shows original retail and era as "AI estimate · high/medium confidence", or "Unknown" when confidence is low. Also: % off computed in code, brand/style value with Classic or Trend-driven, condition as the seller states it, Worth it / Fair deal / Skip with 2–3 reasons, and the caption with a Copy button. | `tools.py::create_fit_card_full`, `BuyerVerdict.tsx` |
| **B2** AI stylist per closet item | Done, outfit quality still improving (see results). A creative-director plan around the item: 2–3 pieces from other categories, with colour, proportion, fabric and occasion notes in your styles (quiet luxury by default). Each piece is matched against real listings, cache first. Hard rules: same category, gender, not kids, inside your budget, has a photo. One verification call keeps a listing only if it truly fits; otherwise the piece shows "Search this". Built automatically on add or edit, saved in `closet_outfits`. In live mode, snapshots older than 24 h are hidden. | `stylist.py`, `StylistOutfit.tsx` |
| **B3** Profile redesign | Done. Grouped cards: Shopping for (test account set to **Women**); sizes per category as multi-select chips (Dresses hidden for Men); optional measurements with an in/cm toggle and a how-to-measure tip; fit; 16 styles; 18 colours in one row on desktop; budget min–max. All of these feed search, ranking and styling. | `ProfileForm.tsx`, migration 0001 |
| **B4** Search filters | Done. Price range, Size, Condition, Colour, Gender, Listed within, Location, Store. Phone: a Filters bottom sheet; desktop: dropdown chips. Pre-filled from the profile. Location is visible but disabled ("Not available for these stores"). | `FilterBar.tsx`, `tools.search_with_status` |
| **C** Ready to deploy | Done. `render.yaml` (production, live data, CORS origins plus an optional preview regex, autoDeploy off), `frontend/vercel.json` (security headers, `/dev/*` redirected away), and the beginner guide `docs/DEPLOY.md`. | |

## Decisions I made (not spelled out in the brief)

1. **Guards around the model's choices.** The model picks each tool, but code
   refuses calls that break the order (styling before a search, a second relax,
   a question about a specific request). Filters the user didn't remove always
   apply, so only `relax_search` can drop one, and it announces it.
2. **What counts as "too vague":** every word is filler, an occasion or a season
   ("something nice", "an outfit for a party"). Any garment, colour, fabric,
   style or brand word means "search".
3. **Fabric counts as a clear mismatch** next to category and colour. The A4
   bug (white denim vs olive corduroy) needs it. "Ivory" counts as white, and
   wool/cashmere/knit don't clash with each other.
4. **Gender comes from words only** (Men's / Women's, plus women's-only types
   such as dress or skirt). Unmarked listings stay in. Stylist searches start
   with "women's" for a women's closet, so live results are mostly women's.
   Kids' items are always dropped.
5. **Sizes from the profile or the Size filter are lenient.** Listings whose
   store states no size (all of eBay) stay in, ranked after matches. A size
   typed in the query ("size M") stays strict, as in the MVP.
6. **The Colour filter matches colours named in the title**, because no store
   sends a colour field. **Listed within** works only on Poshmark, the only
   store with a listing date; when it's on, other stores' items are hidden and
   the UI says so. **Location** has no data at all, so it's disabled.
7. **Test account budget is $10–$40** (the MVP max was $40; I added a $10
   minimum so the cheapest junk, often $1–$5 listings, doesn't fill outfits).
   Sizes were carried over from the MVP profile into the v2 lists.
8. **One live call per outfit on add/edit** (`FITFINDR_STYLIST_LIVE_CALLS=1`)
   in production, to protect the 40/month stop line. Fixtures mode never calls
   live.
9. **A fixtures-mode outfit is never shown in live mode** (`data_mode` column),
   and in live mode a listing snapshot older than 24 h is hidden (CLAUDE.md
   data rule 1).
10. **Verification is one model call per outfit**, choosing among each piece's
    top 5 candidates. After the first live run rejected almost everything, the
    rule became: same garment type, colour family and cut required; fabric
    preferred, not required; loungewear never.
11. **The fit-card verdict comes from the same model call as the caption**
    (one call, not two). Code, not the model, does the % off and the condition
    grade, and drops estimates below medium confidence.
12. **The judge uses a different, stronger model** (`gemini-3.5-flash`) than
    the agent (`gemini-3.5-flash-lite`).
13. **Embeddings never block a request.** The web path and the MCP
    `search_listings` tool fall back to keyword ranking immediately when
    rate-limited (the response says `ranking: keyword`). Batch scripts wait.
14. **Traces store the query text** and are deleted with the user (cascade).
    They're for debugging; the privacy draft should mention them before launch.
15. **Model JSON is read tolerantly** (`generate.loads_json`). Run 1 showed the
    model sometimes adds a stray `}`.

## Migrations applied (Supabase, via `python backend/scripts/migrate.py`)

All four were applied successfully and are recorded in `public.schema_migrations`. RLS is on for every new table.

| File | Change |
|---|---|
| `0001_profile_v2.sql` | profiles: `gender`, `fit`, `measurements` (jsonb), `budget_min` |
| `0002_closet_gender.sql` | closet_items: `gender` |
| `0003_closet_outfits.sql` | new `closet_outfits` (one saved outfit per item), RLS "own rows" |
| `0004_traces.sql` | new `traces`, RLS with no policies (server only) |

## Eval results

**Old (MVP run, `results/run_2026-10-19_0318_mvp.md`):** criteria 1–5 all MET
(5/5, 5/5, 5/5, 5/5, 5/5); buyer voice 20/20; outfit names a closet item 15/15.

**New:** `run_eval.py` now checks all 7 criteria automatically (the old 5 plus
#6 auto-relax and #7 clarifying question) and adds judge scores. **The full
5-try run was not executed** (see the top note). What did run:

| Check | Result |
|---|---|
| Unit tests | **92 run, all pass** (6 integration tests skipped by default), including 39 new offline v2 tests. Same suite green on GitHub Actions. |
| Eval harness, 1 try per scenario, model mocked (no calls) | 7/7 checks pass |
| Live Gemini planner, 3 requests | relax → retry with a fit card; "something nice" → one question; normal path in 4 calls |
| Live end-to-end A1 + A4 (`results/live_e2e_2026-10-19_0605.md`) | 4/4 as expected: guest and test-account "white denim pants" show **no clear mismatches** in 20 results; "…size XXS" relaxes the size once and says so; "something nice" asks a question and does no search |
| Stylist judge, batch run 1 (`results/stylist_eval_2026-10-19_0550.md`) | **average 4.82 / 5** over 10 outfits. Note: only 6 of 30 pieces got a listing, so it mostly grades the plans. The fix for that (decision 10 plus re-search rounds) was in run 2, which was stopped. |
| Playwright | Guest MVP + v2 tests at 375 and 1280 px: **20/20 pass** (after one selector fix). Signed-in v2: profile 2/2, auto-tag 2/2, home + traces 2/2 (after a selector fix; the rerun with the rebuilt app didn't happen). **Not run with v2 code:** the MVP signed-in smoke tests and the P8 outfit test. |
| Frontend build, lint, typecheck | Clean |

## Live calls used tonight

| Service | Used | Limit given |
|---|---|---|
| Fashion Resale API (RapidAPI) | **20** live calls: 5 in stylist run 1, 13 in stylist run 2, 2 in the A1/A4 check. All went through the quota counter (now **28/40** for October) and are cached for 24 h. | 25 |
| Gemini | **187** calls: 127 `flash-lite`, 10 `flash` (judge), 50 embedding requests. Counted in `backend/.cache/gemini_ledger.json`. | ~500 |

## Hand-test checklist

Run the servers in fixtures mode (see "Finish tonight's run", step 3), log in as the test account.

**A1 Agent**
- [ ] Search **something nice** → "One quick question" with suggestions; tap one → results.
- [ ] Search **denim jacket size XXS under $50** → blue notice "Nothing matched in size XXS, so I searched every size." and a best match; the size chip is gone.
- [ ] Search **designer ballgown size XXS under $5** → the notice, then "No matches yet" with **Raise budget to $10**.

**A2 Observability**
- [ ] Open `/dev/traces` → recent runs with planner, tools, model calls, seconds, tokens and $ estimate; expand one to see the steps.
- [ ] GitHub → Actions → "tests" is green for `v2`.

**A3 Auto-tagging**
- [ ] Closet → Add item → choose a photo → "Reading your photo…", then fields filled with **AI suggested** badges; edit the name → its badge goes; save.

**A4 Ranking**
- [ ] Search **white denim pants** → nothing corduroy, olive or a jacket (fixtures may show "No matches" — that's correct; live data shows white denim).

**A5 Collage**
- [ ] Search **flannel shirt** → "How to wear it with your closet" shows a board with the listing and your closet photos.
- [ ] Closet → any item → the outfit board with your photo, the finds and the "To find" tiles.

**B1 Fit card**
- [ ] On any best match: verdict pill, 2–3 reasons, Original retail ("AI estimate · … confidence" or "Unknown"), Era, Value, Condition ("as the seller states" / "Not stated"), caption + **Copy caption**.

**B2 Stylist**
- [ ] Closet → each of the 10 items → "Finds that go with this": title, concept, palette, occasion, notes, 2–3 pieces from other categories; each either a real listing (View on …) or "Search this".
- [ ] Edit an item's colour → back on the item, "Styling your piece…" then a new outfit.
- [ ] No men's or kids' items anywhere.

**B3 Profile**
- [ ] Profile → cards: Shopping for (Women), sizes per category (Dresses disappear for Men), measurements with in/cm and "How to measure", fit, 16 styles, colours in one row on desktop, budget $10–$40 → Save.

**B4 Filters**
- [ ] Home → filters show "Price: $10–$40" and "Gender: Women's" (pre-filled).
- [ ] Results → desktop chips / phone "Filters" sheet; Store = Depop → only Depop; Condition = New with tags; Location disabled with "Not available for these stores".

**C Deploy**
- [ ] Read `docs/DEPLOY.md`; check `render.yaml` and `frontend/vercel.json`. Nothing is deployed yet.

**Both widths:** try each page at 375 px (DevTools phone view) and 1280 px; there should be no sideways scrolling.
