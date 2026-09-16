# Supabase schema audit — project `tbrywdestdngctdjdosl`

Read-only audit, pulled live via `psql` against the Supabase Postgres
instance (session pooler). No code or data was changed. Generated 2026-09-16.

**Context worth knowing up front:** this one Supabase project backs *two*
separate, unrelated apps built in earlier sessions:
- An older FastAPI-based tracker (`block`, `body_log`, `coach_note`,
  `exercise`, `lift_state`, `nutrition_log`, `prescription_override`,
  `set_log`, `sleep_log`, `training_session`) that talked to Postgres
  directly over a raw connection string — never through Supabase's
  client/PostgREST layer.
- The current single-file `physique-os.html` dashboard (`daily_logs`,
  `weight_logs`, `lift_logs`), which talks to Supabase only through the
  `supabase-js` client (anon key + user JWT), so it's subject to RLS.

That split matters for every table below, and is called out explicitly in
each section.

---

## block

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | `nextval('block_id_seq')` |
| name | text | NO | — |
| start_date | date | NO | — |
| weeks | integer | NO | `12` |
| goal | text | NO | `'recomposition'` |
| active | boolean | NO | `true` |

- **Primary key:** `id`
- **Foreign keys:** none outgoing. Referenced *by* `training_session.block_id` (`ON DELETE SET NULL`).
- **Unique constraints/indexes:** only the PK index (`block_pkey`).
- **RLS:** enabled, **zero policies defined** → default-deny. No client using
  the anon/authenticated key can read or write this table at all right now
  (only a service-role/direct-DB connection bypasses RLS).
- **Row count:** 1

---

## body_log

| Column | Type | Nullable | Default |
|---|---|---|---|
| date | date | NO | — |
| weight_kg | numeric | NO | — |
| waist_cm | numeric | YES | — |
| notes | text | YES | `''` |

- **Primary key:** `date`
- **Foreign keys:** none.
- **Unique constraints/indexes:** only the PK index (`body_log_pkey`).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## coach_note

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | `nextval('coach_note_id_seq')` |
| week_no | integer | NO | — |
| body | text | NO | — |
| patch | jsonb | NO | `'{}'` |
| created_at | timestamptz | NO | `now()` |

- **Primary key:** `id`
- **Foreign keys:** none.
- **Unique constraints/indexes:** only the PK index (`coach_note_pkey`).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## daily_logs

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | uuid | NO | `gen_random_uuid()` |
| user_id | uuid | NO | — |
| log_date | date | NO | — |
| water_l | numeric | YES | `0` |
| meals | jsonb | YES | `'{}'` |
| supplements | jsonb | YES | `'{}'` |
| sleep | jsonb | YES | `'{}'` |
| streak | integer | YES | `0` |
| created_at | timestamptz | YES | `now()` |

- **Primary key:** `id`
- **Foreign keys:** `user_id` → `auth.users(id)`, `ON DELETE NO ACTION`.
- **Unique constraints/indexes:** `(user_id, log_date)` unique
  (`daily_logs_user_id_log_date_key`) — one row per user per day, and what
  the frontend's `upsert(..., {onConflict:'user_id,log_date'})` relies on.
- **RLS:** enabled. One policy, **"own rows only"**: `PERMISSIVE`, applies to
  `{public}` role, command `ALL`, `USING (auth.uid() = user_id)`,
  `WITH CHECK (auth.uid() = user_id)`.
- **Row count:** 2
- **Content shape in practice:** `meals` and `supplements` are stored as
  plain JSON arrays of booleans, index-matched to the static meal/supplement
  order hardcoded in `physique-os.html` (not object maps despite the `{}`
  default). `sleep` is `{bed, wake, goal, quality}`.

---

## exercise

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | text | NO | — |
| name | text | NO | — |
| kind | text | NO | — |
| muscle_group | text | NO | — |
| equipment | text | NO | — |
| step_kg | numeric | NO | — |
| min_load_kg | numeric | NO | — |
| mode | text | NO | `'load'` |
| muscles | text[] | NO | `'{}'` |
| cue | text | YES | `''` |
| alt | text | YES | `''` |
| anim | text | YES | `''` |
| is_anchor | boolean | NO | `false` |

- **Primary key:** `id`
- **Foreign keys:** none outgoing. Referenced *by* `lift_state.exercise_id`,
  `prescription_override.exercise_id`, `set_log.exercise_id` (all
  `ON DELETE NO ACTION`).
- **Unique constraints/indexes:** only the PK index (`exercise_pkey`).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 48 (the seeded exercise catalogue from the FastAPI project)

---

## lift_logs

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | uuid | NO | `gen_random_uuid()` |
| user_id | uuid | NO | — |
| log_date | date | NO | — |
| exercise | text | NO | — |
| weight_kg | numeric | NO | — |
| reps | integer | NO | — |
| created_at | timestamptz | YES | `now()` |

- **Primary key:** `id`
- **Foreign keys:** `user_id` → `auth.users(id)`, `ON DELETE NO ACTION`.
- **Unique constraints/indexes:** only the PK index (`lift_logs_pkey`) —
  **no unique constraint** on `(user_id, log_date, exercise)`, and no
  set-index column. Multiple rows can exist for the same user/date/exercise
  by design; the frontend distinguishes "set 1, set 2, ..." purely by
  `created_at` order, and "logs a new set" by deleting all of today's rows
  for that exercise and reinserting the current full list.
- **RLS:** enabled. One policy, **"own rows only"**: `PERMISSIVE`, `{public}`,
  `ALL`, `USING (auth.uid() = user_id)`, `WITH CHECK (auth.uid() = user_id)`.
- **Row count:** 1
- **Note:** `exercise` here is a free-text column (the exercise's display
  name from `physique-os.html`'s hardcoded WORKOUTS data), not a foreign key
  into the `exercise` table above — the two exercise catalogues are
  unrelated.

---

## lift_state

| Column | Type | Nullable | Default |
|---|---|---|---|
| exercise_id | text | NO | — |
| last_session_id | integer | YES | — |
| last_date | date | YES | — |
| last_sets | jsonb | NO | `'[]'` |
| consecutive_misses | integer | NO | `0` |
| best_e1rm_kg | numeric | NO | `0` |
| best_e1rm_date | date | YES | — |
| sessions_logged | integer | NO | `0` |
| updated_at | timestamptz | NO | `now()` |

- **Primary key:** `exercise_id`
- **Foreign keys:** `exercise_id` → `exercise(id)` (`NO ACTION`);
  `last_session_id` → `training_session(id)` (`ON DELETE SET NULL`).
- **Unique constraints/indexes:** only the PK index (`lift_state_pkey`).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## nutrition_log

| Column | Type | Nullable | Default |
|---|---|---|---|
| date | date | NO | — |
| kcal | integer | YES | — |
| protein_g | integer | YES | — |
| carbs_g | integer | YES | — |
| fat_g | integer | YES | — |
| water_l | numeric | YES | — |
| meals | jsonb | NO | `'[]'` |

- **Primary key:** `date`
- **Foreign keys:** none.
- **Unique constraints/indexes:** only the PK index (`nutrition_log_pkey`).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## prescription_override

| Column | Type | Nullable | Default |
|---|---|---|---|
| week_no | integer | NO | — |
| exercise_id | text | NO | — |
| sets | integer | YES | — |
| rep_lo | integer | YES | — |
| rep_hi | integer | YES | — |
| load_kg | numeric | YES | — |
| note | text | YES | `''` |

- **Primary key:** composite, `(week_no, exercise_id)`
- **Foreign keys:** `exercise_id` → `exercise(id)` (`NO ACTION`).
- **Unique constraints/indexes:** only the PK index
  (`prescription_override_pkey`, which also enforces the composite
  uniqueness).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## set_log

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | bigint | NO | `nextval('set_log_id_seq')` |
| session_id | integer | NO | — |
| exercise_id | text | NO | — |
| set_index | integer | NO | — |
| load_kg | numeric | YES | — |
| reps | integer | NO | — |
| rir | numeric | YES | — |
| warmup | boolean | NO | `false` |
| tempo | text | YES | `''` |
| logged_at | timestamptz | NO | `now()` |
| e1rm_kg | numeric | YES | — (generated column: `load_kg * (1 + reps/30.0)`, per original DDL) |
| tonnage_kg | numeric | YES | — (generated column: `load_kg * reps`, per original DDL) |

- **Primary key:** `id`
- **Foreign keys:** `session_id` → `training_session(id)`,
  **`ON DELETE CASCADE`**; `exercise_id` → `exercise(id)` (`NO ACTION`).
- **Unique constraints/indexes:** `(session_id, exercise_id, set_index)`
  unique (`set_log_session_id_exercise_id_set_index_key`); plus a non-unique
  index `set_log_ex_time` on `(exercise_id, logged_at DESC)` for fast
  "history for this exercise" lookups.
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## sleep_log

| Column | Type | Nullable | Default |
|---|---|---|---|
| date | date | NO | — |
| bed_at | time | YES | — |
| wake_at | time | YES | — |
| hours | numeric | YES | — |
| quality | text | YES | — |

- **Primary key:** `date`
- **Foreign keys:** none.
- **Unique constraints/indexes:** only the PK index (`sleep_log_pkey`).
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## training_session

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | integer | NO | `nextval('training_session_id_seq')` |
| block_id | integer | YES | — |
| date | date | NO | — |
| dow | integer | NO | — |
| week_no | integer | NO | — |
| day_key | text | NO | — |
| is_deload | boolean | NO | `false` |
| bodyweight_kg | numeric | YES | — |
| sleep_h_before | numeric | YES | — |
| session_rpe | numeric | YES | — |
| duration_min | integer | YES | — |
| notes | text | YES | `''` |
| created_at | timestamptz | NO | `now()` |

- **Primary key:** `id`
- **Foreign keys:** `block_id` → `block(id)`, `ON DELETE SET NULL`.
- **Unique constraints/indexes:** `(date, day_key)` unique
  (`training_session_date_day_key_key`).
- **Check constraints:** `dow BETWEEN 1 AND 7`; `week_no BETWEEN 1 AND 12`.
- **RLS:** enabled, zero policies → default-deny.
- **Row count:** 0

---

## weight_logs

| Column | Type | Nullable | Default |
|---|---|---|---|
| id | uuid | NO | `gen_random_uuid()` |
| user_id | uuid | NO | — |
| log_date | date | NO | — |
| weight_kg | numeric | NO | — |
| created_at | timestamptz | YES | `now()` |

- **Primary key:** `id`
- **Foreign keys:** `user_id` → `auth.users(id)`, `ON DELETE NO ACTION`.
- **Unique constraints/indexes:** `(user_id, log_date)` unique
  (`weight_logs_user_id_log_date_key`) — one weight entry per user per day.
- **RLS:** enabled. One policy, **"own rows only"**: `PERMISSIVE`, `{public}`,
  `ALL`, `USING (auth.uid() = user_id)`, `WITH CHECK (auth.uid() = user_id)`.
- **Row count:** 1

---

## What `physique-os.html` actually touches

Verified by grepping every `sb.from(...)` call in the file, not by memory.

**Reads and writes (all three of these, and only these):**
- `daily_logs` — read on login/boot (today's row), `upsert` on every tick/edit.
- `weight_logs` — read (last 8, for the sparkline + today's value), `upsert`
  on editing today's weight.
- `lift_logs` — read (all rows, grouped client-side into today's sets vs.
  most recent prior session per exercise), delete+reinsert per exercise
  when a set is logged.

**Exist in Supabase but the frontend never touches — all 10 of them:**
`block`, `body_log`, `coach_note`, `exercise`, `lift_state`, `nutrition_log`,
`prescription_override`, `set_log`, `sleep_log`, `training_session`.

These aren't just unused — **they're currently unreachable from any
client using the anon/authenticated key**, because RLS is enabled on all of
them with no policies defined (default-deny). A feature built on top of one
of these would need an RLS policy added first (and, since none of them have
a `user_id` column, "own rows only" isn't directly applicable — they'd need
either a `user_id` column added, or a different access model, e.g. a policy
scoped to the single known user's UID, or continuing to access them only via
a service-role/direct connection rather than the browser client).
