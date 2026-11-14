"""Optional Worktime-only mapping for external time-based service providers.

EXTERNAL is a sheet in the already required common/id-map.xlsx, not another
input workbook. It is independent of Payroll Contracts: this module only
resolves reader/Worktime identities, not employment/tax classification.

The original ID_MAP sheet remains the employee-only identity contract. In
particular, external actors never become employees for PTO or employee payroll.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from python_calamine import CalamineWorkbook

from bhandara.common.io.input_layout import InputLayoutError, read_sheet


EXTERNAL_SHEET = "EXTERNAL"
EXTERNAL_COLUMNS = ("worker_id", "security_id")


def load_external_workers(
    id_map_path: Path,
    employee_identities: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, Any]]:
    """Read optional EXTERNAL identity rows and fail closed on collisions.

    No external sheet means there are no external Worktime participants.
    Any Worktime schedule/attendance referencing an unregistered worker fails.
    """
    with CalamineWorkbook.from_path(id_map_path) as book:
        has_sheet = EXTERNAL_SHEET in book.sheet_names
    if not has_sheet:
        return {}

    rows = read_sheet(
        id_map_path, EXTERNAL_COLUMNS, sheet_name=EXTERNAL_SHEET
    )
    employee_ids = set(employee_identities)
    employee_worker_ids = {
        values["worker_id"] for values in employee_identities.values()
    }
    security_seen = {
        values["security_id"] for values in employee_identities.values()
    }
    external: dict[str, dict[str, Any]] = {}
    for row in rows:
        line = row["_row_number"]
        worker = str(row.get("worker_id") or "").strip()
        security = str(row.get("security_id") or "").strip()
        if not worker or not security:
            raise InputLayoutError(
                f"id-map.xlsx EXTERNAL row {line}: worker_id and security_id required"
            )
        if worker in employee_ids or worker in employee_worker_ids or worker in external:
            raise InputLayoutError(
                f"id-map.xlsx EXTERNAL row {line}: worker_id duplicated or "
                "collides with employee identity"
            )
        if security in security_seen:
            raise InputLayoutError(
                f"id-map.xlsx EXTERNAL row {line}: duplicate security_id"
            )
        external[worker] = {
            "worker_id": worker,
            "security_id": security,
            "_row_number": line,
        }
        security_seen.add(security)
    return external


def resolve_worktime_actor(
    row: Mapping[str, Any],
    employees: Mapping[str, Mapping[str, str]],
    external: Mapping[str, Mapping[str, Any]],
    *,
    filename: str,
) -> tuple[str, str]:
    """Resolve one Excel row via employee_id XOR external worker_id.

    The canonical Worktime batch uses an `employee_id` key internally.
    For an external actor we use the registered worker_id as that source key,
    strictly as a Worktime alias, never as evidence of an employment contract.
    """
    line = row["_row_number"]
    employee_id = str(row.get("employee_id") or "").strip()
    worker_id = str(row.get("worker_id") or "").strip()

    if bool(employee_id) == bool(worker_id):
        raise InputLayoutError(
            f"{filename} row {line}: provide exactly one of "
            "employee_id (employee) or worker_id (external)"
        )
    if employee_id:
        if employee_id not in employees:
            raise InputLayoutError(
                f"{filename} row {line}: unknown employee_id"
            )
        return employee_id, employees[employee_id]["worker_id"]
    if worker_id not in external:
        raise InputLayoutError(
            f"{filename} row {line}: external worker_id not in "
            "id-map.xlsx EXTERNAL sheet"
        )
    return worker_id, worker_id
