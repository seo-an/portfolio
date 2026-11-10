"""Assemble validated and period-prepared inputs for one Payroll run."""

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


_xlsx = _load_sibling("xlsx_loader")
_contracts = _load_sibling("input_contracts")
_handoff = _load_sibling("worktime_handoff")
_preparation = _load_sibling("operating_input_preparation")
_operating = _load_sibling("operating_period_resolver")


class PayrollRunInputError(ValueError):
    pass


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PayrollRunInputError(f"{field} must be a mapping")
    return dict(value)


def build_payroll_run_input(
    payroll_period: str,
    compensation_path: str | Path,
    payroll_input_path: str | Path,
    worktime_rows: list[dict[str, Any]],
    registry: Mapping[str, Any],
    operating_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Load, validate, and period-prepare all current Payroll source inputs.

    This function does not calculate payroll amounts.
    """
    registry_dict = _mapping(registry, "registry")
    config = _mapping(operating_config, "operating_config")
    _operating.validate_operating_config(config)

    compensation_rows = _xlsx.load_compensation_rows(
        compensation_path, registry_dict
    )
    payroll_input_rows = _xlsx.load_payroll_input_rows(payroll_input_path)
    validated_payroll_input = [
        _contracts.validate_payroll_input_row(row, registry_dict)
        for row in payroll_input_rows
    ]
    validated_worktime = _handoff.validate_worktime_handoff(worktime_rows)

    compensation = _preparation.prepare_compensation_rows(
        compensation_rows, payroll_period, config
    )
    worktime = _preparation.prepare_worktime_rows(
        validated_worktime, payroll_period, config
    )
    payroll_input = _preparation.prepare_payroll_input_rows(
        validated_payroll_input, payroll_period, config
    )

    return {
        "payroll_period": str(payroll_period).strip(),
        "compensation": compensation,
        "compensation_history": compensation_rows,
        "worktime": worktime,
        "worktime_history": validated_worktime,
        "payroll_input": payroll_input,
    }
