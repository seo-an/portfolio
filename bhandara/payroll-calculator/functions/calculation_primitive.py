"""Calculate one payroll component with a reusable Decimal primitive."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class CalculationPrimitiveError(RuntimeError):
    """Raised when a component cannot be calculated deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Calculation primitive failed: {message}"
        )


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CalculationPrimitiveError(
            f"{field} must be decimal-compatible"
        ) from exc

    if not number.is_finite():
        raise CalculationPrimitiveError(f"{field} must be finite")
    if number < 0:
        raise CalculationPrimitiveError(f"{field} must not be negative")
    return number


def calculate_component(
    unit_amount: Any,
    quantity: Any = 1,
    multiplier: Any = 1,
) -> dict[str, Decimal]:
    """Calculate one positive-magnitude component without rounding.

    Direction (payment/deduction), proration, aggregation, references, and
    adjustments belong to later layers and are intentionally not handled here.
    """
    resolved_unit_amount = _decimal(unit_amount, "unit_amount")
    resolved_quantity = _decimal(quantity, "quantity")
    resolved_multiplier = _decimal(multiplier, "multiplier")

    return {
        "unit_amount": resolved_unit_amount,
        "quantity": resolved_quantity,
        "multiplier": resolved_multiplier,
        "calculated_amount": (
            resolved_unit_amount * resolved_quantity * resolved_multiplier
        ),
    }
