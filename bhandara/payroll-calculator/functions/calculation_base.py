"""Resolve and sum direct calculation-base inputs with provenance."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

try:
    from .reference_resolver import resolve_reference
except ImportError:
    from reference_resolver import resolve_reference


class CalculationBaseError(RuntimeError):
    """Raised when a calculation base cannot be resolved deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Calculation base failed: {message}"
        )


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CalculationBaseError(f"{field} must be decimal-compatible") from exc
    if not number.is_finite():
        raise CalculationBaseError(f"{field} must be finite")
    if number < 0:
        raise CalculationBaseError(f"{field} must not be negative")
    return number


def _resolve_term(
    index: int,
    spec: Any,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    field = f"terms[{index}]"
    if not isinstance(spec, Mapping):
        raise CalculationBaseError(f"{field} must be a mapping")

    has_value = "value" in spec
    has_source = "source" in spec
    has_reference = "reference" in spec

    if has_value and (has_source or has_reference):
        raise CalculationBaseError(
            f"{field} must use either literal or reference, not both"
        )

    if has_value:
        resolved_value = spec["value"]
        return {
            "kind": "literal",
            "resolved_value": resolved_value,
            "amount": _decimal(resolved_value, field),
        }

    if has_source != has_reference:
        raise CalculationBaseError(
            f"{field} reference requires source and reference together"
        )

    if has_source and has_reference:
        source = str(spec["source"]).strip()
        if source not in sources:
            raise CalculationBaseError(
                f"{field} source was not provided: {source}"
            )
        resolved = resolve_reference(
            spec["source"],
            spec["reference"],
            sources[source],
        )
        return {
            "kind": "reference",
            **resolved,
            "amount": _decimal(resolved["resolved_value"], field),
        }

    raise CalculationBaseError(
        f"{field} must define value or source/reference"
    )


def calculate_base(
    base_code: Any,
    terms: Any,
    sources: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sum direct literal/reference terms without dependency traversal."""
    code = str(base_code).strip() if base_code is not None else ""
    if not code:
        raise CalculationBaseError("base_code must not be empty")
    if not isinstance(terms, list) or not terms:
        raise CalculationBaseError("terms must be a non-empty list")

    resolved_sources = sources or {}
    if not isinstance(resolved_sources, Mapping):
        raise CalculationBaseError("sources must be a mapping")

    resolved_terms = [
        _resolve_term(index, spec, resolved_sources)
        for index, spec in enumerate(terms)
    ]
    calculated_amount = sum(
        (term["amount"] for term in resolved_terms),
        Decimal("0"),
    )

    return {
        "base_code": code,
        "calculated_amount": calculated_amount,
        "terms": resolved_terms,
    }
