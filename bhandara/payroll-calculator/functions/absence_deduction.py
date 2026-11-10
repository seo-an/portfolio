"""Calculate absence deductions using comparable fallback methods."""

from __future__ import annotations

import calendar
from decimal import Decimal, InvalidOperation
from typing import Any


class AbsenceDeductionError(RuntimeError):
    """Raised when an absence deduction cannot be calculated safely."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Absence deduction failed: {message}")


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AbsenceDeductionError(f"{field} must be decimal-compatible") from exc
    if positive and result <= 0:
        raise AbsenceDeductionError(f"{field} must be greater than zero")
    if not positive and result < 0:
        raise AbsenceDeductionError(f"{field} must not be negative")
    return result


def _calendar_days(payroll_period: str) -> int:
    try:
        year_text, month_text = str(payroll_period).split("-")
        return calendar.monthrange(int(year_text), int(month_text))[1]
    except (TypeError, ValueError) as exc:
        raise AbsenceDeductionError("payroll_period must use YYYY-MM") from exc


def calculate_calendar_day_deduction(
    monthly_amount: Any,
    payroll_period: str,
    deduction_days: Any,
) -> dict[str, Any]:
    """Type A: monthly amount / calendar days * deduction days."""
    amount = _decimal(monthly_amount, "monthly_amount")
    days = _decimal(deduction_days, "deduction_days")
    denominator = Decimal(_calendar_days(payroll_period))
    calculated = amount / denominator * days
    return {
        "method": "calendar_days",
        "monthly_amount": amount,
        "denominator_days": denominator,
        "deduction_days": days,
        "calculated_amount": calculated,
    }


def calculate_paid_day_basis_deduction(
    monthly_amount: Any,
    scheduled_workdays: Any,
    paid_treatment_days: Any,
    deduction_days: Any,
) -> dict[str, Any]:
    """Type B: monthly amount / (scheduled workdays + paid days) * deduction days."""
    amount = _decimal(monthly_amount, "monthly_amount")
    scheduled = _decimal(scheduled_workdays, "scheduled_workdays")
    paid = _decimal(paid_treatment_days, "paid_treatment_days")
    days = _decimal(deduction_days, "deduction_days")
    denominator = scheduled + paid
    if denominator <= 0:
        raise AbsenceDeductionError(
            "scheduled_workdays + paid_treatment_days must be greater than zero"
        )
    calculated = amount / denominator * days
    return {
        "method": "paid_day_basis",
        "monthly_amount": amount,
        "scheduled_workdays": scheduled,
        "paid_treatment_days": paid,
        "denominator_days": denominator,
        "deduction_days": days,
        "calculated_amount": calculated,
    }


def calculate_statutory_fallback(
    monthly_amount: Any,
    payroll_period: str,
    deduction_days: Any,
    scheduled_workdays: Any,
    paid_treatment_days: Any,
) -> dict[str, Any]:
    """Calculate both fallback methods and select the smaller deduction.

    Intermediate values remain unrounded. Final payroll amount processing is
    responsible for truncation or other configured amount handling.
    """
    type_a = calculate_calendar_day_deduction(
        monthly_amount,
        payroll_period,
        deduction_days,
    )
    type_b = calculate_paid_day_basis_deduction(
        monthly_amount,
        scheduled_workdays,
        paid_treatment_days,
        deduction_days,
    )

    candidates = [type_a, type_b]
    selected = min(
        candidates,
        key=lambda result: (result["calculated_amount"], result["method"]),
    )

    return {
        "selection": "employee_favorable",
        "selected_method": selected["method"],
        "selected_amount": selected["calculated_amount"],
        "comparison": {
            type_a["method"]: type_a,
            type_b["method"]: type_b,
        },
    }
