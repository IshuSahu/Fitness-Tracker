# Weekly report as a text file, and two data fixes

## Context
The weekly report endpoint has existed since the FastAPI conversion but
nothing calls it. Deliberately staying backend-only: no UI. It is generated on
demand as a .txt to hand to a coach, whose changes come back as plan edits.

For that to be actionable the report has to carry more than what was logged —
the coach needs to see every exercise and every meal available, with ids, so
they can name a change precisely.

## Steps
- [x] `db.py`: a `num()` helper converting float -> Decimal for numeric columns.
- [x] `weight.py` / `daily.py`: route every numeric write through it.
- [x] Clean the existing rows: round the stored expansions.
- [x] Null the bogus 24-hour sleep row (blank bed/wake, so not a measurement).
- [x] `scripts/weekly_report.py`: the report generator.
- [x] Include the current programme, the full exercise catalogue, and every
      meal option — each with ids — plus a "how to request changes" key.
- [x] Read meal options out of `static/index.html` rather than duplicating them.
- [x] gitignore `reports/`.
- [x] Verify: 10 new checks on rounding; 274 existing checks still green.

## Review

**The report is a file, not a page.** `python scripts/weekly_report.py` writes
`reports/weekly-<start>.txt`. Optional args take a start date or an explicit
range; the default is the last seven days.

It has six parts: what was actually trained (from the existing `weekly_report()`
SQL function), the current programme with slot numbers, any one-off changes
made during the week, the full 48-exercise catalogue, all 27 meal options with
macros, and a short key showing how to phrase a change. The last part matters —
without ids and slot numbers a coach's reply is ambiguous.

**Meal options are read out of `static/index.html`, not copied.** They are a
frontend constant, and a second copy in Python would drift within a week. The
generator evaluates just that one constant with node and reads it back as JSON.

### Two data bugs the first report exposed

**Sleep averaged 10.1h against a real 6.66h.** The 14 Sept row held
`sleep_hours = 24` with blank bed/wake — the bug fixed on 19 Sept, where empty
time fields defaulted to 00:00 so bedtime equalled wake-up and wrapped to a
full day. One stale row moved the weekly average by three and a half hours.
Nulled, since with no times recorded there is no measurement to keep.

**Weight printed as `85.400000000000005684341886...`.** asyncpg hands a Python
float to a numeric column at its exact binary value. Every numeric write now
goes through `num()`, which rounds via a Decimal built from a string, so what
gets stored is what was typed. The affected `weight_kg` and `sleep_hours` rows
were rounded in place.

Both were only visible because the report printed raw stored values — the
dashboard formats on display and hid them.

### Worth knowing
- `reports/` is gitignored: personal data, and regenerable at any time.
- The generator needs `node` on PATH for the meal extraction. It is already a
  dependency of the test suites.
- Nothing about this touches the UI, per the brief.
