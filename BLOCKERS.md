# Blockers and open items — updated 2026-10-20 (after the first deploy)

Things I couldn't finish or that need the owner. Nothing here blocks local use.
Full v2 details: `docs/V2_REPORT.md`.

1. **Real sign-up and email verification were not clicked through.** Email
   verification blocks brand-new accounts, so tests use the pre-confirmed test
   account. Please try one real sign-up yourself (also after deploying —
   `docs/DEPLOY.md` step 5).

2. **"No longer available" on Saved can't trigger yet.** The Fashion Resale API
   sends no sold/status field, so there is no signal that an item is gone.

3. **Facebook Marketplace is not connected: the RapidAPI host isn't subscribed.**
   Etsy is now live. For FB Marketplace one probe call (`GET /`, counted: 1/40
   for October) answered **HTTP 403 "You are not subscribed to this API."**;
   **retried 2026-10-20 05:05 UTC: same 403** (2/40). And
   the listing's endpoint docs aren't public, so there was nothing to record a
   fixture from. The store stays "Coming soon"; the profile's ZIP/city field and
   the Location filter (FB only, disabled for now) are ready. What you need to do:
   1. Sign in at rapidapi.com with the account whose key is `RAPIDAPI_KEY` in `.env`.
   2. Open the API whose host is `facebook-marketplace-api.p.rapidapi.com`
      (search RapidAPI for "Facebook Marketplace API"; the host is shown in its
      code snippets) → **Pricing** → subscribe to the free **Basic** plan.
   3. Note the search endpoint's path and its location parameter (ZIP, city or
      lat/long) from the Endpoints tab, and tell me; or paste one example
      response into `backend/tests/fixtures/fb_<query>.json`.
   4. Then one recording call, `sources/fb_marketplace.py` `parse`/`fetch`,
      `ENABLED = True`, and the Location filter switches on
      (`FILTER_SUPPORT["location"]`). Nothing else in the app changes.

4. **Location filter is disabled** ("Location is for Facebook Marketplace, which
   isn't connected yet"): no other store sends a location. **"Listed within"**
   works only on Poshmark listings (the only store that sends a listing date) and
   says so. Etsy search results state no size, condition or listing date either.

5. **Gemini free-tier limits.** Embeddings hit the per-minute limit under load
   and a **1,000-a-day** limit; the judge model allows only **20 requests a
   day**. Both ran out on Oct 19. When embeddings are out, search and the
   stylist rank by keywords right away (the response says `ranking: keyword`);
   nothing fails. A paid tier, or embedding listings ahead of time, would make
   semantic ranking consistent. The eval now grades each scenario's 5 tries in
   one judge call (5 calls a run, not 25), so it fits the free tier.
   The fallback model (`gemini-3-flash`) allows only **20 requests a day**, so
   it can't stand in for the main model for long: when both are out, the fit
   card's caption is written in code from the listing (no verdict) and the
   outfit stays. The production API ran out of `gemini-3.5-flash-lite` quota on
   the night of Oct 19 (seen in the Render logs). The free tier is shared by
   everyone using the site; a paid key is the real fix.

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

10. **AI preview pictures need a paid Gemini tier.** All three image models on
   this key (`gemini-2.5-flash-image`, `gemini-3.1-flash-image`,
   `gemini-3.1-flash-lite-image`) answered HTTP 429 with no free quota. The code is
   in place (`backend/previews.py`, stored once per piece in Supabase Storage);
   until then a planned piece with no listing in its colour shows the closest
   real listing photo in the same category, labelled "Closest find · Similar
   piece in a different colour". Enabling billing on the Gemini key turns
   previews on with no code change.

11. **October RapidAPI quota: Fashion Resale is used up.** On Oct 20 the
   counts are Fashion Resale **40/40 (paused until Nov 1: no Depop, Poshmark,
   Mercari or eBay results for new searches)**, Etsy 8/40, FB Marketplace 2/40.
   Repeat searches are free for 24 h; Etsy keeps working for new searches. One Etsy call during this session leaked
   from a unit test before Etsy was mocked there; it is counted in `api_usage`
   and the tests can no longer reach RapidAPI at all.
