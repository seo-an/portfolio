"""Coordinate weekly-holiday eligibility, hours, treatment, and pay."""

from __future__ import annotations

from typing import Any

try:
    from .weekly_holiday_eligibility import evaluate_weekly_holiday_eligibility
    from .weekly_holiday_hours import calculate_four_week_weekly_holiday_hours
    from .weekly_holiday_pay_treatment import resolve_weekly_holiday_pay_treatment
    from .weekly_holiday_pay import calculate_weekly_holiday_pay
except ImportError:
    from weekly_holiday_eligibility import evaluate_weekly_holiday_eligibility
    from weekly_holiday_hours import calculate_four_week_weekly_holiday_hours
    from weekly_holiday_pay_treatment import resolve_weekly_holiday_pay_treatment
    from weekly_holiday_pay import calculate_weekly_holiday_pay


def resolve_weekly_holiday(
    *,
    worker_id: str,
    week_start: Any,
    week_end: Any,
    worktime_rows: list[dict[str, Any]],
    absence_events: list[dict[str, Any]],
    weekly_scheduled_hours: Any,
    labor_status: str,
    pay_basis: str,
    ordinary_worker_weekly_prescribed_days: Any = 5,
    hourly_rate: Any | None = None,
    special_agreement: dict[str, Any] | None = None,
    employment_from: Any | None = None,
    employment_to: Any | None = None,
) -> dict[str, Any]:
    """Resolve one week's weekly-holiday payroll effect with full trace."""
    treatment = resolve_weekly_holiday_pay_treatment(
        labor_status=labor_status,
        pay_basis=pay_basis,
        special_agreement=special_agreement,
    )

    eligibility = evaluate_weekly_holiday_eligibility(
        worker_id=worker_id,
        week_start=week_start,
        week_end=week_end,
        worktime_rows=worktime_rows,
        absence_events=absence_events,
        weekly_scheduled_hours=weekly_scheduled_hours,
        employment_from=employment_from,
        employment_to=employment_to,
    )

    hours_result = None
    weekly_holiday_hours = None
    if treatment["applicable"] and eligibility["eligible"]:
        hours_result = calculate_four_week_weekly_holiday_hours(
            weekly_prescribed_hours=weekly_scheduled_hours,
            ordinary_worker_weekly_prescribed_days=ordinary_worker_weekly_prescribed_days,
        )
        weekly_holiday_hours = hours_result["weekly_holiday_hours"]

    monetary = calculate_weekly_holiday_pay(
        eligibility=eligibility,
        treatment=treatment,
        hourly_rate=hourly_rate,
        weekly_holiday_hours=weekly_holiday_hours,
    )

    return {
        "worker_id": str(worker_id).strip(),
        "week_start": eligibility["week_start"],
        "week_end": eligibility["week_end"],
        "eligibility": eligibility,
        "hours": hours_result,
        "treatment": treatment,
        "monetary": monetary,
        "earning_line": monetary["earning_line"],
    }
