from __future__ import annotations
import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import verify_jwt
from ..db import get_pool
from ..schemas import PlanOut, PlanExercise

router = APIRouter(prefix="/api/plan", tags=["plan"])


def week_no_for(start_date: dt.date, today: dt.date) -> int:
    delta_weeks = (today - start_date).days // 7 + 1
    return max(1, min(52, delta_weeks))


@router.get("/{day_key}", response_model=PlanOut)
async def get_plan(
    day_key: str,
    date: Optional[dt.date] = Query(None),
    user_id: str = Depends(verify_jwt),
):
    if day_key not in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
        raise HTTPException(404, "Unknown day_key.")
    pool = await get_pool()

    block = await pool.fetchrow(
        "select id, name, start_date from block where active order by id desc limit 1"
    )
    for_date = date or dt.date.today()
    week_no = week_no_for(block["start_date"], for_date) if block else 1

    # A swap replaces the slot's exercise for this date only; the prescription
    # override still keys off whatever exercise ends up in the slot.
    rows = await pool.fetch(
        """select st.order_no,
                  coalesce(sw.exercise_id, st.exercise_id) as exercise_id,
                  (sw.exercise_id is not null) as swapped,
                  st.exercise_id as planned_exercise_id,
                  e.name, e.mode, e.cue, e.alt, e.anim, e.muscles,
                  st.base_sets, st.base_rep_lo, st.base_rep_hi,
                  po.sets as ov_sets, po.rep_lo as ov_rep_lo, po.rep_hi as ov_rep_hi,
                  po.load_kg as ov_load_kg, po.note as ov_note
             from session_template st
             left join exercise_swap sw
               on sw.log_date = $3 and sw.order_no = st.order_no
             join exercise e on e.id = coalesce(sw.exercise_id, st.exercise_id)
             left join prescription_override po
               on po.week_no = $1 and po.exercise_id = coalesce(sw.exercise_id, st.exercise_id)
            where st.day_key = $2
            order by st.order_no""",
        week_no, day_key, for_date,
    )

    exercises = [
        PlanExercise(
            order_no=r["order_no"],
            exercise_id=r["exercise_id"],
            name=r["name"],
            mode=r["mode"],
            sets=r["ov_sets"] or r["base_sets"],
            rep_lo=r["ov_rep_lo"] or r["base_rep_lo"],
            rep_hi=r["ov_rep_hi"] or r["base_rep_hi"],
            cue=r["cue"] or "",
            alt=r["alt"] or "",
            anim=r["anim"] or "",
            muscles=list(r["muscles"] or []),
            overridden=r["ov_sets"] is not None or r["ov_rep_lo"] is not None
                       or r["ov_rep_hi"] is not None or r["ov_load_kg"] is not None,
            override_note=r["ov_note"] or "",
            override_load_kg=float(r["ov_load_kg"]) if r["ov_load_kg"] is not None else None,
            swapped=r["swapped"],
            planned_exercise_id=r["planned_exercise_id"],
        )
        for r in rows
    ]
    return PlanOut(
        day_key=day_key, week_no=week_no,
        block_name=block["name"] if block else None,
        exercises=exercises,
    )
