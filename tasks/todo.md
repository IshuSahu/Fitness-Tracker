# Set logging: latency, re-editing, single-row entry, warm-up/cool-down

## Context
Four problems found while using the tracker in the gym:
1. Logging a set takes 3-4 seconds before the next can be entered.
2. A logged set can never be corrected — rows disable themselves on save.
3. No warm-up or cool-down guidance.
4. Sets render as a vertical stack — too much scrolling/tapping on a phone.

Confirmed: warm-up/cool-down are tick-off checklists only (nothing numeric
stored), saving should feel instant/optimistic, a 4 × 8 exercise stops at 4.

## Root causes
- `post_set()` ran **11 sequential awaits** in one transaction (13 round-trips
  with BEGIN/COMMIT). At ~250ms RTT to Supabase that is ~3.2s — matches the
  reported lag exactly. Six queries were redundant or mergeable.
- `set_index` was derived from a live `COUNT(*)`, so set 2 became unaddressable
  once sets 3-4 existed. (`set_log` already had unique
  `(session_id, exercise_id, set_index)` + an upsert — only the index
  derivation blocked editing.)
- `data-tick` was local-only; it never gated editability.
- Sets always logged under today's real date, ignoring the date picker.
- `auth.py` made a blocking sync HTTPS JWKS call on the event loop every 300s.

## Steps
- [x] `schemas.py`: `SetIn` gains optional `set_index` and `date`.
- [x] `lifts.py`: use explicit `set_index` when given (falling back to the
      count), and `body.date` for day_key/week_no/session upsert.
- [x] `lifts.py`: drop the redundant exercise-existence check (FK covers it),
      fold `was_first_set` + `consecutive_misses` into the final upsert's
      DO UPDATE, merge the two rep-target lookups, TTL-cache the block row.
      **Measured: 1,400ms -> 720ms warm (~49% faster); 11 awaits -> 5.**
- [x] `lifts.py`: add `GET /api/sets?date=` — lift_state only holds the most
      recent session, so it can't say what was logged on a *viewed* date once
      backdating exists. Not in the original plan; the date feature is
      incorrect in the UI without it.
- [x] `auth.py`: move the blocking JWKS fetch off the event loop.
- [x] Backend correctness: 21/21 checks pass against the live database
      (in-place correction, date routing, misses/session-count semantics,
      off-plan days, FK 404, concurrent distinct indexes).
- [x] `index.html`: `PREP` constant — warm-up/cool-down checklists per session
      type (push/pull/legs/recovery), rendered above and below the exercises.
- [x] `index.html`: single-row set entry — "Set N of M", one kg × reps row,
      Back/Next, progress dots, stop at target.
- [x] `index.html`: optimistic save — advance immediately, POST in background,
      revert + offline chip on failure.
- [x] `index.html`: the per-exercise checkbox becomes the lock; unticking
      re-opens editing any number of times.
- [x] Verify: 21 backend checks against the live DB + 55 UI checks driving the
      real page in jsdom. All pass.
- [x] Confirm no test rows left in the database; the 09-16 session (11
      exercises, 30 sets) is real user data and was not touched.

## Review

Done and verified. The four reported problems and what actually fixed them:

**1. The 3-4s lag was real, not perceived.** `post_set()` made 13 network
round-trips per set. Measured on this machine before the change: **1,400ms
warm / 2,489ms cold**. After cutting it to 5 queries: **720ms warm**. On top
of that the UI no longer waits for the response at all, so the perceived cost
is now zero — the set marks done and the counter advances on click, and the
POST settles in the background. A failed save rolls the set back and shows the
offline chip rather than leaving it looking saved.

**2. Re-editing.** The blocker was `set_index` being derived from a live
`COUNT(*)`, which made set 2 unaddressable once 3 and 4 existed. `SetIn` now
takes an explicit `set_index`; the pre-existing unique constraint and upsert
did the rest. The tick-box is now the lock and nothing else auto-disables, so
any set can be corrected any number of times until you choose to lock it.

**3. Warm-up / cool-down** are frontend constants, not database rows —
they carry no sets, load or e1RM, so pushing them through
`session_template`/`PlanExercise` would have meant inventing catalog entries
for data that never varies. If per-day customisation is ever wanted, that's
when it earns a table.

**4. Single-row entry** replaces the stacked rows: "Set N of M", one kg × reps
line, Back/Next, progress dots, stops at the programmed count.

### Worth knowing

- **Lock state is per-session UI state, not persisted.** A refresh returns
  every exercise to editable. No logged data is ever lost — only the lock
  flag resets. This is deliberately more permissive, matching the request.
- **`GET /api/sets?date=` was added beyond the plan.** `lift_state` only ever
  holds the most recently written session, so once backdating exists it cannot
  answer "what did I log on the date I'm looking at". Without this endpoint the
  date picker would have shown the wrong sets. The UI now reads logged sets
  from `set_log` for the viewed date and uses `lift_state` only for the
  "Last time" reference.
- **Next refuses to advance on an empty set.** Found while writing the tests:
  skipping a set then logging the next one would have left a gap in the set
  indexes and crashed the locked summary on a sparse array. Next now requires
  a valid entry and focuses the offending input instead.
- **Not verified in a real browser.** jsdom drives the actual page code and
  all 55 assertions pass, but that is not the same as rendering — the CSS
  (dots, nav buttons, collapsible panels) has not been looked at on a real
  screen or at phone width. Worth a visual pass.
- `session_template` still has no DDL in the repo; unchanged by this work but
  still worth capturing in a migration.
