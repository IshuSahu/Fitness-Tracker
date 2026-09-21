from __future__ import annotations
import datetime as dt
from typing import Optional
from pydantic import BaseModel, Field


class MealExtra(BaseModel):
    """Something eaten on top of a slot's chosen option."""
    label: str = ""
    kcal: float = Field(0, ge=0)
    protein_g: float = Field(0, ge=0)
    carbs_g: float = Field(0, ge=0)
    fat_g: float = Field(0, ge=0)


class MealSlot(BaseModel):
    """One meal slot on one day. The macros are stored on the day rather than
    looked up from the catalog, so editing the catalog can't rewrite history."""
    eaten: bool = False
    option_id: str = ""          # a catalog id, or "custom" for a typed entry
    name: str = ""
    kcal: float = Field(0, ge=0)
    protein_g: float = Field(0, ge=0)
    carbs_g: float = Field(0, ge=0)
    fat_g: float = Field(0, ge=0)
    # kept whether or not the slot is eaten; only counted toward totals when it is
    extras: list[MealExtra] = []


class DailyOut(BaseModel):
    water_l: float = 0
    meal_log: dict[str, MealSlot] = {}
    supplements: list[bool] = []
    kcal_eaten: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    sleep_hours: Optional[float] = None
    steps: Optional[int] = None
    streak: int = 0


class DailyIn(BaseModel):
    water_l: float = 0
    # None means the client didn't send it (a page loaded before meal_log
    # existed) -- the stored day is kept rather than overwritten with nothing.
    meal_log: Optional[dict[str, MealSlot]] = None
    supplements: list[bool] = []
    # kcal_eaten / protein_g / carbs_g / fat_g are not accepted from the client:
    # the server derives them from meal_log so they can never disagree with it.
    sleep_hours: Optional[float] = None
    steps: Optional[int] = None
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
    # true when this slot is running a one-day substitution; planned_* is what
    # the programme actually says, so the UI can offer to put it back
    swapped: bool = False
    planned_exercise_id: Optional[str] = None


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
    # A ramp-up set: recorded, but kept out of PRs, rep-target checks and the
    # working-set list.
    warmup: bool = False


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
