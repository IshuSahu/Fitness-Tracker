from __future__ import annotations
import datetime as dt
import json
from fastapi import APIRouter, Depends

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import DailyOut, DailyIn

router = APIRouter(prefix="/api/daily", tags=["daily"])


@router.get("/today", response_model=DailyOut)
async def get_today(user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    row = await pool.fetchrow(
        """select water_l, meals, supplements, sleep, kcal_eaten, protein_g,
                  carbs_g, fat_g, sleep_hours, streak
             from daily_logs where user_id = $1 and log_date = current_date""",
        user_id,
    )
    if not row:
        return DailyOut()
    return DailyOut(
        water_l=float(row["water_l"] or 0),
        meals=json.loads(row["meals"]) if isinstance(row["meals"], str) else (row["meals"] or []),
        supplements=json.loads(row["supplements"]) if isinstance(row["supplements"], str) else (row["supplements"] or []),
        sleep=json.loads(row["sleep"]) if isinstance(row["sleep"], str) else (row["sleep"] or {}),
        kcal_eaten=row["kcal_eaten"],
        protein_g=float(row["protein_g"]) if row["protein_g"] is not None else None,
        carbs_g=float(row["carbs_g"]) if row["carbs_g"] is not None else None,
        fat_g=float(row["fat_g"]) if row["fat_g"] is not None else None,
        sleep_hours=float(row["sleep_hours"]) if row["sleep_hours"] is not None else None,
        streak=row["streak"] or 0,
    )


@router.put("/today")
async def put_today(body: DailyIn, user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    await pool.execute(
        """insert into daily_logs (user_id, log_date, water_l, meals, supplements, sleep,
                                   kcal_eaten, protein_g, carbs_g, fat_g, sleep_hours, streak)
           values ($1, current_date, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6, $7, $8, $9, $10, $11)
           on conflict (user_id, log_date) do update set
             water_l = excluded.water_l, meals = excluded.meals,
             supplements = excluded.supplements, sleep = excluded.sleep,
             kcal_eaten = excluded.kcal_eaten, protein_g = excluded.protein_g,
             carbs_g = excluded.carbs_g, fat_g = excluded.fat_g,
             sleep_hours = excluded.sleep_hours, streak = excluded.streak""",
        user_id, body.water_l, json.dumps(body.meals), json.dumps(body.supplements),
        json.dumps(body.sleep), body.kcal_eaten, body.protein_g, body.carbs_g,
        body.fat_g, body.sleep_hours, body.streak,
    )
    return {"ok": True}
