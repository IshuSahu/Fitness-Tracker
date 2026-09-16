-- Seeds session_template from physique-os.html's hardcoded WORKOUTS object.
-- exercise_id values are mapped onto the existing 48-row `exercise` catalog
-- by closest name match (that catalog predates this app and doesn't share
-- WORKOUTS' exact naming). A few are judgment calls, noted inline -- worth
-- a human sanity check against physique-os.html's WORKOUTS data.

insert into session_template (day_key, order_no, exercise_id, base_sets, base_rep_lo, base_rep_hi) values
-- mon: Push A
('mon', 1, 'inc-db-press', 4, 8, 10),
('mon', 2, 'machine-chest-press', 3, 8, 10),       -- "Flat barbell or machine chest press": no flat-barbell row exists
('mon', 3, 'db-shoulder-press', 3, 10, 12),
('mon', 4, 'cable-lateral', 3, 12, 15),
('mon', 5, 'bar-pushdown', 3, 12, 15),              -- "Cable triceps pushdown": generic, mapped to straight-bar
('mon', 6, 'rope-oh-ext', 2, 12, 15),
('mon', 7, 'plank', 3, 40, 50),                     -- seconds, not reps
('mon', 8, 'incline-walk', 1, 12, 12),              -- minutes, not reps

-- tue: Pull A
('tue', 1, 'lat-pulldown', 4, 8, 10),
('tue', 2, 'seated-row', 3, 10, 12),
('tue', 3, 'cs-db-row', 3, 10, 12),
('tue', 4, 'face-pull', 3, 15, 15),
('tue', 5, 'db-curl', 3, 10, 12),
('tue', 6, 'hammer-curl', 2, 12, 12),

-- wed: Legs A
('wed', 1, 'squat', 4, 8, 8),
('wed', 2, 'leg-press', 3, 10, 12),
('wed', 3, 'rdl', 3, 10, 10),
('wed', 4, 'seated-leg-curl', 3, 12, 12),
('wed', 5, 'calf-raise', 3, 15, 15),
('wed', 6, 'plank', 3, 45, 45),

-- thu: Active recovery
('thu', 1, 'easy-walk', 1, 35, 45),                 -- minutes
('thu', 2, 'stretch-circuit', 2, 30, 45),           -- seconds per hold
('thu', 3, 'shoulder-mobility', 2, 10, 12),
('thu', 4, 'plank', 2, 30, 40),                     -- "Dead bug or light plank": no dead-bug row exists

-- fri: Push B
('fri', 1, 'machine-shoulder-press', 3, 10, 10),
('fri', 2, 'inc-db-press', 3, 10, 10),
('fri', 3, 'cable-fly', 3, 12, 12),                 -- "Cable fly or pec deck": picked cable-fly
('fri', 4, 'db-lateral', 4, 12, 15),
('fri', 5, 'rope-oh-ext', 3, 12, 12),
('fri', 6, 'bar-pushdown', 2, 15, 15),               -- "Cable pushdown": generic, same mapping as Monday's

-- sat: Pull B
('sat', 1, 'ng-pulldown', 4, 10, 10),
('sat', 2, 'sa-cable-row', 3, 12, 12),
('sat', 3, 'rear-delt-fly', 3, 15, 15),
('sat', 4, 'inc-db-curl', 3, 12, 12),
('sat', 5, 'cable-curl', 2, 15, 15),
('sat', 6, 'incline-walk', 1, 15, 15),               -- "Treadmill walk": only walk-type id besides Thu's easy-walk

-- sun: Legs B
('sun', 1, 'rdl', 4, 8, 8),
('sun', 2, 'bulgarian', 3, 10, 10),
('sun', 3, 'leg-ext', 3, 12, 12),
('sun', 4, 'seated-leg-curl', 3, 12, 12),
('sun', 5, 'hanging-knee-raise', 3, 12, 12),
('sun', 6, 'incline-walk', 1, 15, 15)
on conflict (day_key, order_no) do update set
  exercise_id = excluded.exercise_id, base_sets = excluded.base_sets,
  base_rep_lo = excluded.base_rep_lo, base_rep_hi = excluded.base_rep_hi;
