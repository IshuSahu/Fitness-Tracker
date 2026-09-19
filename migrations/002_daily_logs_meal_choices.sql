-- Which variant was chosen for each meal slot on a given day.
--
-- `daily_logs.meals` stays what it is: a positional array of booleans saying
-- which slots were eaten. This is a parallel array of integers saying WHICH
-- option was eaten in each slot -- [0,2,0,1,...] indexes into the frontend's
-- MEAL_OPTIONS list per slot, 0 being the default.
--
-- Kept separate from `meals` rather than widening it to objects so existing
-- rows keep reading correctly and nothing has to sniff the shape.

alter table daily_logs
  add column if not exists meal_choices jsonb not null default '[]'::jsonb;
