"""End-to-end PTO accrual orchestration from resolved daily records."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from .aggregation import aggregate_attendance_period
from .core import add_months, anniversary_grants
from .eligibility import (
    build_attendance_eligibility_callbacks,
    has_complete_calendar_coverage,
)


def calculate_anniversary_accrual(
    *,
    hire_date: date,
    as_of_date: date,
    daily_records: Iterable[dict],
) -> dict:
    """Calculate anniversary-basis grants from deterministic daily facts."""
    records = list(daily_records)
    monthly_callback, annual_callback = build_attendance_eligibility_callbacks(records)
    grants = anniversary_grants(
        hire_date=hire_date,
        as_of_date=as_of_date,
        monthly_attendance_met=monthly_callback,
        annual_attendance_met=annual_callback,
    )

    unresolved = []
    for grant in grants:
        if grant.get("eligibility") != "UNDETERMINED":
            continue
        if grant["grant_type"] == "monthly":
            # Reverse-clamping grant_date (e.g. Feb 28 -> Jan 28) is unsafe.
            # Recover month boundaries from the ORIGINAL hire-date anchor.
            matched_month = next(
                month for month in range(1, 12)
                if add_months(hire_date, month) == grant["grant_date"]
            )
            period_start = add_months(hire_date, matched_month - 1)
            period_end = grant["grant_date"].fromordinal(
                grant["grant_date"].toordinal() - 1
            )
        elif grant["grant_type"] == "monthly_under_80":
            period_start, period_end = grant["period_start"], grant["period_end"]
        else:
            period_start = add_months(
                hire_date, (grant["service_year"] - 1) * 12
            )
            period_end = grant["grant_date"].fromordinal(
                grant["grant_date"].toordinal() - 1
            )
        period_records = [
            record for record in records
            if period_start <= record["work_date"] <= period_end
        ]
        summary = aggregate_attendance_period(period_records)
        reasons = list(summary["unresolved_reasons"])
        if not has_complete_calendar_coverage(
            period_records, period_start, period_end
        ):
            reasons.append({
                "work_date": None,
                "reasons": ["PERIOD_SOURCE_COVERAGE_INCOMPLETE"],
                "resolution_categories": ["DATA_REQUIRED"],
            })
        if summary["denominator_included_days"] == 0:
            reasons.append({
                "work_date": None,
                "reasons": ["NO_SCHEDULED_WORKDAYS"],
                "resolution_categories": ["POLICY_REVIEW_REQUIRED"],
            })
        unresolved.append({
            "grant_date": grant["grant_date"],
            "grant_type": grant["grant_type"],
            "period_start": period_start,
            "period_end": period_end,
            "unresolved_reasons": reasons,
        })

    return {
        "hire_date": hire_date,
        "as_of_date": as_of_date,
        "grants": grants,
        "unresolved_grants": unresolved,
    }
