"""Load Payroll XLSX rows without changing workbook semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gearbox.core.xlsx import read_xlsx_rows_raw

try:
    from .input_contracts import (
        read_headers,
        validate_compensation_headers,
        validate_payroll_input_headers,
    )
except ImportError:
    from input_contracts import (
        read_headers,
        validate_compensation_headers,
        validate_payroll_input_headers,
    )


def _read_rows(path: str | Path) -> list[dict[str, Any]]:
    return read_xlsx_rows_raw(path)


def load_compensation_rows(path: str | Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    headers = read_headers(path, "Employee compensation workbook")
    validate_compensation_headers(headers, registry)
    return _read_rows(path)


def load_payroll_input_rows(path: str | Path) -> list[dict[str, Any]]:
    headers = read_headers(path, "Monthly payroll input workbook")
    validate_payroll_input_headers(headers)
    return _read_rows(path)
