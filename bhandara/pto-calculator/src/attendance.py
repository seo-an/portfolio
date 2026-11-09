"""Normalize daily attendance facts without making legal absence conclusions."""

from __future__ import annotations

from datetime import date
from typing import Iterable


FLAG_INCOMPLETE_ATTENDANCE = "INCOMPLETE_ATTENDANCE"
FLAG_NO_ATTENDANCE = "NO_ATTENDANCE"
FLAG_WORK_ON_NON_WORKDAY = "WORK_ON_NON_WORKDAY"

STATUS_PRESENT = "PRESENT"
STATUS_NO_RECORD = "NO_RECORD"
STATUS_NON_WORKDAY = "NON_WORKDAY"


def find_attendance_row(
    attendance_rows: Iterable[dict],
    employee_id: str,
    work_date: date,
) -> dict | None:
    matches = [
        row for row in attendance_rows
        if row["employee_id"] == employee_id and row["work_date"] == work_date
    ]
    if len(matches) > 1:
        raise ValueError(
            f"duplicate attendance: employee_id={employee_id}, work_date={work_date}"
        )
    return matches[0] if matches else None


def classify_daily_attendance(
    resolved_schedule: dict,
    attendance_row: dict | None,
) -> dict:
    """Return observable attendance facts and review flags.

    Missing attendance on a scheduled workday is intentionally not classified
    as absence. Leave, statutory deemed-attendance periods, suspension, and
    other legal/operational context must be reconciled by a later layer.
    """
    employee_id = resolved_schedule.get("employee_id")
    work_date = resolved_schedule.get("work_date")
    day_type = str(resolved_schedule["day_type"]).upper()
    flags: list[str] = []

    clock_in = attendance_row.get("clock_in") if attendance_row else None
    clock_out = attendance_row.get("clock_out") if attendance_row else None
    break_min = attendance_row.get("break_min") if attendance_row else None
    has_any_record = clock_in is not None or clock_out is not None
    has_complete_record = clock_in is not None and clock_out is not None

    if day_type == "WORK":
        if has_complete_record:
            status = STATUS_PRESENT
        elif has_any_record:
            status = STATUS_NO_RECORD
            flags.append(FLAG_INCOMPLETE_ATTENDANCE)
        else:
            status = STATUS_NO_RECORD
            flags.append(FLAG_NO_ATTENDANCE)
    else:
        status = STATUS_NON_WORKDAY
        if has_any_record:
            flags.append(FLAG_WORK_ON_NON_WORKDAY)
            if not has_complete_record:
                flags.append(FLAG_INCOMPLETE_ATTENDANCE)

    return {
        "employee_id": employee_id,
        "work_date": work_date,
        "day_type": day_type,
        "status": status,
        "clock_in": clock_in,
        "clock_out": clock_out,
        "break_min": break_min,
        "flags": flags,
        "requires_review": bool(flags),
    }


def resolve_daily_attendance(
    resolved_schedule: dict,
    attendance_rows: Iterable[dict],
) -> dict:
    employee_id = resolved_schedule.get("employee_id")
    work_date = resolved_schedule.get("work_date")
    if employee_id is None or work_date is None:
        raise ValueError("resolved_schedule requires employee_id and work_date")

    attendance_row = find_attendance_row(attendance_rows, employee_id, work_date)
    return classify_daily_attendance(resolved_schedule, attendance_row)
