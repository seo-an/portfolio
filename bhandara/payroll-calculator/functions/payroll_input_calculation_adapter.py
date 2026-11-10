"""Convert prepared Payroll Input transactions into Payroll Results."""

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


_result_adapter = _load_sibling("payroll_result_adapter")


class PayrollInputCalculationAdapterError(ValueError):
    pass


def build_payroll_input_results(
    prepared_rows: list[Mapping[str, Any]],
    payroll_period: str,
    registry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Promote amount-finalized inputs; never infer a quantity-only calculation."""
    results = []
    for prepared in prepared_rows:
        row = prepared.get("row")
        if not isinstance(row, Mapping):
            raise PayrollInputCalculationAdapterError(
                "prepared payroll input row must be a mapping"
            )
        if row.get("amount") in (None, ""):
            if row.get("quantity") not in (None, ""):
                raise PayrollInputCalculationAdapterError(
                    f"{row.get('pay_item_code')}: quantity-only payroll input "
                    "requires an explicit calculation rule"
                )
            raise PayrollInputCalculationAdapterError(
                f"{row.get('pay_item_code')}: payroll input amount is required"
            )
        results.append(
            _result_adapter.build_payroll_result_from_prepared_input(
                prepared, payroll_period, registry
            )
        )
    return results
