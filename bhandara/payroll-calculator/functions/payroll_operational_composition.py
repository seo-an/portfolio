"""Compose calculated Payroll Results into safe worker-level Payroll runs."""

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


_run = _load_sibling("payroll_run")


class PayrollOperationalCompositionError(ValueError):
    pass


def _period(value: Any) -> str:
    period = str(value).strip() if value is not None else ""
    if not period:
        raise PayrollOperationalCompositionError(
            "payroll_period must not be empty"
        )
    return period


def _group_results(
    results: Iterable[Mapping[str, Any]],
    payroll_period: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        if not isinstance(result, Mapping):
            raise PayrollOperationalCompositionError(
                "each Payroll Result must be a mapping"
            )
        worker_id = str(result.get("worker_id", "")).strip()
        if not worker_id:
            raise PayrollOperationalCompositionError(
                "Payroll Result worker_id must not be empty"
            )
        result_period = str(result.get("payroll_period", "")).strip()
        if not result_period:
            raise PayrollOperationalCompositionError(
                f"{worker_id}: Payroll Result payroll_period must not be empty"
            )
        if result_period != payroll_period:
            raise PayrollOperationalCompositionError(
                f"{worker_id}: mixed payroll_period is not allowed: "
                f"{result_period} != {payroll_period}"
            )
        grouped.setdefault(worker_id, []).append(dict(result))
    return grouped


def run_payroll_composition(
    source_results: Mapping[str, Iterable[Mapping[str, Any]]],
    payroll_period: Any,
    policy: dict[str, Any],
    *,
    validations_by_worker: Mapping[str, list[dict[str, Any]]] | None = None,
    settlement_adjustments_by_worker: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine source Results and execute the current worker Payroll runner.

    Source calculations stay outside this module. Multiple Results with the
    same pay_item_code are allowed because valid source calculations may emit
    daily or component-level lines.
    """
    period = _period(payroll_period)
    if not isinstance(source_results, Mapping):
        raise PayrollOperationalCompositionError(
            "source_results must be a mapping"
        )

    combined: list[Mapping[str, Any]] = []
    source_counts: dict[str, int] = {}
    for source, results in source_results.items():
        source_name = str(source).strip()
        if not source_name:
            raise PayrollOperationalCompositionError(
                "source_results source key must not be empty"
            )
        materialized = list(results)
        source_counts[source_name] = len(materialized)
        combined.extend(materialized)

    grouped = _group_results(combined, period)
    validations = validations_by_worker or {}
    adjustments = settlement_adjustments_by_worker or {}

    unknown_validation_workers = set(validations) - set(grouped)
    if unknown_validation_workers:
        raise PayrollOperationalCompositionError(
            "validations reference workers without Payroll Results: "
            + ", ".join(sorted(unknown_validation_workers))
        )
    unknown_adjustment_workers = set(adjustments) - set(grouped)
    if unknown_adjustment_workers:
        raise PayrollOperationalCompositionError(
            "settlement adjustments reference workers without Payroll Results: "
            + ", ".join(sorted(unknown_adjustment_workers))
        )

    worker_runs = {}
    for worker_id in sorted(grouped):
        worker_runs[worker_id] = _run.run_worker_payroll(
            grouped[worker_id],
            worker_id,
            period,
            policy,
            validations=list(validations.get(worker_id, [])),
            settlement_adjustment=adjustments.get(worker_id, 0),
        )

    return {
        "payroll_period": period,
        "source_counts": source_counts,
        "result_count": len(combined),
        "worker_count": len(worker_runs),
        "worker_runs": worker_runs,
    }
