"""Bridge PTO-compatible monthly schedule/attendance rows to daily Worktime.

The adapter does not infer leave, absence or payroll approval from missing clock
records. Source rows are already decoded from XLSX/Sheets by the caller.
"""
from __future__ import annotations

import importlib.util
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping


def _load_daily():
    path = Path(__file__).with_name("worktime_daily.py")
    spec = importlib.util.spec_from_file_location("worktime_daily_adapter", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_daily = _load_daily()


class WorktimeSourceError(ValueError):
    pass


def _day(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except (ValueError, TypeError) as exc:
        raise WorktimeSourceError(f"invalid work_date: {value!r}") from exc


def _clock(value: Any, name: str) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes")
    if isinstance(value, time):
        return value.isoformat(timespec="minutes")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise WorktimeSourceError(f"{name} missing or unsupported")


def _index(rows: Iterable[Mapping[str, Any]], name: str) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for row in rows:
        worker = str(row.get("employee_id", "")).strip()
        if not worker:
            raise WorktimeSourceError(f"{name}: employee_id required")
        key = (worker, _day(row.get("work_date")))
        if key in result:
            raise WorktimeSourceError(f"{name}: duplicate worker/date {key}")
        result[key] = dict(row)
    return result


def calculate_from_monthly_records(
    schedule_rows: Iterable[Mapping[str, Any]],
    attendance_rows: Iterable[Mapping[str, Any]],
    *,
    worker_ids: Mapping[str, str],
    worktime_assignments: Mapping[str, Mapping[str, str]],
    approvals: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Produce daily facts and the explicit roster of expected recorded days.

    Use employee_id as the source key, resolved to worker_id by explicit mapping.
    Unmatched attendance, scheduled WORK without clocks and OFF work are blocked.
    HOLIDAY work requires an approved holiday ref and a valid planned shift.
    """
    schedule = _index(schedule_rows, "schedule")
    attendance = _index(attendance_rows, "attendance")
    extras = set(attendance) - set(schedule)
    if extras:
        raise WorktimeSourceError(f"attendance without schedule: {sorted(extras)}")
    rows = []
    expected_keys = []
    for (employee_id, day), shift in sorted(schedule.items()):
        kind = str(shift.get("day_type", "")).upper()
        if kind not in {"WORK", "OFF", "HOLIDAY"}:
            raise WorktimeSourceError(f"{employee_id}/{day}: unsupported day_type")
        observed = attendance.get((employee_id, day))
        if observed is None:
            if kind == "WORK":
                raise WorktimeSourceError(
                    f"{employee_id}/{day}: missing clock records require leave/absence adjudication")
            continue
        if kind == "OFF":
            raise WorktimeSourceError(
                f"{employee_id}/{day}: OFF work needs approved rest-day classification")
        worker = str(worker_ids.get(employee_id, "")).strip()
        if not worker:
            raise WorktimeSourceError(f"{employee_id}: worker_id mapping missing")
        assignment = worktime_assignments.get(employee_id, {})
        approval = approvals.get((employee_id, day), {})
        raw = {
            "worker_id": worker,
            "work_date": day,
            "scheduled_start": _clock(shift.get("scheduled_start"), "scheduled_start"),
            "scheduled_end": _clock(shift.get("scheduled_end"), "scheduled_end"),
            "clock_in": _clock(observed.get("clock_in"), "clock_in"),
            "clock_out": _clock(observed.get("clock_out"), "clock_out"),
            "scheduled_break_min": shift.get("break_min", 0),
            "break_min": observed.get("break_min", shift.get("break_min", 0)),
            "holiday_work": kind == "HOLIDAY",
            "worktime_system": assignment.get("worktime_system"),
            "rule_ref": assignment.get("rule_ref"),
            "approval_ref": approval.get("attendance_approval_ref"),
            "overtime_approval_ref": approval.get("overtime_approval_ref"),
            "holiday_approval_ref": approval.get("holiday_approval_ref"),
            "absence_approval_ref": approval.get("absence_approval_ref"),
            "schedule_variance_approval_ref": approval.get("schedule_variance_approval_ref"),
            "approved_absence_hours": approval.get("approved_absence_hours", 0),
            "input_source_ref": observed.get("source", ""),
        }
        result = _daily.calculate_daily_worktime(raw)
        expected_hours = shift.get("scheduled_work_hours")
        if expected_hours not in (None, ""):
            from decimal import Decimal
            if Decimal(str(expected_hours)) != result["scheduled_hours"]:
                result["validation_flags"].append({
                    "code": "SCHEDULE_HOURS_MISMATCH", "severity": "REVIEW",
                    "message": "기존 스케줄의 소정시간과 계산값 불일치",
                })
        rows.append(result)
        expected_keys.append({"worker_id": worker, "work_date": day})
    if len({(row["worker_id"], row["work_date"]) for row in rows}) != len(rows):
        raise WorktimeSourceError("multiple employee IDs mapped to the same worker/date")
    return {
        "rows": sorted(rows, key=lambda row: (row["worker_id"], row["work_date"])),
        "expected_keys": sorted(expected_keys, key=lambda row: (row["worker_id"], row["work_date"])),
    }
