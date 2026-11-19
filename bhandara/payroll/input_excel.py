"""Strict readers for the seven independent Payroll Excel input roles.

No contract selection, payment approval, tax calculation, or file retention.
A selected role is required; an unselected role is never opened or inferred.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re
from typing import Any, Iterable, Mapping
from zipfile import BadZipFile

from openpyxl import load_workbook
from bhandara.common.io.xlsx_stream import XlsxStreamError, open_xlsx_rows
from bhandara.common.validation.headers import HeaderContractError, is_blank, parse_headers
from bhandara.common.utils.hashing import sha256_file


class PayrollInputError(ValueError):
    """Unsafe, incomplete or ambiguous workbook data. No partial result is returned."""


@dataclass(frozen=True)
class PayrollInputs:
    rows: dict[str, tuple[dict[str, Any], ...]]
    paths: dict[str, str]  # filenames only, never private absolute paths
    roles: tuple[str, ...]

    def for_role(self, role: str) -> tuple[dict[str, Any], ...]:
        return self.rows[role]


CONTRACT = Path(__file__).with_name("input-files.json")
ID_FIELDS = frozenset({
    "employee_id", "contract_id", "deduction_code", "allowance_id", "level",
    "rule_id", "bonus_id", "team_id", "project_id",
})
MONEY_FIELDS = frozenset({
    "contract_amount", "declared_base_amount", "daily_base_rate", "amount", "budget_amount",
})
DECIMAL_FIELDS = frozenset({
    "national_pension", "health_insurance", "longterm_care", "employment_insurance",
    "daily_rate_multiplier", "allocation_ratio",
})
INTEGER_FIELDS = frozenset({"installments_per_year", "minimum_minutes"})
DATE_FIELDS = frozenset({
    "calculation_period_from", "calculation_period_to", "payment_date",
    "effective_from", "effective_to",
})
OPTIONAL_CELLS = {
    "contracts": {"installments_per_year", "declared_base_amount"},
    "fixed_allowance_map": {"taxability_policy_ref"},
    "overtime_rules": {"qualifying_from", "qualifying_to"},
    "bonus_budget": {"team_id", "project_id"},
}
UNIQUE_KEYS = {
    "contracts": ("contract_id",),
    "allowance_assignments": ("contract_id", "allowance_id"),
    "fixed_allowance_map": ("allowance_id", "level"),
    "deduction_map": ("deduction_code",),
    "overtime_rules": ("rule_id",),
    "bonus_budget": ("bonus_id",),
    "bonus_allocation": ("bonus_id", "employee_id"),
}


def _fail(role: str, row_number: int, field: str, reason: str) -> None:
    # Never include employee IDs, source values or absolute paths in findings.
    raise PayrollInputError(f"{role}: row {row_number}, {field}: {reason}")


def _decimal(value: Any, role: str, number: int, field: str) -> Decimal:
    if isinstance(value, bool):
        _fail(role, number, field, "boolean is not numeric")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        _fail(role, number, field, "invalid decimal")
    if not result.is_finite() or result < 0:
        _fail(role, number, field, "nonnegative finite value required")
    if field in MONEY_FIELDS | INTEGER_FIELDS and result != result.to_integral_value():
        _fail(role, number, field, "whole number required")
    if field in {"allocation_ratio", "national_pension", "health_insurance",
                 "longterm_care", "employment_insurance"} and result > 1:
        _fail(role, number, field, "ratio must be 0..1")
    if field in {"daily_base_rate", "installments_per_year", "daily_rate_multiplier"} and result == 0:
        _fail(role, number, field, "positive number required")
    return result


def _date(value: Any, role: str, number: int, field: str) -> str:
    if isinstance(value, datetime):
        if value.time().isoformat() != "00:00:00":
            _fail(role, number, field, "date only, not date-time")
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        _fail(role, number, field, "ISO date YYYY-MM-DD required")
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        _fail(role, number, field, "invalid calendar date")


def _cell(value: Any, role: str, number: int, field: str) -> Any:
    if is_blank(value):
        return None
    if field in ID_FIELDS:
        if not isinstance(value, str):
            _fail(role, number, field, "ID must be Excel text (leading zeros preserved)")
        return value.strip()
    if field in DATE_FIELDS:
        return _date(value, role, number, field)
    if field in MONEY_FIELDS | INTEGER_FIELDS | DECIMAL_FIELDS:
        return _decimal(value, role, number, field)
    return str(value).strip()


def _validate_role_row(role: str, number: int, row: dict[str, Any]) -> None:
    if role == "contracts":
        basis, kind = row["pay_basis"], row["amount_type"]
        if basis not in {"ANNUAL", "MONTHLY", "WEEKLY"}:
            _fail(role, number, "pay_basis", "ANNUAL/MONTHLY/WEEKLY only")
        if kind not in {"BASE", "TOTAL"}:
            _fail(role, number, "amount_type", "BASE/TOTAL only")
        if basis == "ANNUAL" and row["installments_per_year"] is None:
            _fail(role, number, "installments_per_year", "annual installments required")
        if kind == "TOTAL" and row["declared_base_amount"] is None:
            _fail(role, number, "declared_base_amount", "TOTAL base required")
        if row["calculation_period_from"] > row["calculation_period_to"]:
            _fail(role, number, "calculation_period", "reversed date range")
    elif role == "fixed_allowance_map":
        if row["payroll_taxability"] not in {"TAXABLE", "NON_TAXABLE", "REVIEW"}:
            _fail(role, number, "payroll_taxability", "invalid taxability candidate")
    elif role == "deduction_map":
        if row["effective_from"] > row["effective_to"]:
            _fail(role, number, "effective_period", "reversed date range")
    elif role == "bonus_budget":
        if (row["team_id"] is None) == (row["project_id"] is None):
            _fail(role, number, "team_id/project_id", "exactly one scope ID required")


def _validate_unique(role: str, indexed: list[tuple[int, dict[str, Any]]]) -> None:
    key_fields = UNIQUE_KEYS[role]
    keys: set[tuple[Any, ...]] = set()
    for number, row in indexed:
        key = tuple(row[name] for name in key_fields)
        if key in keys:
            _fail(role, number, "+".join(key_fields), "duplicate key")
        keys.add(key)


def _validate_periods(indexed: list[tuple[int, dict[str, Any]]]) -> None:
    # These are declared calculation periods, not proof of contract legal validity.
    by_worker: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for number, row in indexed:
        by_worker[row["employee_id"]].append((
            row["calculation_period_from"], row["calculation_period_to"], number,
        ))
    for periods in by_worker.values():
        ordered = sorted(periods)
        for (_, previous_end, _), (start, _, number) in zip(ordered, ordered[1:]):
            if start <= previous_end:
                _fail("contracts", number, "calculation_period", "overlapping declared periods")


def _read_one(path: Path, role: str, spec: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        raise PayrollInputError(f"{role}: missing workbook {path.name}")
    try:
        source_digest = sha256_file(path)
        book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        try:
            if book.sheetnames != [spec["sheet"]]:
                raise PayrollInputError(f"{role}: expected exactly one sheet named {spec['sheet']}")
        finally:
            book.close()
        with open_xlsx_rows(path, sheet_name=spec["sheet"], data_only=False, keep_links=False) as source:
            headers = parse_headers([cell.value for cell in source.header_cells], spec["columns"])
            indexed: list[tuple[int, dict[str, Any]]] = []
            for number, cells in enumerate(source.rows, start=2):
                if not any(not is_blank(cell.value) for cell in cells):
                    continue
                row: dict[str, Any] = {}
                for field, position in zip(headers.required, headers.positions):
                    cell = cells[position] if position < len(cells) else None
                    if cell is not None and cell.data_type == "f":
                        _fail(role, number, field, "formula unsupported")
                    value = _cell(cell.value if cell is not None else None, role, number, field)
                    if value is None and field not in OPTIONAL_CELLS.get(role, set()):
                        _fail(role, number, field, "required value missing")
                    row[field] = value
                row["_row_number"] = number
                _validate_role_row(role, number, row)
                indexed.append((number, row))
            _validate_unique(role, indexed)
            if role == "contracts":
                if not indexed:
                    raise PayrollInputError("contracts: at least one contract required")
                _validate_periods(indexed)
            if sha256_file(path) != source_digest:
                raise PayrollInputError(f"{role}: workbook changed during read")
            return tuple(row for _, row in indexed)
    except PayrollInputError:
        raise
    except HeaderContractError as exc:
        raise PayrollInputError(f"{role}: header: {exc}") from exc
    except XlsxStreamError as exc:
        raise PayrollInputError(f"{role}: {exc}") from exc
    except (OSError, BadZipFile, ValueError, TypeError) as exc:
        raise PayrollInputError(f"{role}: invalid workbook/header ({type(exc).__name__})") from exc


def _join_checks(data: Mapping[str, tuple[dict[str, Any], ...]]) -> None:
    def check(source: str, field: str, target: str, target_key: str) -> None:
        if source not in data or target not in data:
            return
        valid = {row[target_key] for row in data[target]}
        for row in data[source]:
            if row[field] not in valid:
                _fail(source, row["_row_number"], field, f"unmatched {target} reference")

    check("allowance_assignments", "contract_id", "contracts", "contract_id")
    check("contracts", "deduction_code", "deduction_map", "deduction_code")
    check("bonus_allocation", "bonus_id", "bonus_budget", "bonus_id")
    check("bonus_allocation", "employee_id", "contracts", "employee_id")
    if "allowance_assignments" in data and "fixed_allowance_map" in data:
        keys = {(x["allowance_id"], x["level"]) for x in data["fixed_allowance_map"]}
        for row in data["allowance_assignments"]:
            if (row["allowance_id"], row["level"]) not in keys:
                _fail("allowance_assignments", row["_row_number"], "allowance_id+level", "mapping not found")
    if "bonus_budget" in data and "bonus_allocation" in data:
        sums: dict[str, Decimal] = defaultdict(Decimal)
        for row in data["bonus_allocation"]:
            sums[row["bonus_id"]] += row["allocation_ratio"]
        for row in data["bonus_budget"]:
            if sums[row["bonus_id"]] != 1:
                _fail("bonus_budget", row["_row_number"], "bonus_id", "allocation ratio sum must equal 1")


def read_payroll_inputs(input_root: str | Path, *, roles: Iterable[str] | None = None) -> PayrollInputs:
    """Read selected roles from input_root/payroll; never auto-run missing steps.

    Returned rows can be passed to pure Payroll Core. Contract period selection,
    rate effective-date applicability and bonus membership require later approval.
    """
    spec = json.loads(CONTRACT.read_text(encoding="utf-8"))
    books: Mapping[str, dict[str, Any]] = spec["workbooks"]
    selected = tuple(books) if roles is None else tuple(roles)
    if not selected or len(set(selected)) != len(selected) or any(role not in books for role in selected):
        raise PayrollInputError("roles: nonempty unique known role names required")
    directory = Path(input_root) / spec["input_directory"]
    data = {role: _read_one(directory / books[role]["filename"], role, books[role])
            for role in selected}
    _join_checks(data)
    return PayrollInputs(rows=data, paths={r: books[r]["filename"] for r in selected}, roles=selected)
