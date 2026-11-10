"""Build annual rounding settlement batches from open rounding-carry transactions."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

try:
    from .settlement_ledger import SettlementLedgerError, calculate_open_balance, validate_transaction
except ImportError:
    from settlement_ledger import SettlementLedgerError, calculate_open_balance, validate_transaction


def build_rounding_settlement_batch(
    rows: Iterable[dict[str, Any]],
    worker_id: str,
    settlement_period: str,
    batch_id: str,
) -> dict[str, Any]:
    normalized = [validate_transaction(row) for row in rows]
    open_items: list[dict[str, Any]] = []

    for row in normalized:
        if row["worker_id"] != worker_id:
            continue
        if row["transaction_type"] != "rounding_carry":
            continue
        if row.get("related_transaction_id"):
            continue
        balance = calculate_open_balance(normalized, row["transaction_id"])
        if balance["open_balance"] > 0:
            open_items.append({
                "transaction_id": row["transaction_id"],
                "origin_period": row["origin_period"],
                "open_balance": balance["open_balance"],
            })

    carry_total = sum((item["open_balance"] for item in open_items), Decimal("0"))
    settlement_amount = carry_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    settlement_rounding_difference = settlement_amount - carry_total
    settlement_transactions = [
        {
            "worker_id": worker_id,
            "transaction_type": "rounding_settlement",
            "origin_period": item["origin_period"],
            "origin_pay_item_code": "",
            "amount": item["open_balance"],
            "direction": "지급",
            "settlement_period": settlement_period,
            "settlement_batch_id": batch_id,
            "related_transaction_id": item["transaction_id"],
            "note": "Annual rounding carry settlement",
        }
        for item in open_items
    ]

    return {
        "worker_id": worker_id,
        "settlement_period": settlement_period,
        "settlement_batch_id": batch_id,
        "open_items": open_items,
        "carry_total": carry_total,
        "settlement_amount": settlement_amount,
        "settlement_rounding_difference": settlement_rounding_difference,
        "rounding_difference_handling": "annual_rounding_adjustment",
        "closing_carry_balance": Decimal("0"),
        "settlement_transactions": settlement_transactions,
    }
