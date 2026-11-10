"""Resolve effective-dated payroll policies and surface calculation-impacting changes."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Iterable

from gearbox.core.date_interval import is_date_within_interval
from gearbox.diagnostics.contract import REVIEW_REQUIRED, WARNING, build_diagnostic


class PayrollPolicyError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"[payroll-calculator] Payroll policy resolution failed: {message}")


WATCHED_PATHS = (
    ("amount_processing", "unit"),
    ("amount_processing", "method"),
    ("amount_processing", "apply_at"),
    ("amount_processing", "remainder", "settlement_month"),
)

EFFECTIVE_BASIS = {
    "amount_processing": "settlement_date",
}


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise PayrollPolicyError(f"{field} must be YYYY-MM-DD") from exc


def _get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def resolve_payroll_policy(
    policies: Iterable[dict[str, Any]], calculation_date: str
) -> dict[str, Any]:
    target = _date(calculation_date, "calculation_date")
    normalized = []
    for row in policies:
        start = _date(row.get("effective_from"), "effective_from")
        end_raw = str(row.get("effective_to", "")).strip()
        end = _date(end_raw, "effective_to") if end_raw else None
        if end is not None and end < start:
            raise PayrollPolicyError("effective_to cannot precede effective_from")
        normalized.append((start, end, row))

    applicable = [
        x for x in normalized
        if is_date_within_interval(x[0], x[1], target)
    ]
    if len(applicable) != 1:
        raise PayrollPolicyError(f"{calculation_date}: expected exactly one applicable policy, found {len(applicable)}")

    current_start, _, current = applicable[0]
    previous_candidates = [x for x in normalized if x[0] < current_start]
    previous = max(previous_candidates, key=lambda x: x[0])[2] if previous_candidates else None

    warnings = []
    if previous is not None:
        changes = []
        for path in WATCHED_PATHS:
            before = _get(previous, path)
            after = _get(current, path)
            if before != after:
                changes.append({"field": ".".join(path), "before": before, "after": after})
        if changes:
            warning = build_diagnostic(
                "POLICY_CHANGE",
                WARNING,
                "Payroll calculation policy changed from the previous effective policy. Review for intentional change or data-entry error.",
                states=[REVIEW_REQUIRED],
                category="VALIDATION",
                context={
                    "effective_from": current["effective_from"],
                    "changes": changes,
                },
            )
            warning["effective_from"] = current["effective_from"]
            warning["changes"] = changes
            warnings.append(warning)

    return {
        "policy": deepcopy(current),
        "effective_basis": EFFECTIVE_BASIS,
        "warnings": warnings,
    }
