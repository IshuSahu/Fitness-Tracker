from __future__ import annotations
import datetime as dt
from typing import Optional
from pydantic import BaseModel, Field


class DailyOut(BaseModel):
    water_l: float = 0
    meals: list[bool] = []
    supplements: list[bool] = []
    sleep: dict = {}
    kcal_eaten: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    sleep_hours: Optional[float] = None
    streak: int = 0


class DailyIn(BaseModel):
    water_l: float = 0
    meals: list[bool] = []
    supplements: list[bool] = []
    sleep: dict = {}
    kcal_eaten: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    sleep_hours: Optional[float] = None
    streak: int = 0


class WeightEntry(BaseModel):
    log_date: str
    weight_kg: float


class WeightIn(BaseModel):
    weight_kg: float


class PlanExercise(BaseModel):
    order_no: int
    exercise_id: str
    name: str
    mode: str
    sets: int
    rep_lo: int
    rep_hi: int
    cue: str
    alt: str
    anim: str
    muscles: list[str]
    overridden: bool
    override_note: str = ""
    override_load_kg: Optional[float] = None


class PlanOut(BaseModel):
    day_key: str
    week_no: int
    block_name: Optional[str] = None
    exercises: list[PlanExercise]


class LiftStateEntry(BaseModel):
    last_date: Optional[str] = None
    last_sets: list = []
    consecutive_misses: int = 0
    best_e1rm_kg: float = 0
    best_e1rm_date: Optional[str] = None
    sessions_logged: int = 0


class SetIn(BaseModel):
    exercise_id: str
    weight_kg: Optional[float] = None
    reps: int
    # Explicit index lets an already-logged set be corrected in place. Without
    # it the server appends, deriving the index from a live count -- which also
    # races when two sets are posted in quick succession.
    set_index: Optional[int] = Field(None, ge=0)
    # The date the set belongs to; day_key and week_no are derived from it.
    date: Optional[dt.date] = None


class CoachUpdateEntry(BaseModel):
    exercise_id: str
    load_kg: Optional[float] = None
    sets: Optional[int] = None
    rep_lo: Optional[int] = None
    rep_hi: Optional[int] = None
    note: Optional[str] = None


class CoachSwapEntry(BaseModel):
    day_key: str
    order_no: int
    new_exercise_id: str
    reason: Optional[str] = None


class CoachUpdateIn(BaseModel):
    week_no: int
    note: str = ""
    updates: list[CoachUpdateEntry] = []
    swaps: list[CoachSwapEntry] = []


class ReportOut(BaseModel):
    report: str
