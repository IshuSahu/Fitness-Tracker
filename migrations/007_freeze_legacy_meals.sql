-- Freeze the positional meal columns now that meal_log (006) replaces them.
--
-- Renamed rather than dropped: nothing reads or writes them any more, and the
-- rename guarantees that -- any stray reference fails loudly instead of
-- quietly writing a second, drifting copy of a day's meals. They are kept as a
-- record of what was stored before meal_log, not as a live source.

alter table daily_logs rename column meals to meals_legacy;
alter table daily_logs rename column meal_choices to meal_choices_legacy;
