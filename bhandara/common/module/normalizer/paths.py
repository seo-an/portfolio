"""Private per-run file locations for this standalone normalizer.

No imports from bhandara.common's shared library, Gearbox, or calculators.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_ID = "common-normalizer"
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_SOURCE_CHECKOUT = Path(__file__).resolve().parents[4]
_MANIFEST = Path(__file__).with_name("module.json")


class NormalizerPathError(ValueError):
    """Unsafe or missing input, output or module declaration."""


@dataclass(frozen=True, slots=True)
class NormalizerPaths:
    run_id: str
    source: Path
    mapping: Path
    output: Path


def _manifest() -> dict:
    try:
        value = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NormalizerPathError("normalizer module.json unreadable") from exc
    if (not isinstance(value, dict) or value.get("module_id") != _ID
            or not isinstance(value.get("module_version"), str)
            or not isinstance(value.get("input_roles"), dict)):
        raise NormalizerPathError("normalizer manifest invalid")
    return value


def _input_path(input_dir: Path, role: str, declared: str, supplied: str | Path | None) -> Path:
    raw = declared if supplied is None else str(supplied)
    if not raw or raw != raw.strip() or "\x00" in raw:
        raise NormalizerPathError(f"{role}: invalid input path")
    path = Path(raw)
    if not path.is_absolute():
        if ("\\" in raw or ":" in raw
                or any(item in (".", "..", "") for item in raw.split("/"))):
            raise NormalizerPathError(f"{role}: unsafe relative input path")
        path = input_dir / path
    resolved = path.resolve()
    if not Path(raw).is_absolute() and not resolved.is_relative_to(input_dir.resolve()):
        raise NormalizerPathError(f"{role}: input escapes module input directory")
    if not resolved.is_file():
        raise NormalizerPathError(f"{role}: declared input not found")
    return resolved


def resolve_paths(
    private_data_root: str | Path,
    *,
    run_id: str,
    source_path: str | Path | None = None,
    mapping_path: str | Path | None = None,
) -> NormalizerPaths:
    """Explicit role file wins; invalid explicit input never falls back."""
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise NormalizerPathError("run_id must be an explicit safe identifier")
    root = Path(private_data_root).resolve()
    if root == _SOURCE_CHECKOUT or root.is_relative_to(_SOURCE_CHECKOUT):
        raise NormalizerPathError("private data root must be outside public Git checkout")
    module = root / _ID
    if module.is_symlink():
        raise NormalizerPathError("module workspace cannot be symlink")
    input_dir = module / "input"
    output_dir = module / "output"
    if input_dir.is_symlink() or output_dir.is_symlink():
        raise NormalizerPathError("module input/output directory cannot be symlink")
    target = output_dir / run_id
    if target.is_symlink():
        raise NormalizerPathError("run output cannot be symlink")
    manifest = _manifest()
    roles = manifest["input_roles"]
    if set(roles) != {"source", "mapping"}:
        raise NormalizerPathError("normalizer roles must declare source and mapping")
    for role, name in roles.items():
        if not isinstance(name, str) or not name:
            raise NormalizerPathError(f"invalid declared role: {role}")
    return NormalizerPaths(
        run_id=run_id,
        source=_input_path(input_dir, "source", roles["source"], source_path),
        mapping=_input_path(input_dir, "mapping", roles["mapping"], mapping_path),
        output=target,
    )
