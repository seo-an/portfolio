"""Resolve balances and payroll effects from append-only settlement transactions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable


class SettlementLedgerError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"[payroll-calculator] Settlement ledger validation failed: {message}")


DIRECTIONS = {"지급", "공제"}
TRANSACTION_TYPES = {"rounding_carry", "advance", "retroactive_pay", "retroactive_deduction", "prior_period_adjustment", "rounding_settlement"}


def _amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SettlementLedgerError("amount must be decimal-compatible") from exc
    if amount <= 0:
        raise SettlementLedgerError("amount must be greater than zero")
    return amount


def validate_transaction(row: dict[str, Any]) -> dict[str, Any]:
    required = {"transaction_id", "worker_id", "transaction_type", "origin_period", "amount", "direction"}
    missing = [field for field in required if not str(row.get(field, "")).strip()]
    if missing:
        raise SettlementLedgerError("missing required fields: " + ", ".join(sorted(missing)))
    if row["direction"] not in DIRECTIONS:
        raise SettlementLedgerError(f"invalid direction: {row['direction']}")
    if row["transaction_type"] not in TRANSACTION_TYPES:
        raise SettlementLedgerError(f"invalid transaction_type: {row['transaction_type']}")
    normalized = dict(row)
    normalized["amount"] = _amount(row["amount"])
    return normalized


def _validated_index(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    normalized = [validate_transaction(row) for row in rows]
    by_id = {row["transaction_id"]: row for row in normalized}
    if len(by_id) != len(normalized):
        raise SettlementLedgerError("transaction_id must be unique")
    for row in normalized:
        related_id = str(row.get("related_transaction_id", "")).strip()
        if not related_id:
            continue
        origin = by_id.get(related_id)
        if origin is None:
            raise SettlementLedgerError(f"{row['transaction_id']}: unknown related_transaction_id {related_id}")
        if origin["worker_id"] != row["worker_id"]:
            raise SettlementLedgerError(f"{row['transaction_id']}: related transaction must belong to the same worker")
        if origin.get("related_transaction_id"):
            raise SettlementLedgerError(f"{row['transaction_id']}: related_transaction_id must reference an origin transaction")
    return normalized, by_id


def calculate_open_balance(rows: Iterable[dict[str, Any]], transaction_id: str) -> dict[str, Any]:
    normalized, by_id = _validated_index(rows)
    origin = by_id.get(transaction_id)
    if origin is None:
        raise SettlementLedgerError(f"unknown transaction_id: {transaction_id}")
    if origin.get("related_transaction_id"):
        raise SettlementLedgerError("balance must be requested for an origin transaction")

    settlements = [row for row in normalized if row.get("related_transaction_id") == transaction_id]
    settled = sum((row["amount"] for row in settlements), Decimal("0"))
    balance = origin["amount"] - settled
    if balance < 0:
        raise SettlementLedgerError(f"{transaction_id}: settlement exceeds origin amount")

    return {
        "transaction_id": transaction_id,
        "worker_id": origin["worker_id"],
        "origin_amount": origin["amount"],
        "settled_amount": settled,
        "open_balance": balance,
        "derived_status": "정산완료" if balance == 0 else "미정산" if settled == 0 else "부분정산",
    }


def resolve_period_adjustments(
    rows: Iterable[dict[str, Any]], worker_id: str, settlement_period: str
) -> dict[str, Any]:
    normalized, _ = _validated_index(rows)
    selected = [
        row for row in normalized
        if row["worker_id"] == worker_id
        and str(row.get("settlement_period", "")).strip() == settlement_period
    ]
    lines = []
    total = Decimal("0")
    for row in selected:
        signed_amount = row["amount"] if row["direction"] == "지급" else -row["amount"]
        total += signed_amount
        lines.append({
            "transaction_id": row["transaction_id"],
            "transaction_type": row["transaction_type"],
            "direction": row["direction"],
            "amount": row["amount"],
            "signed_amount": signed_amount,
            "related_transaction_id": row.get("related_transaction_id", ""),
        })
    return {"worker_id": worker_id, "settlement_period": settlement_period, "lines": lines, "settlement_adjustment": total}



def resolve_rounding_carry_settlement(
    rows: Iterable[dict[str, Any]], worker_id: str, settlement_period: str
) -> dict[str, Any]:
    """Finalize accumulated rounding carry to integer KRW at settlement time."""
    normalized, _ = _validated_index(rows)
    selected = [
        row for row in normalized
        if row["worker_id"] == worker_id
        and row["transaction_type"] == "rounding_carry"
        and str(row.get("settlement_period", "")).strip() == settlement_period
    ]
    accumulated = sum((row["amount"] for row in selected), Decimal("0"))
    finalized = accumulated.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {
        "worker_id": worker_id,
        "settlement_period": settlement_period,
        "transaction_type": "rounding_settlement",
        "source_transaction_ids": [row["transaction_id"] for row in selected],
        "accumulated_amount": accumulated,
        "settlement_amount": finalized,
        "rounding_adjustment": finalized - accumulated,
    }
