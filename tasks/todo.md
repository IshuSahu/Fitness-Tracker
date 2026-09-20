# Make "swap this exercise" usable: wider candidates, no double-booking, search

## Context
The swap dropdown offers almost nothing. Machine chest press showed three
options; ten exercises in the catalogue return **none at all**. Asked for the
full list minus what's already in the session, plus a searchable dropdown.

Render (first screenshot) needs no work: `/health` returns
`{"ok":true,"db":true}` in 2.5s and the deployed page is byte-identical to
local. That "APPLICATION LOADING" screen is Render's own, shown while a
sleeping free-tier container wakes — not our page, can't be restyled. Chose to
leave it. Already documented in the README.

## Findings
- **The muscle filter is the culprit.** `e.muscles && $3` requires an exact
  free-text match, and the vocabulary is hyper-specific: `machine-chest-press`
  is `Mid chest, Triceps` while `pec-deck`/`cable-fly` are `Chest` and
  `low-high-fly` is `Upper chest` — none intersect, so the obvious chest
  substitutes are filtered out. Across all 48 exercises: **mean 2.5, median 1,
  10 return zero**, 31 of 48 return fewer than three.
- `muscle_group` can't replace it either — 29 of 48 rows are just `upper`.
- **The exclusion misses swaps, both ways.** It reads `session_template` only,
  never `exercise_swap`. Live repro on 2026-09-18: slot 2 is swapped to
  `machine-chest-press`, yet it's still offered for slot 1 — accepting it puts
  the same exercise in the session twice. And on 2026-09-19, `ng-pulldown` /
  `sa-cable-row` were swapped *away* but stay excluded.

## Steps
- [x] `exercises.py`: factor a `resolved_session_exercises(conn, date)` helper
      (`coalesce(sw.exercise_id, st.exercise_id)`) — the set `_slot_exercise`
      already computes one slot at a time.
- [x] `exercises.py`: drop the `kind` and `muscles` filters; exclude self, the
      resolved session, and `muscle_group='cardio'` (unless the source is
      cardio). Order: same group+kind, then same group, then the rest; within
      each by shared-muscle count then name. Return `kind`, `muscle_group`,
      `muscles`, `suggested`.
- [x] `index.html`: replace the native `<select>` with a combobox — trigger
      button, absolutely-positioned panel, search input, `role="listbox"` rows
      grouped under Suggested / All exercises.
- [x] `index.html`: search across name, equipment, muscles, muscle_group,
      debounced with the existing `debounce()`.
- [x] `index.html`: keyboard (Up/Down/Enter/Escape/Tab) + click-outside via one
      delegated document listener. No such pattern exists in the file yet.
- [x] `index.html`: `closeSwapPanel()` at the top of `buildExercises()` — the
      failed-set-POST `.catch()` re-renders at an arbitrary moment.
- [x] `index.html`: cache alternatives per `(exercise_id, viewDate)`, cleared
      on swap or date change.
- [x] Verify: measured counts for all 48; the 09-18 double-booking repro; the
      cardio rule; combobox in a real browser at phone width.
- [x] Update `test_swaps.py` (asserts the old narrow behaviour) and extend
      `test_swapui.js`. Keep the other suites green.
- [x] Clean up test rows; leave the three real `exercise_swap` rows alone.

## Review

Done and verified. 274 checks across ten suites, all passing.

**The dropdown was broken, not narrow.** It required a matching `kind` **and**
an overlapping `muscles` entry, but `muscles` is free text and hyper-specific,
so near-identical movements never matched: `machine-chest-press` is
`Mid chest, Triceps` while `pec-deck` and `cable-fly` are just `Chest`. The
obvious substitutes were filtered out by the very field meant to find them.
Measured across all 48 exercises: **mean 2.5 candidates, median 1, and ten
returning nothing at all.**

Now the whole catalogue is offered minus the session, minus cardio (unless
you're swapping cardio, which would otherwise return nothing). Measured after:
**mean 36.4, median 36, minimum 36, no empties.**

**Ranking is on word overlap, not exact labels.** Same reason: "Mid chest" and
"Chest" are the same muscle spelled differently. Qualifiers (mid/upper/long/
head/front/side/rear) are dropped, or "Mid chest" pairs with "Mid back". A
chest press now leads with low-incline press, cable fly and pec deck instead of
lat pulldown and rows. `suggested` means "trains at least one of the same
muscles" rather than the old "same group and kind", which is what a lifter
actually means by a substitute.

**Double-booking is fixed, both directions.** The exclusion read
`session_template` only, never `exercise_swap`, so on 2026-09-18 —
reproduced against your live data — `machine-chest-press` was swapped into
slot 2 yet still offered for slot 1; accepting it would have put the same
exercise in the session twice. The inverse was also wrong: exercises swapped
*away* stayed excluded. Both now resolve through
`resolved_session_exercises()`, which is the set `_slot_exercise` already
computed one slot at a time.

**The picker is a real combobox.** Native `<select>` can't be typed into, and a
37-row list needs filtering. Search matches name, equipment, kind, muscle group
and muscles, and multiple terms narrow rather than widen ("cable chest").
Arrow keys, Enter, Escape, Tab and click-outside all work; results are grouped
under "Trains the same muscles" / "Everything else".

### Worth knowing

- **Render needed no work.** `/health` returned `{"ok":true,"db":true}` in 2.5s
  and the deployed page was byte-identical to local. That "APPLICATION LOADING"
  screen is Render's own, shown while a sleeping free-tier container wakes —
  not our page, and not restyleable. Left as is by choice.
- **`buildExercises()` closes the panel before re-rendering.** It rewrites
  `#exlist` wholesale, and the failed-set-POST `.catch()` can fire it at any
  moment, which would otherwise orphan an open dropdown.
- Alternatives are cached per `(exercise_id, date)` and cleared on any swap or
  date change, since either changes what's in the session.
- This is the page's first popup, so it brought the first `document` click
  listener and the first arrow-key handling with it.
- **Still not verified in a real browser.** jsdom drives the real handlers, but
  the panel's positioning, z-index and 248px scroll cap are unverified on a
  real screen — and the last three bugs you found were all rendering. Worth a
  look at phone width especially.
- Three test suites asserted the old narrow behaviour and were updated:
  `test_swaps.py`, `test_swapui.js`, `test_empty.js`.
