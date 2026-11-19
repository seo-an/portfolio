"""Canonical schedule definitions/assignments for the new Worktime tool.

The first (legacy) worksheet of work-schedule.xlsx is not read or changed.
No attendance, approval or payroll inference is made here.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from bhandara.common.io.input_layout import read_sheet, InputLayoutError


class ScheduleMappingError(ValueError):
    """Invalid schedule mapping: do not silently substitute another plan."""


def _day(value: Any, field: str, *, optional: bool = False) -> str | None:
    if optional and value in (None, ""):
        return None
    if isinstance(value, datetime):
        value = value.date()
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
        return parsed.isoformat()
    except (ValueError, TypeError) as exc:
        raise ScheduleMappingError(f"{field}: expected a valid YYYY-MM-DD") from exc


def _clock(value: Any, field: str) -> str:
    if isinstance(value, datetime):
        value = value.time()
    try:
        parsed = value if isinstance(value, time) else time.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise ScheduleMappingError(f"{field}: expected HH:MM") from exc
    if parsed.tzinfo or parsed.second or parsed.microsecond:
        raise ScheduleMappingError(f"{field}: expected minute-precision local time")
    return parsed.isoformat(timespec="minutes")


def _whole(value: Any, field: str, *, maximum: int) -> int:
    if isinstance(value, bool):
        raise ScheduleMappingError(f"{field}: integer required")
    try:
        number = int(value)
        if str(value).strip() not in (str(number), str(float(number))):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise ScheduleMappingError(f"{field}: integer required") from exc
    if not 0 <= number <= maximum:
        raise ScheduleMappingError(f"{field}: outside 0..{maximum}")
    return number


def _rows(path: Path, headers: tuple[str, ...], sheet: str) -> list[dict[str, Any]]:
    try:
        return read_sheet(path, headers, sheet_name=sheet)
    except (InputLayoutError, OSError) as exc:
        raise ScheduleMappingError(f"{sheet}: {exc}") from exc


def read_schedule_mapping(
    path: str | Path,
    *,
    period_from: str,
    period_to: str,
) -> list[dict[str, Any]]:
    """Expand SCHEDULE MAP + ASSIGNMENTS into Schedule-module input rows.

    One schedule ID names one immutable definition. Changed hours require a new
    ID. Optional validity dates bound where an assignment may use the ID.
    Unassigned dates are never fabricated. OFF has scheduled_min=0; an unknown
    or missing assignment is not equivalent to a day off.
    """
    first = _day(period_from, "period_from")
    last = _day(period_to, "period_to")
    if first > last:
        raise ScheduleMappingError("period_from is after period_to")
    target = Path(path)
    defs = _rows(
        target,
        ("schedule_id", "schedule_type", "scheduled_start", "scheduled_end",
         "end_day_offset", "break_min", "scheduled_min", "valid_from", "valid_to"),
        "SCHEDULE MAP",
    )
    assignments = _rows(
        target, ("employee_id", "work_date", "schedule_id", "day_type"), "ASSIGNMENTS",
    )
    catalog: dict[str, dict[str, Any]] = {}
    for row in defs:
        line = row["_row_number"]
        ident = str(row.get("schedule_id") or "").strip()
        kind = str(row.get("schedule_type") or "").strip().upper()
        if not ident or not kind:
            raise ScheduleMappingError(f"SCHEDULE MAP row {line}: ID and type required")
        if ident in catalog:
            raise ScheduleMappingError(f"SCHEDULE MAP row {line}: duplicate schedule_id {ident}")
        start = _clock(row.get("scheduled_start"), f"SCHEDULE MAP row {line} start")
        end = _clock(row.get("scheduled_end"), f"SCHEDULE MAP row {line} end")
        offset = _whole(row.get("end_day_offset"), f"SCHEDULE MAP row {line} offset", maximum=1)
        rest = _whole(row.get("break_min"), f"SCHEDULE MAP row {line} break", maximum=1440)
        minutes = _whole(row.get("scheduled_min"), f"SCHEDULE MAP row {line} scheduled", maximum=1440)
        start_dt = datetime.combine(date(2026, 1, 1), time.fromisoformat(start))
        end_dt = datetime.combine(date(2026, 1, 1) + timedelta(days=offset),
                                  time.fromisoformat(end))
        span = int((end_dt - start_dt).total_seconds() // 60)
        if span <= 0 or span > 1440 or rest > span or minutes > span - rest:
            raise ScheduleMappingError(f"SCHEDULE MAP row {line}: impossible duration")
        valid_from = _day(row.get("valid_from"), "valid_from", optional=True)
        valid_to = _day(row.get("valid_to"), "valid_to", optional=True)
        if valid_from and valid_to and valid_from > valid_to:
            raise ScheduleMappingError(f"SCHEDULE MAP row {line}: invalid validity dates")
        catalog[ident] = dict(
            schedule_id=ident, schedule_type=kind,
            scheduled_start=start, scheduled_end=end, end_day_offset=offset,
            break_min=rest, scheduled_min=minutes,
            valid_from=valid_from, valid_to=valid_to,
        )
    if not catalog:
        raise ScheduleMappingError("SCHEDULE MAP: no definitions")
    result: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()
    for row in assignments:
        line = row["_row_number"]
        employee = str(row.get("employee_id") or "").strip()
        day = _day(row.get("work_date"), f"ASSIGNMENTS row {line} date")
        day_type = str(row.get("day_type") or "").strip().upper()
        ident = str(row.get("schedule_id") or "").strip()
        if not employee or day_type not in {"WORK", "OFF", "HOLIDAY"}:
            raise ScheduleMappingError(f"ASSIGNMENTS row {line}: invalid employee/day_type")
        key = (employee, day)
        if key in used:
            raise ScheduleMappingError(f"ASSIGNMENTS row {line}: duplicate employee/date")
        used.add(key)
        if day_type == "WORK" and not ident:
            raise ScheduleMappingError(f"ASSIGNMENTS row {line}: WORK requires schedule_id")
        if day_type == "OFF" and ident:
            raise ScheduleMappingError(f"ASSIGNMENTS row {line}: OFF cannot have schedule_id")
        definition = catalog.get(ident) if ident else None
        if ident and definition is None:
            raise ScheduleMappingError(f"ASSIGNMENTS row {line}: unknown schedule_id {ident}")
        if definition and ((definition["valid_from"] and day < definition["valid_from"])
                           or (definition["valid_to"] and day > definition["valid_to"])):
            raise ScheduleMappingError(f"ASSIGNMENTS row {line}: schedule outside validity")
        if not first <= day <= last:
            continue
        result.append({
            "employee_id": employee, "work_date": day, "day_type": day_type,
            "schedule_id": ident or None,
            "schedule_type": definition["schedule_type"] if definition else None,
            "scheduled_start": definition["scheduled_start"] if definition else None,
            "scheduled_end": definition["scheduled_end"] if definition else None,
            "end_day_offset": definition["end_day_offset"] if definition else None,
            "break_min": definition["break_min"] if definition else None,
            "scheduled_min": definition["scheduled_min"] if definition else 0,
            "source_ref": f"{target.name}:ASSIGNMENTS",
            "_row_number": line,
        })
    return sorted(result, key=lambda r: (r["employee_id"], r["work_date"]))


def for_attendance_verification(schedule_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Date overnight scheduled ends explicitly for the Verification module.

    Schedule keeps local HH:MM, while Attendance Verification needs a full
    next-day timestamp to compare overnight exits without guessing a date.
    """
    results = []
    for row in schedule_rows:
        copy = dict(row)
        if copy.get("end_day_offset") == 1 and copy.get("scheduled_end"):
            day = date.fromisoformat(copy["work_date"]) + timedelta(days=1)
            copy["scheduled_end"] = f"{day.isoformat()}T{copy['scheduled_end']}"
        results.append(copy)
    return results
