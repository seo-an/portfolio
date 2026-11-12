"""Generic scalar coercion used by typed Bhandara input contracts.

No company code, pay-item rule, approval, or calculator policy belongs here.
A caller may map its own source aliases/value strings before conversion.
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


class UnsupportedScalarType(ValueError):
    """The requested primitive conversion kind is not supported."""


def convert_scalar(value: Any, *, kind: str = "str", fmt: str | None = None) -> Any:
    """Convert a primitive to the existing canonical JSON-compatible type."""
    kind = str(kind).lower()
    if kind == "str":
        return str(value).strip()
    if kind == "date":
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        parsed = (
            datetime.strptime(str(value).strip(), fmt).date()
            if fmt else date.fromisoformat(str(value).strip())
        )
        return parsed.isoformat()
    if kind == "time":
        if isinstance(value, datetime):
            parsed = value.timetz()
        elif isinstance(value, time):
            parsed = value
        else:
            parsed = (
                datetime.strptime(str(value).strip(), fmt).time()
                if fmt else time.fromisoformat(str(value).strip())
            )
        if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
            raise ValueError("clock time must have naive minute precision")
        return parsed.isoformat(timespec="minutes")
    if kind == "datetime":
        parsed = value if isinstance(value, datetime) else (
            datetime.strptime(str(value).strip(), fmt)
            if fmt else datetime.fromisoformat(str(value).strip())
        )
        if parsed.second or parsed.microsecond:
            raise ValueError("datetime must have minute precision")
        return parsed.isoformat(timespec="minutes")
    if kind == "decimal":
        if isinstance(value, bool):
            raise ValueError("boolean is not a decimal")
        number = Decimal(str(value).strip().replace(",", ""))
        if not number.is_finite():
            raise ValueError("non-finite decimal")
        return format(number, "f")
    if kind == "int":
        if isinstance(value, bool):
            raise ValueError("boolean is not an integer")
        number = Decimal(str(value).strip().replace(",", ""))
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("integer required")
        return int(number)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in ("true", "1", "yes", "y"):
            return True
        if lowered in ("false", "0", "no", "n"):
            return False
        raise ValueError("boolean mapping requires explicit value_map or true/false")
    raise UnsupportedScalarType(f"unsupported field type: {kind}")
