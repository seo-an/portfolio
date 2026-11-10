"""Resolve one referenced source value while preserving provenance."""

from __future__ import annotations

from typing import Any, Mapping


class ReferenceResolutionError(RuntimeError):
    """Raised when a source reference cannot be resolved deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"[payroll-calculator] Reference resolution failed: {message}"
        )


def _required_text(value: Any, field: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ReferenceResolutionError(f"{field} must not be empty")
    return text


def resolve_reference(
    source: Any,
    reference: Any,
    source_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve one direct field from one already-selected source record.

    This layer performs lookup only. It does not derive values, coerce numeric
    types, traverse nested paths, apply defaults, or calculate dependencies.
    """
    resolved_source = _required_text(source, "source")
    resolved_reference = _required_text(reference, "reference")

    if not isinstance(source_record, Mapping):
        raise ReferenceResolutionError("source_record must be a mapping")
    if resolved_reference not in source_record:
        raise ReferenceResolutionError(
            f"{resolved_source}.{resolved_reference} was not found"
        )

    resolved_value = source_record[resolved_reference]
    if resolved_value is None or resolved_value == "":
        raise ReferenceResolutionError(
            f"{resolved_source}.{resolved_reference} has no value"
        )

    return {
        "source": resolved_source,
        "reference": resolved_reference,
        "resolved_value": resolved_value,
    }
