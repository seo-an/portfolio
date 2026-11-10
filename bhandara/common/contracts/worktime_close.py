"""Approved, content-addressed Worktime close receipts and payroll handoff.

Closing is a review/approval event. It never guesses missing attendance or
evaluates flexible/selective statutory settlement automatically.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


HOUR_FIELDS = (
    "scheduled_hours", "worked_hours", "ordinary_hours", "overtime_hours",
    "night_hours", "holiday_work_hours_within_8",
    "holiday_work_hours_over_8", "absence_hours",
)
REQUIRED_FIELDS = (
    "worker_id", "work_date", "worktime_system", "rule_ref",
    *HOUR_FIELDS, "late_minutes", "early_leave_minutes",
    "validation_flags", "approval_ref",
)


class WorktimeCloseError(ValueError):
    pass


def _date(value: Any, field: str) -> date:
    try:
        parsed = date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise WorktimeCloseError(f"{field} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != str(value):
        raise WorktimeCloseError(f"{field} must use canonical YYYY-MM-DD")
    return parsed


def _nonempty(value: Any, field: str) -> str:
    result = str(value).strip() if value is not None else ""
    if not result:
        raise WorktimeCloseError(f"{field} is required")
    return result


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _digest(data: Mapping[str, Any]) -> str:
    payload = json.dumps(_canonical(data), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_nonempty(row.get("worker_id"), "worker_id"),
            _date(row.get("work_date"), "work_date").isoformat())


def _validated_row(row: Mapping[str, Any], start: date, end: date) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise WorktimeCloseError("Worktime row must be a mapping")
    missing = [name for name in REQUIRED_FIELDS if name not in row]
    if missing:
        raise WorktimeCloseError("missing Worktime fields: " + ", ".join(missing))
    worker, day = _key(row)
    if not start <= date.fromisoformat(day) <= end:
        raise WorktimeCloseError(f"{worker}/{day}: outside close period")
    for name in ("worktime_system", "rule_ref", "approval_ref"):
        _nonempty(row.get(name), f"{worker}/{day}.{name}")
    normalized = dict(row)
    for name in HOUR_FIELDS:
        try:
            value = Decimal(str(row[name]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise WorktimeCloseError(f"{worker}/{day}.{name}: invalid hours") from exc
        if not value.is_finite() or value < 0:
            raise WorktimeCloseError(f"{worker}/{day}.{name}: invalid hours")
        normalized[name] = _canonical(value)
    for name in ("late_minutes", "early_leave_minutes"):
        value = row[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise WorktimeCloseError(f"{worker}/{day}.{name}: invalid minutes")
    flags = row["validation_flags"]
    if not isinstance(flags, list):
        raise WorktimeCloseError("validation_flags must be a list")
    for flag in flags:
        if not isinstance(flag, Mapping):
            raise WorktimeCloseError("validation flag must be a mapping")
        if str(flag.get("severity", "")).upper() not in ("INFO", "WARNING"):
            raise WorktimeCloseError(f"{worker}/{day}: unresolved Worktime validation")
    return normalized


def close_worktime_period(
    rows: Iterable[Mapping[str, Any]],
    *,
    period_from: str,
    period_to: str,
    expected_keys: Iterable[Mapping[str, str]],
    covered_worker_ids: Iterable[str],
    approved_by: str,
    approval_ref: str,
    approved_at: str,
    weekly_review_ref: str,
    policy_ref: str,
) -> dict[str, Any]:
    """Close exactly the roster's expected worker/date facts, with review evidence."""
    start, end = _date(period_from, "period_from"), _date(period_to, "period_to")
    if end < start:
        raise WorktimeCloseError("period_to precedes period_from")
    identity = {
        "approved_by": _nonempty(approved_by, "approved_by"),
        "approval_ref": _nonempty(approval_ref, "approval_ref"),
        "weekly_review_ref": _nonempty(weekly_review_ref, "weekly_review_ref"),
        "policy_ref": _nonempty(policy_ref, "policy_ref"),
    }
    try:
        approved_time = datetime.fromisoformat(approved_at)
    except (TypeError, ValueError) as exc:
        raise WorktimeCloseError("approved_at must be ISO 8601 datetime") from exc
    if approved_time.tzinfo is None or approved_time.utcoffset() is None:
        raise WorktimeCloseError("approved_at must include timezone offset")
    workers = sorted({_nonempty(worker, "covered_worker_ids") for worker in covered_worker_ids})
    if not workers:
        raise WorktimeCloseError("covered_worker_ids must not be empty")
    expected = sorted([_key(item) for item in expected_keys])
    if len(expected) != len(set(expected)):
        raise WorktimeCloseError("duplicate expected worker/date")
    if {worker for worker, _ in expected} - set(workers):
        raise WorktimeCloseError("expected keys include uncovered workers")

    checked = [_validated_row(row, start, end) for row in rows]
    actual = sorted([_key(row) for row in checked])
    if len(actual) != len(set(actual)):
        raise WorktimeCloseError("duplicate actual worker/date")
    if set(actual) != set(expected):
        raise WorktimeCloseError(
            f"roster mismatch: missing={sorted(set(expected) - set(actual))}; "
            f"unexpected={sorted(set(actual) - set(expected))}")
    if {worker for worker, _ in actual} - set(workers):
        raise WorktimeCloseError("Worktime row includes uncovered worker")

    # Daily-only overtime classification must never close an obvious 40h+
    # ordinary-hour week without corrected/approved weekly allocation.
    weekly_ordinary: dict[tuple[str, int, int], Decimal] = {}
    for row in checked:
        day = date.fromisoformat(str(row["work_date"]))
        year, week, _ = day.isocalendar()
        key = (str(row["worker_id"]), year, week)
        weekly_ordinary[key] = weekly_ordinary.get(key, Decimal(0)) + Decimal(str(row["ordinary_hours"]))
    for key, hours in weekly_ordinary.items():
        if hours > Decimal("40"):
            raise WorktimeCloseError(f"{key}: ordinary weekly hours exceed 40; allocation review required")

    receipt = {
        "schema_version": "0.1",
        "status": "CLOSED",
        "period_from": start.isoformat(),
        "period_to": end.isoformat(),
        "covered_worker_ids": workers,
        "expected_keys": [
            {"worker_id": worker, "work_date": day} for worker, day in expected
        ],
        "rows": sorted(checked, key=_key),
        **identity,
        "approved_at": approved_time.isoformat(),
    }
    return {**receipt, "receipt_hash": _digest(receipt)}


def verify_worktime_close(receipt: Mapping[str, Any]) -> None:
    """Reject mutated or forged/unreviewed close payloads (not a digital signature)."""
    if not isinstance(receipt, Mapping) or receipt.get("status") != "CLOSED":
        raise WorktimeCloseError("CLOSED worktime receipt required")
    expected_hash = _nonempty(receipt.get("receipt_hash"), "receipt_hash")
    recalculated = close_worktime_period(
        receipt["rows"],
        period_from=receipt["period_from"],
        period_to=receipt["period_to"],
        expected_keys=receipt["expected_keys"],
        covered_worker_ids=receipt["covered_worker_ids"],
        approved_by=receipt["approved_by"],
        approval_ref=receipt["approval_ref"],
        approved_at=receipt["approved_at"],
        weekly_review_ref=receipt["weekly_review_ref"],
        policy_ref=receipt["policy_ref"],
    )
    if _digest({k: v for k, v in receipt.items() if k != "receipt_hash"}) != expected_hash:
        raise WorktimeCloseError("worktime receipt checksum mismatch")
    if recalculated["receipt_hash"] != expected_hash:
        raise WorktimeCloseError("worktime receipt changed or invalid")


def select_closed_worktime(
    receipts: Iterable[Mapping[str, Any]],
    *,
    period_from: str,
    period_to: str,
    required_worker_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Require whole-period close coverage, not merely rows that happen to exist."""
    start, end = _date(period_from, "period_from"), _date(period_to, "period_to")
    if end < start:
        raise WorktimeCloseError("period_to precedes period_from")
    seen_dates: set[date] = set()
    covered: set[str] = set()
    rows = []
    count = 0
    for receipt in receipts:
        count += 1
        verify_worktime_close(receipt)
        begin = _date(receipt["period_from"], "period_from")
        finish = _date(receipt["period_to"], "period_to")
        if begin < start or finish > end:
            raise WorktimeCloseError("close receipt exceeds payroll source period")
        current = begin
        while current <= finish:
            if current in seen_dates:
                raise WorktimeCloseError("overlapping close periods")
            seen_dates.add(current)
            current += timedelta(days=1)
        covered.update(receipt["covered_worker_ids"])
        rows.extend(receipt["rows"])
    if not count:
        raise WorktimeCloseError("at least one closed period required")
    expected_dates = {start + timedelta(days=i) for i in range((end - start).days + 1)}
    if seen_dates != expected_dates:
        raise WorktimeCloseError("worktime close coverage has gaps")
    missing = {_nonempty(x, "required_worker_ids") for x in required_worker_ids} - covered
    if missing:
        raise WorktimeCloseError("workers missing from close coverage: " + ", ".join(sorted(missing)))
    keys = [_key(item) for item in rows]
    if len(keys) != len(set(keys)):
        raise WorktimeCloseError("duplicate worktime fact across close receipts")
    return sorted([dict(item) for item in rows], key=_key)
