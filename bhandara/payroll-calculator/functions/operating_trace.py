"""Preserve Payroll operating-period provenance without changing factual origin."""

from __future__ import annotations

from typing import Any, Mapping


class OperatingTraceError(ValueError):
    pass


def build_operating_period_trace(period: Mapping[str, Any]) -> dict[str, Any]:
    required = ("period_from", "period_to", "period_resolution")
    missing = [field for field in required if field not in period]
    if missing:
        raise OperatingTraceError(
            "operating period missing field(s): " + ", ".join(missing)
        )
    return {
        "source": period.get("source"),
        "payment_basis": period.get("payment_basis"),
        "payment_basis_label": period.get("payment_basis_label"),
        "period_from": period["period_from"],
        "period_to": period["period_to"],
        "period_resolution": period["period_resolution"],
    }


def merge_operating_trace(
    calculation_trace: Mapping[str, Any] | None,
    period: Mapping[str, Any],
) -> dict[str, Any]:
    trace = dict(calculation_trace or {})
    trace["operating_period"] = build_operating_period_trace(period)
    return trace
