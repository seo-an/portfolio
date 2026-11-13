#!/usr/bin/env python3
"""Nine synthetic PTO event scenarios; no real employees or pay data."""
from __future__ import annotations

import argparse
import json
from datetime import date, time, timedelta
from pathlib import Path

from .generate_demo import save_book


START = date(2025, 7, 1)
END = date(2026, 7, 31)
SCENARIOS = (
    ("S001", "연차", "DAY", 6, None),
    ("S002", "연차", "DAY", 6, None),
    ("S003", "오전 반차", "HALF_DAY", 7, None),
    ("S004", "오전 반차", "HALF_DAY", 7, None),
    ("S005", "오전 반차", "HALF_DAY", 7, None),
    ("S006", "오후 반차", "HALF_DAY", 8, None),
    ("S007", "오후 반차", "HALF_DAY", 8, None),
    ("S008", "조기퇴근", "HOURS", 9, None),
    ("S009", "육아기근로시간단축", "HOURS", 10, 2.0),
)


def dates(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def generate_cases(root: Path) -> dict:
    source = root / "input"
    employees = [(ident, START.isoformat(), None, "FIXED")
                 for ident, *_ in SCENARIOS]
    save_book(
        source / "employee.xlsx",
        ("employee_id", "hire_date", "termination_date", "work_system"),
        employees,
    )
    master = [
        ("FIXED_7", "FIXED", sequence, "WORK" if sequence <= 5 else "OFF",
         "DAY" if sequence <= 5 else None,
         time(9) if sequence <= 5 else None,
         time(18) if sequence <= 5 else None,
         60 if sequence <= 5 else None,
         8 if sequence <= 5 else 0, None)
        for sequence in range(1, 8)
    ]
    save_book(
        source / "work-schedule.xlsx",
        ("schedule_id", "work_system", "sequence", "day_type", "shift_code",
         "start_time", "end_time", "break_min", "scheduled_work_hours", "note"),
        master,
    )
    schedule = []
    attendance = []
    event_rows = []
    for ident, label, unit, july_day, hours in SCENARIOS:
        event_day = date(2026, 7, july_day)
        event_rows.append((
            f"SYNTH-{ident}-{july_day}", ident, label, event_day.isoformat(),
            unit, "APPROVED", "synthetic scenario", hours,
        ))
        for day in dates(START, END):
            weekday = day.weekday()
            work = weekday < 5
            schedule.append((
                ident, day.isoformat(), "FIXED_7", "DAY" if work else None,
                time(9) if work else None, time(18) if work else None,
                60 if work else None, 8 if work else 0,
                "WORK" if work else "OFF", None,
            ))
            if not work or (day == event_day and label == "연차"):
                continue
            # A punch record is not itself evidence of approved partial-leave
            # balance or correct hours; PTO still reviews uncovered obligations.
            out = time(16) if day == event_day and label == "조기퇴근" else time(18)
            attendance.append((ident, day.isoformat(), time(9), out,
                               60, "SYNTHETIC", None))

    save_book(
        source / "work-records/2025-2026-schedule.xlsx",
        ("employee_id", "work_date", "schedule_id", "shift_code",
         "scheduled_start", "scheduled_end", "break_min",
         "scheduled_work_hours", "day_type", "note"),
        schedule,
    )
    save_book(
        source / "work-records/2025-2026-attendance.xlsx",
        ("employee_id", "work_date", "clock_in", "clock_out",
         "break_min", "source", "note"),
        attendance,
    )
    save_book(
        source / "employee-events.xlsx",
        ("request_id", "employee_id", "event_type", "event_date",
         "unit", "status", "note", "reduced_hours"),
        event_rows,
    )
    settings = {
        "schema_version": "1.0",
        "period": {"from": START.isoformat(), "to": END.isoformat()},
        "files": {
            "employees": "employee.xlsx",
            "schedule": "work-schedule.xlsx",
            # Complete dated schedule: no assignments needed.
            "monthly_schedule": ["work-records/2025-2026-schedule.xlsx"],
            "attendance": ["work-records/2025-2026-attendance.xlsx"],
            "events": "employee-events.xlsx",
        },
        "employee_allowlist": [],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"employee_count": len(employees), "event_count": len(event_rows),
            "input_dir": str(source), "config": str(root / "config.json")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(generate_cases(Path(args.output_dir)),
                     ensure_ascii=False, indent=2))
    print("Synthetic-only input; results cannot authorize pay or leave.")


if __name__ == "__main__":
    main()
