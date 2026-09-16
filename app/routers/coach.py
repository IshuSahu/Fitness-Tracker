from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import CoachUpdateIn

router = APIRouter(prefix="/api/coach", tags=["coach"])


@router.post("/update")
async def coach_update(body: CoachUpdateIn, user_id: str = Depends(verify_jwt)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "insert into coach_note (week_no, body, patch) values ($1, $2, $3::jsonb)",
                body.week_no, body.note, body.model_dump_json(),
            )

            for u in body.updates:
                ex = await conn.fetchval("select id from exercise where id = $1", u.exercise_id)
                if not ex:
                    raise HTTPException(404, f"Unknown exercise_id '{u.exercise_id}'.")
                await conn.execute(
                    """insert into prescription_override (week_no, exercise_id, sets, rep_lo, rep_hi, load_kg, note)
                       values ($1, $2, $3, $4, $5, $6, $7)
                       on conflict (week_no, exercise_id) do update set
                         sets = excluded.sets, rep_lo = excluded.rep_lo, rep_hi = excluded.rep_hi,
                         load_kg = excluded.load_kg, note = excluded.note""",
                    body.week_no, u.exercise_id, u.sets, u.rep_lo, u.rep_hi, u.load_kg, u.note or "",
                )

            for s in body.swaps:
                new_ex = await conn.fetchval("select id from exercise where id = $1", s.new_exercise_id)
                if not new_ex:
                    raise HTTPException(404, f"Unknown exercise_id '{s.new_exercise_id}'.")
                result = await conn.execute(
                    """update session_template set exercise_id = $1
                        where day_key = $2 and order_no = $3""",
                    s.new_exercise_id, s.day_key, s.order_no,
                )
                if result == "UPDATE 0":
                    raise HTTPException(404, f"No session_template row for {s.day_key}/{s.order_no}.")

    return {"status": "ok", "week_no": body.week_no}
