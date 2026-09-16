# Live audit: FastAPI backend conversion

Run 2026-09-16, against the live Supabase project and the actual app code
(not reimplemented test logic). Full method, results, one real bug found
and fixed, and what's still unverified and why.

## Method

Two layers, because of one environment constraint discovered mid-audit:

1. **App boot / routing / static serving / 401 rejection** -- tested over
   real HTTP (`curl` against a running `uvicorn` instance in a container).
2. **Auth verification logic** -- tested by manually decoding a real,
   freshly-issued Supabase access token against the real JWKS key, using
   the exact same `jwt.decode(..., algorithms=["ES256"], audience=
   "authenticated")` call `app/auth.py` makes. Not simulated: real token,
   real key, real cryptography library.
3. **Every route's actual behavior** -- tested by importing the real router
   modules inside the running container and calling their handler
   functions directly with a fixed `user_id`, against the live database.
   This exercises 100% of the real application code (SQL, Pydantic
   validation, business rules) -- it skips only the HTTP transport and the
   `verify_jwt` dependency, which layer 2 already proved correct
   independently.

**Why not one full HTTP round-trip end to end:** this sandbox's network
blocks outbound HTTPS from *inside Docker containers* specifically --
confirmed with plain `curl` (not a Python or app issue) failing the exact
same way `PyJWKClient`'s fetch did, while the same requests succeed from
the host shell directly and while `asyncpg`'s connection to Postgres (a
different protocol) works fine from the same container. Given that, I
asked whether I could temporarily bypass TLS verification to get one real
HTTP-level run; that was correctly blocked by a safety check, and I didn't
try to work around it. Layers 2+3 together cover the same ground (real
crypto verification + real app logic against a real database) without
that bypass -- the one thing they *don't* prove is the JWKS network fetch
itself succeeding over real HTTPS in this sandbox, which is a property of
this machine's network, not of the code. Render's servers won't have this
restriction.

## Bug found and fixed

`requirements.txt` had `pyjwt==2.9.0` without the `[crypto]` extra.
Without it, ES256 verification fails immediately with
`MissingCryptographyError` -- **this would have failed in production too**,
not just locally. Fixed to `pyjwt[crypto]==2.9.0`. Found because I
actually tried to verify a real ES256 token, not from reading the code.

## Results, endpoint by endpoint

| Endpoint | Result |
|---|---|
| `GET /health` | PASS -- `{"ok":true}` |
| Static `/` | PASS -- serves `static/index.html`, HTTP 200 |
| Missing/garbage bearer token | PASS -- 401 with a clear message, both cases |
| JWKS-based ES256 verification | PASS -- real token decoded, `sub` extracted and matched against `ALLOWED_USER_ID`, using real cryptographic material |
| `GET /api/daily/today` | PASS |
| `PUT /api/daily/today` | PASS -- wrote `water_l`, `meals`, `supplements`, `sleep`, the new `kcal_eaten`/`protein_g`/`carbs_g`/`fat_g`/`sleep_hours` columns, `streak`; read back and confirmed byte-for-byte |
| `GET /api/weight?limit=8` | PASS |
| `PUT /api/weight/today` | PASS -- wrote and confirmed present in the subsequent list |
| `GET /api/plan/{day_key}` | PASS -- resolved the active block, computed `week_no`, joined `session_template` -> `exercise` -> `prescription_override` correctly; 8 exercises for `mon`, matching the seed |
| `GET /api/lift-state` | PASS |
| `POST /api/sets` (called twice, same exercise/session) | PASS -- `set_index` correctly incremented (append, not overwrite), `sessions_logged` incremented **once** across both calls (not per-set, as specced), `last_sets` correctly accumulated both entries in order, `best_e1rm_kg` computed correctly (35kg x 9 -> 45.5, matches Epley) |
| `POST /api/coach/update` | PASS -- inserted `coach_note`, upserted `prescription_override` inside one transaction |
| Coach update -> plan override, end to end | PASS -- immediately re-fetched `GET /api/plan/mon` and confirmed the just-written override (rep range 8-10 -> 6-10) was reflected, with `overridden: true` |
| `GET /api/reports/weekly` | PASS -- called the real `weekly_report()` SQL function, got back a correctly formatted report referencing the real block name and week number |

**13 for 13.** Every listed endpoint's actual behavior confirmed against
the live database using the real, committed code.

## Cleaned up afterward

All test writes were removed after verification -- `daily_logs`,
`weight_logs`, `lift_logs`, `training_session`, `coach_note`,
`prescription_override`, and the `lift_state` cache row they produced.
Also found and removed a few stray rows from an earlier testing round in
this same session (dated 2026-09-15) that hadn't been cleaned up then.
Final state: `exercise` (48 rows) and `session_template` (42 rows, the
real seed data) intact; every user-data table empty, ready for real use.

## What's still genuinely unverified

- **The JWKS fetch succeeding over a real network path.** The verification
  *logic* is proven correct; the *network call* to Supabase's JWKS endpoint
  has only been tested indirectly (host-side `curl` to the same URL
  works). First real login on Render (or any non-sandboxed host) is the
  actual proof of this specific piece.
- **The browser UI itself.** Nothing above touched `static/index.html` in
  a real browser -- it exercises the backend directly. The frontend's
  `fetch()` calls, the login screen, and the sequential set-logging UI
  change (flagged separately) haven't been clicked through live.
- **Render deployment specifics** (build, env vars, cold start) --
  described in the README, not yet actually run on Render.
