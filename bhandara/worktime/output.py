"""One factual daily Worktime output, independent of payroll valuation.

Inputs are precomputed results of three independent Worktime modules and
optional *external* attendance/leave facts. No status, approval, overtime,
payable time, absence deduction or monetary inference is performed.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping


class WorktimeOutputError(ValueError):
    """A contradictory join cannot become an apparently trustworthy output."""


OUTPUT_FIELDS = (
    "employee_id", "work_date", "schedule_id",
    "scheduled_min", "actual_min", "clock_in_delta_min", "clock_out_delta_min",
    "attendance_type", "leave_type", "leave_request_id",
)


def _key(row: Mapping[str, Any], source: str) -> tuple[str, str]:
    employee = str(row.get("employee_id") or "").strip()
    work_date = str(row.get("work_date") or "").strip()
    try:
        date.fromisoformat(work_date)
    except (ValueError, TypeError) as exc:
        raise WorktimeOutputError(f"{source}: invalid work_date") from exc
    if not employee or len(work_date) != 10:
        raise WorktimeOutputError(f"{source}: missing employee_id or work_date")
    return employee, work_date


def _index(rows: Iterable[Mapping[str, Any]], name: str) -> dict[tuple[str, str], dict[str, Any]]:
    if isinstance(rows, (str, bytes, Mapping)):
        raise WorktimeOutputError(f"{name}: expected iterable rows")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise WorktimeOutputError(f"{name}: expected object row")
        key = _key(row, name)
        if key in result:
            raise WorktimeOutputError(f"{name}: duplicate employee/date {key}")
        result[key] = dict(row)
    return result


def _minutes(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise WorktimeOutputError(f"{field}: expected nonnegative integer minutes")
    return value


def _delta(deviation: Any, direction: int) -> int | float | None:
    if not isinstance(deviation, Mapping):
        return None
    seconds = deviation.get("delta_seconds")
    if seconds is None:
        return None
    if type(seconds) is not int:
        raise WorktimeOutputError("clock deviation seconds must be integer")
    minutes = direction * seconds / 60
    return int(minutes) if minutes.is_integer() else round(minutes, 4)


def _signed_deltas(verification: Mapping[str, Any] | None) -> tuple[int | float | None, int | float | None]:
    if not verification:
        return None, None
    details = verification.get("time_deviations") or {}
    in_delta = (details.get("clock_in") or {}).get("ledger_vs_expected")
    out_delta = (details.get("clock_out") or {}).get("ledger_vs_expected")
    # Existing Verification: ledger - expected (both).
    # FINAL OUTPUT ONLY: entry expected - ledger, exit ledger - expected.
    return _delta(in_delta, -1), _delta(out_delta, 1)


def _actual(compliance: Mapping[str, Any] | None) -> int | None:
    if not compliance:
        return None
    bad = {"WORK_EVIDENCE_UNVERIFIED", "WORK_MINUTES_INVALID",
           "DUPLICATE_DAILY_FACT"}
    if bad.intersection(compliance.get("review_codes") or ()):
        return None
    return _minutes(compliance.get("worked_min"), "actual_min")


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise WorktimeOutputError("attendance and leave references must be strings")
    return value.strip() or None


def build_worktime_result(
    schedule_rows: Iterable[Mapping[str, Any]],
    attendance_verification: Mapping[str, Any],
    worktime_compliance: Mapping[str, Any],
    *,
    period_from: str,
    period_to: str,
    attendance_facts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Join facts by employee/date without approval or payroll calculations.

    External attendance_facts may supply attendance_type, leave_type and
    leave_request_id, exactly as resolved upstream. No category is invented.
    Unverified actual minutes remain None (never 0). Missing assignment
    means unknown schedule, not OFF/0 minutes.
    """
    try:
        start, end = date.fromisoformat(period_from), date.fromisoformat(period_to)
    except (TypeError, ValueError) as exc:
        raise WorktimeOutputError("invalid period") from exc
    if start > end or (start.isoformat(), end.isoformat()) != (period_from, period_to):
        raise WorktimeOutputError("invalid period order/format")
    schedules = _index(schedule_rows, "schedule")
    if not isinstance(attendance_verification, Mapping) or not isinstance(worktime_compliance, Mapping):
        raise WorktimeOutputError("module results must be objects")
    if attendance_verification.get("module") != "attendance-verification":
        raise WorktimeOutputError("wrong attendance module result")
    if worktime_compliance.get("module") != "worktime-compliance":
        raise WorktimeOutputError("wrong compliance module result")
    for result in (attendance_verification, worktime_compliance):
        if (result.get("period_from"), result.get("period_to")) != (period_from, period_to):
            raise WorktimeOutputError("module period mismatch")
    comparisons = _index(attendance_verification.get("rows") or (), "verification")
    actuals = _index(worktime_compliance.get("daily") or (), "compliance")
    external = _index(attendance_facts, "attendance_facts")
    keys = sorted(set(schedules) | set(comparisons) | set(actuals) | set(external))
    result_rows = []
    for key in keys:
        if not period_from <= key[1] <= period_to:
            raise WorktimeOutputError(f"row outside period: {key}")
        plan = schedules.get(key) or {}
        info = external.get(key) or {}
        scheduled = _minutes(plan.get("scheduled_min"), "scheduled_min")
        if plan.get("schedule_id") is None and plan and plan.get("day_type") in {"OFF", "HOLIDAY"}:
            scheduled = 0
        entry, exit_ = _signed_deltas(comparisons.get(key))
        row = {
            "employee_id": key[0],
            "work_date": key[1],
            "schedule_id": _text(plan.get("schedule_id")),
            "scheduled_min": scheduled,
            "actual_min": _actual(actuals.get(key)),
            "clock_in_delta_min": entry,
            "clock_out_delta_min": exit_,
            "attendance_type": _text(info.get("attendance_type")),
            "leave_type": _text(info.get("leave_type")),
            "leave_request_id": _text(info.get("leave_request_id")),
        }
        result_rows.append(row)
    return {
        "schema_version": "0.1",
        "period_from": period_from,
        "period_to": period_to,
        "rows": result_rows,
    }
