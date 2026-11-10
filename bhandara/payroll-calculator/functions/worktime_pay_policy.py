"""Resolve company worktime-pay semantics without inferring missing payroll policy."""

from __future__ import annotations

from typing import Any


class WorktimePayPolicyError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Worktime pay policy resolution failed: {message}")


VALID_BASE_COMPONENT_POLICIES = {"별도지급", "기지급", "중첩"}


def resolve_base_component_policy(
    pay_item_code: str,
    company_policy: dict[str, Any],
    legal_policy: dict[str, Any],
) -> str:
    legal_rule = legal_policy.get("premium_rules", {}).get(pay_item_code)
    if legal_rule is None:
        raise WorktimePayPolicyError(f"no legal premium rule for {pay_item_code}")

    configured = (
        company_policy.get("worktime_pay", {})
        .get("base_component_policy", {})
        .get(pay_item_code)
    )

    if configured in VALID_BASE_COMPONENT_POLICIES:
        return configured

    legal_default = legal_rule.get("base_component", {}).get("default")
    if legal_default in VALID_BASE_COMPONENT_POLICIES:
        return legal_default

    raise WorktimePayPolicyError(
        f"explicit base component policy required for {pay_item_code}"
    )
