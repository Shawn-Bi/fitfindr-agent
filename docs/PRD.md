# FitFindr MVP PRD v2.2

Oct 18, 2026 · @Shawn Bi

FitFindr is a secondhand-clothing search agent for US users. A user describes what they want in one sentence, or starts from their own closet, finds a suitable secondhand piece, and sees how to wear it with clothes they already own. This version merges the three earlier PRDs (sign-up, home, my closet) into one and narrows the scope to an MVP that one person can finish in a few weeks.

## 1. MVP scope

The MVP covers only the "buy" side: search secondhand items, manage your own closet, see outfit suggestions, and save items. Selling and social features are two separate products and come in later phases.

| Feature | MVP | Notes |
| --- | --- | --- |
| Email sign-up, log-in, forgot password | Yes | Use a proven auth service; never store passwords ourselves |
| Size and style profile | Yes | Everything can be skipped |
| Text search + results page | Yes | Real listings from 6 platforms (RapidAPI) |
| Style-card filters | Yes | Vintage, Y2K, Streetwear, etc. |
| My closet: upload a photo + fill in item details | Yes | Create, read, update, delete; photos are required |
| Item detail + AI outfit suggestion | Yes | This is the existing suggest\_outfit |
| Saved items | Yes | Saved inside the site |
| Every recommendation shows a listing photo | Yes | Use the photo returned by each platform's API |
| Image search (upload a reference photo to find similar items) | Placeholder | Shows "Coming soon" |
| Sell items, cross-post to several platforms, AI pricing | No | Most platforms have no posting API |
| Local (same city) | No | Facebook Marketplace items appear in search results first; filtering by city is phase 2 |
| Friends' closets, follows, messages | No | Social features, phase 3 |
| Email/SMS notifications, scheduled recommendations | No | Phase 2 |

## 2. Page list and core flow

The site UI is English only (the target users are in the US) with a sky-blue theme. One responsive codebase supports both phone and desktop: on phones a bottom navigation and one column; on desktop a top navigation and multiple columns. Logged-out visitors see the Landing page; logged-in users see Home. After login the bottom navigation has 4 entries: Home · Closet · Saved · Profile; on desktop they sit in the top bar.

| ID | Page | Who can see it | Purpose |
| --- | --- | --- | --- |
| P1 | Landing | Logged out | Introduce the product; lead to sign-up or a trial search |
| P2 | Sign up / Log in | Logged out | Email + password, terms consent |
| P3 | Profile setup | New users | Sizes, styles, budget; all skippable |
| P4 | Home | Logged in | Search box, style cards, picks for you |
| P5 | Search results | Everyone | Listing cards + outfit suggestion + caption |
| P6 | My Closet | Logged in | Browse your own clothes by category |
| P7 | Add item | Logged in | Upload a photo + fill in item details |
| P8 | Closet item detail | Logged in | This item + secondhand listings that go with it |
| P9 | Saved | Logged in | Saved listings |

Main flow for a new user:

1. Landing → Get Started
2. Sign up (email + password + agree to terms) → email verification
3. Profile setup (skippable)
4. My Closet empty state → Add your first item → upload a photo + fill in details → save
5. Home → type "vintage graphic tee under $30" → Search results
6. The result card shows an outfit suggestion built from the user's own closet → save it, or jump to the original platform to buy

Guests can try a search on Landing; the results page then uses a generic outfit suggestion and prompts "Sign up to get outfits from your own closet."

## 3. Requirements by page

### P1 Landing

- Top bar: FitFindr logo · How it works · Log in · Get started
- Headline: Find pieces that fit your wardrobe, not just your search.
- Subtitle: Secondhand finds from supported stores, matched to your style, size and budget.
- A trial search box (example: vintage graphic tee under $30) + a Get started button
- Three steps: Add your closet → Search in plain words → Get matches that go with what you own
- Data-source bar: Searching eBay · Etsy · Depop · Poshmark · Mercari · FB Marketplace

### P2 Sign up / Log in

- Required: Email, Password (at least 12 characters, show/hide, password-manager friendly)
- Required checkbox: I agree to the Terms of Service and the Privacy Policy (both links open)
- Optional, off by default: Email me new matches (the MVP only records the choice and sends nothing)
- Log-in page: Email + Password + Forgot password; error messages say clearly what is wrong

### P3 Profile setup (everything skippable)

- Usual sizes: tops, bottoms (waist/length), shoes (US/EU/UK)
- Preferred styles (multi-select cards), preferred colors, per-item budget cap
- One sentence per field explaining what it is used for; buttons: Skip for now / Save & continue
- Do not collect height, weight or body measurements (the MVP has no use for them)

### P4 Home

- Row 1: Logo · search box · camera button (opens Coming soon)
- Row 2: Style cards in a horizontal scroll: Vintage · Y2K · Streetwear · Minimalist · Grunge · Cottagecore
- Row 3: Picked for your closet (recommended from the closet and preferences); new users see "Add clothes to unlock" plus popular items from each platform
- Data-source bar: the 6 platform names; a platform whose quota has run out is marked Paused

### P5 Search results

- Top: the conditions the agent understood, as tags: graphic tee · under $30 · size M, each removable with ×
- Listing grid: photo, title, price, size, condition, platform, save heart
- The first (best match) listing is expanded: How to wear it with your closet (with thumbnails of the user's own clothes used) + Fit card caption (copyable)
- When nothing is found: say which conditions were searched and offer a one-tap relax button (drop the size / raise the budget)
- Each listing shows its update time and "Price and stock may change on the original site"; filter by platform; paused platforms show their resume date

### P6 My Closet

- Top: total item count · search · + Add item
- Category tabs: All · Tops · Bottoms · Outerwear · Dresses · Shoes · Accessories, with counts
- Photo grid; empty state: Your closet starts here + Add your first item

### P7 Add item

- Upload the photo first (take a photo or pick from the album); preview, retake and delete are available
- Then fill in the details (fields in section 4); in phase 2 AI pre-fills them from the photo and the user confirms
- Button: Save to closet

### P8 Closet item detail

- Large photo + item details + Edit / Delete
- Finds that go with this: horizontal listing cards (photo, price, platform, a one-line reason for the match)

### P9 Saved

- Grid of saved listings; a listing that has been taken down turns gray and is labeled No longer available

## 4. Closet data and photo upload

Photos and item details are both required features: the more complete the information, the better the agent's outfits. Categories are aligned with the listing data: cosmetics were removed, and outerwear and dresses were added.

| Field | Required | Input | Example |
| --- | --- | --- | --- |
| photo | Yes | Take or upload, JPG/PNG/HEIC, ≤ 10 MB | — |
| name | Yes | Text | Baggy straight-leg jeans |
| category | Yes | Single choice | tops / bottoms / outerwear / dresses / shoes / accessories |
| colors | Yes | Multi-select swatches | dark blue, indigo |
| style\_tags | No | Multi-select cards | denim, streetwear, baggy |
| size | No | Text | W30 L32 |
| brand | No | Text | Levi's |
| season | No | Multi-select | spring, fall |
| notes | No | Text | High-waisted, sits above the hip |

Upload rules: the server checks format and size, strips metadata such as GPS from the photo, compresses it to 1600 px and creates a thumbnail; a failed upload must say why and allow a retry. Photos and the closet are visible only to their owner by default.

## 5. Agent and data sources

All listings come from real data on US secondhand platforms reached through RapidAPI; mock data never appears in the product UI.

| Platform | RapidAPI host | Free quota | Local stop line |
| --- | --- | --- | --- |
| Depop · Poshmark · Mercari · eBay | fashion-resale-api.p.rapidapi.com | 50 calls/month | 40 |
| Etsy | etsy-api2.p.rapidapi.com | 50 calls/month | 40 |
| Facebook Marketplace | facebook-marketplace-api.p.rapidapi.com | 50 calls/month (hard cap) | 40 |

eBay comes through the Fashion Resale API (add ebay to the platforms parameter). There is no separate eBay subscription and no separate eBay quota (confirmed by testing on 2026-10-19).

- **One standard format:** one adapter per platform cleans the response into the FitFindr standard dict id, title, price, size, platform, url, image\_url (optional condition, updated\_at); search\_listings merges, de-duplicates and sorts.
- **Call priority:** call the Fashion Resale API first (one call covers Depop, Poshmark, Mercari and eBay, sorted by price so the platforms mix); wire up Etsy and FB Marketplace last, in one integration pass.
- **Recorded data during development:** call each API for real only 1–2 times and save the raw JSON to tests/fixtures/; unit tests, prompt debugging and UI integration all read these files. Fixtures are used only in development and test code and are never loaded in production.
- **Counting and stop line:** one monthly counter per host (stored in the database, reset on the 1st of each month). At the stop line that platform stops making requests: if a real cache less than 24 hours old exists, use it; otherwise skip the platform and show "eBay results are paused until Nov 1" on the results page. Never fill the gap with fake data.
- **Quota warning:** the 3 APIs total about 150 calls a month, enough only for development and a small demo; upgrade to a paid plan before there are real users.
- **Third-party APIs:** these are third-party APIs on RapidAPI, not the platforms' official APIs; follow the terms of RapidAPI and the providers; the APIs may change, so the failure rate needs monitoring.
- **Do not change the interface shape:** the input and output of search\_listings stay unchanged and it is still called over MCP.
- **Match against the closet:** result ranking uses closet information (which categories are missing, common colors and styles); size (US) and budget (USD) come from the profile automatically and the user can remove them.
- **Search upgrade** (phase 2): replace keyword matching with vector search and check that the result category matches the question.
- **Failure messages are written for ordinary users:** when the model is unavailable, show "Styling suggestions are unavailable right now. Your search results still work."; technical details go only to the logs.
- **Cost control:** real results for the same question are cached for 24 hours; each user may make at most 10 searches a minute.

## 6. Privacy, compliance and honest presentation

- The closet, photos and profile are visible only to their owner by default; single items and the whole account can be deleted from Profile.
- Passwords are handled by the auth service and never stored in plain text; API keys live only in server environment variables.
- Show only the 6 platforms that are really connected, and never claim to "search the whole web"; label each listing with its source platform and link back to the original listing page.
- Purchases are completed on third-party sites; this site collects no payment information. Price and stock are as shown on the original platform.
- Follow the API terms of eBay and Etsy (image display, cache duration, source attribution).
- The terms of service and privacy policy need legal review before launch; when SMS is built in phase 2, it needs separate consent and must support STOP opt-out.

## 7. Suggested technical approach

Use Supabase to cover the database, login and image storage in one go; keep the backend in Python and reuse the existing agent code directly.

| Layer | Choice | Reason |
| --- | --- | --- |
| Frontend | Next.js + Tailwind CSS | Many templates, simple deployment |
| Backend | FastAPI (Python) | Calls the existing run\_agent directly |
| Database | Supabase Postgres | Closet, saved items and profile stored in SQL |
| Auth | Supabase Auth | Email verification and forgot-password are built in |
| Image storage | Supabase Storage | Each user can read and write only their own photos |
| Deploy | Vercel (frontend) + Render (backend) | Both have a free tier |

Tables: users, profiles(user\_id, sizes, styles, colors, budget), closet\_items(id, user\_id, photo\_url, name, category, colors, style\_tags, size, brand, season, notes), saved\_items(user\_id, listing\_id, source, saved\_at).

Endpoints: POST /search, GET/POST/PATCH/DELETE /closet/items, POST /closet/items/{id}/photo, GET /closet/items/{id}/matches, GET/POST/DELETE /saved, GET/PATCH /profile.

The website lives in a new private repository fitfindr-agent (local: the project folder). The course repository is a fork of a public repository, and GitHub does not allow changing it to private, and product code should not be public. Copy agent.py, tools.py, mcp\_server.py and the rest over; keep running run\_eval.py after every large change. Environment variables: GEMINI\_API\_KEY, RAPIDAPI\_KEY, ETSY\_API\_HOST, RESALE\_API\_HOST, FB\_MARKETPLACE\_HOST, SUPABASE\_URL, SUPABASE\_ANON\_KEY, SUPABASE\_SERVICE\_ROLE\_KEY.

## 8. Acceptance criteria

- [ ] A new user can sign up with email + password, verify the email and log in; sign-up is impossible without ticking the terms
- [ ] Every step of Profile setup can be skipped
- [ ] A clothing photo can be uploaded and its details filled in; after logging out and back in the photo and details are still there
- [ ] A file over 10 MB or in an unsupported format is rejected with the reason
- [ ] Searching "vintage graphic tee under $30" returns results with photos, each ≤ $30
- [ ] With a closet, the outfit suggestion names at least 1 item from the closet (at least 4 times out of 5)
- [ ] When nothing is found, no model call is made and tappable relax suggestions are offered
- [ ] A saved item appears in Saved and is still there after logging in again
- [ ] All listings come from the 6 real platforms with photos and original links, and fixtures are not loaded in production; unbuilt features show Coming soon, not a blank page
- [ ] At phone width 375 px no page scrolls horizontally; at desktop width 1280 px the layout is multi-column
- [ ] The 5 criteria of run\_eval.py are still met (reads fixtures, uses no quota); once a platform's counter reaches the stop line, no more real requests are made

## 9. Changes from v1 and open questions

| v1 wording | v2 decision | Reason |
| --- | --- | --- |
| The sign-up PRD and the home PRD each had a home page | Logged-out Landing, logged-in Home | Two home pages leave the developer unsure which to build |
| Pages numbered A/B and A–E overlapped | Unified as P1–P9 | Avoid confusing references |
| Feed Finder / FitFindr | Unified as FitFindr | One brand name |
| Navigation in Chinese, copy in English | UI entirely in English | Users are in the US |
| Two names, Dashboard and "Mine" | Closet + Profile | One concept, one name |
| Five bottom entries: Home / Local / Sell / Messages / Mine | Home / Closet / Saved / Profile | Local, selling and messages have no API support yet |
| Closet categories included cosmetics and lacked outerwear | tops/bottoms/outerwear/dresses/shoes/accessories | Aligned with the listing data; cosmetics are unrelated to outfits |
| Listing data had no photo | The standard format includes image\_url and url | Every recommendation must have a photo |
| Sign-up collected height, weight and measurements | The MVP does not collect them | Not needed, and adds privacy risk |

Open questions:

- Confirmed: US users only, US sizing, prices in USD.
- The RapidAPI free quota is only enough for development and demos: which paid plan before there are real users?
- When a third-party API shuts down, which backup API do we use?

## 10. Pre-development preparation

Most preparation is done; the rest is left to Claude Code, following CLAUDE.md and the start-up instructions, and only 3 things need you to do by hand.

| Item | Status | Who does it |
| --- | --- | --- |
| GitHub, Vercel and Render accounts | Have | — |
| Gemini API key | Have (reused from the course assignment) | — |
| RapidAPI key and 3 hosts | Have | You put them in .env |
| 10 clothing photos (wardrobe photos/) | Have | — |
| Logo and favicon | Have (price tag + FF shape, logo.svg, favicon.svg) | — |
| Create the private repository fitfindr-agent and copy the agent code | To do | Claude Code |
| Put the PRD, CLAUDE.md, prototype HTML and logo in the project folder | Done | Claude (placed directly in FitFindr-Agent) |
| .env.example, .gitignore, folder structure, RapidAPI counter | To do | Claude Code |
| Terms of service and privacy policy templates (marked Draft) | To do | Claude Code |
| Call the Fashion Resale API 1–2 times and record fixtures | To do | Claude Code, asking you before sending requests |
| Install Node.js LTS | To do | You (Claude Code will check first) |
| Sign up for Supabase and create a project | To do | You (about 5 minutes; Claude Code writes the table-creation SQL) |
| Lawyer review of the terms | After real users exist | You |
