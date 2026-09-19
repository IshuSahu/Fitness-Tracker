from __future__ import annotations
import datetime as dt
import json
import time
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import LiftStateEntry, SetIn
from .plan import week_no_for
from .day_plan import resolve_day_key

router = APIRouter(prefix="/api", tags=["lifts"])

DOW_KEYS = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}

# The active block is a single row whose start_date doesn't change mid-workout,
# but re-reading it on every set cost a full round-trip. Short TTL so starting
# a new block still takes effect without a restart.
_BLOCK_TTL_S = 300
_block_cache: tuple[float, asyncpg.Record | None] | None = None


async def _active_block(conn) -> asyncpg.Record | None:
    global _block_cache
    now = time.monotonic()
    if _block_cache is None or now - _block_cache[0] > _BLOCK_TTL_S:
        row = await conn.fetchrow(
            "select id, start_date from block where active order by id desc limit 1"
        )
        _block_cache = (now, row)
    return _block_cache[1]


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


@router.get("/sets")
async def get_sets(
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
) -> dict[str, list[dict]]:
    """Sets actually logged on `date`, keyed by exercise_id. lift_state only
    ever holds the most recently written session, so it can't answer this once
    backdating is in play -- this reads set_log for the date directly."""
    pool = await get_pool()
    rows = await pool.fetch(
        """select sl.exercise_id, sl.set_index, sl.load_kg, sl.reps
             from set_log sl
             join training_session ts on ts.id = sl.session_id
            where ts.date = $1 and sl.warmup = false
            order by sl.exercise_id, sl.set_index""",
        date,
    )
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["exercise_id"], []).append(
            {"load_kg": float(r["load_kg"]) if r["load_kg"] is not None else None,
             "reps": r["reps"]}
        )
    return out


@router.post("/sets", response_model=LiftStateEntry)
async def post_set(body: SetIn, user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    log_date = body.date or dt.date.today()
    dow = log_date.isoweekday()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # the programme being run, which isn't always the weekday's default
            day_key = await resolve_day_key(conn, log_date)
            block = await _active_block(conn)
            week_no = week_no_for(block["start_date"], log_date) if block else 1
            block_id = block["id"] if block else None

            session = await conn.fetchrow(
                """insert into training_session (block_id, date, dow, week_no, day_key)
                   values ($1, $2, $3, $4, $5)
                   on conflict (date, day_key) do update set date = excluded.date
                   returning id""",
                block_id, log_date, dow, week_no, day_key,
            )
            session_id = session["id"]

            if body.set_index is not None:
                set_index = body.set_index
            else:
                set_index = await conn.fetchval(
                    """select count(*) from set_log
                        where session_id = $1 and exercise_id = $2 and warmup = false""",
                    session_id, body.exercise_id,
                )

            try:
                new_set = await conn.fetchrow(
                    """insert into set_log (session_id, exercise_id, set_index, load_kg, reps, warmup)
                       values ($1, $2, $3, $4, $5, false)
                       on conflict (session_id, exercise_id, set_index) do update set
                         load_kg = excluded.load_kg, reps = excluded.reps
                       returning e1rm_kg""",
                    session_id, body.exercise_id, set_index, body.weight_kg, body.reps,
                )
            except asyncpg.ForeignKeyViolationError:
                raise HTTPException(404, f"Unknown exercise_id '{body.exercise_id}'.")
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
            # 1) prescription_override for (week_no, exercise_id), 2) this day's
            # session_template row for (day_key, exercise_id), 3) if neither,
            # leave consecutive_misses untouched -- off-plan exercise, no target
            target_rep_lo = await conn.fetchval(
                """select coalesce(
                     (select rep_lo from prescription_override
                       where week_no = $1 and exercise_id = $2),
                     (select base_rep_lo from session_template
                       where day_key = $3 and exercise_id = $2))""",
                week_no, body.exercise_id, day_key,
            )
            missed = target_rep_lo is not None and best_reps_this_session < target_rep_lo

            # best_e1rm_kg/date: pass this set's e1rm and date as the
            # *candidate*; greatest()/CASE below decide the real winner against
            # whatever's in the row, so there's no read-then-write race on it.
            # consecutive_misses and sessions_logged used to need their own
            # SELECTs first; both are derivable here from lift_state.* (the
            # pre-update row) versus excluded.* (this write).
            row = await conn.fetchrow(
                """insert into lift_state (exercise_id, last_session_id, last_date, last_sets,
                                           consecutive_misses, best_e1rm_kg, best_e1rm_date,
                                           sessions_logged, updated_at)
                   values ($1, $2, $3, $4::jsonb, case when $8 then 1 else 0 end, $5, $6, 1, now())
                   on conflict (exercise_id) do update set
                     last_session_id = excluded.last_session_id,
                     last_date = excluded.last_date,
                     last_sets = excluded.last_sets,
                     consecutive_misses = case
                       when not $7 then lift_state.consecutive_misses
                       when $8 then lift_state.consecutive_misses + 1
                       else 0 end,
                     best_e1rm_kg = greatest(lift_state.best_e1rm_kg, excluded.best_e1rm_kg),
                     best_e1rm_date = case when excluded.best_e1rm_kg > lift_state.best_e1rm_kg
                                            then excluded.best_e1rm_date else lift_state.best_e1rm_date end,
                     sessions_logged = lift_state.sessions_logged + case
                       when lift_state.last_session_id is distinct from excluded.last_session_id
                       then 1 else 0 end,
                     updated_at = now()
                   returning last_date, last_sets, consecutive_misses, best_e1rm_kg,
                             best_e1rm_date, sessions_logged""",
                body.exercise_id, session_id, log_date, json.dumps(last_sets),
                new_e1rm, log_date, target_rep_lo is not None, missed,
            )

    return LiftStateEntry(
        last_date=str(row["last_date"]) if row["last_date"] else None,
        last_sets=json.loads(row["last_sets"]) if isinstance(row["last_sets"], str) else (row["last_sets"] or []),
        consecutive_misses=row["consecutive_misses"] or 0,
        best_e1rm_kg=float(row["best_e1rm_kg"] or 0),
        best_e1rm_date=str(row["best_e1rm_date"]) if row["best_e1rm_date"] else None,
        sessions_logged=row["sessions_logged"] or 0,
    )
