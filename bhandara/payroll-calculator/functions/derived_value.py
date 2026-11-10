"""Calculate named derived payroll values from already-resolved operands."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class DerivedValueError(RuntimeError):
    """Raised when a derived value cannot be calculated deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Derived value failed: {message}"
        )


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DerivedValueError(f"{field} must be decimal-compatible") from exc
    if not number.is_finite():
        raise DerivedValueError(f"{field} must be finite")
    if number < 0:
        raise DerivedValueError(f"{field} must not be negative")
    return number


def calculate_derived_value(
    derived_code: Any,
    operation: Any,
    operands: Any,
) -> dict[str, Any]:
    """Calculate one named value without resolving dependencies or rounding."""
    code = str(derived_code).strip() if derived_code is not None else ""
    if not code:
        raise DerivedValueError("derived_code must not be empty")

    op = str(operation).strip().lower() if operation is not None else ""
    supported = {"add", "subtract", "multiply", "divide"}
    if op not in supported:
        raise DerivedValueError(f"unsupported operation: {operation!r}")

    if not isinstance(operands, list) or len(operands) != 2:
        raise DerivedValueError("operands must contain exactly two values")

    left = _decimal(operands[0], "operands[0]")
    right = _decimal(operands[1], "operands[1]")

    if op == "add":
        value = left + right
    elif op == "subtract":
        value = left - right
    elif op == "multiply":
        value = left * right
    else:
        if right == 0:
            raise DerivedValueError("division by zero is not allowed")
        value = left / right

    if value < 0:
        raise DerivedValueError("derived value must not be negative")

    return {
        "derived_code": code,
        "operation": op,
        "operands": [left, right],
        "calculated_value": value,
        "calculation_trace": {
            "operation": op,
            "operands": [left, right],
        },
    }
