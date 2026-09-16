from __future__ import annotations
import datetime as dt
from fastapi import APIRouter, Depends, Query

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import ReportOut

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/weekly", response_model=ReportOut)
async def weekly_report(
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    try:
        text = await pool.fetchval("select weekly_report($1, $2, $3)", start, end, user_id)
        return ReportOut(report=text or "No data for this range.")
    except Exception as e:
        # Deliberately a 200 with the error as text, not a 500 -- the
        # frontend just displays whatever comes back in `report`.
        return ReportOut(report=f"Could not generate the report: {e}")
