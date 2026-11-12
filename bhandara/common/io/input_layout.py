"""Explicit, shared local input layout for standalone Bhandara calculators.

No fuzzy discovery, guessing by filename, network calls or implicit sample
fallbacks. User-provided overrides are optional and versioned module contracts
remain authoritative for actual sheet/column validation.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable, Mapping

from openpyxl import load_workbook


class InputLayoutError(ValueError):
    pass


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = ROOT / "data" / "input"
ROLE_PATHS = {
    "common": {
        "employees": "common/employee.xlsx",
        "identity": "common/id-map.xlsx",
    },
    "pto": {
        "schedule": "pto/work-schedule.xlsx",
        "assignments": "pto/work-schedule-assignment.xlsx",
        "events": "pto/employee-events.xlsx",
    },
    "worktime": {
        "schedule": "worktime/work-schedule.xlsx",
        "attendance": "worktime/attendance.xlsx",
    },
    "payroll": {
        "contracts": "payroll/pay-contract.xlsx",
        "contract_components": "payroll/pay-contract-components.xlsx",
        "service_contracts": "payroll/service-contracts.xlsx",
        "service_records": "payroll/service-work-records.xlsx",
        "compensation": "payroll/compensation.xlsx",
        "payroll_input": "payroll/payroll-input.xlsx",
        "company_policy": "payroll/company-policy.json",
        "worktime_result": "payroll/worktime-result.json",
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
    if module != "common":
        manifest = ROOT / f"{module}-calculator" / "module.json"
        if manifest.is_file():
            with manifest.open("r", encoding="utf-8") as stream:
                module_contract = json.load(stream)
            declared = module_contract.get("shared_excel_input", {}).get("roles", {})
            if key in declared:
                default = declared[key]
    filename = override.get(key, default)
    return choose_path(root, filename)


def read_sheet(path: Path, required: Iterable[str], *,
               sheet_name: str | None = None) -> list[dict[str, Any]]:
    """Strict workbook parse, preserving row numbers and rejecting bad headers.

    An optional extra column such as case_id is deliberately ignored by the
    consumer, while unknown columns remain visible for source lineage.
    """
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        if sheet_name is not None and sheet_name not in book.sheetnames:
            raise InputLayoutError(f"{path.name}: missing sheet {sheet_name}")
        sheet = book[sheet_name] if sheet_name else book.active
        iterator = sheet.iter_rows(values_only=False)
        try:
            header_cells = next(iterator)
        except StopIteration as exc:
            raise InputLayoutError(f"{path.name}: workbook has no header") from exc
        headers = [str(c.value).strip() if c.value is not None else "" for c in header_cells]
        if not headers or any(not h for h in headers) or len(headers) != len(set(headers)):
            raise InputLayoutError(f"{path.name}: headers must be unique and nonempty")
        missing = set(required) - set(headers)
        if missing:
            raise InputLayoutError(f"{path.name}: missing columns {sorted(missing)}")
        result = []
        for number, cells in enumerate(iterator, start=2):
            if all(c.value is None for c in cells):
                continue
            if any(c.data_type == "f" for c in cells):
                raise InputLayoutError(f"{path.name}: formula at row {number} is unsupported")
            item = dict(zip(headers, (c.value for c in cells)))
            item["_row_number"] = number
            result.append(item)
        return result
    finally:
        book.close()


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


def write_auto_config(
    input_root: Path,
    name: str,
    payload: Any,
    *,
    generated_dir: Path | None = None,
) -> Path:
    """Persist generated inputs outside source data and (optionally) read-only trees.

    The CLI passes a writable runtime config directory alongside --output-dir.
    Keeping the default only preserves callers that already manage a writable
    local bhandara/data directory; it must never be used by a read-only sample.
    """
    if "/" in name or name.startswith("."):
        raise InputLayoutError("invalid generated config name")
    base = (
        Path(generated_dir).resolve()
        if generated_dir is not None
        else input_root.resolve().parent / "config"
    )
    base.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    output = base / f"{Path(name).stem}-{fingerprint}.json"
    # Same content produces the same path; changed sources/configs create a
    # separately traceable auto-config without overwriting prior run settings.
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        if old != payload:
            raise InputLayoutError(
                f"Generated config differs from existing {output}; use a new period "
                "or remove the old generated config explicitly."
            )
    else:
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return output


def next_result_dir(input_root: Path, module_id: str) -> Path:
    """Choose a new output directory without overwriting an earlier run."""
    if module_id not in ("worktime-calculator", "payroll-calculator"):
        raise InputLayoutError("unsupported calculator output directory")
    base = input_root.resolve().parent / "output"
    default = base / module_id
    if not default.exists():
        return default
    for index in range(1, 10000):
        candidate = base / f"{module_id}-{index:03d}"
        if not candidate.exists():
            return candidate
    raise InputLayoutError("too many output versions; archive old runs")
