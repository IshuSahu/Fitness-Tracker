"""Substituting one exercise for another, for a single day.

The bench you wanted is taken, so you do the machine version instead. That's a
fact about today, not a change to the programme -- so it's stored per date and
per slot, and `session_template` is never touched.

Candidates come from the catalogue itself: `muscle_group` is far too coarse
(29 of 48 rows are just "upper"), so alternatives are exercises sharing at
least one entry in `muscles` and the same `kind`, which keeps a compound
pressing movement from being offered a bicep curl as a replacement."""
from __future__ import annotations
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import verify_jwt
from ..db import get_pool
from .day_plan import resolve_day_key

router = APIRouter(prefix="/api", tags=["exercises"])


class SwapIn(BaseModel):
    order_no: int
    exercise_id: str


@router.get("/exercise-alternatives/{exercise_id}")
async def alternatives(
    exercise_id: str,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        src = await conn.fetchrow(
            "select id, name, kind, muscles, equipment from exercise where id = $1", exercise_id
        )
        if not src:
            raise HTTPException(404, f"Unknown exercise_id '{exercise_id}'.")
        day_key = await resolve_day_key(conn, date)
        rows = await conn.fetch(
            """select e.id, e.name, e.equipment, e.muscles, e.kind
                 from exercise e
                where e.id <> $1
                  and e.kind = $2
                  and e.muscles && $3::text[]
                  -- don't offer something already programmed for the day, or
                  -- it'd appear twice in the same session
                  and e.id not in (
                    select st.exercise_id from session_template st where st.day_key = $4)
                order by cardinality(array(select unnest(e.muscles) intersect select unnest($3::text[]))) desc,
                         e.name""",
            exercise_id, src["kind"], list(src["muscles"] or []), day_key,
        )
    return {
        "replacing": {"id": src["id"], "name": src["name"], "equipment": src["equipment"]},
        "alternatives": [
            {"id": r["id"], "name": r["name"], "equipment": r["equipment"],
             "muscles": list(r["muscles"] or [])}
            for r in rows
        ],
    }


@router.put("/exercise-swap")
async def put_swap(
    body: SwapIn,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        current = await _slot_exercise(conn, date, body.order_no)
        if current is None:
            raise HTTPException(404, f"No exercise at slot {body.order_no} for this day.")
        if await _sets_logged_for(conn, date, current) > 0:
            raise HTTPException(
                409, f"Sets are already logged for '{current}' today -- swapping it now "
                     "would leave them filed under an exercise you didn't do."
            )
        try:
            await conn.execute(
                """insert into exercise_swap (log_date, order_no, exercise_id)
                   values ($1, $2, $3)
                   on conflict (log_date, order_no) do update set exercise_id = excluded.exercise_id""",
                date, body.order_no, body.exercise_id,
            )
        except Exception as e:
            if "foreign key" in str(e).lower():
                raise HTTPException(404, f"Unknown exercise_id '{body.exercise_id}'.")
            raise
    return {"order_no": body.order_no, "exercise_id": body.exercise_id}


@router.delete("/exercise-swap")
async def delete_swap(
    order_no: int,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    """Back to whatever the programme says for that slot."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        current = await _slot_exercise(conn, date, order_no)
        if current is not None and await _sets_logged_for(conn, date, current) > 0:
            raise HTTPException(
                409, f"Sets are already logged for '{current}' today."
            )
        await conn.execute(
            "delete from exercise_swap where log_date = $1 and order_no = $2", date, order_no
        )
    return {"order_no": order_no, "reverted": True}


async def _slot_exercise(conn, date: dt.date, order_no: int) -> str | None:
    """What that slot currently resolves to -- the swap if one is set, else the
    template's exercise for the day's programme."""
    swapped = await conn.fetchval(
        "select exercise_id from exercise_swap where log_date = $1 and order_no = $2",
        date, order_no,
    )
    if swapped:
        return swapped
    day_key = await resolve_day_key(conn, date)
    return await conn.fetchval(
        "select exercise_id from session_template where day_key = $1 and order_no = $2",
        day_key, order_no,
    )


async def _sets_logged_for(conn, date: dt.date, exercise_id: str) -> int:
    return await conn.fetchval(
        """select count(*) from set_log sl
             join training_session ts on ts.id = sl.session_id
            where ts.date = $1 and sl.exercise_id = $2""",
        date, exercise_id,
    )
