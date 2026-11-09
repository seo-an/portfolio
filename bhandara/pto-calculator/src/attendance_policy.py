"""Deterministic attendance denominator/credit policy for PTO accrual."""

from __future__ import annotations

from typing import Any

from .event_type import normalize_event_type


DENOMINATOR_INCLUDED = "INCLUDED"
DENOMINATOR_EXCLUDED = "EXCLUDED"
DENOMINATOR_REVIEW = "REVIEW"

CREDIT_PRESENT = "PRESENT"
CREDIT_DEEMED_PRESENT = "DEEMED_PRESENT"
CREDIT_NOT_PRESENT = "NOT_PRESENT"
CREDIT_REVIEW = "REVIEW"

BASIS_STATUTE = "STATUTE"
BASIS_OBSERVED_ATTENDANCE = "OBSERVED_ATTENDANCE"
BASIS_COMPANY_POLICY = "COMPANY_POLICY"
BASIS_REVIEW = "REVIEW"


# Event names are workflow contract identifiers, not labels copied from HR systems.
STATUTORY_DEEMED_PRESENT_EVENTS = {
    "ANNUAL_LEAVE",
    "OCCUPATIONAL_INJURY_LEAVE",
    "MATERNITY_PROTECTION_LEAVE",
    "PARENTAL_LEAVE",
}

PARTIAL_TIME_STATUTORY_DEEMED_PRESENT_EVENTS = {
    "CHILDCARE_REDUCED_HOURS",
    "PREGNANCY_REDUCED_HOURS",
}


def resolve_event_attendance_policy(event: dict[str, Any]) -> dict[str, Any]:
    """Resolve an approved employee event without guessing unknown company rules."""

    raw_event_type = event.get("event_type")
    event_type = normalize_event_type(raw_event_type)
    status = str(event.get("status") or "").upper()

    if status != "APPROVED":
        return {
            "denominator": DENOMINATOR_REVIEW,
            "credit": CREDIT_REVIEW,
            "basis_type": BASIS_REVIEW,
            "reason": "EVENT_NOT_APPROVED",
            "requires_review": True,
        }

    if event_type in STATUTORY_DEEMED_PRESENT_EVENTS:
        return {
            "denominator": DENOMINATOR_INCLUDED,
            "credit": CREDIT_DEEMED_PRESENT,
            "basis_type": BASIS_STATUTE,
            "reason": event_type,
            "requires_review": False,
        }

    if event_type in PARTIAL_TIME_STATUTORY_DEEMED_PRESENT_EVENTS:
        return {
            "denominator": DENOMINATOR_INCLUDED,
            "credit": CREDIT_REVIEW,
            "basis_type": BASIS_REVIEW,
            "reason": "REDUCED_HOURS_REQUIRES_COMPOSITION",
            "event_type": event_type,
            "requires_review": True,
        }

    return {
        "denominator": DENOMINATOR_REVIEW,
        "credit": CREDIT_REVIEW,
        "basis_type": BASIS_REVIEW,
        "reason": event_type or "UNKNOWN_EVENT",
        "raw_event_type": raw_event_type,
        "requires_review": True,
    }


def resolve_daily_attendance_policy(
    *,
    within_employment: bool,
    scheduled_work_day: bool,
    attendance_status: str,
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the legal attendance layers for one employee-date.

    Outside-employment and non-workdays are outside the attendance denominator.
    For scheduled workdays, an approved statutory deemed-present event can
    override missing physical attendance. Unknown events remain REVIEW.
    """

    if not within_employment:
        return {
            "denominator": DENOMINATOR_EXCLUDED,
            "credit": CREDIT_REVIEW,
            "basis_type": BASIS_REVIEW,
            "reason": "OUTSIDE_EMPLOYMENT",
            "requires_review": False,
        }

    if not scheduled_work_day:
        return {
            "denominator": DENOMINATOR_EXCLUDED,
            "credit": CREDIT_REVIEW,
            "basis_type": BASIS_REVIEW,
            "reason": "NON_WORKDAY",
            "requires_review": False,
        }

    if event is not None:
        event_policy = resolve_event_attendance_policy(event)
        if not event_policy["requires_review"]:
            return event_policy

    if attendance_status == "PRESENT":
        return {
            "denominator": DENOMINATOR_INCLUDED,
            "credit": CREDIT_PRESENT,
            "basis_type": BASIS_OBSERVED_ATTENDANCE,
            "reason": "PRESENT",
            "requires_review": False,
        }

    return {
        "denominator": DENOMINATOR_INCLUDED,
        "credit": CREDIT_REVIEW,
        "basis_type": BASIS_REVIEW,
        "reason": "UNRESOLVED_SCHEDULED_WORKDAY",
        "requires_review": True,
    }
