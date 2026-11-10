"""Resolve payroll calculation nodes by dependency rather than hard-coded order."""

from __future__ import annotations

from typing import Any, Mapping

try:
    from .calculation_base import calculate_base
    from .component_calculator import calculate_component_from_spec
    from .derived_value import calculate_derived_value
    from .proration import build_prorated_recurring_item
    from .eligibility_resolver import resolve_payable_period
except ImportError:
    from calculation_base import calculate_base
    from component_calculator import calculate_component_from_spec
    from derived_value import calculate_derived_value
    from proration import build_prorated_recurring_item
    from eligibility_resolver import resolve_payable_period


class DependencyResolutionError(RuntimeError):
    """Raised when a calculation graph cannot be resolved deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Dependency resolution failed: {message}"
        )


def _node_reference(spec: Any) -> str | None:
    if not isinstance(spec, Mapping):
        return None
    if set(spec.keys()) == {"node"}:
        code = str(spec["node"]).strip() if spec["node"] is not None else ""
        if not code:
            raise DependencyResolutionError("node reference must not be empty")
        return code
    return None


def _resolved_value(result: Mapping[str, Any]) -> Any:
    if "calculated_amount" in result:
        return result["calculated_amount"]
    if "calculated_value" in result:
        return result["calculated_value"]
    raise DependencyResolutionError("resolved node has no calculated value")


def resolve_calculation_graph(
    nodes: Mapping[str, Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve base, derived, and component nodes with cycle detection."""
    if not isinstance(nodes, Mapping) or not nodes:
        raise DependencyResolutionError("nodes must be a non-empty mapping")

    resolved_sources = {} if sources is None else sources
    if not isinstance(resolved_sources, Mapping):
        raise DependencyResolutionError("sources must be a mapping")

    results: dict[str, dict[str, Any]] = {}
    visiting: list[str] = []

    def resolve_node(code: str) -> dict[str, Any]:
        if code in results:
            return results[code]
        if code in visiting:
            start = visiting.index(code)
            cycle = visiting[start:] + [code]
            raise DependencyResolutionError(
                "dependency cycle detected: " + " -> ".join(cycle)
            )
        if code not in nodes:
            raise DependencyResolutionError(f"unknown dependency node: {code}")

        spec = nodes[code]
        if not isinstance(spec, Mapping):
            raise DependencyResolutionError(f"{code} must be a mapping")

        visiting.append(code)
        try:
            node_type = spec.get("type")

            if node_type == "prorated_recurring":
                dependencies = []
                required = (
                    "compensation_rows",
                    "worker_id",
                    "payroll_period",
                    "pay_item_code",
                    "registry",
                    "policy",
                )
                missing = [field for field in required if field not in spec]
                if missing:
                    raise DependencyResolutionError(
                        f"{code}: missing required field(s): {', '.join(missing)}"
                    )
                payable_from = None
                payable_to = None
                eligibility_trace = None
                if "eligibility" in spec:
                    eligibility = spec["eligibility"]
                    if not isinstance(eligibility, Mapping):
                        raise DependencyResolutionError(
                            f"{code}.eligibility must be a mapping"
                        )
                    eligibility_trace = resolve_payable_period(
                        eligibility.get("eligibility_from"),
                        eligibility.get("payable_rule"),
                        eligibility.get("eligibility_to"),
                    )
                    payable_from = eligibility_trace["payable_from"]
                    payable_to = eligibility_trace["payable_to"]

                if (
                    eligibility_trace is not None
                    and eligibility_trace.get("payable_status") == "NOT_PAYABLE"
                ):
                    from decimal import Decimal
                    result = {
                        "pay_item_code": spec["pay_item_code"],
                        "calculated_amount": Decimal("0"),
                        "proration_segments": [],
                    }
                else:
                    result = build_prorated_recurring_item(
                        spec["compensation_rows"],
                        spec["worker_id"],
                        spec["payroll_period"],
                        spec["pay_item_code"],
                        spec["registry"],
                        spec["policy"],
                        employment_from=spec.get("employment_from"),
                        employment_to=spec.get("employment_to"),
                        payable_from=payable_from,
                        payable_to=payable_to,
                    )
                if eligibility_trace is not None:
                    result["eligibility"] = eligibility_trace

            elif node_type == "base":
                raw_terms = spec.get("terms")
                if not isinstance(raw_terms, list):
                    raise DependencyResolutionError(f"{code}.terms must be a list")
                terms = []
                dependencies = []
                for term in raw_terms:
                    dependency = _node_reference(term)
                    if dependency is None:
                        terms.append(term)
                    else:
                        dependencies.append(dependency)
                        terms.append({"value": _resolved_value(resolve_node(dependency))})
                result = calculate_base(code, terms, resolved_sources)

            elif node_type == "derived":
                raw_operands = spec.get("operands")
                if not isinstance(raw_operands, list):
                    raise DependencyResolutionError(f"{code}.operands must be a list")
                operands = []
                dependencies = []
                for operand in raw_operands:
                    dependency = _node_reference(operand)
                    if dependency is None:
                        if not isinstance(operand, Mapping) or "value" not in operand:
                            raise DependencyResolutionError(
                                f"{code} operand must define value or node"
                            )
                        operands.append(operand["value"])
                    else:
                        dependencies.append(dependency)
                        operands.append(_resolved_value(resolve_node(dependency)))
                result = calculate_derived_value(
                    code,
                    spec.get("operation"),
                    operands,
                )

            elif node_type == "component":
                raw_inputs = {
                    "unit_amount": spec.get("unit_amount"),
                    "quantity": spec.get("quantity", {"value": 1}),
                    "multiplier": spec.get("multiplier", {"value": 1}),
                }
                component_spec = {}
                dependencies = []
                for field, input_spec in raw_inputs.items():
                    dependency = _node_reference(input_spec)
                    if dependency is None:
                        component_spec[field] = input_spec
                    else:
                        dependencies.append(dependency)
                        component_spec[field] = {
                            "value": _resolved_value(resolve_node(dependency))
                        }
                result = calculate_component_from_spec(
                    component_spec,
                    resolved_sources,
                )

            else:
                raise DependencyResolutionError(
                    f"{code}: unsupported node type: {node_type!r}"
                )

            result = {
                **result,
                "node_code": code,
                "node_type": node_type,
                "dependencies": dependencies,
            }
            results[code] = result
            return result
        finally:
            visiting.pop()

    for node_code in nodes:
        resolve_node(str(node_code))

    return {
        "results": results,
        "resolution_order": list(results.keys()),
    }
