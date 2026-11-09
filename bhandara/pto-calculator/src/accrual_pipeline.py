"""End-to-end PTO accrual orchestration from resolved daily records."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from .aggregation import aggregate_attendance_period
from .core import anniversary_grants
from .eligibility import build_attendance_eligibility_callbacks


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
            period_start = grant["grant_date"]
            # Core monthly uncertainty details are recovered from the preceding
            # employment month by matching the grant boundary.
            from .core import add_months
            period_start = add_months(grant["grant_date"], -1)
        else:
            from .core import add_months
            period_start = add_months(
                hire_date,
                (grant["service_year"] - 1) * 12,
            )
        period_end = grant["grant_date"].fromordinal(
            grant["grant_date"].toordinal() - 1
        )
        summary = aggregate_attendance_period(
            record
            for record in records
            if period_start <= record["work_date"] <= period_end
        )
        unresolved.append({
            "grant_date": grant["grant_date"],
            "grant_type": grant["grant_type"],
            "period_start": period_start,
            "period_end": period_end,
            "unresolved_reasons": summary["unresolved_reasons"],
        })

    return {
        "hire_date": hire_date,
        "as_of_date": as_of_date,
        "grants": grants,
        "unresolved_grants": unresolved,
    }
