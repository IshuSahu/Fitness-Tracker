"""Which programme a date runs, when it isn't that weekday's default.

Miss Tuesday's Pull A and you want to run it on Wednesday. The weekday still
provides the default; a row in `day_plan` overrides it for one date.

The one rule: once a set has been logged for a date, that date's programme is
settled. Re-pointing it afterwards would leave the logged sets filed under a
session they were never part of."""
from __future__ import annotations
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import verify_jwt
from ..db import get_pool

router = APIRouter(prefix="/api/day-plan", tags=["day-plan"])

DOW_KEYS = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}
VALID_DAYS = set(DOW_KEYS.values())


class DayPlanIn(BaseModel):
    day_key: str


async def resolve_day_key(conn, date: dt.date) -> str:
    """The programme for `date`: an explicit override if one exists, else the
    weekday default. Shared with lifts.post_set so a logged set is filed under
    the programme actually being run."""
    override = await conn.fetchval("select day_key from day_plan where log_date = $1", date)
    return override or DOW_KEYS[date.isoweekday()]


async def _sets_logged_on(conn, date: dt.date) -> int:
    return await conn.fetchval(
        """select count(*) from set_log sl
             join training_session ts on ts.id = sl.session_id
            where ts.date = $1""",
        date,
    )


@router.get("")
async def get_day_plan(
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        override = await conn.fetchval("select day_key from day_plan where log_date = $1", date)
        locked = await _sets_logged_on(conn, date) > 0
    return {
        "day_key": override or DOW_KEYS[date.isoweekday()],
        "source": "override" if override else "weekday",
        "locked": locked,
    }


@router.put("")
async def put_day_plan(
    body: DayPlanIn,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    if body.day_key not in VALID_DAYS:
        raise HTTPException(422, f"Unknown day_key '{body.day_key}'.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        if await _sets_logged_on(conn, date) > 0:
            raise HTTPException(
                409, "Sets are already logged for this date -- its workout is settled."
            )
        await conn.execute(
            """insert into day_plan (log_date, day_key) values ($1, $2)
               on conflict (log_date) do update set day_key = excluded.day_key""",
            date, body.day_key,
        )
    return {"day_key": body.day_key, "source": "override", "locked": False}


@router.delete("")
async def delete_day_plan(
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    """Back to the weekday default."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if await _sets_logged_on(conn, date) > 0:
            raise HTTPException(
                409, "Sets are already logged for this date -- its workout is settled."
            )
        await conn.execute("delete from day_plan where log_date = $1", date)
    return {"day_key": DOW_KEYS[date.isoweekday()], "source": "weekday", "locked": False}
