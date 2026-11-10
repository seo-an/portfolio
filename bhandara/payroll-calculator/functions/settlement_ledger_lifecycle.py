"""Coordinate Settlement Ledger balances with one operational Payroll run."""

from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_ledger = _load_sibling("settlement_ledger")
_rounding = _load_sibling("rounding_settlement")


class SettlementLedgerLifecycleError(ValueError):
    pass


def prepare_worker_settlement(
    ledger_rows: Iterable[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
    *,
    settle_rounding_carry: bool = False,
    settlement_batch_id: str | None = None,
) -> dict[str, Any]:
    """Resolve ledger effects to apply before Final Payroll.

    Scheduled non-rounding transactions use their signed ledger direction.
    Rounding carry is settled only when explicitly requested and uses the
    annual HALF_UP settlement amount, while related transactions close the
    exact open balances.
    """
    rows = list(ledger_rows)
    period = _ledger.resolve_period_adjustments(rows, worker_id, payroll_period)
    ordinary_lines = [
        line for line in period["lines"]
        if line["transaction_type"] not in {"rounding_carry", "rounding_settlement"}
    ]
    ordinary_adjustment = sum(
        (line["signed_amount"] for line in ordinary_lines), Decimal("0")
    )

    rounding_batch = None
    rounding_adjustment = Decimal("0")
    ledger_write_requests: list[dict[str, Any]] = []
    if settle_rounding_carry:
        batch_id = str(settlement_batch_id or "").strip()
        if not batch_id:
            raise SettlementLedgerLifecycleError(
                "settlement_batch_id is required when settling rounding carry"
            )
        rounding_batch = _rounding.build_rounding_settlement_batch(
            rows, worker_id, payroll_period, batch_id
        )
        rounding_adjustment = rounding_batch["settlement_amount"]
        ledger_write_requests.extend(rounding_batch["settlement_transactions"])

    return {
        "worker_id": worker_id,
        "payroll_period": payroll_period,
        "ordinary_lines": ordinary_lines,
        "ordinary_adjustment": ordinary_adjustment,
        "rounding_batch": rounding_batch,
        "rounding_adjustment": rounding_adjustment,
        "settlement_adjustment": ordinary_adjustment + rounding_adjustment,
        "ledger_write_requests": ledger_write_requests,
    }


def materialize_ledger_requests(
    requests: Iterable[Mapping[str, Any] | None],
    transaction_id_factory: Callable[[Mapping[str, Any]], str],
) -> list[dict[str, Any]]:
    """Assign IDs to append-only ledger requests and validate final rows."""
    materialized = []
    for request in requests:
        if request is None:
            continue
        row = dict(request)
        if not str(row.get("transaction_id", "")).strip():
            transaction_id = str(transaction_id_factory(row)).strip()
            if not transaction_id:
                raise SettlementLedgerLifecycleError(
                    "transaction_id_factory returned an empty transaction_id"
                )
            row["transaction_id"] = transaction_id
        materialized.append(_ledger.validate_transaction(row))

    ids = [row["transaction_id"] for row in materialized]
    if len(set(ids)) != len(ids):
        raise SettlementLedgerLifecycleError(
            "materialized transaction_id values must be unique"
        )
    return materialized
