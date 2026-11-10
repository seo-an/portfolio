"""Resolve ordinary-wage basis from effective compensation and explicit policy."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class OrdinaryWageResolutionError(RuntimeError):
    """Raised when ordinary-wage basis cannot be determined without inference."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Ordinary wage resolution failed: {message}")


def _registry_by_code(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["code"]: item for item in registry["items"]}


def _policy_decision(code: str, payroll_policy: dict[str, Any]) -> str | None:
    return payroll_policy.get("ordinary_wage", {}).get("pay_items", {}).get(code)


def resolve_ordinary_monthly_wage(
    compensation: dict[str, Any],
    registry: dict[str, Any],
    payroll_policy: dict[str, Any],
) -> dict[str, Any]:
    registry_items = _registry_by_code(registry)
    included: dict[str, Decimal] = {}
    excluded: dict[str, Decimal] = {}
    unresolved: list[str] = []

    for code, raw_amount in compensation.items():
        if code in {"worker_id", "effective_from", "effective_to"} or raw_amount in (None, ""):
            continue

        item = registry_items.get(code)
        if item is None:
            raise OrdinaryWageResolutionError(f"unknown compensation item: {code}")

        amount = Decimal(str(raw_amount))
        classification = item.get("ordinary_wage")
        decision = classification

        if classification in {"회사정책", "별도판정"}:
            decision = _policy_decision(code, payroll_policy)
            if decision not in {"산입", "미산입"}:
                unresolved.append(code)
                continue

        if decision == "산입":
            included[code] = amount
        elif decision == "미산입":
            excluded[code] = amount
        else:
            unresolved.append(code)

    if unresolved:
        raise OrdinaryWageResolutionError(
            "explicit 산입/미산입 policy required for: " + ", ".join(sorted(unresolved))
        )

    return {
        "ordinary_monthly_wage": sum(included.values(), Decimal("0")),
        "included_items": included,
        "excluded_items": excluded,
    }


def resolve_ordinary_hourly_wage(
    ordinary_monthly_wage: Any,
    monthly_basis_hours: Any,
) -> Decimal:
    wage = Decimal(str(ordinary_monthly_wage))
    hours = Decimal(str(monthly_basis_hours))
    if wage < 0:
        raise OrdinaryWageResolutionError("ordinary_monthly_wage must not be negative")
    if hours <= 0:
        raise OrdinaryWageResolutionError("monthly basis hours must be greater than zero")
    return wage / hours
