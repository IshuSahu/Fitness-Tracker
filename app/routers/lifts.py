from __future__ import annotations
import datetime as dt
import json
from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import LiftStateEntry, SetIn
from .plan import week_no_for

router = APIRouter(prefix="/api", tags=["lifts"])

DOW_KEYS = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


@router.get("/lift-state")
async def get_lift_state(user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    rows = await pool.fetch(
        """select exercise_id, last_date, last_sets, consecutive_misses,
                  best_e1rm_kg, best_e1rm_date, sessions_logged
             from lift_state"""
    )
    out: dict[str, LiftStateEntry] = {}
    for r in rows:
        out[r["exercise_id"]] = LiftStateEntry(
            last_date=str(r["last_date"]) if r["last_date"] else None,
            last_sets=json.loads(r["last_sets"]) if isinstance(r["last_sets"], str) else (r["last_sets"] or []),
            consecutive_misses=r["consecutive_misses"] or 0,
            best_e1rm_kg=float(r["best_e1rm_kg"] or 0),
            best_e1rm_date=str(r["best_e1rm_date"]) if r["best_e1rm_date"] else None,
            sessions_logged=r["sessions_logged"] or 0,
        )
    return out


@router.post("/sets", response_model=LiftStateEntry)
async def post_set(body: SetIn, user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    today = dt.date.today()
    dow = today.isoweekday()
    day_key = DOW_KEYS[dow]

    async with pool.acquire() as conn:
        async with conn.transaction():
            block = await conn.fetchrow(
                "select id, start_date from block where active order by id desc limit 1"
            )
            week_no = week_no_for(block["start_date"], today) if block else 1
            block_id = block["id"] if block else None

            ex = await conn.fetchrow("select id from exercise where id = $1", body.exercise_id)
            if not ex:
                raise HTTPException(404, f"Unknown exercise_id '{body.exercise_id}'.")

            session = await conn.fetchrow(
                """insert into training_session (block_id, date, dow, week_no, day_key)
                   values ($1, $2, $3, $4, $5)
                   on conflict (date, day_key) do update set date = excluded.date
                   returning id""",
                block_id, today, dow, week_no, day_key,
            )
            session_id = session["id"]

            was_first_set_this_session = await conn.fetchval(
                "select last_session_id is distinct from $1 from lift_state where exercise_id = $2",
                session_id, body.exercise_id,
            )
            if was_first_set_this_session is None:
                was_first_set_this_session = True

            existing_count = await conn.fetchval(
                """select count(*) from set_log
                    where session_id = $1 and exercise_id = $2 and warmup = false""",
                session_id, body.exercise_id,
            )
            set_index = existing_count

            new_set = await conn.fetchrow(
                """insert into set_log (session_id, exercise_id, set_index, load_kg, reps, warmup)
                   values ($1, $2, $3, $4, $5, false)
                   on conflict (session_id, exercise_id, set_index) do update set
                     load_kg = excluded.load_kg, reps = excluded.reps
                   returning e1rm_kg""",
                session_id, body.exercise_id, set_index, body.weight_kg, body.reps,
            )
            # e1RM is meaningless without a load (bodyweight/timed exercises);
            # the generated column already resolves to 0 for a NULL/<=0 load,
            # so best_e1rm_kg simply won't move for these -- correct.
            new_e1rm = float(new_set["e1rm_kg"] or 0)

            session_sets = await conn.fetch(
                """select load_kg, reps from set_log
                    where session_id = $1 and exercise_id = $2 and warmup = false
                    order by set_index""",
                session_id, body.exercise_id,
            )
            last_sets = [
                {"load_kg": float(s["load_kg"]) if s["load_kg"] is not None else None, "reps": s["reps"]}
                for s in session_sets
            ]
            best_reps_this_session = max(s["reps"] for s in last_sets)

            # rep-range target precedence for consecutive_misses:
            # 1) prescription_override for (week_no, exercise_id), 2) today's
            # session_template row for (day_key, exercise_id), 3) if neither,
            # leave consecutive_misses untouched -- off-plan exercise, no target
            target_rep_lo = await conn.fetchval(
                "select rep_lo from prescription_override where week_no = $1 and exercise_id = $2",
                week_no, body.exercise_id,
            )
            template_row = None
            if target_rep_lo is None:
                template_row = await conn.fetchrow(
                    "select base_rep_lo from session_template where day_key = $1 and exercise_id = $2",
                    day_key, body.exercise_id,
                )
                if template_row:
                    target_rep_lo = template_row["base_rep_lo"]

            cur_misses = await conn.fetchval(
                "select consecutive_misses from lift_state where exercise_id = $1", body.exercise_id
            ) or 0
            if target_rep_lo is not None:
                new_misses = cur_misses + 1 if best_reps_this_session < target_rep_lo else 0
            else:
                new_misses = cur_misses  # off-plan exercise: no target, leave unchanged

            # best_e1rm_kg/date: pass this set's e1rm/today as the *candidate*;
            # greatest()/CASE below decide the real winner against whatever's
            # actually in the row, so there's no read-then-write race on it.
            row = await conn.fetchrow(
                """insert into lift_state (exercise_id, last_session_id, last_date, last_sets,
                                           consecutive_misses, best_e1rm_kg, best_e1rm_date,
                                           sessions_logged, updated_at)
                   values ($1, $2, $3, $4::jsonb, $5, $6, $7, 1, now())
                   on conflict (exercise_id) do update set
                     last_session_id = excluded.last_session_id,
                     last_date = excluded.last_date,
                     last_sets = excluded.last_sets,
                     consecutive_misses = excluded.consecutive_misses,
                     best_e1rm_kg = greatest(lift_state.best_e1rm_kg, excluded.best_e1rm_kg),
                     best_e1rm_date = case when excluded.best_e1rm_kg > lift_state.best_e1rm_kg
                                            then excluded.best_e1rm_date else lift_state.best_e1rm_date end,
                     sessions_logged = lift_state.sessions_logged + case when $8 then 1 else 0 end,
                     updated_at = now()
                   returning last_date, last_sets, consecutive_misses, best_e1rm_kg,
                             best_e1rm_date, sessions_logged""",
                body.exercise_id, session_id, today, json.dumps(last_sets), new_misses,
                new_e1rm, today, bool(was_first_set_this_session),
            )

    return LiftStateEntry(
        last_date=str(row["last_date"]) if row["last_date"] else None,
        last_sets=json.loads(row["last_sets"]) if isinstance(row["last_sets"], str) else (row["last_sets"] or []),
        consecutive_misses=row["consecutive_misses"] or 0,
        best_e1rm_kg=float(row["best_e1rm_kg"] or 0),
        best_e1rm_date=str(row["best_e1rm_date"]) if row["best_e1rm_date"] else None,
        sessions_logged=row["sessions_logged"] or 0,
    )
