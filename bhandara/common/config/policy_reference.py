"""Resolve versioned JSON policy sources without owning business rules.

Only public Portfolio resources or caller-registered local input roots may be
read. Remote Drive/agent sources must be authenticated and materialized by the
private caller first. This resolver is NOT a native Slack file read lease.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PORTFOLIO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY = Path(__file__).with_name("policy-defaults.json")
MAX_JSON_BYTES = 1_048_576


class PolicyReferenceError(ValueError):
    """Unusable explicit policy reference or missing registered default."""


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    value: dict[str, Any]
    source_kind: str
    sha256: str
    used_default: bool


def _object_without_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in items:
        if name in result:
            raise PolicyReferenceError("DUPLICATE_JSON_KEY")
        result[name] = value
    return result


def _parse_object(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_JSON_BYTES:
        raise PolicyReferenceError("POLICY_TOO_LARGE")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_object_without_duplicates)
    except (UnicodeError, ValueError) as exc:
        raise PolicyReferenceError("POLICY_JSON_INVALID") from exc
    if type(result) is not dict:
        raise PolicyReferenceError("POLICY_OBJECT_REQUIRED")
    return result


def _inline(value: Any) -> tuple[dict[str, Any], str]:
    if type(value) is not dict:
        raise PolicyReferenceError("POLICY_OBJECT_REQUIRED")
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PolicyReferenceError("POLICY_JSON_INVALID") from exc
    return _parse_object(raw), hashlib.sha256(raw).hexdigest()


def _safe_file(root: Path, relative: Any) -> bytes:
    if type(relative) is not str or not relative or len(relative) > 512:
        raise PolicyReferenceError("POLICY_PATH_INVALID")
    path = Path(relative)
    if (path.is_absolute() or "\\" in relative or
            any(part in (".", "..", "") for part in relative.split("/"))):
        raise PolicyReferenceError("POLICY_PATH_INVALID")
    if root.is_symlink() or not root.is_dir():
        raise PolicyReferenceError("POLICY_ROOT_INVALID")
    current = root
    for component in path.parts:
        current = current / component
        if current.is_symlink():
            raise PolicyReferenceError("POLICY_SYMLINK_FORBIDDEN")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_file = current.resolve(strict=True)
        resolved_file.relative_to(resolved_root)
        if not resolved_file.is_file():
            raise PolicyReferenceError("POLICY_FILE_INVALID")
        if resolved_file.stat().st_size > MAX_JSON_BYTES:
            raise PolicyReferenceError("POLICY_TOO_LARGE")
        return resolved_file.read_bytes()
    except (OSError, ValueError) as exc:
        raise PolicyReferenceError("POLICY_FILE_UNAVAILABLE") from exc


def default_reference(module_id: str, policy_role: str) -> dict[str, Any] | None:
    """Read reviewed public defaults; None means NO safe default registered."""
    if (type(module_id) is not str or type(policy_role) is not str
            or not module_id or not policy_role):
        raise PolicyReferenceError("POLICY_ROLE_INVALID")
    registry = _parse_object(_safe_file(REGISTRY.parent, REGISTRY.name))
    if registry.get("schema_version") != "1.0" or type(registry.get("modules")) is not dict:
        raise PolicyReferenceError("POLICY_REGISTRY_INVALID")
    roles = registry["modules"].get(module_id)
    if type(roles) is not dict:
        raise PolicyReferenceError("POLICY_MODULE_UNKNOWN")
    ref = roles.get(policy_role)
    if ref is None:
        return None
    if type(ref) is not dict:
        raise PolicyReferenceError("POLICY_REGISTRY_INVALID")
    return dict(ref)


def resolve_policy_reference(
    module_id: str,
    policy_role: str,
    explicit_reference: Mapping[str, Any] | None = None,
    *,
    input_roots: Mapping[str, Path] | None = None,
) -> ResolvedPolicy:
    """Use explicit inline/file source, or the registered public default.

    This selects a COMPLETE policy object; it does not merge partial business
    rules or infer missing employee facts. An invalid explicit source BLOCKS.
    """
    default = explicit_reference is None
    ref = default_reference(module_id, policy_role) if default else explicit_reference
    if ref is None:
        raise PolicyReferenceError("POLICY_DEFAULT_UNAVAILABLE")
    if not isinstance(ref, Mapping):
        raise PolicyReferenceError("POLICY_REFERENCE_INVALID")
    kind = ref.get("kind")
    if kind == "inline":
        if set(ref) != {"kind", "value"}:
            raise PolicyReferenceError("POLICY_REFERENCE_INVALID")
        value, digest = _inline(ref["value"])
    elif kind == "file":
        if set(ref) != {"kind", "root", "path"}:
            raise PolicyReferenceError("POLICY_REFERENCE_INVALID")
        root_id = ref["root"]
        if type(root_id) is not str:
            raise PolicyReferenceError("POLICY_ROOT_INVALID")
        roots: dict[str, Path] = {"portfolio": PORTFOLIO_ROOT}
        for name, root in (input_roots or {}).items():
            if (type(name) is not str or not name or name == "portfolio"
                    or not isinstance(root, Path)):
                raise PolicyReferenceError("POLICY_ROOT_INVALID")
            roots[name] = root
        if root_id not in roots:
            raise PolicyReferenceError("POLICY_ROOT_UNKNOWN")
        raw = _safe_file(roots[root_id], ref["path"])
        value, digest = _parse_object(raw), hashlib.sha256(raw).hexdigest()
    else:
        raise PolicyReferenceError("POLICY_REFERENCE_INVALID")
    return ResolvedPolicy(value=value, source_kind=str(kind),
                          sha256=digest, used_default=default)
