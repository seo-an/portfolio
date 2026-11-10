"""Resolve paid weekly-holiday hours from prescribed working time."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class WeeklyHolidayHoursError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Weekly holiday hours failed: {message}")


def _positive_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise WeeklyHolidayHoursError(f"{field} must be decimal-compatible") from exc
    if result <= 0:
        raise WeeklyHolidayHoursError(f"{field} must be greater than zero")
    return result


def calculate_weekly_holiday_hours(
    prescribed_hours_in_reference_period: Any,
    ordinary_worker_prescribed_days_in_reference_period: Any,
) -> dict[str, Any]:
    """Calculate one paid holiday day's hours.

    For part-time workers, Enforcement Decree of the Labor Standards Act
    Appendix 2 uses prescribed hours over the reference period divided by
    the ordinary worker's prescribed workdays over the same period.
    """
    hours = _positive_decimal(
        prescribed_hours_in_reference_period,
        "prescribed_hours_in_reference_period",
    )
    ordinary_days = _positive_decimal(
        ordinary_worker_prescribed_days_in_reference_period,
        "ordinary_worker_prescribed_days_in_reference_period",
    )
    resolved = hours / ordinary_days
    return {
        "weekly_holiday_hours": resolved,
        "prescribed_hours_in_reference_period": hours,
        "ordinary_worker_prescribed_days_in_reference_period": ordinary_days,
        "method": "prescribed_hours_divided_by_ordinary_worker_prescribed_days",
    }


def calculate_four_week_weekly_holiday_hours(
    weekly_prescribed_hours: Any,
    ordinary_worker_weekly_prescribed_days: Any = Decimal("5"),
) -> dict[str, Any]:
    """Convenience calculation for a stable four-week prescribed schedule."""
    weekly_hours = _positive_decimal(weekly_prescribed_hours, "weekly_prescribed_hours")
    weekly_days = _positive_decimal(
        ordinary_worker_weekly_prescribed_days,
        "ordinary_worker_weekly_prescribed_days",
    )
    return calculate_weekly_holiday_hours(
        prescribed_hours_in_reference_period=weekly_hours * Decimal("4"),
        ordinary_worker_prescribed_days_in_reference_period=weekly_days * Decimal("4"),
    )
