"""Shared, strict XLSX input helpers and canonical Common identity roles.

No implicit file discovery, historical module manifests or formula fallback.
"""
from __future__ import annotations

import calendar
import hashlib
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping

from .xlsx_stream import XlsxStreamError, open_xlsx_rows


class InputLayoutError(ValueError):
    pass


ROLE_PATHS = {
    "common": {
        "employees": "common/employee.xlsx",
        "identity": "common/id-map.xlsx",
    },
}


def period_bounds(month: str) -> tuple[str, str]:
    """Interpret only canonical YYYY-MM, never silently use today's month."""
    try:
        parsed = date.fromisoformat(month + "-01")
    except (TypeError, ValueError) as exc:
        raise InputLayoutError("period must be YYYY-MM") from exc
    if parsed.strftime("%Y-%m") != month:
        raise InputLayoutError("period must be YYYY-MM")
    return (parsed.isoformat(), f"{month}-{calendar.monthrange(parsed.year, parsed.month)[1]:02d}")


def choose_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise InputLayoutError("file path must be nonempty and relative to the input root")
    root = root.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise InputLayoutError("input path escapes shared input directory")
    if not target.is_file():
        raise InputLayoutError(
            f"Missing required input: {relative} (expected at {target})"
        )
    return target


def role(root: Path, module: str, key: str,
         overrides: Mapping[str, Mapping[str, str]] | None = None) -> Path:
    """Use a known role, not position-dependent filename arrays."""
    if module not in ROLE_PATHS or key not in ROLE_PATHS[module]:
        raise InputLayoutError(f"unknown input role: {module}.{key}")
    override = (overrides or {}).get(module, {})
    if not isinstance(override, Mapping):
        raise InputLayoutError(f"files.{module} must be a role-name mapping")
    default = ROLE_PATHS[module][key]
    filename = override.get(key, default)
    return choose_path(root, filename)


def read_sheet(path: Path, required: Iterable[str], *,
               sheet_name: str | None = None) -> list[dict[str, Any]]:
    """Strict workbook parse, preserving row numbers and rejecting bad headers.

    Extra columns are left available to callers without becoming required
    calculation fields. Tool callers validate business-specific fields independently.
    """
    try:
        # This shared-layout contract rejects every formula, as required by the selected Tool.
        with open_xlsx_rows(
            path, sheet_name=sheet_name, data_only=False,
        ) as opened:
            header_cells = opened.header_cells
            headers = [
                str(c.value).strip() if c.value is not None else ""
                for c in header_cells
            ]
            if not headers or any(not h for h in headers) or len(headers) != len(set(headers)):
                raise InputLayoutError(f"{path.name}: headers must be unique and nonempty")
            missing = set(required) - set(headers)
            if missing:
                raise InputLayoutError(f"{path.name}: missing columns {sorted(missing)}")
            result = []
            for number, cells in enumerate(opened.rows, start=2):
                if all(c.value is None for c in cells):
                    continue
                if any(c.data_type == "f" for c in cells):
                    raise InputLayoutError(f"{path.name}: formula at row {number} is unsupported")
                item = dict(zip(headers, (c.value for c in cells)))
                item["_row_number"] = number
                result.append(item)
            return result
    except XlsxStreamError as exc:
        if sheet_name is not None and str(exc) == f"worksheet not found: {sheet_name}":
            raise InputLayoutError(f"{path.name}: missing sheet {sheet_name}") from exc
        if str(exc) == "XLSX source has no header row":
            raise InputLayoutError(f"{path.name}: workbook has no header") from exc
        raise InputLayoutError(str(exc)) from exc

def read_id_map(root: Path, *,
                overrides: Mapping[str, Mapping[str, str]] | None = None
                ) -> dict[str, dict[str, str]]:
    """Read canonical mapping; reject ambiguous employee/worker/source IDs."""
    rows = read_sheet(
        role(root, "common", "identity", overrides),
        ("employee_id", "worker_id", "security_id"),
        sheet_name="ID_MAP",
    )
    records: dict[str, dict[str, str]] = {}
    worker_seen: set[str] = set()
    security_seen: set[str] = set()
    for row in rows:
        values = {
            key: str(row.get(key) or "").strip()
            for key in ("employee_id", "worker_id", "security_id")
        }
        if not all(values.values()):
            raise InputLayoutError(f"id-map.xlsx row {row['_row_number']}: blank identity")
        if (values["employee_id"] in records
                or values["worker_id"] in worker_seen
                or values["security_id"] in security_seen):
            raise InputLayoutError(
                f"id-map.xlsx row {row['_row_number']}: duplicated identity"
            )
        records[values["employee_id"]] = values
        worker_seen.add(values["worker_id"])
        security_seen.add(values["security_id"])
    if not records:
        raise InputLayoutError("id-map.xlsx: no employee mappings")
    return records


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def as_day(value: Any, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            pass
    raise InputLayoutError(f"invalid {field}: {value!r}")


def as_clock(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        if value.second or value.microsecond:
            raise InputLayoutError(f"{field}: minute precision required")
        return value.isoformat(timespec="minutes")
    if isinstance(value, str):
        try:
            clock = time.fromisoformat(value.strip())
            if clock.second or clock.microsecond:
                raise ValueError()
            return clock.isoformat(timespec="minutes")
        except ValueError:
            pass
    raise InputLayoutError(f"invalid {field}: {value!r}")


