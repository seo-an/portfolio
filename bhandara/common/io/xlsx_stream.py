"""Calamine-backed spreadsheet values with fail-closed formula validation.

This module preserves the existing open_xlsx_rows cell interface for public
Bhandara callers. Values come from python-calamine. Strict XLSX/XLSM inputs
continue to reject formula cells using openpyxl for *metadata only*.

python-calamine 0.9.1 exposes values, not formula expressions, so formulas in
binary XLS/XLSB/ODS cannot be verified by this strict public calculator path.
Such formats may be read in explicitly data-only contexts (e.g. a private
source-normalizer), but must not silently bypass a formula-rejecting contract.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterator
from zipfile import BadZipFile

from openpyxl.utils.datetime import WINDOWS_EPOCH
from python_calamine import CalamineError

from openpyxl import load_workbook
from python_calamine import CalamineWorkbook


class XlsxStreamError(ValueError):
    """An explicitly requested sheet, header, or validation path is unavailable."""


@dataclass(frozen=True, slots=True)
class _ReadCell:
    value: Any
    data_type: str = "n"


@dataclass(frozen=True, slots=True)
class _BookEpoch:
    epoch: Any


@dataclass(frozen=True, slots=True)
class _SheetTitle:
    title: str


@dataclass(frozen=True, slots=True)
class XlsxSheetRows:
    workbook: Any
    sheet: Any
    header_cells: tuple[_ReadCell, ...]
    rows: Iterator[tuple[_ReadCell, ...]]


def _normalize_value(value: Any) -> Any:
    """Restore openpyxl-like empty/date values for existing input contracts."""
    if value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, time.min)
    return value


def _formula_locations(path: Path, sheet_name: str, *,
                       keep_links: bool) -> tuple[set[tuple[int, int]], Any]:
    """Inspect XLSX formula metadata; never treat a cached formula as a fact."""
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise XlsxStreamError(
            "strict formula validation is unavailable for this spreadsheet format"
        )
    workbook = load_workbook(
        path, read_only=True, data_only=False, keep_links=keep_links,
    )
    try:
        sheet = workbook[sheet_name]
        formulas = {
            (cell.row, cell.column)
            for row in sheet.iter_rows()
            for cell in row
            if cell.data_type == "f"
        }
        return formulas, workbook.epoch
    finally:
        workbook.close()


def _cells(rows: list[list[Any]], first: int,
           formulas: set[tuple[int, int]]) -> Iterator[tuple[_ReadCell, ...]]:
    for row_number, values in enumerate(rows, start=first):
        yield tuple(
            _ReadCell(
                ("__UNTRUSTED_FORMULA__" if value in (None, "")
                 else _normalize_value(value))
                if (row_number, column) in formulas else _normalize_value(value),
                "f" if (row_number, column) in formulas else "n",
            )
            for column, value in enumerate(values, start=1)
        )


@contextmanager
def open_xlsx_rows(
    path: str | Path,
    *,
    sheet_name: str | None = None,
    header_row: int = 1,
    data_only: bool = False,
    keep_links: bool = True,
) -> Iterator[XlsxSheetRows]:
    """Read spreadsheet values while preserving strict XLSX input safeguards.

    Calamine keeps the source's top/left blank area with skip_empty_area=False.
    Row numbering is therefore physical rather than position inside the data
    rectangle. Neither formulas nor external references are evaluated.
    """
    if type(header_row) is not int or header_row < 1:
        raise XlsxStreamError("header_row must be a positive integer")
    target = Path(path)
    if not data_only and target.suffix.lower() not in (".xlsx", ".xlsm"):
        raise XlsxStreamError(
            "strict formula validation is unavailable for this spreadsheet format"
        )
    try:
        workbook = CalamineWorkbook.from_path(target)
    except CalamineError as exc:
        if target.suffix.lower() in (".xlsx", ".xlsm"):
            raise BadZipFile(str(exc)) from exc
        raise XlsxStreamError("could not read spreadsheet") from exc
    try:
        if sheet_name is not None and sheet_name not in workbook.sheet_names:
            raise XlsxStreamError(f"worksheet not found: {sheet_name}")
        if not workbook.sheet_names:
            raise XlsxStreamError("spreadsheet has no worksheets")
        selected = sheet_name or workbook.sheet_names[0]
        sheet = workbook.get_sheet_by_name(selected)
        values = sheet.to_python(skip_empty_area=False)
        formulas, epoch = (set(), WINDOWS_EPOCH) if data_only else _formula_locations(
            target, selected, keep_links=keep_links,
        )
        if len(values) < header_row:
            raise XlsxStreamError("XLSX source has no header row")
        iterator = _cells(values[header_row-1:], header_row, formulas)
        header_cells = next(iterator, None)
        if header_cells is None:
            raise XlsxStreamError("XLSX source has no header row")
        if any(cell.data_type == "f" for cell in header_cells):
            raise XlsxStreamError("formula in header is unsupported")
        yield XlsxSheetRows(_BookEpoch(epoch), _SheetTitle(selected), header_cells, iterator)
    finally:
        workbook.close()
