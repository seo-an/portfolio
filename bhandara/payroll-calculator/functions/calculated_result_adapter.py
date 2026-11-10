"""Promote completed Payroll calculation outputs into Payroll Result."""

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


class CalculatedResultAdapterError(ValueError):
    pass


def build_payroll_result_from_calculation(
    calculated: Mapping[str, Any],
    payroll_period: str,
    registry: Mapping[str, Any],
    *,
    source: str,
    operating_period: Mapping[str, Any] | None = None,
    origin_from: Any | None = None,
    origin_to: Any | None = None,
    origin_pay_item_code: Any | None = None,
    calculation_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Promote an already-calculated source result without recalculating it."""
    if not isinstance(calculated, Mapping):
        raise CalculatedResultAdapterError("calculated result must be a mapping")

    worker_id = calculated.get("worker_id")
    pay_item_code = calculated.get("pay_item_code")
    calculated_amount = calculated.get("calculated_amount")
    if worker_id in (None, ""):
        raise CalculatedResultAdapterError("calculated result requires worker_id")
    if pay_item_code in (None, ""):
        raise CalculatedResultAdapterError("calculated result requires pay_item_code")
    if calculated_amount in (None, ""):
        raise CalculatedResultAdapterError(
            "calculated result requires calculated_amount"
        )
    normalized_source = str(source).strip()
    if not normalized_source:
        raise CalculatedResultAdapterError("source must not be empty")

    trace = dict(calculation_trace or {})
    trace["calculation"] = dict(calculated)
    if operating_period is not None:
        trace = _operating_trace.merge_operating_trace(trace, operating_period)

    return _payroll_result.build_payroll_result(
        worker_id,
        payroll_period,
        pay_item_code,
        calculated_amount,
        registry,
        origin_from=origin_from,
        origin_to=origin_to,
        origin_pay_item_code=origin_pay_item_code,
        source=normalized_source,
        calculation_trace=trace,
    )
