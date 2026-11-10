"""Select a complete Payroll company policy from a versioned scenario catalog.

The selected policy is a *plain existing engine policy*; calculation rules
never live here. A scenario can replace only company-policy fields, not legal
policy, employee facts, Compensation, Worktime records, or approval receipts.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping


class PolicyCatalogError(ValueError):
    pass


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_REQUIRED_POLICY = ("ordinary_wage", "proration", "worktime_pay", "amount_processing")
_DYNAMIC_MAPS = {("proration",), ("ordinary_wage", "pay_items"),
                 ("worktime_pay", "base_component_policy")}


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise PolicyCatalogError(f"{label} must be a nonempty safe identifier")
    return value


def policy_sha256(policy: Mapping[str, Any]) -> str:
    content = json.dumps(policy, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _validate_policy(policy: Any, label: str) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise PolicyCatalogError(f"{label} must be a policy object")
    if any(not isinstance(k, str) or not k.strip() for k in policy):
        raise PolicyCatalogError(f"{label} has an invalid policy field name")
    missing = [key for key in _REQUIRED_POLICY if not isinstance(policy.get(key), dict)]
    if missing:
        raise PolicyCatalogError(f"{label} missing policy objects: {', '.join(missing)}")
    return deepcopy(policy)


def _merge(base: dict[str, Any], changes: Mapping[str, Any],
           path: tuple[str, ...] = ()) -> dict[str, Any]:
    if not isinstance(changes, dict) or not changes:
        raise PolicyCatalogError("overrides must be a nonempty object")
    result = deepcopy(base)
    for key, value in changes.items():
        if not isinstance(key, str) or not key.strip():
            raise PolicyCatalogError("override field names must be nonempty strings")
        next_path = (*path, key)
        if key not in result and path not in _DYNAMIC_MAPS:
            raise PolicyCatalogError("unknown company-policy override path: " +
                                     ".".join(next_path))
        if isinstance(value, dict):
            if isinstance(result.get(key), dict):
                result[key] = _merge(result[key], value, next_path)
            elif key not in result and path in _DYNAMIC_MAPS:
                # New pay-item policies can be declared only in known dynamic
                # maps, never as unrecognized top-level / calculation fields.
                result[key] = deepcopy(value)
            else:
                raise PolicyCatalogError("cannot merge object into non-object: " +
                                         ".".join(next_path))
        else:
            if isinstance(result.get(key), dict):
                raise PolicyCatalogError("cannot replace policy object with scalar: " +
                                         ".".join(next_path))
            if isinstance(value, (list, dict)):
                raise PolicyCatalogError("override values must be JSON scalars")
            result[key] = deepcopy(value)
    return result


def _difference(left: Any, right: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        changes = []
        for key in sorted(set(left) | set(right)):
            changes.extend(_difference(left.get(key), right.get(key), (*path, key)))
        return changes
    if left == right:
        return []
    return [{"field": ".".join(path), "before": deepcopy(left), "after": deepcopy(right)}]


def _resolve_profiles(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    profiles = catalog.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise PolicyCatalogError("catalog.profiles must be a nonempty object")
    for key in profiles:
        _id(key, "profile id")
    cached: dict[str, dict[str, Any]] = {}
    visiting: set[str] = set()

    def resolve(name: str) -> dict[str, Any]:
        if name in cached:
            return cached[name]
        if name in visiting:
            raise PolicyCatalogError(f"policy profile inheritance cycle: {name}")
        item = profiles.get(name)
        if not isinstance(item, dict):
            raise PolicyCatalogError(f"profile missing or invalid: {name}")
        visiting.add(name)
        try:
            unknown = set(item) - {"policy", "inherits", "overrides", "description"}
            if unknown:
                raise PolicyCatalogError(f"profile {name}: unsupported keys: {sorted(unknown)}")
            if "inherits" in item:
                parent = _id(item["inherits"], f"{name}.inherits")
                if parent not in profiles:
                    raise PolicyCatalogError(f"profile {name}: parent not found: {parent}")
                if "policy" in item:
                    raise PolicyCatalogError(f"profile {name}: policy and inherits are exclusive")
                if "overrides" not in item:
                    raise PolicyCatalogError(f"profile {name}: overrides required with inherits")
                inherited = resolve(parent)
                policy = _merge(inherited["policy"], item["overrides"])
                chain = [*inherited["inheritance"], name]
            else:
                if "overrides" in item:
                    raise PolicyCatalogError(f"profile {name}: overrides require inherits")
                policy = _validate_policy(item.get("policy"), name)
                chain = [name]
            _validate_policy(policy, name)
            cached[name] = {"policy": policy, "inheritance": chain}
            return cached[name]
        finally:
            visiting.remove(name)

    for name in profiles:
        resolve(name)
    return cached


def resolve_policy_catalog(catalog: Mapping[str, Any],
                           scenario_id: str | None = None) -> dict[str, Any]:
    """Resolve explicit scenario, or a catalog-declared default, without guessing."""
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "0.2":
        raise PolicyCatalogError("policy catalog schema_version must be 0.2")
    if set(catalog) - {"schema_version", "catalog_id", "default_scenario_id",
                       "profiles", "scenarios", "description"}:
        raise PolicyCatalogError("unsupported top-level policy catalog keys")
    catalog_id = _id(catalog.get("catalog_id"), "catalog_id")
    profiles = _resolve_profiles(catalog)
    scenarios = catalog.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        raise PolicyCatalogError("catalog.scenarios must be a nonempty object")
    default_id = _id(catalog.get("default_scenario_id"), "default_scenario_id")
    for name, item in scenarios.items():
        _id(name, "scenario id")
        if not isinstance(item, dict) or set(item) - {"profile_id", "kind", "description"}:
            raise PolicyCatalogError(f"scenario {name}: invalid keys or object")
        if item.get("kind") not in ("operational", "simulation"):
            raise PolicyCatalogError(f"scenario {name}: kind must be operational or simulation")
        if _id(item.get("profile_id"), f"{name}.profile_id") not in profiles:
            raise PolicyCatalogError(f"scenario {name}: unknown profile_id")
    if default_id not in scenarios:
        raise PolicyCatalogError("default_scenario_id must reference an existing scenario")
    chosen = _id(scenario_id, "scenario_id") if scenario_id is not None else default_id
    if chosen not in scenarios:
        raise PolicyCatalogError(f"scenario not found: {chosen}")
    profile_id = scenarios[chosen]["profile_id"]
    default_profile = profiles[scenarios[default_id]["profile_id"]]["policy"]
    selected = profiles[profile_id]["policy"]
    return {
        "policy": deepcopy(selected),
        "selection": {
            "catalog_id": catalog_id,
            "schema_version": "0.2",
            "scenario_id": chosen,
            "profile_id": profile_id,
            "scenario_kind": scenarios[chosen]["kind"],
            "selection_source": "catalog_default" if scenario_id is None else "explicit",
            "default_scenario_id": default_id,
            "inheritance": list(profiles[profile_id]["inheritance"]),
            "policy_sha256": policy_sha256(selected),
            "changes_from_default": _difference(default_profile, selected),
        },
    }
