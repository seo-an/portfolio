"""Compose schedule, employment, and attendance facts into a daily PTO record."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .attendance import resolve_daily_attendance
from .attendance_policy import resolve_daily_attendance_policy
from .employment import classify_employment_boundary
from .event_reconciliation import reconcile_daily_employee_event
from .event_type import normalize_event_type
from .partial_attendance import PARTIAL_TIME_EVENTS, compose_reduced_hours_attendance
from .resolver import resolve_employee_schedule


def build_daily_calendar_record(
    employee: dict[str, Any],
    work_date: date,
    schedule_rows: Iterable[dict],
    assignment_rows: Iterable[dict],
    monthly_rows: Iterable[dict],
    attendance_rows: Iterable[dict],
    event_rows: Iterable[dict] = (),
) -> dict[str, Any]:
    """Build one employee-date fact record without legal attendance conclusions."""

    employee_id = employee.get("employee_id")
    if not employee_id:
        raise ValueError("employee_id is required")

    resolved_schedule = resolve_employee_schedule(
        schedule_rows=schedule_rows,
        assignment_rows=assignment_rows,
        monthly_rows=monthly_rows,
        employee_id=employee_id,
        work_date=work_date,
    )
    employment = classify_employment_boundary(
        employee=employee,
        work_date=work_date,
        resolved_schedule=resolved_schedule,
    )
    attendance = resolve_daily_attendance(
        resolved_schedule=resolved_schedule,
        attendance_rows=attendance_rows,
    )
    event_reconciliation = reconcile_daily_employee_event(
        event_rows=event_rows,
        employee_id=employee_id,
        event_date=work_date,
    )
    active_event = event_reconciliation["event"]
    attendance_policy = resolve_daily_attendance_policy(
        within_employment=employment["within_employment"],
        scheduled_work_day=resolved_schedule["day_type"] == "WORK",
        attendance_status=attendance["status"],
        event=active_event,
    )

    partial_attendance = None
    if (
        employment["within_employment"]
        and resolved_schedule["day_type"] == "WORK"
        and active_event is not None
        and normalize_event_type(active_event.get("event_type")) in PARTIAL_TIME_EVENTS
    ):
        partial_attendance = compose_reduced_hours_attendance(
            schedule=resolved_schedule,
            attendance=attendance,
            event=active_event,
        )
        if partial_attendance["resolved"]:
            attendance_policy = {
                "denominator": "INCLUDED",
                "credit": "DEEMED_PRESENT",
                "basis_type": "STATUTE",
                "reason": partial_attendance["reason"],
                "requires_review": False,
            }
        else:
            attendance_policy = {
                "denominator": "INCLUDED",
                "credit": "REVIEW",
                "basis_type": "REVIEW",
                "reason": partial_attendance["reason"],
                "requires_review": True,
            }

    flags = sorted(set(
        employment["flags"]
        + attendance["flags"]
        + event_reconciliation["flags"]
    ))
    if attendance_policy["requires_review"]:
        flags = sorted(set(flags + ["ATTENDANCE_POLICY_REVIEW"]))

    return {
        "employee_id": employee_id,
        "work_date": work_date,
        "scheduled_work_day": resolved_schedule["day_type"] == "WORK",
        "schedule": resolved_schedule,
        "employment": employment,
        "attendance": attendance,
        "employee_event": event_reconciliation,
        "attendance_denominator": attendance_policy["denominator"],
        "attendance_credit": attendance_policy["credit"],
        "attendance_policy": attendance_policy,
        "partial_attendance": partial_attendance,
        "flags": flags,
        "requires_review": bool(flags),
    }
