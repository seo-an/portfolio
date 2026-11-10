"""Resolve payroll operating payment-basis rules into concrete origin periods."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any


class PayrollOperatingConfigError(ValueError):
    pass


def _parse_payroll_period(payroll_period: str) -> tuple[int, int]:
    try:
        year_text, month_text = str(payroll_period).split("-")
        year, month = int(year_text), int(month_text)
        if not 1 <= month <= 12:
            raise ValueError
        return year, month
    except (TypeError, ValueError) as exc:
        raise PayrollOperatingConfigError("payroll_period must use YYYY-MM") from exc


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def _resolve_explicit_origin(
    origin_from: str | None,
    origin_to: str | None,
) -> tuple[date, date] | None:
    if origin_from is None and origin_to is None:
        return None
    if not origin_from or not origin_to:
        raise PayrollOperatingConfigError(
            "origin_from and origin_to must be provided together"
        )
    start, end = date.fromisoformat(origin_from), date.fromisoformat(origin_to)
    if end < start:
        raise PayrollOperatingConfigError("origin_to precedes origin_from")
    return start, end


def validate_operating_config(config: dict[str, Any]) -> dict[str, Any]:
    bases = config.get("payment_basis")
    pay_item_rules = config.get("pay_item_rules")
    source_rules = config.get("source_rules")
    if not isinstance(bases, dict) or not bases:
        raise PayrollOperatingConfigError("payment_basis is required")
    if not isinstance(pay_item_rules, dict):
        raise PayrollOperatingConfigError("pay_item_rules is required")
    if not isinstance(source_rules, dict):
        raise PayrollOperatingConfigError("source_rules is required")

    for code, basis in bases.items():
        rule = basis.get("period_rule", {})
        if rule.get("type") != "calendar_month":
            raise PayrollOperatingConfigError(
                f"{code}: unsupported period_rule.type {rule.get('type')!r}"
            )
        if not isinstance(rule.get("offset_months"), int):
            raise PayrollOperatingConfigError(
                f"{code}: calendar_month requires integer offset_months"
            )

    for pay_item_code, basis_code in pay_item_rules.items():
        if basis_code is not None and basis_code not in bases:
            raise PayrollOperatingConfigError(
                f"{pay_item_code}: unknown payment_basis {basis_code!r}"
            )

    for source, rule in source_rules.items():
        basis_code = rule.get("payment_basis")
        if basis_code not in bases:
            raise PayrollOperatingConfigError(
                f"{source}: unknown payment_basis {basis_code!r}"
            )
    return config


def resolve_payment_basis_period(
    payroll_period: str,
    payment_basis: str,
    config: dict[str, Any],
    origin_from: str | None = None,
    origin_to: str | None = None,
) -> dict[str, Any]:
    validate_operating_config(config)

    explicit = _resolve_explicit_origin(origin_from, origin_to)
    if explicit is not None:
        start, end = explicit
        return {
            "payroll_period": payroll_period,
            "payment_basis": payment_basis,
            "payment_basis_label": config["payment_basis"].get(payment_basis, {}).get("label"),
            "period_from": start,
            "period_to": end,
            "period_resolution": "explicit_origin_override",
        }

    basis = config["payment_basis"].get(payment_basis)
    if basis is None:
        raise PayrollOperatingConfigError(f"unknown payment_basis: {payment_basis}")

    year, month = _parse_payroll_period(payroll_period)
    rule = basis["period_rule"]
    year, month = _shift_month(year, month, rule["offset_months"])
    last_day = calendar.monthrange(year, month)[1]

    return {
        "payroll_period": payroll_period,
        "payment_basis": payment_basis,
        "payment_basis_label": basis["label"],
        "period_from": date(year, month, 1),
        "period_to": date(year, month, last_day),
        "period_resolution": "default_payment_basis",
    }


def resolve_source_period(
    payroll_period: str,
    source: str,
    config: dict[str, Any],
    origin_from: str | None = None,
    origin_to: str | None = None,
    payment_basis: str | None = None,
    pay_item_code: str | None = None,
) -> dict[str, Any]:
    validate_operating_config(config)

    explicit = _resolve_explicit_origin(origin_from, origin_to)
    if explicit is not None:
        return {
            "payroll_period": payroll_period,
            "source": source,
            "pay_item_code": pay_item_code,
            "payment_basis": None,
            "payment_basis_label": None,
            "period_from": explicit[0],
            "period_to": explicit[1],
            "period_resolution": "explicit_origin_override",
        }

    if payment_basis is not None:
        basis_code = payment_basis
        resolution = "explicit_payment_basis"
    else:
        pay_item_basis = (
            config["pay_item_rules"].get(pay_item_code)
            if pay_item_code is not None
            else None
        )
        if pay_item_basis is not None:
            basis_code = pay_item_basis
            resolution = "pay_item_rule"
        else:
            source_rule = config["source_rules"].get(source, {})
            basis_code = source_rule.get("payment_basis")
            resolution = "source_rule"

    if basis_code is None:
        raise PayrollOperatingConfigError(
            f"{source}: payment_basis is required when explicit origin is absent"
        )

    result = resolve_payment_basis_period(
        payroll_period,
        basis_code,
        config,
        origin_from=origin_from,
        origin_to=origin_to,
    )
    result["source"] = source
    result["pay_item_code"] = pay_item_code
    result["period_resolution"] = resolution
    return result
