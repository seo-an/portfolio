"""Bridge aggregated daily attendance records to PTO accrual eligibility."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from .aggregation import FINAL, aggregate_attendance_period


ANNUAL_ATTENDANCE_THRESHOLD = 0.80

ELIGIBLE = "ELIGIBLE"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
UNDETERMINED = "UNDETERMINED"


def records_for_period(
    daily_records: Iterable[dict],
    period_start: date,
    period_end: date,
) -> list[dict]:
    if period_end < period_start:
        raise ValueError("period_end must be on or after period_start")
    return [
        record
        for record in daily_records
        if period_start <= record["work_date"] <= period_end
    ]


def evaluate_monthly_full_attendance(
    daily_records: Iterable[dict],
    period_start: date,
    period_end: date,
) -> str:
    """Return ELIGIBLE, NOT_ELIGIBLE, or UNDETERMINED for one month."""
    summary = aggregate_attendance_period(
        records_for_period(daily_records, period_start, period_end)
    )
    if summary["status"] != FINAL:
        return UNDETERMINED
    return ELIGIBLE if summary["not_present_days"] == 0 else NOT_ELIGIBLE


def evaluate_annual_attendance_80(
    daily_records: Iterable[dict],
    period_start: date,
    period_end: date,
) -> str:
    """Return ELIGIBLE, NOT_ELIGIBLE, or UNDETERMINED for annual attendance."""
    summary = aggregate_attendance_period(
        records_for_period(daily_records, period_start, period_end)
    )
    if summary["status"] != FINAL or summary["attendance_rate"] is None:
        return UNDETERMINED
    return (
        ELIGIBLE
        if summary["attendance_rate"] >= ANNUAL_ATTENDANCE_THRESHOLD
        else NOT_ELIGIBLE
    )


def build_attendance_eligibility_callbacks(daily_records: Iterable[dict]) -> tuple:
    """Build core.py-compatible monthly and annual eligibility callbacks."""
    records = list(daily_records)

    def monthly(period_start: date, period_end: date) -> str:
        return evaluate_monthly_full_attendance(records, period_start, period_end)

    def annual(period_start: date, period_end: date) -> str:
        return evaluate_annual_attendance_80(records, period_start, period_end)

    return monthly, annual
