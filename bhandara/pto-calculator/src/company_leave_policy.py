"""Validate company-defined leave policy rules without inventing policy."""

from __future__ import annotations

from typing import Any


COUNT_BASES = {"CALENDAR_DAY", "WORKING_DAY"}
START_ANCHORS = {"EVENT_DATE", "DAY_AFTER_EVENT"}
ACCUMULATION_BASES = {
    "PER_REQUEST",
    "CALENDAR_YEAR",
    "SERVICE_YEAR",
    "CONTINUOUS_CASE",
}
PAY_STATUSES = {"PAID", "UNPAID", "TRANSITION_REQUIRED"}


def validate_duration_rule(rule: dict[str, Any]) -> dict[str, Any]:
    days = int(rule["days"])
    count_basis = str(rule["count_basis"]).upper()
    start_anchor = str(rule["start_anchor"]).upper()

    if days < 1:
        raise ValueError("duration days must be >= 1")
    if count_basis not in COUNT_BASES:
        raise ValueError(f"invalid count_basis: {count_basis}")
    if start_anchor not in START_ANCHORS:
        raise ValueError(f"invalid start_anchor: {start_anchor}")

    return {
        "days": days,
        "count_basis": count_basis,
        "start_anchor": start_anchor,
    }


def validate_pay_tiers(
    tiers: list[dict[str, Any]],
    *,
    accumulation_basis: str,
) -> dict[str, Any]:
    basis = str(accumulation_basis).upper()
    if basis not in ACCUMULATION_BASES:
        raise ValueError(f"invalid accumulation_basis: {basis}")
    if not tiers:
        raise ValueError("at least one pay tier is required")

    normalized = []
    previous_to = 0
    open_ended_seen = False

    for tier in tiers:
        if open_ended_seen:
            raise ValueError("no tier may follow an open-ended tier")

        from_day = int(tier["from_day"])
        to_day = tier.get("to_day")
        to_day = int(to_day) if to_day is not None else None
        pay_status = str(tier["pay_status"]).upper()

        if from_day != previous_to + 1:
            raise ValueError("pay tiers must be contiguous from day 1")
        if to_day is not None and to_day < from_day:
            raise ValueError("to_day must be >= from_day")
        if pay_status not in PAY_STATUSES:
            raise ValueError(f"invalid pay_status: {pay_status}")

        normalized.append({
            "from_day": from_day,
            "to_day": to_day,
            "pay_status": pay_status,
        })

        if to_day is None:
            open_ended_seen = True
        else:
            previous_to = to_day

    return {
        "accumulation_basis": basis,
        "tiers": normalized,
    }


def validate_leave_policy_rule(rule: dict[str, Any]) -> dict[str, Any]:
    event_type = str(rule["event_type"]).strip().upper()
    event_subtype = rule.get("event_subtype")
    event_subtype = (
        str(event_subtype).strip().upper()
        if event_subtype
        else None
    )

    result = {
        "event_type": event_type,
        "event_subtype": event_subtype,
    }

    if rule.get("duration") is not None:
        result["duration"] = validate_duration_rule(rule["duration"])

    if rule.get("pay") is not None:
        pay = rule["pay"]
        result["pay"] = validate_pay_tiers(
            pay["tiers"],
            accumulation_basis=pay["accumulation_basis"],
        )

    if "duration" not in result and "pay" not in result:
        raise ValueError("leave policy rule requires duration or pay")

    return result
