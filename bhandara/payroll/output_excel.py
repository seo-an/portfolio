"""Write the confirmed dynamic Payroll output layout as one XLSX worksheet.

Only formats a validated register. It never fills missing calculations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .output import FILENAME, SCHEMA_VERSION, SHEET_NAME, PayrollOutputError


_GROUP_COLOR = {
    "직원정보": "29455B",
    "기본급": "29455B",
    "고정수당": "315A74",
    "초과근무수당": "315A74",
    "성과급": "315A74",
    "지급합계": "204A61",
    "공제": "58616D",
    "공제합계": "58616D",
    "실지급액": "204A61",
    "검토": "58616D",
}
_MONEY_FORMAT = '#,##0;[Red]-#,##0;0'


def _validate_result(result: Mapping[str, Any]) -> tuple[list[dict], list[dict]]:
    if not isinstance(result, Mapping):
        raise PayrollOutputError("result must be object")
    if (result.get("schema_version") != SCHEMA_VERSION
            or result.get("sheet_name") != SHEET_NAME
            or result.get("file_name") != FILENAME
            or result.get("approval_state") != "NOT_APPROVED"):
        raise PayrollOutputError("unsupported or approved payroll output contract")
    columns, rows = result.get("columns"), result.get("rows")
    if not isinstance(columns, list) or not columns or not isinstance(rows, list):
        raise PayrollOutputError("columns and rows required")
    keys = []
    for column in columns:
        if not isinstance(column, dict):
            raise PayrollOutputError("column must be object")
        for name in ("key", "group", "label"):
            value = column.get(name)
            if not isinstance(value, str) or not value.strip() or value[0] in ("=", "+", "-", "@"):
                raise PayrollOutputError(f"unsafe or missing column {name}")
        if column["group"] not in _GROUP_COLOR:
            raise PayrollOutputError("unknown column group")
        keys.append(column["key"])
    if len(set(keys)) != len(keys):
        raise PayrollOutputError("duplicate result columns")
    for row in rows:
        if not isinstance(row, dict) or set(row) - set(keys):
            raise PayrollOutputError("invalid output row")
        for key in keys:
            value = row.get(key)
            if value is not None and not isinstance(value, (str, int)):
                raise PayrollOutputError(f"invalid cell value for {key}")
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                raise PayrollOutputError(f"unsafe spreadsheet text in {key}")
    return columns, rows


def write_payroll_result_xlsx(result: Mapping[str, Any], path: str | Path) -> Path:
    """Write PAYROLL sheet with grouped headers, no overwrite and blank omissions."""
    columns, rows = _validate_result(result)
    target = Path(path)
    if target.name != FILENAME:
        raise PayrollOutputError(f"fixed output filename required: {FILENAME}")
    if target.exists():
        raise PayrollOutputError("output already exists; do not overwrite")
    if not target.parent.is_dir():
        raise PayrollOutputError("output parent does not exist")

    book = Workbook()
    try:
        sheet = book.active
        sheet.title = SHEET_NAME
        for index, column in enumerate(columns, start=1):
            sheet.cell(1, index, column["group"])
            sheet.cell(2, index, column["label"])
        for row_index, record in enumerate(rows, start=3):
            for index, column in enumerate(columns, start=1):
                value = record.get(column["key"])
                if value is not None:
                    sheet.cell(row_index, index, value)

        # Only adjacent columns from the same populated group share a header.
        start = 1
        while start <= len(columns):
            end = start
            group = columns[start - 1]["group"]
            while end < len(columns) and columns[end]["group"] == group:
                end += 1
            if end > start:
                sheet.merge_cells(start_row=1, start_column=start, end_row=1, end_column=end)
            start = end + 1

        sheet.row_dimensions[1].height = 26
        sheet.row_dimensions[2].height = 28
        border = Border(bottom=Side(style="hair", color="D9E1E7"))
        for index, column in enumerate(columns, start=1):
            for header_row in (1, 2):
                cell = sheet.cell(header_row, index)
                cell.fill = PatternFill("solid", fgColor=_GROUP_COLOR[column["group"]])
                cell.font = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            width = max(14, min(24, 7 + len(column["label"]) * 1.6))
            if column["key"] in {"employee_id", "employee_name"}:
                width = 18
            if column["key"] == "review_status":
                width = 24
            sheet.column_dimensions[get_column_letter(index)].width = width

        for row_index in range(3, 3 + len(rows)):
            sheet.row_dimensions[row_index].height = 22
            for index, column in enumerate(columns, start=1):
                cell = sheet.cell(row_index, index)
                cell.font = Font(name="맑은 고딕", size=10, color="1A303E")
                cell.border = border
                if column["key"] in {"employee_id", "employee_name", "review_status"}:
                    cell.alignment = Alignment(vertical="center", horizontal="left")
                else:
                    cell.number_format = _MONEY_FORMAT
                    cell.alignment = Alignment(vertical="center", horizontal="right")
                if column["key"] in {"gross_pay", "deduction_total", "net_pay"}:
                    cell.fill = PatternFill("solid", fgColor="EAF0F4")
                    cell.font = Font(name="맑은 고딕", size=10, bold=True, color="1A303E")
        name_columns = sum(1 for col in columns if col["key"] in {"employee_id", "employee_name"})
        sheet.freeze_panes = f"{get_column_letter(name_columns + 1)}3"
        if rows:
            sheet.auto_filter.ref = f"A2:{get_column_letter(len(columns))}{2 + len(rows)}"
        sheet.print_title_rows = "1:2"
        book.save(target)
    finally:
        book.close()
    return target
