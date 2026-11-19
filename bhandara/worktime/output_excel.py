"""Single-sheet Worktime factual Excel, also readable by an independent Tool.

The worksheet uses exactly the same fields as output.build_worktime_result.
There is no separate human/payroll view and no status/approval columns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from bhandara.common.io.input_layout import read_sheet, InputLayoutError
from .output import OUTPUT_FIELDS, WorktimeOutputError, _key, _minutes, _text


SHEET_NAME = "WORKTIME"


def write_worktime_xlsx(result: dict[str, Any], path: str | Path) -> Path:
    """Write a new workbook. Existing files are never overwritten."""
    if result.get("schema_version") != "0.1" or not isinstance(result.get("rows"), list):
        raise WorktimeOutputError("unsupported Worktime result contract")
    target = Path(path)
    if target.suffix.lower() != ".xlsx":
        raise WorktimeOutputError("Worktime result must be XLSX")
    if target.exists():
        raise WorktimeOutputError("output already exists; choose a new filename")
    if not target.parent.is_dir():
        raise WorktimeOutputError("output parent directory does not exist")
    book = Workbook()
    try:
        sheet = book.active
        sheet.title = SHEET_NAME
        sheet.append(OUTPUT_FIELDS)
        for item in result["rows"]:
            if set(item) != set(OUTPUT_FIELDS):
                raise WorktimeOutputError("unexpected or missing output columns")
            sheet.append([item[field] for field in OUTPUT_FIELDS])
        sheet.freeze_panes = "C2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="26445A")
            cell.alignment = Alignment(horizontal="center")
        widths = (16, 17, 20, 18, 16, 21, 22, 20, 18, 22)
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        book.save(target)
    finally:
        book.close()
    return target


def _numeric(value: Any, name: str, *, signed: bool) -> int | float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise WorktimeOutputError(f"{name}: numeric minutes required")
    if value != value or value in (float("inf"), float("-inf")):
        raise WorktimeOutputError(f"{name}: finite minutes required")
    if not signed:
        return _minutes(value, name)
    return value


def read_worktime_xlsx(path: str | Path) -> list[dict[str, Any]]:
    """Strict reader for the exact one-sheet, ten-column factual contract."""
    try:
        rows = read_sheet(Path(path), OUTPUT_FIELDS, sheet_name=SHEET_NAME)
    except (InputLayoutError, OSError) as exc:
        raise WorktimeOutputError(str(exc)) from exc
    result = []
    seen = set()
    for row in rows:
        if set(row) - set(OUTPUT_FIELDS) - {"_row_number"}:
            raise WorktimeOutputError("unexpected columns in WORKTIME")
        ident = _key(row, "WORKTIME")
        if ident in seen:
            raise WorktimeOutputError("duplicate employee/date in WORKTIME")
        seen.add(ident)
        result.append({
            "employee_id": ident[0], "work_date": ident[1],
            "schedule_id": _text(row.get("schedule_id")),
            "scheduled_min": _numeric(row.get("scheduled_min"), "scheduled_min", signed=False),
            "actual_min": _numeric(row.get("actual_min"), "actual_min", signed=False),
            "clock_in_delta_min": _numeric(row.get("clock_in_delta_min"), "clock_in_delta_min", signed=True),
            "clock_out_delta_min": _numeric(row.get("clock_out_delta_min"), "clock_out_delta_min", signed=True),
            "attendance_type": _text(row.get("attendance_type")),
            "leave_type": _text(row.get("leave_type")),
            "leave_request_id": _text(row.get("leave_request_id")),
        })
    return result
