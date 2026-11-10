"""Read and append Settlement Ledger XLSX rows at the file boundary."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from openpyxl import Workbook, load_workbook

try:
    from .settlement_ledger import validate_transaction
except ImportError:
    from settlement_ledger import validate_transaction


LEDGER_COLUMNS = [
    "transaction_id",
    "worker_id",
    "transaction_type",
    "origin_period",
    "origin_pay_item_code",
    "amount",
    "direction",
    "settlement_period",
    "settlement_batch_id",
    "related_transaction_id",
    "note",
]


class SettlementLedgerXlsxError(ValueError):
    pass


def _validate_headers(headers: list[Any]) -> None:
    normalized = [str(value).strip() if value is not None else "" for value in headers]
    if normalized != LEDGER_COLUMNS:
        raise SettlementLedgerXlsxError(
            "Settlement Ledger headers must exactly match the schema columns"
        )


def load_settlement_ledger_rows(path: str | Path) -> list[dict[str, Any]]:
    workbook = load_workbook(path, data_only=True)
    try:
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            raise SettlementLedgerXlsxError("Settlement Ledger workbook is empty")
        _validate_headers(list(rows[0]))
        result = []
        for values in rows[1:]:
            if all(value in (None, "") for value in values):
                continue
            row = dict(zip(LEDGER_COLUMNS, values))
            result.append(validate_transaction(row))
        ids = [row["transaction_id"] for row in result]
        if len(set(ids)) != len(ids):
            raise SettlementLedgerXlsxError(
                "Settlement Ledger transaction_id values must be unique"
            )
        return result
    finally:
        workbook.close()


def create_settlement_ledger(path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    try:
        sheet = workbook.active
        sheet.title = "Settlement Ledger"
        sheet.append(LEDGER_COLUMNS)
        workbook.save(target)
    finally:
        workbook.close()


def append_settlement_ledger_rows(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        raise SettlementLedgerXlsxError(
            "Settlement Ledger workbook does not exist"
        )

    existing = load_settlement_ledger_rows(target)
    existing_ids = {row["transaction_id"] for row in existing}
    normalized = [validate_transaction(dict(row)) for row in rows]
    new_ids = [row["transaction_id"] for row in normalized]
    if len(set(new_ids)) != len(new_ids):
        raise SettlementLedgerXlsxError(
            "append transaction_id values must be unique"
        )
    conflicts = existing_ids & set(new_ids)
    if conflicts:
        raise SettlementLedgerXlsxError(
            "transaction_id already exists: " + ", ".join(sorted(conflicts))
        )

    workbook = load_workbook(target)
    try:
        sheet = workbook.active
        _validate_headers([cell.value for cell in sheet[1]])
        for row in normalized:
            values = []
            for column in LEDGER_COLUMNS:
                value = row.get(column, "")
                if isinstance(value, Decimal):
                    value = str(value)
                values.append(value if value is not None else "")
            sheet.append(values)
        workbook.save(target)
    finally:
        workbook.close()
    return normalized
