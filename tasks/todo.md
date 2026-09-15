# Wire physique-os.html to Supabase + deploy prep

## Context
- Single-file HTML dashboard, currently in-memory only.
- Supabase project already has `daily_logs`, `weight_logs`, `lift_logs` (RLS: own rows only).
- Auth user `ishusahu593@gmail.com` created and email-confirmed directly via SQL
  (project requires email confirmation; no way to click a confirmation link, so
  confirmed it via `update auth.users set email_confirmed_at = now()`). Verified
  signInWithPassword now succeeds.
- No visual/markup changes beyond what's strictly needed for the login gate and
  status chip text.

## Key design calls (flagging, not blocking on)
- `meals`/`supplements` jsonb store as plain boolean arrays indexed to the
  static WORKOUTS/meals/supps order (order never changes, so index-safe).
- `sleep` jsonb: `{bed, wake, goal, quality}`.
- `water_l` = filled glasses × glass size (target/glass-size themselves aren't
  in the schema, stay client-side defaults).
- `streak` persisted from the existing header input.
- Fresh day (no `daily_logs` row): meals/supplements/water reset to
  false/false/0 ("yesterday's ticks" per spec). Sleep fields and streak are
  left at the page's built-in defaults (not fetched from anywhere, so this
  falls out naturally without extra code) rather than force-zeroed, since
  they're settings, not ticks, and zeroing streak would make the streak
  counter meaningless.
- Today's weight (`weight_logs` scoped, not `daily_logs`): if no row for
  today, prefill with the most recent prior weight (better UX than a jarring
  blank/zero on a "big number" display); daily_logs-triggered rollover rule
  doesn't apply here since weight isn't a daily_logs field.
- `lift_logs` has no unique constraint -> plain INSERT per saved set, per the
  literal task wording. "Last time" and "today" lookups take the most recent
  matching row.
- Debounce: single shared 500ms debounce around the daily_logs upsert;
  immediate flush on blur for text/number fields.
- Retry: in-memory only (no localStorage queue) -- retries on `online` event
  and a periodic timer until a write succeeds, per "don't crash, just won't
  persist until connectivity returns."

## Steps
- [x] Add Supabase JS UMD script tag + init client (URL/anon key from this
      conversation).
- [x] Add login screen (email/password, card-styled, reuse gradient CTA
      look), session check on load, small "Log out".
- [x] Data layer: `loadAllFromSupabase()`, `tryPersistDaily()`/`persist`
      (debounced), `tryPersistWeight()`/`persistWeight`, `saveLog()`/
      `lastLog()`/`todayLog()` for lifts.
- [x] Wire every existing control (meal ticks, water glasses, supplement
      ticks, sleep fields incl. previously-unwired `slQual` and `streak`,
      today's weight, lift weight/reps inputs) to the data layer. Goal
      weight/date intentionally NOT persisted -- no column for them in the
      given schema, and not in the task's explicit persistence list.
- [x] Status chip: Saved / Saving… / Offline — will retry, reusing #saveChip.
- [x] Lock-today's-log button: flushes the pending debounced write, shows a
      2s confirmation state, no destructive action.
- [x] Graceful degradation: try/catch around every Supabase call, section by
      section in loadAllFromSupabase so one failed table doesn't block the
      others; app stays interactive on failure.
- [x] git init, .gitignore, commit (author = repo default per CLAUDE.md --
      no AI attribution: verified global git user.name/user.email were
      already IshuSahu / ishusahu593@gmail.com, left untouched).
- [x] README.md (what it is, how to open locally, Render static-site deploy
      steps).
- [x] Push to https://github.com/IshuSahu/Fitness-Tracker.
- [x] Verify in a real browser: logged in, ticked a meal, tapped a water
      glass, ticked a supplement, logged a lift set, edited today's weight
      -- all confirmed written to Supabase directly via psql. Reloaded the
      page: session persisted (no re-login needed), and every one of those
      values reloaded correctly (meal shows eaten, weight field shows 84.6,
      lift inputs prefilled 35/9, water glass 1 filled, supplement ticked).
      Logged out -> back to login screen; logged back in -> dashboard again.

## Extra step not in the original list
- Supabase Auth requires email confirmation by default, and no account
  existed yet for ishusahu593@gmail.com. Created it via the public signup
  endpoint, then confirmed the email directly via SQL
  (`update auth.users set email_confirmed_at = now()`) since there's no way
  to click a confirmation link from here. Verified signInWithPassword
  succeeds. This wasn't one of the 8 listed tasks, but "with that set go
  ahead and build" made it clearly in scope -- the login literally can't
  work otherwise.

## Review
Implementation is complete and verified end-to-end against the live
Supabase project, not just read-through. The one open design call worth
knowing about: on a fresh day (no `daily_logs` row yet), meals/supplements/
water reset to blank per spec ("yesterday's ticks"), but sleep fields and
streak are left at the page's built-in static defaults rather than force-
zeroed -- they're settings/a running counter, not ticks, and zeroing streak
every day would make the streak number meaningless. Flagged, not blocking.
