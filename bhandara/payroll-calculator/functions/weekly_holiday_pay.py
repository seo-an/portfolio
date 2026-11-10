"""Convert weekly-holiday eligibility and treatment into a payroll earning."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class WeeklyHolidayPayError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Weekly holiday pay failed: {message}")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise WeeklyHolidayPayError(f"{field} must be decimal-compatible") from exc
    if result < 0:
        raise WeeklyHolidayPayError(f"{field} must not be negative")
    return result


def calculate_weekly_holiday_pay(
    eligibility: dict[str, Any],
    treatment: dict[str, Any],
    hourly_rate: Any | None = None,
    weekly_holiday_hours: Any | None = None,
) -> dict[str, Any]:
    """Return monetary effect without deriving weekly-holiday hours itself."""
    eligible = bool(eligibility.get("eligible"))
    applicable = bool(treatment.get("applicable"))
    mode = str(treatment.get("treatment", "")).strip()

    base = {
        "pay_item_code": "weekly_holiday_pay",
        "eligible": eligible,
        "applicable": applicable,
        "treatment": mode,
        "calculated_amount": Decimal("0"),
        "earning_line": None,
    }

    if not applicable or mode == "not_applicable":
        return {**base, "reason": "not_applicable"}

    if not eligible:
        return {**base, "reason": "not_eligible"}

    if mode == "included_in_monthly_pay":
        return {**base, "reason": "included_in_monthly_pay"}

    if mode != "separately_calculated":
        raise WeeklyHolidayPayError(f"unsupported treatment: {mode}")

    if hourly_rate is None:
        raise WeeklyHolidayPayError(
            "hourly_rate is required for separately_calculated treatment"
        )
    if weekly_holiday_hours is None:
        raise WeeklyHolidayPayError(
            "weekly_holiday_hours is required for separately_calculated treatment"
        )

    rate = _decimal(hourly_rate, "hourly_rate")
    hours = _decimal(weekly_holiday_hours, "weekly_holiday_hours")
    amount = rate * hours
    line = {
        "pay_item_code": "weekly_holiday_pay",
        "calculated_amount": amount,
        "weekly_holiday_hours": hours,
        "hourly_rate": rate,
    }
    return {
        **base,
        "calculated_amount": amount,
        "earning_line": line,
        "reason": "separately_calculated",
    }
