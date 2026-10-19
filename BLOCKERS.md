# Blockers and open items — updated for v2, 2026-10-19

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

5. **Gemini embeddings hit the free-tier per-minute limit** under load. Search
   and the stylist then rank by keywords for that request (the response says
   `ranking: keyword`); nothing fails. A paid tier, or embedding listings ahead
   of time, would make semantic ranking consistent.

6. **Free Render plan sleeps after 15 minutes.** A closet-item outfit that is
   still being built when the server sleeps is lost; the page shows "Style this
   piece" and the user can press it again.

7. **Rate limit and token cache are in memory** (per backend process). Fine for
   one Render instance.

8. **npm audit** advisories in build tooling from `create-next-app@15` (not in
   shipped browser code); `npm audit fix --force` would jump major versions.
