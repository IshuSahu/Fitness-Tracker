# Meal catalog replacement, "Other" option, per-slot extras

## Status: done and verified locally. Live Render app DOWN until pushed.

## Step 0 findings (verified against code and live data)
- Catalog: hardcoded `MEAL_OPTIONS` const in `static/index.html`. No DB table.
- Per-slot option was already pickable, stored in a separate
  `daily_logs.meal_choices` jsonb as a positional int array.
- `daily_logs.meals` was a positional bool array; no longer tied to a fixed
  default once meal_choices existed.
- Hazard: choices were positional and totals recomputed from the *current*
  catalog on every save, so replacing the catalog in place would have silently
  rewritten past days the next time anything on them was saved.

## Steps
- [x] 1. `meal_log jsonb not null default '{}'` added (migration 006).
- [x] 2. Backfilled from meals + meal_choices against the OLD catalog. All 6
      rows matched stored kcal_eaten, and P/C/F too; re-verified from the DB.
- [x] 3. Backend + frontend read/write meal_log only. meals -> meals_legacy,
      meal_choices -> meal_choices_legacy (migration 007). Frozen, not dropped.
- [x] 4. Catalog replaced per spec; breakfast 4 is the full-scoop version.
- [x] 5. "Other" custom option and "+ Add extra" on every slot.
- [x] 6. Ring and all three macro bars recompute live on every change.
- [x] 7. weekly_report verified against meal_log for 14-19 Sep.

## Review

All seven steps done, each verified before moving on. 432 checks across 16
suites pass.

### What the data looks like now
`meal_log` per day, keyed by slot id. Each slot stores `eaten`, `option_id`
(a catalog id or `"custom"`), `name`, the four macros, and `extras`. The macros
are copied onto the day when an option is picked, so the catalog is used to
choose and never to sum. That is what keeps 19 Sep correct: its breakfast is
still "Poha + milk + whey" at 560 kcal, shown as "no longer in the plan",
even though that option was removed in step 4.

### Beyond the approved plan -- flagged, not hidden
- **Totals are computed on the server**, and any totals the browser sends are
  ignored. The weekly report reads kcal_eaten/protein_g, so they must never
  disagree with meal_log. During the cutover a phone tab still running the old
  page would read no `meals` field, show everything uneaten, and write zeros.
  Deriving the totals server-side makes that impossible.
- **A save without meal_log keeps the stored day** instead of wiping it, for
  the same stale-tab reason.
- **Boundary validation:** negative or non-numeric macros are rejected by the
  server. The page clamps a typed negative to 0, so a stray minus sign can't
  fail the whole day's save.
- **kcal rounds half-up.** Python's `round()` rounds .5 to even, so 1390.5 was
  stored as 1390 while the ring showed 1391. Matched to what the ring shows.
- **Two now-false descriptions corrected.** The code comment and the coach's
  report both said options within a slot were macro-matched. Lunch now spans
  535 to 700 kcal.
- The spec said "four small inputs" but listed five fields (name, kcal,
  protein, carbs, fat). Built all five.

### Test changes
- `test_meals.py` retired: it tested the removed columns. It also crashed
  mid-run and left a row on 2026-03-03, which was checked against its exact
  fingerprint and deleted.
- The vegetarian guard was a substring match and flagged "veggies" as egg.
  Now `\beggs?\b`: catches egg, eggs, egg whites; ignores veggies, eggless.
- Two step-snapshot tests updated for later, intentional changes.

### Worth knowing
- **The live Render app has been down since step 3.** Render still runs
  `f95a1fc`, which selects the renamed columns. Accepted as downtime; it comes
  back when this is pushed.
- **An all-defaults day is 1,805 kcal and 123 g protein**, below the 137 g
  floor the report uses for "days on protein target". Every default-only day
  will read as a miss in the coach's report.
- **20 Sep is a logged-but-empty day** (kcal 0). A report covering it averages
  in that zero. This was the case before this work; nothing here changed it.
- `coach.py`'s swap is still a permanent global mutation. Not touched.
