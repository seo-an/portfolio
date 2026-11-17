"""Filesystem contract for the independent Common normalizer.

Only this module's own files are used. It never imports Common library code
or another calculator. The default input/output folders sit next to runner.py;
production callers should provide a private data root to keep sensitive files
outside the Git checkout.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

MODULE_ID = "common-normalizer"
MODULE_DIR = Path(__file__).resolve().parent
_SOURCE_CHECKOUT = MODULE_DIR.parents[3]
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_MANIFEST = MODULE_DIR / "module.json"


class NormalizerPathError(ValueError):
    """Invalid or unsafe module input/output path."""


@dataclass(frozen=True, slots=True)
class NormalizerPaths:
    run_id: str
    source: Path
    mapping: Path
    output: Path


def module_root(private_data_root: str | Path | None = None) -> Path:
    """Use source module folders by default; private external workspace in production."""
    if private_data_root is None:
        return MODULE_DIR
    root = Path(private_data_root).resolve()
    if root == _SOURCE_CHECKOUT or root.is_relative_to(_SOURCE_CHECKOUT):
        raise NormalizerPathError("private data root must be outside public Git checkout")
    result = root / MODULE_ID
    if result.is_symlink():
        raise NormalizerPathError("module workspace cannot be a symlink")
    return result


def _manifest() -> dict:
    try:
        value = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NormalizerPathError("normalizer module.json unreadable") from exc
    if (not isinstance(value, dict) or value.get("module_id") != MODULE_ID
            or not isinstance(value.get("module_version"), str)
            or not isinstance(value.get("input_roles"), dict)
            or set(value["input_roles"]) != {"source", "mapping"}):
        raise NormalizerPathError("normalizer manifest invalid")
    return value


def _input_path(
    input_dir: Path, role: str, declared: str, supplied: str | Path | None,
) -> Path:
    raw = declared if supplied is None else str(supplied)
    if not raw or raw != raw.strip() or "\x00" in raw:
        raise NormalizerPathError(f"{role}: invalid input path")
    selected = Path(raw)
    if not selected.is_absolute():
        if ("\\" in raw or ":" in raw or any(
            part in (".", "..", "") for part in raw.split("/")
        )):
            raise NormalizerPathError(f"{role}: unsafe relative input path")
        selected = input_dir / selected
    target = selected.resolve()
    if (not Path(raw).is_absolute()
            and not target.is_relative_to(input_dir.resolve())):
        raise NormalizerPathError(f"{role}: input escapes module input directory")
    if not target.is_file():
        raise NormalizerPathError(f"{role}: selected input file not found")
    return target


def resolve_paths(
    private_data_root: str | Path | None = None,
    *,
    run_id: str,
    source_path: str | Path | None = None,
    mapping_path: str | Path | None = None,
) -> NormalizerPaths:
    """Exact input priority: explicit path, otherwise this module's input folder.

    Explicit absolute files can be accepted from other module outputs only
    after the caller has authorized the path. No implicit fallback or copying.
    """
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise NormalizerPathError("run_id must be an explicit safe identifier")
    home = module_root(private_data_root)
    input_dir, output_dir = home / "input", home / "output"
    if input_dir.is_symlink() or output_dir.is_symlink():
        raise NormalizerPathError("input/output directory cannot be a symlink")
    output = output_dir / run_id
    if output.is_symlink():
        raise NormalizerPathError("run output cannot be a symlink")
    roles = _manifest()["input_roles"]
    # Editable defaults are local to this executable module.
    from . import user_settings
    defaults = {
        "source": user_settings.SOURCE_FILE,
        "mapping": user_settings.MAPPING_FILE,
    }
    for role, filename in defaults.items():
        if (not isinstance(filename, str) or not filename
                or filename != filename.strip()):
            raise NormalizerPathError(f"{role}: invalid user setting")
        # The manifest still owns declared role names and supported files.
        if role not in roles:
            raise NormalizerPathError(f"{role}: role missing in manifest")
    return NormalizerPaths(
        run_id=run_id,
        source=_input_path(input_dir, "source", defaults["source"], source_path),
        mapping=_input_path(input_dir, "mapping", defaults["mapping"], mapping_path),
        output=output,
    )
