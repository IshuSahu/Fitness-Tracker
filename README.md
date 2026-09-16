# Physique OS

A single-user personal fitness dashboard: body weight, calories/macros,
today's training session, water, meals, supplements, and sleep. A FastAPI
backend owns all the data in Postgres (Supabase-hosted); the browser only
talks to Supabase directly for login.

## Architecture

```
Browser (static/index.html)
  -> supabase-js: signInWithPassword / getSession / signOut only
  -> fetch(), with "Authorization: Bearer <session JWT>", for everything else
       |
       v
FastAPI backend (app/)
  -> verifies the JWT against Supabase's public JWKS (ES256 -- this project
     uses Supabase's newer asymmetric JWT Signing Keys, not the legacy
     HS256 shared secret) and checks its "sub" matches ALLOWED_USER_ID --
     this, not Supabase RLS, is what enforces "only I can read or write
     this data"
  -> one asyncpg connection pool straight to Postgres
  -> serves /api/* JSON routes and the static/ dashboard itself --
     one deployable service
```

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Supabase: Project Settings -> Database -> Connection string -> URI -> **Session pooler** tab (not "Direct connection" -- that's IPv6-only) |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | Supabase: Project Settings -> API. These are already hardcoded into `static/index.html` (the anon key is meant to be public); the `.env` copies are here for reference if you ever need to change them. `SUPABASE_URL` is also used server-side to build the JWKS URL that verifies tokens |
| `ALLOWED_USER_ID` | Supabase: Authentication -> Users -> your account's UUID |

Run it:

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000**, log in, and you're on the same dashboard,
now backed by the API instead of talking to Supabase directly for data.

## Database migrations

`migrations/001_seed_session_template.sql` seeds the `session_template`
table (which day maps to which exercises, sets and rep ranges) from the
dashboard's original hardcoded workout data. It's already been run against
the live Supabase project as part of building this; keeping it in the repo
is just for reproducibility if the table ever needs rebuilding. A few
exercise-name mappings in it were judgment calls (noted inline in the
file) -- worth a skim if a session's set/rep target looks off.

## Deploying on Render (free Web Service)

1. Push this repo to GitHub.
2. On [Render](https://render.com), **New -> Web Service**, connect the repo.
3. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add the same environment variables from `.env` in Render's dashboard
   (Environment tab) -- `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
   `ALLOWED_USER_ID`.
5. Deploy. Render's free tier sleeps after 15 minutes idle -- the first
   request after that will be slow (the container cold-starting). That's
   expected on the free tier, not a bug.

## What's not wired up yet

`GET /api/reports/weekly` and `POST /api/coach/update` are fully built and
tested (directly, via HTTP) but **`static/index.html` has no UI that calls
them** -- there's no Weekly Report tab or Coach Update panel in the
dashboard as it currently exists. Both endpoints work; nothing in the page
triggers them yet.
