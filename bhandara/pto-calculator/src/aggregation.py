"""Aggregate daily PTO attendance records without reinterpreting legal policy."""

from __future__ import annotations

from typing import Iterable

from .unresolved_reason import build_unresolved_diagnostic, classify_unresolved_reason


FINAL = "FINAL"
NOT_FINAL = "NOT_FINAL"


def aggregate_attendance_period(daily_records: Iterable[dict]) -> dict:
    """Aggregate already-resolved daily records for one employee-period.

    Any unresolved included-day denominator/credit prevents a final
    attendance rate. Counts remain visible for diagnostics.
    """

    records = list(daily_records)

    summary = {
        "calendar_days": len(records),
        "scheduled_work_days_raw": 0,
        "outside_employment_days": 0,
        "denominator_included_days": 0,
        "denominator_excluded_days": 0,
        "denominator_review_days": 0,
        "credited_present_days": 0,
        "credited_deemed_present_days": 0,
        "not_present_days": 0,
        "unresolved_days": 0,
    }

    unresolved_dates = []
    unresolved_reasons = []
    diagnostics = []

    for record in records:
        if record.get("scheduled_work_day"):
            summary["scheduled_work_days_raw"] += 1

        employment = record.get("employment", {})
        if not employment.get("within_employment", False):
            summary["outside_employment_days"] += 1

        denominator = record.get("attendance_denominator")
        credit = record.get("attendance_credit")
        policy = record.get("attendance_policy", {})

        if denominator == "INCLUDED":
            summary["denominator_included_days"] += 1
        elif denominator == "EXCLUDED":
            summary["denominator_excluded_days"] += 1
        else:
            summary["denominator_review_days"] += 1

        if credit == "PRESENT":
            summary["credited_present_days"] += 1
        elif credit == "DEEMED_PRESENT":
            summary["credited_deemed_present_days"] += 1
        elif credit == "NOT_PRESENT":
            summary["not_present_days"] += 1

        unresolved = (
            denominator == "REVIEW"
            or (denominator == "INCLUDED" and credit == "REVIEW")
            or record.get("employee_event", {}).get("status") == "CONFLICT"
        )
        if unresolved:
            summary["unresolved_days"] += 1
            work_date = record.get("work_date")
            unresolved_dates.append(work_date)

            reasons = []
            if record.get("employee_event", {}).get("status") == "CONFLICT":
                reasons.append("EVENT_CONFLICT")
            if denominator == "REVIEW" or (
                denominator == "INCLUDED" and credit == "REVIEW"
            ):
                policy_reason = policy.get("reason")
                if policy_reason:
                    reasons.append(policy_reason)
                elif not reasons:
                    reasons.append("ATTENDANCE_POLICY_UNRESOLVED")

            unique_reasons = sorted(set(reasons))
            unresolved_reasons.append({
                "work_date": work_date,
                "reasons": unique_reasons,
                "resolution_categories": sorted({
                    classify_unresolved_reason(reason)
                    for reason in unique_reasons
                }),
            })
            diagnostics.extend(
                build_unresolved_diagnostic(reason, work_date=work_date)
                for reason in unique_reasons
            )

    finalizable = summary["unresolved_days"] == 0
    credited_days = (
        summary["credited_present_days"]
        + summary["credited_deemed_present_days"]
    )

    attendance_rate = None
    if finalizable and summary["denominator_included_days"] > 0:
        attendance_rate = credited_days / summary["denominator_included_days"]

    return {
        **summary,
        "credited_days": credited_days,
        "attendance_rate": attendance_rate,
        "status": FINAL if finalizable else NOT_FINAL,
        "unresolved_dates": unresolved_dates,
        "unresolved_reasons": unresolved_reasons,
        "diagnostics": diagnostics,
    }
