"""Build Payroll Results while preserving operating-period provenance."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_payroll_result = _load_sibling("payroll_result")
_operating_trace = _load_sibling("operating_trace")


class PayrollResultAdapterError(ValueError):
    pass


def build_payroll_result_from_prepared_input(
    prepared: Mapping[str, Any],
    payroll_period: str,
    registry: Mapping[str, Any],
    *,
    calculated_amount: Any | None = None,
    calculation_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one prepared Payroll Input transaction into Payroll Result.

    Resolved operating periods are selection provenance, not factual origin.
    Explicit origin fields remain factual origin on the Result.
    """
    row = prepared.get("row")
    period = prepared.get("period")
    if not isinstance(row, Mapping):
        raise PayrollResultAdapterError("prepared.row must be a mapping")
    if not isinstance(period, Mapping):
        raise PayrollResultAdapterError("prepared.period must be a mapping")

    amount = row.get("amount") if calculated_amount is None else calculated_amount
    if amount in (None, ""):
        raise PayrollResultAdapterError(
            "calculated_amount is required when payroll input amount is empty"
        )

    trace = _operating_trace.merge_operating_trace(calculation_trace, period)

    return _payroll_result.build_payroll_result(
        row.get("worker_id"),
        payroll_period,
        row.get("pay_item_code"),
        amount,
        registry,
        origin_from=row.get("origin_from"),
        origin_to=row.get("origin_to"),
        origin_pay_item_code=row.get("origin_pay_item_code"),
        source="payroll_input",
        calculation_trace=trace,
    )
