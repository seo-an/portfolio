"""Employment-boundary facts for PTO daily calendar construction."""

from __future__ import annotations

from datetime import date
from typing import Any

from bhandara.common.utils.employment import is_within_employment_interval


OUTSIDE_EMPLOYMENT = "OUTSIDE_EMPLOYMENT"
WITHIN_EMPLOYMENT = "WITHIN_EMPLOYMENT"
SCHEDULE_OUTSIDE_EMPLOYMENT = "SCHEDULE_OUTSIDE_EMPLOYMENT"


def classify_employment_boundary(
    employee: dict[str, Any],
    work_date: date,
    resolved_schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify whether a date falls inside an employee's employment period.

    This function deliberately does not interpret leave, suspension, or other
    employee events. Those belong to later attendance denominator/credit rules.
    """

    employee_id = employee.get("employee_id")
    hire_date = employee.get("hire_date")
    termination_date = employee.get("termination_date")

    if not employee_id:
        raise ValueError("employee_id is required")
    within_employment = is_within_employment_interval(
        hire_date,
        termination_date,
        work_date,
    )

    flags: list[str] = []
    if (
        not within_employment
        and resolved_schedule is not None
        and resolved_schedule.get("day_type") == "WORK"
    ):
        flags.append(SCHEDULE_OUTSIDE_EMPLOYMENT)

    return {
        "employee_id": employee_id,
        "work_date": work_date,
        "employment_status": (
            WITHIN_EMPLOYMENT if within_employment else OUTSIDE_EMPLOYMENT
        ),
        "within_employment": within_employment,
        "flags": flags,
        "requires_review": bool(flags),
    }
