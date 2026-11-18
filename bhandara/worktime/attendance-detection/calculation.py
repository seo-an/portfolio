"""Independent candidate detection from schedules, ledgers and verified work spans.

Device-only first/last access NEVER becomes a worked interval or an approved
clock-in. Reported presence and independently verified work remain separate.
All findings require HR review; this module never finalizes pay or legal status.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping

from bhandara.worktime.user_settings import ATTENDANCE_DETECTION_DEFAULTS


class DetectionInputError(ValueError):
    """Invalid request-level contract, not a single employee/day source issue."""


DAY_TYPES = frozenset({"WORK", "OFF", "HOLIDAY"})
CANDIDATE_STATUSES = frozenset({
    "EXPLICIT_PAIR", "INFERRED_PAIR", "PARTIAL_EXPLICIT",
    "MULTIPLE_EXPLICIT_REVIEW", "SINGLE_ACCESS",
    "NO_ATTENDANCE_CANDIDATE", "TIME_SEQUENCE_REVIEW",
})
MAX_SPAN = timedelta(days=1)


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    if type(value) is not str or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _wall(value: Any, field: str) -> time:
    if type(value) is not str or len(value) != 5 or value[2] != ":":
        raise DetectionInputError(f"{field} must be HH:MM")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise DetectionInputError(f"{field} must be HH:MM") from exc
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise DetectionInputError(f"{field} must be local minute precision")
    return parsed


def _settings(policy: Mapping[str, Any] | None) -> dict[str, Any]:
    if policy is not None and not isinstance(policy, Mapping):
        raise DetectionInputError("policy must be a mapping")
    values = dict(ATTENDANCE_DETECTION_DEFAULTS)
    if policy is not None:
        unknown = set(policy) - set(values)
        if unknown:
            raise DetectionInputError("unsupported detection settings: " +
                                      ", ".join(sorted(map(str, unknown))))
        values.update(policy)
    for key in ("late_grace_min", "early_leave_grace_min", "outside_schedule_grace_min"):
        amount = values.get(key)
        if type(amount) is not int or amount < 0 or amount > 1440:
            raise DetectionInputError(f"{key} must be nonnegative integer minutes <= 1440")
    start = _wall(values.get("night_start"), "night_start")
    end = _wall(values.get("night_end"), "night_end")
    if start == end:
        raise DetectionInputError("night window cannot have zero or ambiguous length")
    values["night_start"] = start
    values["night_end"] = end
    return values


def _instant(value: Any, day: date, field: str, *, allow_next_day: bool
             ) -> tuple[datetime | None, str | None, bool]:
    """Parse strict wall times or local ISO datetimes; never infer an overnight day."""
    if value is None or value == "":
        return None, None, False
    explicit = isinstance(value, datetime)
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, time):
        result = datetime.combine(day, value)
    elif type(value) is str:
        if len(value) in (5, 8) and value[2] == ":":
            try:
                result = datetime.combine(day, time.fromisoformat(value))
            except ValueError:
                return None, f"{field.upper()}_INVALID", False
        elif len(value) in (16, 19) and value[10] == "T":
            try:
                result = datetime.fromisoformat(value)
            except ValueError:
                return None, f"{field.upper()}_INVALID", False
            explicit = True
        else:
            return None, f"{field.upper()}_INVALID", False
    else:
        return None, f"{field.upper()}_INVALID", False
    if result.tzinfo is not None or result.microsecond:
        return None, f"{field.upper()}_INVALID", explicit
    if result.date() != day and not (allow_next_day and result.date() == day + timedelta(days=1)):
        return None, f"{field.upper()}_OUTSIDE_WORKDAY", explicit
    return result, None, explicit


def _interval(row: Mapping[str, Any], day: date, start_field: str, end_field: str,
              prefix: str, *, optional: bool = False
              ) -> tuple[tuple[datetime, datetime] | None, list[str]]:
    first, problem_a, _ = _instant(row.get(start_field), day, prefix + "_start",
                                    allow_next_day=False)
    last, problem_b, explicit_end = _instant(row.get(end_field), day, prefix + "_end",
                                            allow_next_day=True)
    codes = [code for code in (problem_a, problem_b) if code]
    if first is None and last is None and not codes:
        return None, [] if optional else [prefix.upper() + "_INCOMPLETE"]
    if first is None or last is None:
        return None, sorted(set(codes + [prefix.upper() + "_INCOMPLETE"]))
    if last <= first:
        return None, sorted(set(codes + [
            prefix.upper() + ("_OVERNIGHT_DATE_REQUIRED" if not explicit_end
                              else "_INVALID_SEQUENCE"),
        ]))
    if last - first > MAX_SPAN:
        return None, sorted(set(codes + [prefix.upper() + "_EXCEEDS_24H"]))
    return (first, last), codes


def _serialize_interval(interval: tuple[datetime, datetime] | None,
                        start_key: str, end_key: str) -> dict[str, Any] | None:
    if interval is None:
        return None
    return {
        start_key: interval[0].isoformat(timespec="seconds"),
        end_key: interval[1].isoformat(timespec="seconds"),
    }


def _ref(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"source_ref": str(row.get("source_ref") or ""),
            "row_number": row.get("_row_number")}


def _source_issue(code: str, source: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": source, "code": code,
        "employee_id": str(row.get("employee_id") or "").strip(),
        "work_date": str(row.get("work_date") or ""),
        **_ref(row),
    }


def _index(rows: Iterable[Mapping[str, Any]], source: str,
           begin: date, end: date
           ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    if isinstance(rows, (str, bytes, Mapping)):
        raise DetectionInputError(f"{source} must be a row iterable")
    try:
        iterator = iter(rows)
    except TypeError as exc:
        raise DetectionInputError(f"{source} must be a row iterable") from exc
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    source_issues: list[dict[str, Any]] = []
    for row in iterator:
        if not isinstance(row, Mapping):
            raise DetectionInputError(f"{source}: row must be a mapping")
        employee = str(row.get("employee_id") or "").strip()
        day = _day(row.get("work_date"))
        if not employee or day is None:
            source_issues.append(_source_issue("ROW_KEY_INVALID", source, row))
        elif not begin <= day <= end:
            source_issues.append(_source_issue("OUTSIDE_PERIOD", source, row))
        else:
            index[(employee, day.isoformat())].append(dict(row))
    return dict(index), source_issues


def _identity_issues(rows: dict[str, Mapping[str, Any]]) -> list[str]:
    identities = {
        str(item.get("worker_id") or "").strip()
        for item in rows.values() if item is not None
        and str(item.get("worker_id") or "").strip()
    }
    return ["WORKER_ID_CONFLICT"] if len(identities) > 1 else []


def _normalize_plan(row: Mapping[str, Any], day: date
                    ) -> tuple[dict[str, Any], tuple[datetime, datetime] | None, list[str]]:
    kind = str(row.get("day_type") or "").strip().upper()
    errors = [] if kind in DAY_TYPES else ["DAY_TYPE_INVALID"]
    span, issues = _interval(row, day, "scheduled_start", "scheduled_end",
                             "schedule", optional=kind in {"OFF", "HOLIDAY"})
    errors.extend(issues)
    return {
        "day_type": kind,
        "scheduled_start": span[0].isoformat(timespec="seconds") if span else None,
        "scheduled_end": span[1].isoformat(timespec="seconds") if span else None,
        "source": _ref(row),
    }, span, sorted(set(errors))


def _normalize_ledger(row: Mapping[str, Any], day: date
                      ) -> tuple[dict[str, Any], tuple[datetime, datetime] | None, list[str]]:
    span, codes = _interval(row, day, "clock_in", "clock_out", "ledger")
    return {
        "clock_in": span[0].isoformat(timespec="seconds") if span else None,
        "clock_out": span[1].isoformat(timespec="seconds") if span else None,
        "source": _ref(row),
    }, span, codes


def _normalize_device(row: Mapping[str, Any], day: date
                      ) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if row.get("confirmed") is not False:
        errors.append("DEVICE_CANDIDATE_MUST_BE_UNCONFIRMED")
    status = row.get("candidate_status")
    if status not in CANDIDATE_STATUSES:
        errors.append("DEVICE_CANDIDATE_STATUS_INVALID")
    elif status in {"MULTIPLE_EXPLICIT_REVIEW", "TIME_SEQUENCE_REVIEW"}:
        errors.append("DEVICE_CANDIDATE_NEEDS_REVIEW")
    arrival, err_arrival, _ = _instant(row.get("arrival_time"), day,
                                       "device_arrival", allow_next_day=False)
    departure, err_depart, _ = _instant(row.get("departure_time"), day,
                                        "device_departure", allow_next_day=True)
    errors.extend(code for code in (err_arrival, err_depart) if code)
    if arrival and departure and departure <= arrival:
        errors.append("DEVICE_CANDIDATE_SEQUENCE_INVALID")
    if (status in {"INFERRED_PAIR", "EXPLICIT_PAIR"} and not (arrival and departure)):
        errors.append("DEVICE_CANDIDATE_PAIR_INCOMPLETE")
    if errors:
        return None, sorted(set(errors))
    return {
        "arrival_time": arrival.isoformat(timespec="seconds") if arrival else None,
        "departure_time": departure.isoformat(timespec="seconds") if departure else None,
        "arrival_basis": str(row.get("arrival_basis") or ""),
        "departure_basis": str(row.get("departure_basis") or ""),
        "candidate_status": status,
        "confirmed": False,
        "evidence_event_ids": str(row.get("evidence_event_ids") or ""),
        "source_vendor": str(row.get("source_vendor") or ""),
    }, []


def _normalize_work_intervals(
    rows: list[dict[str, Any]], day: date,
) -> tuple[list[dict[str, Any]], list[tuple[datetime, datetime]], list[str]]:
    normalized: list[dict[str, Any]] = []
    spans: list[tuple[datetime, datetime]] = []
    errors: list[str] = []
    for row in rows:
        span, codes = _interval(row, day, "start", "end", "work_interval")
        if row.get("verified") is not True or not str(row.get("evidence_ref") or "").strip():
            codes.append("WORK_INTERVAL_EVIDENCE_UNVERIFIED")
        errors.extend(codes)
        if span and not codes:
            spans.append(span)
            normalized.append({
                "start": span[0].isoformat(timespec="seconds"),
                "end": span[1].isoformat(timespec="seconds"),
                "evidence_ref": str(row["evidence_ref"]).strip(),
                "source": _ref(row),
            })
    sorted_spans = sorted(spans)
    if any(left[1] > right[0] for left, right in zip(sorted_spans, sorted_spans[1:])):
        errors.append("WORK_INTERVAL_OVERLAP_REVIEW")
    return normalized, sorted_spans, sorted(set(errors))


def _overlap_seconds(a: tuple[datetime, datetime],
                     b: tuple[datetime, datetime]) -> int:
    return max(0, int((min(a[1], b[1]) - max(a[0], b[0])).total_seconds()))


def _night_seconds(span: tuple[datetime, datetime], settings: Mapping[str, Any]) -> int:
    start, end = span
    day = start.date() - timedelta(days=1)
    last = end.date()
    total = 0
    while day <= last:
        nstart = datetime.combine(day, settings["night_start"])
        nend = datetime.combine(
            day + timedelta(days=1) if settings["night_end"] <= settings["night_start"]
            else day, settings["night_end"],
        )
        total += _overlap_seconds(span, (nstart, nend))
        day += timedelta(days=1)
    return total


def _signal(code: str, basis: str, seconds: int | None,
            refs: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "code": code,
        "basis": basis,
        "duration_seconds": seconds,
        "evidence_refs": sorted(set(ref for ref in refs if ref)),
    }


def _detect_one(
    key: tuple[str, str],
    schedule_rows: list[dict[str, Any]],
    attendance_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    work_rows: list[dict[str, Any]],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    employee, work_date = key
    day = date.fromisoformat(work_date)
    codes: list[str] = []
    if len(schedule_rows) > 1:
        codes.append("DUPLICATE_SCHEDULE")
    if len(attendance_rows) > 1:
        codes.append("DUPLICATE_ATTENDANCE")
    if len(candidate_rows) > 1:
        codes.append("DUPLICATE_DEVICE_CANDIDATE")
    selected = {
        "schedule": schedule_rows[0] if len(schedule_rows) == 1 else None,
        "attendance": attendance_rows[0] if len(attendance_rows) == 1 else None,
        "device": candidate_rows[0] if len(candidate_rows) == 1 else None,
    }
    codes.extend(_identity_issues(selected))
    for row in work_rows:
        if selected["schedule"] and row.get("worker_id") and (
            str(row["worker_id"]) != str(selected["schedule"].get("worker_id") or "")
            and selected["schedule"].get("worker_id")
        ):
            codes.append("WORKER_ID_CONFLICT")
        if selected["attendance"] and row.get("worker_id") and (
            str(row["worker_id"]) != str(selected["attendance"].get("worker_id") or "")
            and selected["attendance"].get("worker_id")
        ):
            codes.append("WORKER_ID_CONFLICT")
    plan, schedule_span = None, None
    if selected["schedule"]:
        plan, schedule_span, issues = _normalize_plan(selected["schedule"], day)
        codes.extend(issues)
    reported, attendance_span = None, None
    if selected["attendance"]:
        reported, attendance_span, issues = _normalize_ledger(selected["attendance"], day)
        codes.extend(issues)
    candidate = None
    if selected["device"]:
        candidate, issues = _normalize_device(selected["device"], day)
        codes.extend(issues)
    verified_rows, work_spans, work_errors = _normalize_work_intervals(work_rows, day)
    codes.extend(work_errors)
    codes = sorted(set(codes))
    signals: list[dict[str, Any]] = []

    # Never calculate classification from malformed or potentially cross-person
    # source data. Keep review codes and all available lineage for investigation.
    if not codes:
        day_type = plan["day_type"] if plan else None
        if day_type == "WORK" and reported is None:
            signals.append(_signal("MISSING_ATTENDANCE_RECORD", "SCHEDULE", None))
        if plan is None and attendance_span:
            signals.append(_signal("UNSCHEDULED_PRESENCE_CANDIDATE", "LEDGER_REPORTED",
                                   int((attendance_span[1]-attendance_span[0]).total_seconds())))
        if candidate and reported is None:
            code = ("DEVICE_PRESENCE_UNCONFIRMED" if candidate["arrival_time"]
                    else "DEVICE_EVENTS_WITHOUT_ATTENDANCE_CANDIDATE")
            signals.append(_signal(code, "DEVICE_CANDIDATE", None))
        if attendance_span:
            if day_type == "OFF":
                signals.append(_signal("REST_DAY_PRESENCE_CANDIDATE", "LEDGER_REPORTED",
                                       int((attendance_span[1]-attendance_span[0]).total_seconds())))
            elif day_type == "HOLIDAY":
                signals.append(_signal("HOLIDAY_PRESENCE_CANDIDATE", "LEDGER_REPORTED",
                                       int((attendance_span[1]-attendance_span[0]).total_seconds())))
            elif schedule_span and day_type == "WORK":
                late = int((attendance_span[0] - schedule_span[0]).total_seconds())
                early = int((schedule_span[1] - attendance_span[1]).total_seconds())
                pre = int((schedule_span[0] - attendance_span[0]).total_seconds())
                post = int((attendance_span[1] - schedule_span[1]).total_seconds())
                if late > settings["late_grace_min"]*60:
                    signals.append(_signal("LATE_ARRIVAL_REPORTED_CANDIDATE", "LEDGER_REPORTED", late))
                if early > settings["early_leave_grace_min"]*60:
                    signals.append(_signal("EARLY_LEAVE_REPORTED_CANDIDATE", "LEDGER_REPORTED", early))
                if pre > settings["outside_schedule_grace_min"]*60:
                    signals.append(_signal("PRE_SHIFT_PRESENCE_CANDIDATE", "LEDGER_REPORTED", pre))
                if post > settings["outside_schedule_grace_min"]*60:
                    signals.append(_signal("POST_SHIFT_PRESENCE_CANDIDATE", "LEDGER_REPORTED", post))
            night = _night_seconds(attendance_span, settings)
            if night:
                signals.append(_signal("NIGHT_PRESENCE_CANDIDATE", "LEDGER_REPORTED", night))
        if work_spans:
            refs = [row["evidence_ref"] for row in verified_rows]
            total = sum(int((b-a).total_seconds()) for a, b in work_spans)
            if day_type == "HOLIDAY":
                signals.append(_signal("HOLIDAY_WORK_CANDIDATE", "VERIFIED_WORK", total, refs))
            elif day_type == "OFF":
                signals.append(_signal("REST_DAY_WORK_CANDIDATE", "VERIFIED_WORK", total, refs))
            elif plan is None:
                signals.append(_signal("UNSCHEDULED_WORK_CANDIDATE", "VERIFIED_WORK", total, refs))
            elif day_type == "WORK" and schedule_span:
                extra = sum(int((b-a).total_seconds()) -
                            _overlap_seconds((a, b), schedule_span)
                            for a, b in work_spans)
                if extra > settings["outside_schedule_grace_min"]*60:
                    signals.append(_signal("EXTENDED_WORK_CANDIDATE", "VERIFIED_WORK", extra, refs))
            night_work = sum(_night_seconds(span, settings) for span in work_spans)
            if night_work:
                signals.append(_signal("NIGHT_WORK_CANDIDATE", "VERIFIED_WORK", night_work, refs))

    return {
        "employee_id": employee,
        "work_date": work_date,
        "status": ("REVIEW_REQUIRED" if codes else
                   "CANDIDATES_FOUND" if signals else "NO_FINDINGS"),
        "day_type": plan["day_type"] if plan else None,
        "planned": plan,
        "reported": reported,
        "device_candidate": candidate,
        "verified_work_intervals": verified_rows,
        "signals": signals,
        "review_codes": codes,
        "sources": {
            "schedule": [_ref(row) for row in schedule_rows],
            "attendance": [_ref(row) for row in attendance_rows],
            "device": [_ref(row) for row in candidate_rows],
            "work_intervals": [_ref(row) for row in work_rows],
        },
    }


def detect_attendance(
    schedule_rows: Iterable[Mapping[str, Any]],
    attendance_rows: Iterable[Mapping[str, Any]],
    *,
    period_from: str,
    period_to: str,
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    verified_work_intervals: Iterable[Mapping[str, Any]] = (),
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect HR review candidates without auto-approving or paying any hours."""
    begin, end = _day(period_from), _day(period_to)
    if begin is None or end is None or end < begin:
        raise DetectionInputError("period_from/period_to must be ordered YYYY-MM-DD")
    settings = _settings(policy)
    planned, issues = _index(schedule_rows, "schedule", begin, end)
    ledger, more = _index(attendance_rows, "attendance", begin, end)
    issues.extend(more)
    device, more = _index(candidate_rows, "device_candidates", begin, end)
    issues.extend(more)
    worked, more = _index(verified_work_intervals, "verified_work", begin, end)
    issues.extend(more)
    keys = sorted(set(planned) | set(ledger) | set(device) | set(worked))
    rows = [
        _detect_one(key, planned.get(key, []), ledger.get(key, []),
                    device.get(key, []), worked.get(key, []), settings)
        for key in keys
    ]
    if not rows:
        issues.append({
            "source": "schedule", "code": "NO_COMPARABLE_ROWS",
            "employee_id": "", "work_date": "", "source_ref": "", "row_number": None,
        })
    return {
        "schema_version": "0.1",
        "module": "attendance-detection",
        "status": ("PASS" if rows and not issues
                   and all(row["status"] == "NO_FINDINGS" for row in rows)
                   else "REVIEW_REQUIRED"),
        "period_from": begin.isoformat(),
        "period_to": end.isoformat(),
        "settings": {
            **{key: settings[key] for key in (
                "late_grace_min", "early_leave_grace_min",
                "outside_schedule_grace_min",
            )},
            "night_start": settings["night_start"].isoformat(timespec="minutes"),
            "night_end": settings["night_end"].isoformat(timespec="minutes"),
        },
        "rows": rows,
        "source_issues": issues,
        "approved": False,
        "verified_work_hours": False,
        "payroll_finalizable": False,
        "notice": (
            "지각·조퇴·근태누락·연장·야간·휴무·휴일근무 검토 후보이며 "
            "출입 인증을 실근로로 대체하거나 근태·임금을 승인하지 않습니다."
        ),
    }
