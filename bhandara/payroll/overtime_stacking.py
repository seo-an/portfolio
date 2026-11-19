"""Explicit, review-only stacking of concurrent approved work categories.

The same minute may carry more than one *additional component* only when
a caller supplies an explicit documented category combination. This is an
arithmetic safeguard, NOT legal eligibility or authentic policy verification.

Use a minute-boundary sweep. Adjacent non-overlapping shifts share a
boundary and are NOT concurrent. Triple stacks need their own exact set.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable, Mapping


class OvertimeStackingError(ValueError):
    """Unknown concurrent-pay policy or duplicate component: fail closed."""


_STACKABLE = frozenset({"OVERTIME", "NIGHT", "HOLIDAY"})
_POLICY_FIELDS = frozenset({
    "mode", "policy_ref", "same_category", "base_component_policy",
    "allowed_category_sets",
})
_SEGMENT_FIELDS = frozenset({
    "employee_id", "segment_id", "start_at", "end_at",
    "category", "base_pay_includes_time",
})


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OvertimeStackingError(f"{name}: explicit nonempty text required")
    value = value.strip()
    if value[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        raise OvertimeStackingError(f"{name}: unsafe text")
    return value


def _policy(raw: Any) -> tuple[str | None, dict[frozenset[str], str]]:
    """No configuration = no overlapping approvals accepted, as in P1-2."""
    if raw is None:
        return None, {}
    if not isinstance(raw, Mapping) or set(raw) != _POLICY_FIELDS:
        raise OvertimeStackingError("overlap_policy: exact documented fields required")
    if raw["mode"] != "EXPLICIT_CATEGORY_SETS":
        raise OvertimeStackingError("overlap_policy: unsupported mode")
    if raw["same_category"] != "BLOCK":
        raise OvertimeStackingError("overlap_policy: same-category overlaps must be blocked")
    if raw["base_component_policy"] != "CONSISTENT_INCLUSION_SINGLE_OWNER":
        raise OvertimeStackingError("overlap_policy: consistent base inclusion and single owner required")
    ref = _text(raw["policy_ref"], "overlap_policy.policy_ref")
    values = raw["allowed_category_sets"]
    if not isinstance(values, (list, tuple)):
        raise OvertimeStackingError("overlap_policy: allowed_category_sets list required")
    permitted: dict[frozenset[str], str] = {}
    for entry in values:
        if not isinstance(entry, Mapping) or set(entry) != {"categories", "unpaid_base_owner"}:
            raise OvertimeStackingError("overlap_policy: categories and unpaid_base_owner required")
        group = entry["categories"]
        if not isinstance(group, (list, tuple)) or len(group) not in (2, 3):
            raise OvertimeStackingError("overlap_policy: each category set needs 2 or 3 items")
        if any(not isinstance(item, str) or item not in _STACKABLE for item in group):
            raise OvertimeStackingError("overlap_policy: unknown stacking category")
        key = frozenset(group)
        if len(key) != len(group):
            raise OvertimeStackingError("overlap_policy: repeated category in a set")
        if key in permitted:
            raise OvertimeStackingError("overlap_policy: duplicated category set")
        owner = _text(entry["unpaid_base_owner"], "overlap_policy.unpaid_base_owner")
        if owner not in key:
            raise OvertimeStackingError("overlap_policy: base owner outside category set")
        permitted[key] = owner
    return ref, permitted


def _segment(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping) or set(row) != _SEGMENT_FIELDS:
        raise OvertimeStackingError("approved stacking segment: exact fields required")
    employee = _text(row["employee_id"], "employee_id")
    segment_id = _text(row["segment_id"], "segment_id")
    category = _text(row["category"], "category")
    if category not in {"OVERTIME", "NIGHT", "HOLIDAY", "EARLY", "LATE"}:
        raise OvertimeStackingError("approved stacking segment: unknown category")
    included = row["base_pay_includes_time"]
    if type(included) is not bool:
        raise OvertimeStackingError("approved stacking segment: boolean inclusion required")
    begin, end = row["start_at"], row["end_at"]
    if (not isinstance(begin, datetime) or not isinstance(end, datetime)
            or begin.tzinfo is not None or end.tzinfo is not None or begin >= end):
        raise OvertimeStackingError("approved stacking segment: valid naive interval required")
    return {
        "employee_id": employee, "segment_id": segment_id,
        "category": category, "base_pay_includes_time": included,
        "start_at": begin, "end_at": end,
    }


def review_approved_stacking(
    segments: Iterable[Mapping[str, Any]],
    *,
    overlap_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Review exact active category sets for every concurrent time slice.

    This never changes the approved segment minutes or silently resolves
    legal category conflicts. Each employee's half-open time intervals are
    swept using END-before-START at equal timestamps.
    """
    policy_ref, allowed = _policy(overlap_policy)
    by_employee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for raw in segments:
        row = _segment(raw)
        if row["segment_id"] in seen_ids:
            raise OvertimeStackingError("approved stacking segment: duplicate segment_id")
        seen_ids.add(row["segment_id"])
        by_employee[row["employee_id"]].append(row)

    slices: list[dict[str, Any]] = []
    for employee, rows in sorted(by_employee.items()):
        starts: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        ends: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            starts[row["start_at"]].append(row)
            ends[row["end_at"]].append(row)
        timeline = sorted(set(starts) | set(ends))
        active: dict[str, dict[str, Any]] = {}
        for index, current in enumerate(timeline[:-1]):
            # Half-open intervals: end timestamp is not inside next slice.
            for row in ends[current]:
                active.pop(row["segment_id"], None)
            for row in starts[current]:
                active[row["segment_id"]] = row
            next_time = timeline[index + 1]
            if len(active) < 2:
                continue
            categories = [item["category"] for item in active.values()]
            if len(set(categories)) != len(categories):
                raise OvertimeStackingError("approved stacking: overlapping same-category components")
            if policy_ref is None:
                raise OvertimeStackingError("approved_segment: overlapping intervals require a stacking policy")
            category_set = frozenset(categories)
            if category_set not in allowed:
                raise OvertimeStackingError(
                    "approved stacking: active category set not explicitly permitted"
                )
            inclusion = {item["base_pay_includes_time"] for item in active.values()}
            if len(inclusion) != 1:
                raise OvertimeStackingError("approved stacking: inconsistent base-pay inclusion for same minutes")
            base_prepaid = True in inclusion
            owner = None
            if not base_prepaid:
                owner_category = allowed[category_set]
                owner = next(
                    item["segment_id"] for item in active.values()
                    if item["category"] == owner_category
                )
            minutes = int((next_time - current).total_seconds() / 60)
            slices.append({
                "employee_id": employee,
                "start_at": current.isoformat(timespec="minutes"),
                "end_at": next_time.isoformat(timespec="minutes"),
                "categories": sorted(category_set),
                "segment_ids": sorted(active),
                "overlap_minutes": minutes,
                "base_prepaid": base_prepaid,
                "ordinary_base_owner_segment_id": owner,
            })
    return {
        "schema_version": "0.1",
        "status": "EXPLICIT_POLICY_MATCHED" if slices else "NO_OVERLAP",
        "policy_ref": policy_ref,
        "overlap_slices": slices,
        "legal_compliance": "NOT_ASSESSED",
        "approval_state": "NOT_APPROVED",
    }
