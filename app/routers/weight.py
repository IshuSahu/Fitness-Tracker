from __future__ import annotations
from fastapi import APIRouter, Depends, Query

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import WeightEntry, WeightIn

router = APIRouter(prefix="/api/weight", tags=["weight"])


@router.get("", response_model=list[WeightEntry])
async def list_weight(limit: int = Query(8, ge=1, le=100), user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    rows = await pool.fetch(
        """select log_date, weight_kg from weight_logs
            where user_id = $1 order by log_date desc limit $2""",
        user_id, limit,
    )
    return [WeightEntry(log_date=str(r["log_date"]), weight_kg=float(r["weight_kg"])) for r in reversed(rows)]


@router.put("/today")
async def put_today(body: WeightIn, user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    await pool.execute(
        """insert into weight_logs (user_id, log_date, weight_kg)
           values ($1, current_date, $2)
           on conflict (user_id, log_date) do update set weight_kg = excluded.weight_kg""",
        user_id, body.weight_kg,
    )
    return {"ok": True}
