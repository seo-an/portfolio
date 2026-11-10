"""Build legal/worktime validation results without calculating payroll money."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


ZERO = Decimal("0")


def decimal_hours(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def resolve_weekly_limit(system: str, labor_policy: dict[str, Any]) -> Decimal | None:
    rule = labor_policy["rules"][system]
    if "specific_week_max_hours" in rule:
        base = Decimal(str(rule["specific_week_max_hours"]))
        extension = Decimal(str(rule.get("weekly_extension_limit_hours", 0)))
        return base + extension
    if system == "standard":
        return Decimal(str(rule["base_weekly_hours"])) + Decimal(str(rule["weekly_extension_limit_hours"]))
    return None


def build_flag(code: str, severity: str, basis: str, rule_ref: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "basis": basis, "rule_ref": rule_ref, "message": message}


def evaluate_week(
    weekly_worked_hours: Any,
    system: str,
    labor_policy: dict[str, Any],
    active_exceptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    worked = decimal_hours(weekly_worked_hours)
    rule = labor_policy["rules"][system]
    rule_ref = rule["rule_ref"]
    active_exceptions = active_exceptions or []

    # A temporary exception changes the applicable legal ceiling only when its
    # own validated policy provides a numeric allowance. Merely having an
    # approval reference must never silently invent extra hours.
    limit = resolve_weekly_limit(system, labor_policy)
    exception_refs = [item["exception_type"] for item in active_exceptions]

    if limit is None:
        return {
            "weekly_worked_hours": worked,
            "weekly_remaining_hours": None,
            "rule_ref": rule_ref,
            "active_exceptions": exception_refs,
            "validation_flags": [build_flag(
                "LEGAL_REVIEW_REQUIRED", "REVIEW", "법정기준", rule_ref,
                "해당 근로시간제는 주 단일 상한만으로 적법성을 판정할 수 없어 정산기간 평가가 필요합니다.",
            )],
        }

    remaining = limit - worked
    flags: list[dict[str, str]] = []
    if remaining < ZERO:
        flags.append(build_flag(
            "WEEKLY_LEGAL_LIMIT_EXCEEDED", "ERROR", "법정기준", rule_ref,
            "현재 적용 rule의 주 단위 한도를 초과했습니다.",
        ))
    elif remaining == ZERO:
        flags.append(build_flag(
            "WEEKLY_LEGAL_LIMIT_REACHED", "WARNING", "법정기준", rule_ref,
            "현재 적용 rule의 주 단위 한도에 도달했습니다.",
        ))

    return {
        "weekly_worked_hours": worked,
        "weekly_remaining_hours": max(remaining, ZERO),
        "rule_ref": rule_ref,
        "active_exceptions": exception_refs,
        "validation_flags": flags,
    }
