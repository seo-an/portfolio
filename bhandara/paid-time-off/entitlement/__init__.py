"""Independent anniversary-basis leave grant calculations.

Eligibility is explicit caller evidence, not an imported or implicitly
executed module.  Fiscal-year grants require a separately reviewed policy
contract and are intentionally NOT provided by this first migration slice.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

ELIGIBLE = "ELIGIBLE"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
UNDETERMINED = "UNDETERMINED"
_STATUSES = {ELIGIBLE, NOT_ELIGIBLE, UNDETERMINED}

MAX_MONTHLY_DAYS = 11
BASE_ANNUAL_DAYS = 15
MAX_ANNUAL_DAYS = 25
EligibilityResolver = Callable[[date, date], str]


def add_months(anchor: date, months: int) -> date:
    """Month boundary is always recalculated from the original hire anchor."""
    month_index = anchor.year * 12 + anchor.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def annual_days_for_service_year(service_year: int) -> int:
    if isinstance(service_year, bool) or not isinstance(service_year, int):
        raise ValueError("service_year must be an integer")
    if service_year < 1:
        return 0
    return min(BASE_ANNUAL_DAYS + max(0, (service_year - 1) // 2),
               MAX_ANNUAL_DAYS)


def _resolve(resolver: EligibilityResolver, start: date, end: date) -> str:
    if not callable(resolver):
        raise ValueError("explicit eligibility resolver is required")
    status = resolver(start, end)
    if status not in _STATUSES:
        raise ValueError("eligibility must be ELIGIBLE, NOT_ELIGIBLE or UNDETERMINED")
    return status


def _grant(
    grant_date: date, grant_type: str, status: str, days: Decimal,
    *, service_year: int | None = None,
    period_start: date | None = None, period_end: date | None = None,
) -> dict:
    return {
        "grant_date": grant_date,
        "grant_type": grant_type,
        "service_year": service_year,
        "period_start": period_start,
        "period_end": period_end,
        "eligibility": status,
        "raw_days": days if status == ELIGIBLE else None,
    }


def calculate_first_year_monthly_grants(
    *,
    hire_date: date,
    as_of_date: date,
    monthly_eligibility: EligibilityResolver,
) -> list[dict]:
    """Return hire-date monthly grants for months 1..11, without annual grants.

    Shared by anniversary and fiscal-year calculations. Missing attendance
    evidence stays UNDETERMINED; it must never become zero or an approval.
    """
    if not isinstance(hire_date, date) or not isinstance(as_of_date, date):
        raise ValueError("hire_date and as_of_date must be dates")
    if not callable(monthly_eligibility):
        raise ValueError("explicit monthly eligibility resolver is required")
    if as_of_date <= hire_date:
        return []

    first_anniversary = add_months(hire_date, 12)
    grants: list[dict] = []
    for month in range(1, MAX_MONTHLY_DAYS + 1):
        grant_date = add_months(hire_date, month)
        if grant_date > as_of_date or grant_date >= first_anniversary:
            continue
        start = add_months(hire_date, month - 1)
        end = grant_date - timedelta(days=1)
        status = _resolve(monthly_eligibility, start, end)
        if status != NOT_ELIGIBLE:
            grants.append(_grant(
                grant_date, "monthly", status, Decimal("1"),
                period_start=start, period_end=end,
            ))
    return grants


def calculate_anniversary_grants(
    *,
    hire_date: date,
    as_of_date: date,
    monthly_eligibility: EligibilityResolver,
    annual_eligibility: EligibilityResolver,
) -> list[dict]:
    """Calculate grants only; no usage, balances, expiry, closing or approvals.

    Monthly/annual evaluators are provided explicitly by the caller.  An
    unresolved evaluation yields no numeric grant amount.
    """
    if not isinstance(hire_date, date) or not isinstance(as_of_date, date):
        raise ValueError("hire_date and as_of_date must be dates")
    if not callable(monthly_eligibility) or not callable(annual_eligibility):
        raise ValueError("both explicit eligibility resolvers are required")
    if as_of_date <= hire_date:
        return []
    grants = calculate_first_year_monthly_grants(
        hire_date=hire_date, as_of_date=as_of_date,
        monthly_eligibility=monthly_eligibility,
    )

    service_year = 1
    while True:
        grant_date = add_months(hire_date, service_year * 12)
        if grant_date > as_of_date:
            break
        start = add_months(hire_date, (service_year - 1) * 12)
        end = grant_date - timedelta(days=1)
        status = _resolve(annual_eligibility, start, end)
        if status != NOT_ELIGIBLE:
            grants.append(_grant(
                grant_date, "annual", status,
                Decimal(annual_days_for_service_year(service_year)),
                service_year=service_year, period_start=start, period_end=end,
            ))
        else:
            # First-year months 1..11 were evaluated above: never double-award.
            month_start = 11 if service_year == 1 else 0
            for offset in range(month_start, 12):
                start = add_months(hire_date, (service_year - 1) * 12 + offset)
                end = add_months(hire_date, (service_year - 1) * 12 + offset + 1) - timedelta(days=1)
                monthly_status = _resolve(monthly_eligibility, start, end)
                if monthly_status != NOT_ELIGIBLE:
                    grants.append(_grant(
                        grant_date, "monthly_under_80", monthly_status, Decimal("1"),
                        service_year=service_year, period_start=start, period_end=end,
                    ))
        service_year += 1
    return sorted(grants, key=lambda grant: grant["grant_date"])
