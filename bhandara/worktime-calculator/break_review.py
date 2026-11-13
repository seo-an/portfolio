"""CAPS-neutral access event review for statutory breaks.

This module consumes *normalized* access reader facts. It never interprets
vendor-specific raw codes, authenticates a CAPS API, or declares that a gate
exit is legally a rest. It runs independently of Payroll/PTO and leaves the
migrated Worktime calculation and its three original artifacts unchanged.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Mapping

from openpyxl import load_workbook

VERSION = "0.1"
LEGAL_BASIS = "KR_LSA_ART54_2026-10-08"
EXCEPTION_START = date(2026, 12, 10)
DIRECTIONS = {"OUT": "OUT", "EXIT": "OUT", "IN": "IN", "ENTRY": "IN"}
CLASSES = {"REST_CONFIRMED", "BUSINESS_OUTING", "PERSONAL_OUTING", "UNKNOWN"}
REVIEW = "REVIEW_REQUIRED"


class BreakReviewError(ValueError):
    """Unusable normalized reader evidence; do not guess a legal conclusion."""


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        result = date.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise BreakReviewError("work_date must be YYYY-MM-DD") from exc
    if result.isoformat() != str(value):
        raise BreakReviewError("work_date must be YYYY-MM-DD")
    return result


def _clock(value: Any, day: date) -> datetime:
    if isinstance(value, datetime):
        candidate = value
    elif isinstance(value, time):
        candidate = datetime.combine(day, value)
    elif isinstance(value, str):
        if not value or value.strip() != value:
            raise BreakReviewError("event clock is blank or uncanonical")
        try:
            candidate = datetime.fromisoformat(
                f"{day.isoformat()}T{value}" if "T" not in value and " " not in value
                else value
            )
        except ValueError as exc:
            raise BreakReviewError("event clock invalid") from exc
    else:
        raise BreakReviewError("event clock invalid")
    if (candidate.tzinfo is not None or candidate.second or candidate.microsecond
            or not day <= candidate.date() <= day + timedelta(days=1)):
        raise BreakReviewError("event clock must be local minute precision")
    return candidate


def _interval(day: date, start: Any, end: Any) -> tuple[datetime, datetime]:
    first = _clock(start, day)
    last = _clock(end, day)
    if last <= first and last.date() == day:
        last += timedelta(days=1)
    if not 0 < (last - first).total_seconds() <= 24 * 3600:
        raise BreakReviewError("invalid time interval")
    return first, last


def _minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def legal_break_min(worked_min: int, work_date: date, *, explicit_request_ref: str = "") -> int:
    """Statutory minimum, not maximum; exception requires explicit evidence."""
    if type(worked_min) is not int or worked_min < 0:
        raise BreakReviewError("worked minutes invalid")
    if worked_min < 240:
        return 0
    if (work_date >= EXCEPTION_START and worked_min == 240
            and isinstance(explicit_request_ref, str) and explicit_request_ref.strip()):
        return 0
    return 30 if worked_min < 480 else 60


def _planned_window(schedule: Mapping[str, Any], day: date):
    start = schedule.get("break_start")
    end = schedule.get("break_end")
    if start in (None, "") and end in (None, ""):
        return None
    if start in (None, "") or end in (None, ""):
        raise BreakReviewError("scheduled break boundary incomplete")
    return _interval(day, start, end)


def _indexed_rows(bundle: Mapping[str, Any], kind: str) -> dict[tuple[str, str], dict]:
    source = bundle.get("sources", {}).get(kind, {})
    rows = source.get("rows", []) if isinstance(source, Mapping) else []
    if not isinstance(rows, list):
        raise BreakReviewError(f"{kind}: rows invalid")
    result: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise BreakReviewError(f"{kind}: non-object row")
        ident = row.get("employee_id")
        if not isinstance(ident, str) or not ident.strip():
            raise BreakReviewError(f"{kind}: employee_id missing")
        day = _date(row.get("work_date")).isoformat()
        key = (ident, day)
        if key in result:
            # Do not suppress conflicting or duplicated schedule/attendance facts.
            raise BreakReviewError(f"{kind}: duplicate employee-day")
        result[key] = dict(row)
    return result


def _events(bundle: Mapping[str, Any]) -> tuple[dict[tuple[str, str], list], str]:
    source = bundle.get("sources", {}).get("access_events")
    if not isinstance(source, Mapping):
        raise BreakReviewError("access_events source required")
    raw = source.get("rows")
    lineage = source.get("lineage")
    digest = source.get("source_sha256")
    if (not isinstance(raw, list) or not isinstance(lineage, list)
            or len(raw) != len(lineage)
            or type(digest) is not str or not digest):
        raise BreakReviewError("access_events provenance invalid")
    results = defaultdict(list)
    ids = set()
    for row, trace in zip(raw, lineage):
        if (not isinstance(row, Mapping) or not isinstance(trace, Mapping)
                or trace.get("status") != "ACCEPTED"):
            raise BreakReviewError("access_events must have accepted lineage")
        person = row.get("employee_id")
        day = _date(row.get("work_date"))
        event_id = row.get("event_id")
        direction = DIRECTIONS.get(str(row.get("direction") or "").strip().upper())
        if not isinstance(person, str) or not person or not isinstance(event_id, str) or not event_id:
            raise BreakReviewError("access event identifier invalid")
        if event_id in ids:
            raise BreakReviewError("duplicated CAPS event ID")
        ids.add(event_id)
        if direction is None:
            raise BreakReviewError("direction must be normalized IN/OUT")
        stamped = _clock(row.get("event_time"), day)
        classification = str(row.get("classification") or "UNKNOWN").upper()
        if classification not in CLASSES:
            raise BreakReviewError("unrecognized access classification")
        results[(person, day.isoformat())].append({
            "event_id": event_id, "at": stamped, "direction": direction,
            "classification": classification,
            "free_use_confirmed": row.get("free_use_confirmed") is True,
            "verification_ref": row.get("verification_ref"),
        })
    for daily in results.values():
        daily.sort(key=lambda row: row["at"])
    return dict(results), digest


def _paired_outings(events: list[dict], start: datetime, end: datetime):
    """Pair OUT to following IN. Unknown/duplicate/partial punches stay reviews."""
    outings = []
    problems = []
    open_exit = None
    for event in events:
        moment = event["at"]
        if not start <= moment <= end:
            problems.append("ACCESS_EVENT_OUTSIDE_ATTENDANCE")
            continue
        # The first entry and final exit are already represented by the
        # canonical attendance clock interval, not an intra-shift outing.
        if event["direction"] == "IN" and moment == start and open_exit is None:
            continue
        if event["direction"] == "OUT" and moment == end and open_exit is None:
            continue
        if event["direction"] == "OUT":
            if open_exit is not None:
                problems.append("DUPLICATE_OUT_PUNCH")
            open_exit = event
        else:
            if open_exit is None:
                problems.append("UNPAIRED_IN_PUNCH")
                continue
            if moment <= open_exit["at"]:
                problems.append("INVALID_ACCESS_SEQUENCE")
                open_exit = None
                continue
            outings.append((open_exit, event))
            open_exit = None
    if open_exit is not None:
        problems.append("UNPAIRED_OUT_PUNCH")
    return outings, sorted(set(problems))


def _verification_index(config: Mapping[str, Any]) -> dict[tuple[str, str], dict]:
    supplied = config.get("break_verifications", [])
    if not isinstance(supplied, list):
        raise BreakReviewError("break_verifications must be a list")
    by_day = {}
    for row in supplied:
        if not isinstance(row, Mapping):
            raise BreakReviewError("break_verification row invalid")
        ident = row.get("employee_id")
        day = _date(row.get("work_date")).isoformat()
        key = (ident, day)
        if not isinstance(ident, str) or not ident or key in by_day:
            raise BreakReviewError("duplicated or invalid break_verification")
        coverage = row.get("coverage_complete", False)
        if type(coverage) is not bool:
            raise BreakReviewError("coverage_complete must be boolean")
        if coverage and not str(row.get("evidence_ref") or "").strip():
            raise BreakReviewError("complete coverage requires evidence_ref")
        by_day[key] = dict(row)
    return by_day


def _classify_outing(exit_event: dict, entry_event: dict, planned) -> dict:
    """Reader facts alone are only candidates; verified rest needs extra evidence."""
    first, last = exit_event["at"], entry_event["at"]
    minutes = _minutes(first, last)
    label = exit_event["classification"]
    verified = (
        label == "REST_CONFIRMED"
        and exit_event["free_use_confirmed"]
        and isinstance(exit_event["verification_ref"], str)
        and bool(exit_event["verification_ref"].strip())
        and entry_event["classification"] in (label, "UNKNOWN")
    )
    if label == "BUSINESS_OUTING":
        kind = "BUSINESS_OUTING"
    elif label == "PERSONAL_OUTING":
        kind = "PERSONAL_OUTING"
    elif verified:
        kind = "REST_VERIFIED"
    elif planned is not None and first >= planned[0] and last <= planned[1]:
        kind = "PLANNED_BREAK_CANDIDATE"
    else:
        kind = "OUTING_REVIEW"
    return {
        "start": first.isoformat(timespec="minutes"),
        "end": last.isoformat(timespec="minutes"),
        "duration_min": minutes,
        "classification": kind,
        "confirmed_rest_min": minutes if verified else 0,
        "verification_ref": exit_event["verification_ref"] if verified else None,
    }


def _assess_one(worker_id: str, employee_id: str, day: str,
                schedule: Mapping[str, Any], attendance: Mapping[str, Any],
                events: list[dict], verification: Mapping[str, Any]) -> dict:
    work_date = _date(day)
    try:
        planned = _planned_window(schedule, work_date)
        start, end = _interval(work_date, attendance.get("clock_in"), attendance.get("clock_out"))
        outings, errors = _paired_outings(events, start, end)
        classifications = [_classify_outing(out, back, planned)
                           for out, back in outings]
    except BreakReviewError:
        return _unresolved(worker_id, day, "BREAK_SOURCE_TIME_INVALID", schedule)
    # Independent from migrated payroll-hour calculations: do not revise pay.
    rest_min = sum(item["confirmed_rest_min"] for item in classifications)
    unknown = any(item["classification"] in
                  {"PLANNED_BREAK_CANDIDATE", "OUTING_REVIEW", "PERSONAL_OUTING"}
                  for item in classifications)
    gross_min = _minutes(start, end)
    if rest_min > gross_min:
        return _unresolved(worker_id, day, "REST_EXCEEDS_ATTENDANCE_SPAN", schedule)
    # The conservative upper bound on work excludes only verified rest.
    work_upper = gross_min - rest_min
    waiver = verification.get("four_hour_waiver_ref", "")
    required_upper = legal_break_min(work_upper, work_date,
                                     explicit_request_ref=waiver)
    coverage = verification.get("coverage_complete") is True
    if required_upper == 0 or rest_min >= required_upper:
        state = "PASS_VERIFIED" if required_upper and rest_min >= required_upper else REVIEW
        reasons = [] if state == "PASS_VERIFIED" else ["MINIMUM_THRESHOLD_NOT_FULLY_VERIFIED"]
        required = required_upper
        gap = 0 if state == "PASS_VERIFIED" else None
    elif coverage and not errors and not unknown:
        # Only a separately certified complete record rules out indoor rest.
        state = "SHORTFALL_DETECTED"
        reasons = ["STATUTORY_BREAK_MINIMUM_SHORTFALL"]
        required = required_upper
        gap = required - rest_min
    else:
        state = REVIEW
        reasons = ["UNVERIFIED_OR_INCOMPLETE_BREAK_EVIDENCE"]
        required = required_upper if coverage and not errors and not unknown else None
        gap = None
    if errors:
        state = REVIEW
        reasons.extend(errors)
        required = None
        gap = None
    if verification.get("four_hour_waiver_ref") and work_date < EXCEPTION_START:
        state = REVIEW
        reasons.append("WAIVER_NOT_IN_FORCE")
        required = None
        gap = None
    return {
        "worker_id": worker_id, "work_date": day,
        "status": state,
        "planned_break_min": schedule.get("break_min"),
        "planned_window": [
            item.isoformat(timespec="minutes") for item in planned
        ] if planned else None,
        "gross_presence_min": gross_min,
        "verified_rest_min": rest_min,
        "required_break_min": required,
        "confirmed_shortfall_min": gap,
        "coverage_complete": coverage,
        "event_intervals": classifications,
        "review_codes": sorted(set(reasons)),
        "legal_basis": LEGAL_BASIS,
        "approved": False,
    }


def _unresolved(worker_id: str, day: str, reason: str,
                schedule: Mapping[str, Any]) -> dict:
    return {
        "worker_id": worker_id, "work_date": day, "status": REVIEW,
        "planned_break_min": schedule.get("break_min"),
        "planned_window": None, "gross_presence_min": None,
        "verified_rest_min": None, "required_break_min": None,
        "confirmed_shortfall_min": None, "coverage_complete": False,
        "event_intervals": [], "review_codes": [reason],
        "legal_basis": LEGAL_BASIS, "approved": False,
    }


def analyze_access_breaks(bundle: Mapping[str, Any],
                          config: Mapping[str, Any],
                          result: Mapping[str, Any]) -> dict:
    """Analyze only scheduled/calc'd days, preserve all CAPS source lineage."""
    if "access_events" not in bundle.get("sources", {}):
        raise BreakReviewError("access_events normalized source not supplied")
    schedule = _indexed_rows(bundle, "schedule")
    attendance = _indexed_rows(bundle, "attendance")
    events, digest = _events(bundle)
    checks = _verification_index(config)
    roster = {
        row["employee_id"]: row["worker_id"]
        for row in bundle["sources"]["employees"]["rows"]
    }
    if len(set(roster.values())) != len(roster):
        raise BreakReviewError("ambiguous worker identity mapping")
    # A cross-employee collision or forged worker_id is never an implicit match.
    for key, items in events.items():
        if key[0] not in roster:
            raise BreakReviewError("access event references unknown employee")
    examined = set()
    rows = []
    for computed in result["rows"]:
        worker, day = computed["worker_id"], computed["work_date"]
        owners = [ident for ident, wid in roster.items() if wid == worker]
        if len(owners) != 1:
            raise BreakReviewError("worker identity not one-to-one")
        ident = owners[0]
        key = (ident, day)
        examined.add(key)
        if key not in schedule or key not in attendance:
            rows.append(_unresolved(worker, day, "SOURCE_DAY_MISSING", {}))
        else:
            rows.append(_assess_one(worker, ident, day, schedule[key],
                                    attendance[key], events.get(key, []),
                                    checks.get(key, {})))
    for key in sorted(set(events) - examined):
        ident, day = key
        rows.append(_unresolved(roster.get(ident, ""), day,
                                "UNMATCHED_ACCESS_EVENTS", schedule.get(key, {})))
    for key in sorted(set(checks) - examined):
        ident, day = key
        rows.append(_unresolved(roster.get(ident, ""), day,
                                "UNMATCHED_BREAK_VERIFICATION", schedule.get(key, {})))
    rows.sort(key=lambda row: (row["worker_id"], row["work_date"], row["review_codes"]))
    return {
        "schema_version": VERSION,
        "status": REVIEW if any(row["status"] != "PASS_VERIFIED" for row in rows)
                  else "PASS_VERIFIED",
        "finalizable": False, "approved": False,
        "source_batch_id": bundle.get("batch_id"),
        "access_events_sha256": digest,
        "legal_basis": LEGAL_BASIS,
        "rows": rows,
    }


def write_break_review(output_dir: str | Path, data: Mapping[str, Any]) -> None:
    """Append an Excel review sheet; create a separately review-only JSON sidecar.

    Called after original Worktime outputs exist, while this new run directory
    is still private. The original three Worktime JSON/XLSX contracts and the
    migrated calculation files are not modified except for the new XLSX sheet.
    """
    folder = Path(output_dir)
    path = folder / "worktime-review.xlsx"
    sidecar = folder / "break-compliance.json"
    if not path.is_file() or sidecar.exists():
        raise BreakReviewError("existing Worktime review expected; no overwrites")
    book = load_workbook(path)
    try:
        if "Break Compliance" in book.sheetnames:
            raise BreakReviewError("Break Compliance already exists")
        sheet = book.create_sheet("Break Compliance")
        cols = ("worker_id", "work_date", "status", "planned_break_min",
                "gross_presence_min", "verified_rest_min",
                "required_break_min", "confirmed_shortfall_min",
                "coverage_complete", "review_codes", "event_intervals")
        sheet.append(cols)
        for row in data["rows"]:
            values = []
            for name in cols:
                value = row.get(name)
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                values.append(value)
            sheet.append(values)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
        os.chmod(path, 0o600)
    finally:
        book.close()
    with sidecar.open("x", encoding="utf-8") as handle:
        os.chmod(sidecar, 0o600)
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
