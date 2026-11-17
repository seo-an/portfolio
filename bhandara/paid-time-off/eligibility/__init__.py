"""Independent attendance-eligibility decisions from verified period evidence.

Caller owns daily-fact preparation and provenance.  This module never imports
entitlement or another PTO business module and never presumes missing evidence
is satisfactory.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

ELIGIBLE = "ELIGIBLE"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
UNDETERMINED = "UNDETERMINED"
FINAL = "FINAL"
ANNUAL_THRESHOLD = Decimal("0.80")


def _days(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative number")
    try:
        amount = Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValueError(f"{name} must be a non-negative number") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return amount


def _decision(status: str, codes: list[str], rate: Decimal | None = None) -> dict:
    return {
        "eligibility": status,
        "attendance_rate": str(rate) if rate is not None else None,
        "review_codes": codes,
        "approved": False,
        "finalizable": False,
    }


def evaluate_monthly_full_attendance(
    *,
    denominator_included_days: object,
    not_present_days: object,
    coverage_complete: bool,
    source_status: str,
) -> dict:
    """Monthly all-present rule. Evidence must already be period-scoped.

    No hours, non-workdays, holidays or approved-leave credits are inferred.
    Those classification decisions belong to the evidence preparation policy.
    """
    denominator = _days(denominator_included_days, "denominator_included_days")
    absent = _days(not_present_days, "not_present_days")
    if denominator is not None and absent is not None and absent > denominator:
        raise ValueError("not_present_days exceeds denominator_included_days")
    if coverage_complete is not True or source_status != FINAL:
        return _decision(UNDETERMINED, ["PERIOD_EVIDENCE_NOT_FINAL"])
    if denominator is None or absent is None or denominator == 0:
        return _decision(UNDETERMINED, ["PERIOD_EVIDENCE_INCOMPLETE"])
    return _decision(ELIGIBLE if absent == 0 else NOT_ELIGIBLE, [])


def evaluate_annual_attendance_80(
    *,
    denominator_included_days: object,
    attendance_credited_days: object,
    coverage_complete: bool,
    source_status: str,
) -> dict:
    """80% threshold from an independently verified daily-fact summary."""
    denominator = _days(denominator_included_days, "denominator_included_days")
    credited = _days(attendance_credited_days, "attendance_credited_days")
    if denominator is not None and credited is not None and credited > denominator:
        raise ValueError("attendance_credited_days exceeds denominator_included_days")
    if coverage_complete is not True or source_status != FINAL:
        return _decision(UNDETERMINED, ["PERIOD_EVIDENCE_NOT_FINAL"])
    if denominator is None or credited is None or denominator == 0:
        return _decision(UNDETERMINED, ["PERIOD_EVIDENCE_INCOMPLETE"])
    rate = credited / denominator
    return _decision(
        ELIGIBLE if rate >= ANNUAL_THRESHOLD else NOT_ELIGIBLE,
        [], rate,
    )
