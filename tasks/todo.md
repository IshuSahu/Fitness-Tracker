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
- [ ] Migration `003_day_plan.sql`: `day_plan(log_date pk, day_key)`.
- [ ] `routers/day_plan.py`: GET / PUT (409 once sets exist) / DELETE.
- [ ] `lifts.py`: `post_set` resolves day_key from `day_plan` first.
- [ ] `index.html`: workout select in the session header, disabled once locked.

### 4. Substitute an exercise
- [ ] Migration `004_exercise_swap.sql`: `exercise_swap(log_date, order_no, exercise_id)`.
- [ ] `plan.py`: optional `date`, left-join the swap and substitute the slot.
- [ ] `routers/exercises.py`: alternatives by shared `muscles` + same `kind`;
      PUT/DELETE swap with a 409 guard once that slot has sets.
- [ ] `index.html`: per-exercise swap control + dropdown.

### Verification
- [ ] Live-DB checks for the new endpoints and their 409 guards.
- [ ] jsdom checks for the dropdowns, skeleton and error panel.
- [ ] Real browser: all three boot states, no fake numbers anywhere.
- [ ] Clean up all test rows.

## Review
_(to be written when the unit of work is finished)_
