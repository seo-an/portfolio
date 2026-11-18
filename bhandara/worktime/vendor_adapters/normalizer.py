"""Normalize security-system raw Excel into the sole Worktime Access Events XLSX.

Only observed vendor headers and documented codes are mapped. Any identifier
ambiguity or undocumented interpretation is review-only, never guessed.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping

from bhandara.common.io.input_layout import InputLayoutError, hash_file, read_sheet
from bhandara.worktime.access_source import write_access_events_xlsx

from .profiles import PROFILES, VendorProfile


class VendorSourceError(ValueError):
    """Invalid input contract, profile, or conflicting identity index."""


AUTH_METHODS = {
    "지문": "FINGERPRINT", "지문인식": "FINGERPRINT",
    "안면인식": "FACE", "얼굴인식": "FACE",
    "카드": "CARD", "카드인증": "CARD", "RF카드": "CARD",
    "비밀번호": "PIN", "PIN": "PIN",
}
MODES = {
    "출근": "CLOCK_IN", "출근(인증)": "CLOCK_IN",
    "퇴근": "CLOCK_OUT", "퇴근(인증)": "CLOCK_OUT",
    "출입": "ACCESS", "일반출입": "ACCESS",
    "외출": "OUTING", "복귀": "RETURN",
    "경비해제": "DISARM",
}
EXCLUDED_SECURITY_SET = frozenset({
    "세트", "세트(경비시작)", "경비시작", "경비설정", "경비세트", "경비시작(세트)",
})
OPTIONAL_MODE_COLUMNS = ("구분", "상태", "출입구분", "근태구분")


def _number(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if type(value) is int:
        return str(value)
    if type(value) is float:
        return str(int(value)) if value.is_integer() else ""
    if isinstance(value, str):
        return value.strip()
    return ""


def _identity_index(
    identities: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, str]]:
    if isinstance(identities, (str, bytes, Mapping)):
        raise VendorSourceError("identity_rows must be a list of mappings")
    index: dict[tuple[str, str], dict[str, str]] = {}
    seen_workers: dict[str, tuple[str, str]] = {}
    try:
        iterator = iter(identities)
    except TypeError as exc:
        raise VendorSourceError("identity_rows must be iterable") from exc
    for row in iterator:
        if not isinstance(row, Mapping):
            raise VendorSourceError("identity row must be mapping")
        department = str(row.get("department") or "").strip()
        number = _number(row.get("employee_number"))
        employee_id = str(row.get("employee_id") or "").strip()
        worker_id = str(row.get("worker_id") or "").strip()
        key = (department, number)
        if (not all((*key, employee_id, worker_id)) or key in index or
                (worker_id in seen_workers and seen_workers[worker_id] != key)):
            raise VendorSourceError("incomplete, duplicate, or ambiguous department-number mapping")
        index[key] = {
            "employee_id": employee_id, "worker_id": worker_id,
            "name": str(row.get("name") or "").strip(),
        }
        seen_workers[worker_id] = key
    if not index:
        raise VendorSourceError("verified identity mapping is required")
    return index


def _datetime(value: Any, *, date_value: Any = None) -> datetime:
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    if date_value is None:
        if isinstance(value, datetime):
            result = value
        elif isinstance(value, str):
            label = value.strip()
            korean = re.fullmatch(
                r"(\d{4}-\d{2}-\d{2})\s*(오전|오후)\s*(\d{1,2}):(\d{2})(?::(\d{2}))?",
                label,
            )
            if korean:
                day, ampm, hh, mm, ss = korean.groups()
                hour = int(hh)
                if not 1 <= hour <= 12:
                    raise VendorSourceError("invalid Korean AM/PM hour")
                hour = hour % 12 + (12 if ampm == "오후" else 0)
                result = datetime.fromisoformat(f"{day}T{hour:02d}:{mm}:{ss or '00'}")
            else:
                try:
                    result = datetime.fromisoformat(label.replace(" ", "T", 1))
                except ValueError as exc:
                    raise VendorSourceError("unsupported combined timestamp") from exc
        else:
            raise VendorSourceError("unsupported combined timestamp type")
    else:
        if isinstance(date_value, date):
            day = date_value
        elif isinstance(date_value, str):
            try:
                day = date.fromisoformat(date_value.strip())
            except ValueError as exc:
                raise VendorSourceError("invalid source work date") from exc
        else:
            raise VendorSourceError("invalid source work date")
        if isinstance(value, datetime):
            t = value.time()
        elif isinstance(value, time):
            t = value
        elif isinstance(value, str):
            try:
                t = time.fromisoformat(value.strip())
            except ValueError as exc:
                raise VendorSourceError("invalid source time") from exc
        else:
            raise VendorSourceError("unsupported source time type")
        result = datetime.combine(day, t)
    if result.tzinfo is not None or result.microsecond:
        raise VendorSourceError("source times must be local second precision")
    return result


def _classification(value: Any, *, mode_column: bool) -> str:
    if not mode_column:
        return "ACCESS"
    raw = str(value or "").strip()
    if not raw:
        raise VendorSourceError("empty source mode")
    key = re.sub(r"\s+", "", raw)
    if key not in MODES:
        raise VendorSourceError("unrecognized source mode")
    return MODES[key]


def _excluded(row: Mapping[str, Any], profile: VendorProfile) -> str:
    # Both mode/status and credential-type exports can contain exclusion codes.
    for column in (profile.mode_column, profile.auth_method_column, *OPTIONAL_MODE_COLUMNS):
        if not column or row.get(column) in (None, ""):
            continue
        label = re.sub(r"\s+", "", str(row[column]))
        if label in EXCLUDED_SECURITY_SET or label.startswith("세트("):
            return "SECURITY_SET_EXCLUDED"
        if "인식실패" in label or "인증실패" in label or label.endswith("실패"):
            return "AUTH_FAILURE_EXCLUDED"
    return ""


def _review(vendor: str, row_number: int, ref: str, status: str,
            issue: str) -> dict[str, Any]:
    return {
        "source_vendor": vendor, "source_row_number": row_number,
        "status": status, "issue_codes": issue,
        "source_ref": ref, "detail": issue,
    }


def normalize_vendor_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    vendor: str,
    identities: Iterable[Mapping[str, Any]],
    source_ref: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize raw rows, preserving omissions as review or explicit exclusion."""
    profile = PROFILES.get(vendor)
    if profile is None:
        raise VendorSourceError("unknown vendor profile")
    mapping = _identity_index(identities)
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise VendorSourceError("source_ref required")
    events = []
    reviews = []
    for offset, raw in enumerate(rows, start=2):
        if not isinstance(raw, Mapping):
            raise VendorSourceError("raw rows must be mapping")
        physical = raw.get("_row_number", offset)
        if type(physical) is not int or physical < 2:
            raise VendorSourceError("invalid physical row number")
        exclude = _excluded(raw, profile)
        if exclude:
            reviews.append(_review(vendor, physical, source_ref, "EXCLUDED", exclude))
            continue
        department = str(raw.get(profile.department) or "").strip()
        number = _number(raw.get(profile.employee_number))
        matched = mapping.get((department, number))
        if not matched:
            reviews.append(_review(vendor, physical, source_ref, "UNMAPPED",
                                   "DEPARTMENT_EMPLOYEE_NUMBER_UNMAPPED"))
            continue
        name = str(raw.get(profile.employee_name) or "").strip()
        if matched["name"] and matched["name"] != name:
            reviews.append(_review(vendor, physical, source_ref, "REVIEW_REQUIRED",
                                   "EMPLOYEE_NAME_CONFLICT"))
            continue
        try:
            if profile.timestamp_column:
                moment = _datetime(raw.get(profile.timestamp_column))
            else:
                moment = _datetime(raw.get(profile.time_column),
                                   date_value=raw.get(profile.date_column))
            mode_key = profile.mode_column
            if mode_key is None:
                mode_key = next((key for key in OPTIONAL_MODE_COLUMNS
                                 if key in raw and raw.get(key) not in (None, "")), None)
            mode = _classification(raw.get(mode_key), mode_column=bool(mode_key))
        except VendorSourceError as exc:
            reviews.append(_review(vendor, physical, source_ref, "REVIEW_REQUIRED",
                                   str(exc).upper().replace(" ", "_")[:70]))
            continue
        credential = raw.get(profile.auth_method_column) if profile.auth_method_column else None
        if profile.auth_method_column:
            method = AUTH_METHODS.get(re.sub(r"\s+", "", str(credential or "")), "UNKNOWN")
        else:
            method = "UNKNOWN"
        if profile.auth_method_column and method == "UNKNOWN" and credential not in (None, ""):
            reviews.append(_review(vendor, physical, source_ref, "REVIEW_REQUIRED",
                                   "AUTH_METHOD_UNMAPPED"))
        events.append({
            "event_id": f"{vendor}-{physical}-{number}",
            "employee_id": matched["employee_id"],
            "worker_id": matched["worker_id"],
            "work_date": moment.date().isoformat(),
            "event_time": moment.isoformat(timespec="minutes"),
            "event_timestamp": moment.isoformat(timespec="seconds"),
            "mode": mode, "direction": "UNKNOWN",
            "auth_status": "SUCCESS", "auth_method": method,
            "device_id": str(raw.get(profile.device) or "").strip(),
            "source_vendor": vendor, "source_ref": source_ref,
            "source_row_number": physical,
        })
    return events, reviews


def normalize_vendor_excel(
    source_path: str | Path,
    output_path: str | Path,
    *,
    vendor: str,
    identities: Iterable[Mapping[str, Any]],
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Read one vendor's source sheet and write identical canonical Excel."""
    profile = PROFILES.get(vendor)
    if profile is None:
        raise VendorSourceError("unknown vendor profile")
    path = Path(source_path)
    try:
        raw = read_sheet(path, profile.required, sheet_name=sheet_name)
        digest = hash_file(path)
    except (InputLayoutError, OSError) as exc:
        raise VendorSourceError(str(exc)) from exc
    ref = f"{path.name}:{sheet_name or '[first-sheet]'}"
    events, reviews = normalize_vendor_rows(
        raw, vendor=vendor, identities=identities, source_ref=ref,
    )
    target = write_access_events_xlsx(
        output_path, events, reviews,
        source_vendor=vendor, source_sha256=digest, source_file=path.name,
    )
    return {
        "output_path": str(target),
        "source_vendor": vendor,
        "normalized_events": len(events),
        "source_reviews": len(reviews),
        "excluded": sum(row["status"] == "EXCLUDED" for row in reviews),
        "status": ("PASS" if events and all(r["status"] == "EXCLUDED" for r in reviews)
                   else "REVIEW_REQUIRED"),
    }
