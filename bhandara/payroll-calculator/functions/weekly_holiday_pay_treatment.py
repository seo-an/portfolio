"""Resolve weekly-holiday applicability and monetary treatment policy."""

from __future__ import annotations

from typing import Any


LABOR_STATUSES = {"employee", "non_employee"}
PAY_BASES = {"monthly", "daily", "hourly"}
TREATMENTS = {"included_in_monthly_pay", "separately_calculated", "not_applicable"}


class WeeklyHolidayPayTreatmentError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Weekly holiday pay treatment failed: {message}"
        )


def resolve_weekly_holiday_pay_treatment(
    labor_status: str,
    pay_basis: str,
    special_agreement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve treatment without inferring it from employment_type."""
    status = str(labor_status).strip()
    basis = str(pay_basis).strip()

    if status not in LABOR_STATUSES:
        raise WeeklyHolidayPayTreatmentError(
            f"unsupported labor_status: {status}"
        )
    if basis not in PAY_BASES:
        raise WeeklyHolidayPayTreatmentError(
            f"unsupported pay_basis: {basis}"
        )

    if status == "non_employee":
        return {
            "applicable": False,
            "pay_basis": basis,
            "treatment": "not_applicable",
            "source": "labor_status",
        }

    if special_agreement is not None:
        treatment = str(special_agreement.get("weekly_holiday_pay_treatment", "")).strip()
        if treatment not in TREATMENTS - {"not_applicable"}:
            raise WeeklyHolidayPayTreatmentError(
                f"unsupported special agreement treatment: {treatment}"
            )
        return {
            "applicable": True,
            "pay_basis": basis,
            "treatment": treatment,
            "source": "special_agreement",
        }

    default_treatment = (
        "included_in_monthly_pay"
        if basis == "monthly"
        else "separately_calculated"
    )
    return {
        "applicable": True,
        "pay_basis": basis,
        "treatment": default_treatment,
        "source": "default",
    }
