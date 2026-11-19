"""Common PERSON MAP reader for security-system identity reconciliation.

Each PERSON MAP row means one employee x one security vendor. Additional columns
are intentionally ignored. Legacy ID_MAP reading remains unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .input_layout import InputLayoutError, read_sheet, role


PERSON_SHEET = "PERSON MAP"
DEPARTMENT_SHEET = "DEPARTMENT MAP"
AREA_SHEET = "AREA Map"
PERSON_COLUMNS = (
    "employee_id", "name", "security_department_id", "security_id",
    "worker_id", "payroll_id", "security_person_id", "main_area",
)
DEPARTMENT_COLUMNS = ("department", "security_department_id")
AREA_COLUMNS = ("area", "security_area_id")

VENDOR_NAMES = {
    "CAPS": "CAPS",
    "SECOM": "SECOM",
    "KT_TELECOP": "KT_TELECOP",
    "TELECOP": "KT_TELECOP",
    "KTTELECOP": "KT_TELECOP",
}


def _text(value: Any) -> str:
    """Preserve string IDs (including leading zeros), normalize Excel integers."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()


def _vendor(value: Any) -> str:
    raw = _text(value).upper().replace("-", "_").replace(" ", "_")
    return VENDOR_NAMES.get(raw, "")


def _issue(sheet: str, row: int, code: str) -> dict[str, Any]:
    # Do not put names, personal IDs, or source cell contents into diagnostics.
    return {"sheet": sheet, "row_number": row, "code": code}


def _reference_map(
    path: Path, *, sheet_name: str, key_field: str, value_field: str,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    rows = read_sheet(path, (value_field, key_field), sheet_name=sheet_name)
    mapping: dict[str, str] = {}
    issues: list[dict[str, Any]] = []
    for row in rows:
        key = _text(row.get(key_field))
        value = _text(row.get(value_field))
        if not key or not value:
            issues.append(_issue(sheet_name, row["_row_number"], "INCOMPLETE_REFERENCE_ROW"))
            continue
        if key in mapping and mapping[key] != value:
            raise InputLayoutError(
                f"{sheet_name} row {row['_row_number']}: conflicting reference key"
            )
        if key in mapping:
            raise InputLayoutError(
                f"{sheet_name} row {row['_row_number']}: duplicate reference key"
            )
        mapping[key] = value
    return mapping, issues


def read_security_person_map(path: str | Path, *, vendor: str) -> dict[str, Any]:
    """Validate one workbook, then select identities for the requested vendor.

    The vendor has to be explicit; no selection by person name or file name.
    A repeated employee_id is valid across different vendors only when stable
    employee/worker/payroll identifiers agree. Duplicated employee x vendor or
    duplicated vendor/department/person keys always fail closed.
    Missing optional vendor-specific identifiers are reported, not invented.
    """
    vendor_key = _vendor(vendor)
    if not vendor_key:
        raise InputLayoutError("unsupported security vendor")
    path = Path(path)
    rows = read_sheet(path, PERSON_COLUMNS, sheet_name=PERSON_SHEET)
    departments, dept_issues = _reference_map(
        path, sheet_name=DEPARTMENT_SHEET,
        key_field="security_department_id", value_field="department",
    )
    areas, area_issues = _reference_map(
        path, sheet_name=AREA_SHEET,
        key_field="security_area_id", value_field="area",
    )
    issues = dept_issues + area_issues
    stable: dict[str, dict[str, str]] = {}
    worker_owners: dict[str, str] = {}
    payroll_owners: dict[str, str] = {}
    vendor_person: set[tuple[str, str]] = set()
    raw_keys: set[tuple[str, str, str]] = set()
    identities: list[dict[str, str]] = []

    for row in rows:
        number = row["_row_number"]
        record = {key: _text(row.get(key)) for key in PERSON_COLUMNS}
        employee = record["employee_id"]
        worker = record["worker_id"]
        payroll = record["payroll_id"]
        code = _vendor(record["security_id"])
        if not employee or not worker:
            raise InputLayoutError(
                f"{PERSON_SHEET} row {number}: employee_id and worker_id required"
            )
        if not code:
            raise InputLayoutError(
                f"{PERSON_SHEET} row {number}: unsupported security_id (vendor)"
            )
        old = stable.get(employee)
        if old and (
            old["worker_id"] != worker
            or (old["payroll_id"] and payroll and old["payroll_id"] != payroll)
            or (old["name"] and record["name"] and old["name"] != record["name"])
        ):
            raise InputLayoutError(
                f"{PERSON_SHEET} row {number}: same employee has conflicting identities"
            )
        if old:
            if not old["payroll_id"] and payroll:
                old["payroll_id"] = payroll
            if not old["name"] and record["name"]:
                old["name"] = record["name"]
        else:
            stable[employee] = {
                "employee_id": employee, "worker_id": worker,
                "payroll_id": payroll, "name": record["name"],
            }
        if worker in worker_owners and worker_owners[worker] != employee:
            raise InputLayoutError(
                f"{PERSON_SHEET} row {number}: worker_id belongs to another employee"
            )
        worker_owners[worker] = employee
        if payroll:
            if payroll in payroll_owners and payroll_owners[payroll] != employee:
                raise InputLayoutError(
                    f"{PERSON_SHEET} row {number}: payroll_id belongs to another employee"
                )
            payroll_owners[payroll] = employee
        employee_vendor_key = (employee, code)
        if employee_vendor_key in vendor_person:
            raise InputLayoutError(
                f"{PERSON_SHEET} row {number}: duplicate employee and security vendor"
            )
        vendor_person.add(employee_vendor_key)
        dept_id = record["security_department_id"]
        person_id = record["security_person_id"]
        if dept_id and person_id:
            raw_key = (code, dept_id, person_id)
            if raw_key in raw_keys:
                raise InputLayoutError(
                    f"{PERSON_SHEET} row {number}: duplicate vendor/department/person key"
                )
            raw_keys.add(raw_key)
        elif dept_id or person_id:
            issues.append(_issue(PERSON_SHEET, number, "INCOMPLETE_SECURITY_PERSON_KEY"))
        if record["main_area"] and record["main_area"] not in areas:
            issues.append(_issue(PERSON_SHEET, number, "MAIN_AREA_UNMAPPED"))

        if code != vendor_key:
            continue
        if not dept_id or not person_id:
            issues.append(_issue(PERSON_SHEET, number, "SECURITY_PERSON_KEY_MISSING"))
            continue
        if dept_id not in departments:
            issues.append(_issue(PERSON_SHEET, number, "SECURITY_DEPARTMENT_UNMAPPED"))
            continue
        identities.append({
            "department": departments[dept_id],
            "employee_number": person_id,
            "employee_id": employee,
            "worker_id": worker,
            "name": record["name"],
        })

    if not rows:
        raise InputLayoutError(f"{PERSON_SHEET}: no identity rows")
    if not any(_vendor(row.get("security_id")) == vendor_key for row in rows):
        raise InputLayoutError(f"{PERSON_SHEET}: no rows for selected security vendor")
    return {
        "vendor": vendor_key,
        "identities": identities,
        "issues": issues,
        "area_map": areas,
        "employee_count": len(stable),
    }


def read_security_person_map_from_root(
    root: str | Path, *, vendor: str, overrides: dict | None = None,
) -> dict[str, Any]:
    """Resolve existing Common role path; do not create another Worktime map."""
    path = role(Path(root), "common", "identity", overrides)
    return read_security_person_map(path, vendor=vendor)
