"""Compose prepared Compensation facts into prorated Payroll Results."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Iterable, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_facts = _load_sibling("payroll_fact_contracts")
_graph = _load_sibling("dependency_resolver")
_result_adapter = _load_sibling("calculated_result_adapter")


class CompensationCalculationAdapterError(ValueError):
    pass


def _employment_by_worker(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    resolved = {}
    for raw in rows:
        fact = _facts.validate_employment_fact(raw)
        worker_id = fact["worker_id"]
        if worker_id in resolved:
            raise CompensationCalculationAdapterError(
                f"{worker_id}: multiple employment facts are not supported in v0.1"
            )
        resolved[worker_id] = fact
    return resolved


def _eligibility_by_worker_item(
    rows: Iterable[Mapping[str, Any]],
    registry: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    resolved = {}
    for raw in rows:
        fact = _facts.validate_pay_item_eligibility(raw, registry)
        key = (fact["worker_id"], fact["pay_item_code"])
        if key in resolved:
            raise CompensationCalculationAdapterError(
                f"{key[0]}/{key[1]}: multiple eligibility facts are not supported in v0.1"
            )
        resolved[key] = fact
    return resolved


def build_prorated_compensation_results(
    prepared_compensation: Mapping[str, Any],
    payroll_period: str,
    registry: Mapping[str, Any],
    policy: Mapping[str, Any],
    employment_facts: Iterable[Mapping[str, Any]],
    *,
    pay_item_codes: Iterable[str],
    eligibility_facts: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Calculate explicitly selected recurring Compensation items.

    This adapter owns composition only. Proration, eligibility resolution, and
    Payroll Result construction remain in their dedicated modules.
    """
    rows = prepared_compensation.get("rows")
    operating_period = prepared_compensation.get("period")
    if not isinstance(rows, list):
        raise CompensationCalculationAdapterError(
            "prepared_compensation.rows must be a list"
        )
    if not isinstance(operating_period, Mapping):
        raise CompensationCalculationAdapterError(
            "prepared_compensation.period must be a mapping"
        )

    codes = [str(code).strip() for code in pay_item_codes]
    if not codes or any(not code for code in codes):
        raise CompensationCalculationAdapterError(
            "pay_item_codes must contain at least one non-empty code"
        )
    if len(set(codes)) != len(codes):
        raise CompensationCalculationAdapterError(
            "pay_item_codes must not contain duplicates"
        )

    employment = _employment_by_worker(employment_facts)
    eligibility = _eligibility_by_worker_item(eligibility_facts, registry)
    worker_ids = sorted({
        str(row.get("worker_id", "")).strip()
        for row in rows
        if str(row.get("worker_id", "")).strip()
    })

    results = []
    for worker_id in worker_ids:
        if worker_id not in employment:
            raise CompensationCalculationAdapterError(
                f"{worker_id}: employment fact is required"
            )
        employment_fact = employment[worker_id]

        for pay_item_code in codes:
            if not any(
                str(row.get("worker_id", "")).strip() == worker_id
                and row.get(pay_item_code) not in (None, "")
                for row in rows
            ):
                continue

            node = {
                "type": "prorated_recurring",
                "compensation_rows": rows,
                "worker_id": worker_id,
                "payroll_period": payroll_period,
                "pay_item_code": pay_item_code,
                "registry": dict(registry),
                "policy": dict(policy),
                "employment_from": employment_fact["employment_from"],
                "employment_to": employment_fact["employment_to"],
            }
            eligibility_fact = eligibility.get((worker_id, pay_item_code))
            if eligibility_fact is not None:
                node["eligibility"] = {
                    "eligibility_from": eligibility_fact["eligibility_from"],
                    "eligibility_to": eligibility_fact["eligibility_to"],
                    "payable_rule": eligibility_fact["payable_rule"],
                }

            calculated = _graph.resolve_calculation_graph(
                {pay_item_code: node}
            )["results"][pay_item_code]
            results.append(
                _result_adapter.build_payroll_result_from_calculation(
                    calculated,
                    payroll_period,
                    registry,
                    source="compensation",
                    operating_period=operating_period,
                )
            )

    return results
