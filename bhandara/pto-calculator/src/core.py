"""Pure deterministic PTO accrual calculations.

Legal baseline: Korean Labor Standards Act Article 60.
Attendance eligibility is supplied by the caller; v1 defaults to satisfied.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Callable, Iterable

ELIGIBLE = "ELIGIBLE"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
UNDETERMINED = "UNDETERMINED"


MAX_MONTHLY_DAYS = 11
BASE_ANNUAL_DAYS = 15
MAX_ANNUAL_DAYS = 25


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def monthly_grant_evaluations(
    hire_date: date,
    as_of_date: date,
    monthly_attendance_met: Callable[[date, date], bool | str] | None = None,
) -> list[dict]:
    """Evaluate each reached first-year monthly grant without losing uncertainty."""
    if as_of_date <= hire_date:
        return []

    monthly_attendance_met = monthly_attendance_met or (lambda _start, _end: True)
    first_anniversary = add_months(hire_date, 12)
    evaluations: list[dict] = []

    for month in range(1, MAX_MONTHLY_DAYS + 1):
        grant_date = add_months(hire_date, month)
        if grant_date > as_of_date or grant_date >= first_anniversary:
            continue

        period_start = add_months(hire_date, month - 1)
        period_end = grant_date.fromordinal(grant_date.toordinal() - 1)
        eligibility = monthly_attendance_met(period_start, period_end)

        if eligibility is True or eligibility == ELIGIBLE:
            status = ELIGIBLE
        elif eligibility == UNDETERMINED:
            status = UNDETERMINED
        else:
            status = NOT_ELIGIBLE

        evaluations.append({
            "grant_date": grant_date,
            "period_start": period_start,
            "period_end": period_end,
            "eligibility": status,
        })

    return evaluations


def completed_month_grants(
    hire_date: date,
    as_of_date: date,
    monthly_attendance_met: Callable[[date, date], bool | str] | None = None,
) -> list[date]:
    """Return only confirmed first-year monthly grant dates."""
    return [
        item["grant_date"]
        for item in monthly_grant_evaluations(
            hire_date,
            as_of_date,
            monthly_attendance_met,
        )
        if item["eligibility"] == ELIGIBLE
    ]


def annual_days_for_service_year(service_year: int) -> int:
    """Days granted after completing service_year years.

    Examples: 1y=15, 2y=15, 3y=16, 4y=16, 5y=17.
    """
    if service_year < 1:
        return 0
    additional = max(0, (service_year - 1) // 2)
    return min(BASE_ANNUAL_DAYS + additional, MAX_ANNUAL_DAYS)


def anniversary_grants(
    hire_date: date,
    as_of_date: date,
    monthly_attendance_met: Callable[[date, date], bool | str] | None = None,
    annual_attendance_met: Callable[[date, date], bool | str] | None = None,
) -> list[dict]:
    """Build statutory anniversary-basis grants with separate attendance rules.

    monthly_attendance_met evaluates completed months and the low-attendance
    yearly fallback. annual_attendance_met evaluates completed service years.
    Omitted evaluators preserve the v1 assumption that requirements are met.
    """
    events: list[dict] = []
    annual_attendance_met = annual_attendance_met or (lambda _start, _end: True)

    for evaluation in monthly_grant_evaluations(
        hire_date,
        as_of_date,
        monthly_attendance_met,
    ):
        if evaluation["eligibility"] == ELIGIBLE:
            events.append({
                "grant_date": evaluation["grant_date"],
                "grant_type": "monthly",
                "raw_days": Decimal("1"),
            })
        elif evaluation["eligibility"] == UNDETERMINED:
            events.append({
                "grant_date": evaluation["grant_date"],
                "grant_type": "monthly",
                "raw_days": None,
                "eligibility": UNDETERMINED,
            })

    service_year = 1
    while True:
        grant_date = add_months(hire_date, service_year * 12)
        if grant_date > as_of_date:
            break

        period_start = add_months(hire_date, (service_year - 1) * 12)
        period_end = grant_date.fromordinal(grant_date.toordinal() - 1)
        eligibility = annual_attendance_met(period_start, period_end)
        if eligibility is True or eligibility == ELIGIBLE:
            events.append({
                "grant_date": grant_date,
                "grant_type": "annual",
                "service_year": service_year,
                "raw_days": Decimal(annual_days_for_service_year(service_year)),
            })
        elif eligibility is False or eligibility == NOT_ELIGIBLE:
            # Article 60(2): when annual attendance is below 80%, award
            # one day for each fully attended month in the COMPLETED service
            # year, to be granted in the following service year (MOLEG
            # opinions 24-0114 and 24-0674).
            #
            # Months 1..11 of the first year were already considered above
            # as first-year monthly entitlements. Do not double-award them.
            check_from = 11 if service_year == 1 else 0
            for month in range(check_from, 12):
                period_start = add_months(
                    hire_date, (service_year - 1) * 12 + month
                )
                next_boundary = add_months(
                    hire_date, (service_year - 1) * 12 + month + 1
                )
                period_end = next_boundary.fromordinal(next_boundary.toordinal() - 1)
                monthly_eligibility = (
                    monthly_attendance_met(period_start, period_end)
                    if monthly_attendance_met else ELIGIBLE
                )
                if monthly_eligibility is True or monthly_eligibility == ELIGIBLE:
                    events.append({
                        "grant_date": grant_date,
                        "grant_type": "monthly_under_80",
                        "service_year": service_year,
                        "period_start": period_start,
                        "period_end": period_end,
                        "raw_days": Decimal("1"),
                    })
                elif monthly_eligibility == UNDETERMINED:
                    events.append({
                        "grant_date": grant_date,
                        "grant_type": "monthly_under_80",
                        "service_year": service_year,
                        "period_start": period_start,
                        "period_end": period_end,
                        "raw_days": None,
                        "eligibility": UNDETERMINED,
                    })
        elif eligibility == UNDETERMINED:
            events.append({
                "grant_date": grant_date,
                "grant_type": "annual",
                "service_year": service_year,
                "raw_days": None,
                "eligibility": UNDETERMINED,
            })
        service_year += 1

    return sorted(events, key=lambda item: item["grant_date"])


def fiscal_first_year_proration(
    hire_date: date,
    fiscal_year_end: date,
    annual_base_days: Decimal = Decimal("15"),
) -> Decimal:
    """Calendar/fiscal first-year proration by inclusive calendar days.

    This is a deterministic default for the common Jan-Dec policy.
    Company policy may replace the denominator/numerator with scheduled workdays.
    """
    if fiscal_year_end < hire_date:
        return Decimal("0")
    year_start = date(fiscal_year_end.year, 1, 1)
    if hire_date < year_start:
        raise ValueError("hire_date must be within fiscal_year_end.year")

    numerator = Decimal((fiscal_year_end - hire_date).days + 1)
    denominator = Decimal((fiscal_year_end - year_start).days + 1)
    return annual_base_days * numerator / denominator


def ceil_half_day(raw_days: Decimal) -> Decimal:
    """Operational representation: ceil positive fractions to 0.5-day units."""
    if raw_days < 0:
        raise ValueError("raw_days must be non-negative")
    return (raw_days * 2).to_integral_value(rounding=ROUND_CEILING) / Decimal(2)


def total_days(events: Iterable[dict]) -> Decimal:
    return sum((Decimal(event["raw_days"]) for event in events), Decimal("0"))
