"""Resolve component inputs, calculate them, and preserve calculation trace."""

from __future__ import annotations

from typing import Any, Mapping

try:
    from .calculation_primitive import calculate_component
    from .reference_resolver import resolve_reference
except ImportError:
    from calculation_primitive import calculate_component
    from reference_resolver import resolve_reference


class ComponentCalculationError(RuntimeError):
    """Raised when a component input contract cannot be resolved."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Component calculation failed: {message}"
        )


def _resolve_input(
    field: str,
    spec: Any,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise ComponentCalculationError(f"{field} must be a mapping")

    has_value = "value" in spec
    has_source = "source" in spec
    has_reference = "reference" in spec

    if has_value and (has_source or has_reference):
        raise ComponentCalculationError(
            f"{field} must use either literal or reference, not both"
        )

    if has_value:
        return {
            "kind": "literal",
            "resolved_value": spec["value"],
        }

    if has_source != has_reference:
        raise ComponentCalculationError(
            f"{field} reference requires source and reference together"
        )

    if has_source and has_reference:
        source = str(spec["source"]).strip()
        if source not in sources:
            raise ComponentCalculationError(
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
        }

    raise ComponentCalculationError(
        f"{field} must define value or source/reference"
    )


def calculate_component_from_spec(
    component_spec: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calculate one component from explicit literal/reference input specs."""
    if not isinstance(component_spec, Mapping):
        raise ComponentCalculationError("component_spec must be a mapping")

    resolved_sources = sources or {}
    if not isinstance(resolved_sources, Mapping):
        raise ComponentCalculationError("sources must be a mapping")

    if "unit_amount" not in component_spec:
        raise ComponentCalculationError("unit_amount is required")

    input_specs = {
        "unit_amount": component_spec["unit_amount"],
        "quantity": component_spec.get("quantity", {"value": 1}),
        "multiplier": component_spec.get("multiplier", {"value": 1}),
    }
    trace = {
        field: _resolve_input(field, spec, resolved_sources)
        for field, spec in input_specs.items()
    }

    calculated = calculate_component(
        trace["unit_amount"]["resolved_value"],
        trace["quantity"]["resolved_value"],
        trace["multiplier"]["resolved_value"],
    )

    return {
        **calculated,
        "calculation_trace": trace,
    }
