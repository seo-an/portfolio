"""Evaluate weekly-holiday eligibility from schedule and attendance facts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class WeeklyHolidayEligibilityError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Weekly holiday eligibility failed: {message}"
        )


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise WeeklyHolidayEligibilityError(
            f"{field} must use YYYY-MM-DD"
        ) from exc


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise WeeklyHolidayEligibilityError(
            f"{field} must be decimal-compatible"
        ) from exc
    if result < 0:
        raise WeeklyHolidayEligibilityError(f"{field} must not be negative")
    return result


def evaluate_weekly_holiday_eligibility(
    worker_id: str,
    week_start: Any,
    week_end: Any,
    worktime_rows: list[dict[str, Any]],
    absence_events: list[dict[str, Any]],
    weekly_scheduled_hours: Any,
    employment_from: Any | None = None,
    employment_to: Any | None = None,
) -> dict[str, Any]:
    """Evaluate eligibility without calculating its monetary effect."""
    start = _date(week_start, "week_start")
    end = _date(week_end, "week_end")
    if (end - start).days != 6:
        raise WeeklyHolidayEligibilityError(
            "week_start and week_end must define 7 consecutive days"
        )

    scheduled_hours = _decimal(weekly_scheduled_hours, "weekly_scheduled_hours")
    employment_start = (
        _date(employment_from, "employment_from")
        if employment_from is not None else start
    )
    employment_end = (
        _date(employment_to, "employment_to")
        if employment_to is not None else end
    )

    target = str(worker_id).strip()
    scheduled_dates: set[date] = set()
    actual_work_dates: set[date] = set()
    for row in worktime_rows:
        if str(row.get("worker_id", "")).strip() != target:
            continue
        work_date = _date(row.get("work_date"), "work_date")
        if not start <= work_date <= end:
            continue
        if _decimal(row.get("scheduled_hours", 0), "scheduled_hours") > 0:
            scheduled_dates.add(work_date)
        if _decimal(row.get("worked_hours", 0), "worked_hours") > 0:
            actual_work_dates.add(work_date)

    breaking_dates: list[date] = []
    leave_dates: list[date] = []
    for event in absence_events:
        if str(event.get("worker_id", "")).strip() != target:
            continue
        work_date = _date(event.get("work_date"), "work_date")
        if not start <= work_date <= end or work_date not in scheduled_dates:
            continue
        treatment = str(event.get("attendance_treatment", "")).strip()
        if treatment == "absence":
            breaking_dates.append(work_date)
        elif treatment == "leave":
            leave_dates.append(work_date)
        else:
            raise WeeklyHolidayEligibilityError(
                f"unsupported attendance_treatment: {treatment}"
            )

    reasons = []
    eligible = True
    if scheduled_hours < Decimal("15"):
        eligible = False
        reasons.append("weekly_scheduled_hours_below_15")
    if employment_end < end:
        eligible = False
        reasons.append("employment_ended_before_weekly_holiday")
    if not scheduled_dates:
        eligible = False
        reasons.append("no_scheduled_workdays")
    if breaking_dates:
        eligible = False
        reasons.append("absence_on_scheduled_day")
    if scheduled_dates and not actual_work_dates:
        eligible = False
        reasons.append("no_actual_work_in_week")

    if eligible:
        reasons.append("eligible")

    return {
        "worker_id": target,
        "week_start": start,
        "week_end": end,
        "eligible": eligible,
        "reason_codes": reasons,
        "weekly_scheduled_hours": scheduled_hours,
        "scheduled_work_dates": sorted(scheduled_dates),
        "actual_work_dates": sorted(actual_work_dates),
        "attendance_breaking_dates": sorted(set(breaking_dates)),
        "leave_dates": sorted(set(leave_dates)),
    }
