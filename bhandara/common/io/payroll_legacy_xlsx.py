"""Reusable XLSX row readers and structural validation for Gearbox."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook


def validate_xlsx_headers(
    headers: list[str],
    *,
    path: Path | str | None = None,
) -> list[str]:
    """Validate generic XLSX header structure without applying domain rules."""
    label = f"{Path(path)}: " if path is not None else ""

    if any(not header for header in headers):
        raise ValueError(f"{label}blank header is not allowed")
    if len(headers) != len(set(headers)):
        raise ValueError(f"{label}duplicate headers are not allowed")

    return headers


def read_xlsx_rows_raw(path: Path | str) -> list[dict[str, Any]]:
    """Read XLSX rows without imposing generic header validation."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        values = sheet.iter_rows(values_only=True)
        try:
            header_row = next(values)
        except StopIteration:
            return []

        headers = [str(value).strip() if value is not None else "" for value in header_row]
        rows = []
        for values_row in values:
            if all(value in (None, "") for value in values_row):
                continue
            rows.append(dict(zip(headers, values_row)))
        return rows
    finally:
        workbook.close()


def read_xlsx_rows(path: Path | str) -> list[dict[str, Any]]:
    """Read XLSX rows with strict generic workbook/header validation."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        values = sheet.iter_rows(values_only=True)
        try:
            header_row = next(values)
        except StopIteration as exc:
            raise ValueError(f"{path}: workbook is empty") from exc

        headers = [str(value).strip() if value is not None else "" for value in header_row]
        validate_xlsx_headers(headers, path=path)

        rows = []
        for values_row in values:
            if all(value is None or (isinstance(value, str) and not value.strip()) for value in values_row):
                continue
            rows.append(dict(zip(headers, values_row)))
        return rows
    finally:
        workbook.close()
