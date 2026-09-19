-- Which programme a given date runs, when it isn't the weekday's default.
--
-- Normally the workout for a date is derived from its weekday (Monday ->
-- 'mon' -> Push A). Miss a session and you want to run it the next day
-- instead; this records that decision for one date.
--
-- One row per date, so deleting the row reverts to the weekday default and
-- swapping two days is just two rows. `training_session.day_key` still records
-- what a date ACTUALLY ran once sets are logged -- this is the intent that
-- feeds it, not a duplicate of it.

create table if not exists day_plan (
  log_date date primary key,
  day_key   text not null check (day_key in ('mon','tue','wed','thu','fri','sat','sun')),
  created_at timestamptz not null default now()
);
