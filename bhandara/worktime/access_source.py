"""Canonical, vendor-independent Excel contract for normalized access events.

Every vendor adapter writes the same fixed workbook. Calculation modules never
read raw CAPS/KT-specific column names or guess undocumented device codes.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from openpyxl import Workbook, load_workbook

from bhandara.common.io.input_layout import InputLayoutError, read_sheet

SCHEMA_VERSION = "0.2"
ACCESS_SHEET = "Access Events"
CANDIDATE_SHEET = "Attendance Candidates"
REVIEW_SHEET = "Source Review"
META_SHEET = "Metadata"
EVENT_COLUMNS = (
    "event_id", "employee_id", "worker_id", "work_date", "event_time",
    "mode", "direction", "auth_status", "auth_method", "device_id",
    "source_vendor", "source_ref", "source_row_number", "event_timestamp",
)
CANDIDATE_COLUMNS = (
    "employee_id", "worker_id", "work_date", "arrival_time", "departure_time",
    "arrival_basis", "departure_basis", "candidate_status", "confirmed",
    "evidence_event_ids", "source_vendor",
)
REVIEW_COLUMNS = (
    "source_vendor", "source_row_number", "status", "issue_codes",
    "source_ref", "detail",
)
META_COLUMNS = ("key", "value")
META_KEYS = (
    "schema_version", "source_vendor", "source_sha256", "source_file",
    "timezone", "event_count", "candidate_count", "review_count",
)
MODES = {"CLOCK_IN", "CLOCK_OUT", "ACCESS", "OUTING", "RETURN", "DISARM", "UNKNOWN"}
DIRECTIONS = {"IN", "OUT", "UNKNOWN"}
AUTH_STATUSES = {"SUCCESS", "FAILED", "UNKNOWN"}
AUTH_METHODS = {"FINGERPRINT", "FACE", "CARD", "PIN", "UNKNOWN"}
REVIEW_STATUSES = {"REJECTED", "REVIEW_REQUIRED", "UNMAPPED", "EXCLUDED"}


class AccessWorkbookError(ValueError):
    """Invalid canonical workbook or normalized upstream payload."""


def _iso_day(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or len(value) != 10:
        raise AccessWorkbookError("work_date requires YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AccessWorkbookError("invalid work_date") from exc
    if parsed.isoformat() != value:
        raise AccessWorkbookError("work_date requires canonical YYYY-MM-DD")
    return value


def _event_time(value: Any, work_date: str) -> str:
    if not isinstance(value, str) or len(value) != 16 or value[10] != "T":
        raise AccessWorkbookError("event_time requires YYYY-MM-DDTHH:MM")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AccessWorkbookError("invalid event_time") from exc
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise AccessWorkbookError("event_time must be local minute precision")
    workday = date.fromisoformat(work_date)
    if not workday <= parsed.date() <= workday + timedelta(days=1):
        raise AccessWorkbookError("event_time outside work_date/next day")
    return parsed.isoformat(timespec="minutes")


def _full_timestamp(value: Any, work_date: str) -> str:
    if not isinstance(value, str) or len(value) != 19 or value[10] != "T":
        raise AccessWorkbookError("event_timestamp requires YYYY-MM-DDTHH:MM:SS")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AccessWorkbookError("invalid event_timestamp") from exc
    if parsed.tzinfo is not None or parsed.microsecond:
        raise AccessWorkbookError("event_timestamp must be local second precision")
    workday = date.fromisoformat(work_date)
    if not workday <= parsed.date() <= workday + timedelta(days=1):
        raise AccessWorkbookError("event_timestamp outside workday/next day")
    return parsed.isoformat(timespec="seconds")


def _str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AccessWorkbookError(f"{key} must be string")
    return value.strip()


def _positive(row: Mapping[str, Any], key: str) -> int:
    value = row.get(key)
    if type(value) is not int or value < 1:
        raise AccessWorkbookError(f"{key} must be a positive Excel row number")
    return value


def _normalized_event(value: Mapping[str, Any], vendor: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AccessWorkbookError("access event must be mapping")
    row = {key: _str(value, key) for key in EVENT_COLUMNS
           if key not in ("work_date", "event_time", "source_row_number")}
    row["work_date"] = _iso_day(value.get("work_date"))
    row["event_time"] = _event_time(value.get("event_time"), row["work_date"])
    row["source_row_number"] = _positive(value, "source_row_number")
    full = value.get("event_timestamp")
    if full in (None, ""):
        full = row["event_time"] + ":00"
    row["event_timestamp"] = _full_timestamp(full, row["work_date"])
    if row["event_timestamp"][:16] != row["event_time"]:
        raise AccessWorkbookError("event_timestamp and event_time minute differ")
    for field in ("event_id", "employee_id", "worker_id", "source_ref"):
        if not row[field]:
            raise AccessWorkbookError(f"{field} is required")
    if row["source_vendor"] != vendor:
        raise AccessWorkbookError("event source_vendor must match metadata")
    for field, allowed in (
        ("mode", MODES), ("direction", DIRECTIONS),
        ("auth_status", AUTH_STATUSES), ("auth_method", AUTH_METHODS),
    ):
        if row[field] not in allowed:
            raise AccessWorkbookError(f"{field} not in normalized enumeration")
    return row


def _normalized_review(value: Mapping[str, Any], vendor: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AccessWorkbookError("source review must be mapping")
    row = {key: _str(value, key) for key in REVIEW_COLUMNS
           if key != "source_row_number"}
    row["source_row_number"] = _positive(value, "source_row_number")
    if row["source_vendor"] != vendor:
        raise AccessWorkbookError("review source_vendor must match metadata")
    if row["status"] not in REVIEW_STATUSES or not row["issue_codes"] or not row["source_ref"]:
        raise AccessWorkbookError("review status, issue_codes and source_ref required")
    return row



def _candidates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve explicit attendance modes; use first/last generic ACCESS only otherwise.

    Excluded security-setting/failed-auth raw records must never reach this
    stage. A candidate is never an approved attendance punch.
    """
    from collections import defaultdict

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[(event["employee_id"], event["worker_id"], event["work_date"])].append(event)
    output = []
    for key, rows in sorted(groups.items()):
        sorted_rows = sorted(rows, key=lambda row: (row["event_timestamp"], row["event_id"]))
        ins = [r for r in sorted_rows if r["mode"] == "CLOCK_IN"
               and r["auth_status"] != "FAILED"]
        outs = [r for r in sorted_rows if r["mode"] == "CLOCK_OUT"
                and r["auth_status"] != "FAILED"]
        generic = [r for r in sorted_rows if r["mode"] == "ACCESS"
                   and r["auth_status"] != "FAILED"]
        selected: list[dict[str, Any]] = []
        if ins or outs:
            arrival, departure = (ins[0] if len(ins) == 1 else None,
                                  outs[0] if len(outs) == 1 else None)
            arrival_basis = "EXPLICIT_CLOCK_IN" if arrival else "MISSING"
            departure_basis = "EXPLICIT_CLOCK_OUT" if departure else "MISSING"
            status = ("EXPLICIT_PAIR" if arrival and departure
                      else "MULTIPLE_EXPLICIT_REVIEW" if len(ins) > 1 or len(outs) > 1
                      else "PARTIAL_EXPLICIT")
            selected = ins + outs
        elif generic:
            arrival = generic[0]
            departure = generic[-1] if len(generic) > 1 else None
            arrival_basis = "INFERRED_FIRST_ACCESS"
            departure_basis = "INFERRED_LAST_ACCESS" if departure else "MISSING"
            status = "INFERRED_PAIR" if departure else "SINGLE_ACCESS"
            selected = generic if len(generic) <= 2 else [generic[0], generic[-1]]
        else:
            arrival = departure = None
            arrival_basis = departure_basis = "MISSING"
            status = "NO_ATTENDANCE_CANDIDATE"
        if arrival and departure and departure["event_timestamp"] <= arrival["event_timestamp"]:
            status = "TIME_SEQUENCE_REVIEW"
        output.append({
            "employee_id": key[0], "worker_id": key[1], "work_date": key[2],
            "arrival_time": arrival["event_timestamp"] if arrival else "",
            "departure_time": departure["event_timestamp"] if departure else "",
            "arrival_basis": arrival_basis, "departure_basis": departure_basis,
            "candidate_status": status, "confirmed": False,
            "evidence_event_ids": ",".join(r["event_id"] for r in selected),
            "source_vendor": rows[0]["source_vendor"],
        })
    return output


def _normalized_candidate(row: Mapping[str, Any], vendor: str) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise AccessWorkbookError("candidate must be mapping")
    output = {key: row.get(key) for key in CANDIDATE_COLUMNS}
    if type(output["confirmed"]) is not bool or output["confirmed"]:
        raise AccessWorkbookError("candidate must be unconfirmed")
    if output["source_vendor"] != vendor or not output["employee_id"] or not output["worker_id"]:
        raise AccessWorkbookError("candidate identity/vendor invalid")
    workday = _iso_day(output["work_date"])
    for key in ("arrival_time", "departure_time"):
        if output[key]:
            output[key] = _full_timestamp(output[key], workday)
    return output


def _safe(value: Any) -> Any:
    # Source/device-controlled values must never become executable formulas.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _append(sheet: Any, columns: tuple[str, ...],
            values: list[Mapping[str, Any]]) -> None:
    sheet.append(columns)
    for record in values:
        sheet.append([_safe(record[key]) for key in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(
            32, max(13, max(len(str(c.value or "")) for c in column[:100]) + 2)
        )


def write_access_events_xlsx(
    target: str | Path,
    events: Iterable[Mapping[str, Any]],
    source_reviews: Iterable[Mapping[str, Any]],
    *,
    source_vendor: str,
    source_sha256: str,
    source_file: str,
) -> Path:
    """Write a single stable schema regardless of raw vendor input format."""
    vendor = source_vendor.strip() if isinstance(source_vendor, str) else ""
    digest = source_sha256.lower() if isinstance(source_sha256, str) else ""
    if not vendor or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise AccessWorkbookError("source_vendor and SHA-256 are required")
    if (not isinstance(source_file, str) or not source_file or
            Path(source_file).name != source_file):
        raise AccessWorkbookError("source_file must be a basename")
    if isinstance(events, (str, bytes, Mapping)) or isinstance(source_reviews, (str, bytes, Mapping)):
        raise AccessWorkbookError("events and source_reviews must be row iterables")
    try:
        accepted = [_normalized_event(row, vendor) for row in events]
        reviews = [_normalized_review(row, vendor) for row in source_reviews]
    except TypeError as exc:
        raise AccessWorkbookError("events and source_reviews must be iterable") from exc
    keys = [row["event_id"] for row in accepted]
    if len(keys) != len(set(keys)):
        raise AccessWorkbookError("duplicate event_id; put unresolved input in Source Review")
    if not accepted and not reviews:
        raise AccessWorkbookError("empty source requires explicit review finding")
    candidates = [_normalized_candidate(row, vendor) for row in _candidates(accepted)]
    meta = [
        {"key": key, "value": str(value)}
        for key, value in {
            "schema_version": SCHEMA_VERSION,
            "source_vendor": vendor,
            "source_sha256": digest,
            "source_file": source_file,
            "timezone": "Asia/Seoul",
            "event_count": len(accepted),
            "candidate_count": len(candidates),
            "review_count": len(reviews),
        }.items()
    ]
    path = Path(target)
    if path.suffix.lower() != ".xlsx" or path.exists():
        raise AccessWorkbookError("output must be a new .xlsx file")
    if not path.parent.is_dir():
        raise AccessWorkbookError("output parent directory must exist")
    book = Workbook()
    try:
        primary = book.active
        primary.title = ACCESS_SHEET
        candidate_sheet = book.create_sheet(CANDIDATE_SHEET)
        review_sheet = book.create_sheet(REVIEW_SHEET)
        meta_sheet = book.create_sheet(META_SHEET)
        _append(primary, EVENT_COLUMNS, accepted)
        _append(candidate_sheet, CANDIDATE_COLUMNS, candidates)
        _append(review_sheet, REVIEW_COLUMNS, reviews)
        _append(meta_sheet, META_COLUMNS, meta)
        book.save(path)
        os.chmod(path, 0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        book.close()
    return path


def _exact_header(book: Any, sheet: str, expected: tuple[str, ...]) -> None:
    if sheet not in book.sheetnames:
        raise AccessWorkbookError(f"missing standard sheet: {sheet}")
    values = tuple(cell.value for cell in book[sheet][1])
    if values != expected:
        raise AccessWorkbookError(f"{sheet} columns differ from canonical schema")


def read_access_events_xlsx(source: str | Path) -> dict[str, Any]:
    """Read the canonical workbook and retain upstream rejected/review rows."""
    path = Path(source)
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        raise AccessWorkbookError("canonical .xlsx file required")
    try:
        book = load_workbook(path, read_only=True, data_only=False)
        try:
            if book.sheetnames != [ACCESS_SHEET, CANDIDATE_SHEET, REVIEW_SHEET, META_SHEET]:
                raise AccessWorkbookError("canonical sheet names/order mismatch")
            _exact_header(book, ACCESS_SHEET, EVENT_COLUMNS)
            _exact_header(book, CANDIDATE_SHEET, CANDIDATE_COLUMNS)
            _exact_header(book, REVIEW_SHEET, REVIEW_COLUMNS)
            _exact_header(book, META_SHEET, META_COLUMNS)
        finally:
            book.close()
        # Shared strict reader rejects formulas; no cached formula results are trusted.
        events = read_sheet(path, EVENT_COLUMNS, sheet_name=ACCESS_SHEET)
        candidate_rows = read_sheet(path, CANDIDATE_COLUMNS, sheet_name=CANDIDATE_SHEET)
        reviews = read_sheet(path, REVIEW_COLUMNS, sheet_name=REVIEW_SHEET)
        meta_rows = read_sheet(path, META_COLUMNS, sheet_name=META_SHEET)
    except (InputLayoutError, OSError, ValueError) as exc:
        raise AccessWorkbookError(str(exc)) from exc
    metadata = {row["key"]: str(row["value"]) for row in meta_rows}
    if set(metadata) != set(META_KEYS) or metadata["schema_version"] != SCHEMA_VERSION:
        raise AccessWorkbookError("canonical metadata keys or version invalid")
    if metadata["timezone"] != "Asia/Seoul":
        raise AccessWorkbookError("canonical timezone mismatch")
    if (metadata["event_count"] != str(len(events)) or
            metadata["candidate_count"] != str(len(candidate_rows)) or
            metadata["review_count"] != str(len(reviews))):
        raise AccessWorkbookError("canonical source counts mismatch")
    canonical_events = [_normalized_event(row, metadata["source_vendor"]) for row in (
        {**x, "source_row_number": x["source_row_number"]} for x in events
    )]
    canonical_reviews = [_normalized_review(row, metadata["source_vendor"]) for row in reviews]
    candidates = [_normalized_candidate(row, metadata["source_vendor"]) for row in candidate_rows]
    if candidates != _candidates(canonical_events):
        raise AccessWorkbookError("attendance candidates do not match normalized events")
    ids = [event["event_id"] for event in canonical_events]
    if len(set(ids)) != len(ids):
        raise AccessWorkbookError("canonical duplicate event_id")
    # Lower-level provenance uses _row_number for normalized-workbook row and
    # source_row_number for the vendor's original Excel line.
    for physical, event in zip(events, canonical_events):
        event["_row_number"] = event["source_row_number"]
        event["normalized_row_number"] = physical["_row_number"]
    actionable = [row for row in canonical_reviews if row["status"] != "EXCLUDED"]
    return {
        "schema_version": SCHEMA_VERSION,
        "events": canonical_events,
        "attendance_candidates": candidates,
        "source_reviews": canonical_reviews,
        "metadata": metadata,
        "status": "PASS" if canonical_events and not actionable else "REVIEW_REQUIRED",
    }


def verify_attendance_xlsx(
    attendance_rows: Iterable[Mapping[str, Any]],
    workbook_path: str | Path,
    *,
    period_from: str,
    period_to: str,
    accepted_auth_methods: Iterable[str] = ("FINGERPRINT",),
) -> dict[str, Any]:
    """One tool-internal handoff from *canonical* Excel to Attendance Verification.

    Do not discard vendor normalization findings even when accepted events
    alone happen to match the reported attendance ledger.
    """
    from importlib import import_module

    normalized = read_access_events_xlsx(workbook_path)
    module = import_module("bhandara.worktime.attendance-verification")
    result = module.verify_attendance(
        attendance_rows, normalized["events"],
        period_from=period_from, period_to=period_to,
        accepted_auth_methods=accepted_auth_methods,
    )
    actionable = [row for row in normalized["source_reviews"] if row["status"] != "EXCLUDED"]
    for row in actionable:
        result["source_issues"].append({
            "source": "access_normalization",
            "code": "NORMALIZATION_" + row["status"],
            "employee_id": "", "work_date": "",
            "source_ref": row["source_ref"],
            "row_number": row["source_row_number"],
            "detail": row["issue_codes"],
        })
    if actionable:
        result["status"] = "REVIEW_REQUIRED"
    result["normalized_source"] = {
        "schema_version": normalized["schema_version"],
        "source_vendor": normalized["metadata"]["source_vendor"],
        "source_sha256": normalized["metadata"]["source_sha256"],
        "normalized_review_count": len(actionable),
        "excluded_count": len(normalized["source_reviews"]) - len(actionable),
    }
    result["attendance_candidates"] = normalized["attendance_candidates"]
    return result
