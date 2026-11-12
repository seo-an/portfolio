"""Stream XLSX worksheet cells without deciding calculator validation policy.

Callers retain control over header rules, formula handling, row rejection,
source hashes, and business-specific conversion. The workbook closes when the
context exits, including when a caller raises an exception.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from openpyxl import load_workbook


class XlsxStreamError(ValueError):
    """An explicitly requested sheet or header row is unavailable."""


@dataclass(frozen=True, slots=True)
class XlsxSheetRows:
    workbook: Any
    sheet: Any
    header_cells: tuple[Any, ...]
    rows: Iterator[tuple[Any, ...]]


@contextmanager
def open_xlsx_rows(
    path: str | Path,
    *,
    sheet_name: str | None = None,
    header_row: int = 1,
    data_only: bool = False,
    keep_links: bool = True,
) -> Iterator[XlsxSheetRows]:
    """Open one selected XLSX worksheet and yield actual cells, not values.

    No headers are normalized here, and formula cells remain available when
    data_only=False. These decisions belong to each consuming contract.
    """
    if type(header_row) is not int or header_row < 1:
        raise XlsxStreamError("header_row must be a positive integer")

    workbook = load_workbook(
        path, read_only=True, data_only=data_only, keep_links=keep_links,
    )
    try:
        if sheet_name is not None and sheet_name not in workbook.sheetnames:
            raise XlsxStreamError(f"worksheet not found: {sheet_name}")
        sheet = workbook[sheet_name] if sheet_name is not None else workbook.active
        rows = sheet.iter_rows(min_row=header_row, values_only=False)
        header_cells = next(rows, None)
        if header_cells is None:
            raise XlsxStreamError("XLSX source has no header row")
        yield XlsxSheetRows(workbook, sheet, header_cells, rows)
    finally:
        workbook.close()
