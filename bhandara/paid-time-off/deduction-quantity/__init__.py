"""Independent requested annual-leave deduction quantity calculator.

This is quantity arithmetic only.  Request approval, overlaps, employee
schedule, holidays and ledger posting must be validated elsewhere.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

_FIXED_UNITS = {
    "DAY": Decimal("1"),
    "HALF_DAY": Decimal("0.5"),
    "QUARTER_DAY": Decimal("0.25"),
}
_HOURLY = "HOUR"


def _positive(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a finite positive number")
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValueError(f"{name} must be a finite positive number") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return number


def _format_days(value: Decimal) -> str:
    return format(value.normalize(), "f")


def calculate_deduction_quantity(
    *,
    unit: str,
    duration_hours: object = None,
    standard_daily_hours: object = None,
) -> dict:
    """Calculate a quantity, not whether the request is valid or approved.

    For hours, the caller must supply an explicit policy-controlled standard
    daily-hours denominator.  A missing denominator never becomes 8 hours.
    """
    if not isinstance(unit, str):
        raise ValueError("unit must be a declared leave unit")
    if unit in _FIXED_UNITS:
        if duration_hours is not None or standard_daily_hours is not None:
            raise ValueError("fixed-unit requests cannot carry hourly inputs")
        quantity = _FIXED_UNITS[unit]
        review_codes: list[str] = []
    elif unit == _HOURLY:
        hours = _positive(duration_hours, "duration_hours")
        if standard_daily_hours is None:
            quantity = None
            review_codes = ["HOURLY_CONVERSION_POLICY_REQUIRED"]
        else:
            denominator = _positive(standard_daily_hours, "standard_daily_hours")
            if hours > denominator:
                raise ValueError("duration_hours exceeds standard_daily_hours")
            quantity = hours / denominator
            review_codes = []
    else:
        raise ValueError("unsupported leave unit; do not infer a conversion")
    return {
        "unit": unit,
        "quantity_days": _format_days(quantity) if quantity is not None else None,
        "status": "CALCULATED" if quantity is not None else "REVIEW_REQUIRED",
        "review_codes": review_codes,
        "approved": False,
        "finalizable": False,
    }
