#!/usr/bin/env python3
"""Reproducible 80-employee SHARED input fixtures.

Use only for publication/testing. The security-reader examples reconstruct
illustrative formats; they are NOT authoritative exports from ADT/S1/KT.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, time, timedelta
from pathlib import Path

from openpyxl import Workbook

SEED = 20261112
EMPLOYEES = 80
SCHEDULES = ("FIXED", "STAGGERED", "TWO_SHIFT", "THREE_SHIFT", "DAY_NIGHT", "FLEXIBLE")
START = date(2026, 6, 1)
END = date(2026, 7, 31)


def save_xlsx(path: Path, headers: tuple[str, ...], records: list[tuple], *,
              sheet_name: str = "Sheet1") -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing fixture: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    try:
        sheet = book.active
        sheet.title = sheet_name
        sheet.append(headers)
        for record in records:
            sheet.append(record)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
    finally:
        book.close()


def write_json(path: Path, content: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing fixture: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def dates(first: date, last: date):
    current = first
    while current <= last:
        yield current
        current += timedelta(days=1)


def roster() -> list[dict]:
    result = []
    for i in range(1, EMPLOYEES + 1):
        schedule = SCHEDULES[(i - 1) // 14 % len(SCHEDULES)]
        result.append({
            "employee_id": f"E{i:03d}",
            "worker_id": f"EP{i:04d}",
            "security_id": f"SEC-{i:04d}",
            "payroll_id": f"PAY-{i:04d}",
            "hire_date": date(2024 + ((i // 35) % 2), (i % 12) + 1, min((i % 26) + 1, 28)),
            "termination_date": date(2026, 7, 20) if i == 7 else
                                date(2026, 7, 31) if i == 19 else None,
            "work_system": schedule,
            "case_id": (
                {2: "LOW_ATTENDANCE", 5: "MISSING_RAW_EVENT",
                 7: "TERMINATED_JUL20", 12: "NIGHT_SHIFT",
                 19: "TERMINATED_JUL31", 31: "CHILDCARE_REDUCED",
                 44: "DUPLICATE_RAW_TAG", 67: "FLEXIBLE_REVIEW"}
            ).get(i, "NORMAL_OR_WORKSYSTEM_REVIEW"),
        })
    return result


def day_schedule(employee: dict, day: date):
    if day.weekday() >= 5:
        return False, None, None, 0, 0
    idx = int(employee["employee_id"][1:])
    system = employee["work_system"]
    if system in ("TWO_SHIFT", "THREE_SHIFT", "DAY_NIGHT") and (idx + day.day) % 4 == 0:
        start, end = time(21), time(6)
    elif system == "STAGGERED":
        start, end = time(10), time(19)
    elif system == "FLEXIBLE":
        start, end = time(8), time(17)
    else:
        start, end = time(9), time(18)
    return True, start, end, 60, 8


def build_shared_input(root: Path) -> dict[str, int]:
    people = roster()
    rng = random.Random(SEED)
    input_dir = root / "input"
    employee_rows = [
        (x["employee_id"], x["hire_date"].isoformat(),
         x["termination_date"].isoformat() if x["termination_date"] else None,
         x["work_system"], x["case_id"])
        for x in people
    ]
    ids = [
        (x["employee_id"], x["security_id"], x["worker_id"],
         x["payroll_id"], x["work_system"], x["case_id"])
        for x in people
    ]
    rng.shuffle(employee_rows)
    rng.shuffle(ids)
    save_xlsx(input_dir / "common/employee.xlsx",
              ("employee_id", "hire_date", "termination_date", "work_system", "case_id"),
              employee_rows)
    save_xlsx(input_dir / "common/id-map.xlsx",
              ("employee_id", "security_id", "worker_id", "payroll_id",
               "work_system", "case_id"), ids, sheet_name="ID_MAP")

    master, assignments = [], []
    cycle_anchor = "2026-06-01"
    for system in SCHEDULES:
        for sequence in range(1, 8):
            work = sequence <= 5
            start, end = (
                (time(10), time(19)) if system == "STAGGERED"
                else (time(8), time(17)) if system == "FLEXIBLE"
                else (time(9), time(18))
            )
            master.append((
                f"{system}_7", system, sequence, "WORK" if work else "OFF",
                "DAY" if work else None, start if work else None,
                end if work else None, 60 if work else None, 8 if work else 0,
                "Synthetic recurring template",
            ))
    for person in people:
        assignments.append((
            person["employee_id"], f"{person['work_system']}_7",
            "2024-01-01", None, cycle_anchor, 1, "Synthetic assignment",
        ))
    rng.shuffle(assignments)
    save_xlsx(input_dir / "pto/work-schedule.xlsx",
              ("schedule_id", "work_system", "sequence", "day_type", "shift_code",
               "start_time", "end_time", "break_min", "scheduled_work_hours", "note"),
              master)
    save_xlsx(input_dir / "pto/work-schedule-assignment.xlsx",
              ("employee_id", "schedule_id", "effective_from", "effective_to",
               "cycle_anchor_date", "start_sequence", "note"),
              assignments)

    pto_schedules, pto_attendance, work_schedule, work_attendance = [], [], [], []
    for person in people:
        for day in dates(START, END):
            if person["termination_date"] and day > person["termination_date"]:
                continue
            work, start, end, rest, scheduled_hours = day_schedule(person, day)
            code = f"{person['work_system']}_7"
            record = (
                person["employee_id"], day.isoformat(), code,
                "NIGHT" if work and start == time(21) else "DAY" if work else None,
                start, end, rest if work else None, scheduled_hours,
                "WORK" if work else "OFF", "Synthetic case",
            )
            if day.month == 7:
                pto_schedules.append(record)
                if work:
                    pto_attendance.append((
                        person["employee_id"], day.isoformat(), start, end,
                        rest, "SYNTHETIC_ADJUDICATED", "Synthetic confirmed clock pair",
                    ))
            if day.month == 6:
                work_schedule.append((
                    person["employee_id"], day.isoformat(), "WORK" if work else "OFF",
                    start, end, rest if work else None, scheduled_hours,
                    "Synthetic schedule",
                ))
                if work:
                    work_attendance.append((
                        person["employee_id"], day.isoformat(), start, end,
                        rest, "SYNTHETIC_ADJUDICATED", "Synthetic confirmed clock pair",
                    ))
    for rows in (pto_schedules, pto_attendance, work_schedule, work_attendance):
        rng.shuffle(rows)
    save_xlsx(input_dir / "pto/work-records/2026/2026-07-schedule.xlsx",
              ("employee_id", "work_date", "schedule_id", "shift_code",
               "scheduled_start", "scheduled_end", "break_min",
               "scheduled_work_hours", "day_type", "note"), pto_schedules)
    save_xlsx(input_dir / "pto/work-records/2026/2026-07-attendance.xlsx",
              ("employee_id", "work_date", "clock_in", "clock_out", "break_min",
               "source", "note"), pto_attendance)
    save_xlsx(input_dir / "worktime/work-schedule.xlsx",
              ("employee_id", "work_date", "day_type", "scheduled_start",
               "scheduled_end", "break_min", "scheduled_work_hours", "note"),
              work_schedule)
    save_xlsx(input_dir / "worktime/attendance.xlsx",
              ("employee_id", "work_date", "clock_in", "clock_out", "break_min",
               "source", "note"), work_attendance)

    events = [
        ("CASE-031-2026-07-01", "E031", "PREGNANCY_REDUCED_HOURS",
         "2026-07-01", "HOURS", "APPROVED", "Synthetic event only", 2),
        ("CASE-044-2026-07-12", "E044", "SICK_LEAVE",
         "2026-07-12", "DAY", "APPROVED", "Company policy review", None),
    ]
    save_xlsx(input_dir / "pto/employee-events.xlsx",
              ("request_id", "employee_id", "event_type", "event_date",
               "unit", "status", "note", "reduced_hours"), events)

    # Mocked raw security data are separate evidence, not canonical attendance.
    # They preserve ambiguous events, duplicate tags and device differences.
    raw = {"caps": [], "s1": [], "kt": []}
    candidates = []
    for person in people:
        for day in dates(START, date(2026, 6, 10)):
            work, start, end, *_ = day_schedule(person, day)
            if not work:
                continue
            candidates.append((person["security_id"], day, start, end))
    rng.shuffle(candidates)
    for index, (security_id, day, start, end) in enumerate(candidates[:600]):
        vendor = ("caps", "s1", "kt")[index % 3]
        if vendor == "caps":
            raw[vendor].extend([
                (security_id, day.isoformat(), start, "인증", "CAPS-DEMO-01"),
                (security_id, day.isoformat(), end, "퇴근", "CAPS-DEMO-01"),
            ])
        elif vendor == "s1":
            raw[vendor].extend([
                (security_id, day.isoformat(), start, "출근", "S1-DEMO-02"),
                (security_id, day.isoformat(), end, "인증", "S1-DEMO-02"),
            ])
        else:
            raw[vendor].extend([
                (security_id, day.isoformat(), start, "IN", "KT-DEMO-03"),
                (security_id, day.isoformat(), end, "OUT", "KT-DEMO-03"),
            ])
    if raw["caps"]:
        raw["caps"].append(raw["caps"][0])  # intentional duplicate evidence
    raw_specs = (
        ("caps", "security-raw-caps-synthetic.xlsx"),
        ("s1", "security-raw-s1-synthetic.xlsx"),
        ("kt", "security-raw-kt-synthetic.xlsx"),
    )
    for vendor, filename in raw_specs:
        rng.shuffle(raw[vendor])
        save_xlsx(input_dir / "worktime" / filename,
                  ("source_person_id", "event_date", "event_time", "raw_event",
                   "device_id"), raw[vendor])

    compensation = []
    for i, person in enumerate(people, start=1):
        compensation.append((
            person["worker_id"], "2026-01-01", None, 2800000 + (i % 13) * 100000,
        ))
    rng.shuffle(compensation)
    save_xlsx(input_dir / "payroll/compensation.xlsx",
              ("worker_id", "effective_from", "effective_to", "base_salary"),
              compensation)
    variable = [
        (x["worker_id"], "performance_bonus", 100000, None,
         None, None, None, "Synthetic one-off bonus")
        for i, x in enumerate(people, start=1) if i % 9 == 0
    ]
    rng.shuffle(variable)
    save_xlsx(input_dir / "payroll/payroll-input.xlsx",
              ("worker_id", "pay_item_code", "amount", "quantity",
               "origin_pay_item_code", "origin_from", "origin_to", "note"),
              variable)
    write_json(input_dir / "payroll/company-policy.json", {
        "proration": {"base_salary": {"method": "역일수"}},
        "ordinary_wage": {"monthly_basis_hours": 200, "pay_items": {}},
        "worktime_pay": {"base_component_policy": {}},
        "amount_processing": {
            "unit": 10, "method": "절사", "apply_at": "최종지급액",
            "remainder": {
                "handling": "settlement_ledger",
                "transaction_type": "rounding_carry",
                "settlement_month": 12,
            },
        },
    })
    write_json(root / "sample-manifest.json", {
        "schema_version": "1.0", "seed": SEED, "employees": EMPLOYEES,
        "note": "Synthetic inputs. Raw reader layouts are illustrative, not vendor-certified.",
        "worktime_month": "2026-06", "pto_month": "2026-07",
        "payroll_month": "2026-07",
        "identity_map": "input/common/id-map.xlsx",
        "source_files": {
            "pto_schedule": len(pto_schedules),
            "pto_attendance": len(pto_attendance),
            "worktime_schedule": len(work_schedule),
            "worktime_attendance": len(work_attendance),
            "raw_security_events": sum(len(v) for v in raw.values()),
            "compensation": len(compensation),
        },
    })
    return {"employees": EMPLOYEES, "worktime_days": len(work_attendance),
            "pto_days": len(pto_attendance)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build_shared_input(Path(args.output_dir)), ensure_ascii=False))


if __name__ == "__main__":
    main()
