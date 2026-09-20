from __future__ import annotations
import datetime as dt
import json
from fastapi import APIRouter, Depends, Query

from ..auth import verify_jwt
from ..db import get_pool, num
from ..schemas import DailyOut, DailyIn

router = APIRouter(prefix="/api/daily", tags=["daily"])


@router.get("", response_model=DailyOut)
async def get_daily(
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        """select water_l, meals, meal_choices, supplements, sleep, kcal_eaten,
                  protein_g, carbs_g, fat_g, sleep_hours, streak
             from daily_logs where user_id = $1 and log_date = $2""",
        user_id, date,
    )
    if not row:
        return DailyOut()
    return DailyOut(
        water_l=float(row["water_l"] or 0),
        meals=json.loads(row["meals"]) if isinstance(row["meals"], str) else (row["meals"] or []),
        meal_choices=json.loads(row["meal_choices"]) if isinstance(row["meal_choices"], str) else (row["meal_choices"] or []),
        supplements=json.loads(row["supplements"]) if isinstance(row["supplements"], str) else (row["supplements"] or []),
        sleep=json.loads(row["sleep"]) if isinstance(row["sleep"], str) else (row["sleep"] or {}),
        kcal_eaten=row["kcal_eaten"],
        protein_g=float(row["protein_g"]) if row["protein_g"] is not None else None,
        carbs_g=float(row["carbs_g"]) if row["carbs_g"] is not None else None,
        fat_g=float(row["fat_g"]) if row["fat_g"] is not None else None,
        sleep_hours=float(row["sleep_hours"]) if row["sleep_hours"] is not None else None,
        streak=row["streak"] or 0,
    )


@router.put("")
async def put_daily(
    body: DailyIn,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    await pool.execute(
        """insert into daily_logs (user_id, log_date, water_l, meals, meal_choices,
                                   supplements, sleep, kcal_eaten, protein_g, carbs_g,
                                   fat_g, sleep_hours, streak)
           values ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, $8, $9, $10, $11, $12, $13)
           on conflict (user_id, log_date) do update set
             water_l = excluded.water_l, meals = excluded.meals,
             meal_choices = excluded.meal_choices,
             supplements = excluded.supplements, sleep = excluded.sleep,
             kcal_eaten = excluded.kcal_eaten, protein_g = excluded.protein_g,
             carbs_g = excluded.carbs_g, fat_g = excluded.fat_g,
             sleep_hours = excluded.sleep_hours, streak = excluded.streak""",
        user_id, date, num(body.water_l), json.dumps(body.meals), json.dumps(body.meal_choices),
        json.dumps(body.supplements), json.dumps(body.sleep), body.kcal_eaten,
        num(body.protein_g), num(body.carbs_g), num(body.fat_g),
        num(body.sleep_hours), body.streak,
    )
    return {"ok": True}
