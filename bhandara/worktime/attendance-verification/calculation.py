"""Independent normalized device-evidence to reported-attendance reconciliation.

Vendor parsing and identity mapping happen before this module. A successful
biometric CLOCK_IN/CLOCK_OUT is evidence of a punch, never a final HR decision
about actual paid work, lateness, rest, overtime or attendance approval.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping

from .deviations import compare_time_deviations

MODES = frozenset({"CLOCK_IN", "CLOCK_OUT", "ACCESS", "OUTING", "RETURN", "DISARM", "UNKNOWN"})
DIRECTIONS = frozenset({"IN", "OUT", "UNKNOWN"})
AUTH_STATUSES = frozenset({"SUCCESS", "FAILED", "UNKNOWN"})
AUTH_METHODS = frozenset({"FINGERPRINT", "FACE", "CARD", "PIN", "UNKNOWN"})
DEFAULT_ACCEPTED_METHODS = ("FINGERPRINT",)


class AttendanceVerificationInputError(ValueError):
    """Invalid batch-level contract; not merely a suspect source row."""


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


def _timestamp(value: Any, work_date: str) -> tuple[str | None, bool, bool]:
    """Return (local minute ISO time, valid, explicit calendar date)."""
    if value in (None, ""):
        return None, True, False
    explicit = False
    if isinstance(value, datetime):
        stamp, explicit = value, True
    elif isinstance(value, time):
        stamp = datetime.combine(date.fromisoformat(work_date), value)
    elif isinstance(value, str):
        if len(value) == 5 and value[2] == ":":
            try:
                stamp = datetime.combine(date.fromisoformat(work_date), time.fromisoformat(value))
            except ValueError:
                return None, False, False
        elif len(value) == 16 and value[10] == "T":
            try:
                stamp = datetime.fromisoformat(value)
            except ValueError:
                return None, False, False
            explicit = True
        else:
            return None, False, False
    else:
        return None, False, False
    if stamp.tzinfo is not None or stamp.second or stamp.microsecond:
        return None, False, explicit
    day = date.fromisoformat(work_date)
    if not day <= stamp.date() <= day + timedelta(days=1):
        return None, False, explicit
    return stamp.isoformat(timespec="minutes"), True, explicit


def _reference(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_ref": str(row.get("source_ref") or ""),
        "row_number": row.get("_row_number"),
    }


def _issue(source: str, row: Mapping[str, Any], code: str) -> dict[str, Any]:
    return {
        "source": source,
        "code": code,
        "employee_id": str(row.get("employee_id") or "").strip(),
        "work_date": str(row.get("work_date") or ""),
        **_reference(row),
    }


def _index(rows: Iterable[Mapping[str, Any]], source: str, begin: str, end: str
           ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    if isinstance(rows, (Mapping, str, bytes)):
        raise AttendanceVerificationInputError(f"{source} must be an iterable of objects")
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    issues: list[dict[str, Any]] = []
    try:
        iterator = iter(rows)
    except TypeError as exc:
        raise AttendanceVerificationInputError(f"{source} must be iterable") from exc
    for row in iterator:
        if not isinstance(row, Mapping):
            raise AttendanceVerificationInputError(f"{source}: every row must be an object")
        employee = str(row.get("employee_id") or "").strip()
        day = _day(row.get("work_date"))
        if not employee or day is None:
            issues.append(_issue(source, row, "ROW_KEY_INVALID"))
        elif not begin <= day <= end:
            issues.append(_issue(source, row, "OUTSIDE_PERIOD"))
        else:
            by_key.setdefault((employee, day), []).append(dict(row))
    return by_key, issues


def _ledger(row: Mapping[str, Any], day: str) -> tuple[dict[str, Any], list[str]]:
    entry, valid_in, explicit_in = _timestamp(row.get("clock_in"), day)
    exit_, valid_out, explicit_out = _timestamp(row.get("clock_out"), day)
    problems: list[str] = []
    if not valid_in:
        problems.append("LEDGER_CLOCK_IN_INVALID")
    if not valid_out:
        problems.append("LEDGER_CLOCK_OUT_INVALID")
    if not entry or not exit_:
        problems.append("LEDGER_CLOCK_INCOMPLETE")
    elif exit_ <= entry:
        problems.append("OVERNIGHT_DATE_REQUIRED" if not explicit_out else "LEDGER_CLOCK_SEQUENCE_INVALID")
    elif (datetime.fromisoformat(exit_) - datetime.fromisoformat(entry)).total_seconds() > 86400:
        problems.append("LEDGER_SPAN_EXCEEDS_24H")
    return {"clock_in": entry, "clock_out": exit_,
            "worker_id": str(row.get("worker_id") or "")}, sorted(set(problems))


def _event(row: Mapping[str, Any], day: str, accepted: frozenset[str],
           duplicated_ids: set[str]) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        problems.append("EVENT_ID_MISSING")
    elif event_id in duplicated_ids:
        problems.append("EVENT_ID_DUPLICATED")
    stamped, valid, _ = _timestamp(row.get("event_time"), day)
    if not stamped or not valid:
        problems.append("EVENT_TIME_INVALID")
    mode = str(row.get("mode") or "UNKNOWN").strip().upper()
    direction = str(row.get("direction") or "UNKNOWN").strip().upper()
    auth = str(row.get("auth_status") or "UNKNOWN").strip().upper()
    method = str(row.get("auth_method") or "UNKNOWN").strip().upper()
    if mode not in MODES:
        problems.append("EVENT_MODE_INVALID")
    elif mode == "UNKNOWN":
        problems.append("EVENT_MODE_UNKNOWN")
    if direction not in DIRECTIONS:
        problems.append("EVENT_DIRECTION_INVALID")
    if auth not in AUTH_STATUSES:
        problems.append("EVENT_AUTH_STATUS_INVALID")
    elif auth != "SUCCESS":
        problems.append("EVENT_AUTH_NOT_VERIFIED")
    if method not in AUTH_METHODS:
        problems.append("EVENT_AUTH_METHOD_INVALID")
    elif method == "UNKNOWN":
        problems.append("EVENT_AUTH_METHOD_UNKNOWN")
    elif method not in accepted:
        problems.append("EVENT_AUTH_METHOD_NOT_ACCEPTED")
    evidence = {
        "event_id": event_id, "event_time": stamped,
        "mode": mode, "direction": direction,
        "auth_status": auth, "auth_method": method,
        "worker_id": str(row.get("worker_id") or ""),
        "device_id": str(row.get("device_id") or ""),
        **_reference(row),
    }
    return evidence, sorted(set(problems))


def _compare(key: tuple[str, str], ledger_rows: list[dict[str, Any]],
             event_rows: list[dict[str, Any]], accepted: frozenset[str],
             duplicated_ids: set[str],
             schedule_rows: list[dict[str, Any]],
             candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    problems: list[str] = []
    recorded = None
    if len(ledger_rows) > 1:
        problems.append("DUPLICATE_LEDGER")
    if len(schedule_rows) > 1:
        problems.append("DUPLICATE_SCHEDULE")
    if len(candidate_rows) > 1:
        problems.append("DUPLICATE_DEVICE_CANDIDATE")
    if len(ledger_rows) == 1:
        recorded, errors = _ledger(ledger_rows[0], key[1])
        problems.extend(errors)

    events = []
    punches: dict[str, list[str]] = {"CLOCK_IN": [], "CLOCK_OUT": []}
    access_candidates: list[str] = []
    for row in event_rows:
        evidence, errors = _event(row, key[1], accepted, duplicated_ids)
        events.append(evidence)
        if recorded and recorded["worker_id"] and evidence["worker_id"] and (
                recorded["worker_id"] != evidence["worker_id"]):
            errors.append("WORKER_ID_CONFLICT")
        problems.extend(errors)
        if not errors:
            if evidence["mode"] in punches:
                punches[evidence["mode"]].append(evidence["event_time"])
            elif evidence["mode"] == "ACCESS":
                access_candidates.append(evidence["event_time"])
        # Successful general access can be a review-only arrival candidate,
        # never a synthesized CLOCK_IN. Do not infer direction from mode.
    if len(punches["CLOCK_IN"]) > 1:
        problems.append("MULTIPLE_CLOCK_IN")
    if len(punches["CLOCK_OUT"]) > 1:
        problems.append("MULTIPLE_CLOCK_OUT")
    in_punch = punches["CLOCK_IN"][0] if len(punches["CLOCK_IN"]) == 1 else None
    out_punch = punches["CLOCK_OUT"][0] if len(punches["CLOCK_OUT"]) == 1 else None
    if in_punch and out_punch and out_punch <= in_punch:
        problems.append("DEVICE_CLOCK_SEQUENCE_INVALID")
    time_deviations, deviation_issues = compare_time_deviations(
        work_date=key[1],
        schedule=schedule_rows[0] if len(schedule_rows) == 1 else None,
        attendance=ledger_rows[0] if len(ledger_rows) == 1 else None,
        device_punches={"clock_in": in_punch, "clock_out": out_punch},
        device_candidate=candidate_rows[0] if len(candidate_rows) == 1 else None,
    )
    problems.extend(deviation_issues)
    different: list[str] = []
    if recorded and in_punch and recorded["clock_in"] != in_punch:
        different.append("clock_in")
    if recorded and out_punch and recorded["clock_out"] != out_punch:
        different.append("clock_out")

    if problems:
        state = "REVIEW_REQUIRED"
    elif not ledger_rows and not event_rows:
        state = "MISSING_EVIDENCE"
    elif not ledger_rows:
        state = "DEVICE_ONLY"
    elif not event_rows:
        state = "MISSING_EVIDENCE"
    elif not in_punch or not out_punch:
        state = "ACCESS_ONLY" if not in_punch and not out_punch and access_candidates else "MISSING_EVIDENCE"
    else:
        state = "RECORD_DIFFERENT" if different else "RECORD_MATCH"
    if state in {"MISSING_EVIDENCE", "ACCESS_ONLY"}:
        if not in_punch:
            problems.append("CLOCK_IN_EVIDENCE_MISSING")
        if not out_punch:
            problems.append("CLOCK_OUT_EVIDENCE_MISSING")
    return {
        "employee_id": key[0], "work_date": key[1], "status": state,
        "reported": recorded,
        "device_punches": {"clock_in": in_punch, "clock_out": out_punch},
        "different_fields": different,
        "time_deviations": time_deviations,
        "review_codes": sorted(set(problems)),
        "first_access_candidate": (
            {"event_time": min(access_candidates),
             "basis": "FIRST_GENERIC_ACCESS", "confirmed": False}
            if access_candidates else None),
        "ledger_sources": [_reference(row) for row in ledger_rows],
        "schedule_sources": [_reference(row) for row in schedule_rows],
        "candidate_sources": [_reference(row) for row in candidate_rows],
        "access_evidence": events,
    }


def verify_attendance(
    attendance_rows: Iterable[Mapping[str, Any]],
    access_events: Iterable[Mapping[str, Any]],
    *,
    period_from: str,
    period_to: str,
    accepted_auth_methods: Iterable[str] = DEFAULT_ACCEPTED_METHODS,
    schedule_rows: Iterable[Mapping[str, Any]] = (),
    candidate_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Reconcile trustworthy *punch evidence* with reported ledger data.

    Authenticated device punches are not employer approval or worked hours.
    Optional schedule and *unconfirmed* vendor candidate rows supply signed
    time deviations without changing the accepted authentication policy.
    """
    begin, end = _day(period_from), _day(period_to)
    if begin is None or end is None or end < begin:
        raise AttendanceVerificationInputError("period must be ordered YYYY-MM-DD")
    if isinstance(accepted_auth_methods, (str, bytes, Mapping)):
        raise AttendanceVerificationInputError("accepted_auth_methods must be an iterable of method names")
    try:
        values = list(accepted_auth_methods)
    except TypeError as exc:
        raise AttendanceVerificationInputError("invalid accepted_auth_methods") from exc
    if not values or any(type(value) is not str or value not in AUTH_METHODS - {"UNKNOWN"} for value in values):
        raise AttendanceVerificationInputError("accepted_auth_methods must contain known explicit methods")
    accepted = frozenset(values)
    ledger, ledger_issues = _index(attendance_rows, "attendance", begin, end)
    access, access_issues = _index(access_events, "access_events", begin, end)
    schedule, schedule_issues = _index(schedule_rows, "schedule", begin, end)
    candidates, candidate_issues = _index(candidate_rows, "device_candidates", begin, end)
    ids = Counter(str(row.get("event_id") or "").strip()
                  for items in access.values() for row in items
                  if str(row.get("event_id") or "").strip())
    duplicated_ids = {identifier for identifier, count in ids.items() if count > 1}
    keys = sorted(set(ledger) | set(access) | set(schedule) | set(candidates))
    rows = [_compare(key, ledger.get(key, []), access.get(key, []),
                     accepted, duplicated_ids,
                     schedule.get(key, []), candidates.get(key, []))
            for key in keys]
    source_issues = ledger_issues + access_issues + schedule_issues + candidate_issues
    if not rows:
        source_issues.append({
            "source": "attendance", "code": "NO_COMPARABLE_ROWS",
            "employee_id": "", "work_date": "",
            "source_ref": "", "row_number": None,
        })
    return {
        "schema_version": "0.2", "module": "attendance-verification",
        "status": ("PASS" if not source_issues and
                   all(row["status"] == "RECORD_MATCH" and
                       row["time_deviations"]["status"] != "DIFFERENT"
                       for row in rows)
                   else "REVIEW_REQUIRED"),
        "period_from": begin, "period_to": end,
        "accepted_auth_methods": sorted(accepted),
        "rows": rows, "source_issues": source_issues,
        "approved": False, "verified_work_hours": False,
        "notice": "출입기 인증과 장부의 대조 결과이며 근로시간·지각·연장·근태 승인 판단이 아닙니다.",
    }
