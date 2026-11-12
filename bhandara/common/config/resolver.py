"""Resolve calculator-local Python string variables into a plain JSON-compatible mapping.

The common layer never imports another calculator. External complete JSON
configurations bypass local settings entirely; no silent value merging.
"""
from __future__ import annotations

import importlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping


class SettingsContractError(ValueError):
    """Invalid caller input or module-local variable; no fallback."""


def _validate(value: Any, kind: str, name: str) -> str:
    if type(value) is not str or (not value and kind != "optional_file") or value != value.strip():
        raise SettingsContractError(f"{name} must be a nonempty string without surrounding spaces")
    if kind == "optional_file" and value == "":
        return value
    if kind == "month":
        try:
            month = date.fromisoformat(value + "-01")
        except ValueError as exc:
            raise SettingsContractError(f"{name} must be YYYY-MM") from exc
        if month.strftime("%Y-%m") != value:
            raise SettingsContractError(f"{name} must be YYYY-MM")
    elif kind in ("file", "optional_file"):
        path = Path(value)
        if (path.is_absolute() or len(path.parts) == 0
                or any(part in (".", "..") for part in path.parts)
                or "\\" in value or value.endswith("/")):
            raise SettingsContractError(f"{name} must be a safe relative file path")
    else:
        raise SettingsContractError("unsupported local setting kind")
    return value


def load_local_settings(module_id: str, fields: Mapping[str, str]) -> dict[str, str]:
    """Load ONLY the requested calculator's user_settings.py string constants."""
    if module_id not in ("pto-calculator", "worktime-calculator", "payroll-calculator"):
        raise SettingsContractError("unregistered calculator")
    module = importlib.import_module(f"bhandara.{module_id}.user_settings")
    result: dict[str, str] = {}
    for name, kind in fields.items():
        if not name.isupper() or not name.replace("_", "").isalpha():
            raise SettingsContractError("invalid local setting field")
        if not hasattr(module, name):
            raise SettingsContractError(f"{module_id}: required local setting {name} missing")
        result[name] = _validate(getattr(module, name), kind, name)
    return result


def resolve_config(
    external: Mapping[str, Any] | None,
    local_builder: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Choose exactly one complete configuration source, then JSON-normalize.

    Explicit external JSON is authoritative. Missing fields in that JSON
    are errors for the calculator's own validator, never secretly filled
    from the user's editable Python defaults.
    """
    selected = external if external is not None else local_builder()
    if not isinstance(selected, Mapping):
        raise SettingsContractError("resolved calculator config must be an object")
    try:
        encoded = json.dumps(dict(selected), ensure_ascii=False, allow_nan=False)
        decoded = json.loads(encoded)
    except (ValueError, TypeError, OverflowError) as exc:
        raise SettingsContractError("calculator settings must be JSON-compatible") from exc
    if type(decoded) is not dict:
        raise SettingsContractError("calculator settings must resolve to an object")
    return decoded
