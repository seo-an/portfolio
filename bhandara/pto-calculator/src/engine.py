#!/usr/bin/env python3
"""Deterministic PTO calculation entrypoint for prepared handoff data."""

from __future__ import annotations

from datetime import date, timedelta
from .accrual_pipeline import calculate_anniversary_accrual
from .daily_calendar import build_daily_calendar_record
from .handoff_inputs import load_handoff_inputs


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def calculate_employee(employee: dict, inputs: dict, *, start_date: date, end_date: date) -> dict:
    effective_start = max(start_date, employee["hire_date"])
    effective_end = end_date
    if employee.get("termination_date"):
        effective_end = min(effective_end, employee["termination_date"])

    daily_records = []
    if effective_start <= effective_end:
        for work_date in _date_range(effective_start, effective_end):
            daily_records.append(build_daily_calendar_record(
                employee=employee,
                work_date=work_date,
                schedule_rows=inputs["schedule_rows"],
                assignment_rows=inputs["assignment_rows"],
                monthly_rows=inputs["monthly_rows"],
                attendance_rows=inputs["attendance_rows"],
                event_rows=inputs["event_rows"],
            ))

    accrual = calculate_anniversary_accrual(
        hire_date=employee["hire_date"],
        as_of_date=effective_end,
        daily_records=daily_records,
    )
    return {
        "employee_id": employee["employee_id"],
        "name": employee.get("name"),
        **accrual,
    }


def calculate_handoff(
    handoff: dict,
    *,
    start_year: int,
    end_year: int,
) -> list[dict]:
    """Calculate PTO from an already prepared, privacy-minimized handoff."""
    inputs = load_handoff_inputs(handoff)
    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    return [
        calculate_employee(
            employee,
            inputs,
            start_date=start_date,
            end_date=end_date,
        )
        for employee in inputs["employees"]
    ]
