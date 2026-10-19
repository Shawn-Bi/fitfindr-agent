# Blockers and open items — MVP build, 2026-10-19

Things I couldn't finish or that need the owner. Nothing here blocks local use.

1. **`.env.example` not updated.** My permissions don't allow reading `.env*`
   files, so I couldn't edit it safely. Please add these names (empty values):
   `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`, `FRONTEND_ORIGINS`, and for
   `frontend/.env.local`: `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`.
   Also: `.env` contains an `EBAY_API_HOST` that nothing uses any more (eBay
   comes through the Fashion Resale API) — safe to delete.

2. **Supabase redirect URLs.** Verification and password-reset emails link to
   `/onboarding` and `/reset-password`. Add `http://localhost:3000/**` (and the
   Vercel URL later) under Supabase → Authentication → URL Configuration →
   Redirect URLs, or Supabase falls back to the Site URL.

3. **Real sign-up and email verification were not clicked through.** Email
   verification blocks brand-new accounts, so tests use the pre-confirmed test
   account. The sign-up form, validation and the `signUp` call are in place;
   please try one real sign-up yourself.

4. **"No longer available" on Saved can't trigger yet.** The Fashion Resale API
   sends no sold/status field (checked in all fixtures), so there is no signal
   that an item is gone. The `available` column and the greyed-out UI are ready;
   the trigger needs a status field from an API.

5. **Etsy and FB Marketplace** stay "Coming soon" (DECISIONS.md #4) until request
   examples and call permission exist.

6. **npm audit** reports 7 advisories (1 moderate, 6 high) in build tooling pulled
   by `create-next-app@15` (`braces`, a nested `postcss`). Not in shipped browser
   code; `npm audit fix --force` would jump major versions, so I left it.

7. **Rate limit and token cache are in memory** (per backend process). Fine for
   one Render instance; several instances would need a shared store.
