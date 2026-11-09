#!/usr/bin/env python3
"""Generate an entirely synthetic PTO Excel dataset; no real employees or approvals."""
from __future__ import annotations

import argparse
import json
from datetime import date, time, timedelta
from pathlib import Path

from openpyxl import Workbook


def save_book(path: Path, header: tuple[str, ...], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    try:
        sheet = book.active
        sheet.title = "Sheet1"
        sheet.append(header)
        for row in rows:
            sheet.append(row)
        book.save(path)
    finally:
        book.close()


def generate_demo(root: Path) -> tuple[Path, Path]:
    source = root / "input"
    employees = [
        ("E001", "2026-06-01", None, "FIXED"),
        ("E005", "2026-01-01", None, "FIXED"),
    ]
    save_book(source / "employee.xlsx",
              ("employee_id", "hire_date", "termination_date", "work_system"), employees)
    master = []
    for sequence in range(1, 8):
        work = sequence <= 5
        master.append(("FIXED_7", "FIXED", sequence, "WORK" if work else "OFF",
                       "DAY" if work else None, time(9), time(18) if work else None,
                       60 if work else None, 8 if work else 0, None))
    save_book(source / "work-schedule.xlsx",
              ("schedule_id", "work_system", "sequence", "day_type", "shift_code",
               "start_time", "end_time", "break_min", "scheduled_work_hours", "note"), master)
    assignments = [(identifier, "FIXED_7", "2026-01-01", None, "2026-07-01", 1, None)
                   for identifier, *_ in employees]
    save_book(source / "work-schedule-assignment.xlsx",
              ("employee_id", "schedule_id", "effective_from", "effective_to",
               "cycle_anchor_date", "start_sequence", "note"), assignments)
    monthly, attendance = [], []
    for person, *_ in employees:
        for index in range(7):
            day = date(2026, 7, 1) + timedelta(days=index)
            work = index < 5
            monthly.append((person, day, "FIXED_7", "DAY" if work else None,
                            time(9) if work else None, time(18) if work else None,
                            60 if work else None, 8 if work else 0,
                            "WORK" if work else "OFF", None))
            if work:
                attendance.append((person, day, time(9), time(18), 60,
                                   "SYNTHETIC", None))
    folder = source / "work-records" / "2026"
    save_book(folder / "2026-07-schedule.xlsx",
              ("employee_id", "work_date", "schedule_id", "shift_code",
               "scheduled_start", "scheduled_end", "break_min",
               "scheduled_work_hours", "day_type", "note"), monthly)
    save_book(folder / "2026-07-attendance.xlsx",
              ("employee_id", "work_date", "clock_in", "clock_out",
               "break_min", "source", "note"), attendance)
    config = {
        "schema_version": "1.0",
        "period": {"from": "2026-07-01", "to": "2026-07-07"},
        "files": {
            "employees": "employee.xlsx",
            "schedule": "work-schedule.xlsx",
            "assignments": "work-schedule-assignment.xlsx",
            "monthly_schedule": ["work-records/2026/2026-07-schedule.xlsx"],
            "attendance": ["work-records/2026/2026-07-attendance.xlsx"],
            "events": None,
        },
        "employee_allowlist": [],
    }
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return source, config_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.output_dir)
    source, config = generate_demo(root)
    print("Synthetic PTO input:", source)
    print("Synthetic PTO config:", config)
    print("No real employee records, approvals, or payroll data were created.")


if __name__ == "__main__":
    main()
