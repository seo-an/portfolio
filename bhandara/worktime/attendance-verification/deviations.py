"""Signed clock-time comparisons kept separate from attendance verification status.

Three baselines are distinct:
- ledger vs expected work schedule,
- device evidence vs expected work schedule,
- device evidence vs the reported attendance ledger.

A generic first/last access candidate is always UNCONFIRMED. Neither a
deviation nor its reason proves authorized overtime, flex time or paid work.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Mapping

FIELDS = (("clock_in", "scheduled_start", "arrival_time", "clock_in_reason"),
          ("clock_out", "scheduled_end", "departure_time", "clock_out_reason"))
CANDIDATE_STATUSES = frozenset({
    "EXPLICIT_PAIR", "INFERRED_PAIR", "PARTIAL_EXPLICIT",
    "MULTIPLE_EXPLICIT_REVIEW", "SINGLE_ACCESS",
    "NO_ATTENDANCE_CANDIDATE", "TIME_SEQUENCE_REVIEW",
})
BAD_CANDIDATE_STATUSES = frozenset({
    "MULTIPLE_EXPLICIT_REVIEW", "TIME_SEQUENCE_REVIEW",
})


def _stamp(value: Any, work_date: str, *, end: bool
           ) -> tuple[datetime | None, bool, bool]:
    """(timestamp, valid, explicit date); null is unknown, not invalid."""
    if value is None or value == "":
        return None, True, False
    explicit = isinstance(value, datetime)
    day = date.fromisoformat(work_date)
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, time):
        stamp = datetime.combine(day, value)
    elif isinstance(value, str):
        try:
            if len(value) in (5, 8) and value[2] == ":":
                stamp = datetime.combine(day, time.fromisoformat(value))
            elif len(value) in (16, 19) and value[10] == "T":
                stamp = datetime.fromisoformat(value)
                explicit = True
            else:
                return None, False, explicit
        except ValueError:
            return None, False, explicit
    else:
        return None, False, explicit
    if stamp.tzinfo is not None or stamp.microsecond:
        return None, False, explicit
    if stamp.date() != day and not (end and stamp.date() == day + timedelta(days=1)):
        return None, False, explicit
    return stamp, True, explicit


def _delta(
    later: datetime | None, later_dated: bool,
    baseline: datetime | None, baseline_dated: bool,
) -> tuple[dict[str, int | float | None], str | None]:
    if later is None or baseline is None:
        return {"delta_minutes": None, "delta_seconds": None}, None
    seconds = int((later - baseline).total_seconds())
    if abs(seconds) >= 12 * 3600 and not (later_dated and baseline_dated):
        return {"delta_minutes": None, "delta_seconds": None}, "CLOCK_DATE_AMBIGUOUS"
    minutes = seconds // 60 if seconds % 60 == 0 else round(seconds / 60, 4)
    return {"delta_minutes": minutes, "delta_seconds": seconds}, None


def _text_reason(row: Mapping[str, Any] | None, field: str
                 ) -> tuple[str | None, str | None]:
    if row is None:
        return None, None
    raw = row.get(field)
    if raw is None or raw == "":
        return None, None
    if not isinstance(raw, str):
        return None, "INVALID_" + field.upper()
    return raw.strip() or None, None


def compare_time_deviations(
    *,
    work_date: str,
    schedule: Mapping[str, Any] | None,
    attendance: Mapping[str, Any] | None,
    device_punches: Mapping[str, Any],
    device_candidate: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Calculate signed recorded-minus-expected differences without classification."""
    issues = []
    if device_candidate:
        if device_candidate.get("confirmed") is not False:
            issues.append("DEVICE_CANDIDATE_MUST_BE_UNCONFIRMED")
            device_candidate = None
        elif device_candidate.get("candidate_status") not in CANDIDATE_STATUSES:
            issues.append("DEVICE_CANDIDATE_STATUS_INVALID")
            device_candidate = None
        elif device_candidate.get("candidate_status") in BAD_CANDIDATE_STATUSES:
            issues.append("DEVICE_CANDIDATE_NEEDS_REVIEW")
            device_candidate = None
        elif (schedule and device_candidate.get("worker_id")
              and schedule.get("worker_id")
              and device_candidate["worker_id"] != schedule["worker_id"]) or (
              attendance and device_candidate.get("worker_id")
              and attendance.get("worker_id")
              and device_candidate["worker_id"] != attendance["worker_id"]):
            issues.append("DEVICE_CANDIDATE_ID_CONFLICT")
            device_candidate = None
    if schedule and attendance and schedule.get("worker_id") and attendance.get("worker_id"):
        if schedule["worker_id"] != attendance["worker_id"]:
            issues.append("SCHEDULE_ATTENDANCE_ID_CONFLICT")

    results = {}
    any_expected_comparison = False
    expected_difference = False
    for ledger_field, planned_field, candidate_field, reason_field in FIELDS:
        is_end = ledger_field == "clock_out"
        expected, expected_valid, expected_dated = _stamp(
            schedule.get(planned_field) if schedule else None, work_date, end=is_end,
        )
        ledger, ledger_valid, ledger_dated = _stamp(
            attendance.get(ledger_field) if attendance else None, work_date, end=is_end,
        )
        raw_device = device_punches.get(ledger_field)
        device_origin = "AUTHENTICATED_PUNCH" if raw_device else None
        basis = "EXPLICIT_" + ledger_field.upper() if raw_device else None
        if not raw_device and device_candidate:
            raw_device = device_candidate.get(candidate_field)
            if raw_device:
                device_origin = "UNCONFIRMED_ACCESS_CANDIDATE"
                basis = device_candidate.get("arrival_basis" if not is_end else "departure_basis")
        device, device_valid, device_dated = _stamp(raw_device, work_date, end=is_end)
        if not expected_valid:
            issues.append("EXPECTED_" + planned_field.upper() + "_INVALID")
        if not ledger_valid:
            issues.append("LEDGER_" + ledger_field.upper() + "_INVALID")
        if not device_valid:
            issues.append("DEVICE_" + ledger_field.upper() + "_INVALID")
        reason, bad_reason = _text_reason(attendance, reason_field)
        if bad_reason:
            issues.append(bad_reason)

        a, warning_a = _delta(ledger, ledger_dated, expected, expected_dated)
        b, warning_b = _delta(device, device_dated, expected, expected_dated)
        c, warning_c = _delta(device, device_dated, ledger, ledger_dated)
        if warning_a or warning_b or warning_c:
            issues.append("CLOCK_DATE_AMBIGUOUS")
        for value in (a, b):
            if value["delta_seconds"] is not None:
                any_expected_comparison = True
                if value["delta_seconds"] != 0:
                    expected_difference = True
        results[ledger_field] = {
            "expected": expected.isoformat(timespec="seconds") if expected else None,
            "ledger_recorded": ledger.isoformat(timespec="seconds") if ledger else None,
            "device_recorded": device.isoformat(timespec="seconds") if device else None,
            "ledger_vs_expected": a,
            "device_vs_expected": b,
            "device_vs_ledger": c,
            "device_origin": device_origin,
            "device_basis": basis,
            "device_confirmed_as_work": False,
            "reason": reason,
        }
    return {
        "status": ("DIFFERENT" if expected_difference else "MATCH"
                   if any_expected_comparison else "NOT_COMPARABLE"),
        "clock_in": results["clock_in"],
        "clock_out": results["clock_out"],
    }, sorted(set(issues))
