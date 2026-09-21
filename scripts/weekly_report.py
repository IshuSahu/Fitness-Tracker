"""Generate the weekly report as a text file, for sending to a coach.

Backend only -- there is deliberately no UI for this. Run it, hand the file
over, and bring any changes the coach asks for back into the plan.

    python scripts/weekly_report.py                # the last 7 days
    python scripts/weekly_report.py 2026-09-14     # the week starting then
    python scripts/weekly_report.py 2026-09-14 2026-09-20

Beyond what was logged, the report lists the full exercise catalogue and every
meal option, with their ids. That's what makes it actionable: the coach can
write "mon slot 3 -> pec-deck" or "breakfast -> option 2" and it maps straight
onto the data.
"""
from __future__ import annotations
import asyncio
import datetime as dt
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.db import get_pool, close_pool  # noqa: E402

DAY_NAMES = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}


def meal_options() -> list:
    """Read MEAL_OPTIONS out of the dashboard rather than keeping a second
    copy here -- two lists of meals would drift within a week."""
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    start = html.index("const MEAL_OPTIONS = [")
    end = html.index("\n];", start) + 3
    script = html[start:end] + "\nconsole.log(JSON.stringify(MEAL_OPTIONS));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return json.loads(out.stdout)


def wrap(text: str, width: int = 78, indent: str = "") -> str:
    words, lines, cur = text.split(), [], indent
    for w in words:
        if len(cur) + len(w) + 1 > width and cur.strip():
            lines.append(cur.rstrip())
            cur = indent + w + " "
        else:
            cur += w + " "
    if cur.strip():
        lines.append(cur.rstrip())
    return "\n".join(lines)


async def build(start: dt.date, end: dt.date) -> str:
    pool = await get_pool()
    user_id = os.environ["ALLOWED_USER_ID"]
    out: list[str] = []
    add = out.append

    add("=" * 78)
    add(f"  PHYSIQUE OS — WEEKLY REPORT".center(78))
    add(f"  {start:%d %b %Y} to {end:%d %b %Y}".center(78))
    add("=" * 78)

    # ---- 1. what actually happened -------------------------------------
    body = await pool.fetchval("select weekly_report($1, $2, $3)", start, end, user_id)
    add("")
    add(body or "No data for this range.")

    # ---- 2. what the programme currently says ---------------------------
    add("")
    add("-" * 78)
    add("CURRENT PROGRAMME")
    add("-" * 78)
    add(wrap("What is scheduled each day, before any one-off substitutions. "
             "Slot numbers are stable -- use them to specify a change."))
    rows = await pool.fetch(
        """select st.day_key, st.order_no, st.exercise_id, e.name,
                  st.base_sets, st.base_rep_lo, st.base_rep_hi, e.mode
             from session_template st join exercise e on e.id = st.exercise_id
            order by array_position(array['mon','tue','wed','thu','fri','sat','sun'], st.day_key),
                     st.order_no"""
    )
    cur_day = None
    for r in rows:
        if r["day_key"] != cur_day:
            cur_day = r["day_key"]
            add("")
            add(f"  {DAY_NAMES[cur_day]} ({cur_day})")
        rng = (str(r["base_rep_lo"]) if r["base_rep_lo"] == r["base_rep_hi"]
               else f"{r['base_rep_lo']}-{r['base_rep_hi']}")
        unit = {"time": "sec", "mins": "min", "reps": "reps"}.get(r["mode"], "")
        add(f"    {r['order_no']}. {r['name']:<38} {r['base_sets']} x {rng} {unit}".rstrip()
            + f"   [{r['exercise_id']}]")

    # ---- 3. one-off substitutions in the week ---------------------------
    swaps = await pool.fetch(
        """select sw.log_date, sw.order_no, sw.exercise_id, e.name
             from exercise_swap sw join exercise e on e.id = sw.exercise_id
            where sw.log_date between $1 and $2
            order by sw.log_date, sw.order_no""",
        start, end,
    )
    reassigned = await pool.fetch(
        "select log_date, day_key from day_plan where log_date between $1 and $2 order by log_date",
        start, end,
    )
    if swaps or reassigned:
        add("")
        add("  Changes made during this week")
        for r in reassigned:
            add(f"    {r['log_date']:%a %d %b}: ran the {DAY_NAMES[r['day_key']]} session instead")
        for r in swaps:
            add(f"    {r['log_date']:%a %d %b}: slot {r['order_no']} -> {r['name']} [{r['exercise_id']}]")

    # ---- 4. the catalogue the coach can choose from ---------------------
    add("")
    add("-" * 78)
    add("EXERCISE CATALOGUE — EVERYTHING AVAILABLE")
    add("-" * 78)
    add(wrap("Any of these can replace any slot above. Ids in brackets are what "
             "to quote when asking for a change."))
    cat = await pool.fetch(
        """select id, name, kind, muscle_group, equipment, muscles
             from exercise
            order by array_position(array['upper','lower','core','cardio'], muscle_group),
                     kind, name"""
    )
    group = None
    for r in cat:
        g = (r["muscle_group"], r["kind"])
        if g != group:
            group = g
            label = {"comp": "compound", "iso": "isolation", "cardio": "cardio / mobility"}.get(r["kind"], r["kind"])
            add("")
            add(f"  {r['muscle_group'].upper()} — {label}")
        add(f"    {r['name']:<38} {r['equipment']:<10} {', '.join(r['muscles'] or [])}")
        add(f"      [{r['id']}]")

    # ---- 5. the meals the coach can choose from -------------------------
    add("")
    add("-" * 78)
    add("MEAL OPTIONS — EVERYTHING AVAILABLE")
    add("-" * 78)
    add(wrap("All vegetarian, no egg. Option 1 is the current default. "
             "Options within a slot are not macro-matched -- check the kcal and "
             "protein on each before swapping."))
    for slot in meal_options():
        add("")
        add(f"  {slot['n'].upper()} ({slot['t']})")
        for i, o in enumerate(slot["opts"], 1):
            add(f"    {i}. {o['label']}  —  {o['k']} kcal · P {o['p']} · C {o['c']} · F {o['fa']}")
            add(wrap(o["f"], indent="         "))
            if o.get("prep"):
                add(wrap(o["prep"], indent="         "))

    # ---- 6. how to send changes back ------------------------------------
    add("")
    add("-" * 78)
    add("HOW TO REQUEST CHANGES")
    add("-" * 78)
    add(wrap("Anything below can be applied directly. Quote the slot number or "
             "the id in brackets."))
    add("")
    add("  Change an exercise permanently:  mon slot 3 -> pec-deck")
    add("  Change sets or reps:             tue slot 1 -> 4 x 6-8")
    add("  Change a target load:            wed slot 1 -> 60 kg")
    add("  Change a default meal:           breakfast -> option 3")
    add("  Add a note for a lift:           mon slot 1: pause at the bottom")
    add("")
    add(wrap("A substitution made in the app is for one day only and leaves the "
             "programme untouched. Anything here is a change to the programme "
             "itself, so it applies every week until changed again."))
    add("")
    add("=" * 78)
    await close_pool()
    return "\n".join(out)


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2:
        start, end = dt.date.fromisoformat(args[0]), dt.date.fromisoformat(args[1])
    elif len(args) == 1:
        start = dt.date.fromisoformat(args[0])
        end = start + dt.timedelta(days=6)
    else:
        end = dt.date.today()
        start = end - dt.timedelta(days=6)

    text = asyncio.run(build(start, end))
    dest = ROOT / "reports" / f"weekly-{start:%Y-%m-%d}.txt"
    dest.parent.mkdir(exist_ok=True)
    io.open(dest, "w", encoding="utf-8").write(text)
    print(f"{dest}  ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
