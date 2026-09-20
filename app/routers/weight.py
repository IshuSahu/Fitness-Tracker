from __future__ import annotations
import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..auth import verify_jwt
from ..db import get_pool, num
from ..schemas import WeightEntry, WeightIn

router = APIRouter(prefix="/api/weight", tags=["weight"])


@router.get("", response_model=list[WeightEntry])
async def list_weight(
    limit: int = Query(8, ge=1, le=100),
    date: Optional[dt.date] = Query(None),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    rows = await pool.fetch(
        """select log_date, weight_kg from weight_logs
            where user_id = $1 order by log_date desc limit $2""",
        user_id, limit,
    )
    # The sparkline/trend always reflects the real recent history regardless
    # of which date is being edited. But if `date` (the date currently being
    # logged for) falls outside that window -- e.g. editing an entry from
    # months back -- make sure its row is still included so the edit field
    # isn't silently blank just because it's not "recent".
    if date is not None and not any(r["log_date"] == date for r in rows):
        extra = await pool.fetchrow(
            "select log_date, weight_kg from weight_logs where user_id = $1 and log_date = $2",
            user_id, date,
        )
        if extra:
            rows = [*rows, extra]
    return [WeightEntry(log_date=str(r["log_date"]), weight_kg=float(r["weight_kg"])) for r in reversed(rows)]


@router.put("")
async def put_weight(
    body: WeightIn,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    await pool.execute(
        """insert into weight_logs (user_id, log_date, weight_kg)
           values ($1, $2, $3)
           on conflict (user_id, log_date) do update set weight_kg = excluded.weight_kg""",
        user_id, date, num(body.weight_kg),
    )
    return {"ok": True}
