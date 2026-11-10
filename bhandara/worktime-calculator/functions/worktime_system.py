"""Validation for worker worktime-system and temporary-exception assignments."""

from __future__ import annotations

from typing import Any


PERIOD_SYSTEMS = {"flexible_2w", "flexible_3m", "flexible_3_to_6m", "selective"}


def validate_system_assignment(row: dict[str, Any], labor_policy: dict[str, Any]) -> dict[str, Any]:
    system = row.get("worktime_system")
    if system not in labor_policy["rules"] or system == "special_extension":
        raise ValueError(f"unsupported base worktime system: {system}")
    if not row.get("effective_from"):
        raise ValueError("worktime system assignment requires effective_from")
    if system in PERIOD_SYSTEMS:
        if not row.get("settlement_period_start") or not row.get("settlement_period_end"):
            raise ValueError(f"{system} requires settlement period")
        if not row.get("agreement_ref"):
            raise ValueError(f"{system} requires agreement_ref")
    return row


def validate_exception_assignment(row: dict[str, Any], labor_policy: dict[str, Any]) -> dict[str, Any]:
    exception_type = row.get("exception_type")
    rule = labor_policy["rules"].get(exception_type)
    if not rule or rule.get("kind") != "한시적예외":
        raise ValueError(f"unsupported worktime exception: {exception_type}")
    if not row.get("effective_from") or not row.get("effective_to"):
        raise ValueError("temporary worktime exception requires an effective period")
    if not row.get("approval_ref"):
        raise ValueError(f"{exception_type} requires approval_ref")
    if not row.get("consent_ref"):
        raise ValueError(f"{exception_type} requires consent_ref")
    if not row.get("reason"):
        raise ValueError(f"{exception_type} requires reason")
    return row


def validate_no_overlapping_assignments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_worker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_worker.setdefault(row["worker_id"], []).append(row)

    for worker_id, worker_rows in by_worker.items():
        ordered = sorted(worker_rows, key=lambda row: row["effective_from"])
        previous_end = None
        for row in ordered:
            start = row["effective_from"]
            if previous_end is not None and start <= previous_end:
                raise ValueError(f"{worker_id}: overlapping worktime system assignments")
            previous_end = row.get("effective_to")
            if previous_end is None and row is not ordered[-1]:
                raise ValueError(f"{worker_id}: open-ended assignment must be last")
    return rows
