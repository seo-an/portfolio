"""Resolve eligibility facts into policy-controlled payable periods."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any


class EligibilityResolutionError(RuntimeError):
    """Raised when an eligibility period cannot be resolved deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Eligibility resolution failed: {message}"
        )


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise EligibilityResolutionError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise EligibilityResolutionError(
        f"{field} must be a date or YYYY-MM-DD string"
    )


def _next_month_start(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def resolve_payable_period(
    eligibility_from: Any,
    payable_rule: Any,
    eligibility_to: Any | None = None,
) -> dict[str, Any]:
    """Convert an eligibility fact period into a payable period."""
    eligible_from = _date(eligibility_from, "eligibility_from")
    eligible_to = (
        _date(eligibility_to, "eligibility_to")
        if eligibility_to not in (None, "")
        else None
    )
    if eligible_to is not None and eligible_to < eligible_from:
        raise EligibilityResolutionError(
            "eligibility_to precedes eligibility_from"
        )

    rule = str(payable_rule).strip() if payable_rule is not None else ""
    supported = {
        "from_eligibility_date",
        "next_month",
        "eligibility_month_full",
    }
    if rule not in supported:
        raise EligibilityResolutionError(
            f"unsupported payable_rule: {payable_rule!r}"
        )

    if rule == "from_eligibility_date":
        payable_from = eligible_from
    elif rule == "next_month":
        payable_from = _next_month_start(eligible_from)
    else:
        payable_from = eligible_from.replace(day=1)

    payable_to = eligible_to
    payable_status = "PAYABLE"
    if payable_to is not None and payable_to < payable_from:
        payable_from = None
        payable_to = None
        payable_status = "NOT_PAYABLE"

    return {
        "eligibility_from": eligible_from,
        "eligibility_to": eligible_to,
        "payable_rule": rule,
        "payable_status": payable_status,
        "payable_from": payable_from,
        "payable_to": payable_to,
    }
