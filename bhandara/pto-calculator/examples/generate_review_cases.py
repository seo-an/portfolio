#!/usr/bin/env python3
"""Reproducible, mixed PTO case-study workbooks. Synthetic employees only.

These cases test observable calculations and review behavior. They are NOT a
private vendor's "golden standard" and do not certify legal compliance.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, time, timedelta
from pathlib import Path

from openpyxl import Workbook

SEED = 20261111
PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2026, 1, 31)
EMPLOYEE_CASES = (
    ("R001", "NORMAL_ANNIVERSARY", "2025-01-01", None, "FIXED_7"),
    ("R002", "LOW_80_FALLBACK", "2025-01-01", None, "FIXED_7"),
    ("R003", "EXACTLY_80", "2025-01-01", None, "FIXED_7"),
    ("R004", "ABOVE_80", "2025-01-01", None, "FIXED_7"),
    ("R005", "MISSING_CLOCK", "2025-01-01", None, "FIXED_7"),
    ("R006", "TERMINATED", "2025-01-01", "2025-06-30", "FIXED_7"),
    ("R007", "END_OF_MONTH_HIRE", "2025-01-31", None, "FIXED_7"),
    ("R008", "REDUCED_HOURS", "2025-01-01", None, "FIXED_7"),
    ("R009", "ZERO_WORKDAYS", "2025-01-01", None, "OFF_7"),
    ("R010", "SICK_LEAVE_REVIEW", "2025-01-01", None, "FIXED_7"),
    ("R011", "PARENTAL_LEAVE", "2025-01-01", None, "FIXED_7"),
    ("R012", "ABSENCE_CLOCK_CONFLICT", "2025-01-01", None, "FIXED_7"),
    ("R013", "NORMAL_CONTROL_A", "2025-01-01", None, "FIXED_7"),
    ("R014", "NORMAL_CONTROL_B", "2025-01-01", None, "FIXED_7"),
)


def save_book(path: Path, columns: tuple[str, ...], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    try:
        sheet = book.active
        sheet.title = "Sheet1"
        sheet.append(columns)
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
    finally:
        book.close()


def days_between(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def is_scheduled(id_: str, day: date) -> bool:
    # E003's one-day scheduled OFF override makes exactly 260 workdays in 2025:
    # 208 credited / 260 = 80%, not an approximation.
    if id_ == "R009" or (id_ == "R003" and day == date(2025, 1, 1)):
        return False
    return day.weekday() < 5


def synthetic_absence_days(id_: str) -> set[date]:
    limits = {"R002": 53, "R003": 52, "R004": 51}
    if id_ not in limits:
        return set()
    candidates = [
        d for d in days_between(date(2025, 1, 1), date(2025, 12, 31))
        if is_scheduled(id_, d)
    ]
    return set(candidates[:limits[id_]])


def add_event(rows: list[tuple], id_: str, day: date, event_type: str,
              status: str, reduced_hours: float | None = None) -> None:
    request_id = f"CASE-{id_}-{day.isoformat()}"
    rows.append((request_id, id_, event_type, day.isoformat(),
                 "HOURS" if reduced_hours is not None else "DAY",
                 status, "synthetic case only", reduced_hours))


def build_rows() -> dict[str, list[tuple]]:
    employees = [
        (id_, hired, terminated, "FIXED")
        for id_, _, hired, terminated, _ in EMPLOYEE_CASES
    ]
    master = []
    for schedule_id in ("FIXED_7", "OFF_7"):
        for seq in range(1, 8):
            work = schedule_id == "FIXED_7" and seq <= 5
            master.append((schedule_id, "FIXED", seq, "WORK" if work else "OFF",
                           "DAY" if work else None, time(9) if work else None,
                           time(18) if work else None, 60 if work else None,
                           8 if work else 0, None))
    assignments = [
        (id_, schedule, "2025-01-01", None, "2025-01-06", 1, "synthetic")
        for id_, _, _, _, schedule in EMPLOYEE_CASES
    ]
    schedule_rows: list[tuple] = []
    attendance_rows: list[tuple] = []
    event_rows: list[tuple] = []

    for id_, case_id, hired, terminated, schedule_id in EMPLOYEE_CASES:
        hire_day = date.fromisoformat(hired)
        termination_day = date.fromisoformat(terminated) if terminated else PERIOD_END
        absence_days = synthetic_absence_days(id_)
        for day in days_between(max(hire_day, PERIOD_START), min(termination_day, PERIOD_END)):
            work = is_scheduled(id_, day)
            schedule_rows.append((
                id_, day.isoformat(), schedule_id, "DAY" if work else None,
                time(9) if work else None, time(18) if work else None,
                60 if work else None, 8 if work else 0,
                "WORK" if work else "OFF", "synthetic",
            ))
            if not work:
                continue
            if day in absence_days:
                add_event(event_rows, id_, day, "CONFIRMED_ABSENCE", "CONFIRMED")
                continue
            if id_ == "R005" and day == date(2025, 4, 1):
                continue  # missing clock is uncertain, not a confirmed absence
            if id_ == "R010" and day == date(2025, 6, 2):
                add_event(event_rows, id_, day, "SICK_LEAVE", "APPROVED")
                continue
            if id_ == "R011" and day == date(2025, 6, 2):
                add_event(event_rows, id_, day, "PARENTAL_LEAVE", "APPROVED")
                continue
            if id_ == "R008" and day == date(2025, 7, 1):
                add_event(event_rows, id_, day, "PREGNANCY_REDUCED_HOURS",
                          "APPROVED", reduced_hours=2.0)
                attendance_rows.append((id_, day.isoformat(), time(10),
                                        time(17), 60, "SYNTHETIC", None))
                continue
            if id_ == "R012" and day == date(2025, 6, 2):
                add_event(event_rows, id_, day, "CONFIRMED_ABSENCE", "CONFIRMED")
                # Intentionally contradictory clock record below.
            attendance_rows.append((id_, day.isoformat(), time(9),
                                    time(18), 60, "SYNTHETIC", None))

    return {
        "employees": employees,
        "master": master,
        "assignments": assignments,
        "schedule": schedule_rows,
        "attendance": attendance_rows,
        "events": event_rows,
    }


def generate_review_cases(root: Path, *, seed: int = SEED) -> dict:
    rng = random.Random(seed)
    rows = build_rows()
    for kind in ("employees", "assignments", "schedule", "attendance", "events"):
        rng.shuffle(rows[kind])

    source = root / "input"
    files = {
        "employees": "employee.xlsx",
        "schedule": "work-schedule.xlsx",
        "assignments": "work-schedule-assignment.xlsx",
        "monthly_schedule": ["work-records/2025-2026-schedule.xlsx"],
        "attendance": ["work-records/2025-2026-attendance.xlsx"],
        "events": "employee-events.xlsx",
    }
    save_book(source / files["employees"],
              ("employee_id", "hire_date", "termination_date", "work_system"),
              rows["employees"])
    save_book(source / files["schedule"],
              ("schedule_id", "work_system", "sequence", "day_type", "shift_code",
               "start_time", "end_time", "break_min", "scheduled_work_hours", "note"),
              rows["master"])
    save_book(source / files["assignments"],
              ("employee_id", "schedule_id", "effective_from", "effective_to",
               "cycle_anchor_date", "start_sequence", "note"), rows["assignments"])
    save_book(source / files["monthly_schedule"][0],
              ("employee_id", "work_date", "schedule_id", "shift_code",
               "scheduled_start", "scheduled_end", "break_min",
               "scheduled_work_hours", "day_type", "note"), rows["schedule"])
    save_book(source / files["attendance"][0],
              ("employee_id", "work_date", "clock_in", "clock_out",
               "break_min", "source", "note"), rows["attendance"])
    save_book(source / files["events"],
              ("request_id", "employee_id", "event_type", "event_date",
               "unit", "status", "note", "reduced_hours"), rows["events"])

    config = {
        "schema_version": "1.0",
        "period": {"from": PERIOD_START.isoformat(), "to": PERIOD_END.isoformat()},
        "files": files, "employee_allowlist": [],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    catalogue = {
        "schema_version": "1.0",
        "seed": seed,
        "note": "Case objectives, not universally authoritative legal outcomes.",
        "cases": [
            {"employee_id": id_, "case_id": case_id,
             "review_status": "synthetic test expectation, not legal certification"}
            for id_, case_id, *_ in EMPLOYEE_CASES
        ],
    }
    (root / "case-index.json").write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"employee_count": len(EMPLOYEE_CASES), "seed": seed,
            "source_dir": str(source), "config": str(root / "config.json")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    result = generate_review_cases(Path(args.output_dir), seed=args.seed)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
