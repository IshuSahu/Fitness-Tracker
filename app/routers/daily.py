from __future__ import annotations
import datetime as dt
import json
from fastapi import APIRouter, Depends, Query

from ..auth import verify_jwt
from ..db import get_pool, num
from ..schemas import DailyOut, DailyIn

router = APIRouter(prefix="/api/daily", tags=["daily"])

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")


def meal_totals(meal_log: dict) -> dict:
    """Each eaten slot's own macros plus all of its extras. This is the only
    place kcal_eaten and friends are computed, so the stored totals -- which
    weekly_report reads -- can't disagree with meal_log."""
    t = dict.fromkeys(MACROS, 0.0)
    for slot in meal_log.values():
        if not slot.get("eaten"):
            continue
        for k in MACROS:
            t[k] += float(slot.get(k) or 0)
            t[k] += sum(float(e.get(k) or 0) for e in slot.get("extras") or [])
    return t


def _json(v, empty):
    return json.loads(v) if isinstance(v, str) else (v or empty)


@router.get("", response_model=DailyOut)
async def get_daily(
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        """select water_l, meal_log, supplements, sleep, kcal_eaten,
                  protein_g, carbs_g, fat_g, sleep_hours, steps, streak
             from daily_logs where user_id = $1 and log_date = $2""",
        user_id, date,
    )
    if not row:
        return DailyOut()
    return DailyOut(
        water_l=float(row["water_l"] or 0),
        meal_log=_json(row["meal_log"], {}),
        supplements=_json(row["supplements"], []),
        sleep=_json(row["sleep"], {}),
        kcal_eaten=row["kcal_eaten"],
        protein_g=float(row["protein_g"]) if row["protein_g"] is not None else None,
        carbs_g=float(row["carbs_g"]) if row["carbs_g"] is not None else None,
        fat_g=float(row["fat_g"]) if row["fat_g"] is not None else None,
        sleep_hours=float(row["sleep_hours"]) if row["sleep_hours"] is not None else None,
        steps=row["steps"],
        streak=row["streak"] or 0,
    )


@router.put("")
async def put_daily(
    body: DailyIn,
    date: dt.date = Query(default_factory=dt.date.today),
    user_id: str = Depends(verify_jwt),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if body.meal_log is not None:
            meal_log = {slot: v.model_dump() for slot, v in body.meal_log.items()}
        else:
            # A page loaded before meal_log existed doesn't send it; keep the
            # stored day instead of overwriting it with nothing.
            meal_log = _json(await conn.fetchval(
                "select meal_log from daily_logs where user_id = $1 and log_date = $2",
                user_id, date), {})
        t = meal_totals(meal_log)
        await conn.execute(
            """insert into daily_logs (user_id, log_date, water_l, meal_log, supplements,
                                       sleep, kcal_eaten, protein_g, carbs_g, fat_g,
                                       sleep_hours, steps, streak)
               values ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7, $8, $9, $10, $11, $12, $13)
               on conflict (user_id, log_date) do update set
                 water_l = excluded.water_l, meal_log = excluded.meal_log,
                 supplements = excluded.supplements, sleep = excluded.sleep,
                 kcal_eaten = excluded.kcal_eaten, protein_g = excluded.protein_g,
                 carbs_g = excluded.carbs_g, fat_g = excluded.fat_g,
                 sleep_hours = excluded.sleep_hours, steps = excluded.steps,
                 streak = excluded.streak""",
            user_id, date, num(body.water_l), json.dumps(meal_log),
            json.dumps(body.supplements), json.dumps(body.sleep),
            # half-up, not round()'s half-to-even: the ring rounds 1390.5 to 1391
            # with Math.round, and the stored figure must match what was shown
            int(t["kcal"] + 0.5), num(t["protein_g"]), num(t["carbs_g"]), num(t["fat_g"]),
            num(body.sleep_hours), body.steps, body.streak,
        )
    return {"ok": True}
