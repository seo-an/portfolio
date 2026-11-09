"""Materialize company leave duration rules into employee-date events."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from .company_leave_policy import validate_duration_rule
from .resolver import resolve_employee_schedule


def materialize_leave_dates(
    *,
    event_date: date,
    duration_rule: dict,
    employee_id: str,
    schedule_rows: Iterable[dict],
    assignment_rows: Iterable[dict],
    monthly_rows: Iterable[dict],
) -> list[date]:
    """Expand one duration rule to covered dates.

    CALENDAR_DAY counts consecutive calendar dates.
    WORKING_DAY counts only dates whose resolved employee schedule is WORK.
    """
    rule = validate_duration_rule(duration_rule)
    current = (
        event_date
        if rule["start_anchor"] == "EVENT_DATE"
        else event_date + timedelta(days=1)
    )

    if rule["count_basis"] == "CALENDAR_DAY":
        return [
            current + timedelta(days=offset)
            for offset in range(rule["days"])
        ]

    dates: list[date] = []
    while len(dates) < rule["days"]:
        resolved = resolve_employee_schedule(
            schedule_rows=schedule_rows,
            assignment_rows=assignment_rows,
            monthly_rows=monthly_rows,
            employee_id=employee_id,
            work_date=current,
        )
        if str(resolved["day_type"]).upper() == "WORK":
            dates.append(current)
        current += timedelta(days=1)

    return dates


def materialize_leave_event_rows(
    *,
    source_event: dict,
    policy_rule: dict,
    schedule_rows: Iterable[dict],
    assignment_rows: Iterable[dict],
    monthly_rows: Iterable[dict],
) -> list[dict]:
    """Expand an approved source event into daily employee-event rows."""
    dates = materialize_leave_dates(
        event_date=source_event["event_date"],
        duration_rule=policy_rule["duration"],
        employee_id=source_event["employee_id"],
        schedule_rows=schedule_rows,
        assignment_rows=assignment_rows,
        monthly_rows=monthly_rows,
    )

    rows = []
    for covered_date in dates:
        row = dict(source_event)
        row["event_date"] = covered_date
        row["unit"] = "DAY"
        row["materialized_from_event_date"] = source_event["event_date"]
        rows.append(row)
    return rows
