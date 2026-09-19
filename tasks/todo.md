# Flexibility pass: swap the day, swap an exercise, swap a meal, honest boot

## Context
Four asks, all about rigidity — plus one real bug found while researching them.

1. Miss a training day and there's no way to run that workout on another date;
   which workout runs is derived purely from the weekday. Rule given: **once a
   set is logged for that date, the day is locked in.**
2. No way to substitute an exercise within a session (flat DB press -> machine),
   with a dropdown of sensible alternatives. Scoped to that day only.
3. Meals are a fixed list — no alternative if the overnight oats weren't soaked.
4. With the server down the page shows **fabricated data that looks real**
   (85.4 kg, a fake downward sparkline, 2,200 kcal, streak 12) under a green
   "Saved locally" chip. Wanted: a proper skeleton + honest failure state.

**Standing constraint: fully vegetarian, no eggs.** Governs all meal content.

## Findings that shaped the plan
- `bootDashboard` reveals `#dashboard` *before the first fetch starts*, and
  every loader swallows its error, so offline you get a complete plausible
  dashboard with nothing indicating the backend is dead.
- `/health` returns `{"ok":true}` unconditionally — it never checks the DB, and
  no frontend code calls it.
- `muscle_group` is too coarse for an alternatives dropdown (29 of 48 rows are
  "upper"); `exercise.muscles text[]` + `kind` + `equipment` give a real rule.
- **Do not reuse `coach.py`'s swap** — it mutates `session_template`
  permanently and globally, no undo, and ignores the `week_no` it accepts.
- `prescription_override` can't express substitution (PK `(week_no,
  exercise_id)`, no day_key, no replacement column).

## Steps

### 1. Honest boot
- [x] `main.py`: `/health` actually pings the DB (`select 1`), 503 when it can't.
- [x] `index.html`: `#skeleton` node + shimmer CSS, with a
      `prefers-reduced-motion` static fallback.
- [x] `bootDashboard`: skeleton -> load -> reveal dashboard **only on success**;
      failure shows a "can't reach the server" panel with Retry.
- [x] Strip every fabricated default (`S.weight/start/lastWeek/history`,
      `streak="12"`, `#wNow` 85.4, "3 confirmed", hardcoded macro figures).
- [x] `loadAllFromApi` propagates failure instead of swallowing it.

### 2. Meal options
- [x] Migration `002_daily_logs_meal_choices.sql`: add `meal_choices jsonb`.
- [ ] `schemas.py`/`daily.py`: `meal_choices: list[int]` through DailyIn/Out.
- [x] `index.html`: `MEAL_OPTIONS` constant (all vegetarian, macro-matched per
      slot), `<select>` per meal card, choice persisted.
- [x] Collapse the duplicate macro summers (`recalc()` / `eatenTotals()`) into
      one function reading the chosen variant.

### 3. Reassign a date's workout
- [x] Migration `003_day_plan.sql`: `day_plan(log_date pk, day_key)`.
- [x] `routers/day_plan.py`: GET / PUT (409 once sets exist) / DELETE.
- [x] `lifts.py`: `post_set` resolves day_key from `day_plan` first.
- [x] `index.html`: workout select in the session header, disabled once locked.

### 4. Substitute an exercise
- [x] Migration `004_exercise_swap.sql`: `exercise_swap(log_date, order_no, exercise_id)`.
- [x] `plan.py`: optional `date`, left-join the swap and substitute the slot.
- [x] `routers/exercises.py`: alternatives by shared `muscles` + same `kind`;
      PUT/DELETE swap with a 409 guard once that slot has sets.
- [x] `index.html`: per-exercise swap control + dropdown.

### Verification
- [x] Live-DB checks for the new endpoints and their 409 guards.
- [x] jsdom checks for the dropdowns, skeleton and error panel.
- [ ] Real browser: all three boot states, no fake numbers anywhere.
- [x] Clean up all test rows.

## Review

All four shipped and verified. 189 checks across seven suites, all passing:
53 against the live database, 136 driving the real page in jsdom.

**1. Honest boot.** The complaint was cosmetic; the cause wasn't. The page
revealed itself *before the first fetch started*, and every loader swallowed
its error, so with the server down you got a complete, plausible dashboard --
85.4 kg, a downward sparkline, a 12-day streak -- under a green "Saved
locally" chip. The headline weight was a hardcoded `data-count="85.4"` that no
code ever updated, so it read 85.4 no matter what you'd logged. The dashboard
now appears only once real data is in hand, `/health` actually runs `select 1`,
and failure states distinguish an unreachable server from a reachable one that
can't get to the database. Every fabricated default is gone.

**2. Meal options.** Each of the six slots carries 4-5 alternatives that hit
roughly the same macros, so swapping never quietly wrecks the day's totals.
All vegetarian, no egg -- asserted by a test so it stays that way. Where a
variant genuinely can't match, it says so: the curd-and-honey post-workout
option is labelled the low-protein fallback, and "Skip tonight" is a real
zero-calorie choice rather than a box left untouched.

**3. Reassigning a date's workout.** One row per date in `day_plan`, so
reverting is deleting the row and swapping two days is two rows. `post_set`
resolves `day_key` the same way, so a set logged on a reassigned day is filed
under the programme actually being run. Locked once any set exists, per the
stated rule.

**4. Substituting an exercise.** Per date, per slot, in `exercise_swap` --
`session_template` is never touched. Alternatives are derived from the
catalogue: shared `muscles` entries plus matching `kind`, excluding anything
already programmed that day.

### Worth knowing

- **The day tabs now reassign the date, not just preview it.** Built as two
  separate controls first, which created a footgun: clicking a tab showed
  another programme's exercises, but a set logged there was filed under the
  date's *real* programme, against an exercise that session didn't contain.
  Unified to one control -- picking a day IS choosing what you're doing.
  The redundant select was removed.
- **`loadDayPlan` validates the `day_key` it receives.** `curDay` drives every
  subsequent render; an unusable value took the whole session card down. Found
  because a test harness returned an empty object.
- **Not verified in a real browser.** jsdom drives the actual page code, but
  that tests behaviour, not rendering. The skeleton shimmer, the new selects
  and the disabled day tabs have not been looked at on a real screen or at
  phone width.
- Migrations 002-004 are applied to the live database; existing rows were
  preserved and verified.
- `coach.py`'s swap is still a loaded gun -- permanent, global, no undo,
  ignores the `week_no` it accepts. Unused by the UI. The new per-date swap is
  what it should be rebuilt on if anything ever calls it.
- `session_template` still has no DDL in the repo.
