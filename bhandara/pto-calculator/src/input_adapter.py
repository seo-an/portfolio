"""Excel-to-PTO handoff adapter; no Gearbox, auth, or cloud dependency.

The original Gearbox Tooth's *field selection and value conversions* are
preserved. This adapter deliberately does not use randomly pseudonymized IDs:
it runs locally and writes restricted outputs; source IDs remain stable so
human review and the private Golden baseline can be reconciled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from openpyxl.utils.exceptions import InvalidFileException

from bhandara.common.contracts.findings import Finding, Scope, Severity
from bhandara.common.utils.hashing import sha256_file
from bhandara.common.validation.headers import HeaderContractError, is_blank, parse_headers


class PTOInputError(ValueError):
    """Run-wide input contract failure; no calculation can safely begin."""


# These are the exact selected columns of the legacy PTO preparation Tooth.
EMPLOYEE_HEADERS = ("employee_id", "hire_date", "termination_date", "work_system")
SCHEDULE_HEADERS = (
    "schedule_id", "work_system", "sequence", "day_type", "shift_code",
    "start_time", "end_time", "break_min", "scheduled_work_hours", "note",
)
ASSIGNMENT_HEADERS = (
    "employee_id", "schedule_id", "effective_from", "effective_to",
    "cycle_anchor_date", "start_sequence", "note",
)
MONTHLY_SCHEDULE_HEADERS = (
    "employee_id", "work_date", "schedule_id", "shift_code", "scheduled_start",
    "scheduled_end", "break_min", "scheduled_work_hours", "day_type", "note",
)
ATTENDANCE_HEADERS = (
    "employee_id", "work_date", "clock_in", "clock_out", "break_min", "source", "note",
)
EVENT_HEADERS = (
    "request_id", "employee_id", "event_type", "event_date", "unit", "status", "note",
)


@dataclass(slots=True)
class LoadedSheet:
    kind: str
    path: Path
    sheet: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_numbers: list[int] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    rejected_owners: set[str] = field(default_factory=set)
    unassignable_error: bool = False
    source_hash: str = ""


@dataclass(slots=True)
class PTOInputBundle:
    handoff: dict[str, list[dict[str, Any]]]
    sources: dict[str, Path]
    source_hashes: dict[str, str]
    findings: list[Finding]
    blocked_employee_ids: set[str]
    global_block: bool


def _normalize_date(value: Any, *, epoch: datetime) -> date | None:
    # Retained from gearbox.teeth.pto_preparation._normalize_date.
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    if isinstance(value, (int, float)):
        converted = from_excel(value, epoch=epoch)
        if isinstance(converted, datetime):
            return converted.date()
        if isinstance(converted, date):
            return converted
    raise ValueError("unsupported date value")


def _normalize_time(value: Any) -> time | None:
    # Retained from gearbox.teeth.pto_preparation._normalize_time.
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, time):
        return value.replace(microsecond=0)
    if isinstance(value, str):
        return time.fromisoformat(value.strip()).replace(microsecond=0)
    if isinstance(value, (int, float)) and 0 <= value < 1:
        seconds = round(float(value) * 86400) % 86400
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return time(hours, minutes, seconds)
    raise ValueError("unsupported time value")


SCHEMAS: dict[str, dict[str, Any]] = {
    "employees": {
        "headers": EMPLOYEE_HEADERS, "required_values": ("employee_id", "hire_date"),
        "dates": ("hire_date", "termination_date"),
    },
    "schedule": {
        "headers": SCHEDULE_HEADERS, "required_values": ("schedule_id", "sequence", "day_type"),
        "times": ("start_time", "end_time"), "integers": ("sequence", "break_min"),
    },
    "assignments": {
        "headers": ASSIGNMENT_HEADERS,
        "required_values": ("employee_id", "schedule_id", "effective_from",
                            "cycle_anchor_date", "start_sequence"),
        "dates": ("effective_from", "effective_to", "cycle_anchor_date"),
        "integers": ("start_sequence",),
    },
    "monthly_schedule": {
        "headers": MONTHLY_SCHEDULE_HEADERS,
        "required_values": ("employee_id", "work_date", "day_type"),
        "dates": ("work_date",), "times": ("scheduled_start", "scheduled_end"),
        "integers": ("break_min",),
    },
    "attendance": {
        "headers": ATTENDANCE_HEADERS,
        "required_values": ("employee_id", "work_date"),
        "dates": ("work_date",), "times": ("clock_in", "clock_out"),
        "integers": ("break_min",),
    },
    "events": {
        "headers": EVENT_HEADERS,
        "required_values": ("employee_id", "event_date", "event_type"),
        "dates": ("event_date",),
    },
}


def resolve_input_file(input_dir: Path, relative_name: str) -> Path:
    """Keep all declared sources inside the chosen input directory."""
    if (not isinstance(relative_name, str) or not relative_name.strip()
            or relative_name.startswith(("/", "\\")) or "\x00" in relative_name):
        raise PTOInputError("source filename must be a nonempty relative path")
    root = input_dir.resolve(strict=True)
    path = input_dir / relative_name
    if path.is_symlink():
        raise PTOInputError("source files must not be symlinks")
    target = path.resolve()
    if not target.is_relative_to(root):
        raise PTOInputError("source path escapes input directory")
    if target.suffix.lower() not in (".xlsx", ".xlsm") or not target.is_file():
        raise PTOInputError(f"XLSX/XLSM input not found: {Path(relative_name).name}")
    return target


def _finding(kind: str, path: Path, sheet: str, row: int, field_name: str, code: str) -> Finding:
    return Finding(
        code=code, severity=Severity.ERROR, scope=Scope.CELL,
        message=f"{kind} input cell requires correction before its affected calculation",
        source=path.name, sheet=sheet, row_number=row, field=field_name,
    )


def read_pto_sheet(path: Path, kind: str, *, sheet_name: str | None = None) -> LoadedSheet:
    """Read the exact legacy column set without rejecting blanks in optional cells."""
    if kind not in SCHEMAS:
        raise PTOInputError(f"unknown PTO source kind: {kind}")
    spec = SCHEMAS[kind]
    try:
        before = sha256_file(path)
        book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        raise PTOInputError(f"unable to open {path.name}: {type(exc).__name__}") from exc
    try:
        if sheet_name is not None and sheet_name not in book.sheetnames:
            raise PTOInputError(f"{path.name}: required worksheet missing: {sheet_name}")
        sheet = book[sheet_name] if sheet_name is not None else book.active
        values = sheet.iter_rows()
        first = next(values, None)
        if first is None:
            raise PTOInputError(f"{path.name}: no header row")
        try:
            header_map = parse_headers([cell.value for cell in first], spec["headers"])
        except HeaderContractError as exc:
            raise PTOInputError(f"{path.name}: {exc}") from exc
        loaded = LoadedSheet(kind=kind, path=path, sheet=sheet.title, source_hash=before)
        for row_number, cells in enumerate(values, start=2):
            if not any(not is_blank(c.value) for c in cells):
                continue
            selected = header_map.project([c.value for c in cells])
            invalid = False
            owner = selected.get("employee_id")
            if isinstance(owner, str) and owner and owner == owner.strip():
                owner_id = owner
            else:
                owner_id = None
            for name, position in zip(header_map.required, header_map.positions):
                if position < len(cells) and cells[position].data_type == "f":
                    loaded.findings.append(_finding(kind, path, sheet.title, row_number, name, "FORMULA_UNSUPPORTED"))
                    invalid = True
            for required in spec["required_values"]:
                if is_blank(selected[required]):
                    loaded.findings.append(_finding(kind, path, sheet.title, row_number, required, "REQUIRED_CELL_MISSING"))
                    invalid = True
            for required in spec["required_values"]:
                if required == "employee_id" and selected[required] is not None and owner_id is None:
                    loaded.findings.append(_finding(kind, path, sheet.title, row_number, required, "EMPLOYEE_ID_INVALID"))
                    invalid = True
            for name in spec.get("dates", ()):
                try:
                    selected[name] = _normalize_date(selected[name], epoch=book.epoch)
                except (ValueError, TypeError, OverflowError):
                    loaded.findings.append(_finding(kind, path, sheet.title, row_number, name, "INVALID_DATE"))
                    invalid = True
            for name in spec.get("times", ()):
                try:
                    selected[name] = _normalize_time(selected[name])
                except (ValueError, TypeError, OverflowError):
                    loaded.findings.append(_finding(kind, path, sheet.title, row_number, name, "INVALID_TIME"))
                    invalid = True
            for name in spec.get("integers", ()):
                value = selected[name]
                if value not in (None, ""):
                    try:
                        selected[name] = int(value)
                    except (ValueError, TypeError, OverflowError):
                        loaded.findings.append(_finding(kind, path, sheet.title, row_number, name, "INVALID_INTEGER"))
                        invalid = True
            if invalid:
                if owner_id is None or kind == "schedule":
                    loaded.unassignable_error = True
                else:
                    loaded.rejected_owners.add(owner_id)
                continue
            loaded.rows.append(selected)
            loaded.row_numbers.append(row_number)
        if sha256_file(path) != before:
            raise PTOInputError(f"{path.name}: input changed during read")
        return loaded
    except (BadZipFile, OSError) as exc:
        raise PTOInputError(f"could not read {path.name}: {type(exc).__name__}") from exc
    finally:
        book.close()


def load_pto_inputs(input_dir: Path, source_files: dict[str, Any]) -> PTOInputBundle:
    """Prepare legacy handoff, retaining per-file provenance and blast radius."""
    if not isinstance(source_files, dict):
        raise PTOInputError("config.files must be an object")
    mandatory = ("employees", "schedule", "assignments")
    for name in mandatory:
        if not isinstance(source_files.get(name), str):
            raise PTOInputError(f"config.files.{name} must be a filename")
    for name in ("monthly_schedule", "attendance"):
        if not isinstance(source_files.get(name, []), list):
            raise PTOInputError(f"config.files.{name} must be a list")
    tasks = [(name, source_files[name]) for name in mandatory]
    tasks += [(kind, name) for kind in ("monthly_schedule", "attendance")
              for name in source_files.get(kind, [])]
    if source_files.get("events") is not None:
        tasks.append(("events", source_files["events"]))
    for kind, filename in tasks:
        if not isinstance(filename, str):
            raise PTOInputError(f"{kind}: input filename must be text")
    paths_seen = set()
    loaded: dict[str, list[LoadedSheet]] = {}
    sources: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    findings: list[Finding] = []
    blocked: set[str] = set()
    global_block = False
    for kind, filename in tasks:
        path = resolve_input_file(input_dir, filename)
        if path in paths_seen:
            raise PTOInputError("same source file appears multiple times")
        paths_seen.add(path)
        item = read_pto_sheet(path, kind)
        loaded.setdefault(kind, []).append(item)
        label = f"{kind}:{filename}"
        sources[label] = path
        hashes[label] = item.source_hash
        findings.extend(item.findings)
        blocked.update(item.rejected_owners)
        global_block = global_block or item.unassignable_error
    employees = loaded["employees"][0]
    seen: set[str] = set()
    for row, row_number in zip(employees.rows, employees.row_numbers):
        ident = row["employee_id"]
        if not isinstance(ident, str) or not ident.strip() or ident != ident.strip():
            global_block = True
            findings.append(_finding("employees", employees.path, employees.sheet,
                                     row_number, "employee_id", "EMPLOYEE_ID_INVALID"))
            continue
        if ident in seen:
            blocked.add(ident)
            findings.append(_finding("employees", employees.path, employees.sheet,
                                     row_number, "employee_id", "DUPLICATE_EMPLOYEE"))
        seen.add(ident)
        if row.get("termination_date") and row["termination_date"] < row["hire_date"]:
            blocked.add(ident)
            findings.append(_finding("employees", employees.path, employees.sheet,
                                     row_number, "termination_date", "INVALID_EMPLOYMENT_PERIOD"))
    if not employees.rows:
        global_block = True
        findings.append(Finding(
            code="EMPLOYEE_ROSTER_EMPTY", severity=Severity.ERROR,
            scope=Scope.RUN, message="No usable PTO employees in roster",
            source=employees.path.name,
        ))
    handoff = {
        "employees": employees.rows,
        "schedule_rows": [row for sheet in loaded["schedule"] for row in sheet.rows],
        "assignment_rows": [row for sheet in loaded["assignments"] for row in sheet.rows],
        "monthly_rows": [row for sheet in loaded.get("monthly_schedule", []) for row in sheet.rows],
        "attendance_rows": [row for sheet in loaded.get("attendance", []) for row in sheet.rows],
        "event_rows": [row for sheet in loaded.get("events", []) for row in sheet.rows],
    }
    roster = {x["employee_id"] for x in handoff["employees"] if isinstance(x.get("employee_id"), str)}
    for kind, rows in (("assignments", handoff["assignment_rows"]),
                       ("monthly_schedule", handoff["monthly_rows"]),
                       ("attendance", handoff["attendance_rows"]),
                       ("events", handoff["event_rows"])):
        for row in rows:
            if row["employee_id"] not in roster:
                findings.append(Finding(
                    code="UNKNOWN_EMPLOYEE_REFERENCE", severity=Severity.ERROR,
                    scope=Scope.ROW, message=f"{kind} references a person absent from the roster",
                ))
    return PTOInputBundle(handoff, sources, hashes, findings, blocked, global_block)
