# Deploying FitFindr — step by step

Backend (FastAPI) on **Render**, frontend (Next.js) on **Vercel**, data on the
**Supabase** project you already have. Both hosts have free plans. Set aside
about 45 minutes. Nothing here costs money, and no key is ever pasted into a
file — only into the Render and Vercel dashboards.

You'll deploy in this order, because each step needs a URL from the one before:

1. Check the database is up to date (2 min)
2. Backend on Render → you get `https://fitfindr-api-XXXX.onrender.com`
3. Frontend on Vercel → you get `https://fitfindr-XXXX.vercel.app`
4. Tell Render the Vercel URL (CORS) and tell Supabase the Vercel URL (sign-in emails)
5. Smoke test

Keep `.env` open in VS Code next to you: most values you paste come from there.
Copy each value straight from `.env` into the dashboard; don't put keys in chat,
screenshots or files.

---

## 1. Database: apply any new migrations

In a PowerShell terminal in VS Code:

```powershell
cd backend; .venv\Scripts\Activate.ps1; $env:PYTHONUTF8=1
python scripts/migrate.py --status
```

Every line should say `applied` (0001 to 0005; `0005_profile_location.sql`
adds the profile's ZIP/city). If any says `pending`, run
`python scripts/migrate.py` (it applies them and prints `APPLIED …`).

---

## 2. Backend on Render

1. Push the branch you want to deploy to GitHub (for example merge `v2` into
   `main` first, or deploy `v2` directly).
2. Go to **dashboard.render.com** → **New** → **Blueprint**.
3. Connect GitHub if asked, pick the **fitfindr-agent** repository and the branch.
   Render finds `render.yaml` and shows one service, **fitfindr-api**.
4. Render now asks for the values marked "sync: false". Paste them:

   | Key | What to paste |
   |---|---|
   | `FRONTEND_ORIGINS` | For now `https://example.com` (you'll change it in step 4) |
   | `FRONTEND_ORIGIN_REGEX` | Leave empty for now |
   | `GEMINI_API_KEY` | from `.env` |
   | `RAPIDAPI_KEY` | from `.env` |
   | `RESALE_API_HOST` | from `.env` (fashion-resale-api.p.rapidapi.com) |
   | `ETSY_API_HOST` | from `.env` (etsy-api2.p.rapidapi.com) — Etsy is live |
   | `FB_MARKETPLACE_HOST` | from `.env` (facebook-marketplace-api.p.rapidapi.com) — stays "Coming soon" until you subscribe, see `BLOCKERS.md` |
   | `SUPABASE_URL` | from `.env` |
   | `SUPABASE_ANON_KEY` | from `.env` |
   | `SUPABASE_SERVICE_ROLE_KEY` | from `.env` — the secret one, backend only |

   These are already set by `render.yaml`, don't change them: `APP_ENV=production`,
   `FITFINDR_DATA_MODE=live`, `FITFINDR_PLANNER=gemini`,
   `FITFINDR_STYLIST_LIVE_CALLS=1`, `FITFINDR_BROADEN_LIVE_FETCHES=1` (a search
   with fewer than 4 results may make one extra store search per host),
   `FITFINDR_IMAGE_MODEL` ("AI preview" outfit pictures; on the free Gemini tier
   it has no quota and the app shows the closest real listing photo instead),
   `PYTHON_VERSION`, `PYTHONUTF8`.

   AI preview pictures are stored in the existing private `closet-photos`
   bucket under `ai-previews/`; nothing to set up.

   Do **not** add `TEST_USER_EMAIL`, `TEST_USER_PASSWORD` or `SUPABASE_DB_URL`
   to Render; the website doesn't use them.
5. Click **Apply**. The first build takes 3–5 minutes.
6. **How to tell it worked:** open the service, copy its URL
   (`https://fitfindr-api-XXXX.onrender.com`) and open `…/health` in a browser.
   You should see `{"ok":true,"data_mode":"live","env":"production"}`.
   - If the log says `Refusing to start: … FITFINDR_DATA_MODE=fixtures`, the
     data mode is wrong — it must be `live`.
   - If it says `Refusing to start: production needs FRONTEND_ORIGINS`, step 4.1 was skipped.

The free plan sleeps after 15 minutes without visitors; the first request after
that takes about a minute. That's normal.

---

## 3. Frontend on Vercel

1. Go to **vercel.com/new** → **Import** the **fitfindr-agent** repository.
2. **Root Directory**: click Edit and choose `frontend`. Framework: Next.js
   (detected from `frontend/vercel.json`).
3. Open **Environment Variables** and add three (all three are safe to be
   public; never add the service-role key here):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | `SUPABASE_URL` from `.env` (just `https://xxxx.supabase.co`, no `/rest/v1`) |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `SUPABASE_ANON_KEY` from `.env` |
   | `NEXT_PUBLIC_API_URL` | your Render URL from step 2, no trailing `/` |

4. Click **Deploy** (about 2 minutes).
5. **How to tell it worked:** Vercel shows your URL, like
   `https://fitfindr-XXXX.vercel.app`. The landing page loads. Searching won't
   work yet — that's step 4.

---

## 4. Connect the two (CORS and sign-in emails)

**Render (CORS):** service **fitfindr-api** → **Environment** → edit
`FRONTEND_ORIGINS` → paste your Vercel URL exactly, e.g.
`https://fitfindr-xxxx.vercel.app` (https, no trailing `/`). If you also want
Vercel preview deploys to work, set `FRONTEND_ORIGIN_REGEX` to
`^https://fitfindr(-[a-z0-9-]+)?\.vercel\.app$` (adjust `fitfindr` to your
project name). **Save, rebuild and deploy**.

**Supabase (redirects for confirmation and password-reset emails):**
dashboard → your project → **Authentication** → **URL Configuration**:

- **Site URL**: `https://fitfindr-xxxx.vercel.app`
- **Redirect URLs** → **Add URL**: `https://fitfindr-xxxx.vercel.app/**`

  (The app sends people to `/onboarding` after confirming their email and to
  `/reset-password` from the reset email; the `/**` entry covers both. Keep
  the `http://localhost:3000/**` entry for local development.)

---

## 5. Smoke test (5 minutes)

1. Open the Vercel URL. The landing page says **5 stores live** and
   "FB Marketplace (coming soon)". Search **vintage graphic tee under $30**.
   Results show with photos (Etsy among the stores) and no "Development mode"
   note. (This is one live call per host, Fashion Resale and Etsy; identical
   searches in the next 24 h are free.)
2. On the results, open **Filters** and tap **Depop**: the results change at
   once, with no Apply button, and the URL gains `stores=depop`.
3. Sign up with a real email → confirm from the email → you land on
   onboarding. Fill in "Shopping for" and save.
4. Add a closet item with a photo → the fields fill in with "AI suggested"
   badges → save → the item page shows "Styling your piece…" and then an outfit
   where every piece has a picture (a listing, "Closest find" or "AI preview").
5. Open `…onrender.com/dev/traces` in a browser: it must say **Not found** in
   production (traces are dev-only).

**RapidAPI quota:** each store host stops itself at 40 calls a month and shows
"Paused until …". After the v2 fixes on Oct 19 the October counts are
Fashion Resale 34/40 (see `docs/V2_REPORT.md`), Etsy 3/40, FB Marketplace 1/40,
so October has only a few new searches left; the cache keeps repeat searches free
and November starts at 0. Check the count any time with
`python -m sources.quota` in `backend` (with `.env` loaded).

## If something goes wrong

| Symptom | Fix |
|---|---|
| Search says "We couldn't reach FitFindr" | `NEXT_PUBLIC_API_URL` wrong on Vercel, or Render asleep — open `/health` and wait a minute |
| Browser console shows a CORS error | `FRONTEND_ORIGINS` on Render doesn't exactly match the Vercel URL |
| Confirmation email link goes to localhost | Supabase Site URL / Redirect URLs (step 4) |
| Results "Paused until Nov 1" | The 40-call stop line for this month; it resets on the 1st |
| Render log: `Refusing to start` | Read the sentence after it — it names the missing setting |
