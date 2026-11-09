"""Resolve an employee's effective work schedule for a specific date."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from bhandara.common.utils.date_interval import is_date_within_interval
from .schedule import resolve_schedule_day


def find_monthly_schedule(
    monthly_rows: Iterable[dict],
    employee_id: str,
    work_date: date,
) -> dict | None:
    matches = [
        row for row in monthly_rows
        if row["employee_id"] == employee_id and row["work_date"] == work_date
    ]
    if len(matches) > 1:
        raise ValueError(
            f"duplicate monthly schedule: employee_id={employee_id}, work_date={work_date}"
        )
    return matches[0] if matches else None


def find_effective_assignment(
    assignment_rows: Iterable[dict],
    employee_id: str,
    work_date: date,
) -> dict:
    matches = [
        row for row in assignment_rows
        if row["employee_id"] == employee_id
        and is_date_within_interval(
            row["effective_from"], row.get("effective_to"), work_date
        )
    ]
    if not matches:
        raise LookupError(
            f"no effective schedule assignment: employee_id={employee_id}, work_date={work_date}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"overlapping schedule assignments: employee_id={employee_id}, work_date={work_date}"
        )
    return matches[0]


def resolve_employee_schedule(
    schedule_rows: Iterable[dict],
    assignment_rows: Iterable[dict],
    monthly_rows: Iterable[dict],
    employee_id: str,
    work_date: date,
) -> dict:
    """Resolve monthly confirmed schedule first, otherwise assignment + master cycle."""
    monthly = find_monthly_schedule(monthly_rows, employee_id, work_date)
    if monthly is not None:
        resolved = dict(monthly)
        resolved["resolution_source"] = "monthly_schedule"
        return resolved

    assignment = find_effective_assignment(assignment_rows, employee_id, work_date)
    cycle_day = resolve_schedule_day(
        schedule_rows=schedule_rows,
        schedule_id=assignment["schedule_id"],
        work_date=work_date,
        cycle_anchor_date=assignment["cycle_anchor_date"],
        start_sequence=assignment["start_sequence"],
    )
    resolved = dict(cycle_day)
    resolved["employee_id"] = employee_id
    resolved["work_date"] = work_date
    resolved["resolution_source"] = "assignment_cycle"
    return resolved
