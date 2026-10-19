# Blockers and open items — MVP build, 2026-10-19

Things I couldn't finish or that need the owner. Nothing here blocks local use.

1. **Real sign-up and email verification were not clicked through.** Email
   verification blocks brand-new accounts, so tests use the pre-confirmed test
   account. The sign-up form, validation and the `signUp` call are in place;
   please try one real sign-up yourself.

2. **"No longer available" on Saved can't trigger yet.** The Fashion Resale API
   sends no sold/status field (checked in all fixtures), so there is no signal
   that an item is gone. The `available` column and the greyed-out UI are ready;
   the trigger needs a status field from an API.

3. **Etsy and FB Marketplace** stay "Coming soon" (DECISIONS.md #4) until request
   examples and call permission exist.

4. **npm audit** reports 7 advisories (1 moderate, 6 high) in build tooling pulled
   by `create-next-app@15` (`braces`, a nested `postcss`). Not in shipped browser
   code; `npm audit fix --force` would jump major versions, so I left it.

5. **Rate limit and token cache are in memory** (per backend process). Fine for
   one Render instance; several instances would need a shared store.
