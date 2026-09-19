-- A one-day substitution of one exercise for another.
--
-- Keyed by the SLOT (order_no within the day's session), not by the exercise
-- being replaced, so the swap survives regardless of what the template holds
-- and reverting is just deleting the row. Deliberately does NOT touch
-- session_template: coach.py's swap mutates the template permanently and
-- globally with no undo, which is exactly what this avoids.

create table if not exists exercise_swap (
  log_date    date not null,
  order_no    int  not null,
  exercise_id text not null references exercise(id),
  created_at  timestamptz not null default now(),
  primary key (log_date, order_no)
);
