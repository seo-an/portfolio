"""Generic, local-only CSV/XLSX/JSON row readers for Bhandara calculators.

Only file structure, path containment, and primitive row/column contracts live
here. Company-specific source aliases and business meanings are supplied by
the caller. Preserve original physical row numbers for review and lineage.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

from .xlsx_stream import XlsxStreamError, open_xlsx_rows


class TabularInputError(ValueError):
    """A generic structural input contract was violated."""


MISSING = object()
SUPPORTED_FORMATS = frozenset(("csv", "json", "xlsx"))


def lookup_field(row: Mapping[str, Any], path: str) -> Any:
    """Read exact header names first; otherwise use nested dotted paths."""
    if path in row:
        return row[path]
    current: Any = row
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return MISSING
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            return MISSING
    return current


def is_blank_value(value: Any) -> bool:
    """Missing, None, empty and whitespace-only strings are blank; zero is not."""
    return value is MISSING or value is None or (
        isinstance(value, str) and not value.strip()
    )


def column_names(values: list[Any]) -> list[str]:
    """Accept non-empty, unique header cells; normalize surrounding spaces."""
    names = [str(item).strip() if item is not None else "" for item in values]
    if not names or any(not name for name in names) or len(set(names)) != len(names):
        raise TabularInputError("source headers must be unique and non-empty")
    return names


def resolve_source_path(root: Path, name: Any) -> Path:
    """Never read a named source outside its declared input root."""
    if not isinstance(name, str) or not name.strip():
        raise TabularInputError("source.path is required")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise TabularInputError("source path must stay within input directory")
    if not target.is_file():
        raise TabularInputError(f"source file not found: {name}")
    return target


def read_csv_rows(path: Path, spec: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """Return (physical_start_line, record), retaining quoted multiline cells."""
    encoding = str(spec.get("encoding", "utf-8-sig"))
    delimiter = str(spec.get("delimiter", ","))
    if len(delimiter) != 1:
        raise TabularInputError("CSV delimiter must be a single character")
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            columns = column_names(next(reader))
        except StopIteration as exc:
            raise TabularInputError("CSV source is empty") from exc
        rows: list[tuple[int, dict[str, Any]]] = []
        previous_end_line = reader.line_num
        for values in reader:
            # Preserve the original parser's physical line accounting.
            number = previous_end_line + 1
            previous_end_line = reader.line_num
            if not values:  # Only a physically empty CSV line is omitted.
                continue
            if len(values) != len(columns):
                raise TabularInputError(f"CSV row {number}: column count mismatch")
            rows.append((number, dict(zip(columns, values))))
        return rows


def read_xlsx_rows(path: Path, spec: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """Read an explicitly selected worksheet/header row without editing cells."""
    header_row = spec.get("header_row", 1)
    if type(header_row) is not int or header_row < 1:
        raise TabularInputError("header_row must be a positive integer")
    try:
        # Retain the original data_only=True contract for Payroll source mapping.
        # Other consumers can reject formulas by using data_only=False instead.
        with open_xlsx_rows(
            path, sheet_name=spec.get("sheet"), header_row=header_row,
            data_only=True,
        ) as opened:
            columns = column_names([cell.value for cell in opened.header_cells])
            rows: list[tuple[int, dict[str, Any]]] = []
            for number, cells in enumerate(opened.rows, start=header_row + 1):
                values = [cell.value for cell in cells]
                if all(is_blank_value(value) for value in values):
                    continue
                if any(not is_blank_value(value) for value in values[len(columns):]):
                    raise TabularInputError(f"XLSX row {number}: unexpected extra columns")
                rows.append((number, dict(zip(columns, values))))
            return rows
    except XlsxStreamError as exc:
        raise TabularInputError(str(exc)) from exc

def read_json_rows(path: Path, spec: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """Select optional records_path; reject non-object array elements."""
    with path.open("r", encoding=str(spec.get("encoding", "utf-8"))) as handle:
        value = json.load(handle)
    records_path = spec.get("records_path")
    if records_path:
        value = lookup_field(value, str(records_path)) if isinstance(value, Mapping) else MISSING
    if not isinstance(value, list):
        raise TabularInputError("JSON rows must be a list or records_path must select a list")
    rows: list[tuple[int, dict[str, Any]]] = []
    for number, row in enumerate(value, start=1):
        if not isinstance(row, Mapping):
            raise TabularInputError(f"JSON row {number}: object required")
        rows.append((number, dict(row)))
    return rows
