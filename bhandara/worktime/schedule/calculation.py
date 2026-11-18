"""Pure Schedule workday/attendance-record presence matching. No clock deltas or approval.

This module compares an authoritative planned schedule with the *reported*
attendance ledger. Device access events are exclusively owned by Attendance
Verification and are never synthesized here.
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

NON_WORK_TYPES = frozenset({"OFF", "HOLIDAY"})


class ScheduleInputError(ValueError):
    """Fatal request-contract error (not a problem confined to one source row)."""


def _day(value: Any) -> str | None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed.isoformat() if parsed.isoformat() == value else None


def _clock(value: Any) -> tuple[str | None, bool]:
    """Normalize a wall clock only. Never infer overnight duration from HH:MM."""
    if value in (None, ""):
        return None, True
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        if value.tzinfo or value.second or value.microsecond:
            return None, False
        return value.isoformat(timespec="minutes"), True
    if not isinstance(value, str):
        return None, False
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return None, False
    if parsed.tzinfo or parsed.second or parsed.microsecond:
        return None, False
    return parsed.isoformat(timespec="minutes"), True


def _minutes(value: Any) -> tuple[str | None, bool]:
    if value in (None, ""):
        return None, True
    if isinstance(value, bool):
        return None, False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None, False
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        return None, False
    return str(int(number)), True


def _issue(code: str, source: str, row: Mapping[str, Any], *, work_date: str = "") -> dict[str, Any]:
    return {
        "code": code,
        "source": source,
        "employee_id": str(row.get("employee_id") or "").strip(),
        "work_date": work_date or str(row.get("work_date") or ""),
        "source_ref": str(row.get("source_ref") or ""),
        "row_number": row.get("_row_number"),
    }


def _index(rows: Iterable[Mapping[str, Any]], source: str, start: str, end: str
           ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    issues: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ScheduleInputError(f"{source}: each input row must be an object")
        employee = str(row.get("employee_id") or "").strip()
        day = _day(row.get("work_date"))
        if not employee or day is None:
            issues.append(_issue("ROW_KEY_INVALID", source, row))
            continue
        if not start <= day <= end:
            issues.append(_issue("OUTSIDE_PERIOD", source, row, work_date=day))
            continue
        indexed.setdefault((employee, day), []).append(dict(row))
    return indexed, issues


def _normalized(row: Mapping[str, Any], kind: str) -> tuple[dict[str, Any], list[str]]:
    result: dict[str, Any] = {}
    problems: list[str] = []
    names = ("scheduled_start", "scheduled_end") if kind == "schedule" else ("clock_in", "clock_out")
    for field in names:
        result[field], valid = _clock(row.get(field))
        if not valid:
            problems.append(f"INVALID_{field.upper()}")
    result["break_min"], valid = _minutes(row.get("break_min"))
    if not valid:
        problems.append("INVALID_BREAK_MIN")
    if kind == "schedule":
        day_type = str(row.get("day_type") or "").strip().upper()
        if day_type not in {"WORK", "OFF", "HOLIDAY"}:
            problems.append("DAY_TYPE_INVALID")
        result["day_type"] = day_type
        if (result["scheduled_start"] is None) != (result["scheduled_end"] is None):
            problems.append("INCOMPLETE_SCHEDULE")
        if day_type == "WORK" and not result["scheduled_start"]:
            problems.append("INCOMPLETE_SCHEDULE")
    elif (result["clock_in"] is None) != (result["clock_out"] is None):
        problems.append("INCOMPLETE_ATTENDANCE")
    elif not result["clock_in"]:
        problems.append("INCOMPLETE_ATTENDANCE")
    return result, sorted(set(problems))


def _provenance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"source_ref": str(r.get("source_ref") or ""), "row_number": r.get("_row_number")}
        for r in rows
    ]


def _compare(key: tuple[str, str], schedules: list[dict[str, Any]],
             attendances: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    if len(schedules) > 1:
        issues.append("DUPLICATE_SCHEDULE")
    if len(attendances) > 1:
        issues.append("DUPLICATE_ATTENDANCE")
    planned, recorded = None, None
    if len(schedules) == 1:
        planned, check = _normalized(schedules[0], "schedule")
        issues.extend(check)
    if len(attendances) == 1:
        recorded, check = _normalized(attendances[0], "attendance")
        issues.extend(check)
    issues = sorted(set(issues))
    # Schedule decides only whether an attendance record exists for an
    # expected working/non-working day. Clock, break and reason differences
    # belong to Attendance Verification and Worktime Compliance.
    expected_to_work = bool(planned and (
        planned["day_type"] == "WORK" or planned["scheduled_start"] is not None
    ))
    if issues:
        state = "REVIEW_REQUIRED"
    elif planned is None:
        state = "UNSCHEDULED"
    elif recorded is None:
        state = "MISSING" if expected_to_work else "NON_WORK_MATCH"
    else:
        state = "WORK_MATCH" if expected_to_work else "UNSCHEDULED"
    return {
        "employee_id": key[0], "work_date": key[1], "status": state,
        "planned": planned, "recorded": recorded,
        "different_fields": [], "review_codes": issues,
        "schedule_sources": _provenance(schedules),
        "attendance_sources": _provenance(attendances),
    }


def reconcile_schedule(
    schedule_rows: Iterable[Mapping[str, Any]],
    attendance_rows: Iterable[Mapping[str, Any]],
    *,
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Compare source facts per employee/day. Safe for independent execution.

    Only workday/attendance-record presence is determined. No time deltas,
    leave/absence approval, rest compliance, lateness, overtime, holiday pay,
    or device-authentication claims.
    """
    start, end = _day(period_from), _day(period_to)
    if start is None or end is None or end < start:
        raise ScheduleInputError("period_from/period_to must be ordered YYYY-MM-DD")
    if isinstance(schedule_rows, (str, bytes, Mapping)) or isinstance(attendance_rows, (str, bytes, Mapping)):
        raise ScheduleInputError("schedule_rows and attendance_rows must be row iterables")
    try:
        planned, schedule_issues = _index(schedule_rows, "schedule", start, end)
        recorded, attendance_issues = _index(attendance_rows, "attendance", start, end)
    except TypeError as exc:
        raise ScheduleInputError("schedule_rows and attendance_rows must be row iterables") from exc
    rows = [_compare(key, planned.get(key, []), recorded.get(key, []))
            for key in sorted(set(planned) | set(recorded))]
    source_issues = schedule_issues + attendance_issues
    if not rows:
        source_issues.append({"code": "NO_COMPARABLE_ROWS", "source": "schedule",
                              "employee_id": "", "work_date": "",
                              "source_ref": "", "row_number": None})
    state = ("PASS" if not source_issues and all(row["status"] in {"WORK_MATCH", "NON_WORK_MATCH"} for row in rows)
             else "REVIEW_REQUIRED")
    return {
        "schema_version": "0.1", "module": "schedule", "status": state,
        "period_from": start, "period_to": end, "rows": rows,
        "source_issues": source_issues, "approved": False,
        "notice": "근무 예정일과 근태장부 기록의 존재 여부만 대조합니다. 시각 차이·휴게·지각·연장근무·휴가 승인 여부는 계산하지 않습니다.",
    }
