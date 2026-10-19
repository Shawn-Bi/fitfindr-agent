# Blockers and open items — updated for v2, 2026-10-19 (morning)

Things I couldn't finish or that need the owner. Nothing here blocks local use.
Full v2 details: `docs/V2_REPORT.md`.

1. **Real sign-up and email verification were not clicked through.** Email
   verification blocks brand-new accounts, so tests use the pre-confirmed test
   account. Please try one real sign-up yourself (also after deploying —
   `docs/DEPLOY.md` step 5).

2. **"No longer available" on Saved can't trigger yet.** The Fashion Resale API
   sends no sold/status field, so there is no signal that an item is gone.

3. **Etsy and FB Marketplace** stay "Coming soon" (no request examples, no call
   permission yet).

4. **Location filter is disabled** ("Not available for these stores"): no store
   in the Fashion Resale API sends a location. **"Listed within"** works only on
   Poshmark listings (the only store that sends a listing date) and says so.

5. **Gemini free-tier limits.** Embeddings hit the per-minute limit under load
   and a **1,000-a-day** limit; the judge model allows only **20 requests a
   day**. Both ran out on Oct 19. When embeddings are out, search and the
   stylist rank by keywords right away (the response says `ranking: keyword`);
   nothing fails. A paid tier, or embedding listings ahead of time, would make
   semantic ranking consistent, and a full 5-try judged eval (about 35 judge
   calls) needs a paid tier or two days.

6. **Free Render plan sleeps after 15 minutes.** A closet-item outfit that is
   still being built when the server sleeps is lost; the page shows "Style this
   piece" and the user can press it again.

7. **Rate limit and token cache are in memory** (per backend process). Fine for
   one Render instance.

8. **npm audit** advisories in build tooling from `create-next-app@15` (not in
   shipped browser code); `npm audit fix --force` would jump major versions.

9. **Judge scores still to collect** (needs the judge quota, which resets at
   midnight Pacific time): the v2 eval has scores for 4 of 25 tries, and the rebuilt stylist
   outfits (21/30 pieces with a listing) have none. Commands are at the top of
   `docs/V2_REPORT.md`. Re-score the outfits before about 06:10 Oct 20, while
   the cached searches are still under 24 h old, so it needs no RapidAPI calls.
