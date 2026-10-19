# v2 build report — 2026-10-19 (branch `v2`)

Built unattended from `CLAUDE.md`, `docs/PRD.md`, `docs/DECISIONS.md` and the
v2 brief. Branch `v2` was created from `mvp`, committed in small steps and
pushed; `main` and `mvp` were not touched, nothing was force-pushed, nothing was
deployed, and no accounts or paid services were created.

> **Finished the morning after (Oct 19, 09:15–09:55)**, one step at a time.
> The overnight run had been stopped around 06:15 because the machine ran
> low on memory. All three steps of "Finish tonight's run" have now run:
> - **Outfits rebuilt** from the cached searches with no RapidAPI calls:
>   **21 of 30 pieces now show a real listing** (run 1: 6 of 30), and every
>   outfit has at least one (`results/stylist_eval_2026-10-19_0929.md`).
> - **`run_eval.py --label v2`: all 7 criteria MET (5/5 each)**
>   (`results/run_2026-10-19_0942_v2.md`).
> - **Playwright: 34/34 pass** at 375 px and 1280 px, including the signed-in
>   MVP smoke tests and the P8 stylist-outfit test.
>
> **Not finished: judge scores.** The judge model's free tier allows only 20
> requests a day, and they were used up. The eval has judge scores for 4 of
> 25 tries, and the new outfits have none. To finish after the quota resets
> (midnight Pacific time):
> `$env:FITFINDR_DATA_MODE='live'; python scripts/generate_outfits.py --live-budget 0`
> (works with no RapidAPI calls only while the cached searches are under
> 24 h old, until about 06:10 Oct 20). After that the same command without
> `--live-budget` still re-scores, but on fewer listings.

### Fixed while finishing

1. **The stylist's pick step lost good matches.** The model sometimes answers
   with a bare list `[{"piece": 0, …}]` instead of `{"choices": […]}`. The code
   failed on that, caught the error silently and showed "Search this" for
   every piece of the outfit. That's why the denim-jacket outfit went from
   3/3 to 0/3 between two identical runs. `stylist.pick_listings` now accepts
   both shapes (test added). Result: 12/30 → 21/30 pieces with a listing.
2. **A daily quota was retried as if it were per-minute.** When the free-tier
   embedding quota (1,000 a day) ran out, every search waited 5 × 65 s
   before falling back to keyword ranking, which would have taken more than
   2 hours. `generate._request` now gives up at once on a `PerDay` quota
   (test added). Search and the stylist fall back to keyword ranking
   immediately, as they already did for other errors.
3. **`generate_outfits.py` crashed when the judge was unavailable**, after the
   outfits had already been saved. It now writes the report without scores
   and says why, as `run_eval.py` already did.

## What's done

| Item | Status | Where |
|---|---|---|
| **A1** Tool-choosing agent | Done. Gemini function calling over `search_listings`, `relax_search`, `suggest_outfit`, `create_fit_card` and `ask_user`. Code guards refuse out-of-order calls and tell the model why. Auto-relax drops the size first, then raises the budget +50%, once, and says what it dropped. A vague request gets one question. Capped at 8 tool calls; the rules policy is the fallback. | `backend/agent.py` |
| **A2** Judge, traces, CI | Done. LLM judge (`gemini-3.5-flash`, temperature 0) scores outfits on 5 dimensions and the fit card on 3. Every search, stylist and auto-tag run is saved to `traces` (steps, tool calls, latency, tokens, estimated cost), shown on `/dev/traces` (404 in production). A GitHub Actions workflow runs the unit tests plus lint, typecheck and build on every push, with no keys; it passed on GitHub. | `judge.py`, `observe.py`, `.github/workflows/tests.yml` |
| **A3** Photo auto-tagging | Done. Choosing a photo pre-fills name, category, colours, style tags, season and gender, each with an "AI suggested" badge that disappears once you edit that field. Only values from the form's own lists are accepted. | `autotag.py`, `ClosetItemForm.tsx` |
| **A4** Semantic ranking | Done. Gemini embeddings (cached on disk) rerank results after hard drops for category, colour, fabric and gender mismatches. **Bug fixed:** "white denim pants" returned no corduroy or olive items in fixtures or on live data. | `ranking.py`, `attributes.py` |
| **A5** Outfit collage | Done. Your closet photo(s) plus the listing photo(s) on one white board, on P5 and P8. Planned pieces with no listing show as a colour-swatch "To find" tile. | `OutfitCollage.tsx` |
| **B1** Fit card verdict | Done. Outfit text unchanged. The card now shows original retail and era as "AI estimate · high/medium confidence", or "Unknown" when confidence is low. Also: % off computed in code, brand/style value with Classic or Trend-driven, condition as the seller states it, Worth it / Fair deal / Skip with 2–3 reasons, and the caption with a Copy button. | `tools.py::create_fit_card_full`, `BuyerVerdict.tsx` |
| **B2** AI stylist per closet item | Done. 21 of 30 pieces show a real listing after the morning fixes. A creative-director plan around the item: 2–3 pieces from other categories, with colour, proportion, fabric and occasion notes in your styles (quiet luxury by default). Each piece is matched against real listings, cache first. Hard rules: same category, gender, not kids, inside your budget, has a photo. One verification call keeps a listing only if it truly fits; otherwise the piece shows "Search this". Built automatically on add or edit, saved in `closet_outfits`. In live mode, snapshots older than 24 h are hidden. | `stylist.py`, `StylistOutfit.tsx` |
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

**New (`results/run_2026-10-19_0942_v2.md`, 5 tries per scenario, fixtures):**
criteria 1–7 all MET (5/5 each, including #6 auto-relax and #7 clarifying
question); buyer voice 25/25 fit cards; outfit names a closet item 20/20.
Judge scores for only **4 of 25 tries** (daily judge quota ran out): outfit
4.25 (style_match 1.75, gender 5.0, colour 4.75, proportion 4.75, completeness
5.0), fit card 5.0 on all three. With 4 tries, style_match is too thin a sample
to act on. It's the first thing to check when the full judge run happens. 149 model
calls (145 flash-lite, 4 flash).

| Check | Result |
|---|---|
| Unit tests | **93 run, all pass** (6 integration tests skipped by default), including 40 offline v2 tests (2 new checks added this morning). Same suite green on GitHub Actions. |
| Eval harness, 1 try per scenario, model mocked (no calls) | 7/7 checks pass |
| Live Gemini planner, 3 requests | relax → retry with a fit card; "something nice" → one question; normal path in 4 calls |
| Live end-to-end A1 + A4 (`results/live_e2e_2026-10-19_0605.md`) | 4/4 as expected: guest and test-account "white denim pants" show **no clear mismatches** in 20 results; "…size XXS" relaxes the size once and says so; "something nice" asks a question and does no search |
| Stylist judge, batch run 1 (`results/stylist_eval_2026-10-19_0550.md`) | **average 4.82 / 5** over 10 outfits. Note: only 6 of 30 pieces got a listing, so it mostly grades the plans. |
| Stylist rebuild (`results/stylist_eval_2026-10-19_0929.md`) | **21 of 30 pieces with a real listing**, every outfit at least 1; three are 3/3 (lilac blouse, denim jacket, camel jacket). 0 RapidAPI calls, 10 flash-lite calls. **No judge scores** (daily quota). The same cream trousers and Everlane loafers appear in three outfits, because the cached pool is small. |
| Playwright (rebuilt app, fixtures API) | **34/34 pass** in one run (5.7 min), 17 tests × 375 px and 1280 px: guest MVP, signed-in MVP smoke (home/closet/item/saved/profile, search with own closet, add + delete item), guest v2 (A1, B1/A5, B4), signed-in v2 (B3, **P8 stylist outfit + collage**, A3, B4/A2). |
| Frontend build, lint, typecheck | Clean |

## Live calls used tonight

| Service | Used | Limit given |
|---|---|---|
| Fashion Resale API (RapidAPI) | **20** live calls: 5 in stylist run 1, 13 in stylist run 2, 2 in the A1/A4 check. All went through the quota counter (now **28/40** for October) and are cached for 24 h. **0** more this morning. | 25 |
| Gemini | **187** overnight: 127 `flash-lite`, 10 `flash` (judge), 50 embedding requests. This morning about 250 more (mostly the eval's 145 flash-lite, plus the outfit rebuilds and debugging). Ledger for Oct 19: 373 flash-lite, 15 flash, 52 embedding. Counted in `backend/.cache/gemini_ledger.json`. | ~500 |

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
