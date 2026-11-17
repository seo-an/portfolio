"""Module-owned file paths for standalone Bhandara tools (v2 contract).

This module plans and validates paths only. It does not run calculators,
infer a company policy, import another calculator, copy inputs, or create
output directories. Gearbox remains responsible for caller authorization,
private storage, cache retention, and cleanup.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class ModuleIOError(ValueError):
    """A module's declared file role or concrete input/output path is invalid."""


_MODULE_NAME = re.compile(r"(?:common|[a-z][a-z0-9-]*-calculator)\Z")
_ROLE_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_BHANDARA_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ModuleIOContract:
    module_id: str
    module_version: str
    input_roles: Mapping[str, str]
    output_files: frozenset[str]


@dataclass(frozen=True, slots=True)
class ResolvedInput:
    role: str
    path: Path
    source: str  # "default" or "explicit"; never inferred from another run


def _relative_file(value: object, label: str) -> str:
    """Validate a declared or caller-relative path without normalizing traversal."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise ModuleIOError(f"{label}: nonempty relative filename required")
    if ("\\" in value or "\x00" in value or ":" in value
            or value.startswith("/") or any(
                part in ("", ".", "..") for part in value.split("/")
            )):
        raise ModuleIOError(f"{label}: unsafe relative filename")
    return value


def _module_name(module_id: str) -> str:
    if not isinstance(module_id, str) or not _MODULE_NAME.fullmatch(module_id):
        raise ModuleIOError("invalid Bhandara module_id")
    return module_id


def _declared_outputs(raw: object) -> frozenset[str]:
    if isinstance(raw, list):
        groups = [raw]
    elif isinstance(raw, dict):
        groups = list(raw.values())
    else:
        raise ModuleIOError("module.json: output_files must be a list or grouped lists")
    names: set[str] = set()
    for group in groups:
        if not isinstance(group, list):
            raise ModuleIOError("module.json: output file group must be a list")
        for filename in group:
            name = _relative_file(filename, "output_files")
            if "/" in name:
                raise ModuleIOError("output file names must be flat filenames")
            names.add(name)
    if not names:
        raise ModuleIOError("module.json: no output files declared")
    return frozenset(names)


def load_module_io_contract(
    module_id: str, *, bhandara_root: Path | None = None,
) -> ModuleIOContract:
    """Read only the requested module's manifest, not other installed modules.

    The legacy shared_excel_input.default_root describes the old CLI. V2 paths
    instead use the caller-supplied private_data_root / module_id / input.
    Existing declared relative filenames remain unchanged during migration.
    """
    module_id = _module_name(module_id)
    root = Path(bhandara_root or _BHANDARA_ROOT).resolve()
    manifest = root / module_id / "module.json"
    if not manifest.resolve().is_relative_to(root) or not manifest.is_file():
        raise ModuleIOError(f"{module_id}: module.json not found in Bhandara root")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModuleIOError(f"{module_id}: unreadable module.json") from exc
    if not isinstance(data, dict) or data.get("module_id") != module_id:
        raise ModuleIOError(f"{module_id}: manifest identity mismatch")
    version = data.get("module_version")
    if not isinstance(version, str) or not version.strip():
        raise ModuleIOError(f"{module_id}: invalid module_version")

    # V2 manifests declare their own roles directly. Existing calculators
    # keep the original shared Excel declarations until migrated separately.
    direct = data.get("input_roles")
    if direct is not None:
        if not isinstance(direct, dict):
            raise ModuleIOError(f"{module_id}: input_roles must be an object")
        sections = (("input_roles", direct),)
    else:
        shared = data.get("shared_excel_input")
        if not isinstance(shared, dict) or shared.get("supported") is not True:
            raise ModuleIOError(f"{module_id}: input roles are not declared")
        sections = tuple((section, shared.get(section))
                         for section in ("common_roles", "roles"))
    roles: dict[str, str] = {}
    for section, declared in sections:
        if not isinstance(declared, dict):
            raise ModuleIOError(f"{module_id}: missing {section}")
        for role, filename in declared.items():
            if not isinstance(role, str) or not _ROLE_NAME.fullmatch(role):
                raise ModuleIOError(f"{module_id}: invalid input role")
            if role in roles:
                raise ModuleIOError(f"{module_id}: ambiguous input role {role}")
            roles[role] = _relative_file(filename, f"{section}.{role}")
    if not roles:
        raise ModuleIOError(f"{module_id}: no input roles declared")
    return ModuleIOContract(
        module_id=module_id,
        module_version=version,
        input_roles=roles,
        output_files=_declared_outputs(data.get("output_files")),
    )


def _module_space(private_data_root: Path, module_id: str) -> Path:
    root = Path(private_data_root).resolve()
    # Runtime inputs and outputs must not live in the public source checkout.
    if root.is_relative_to(_BHANDARA_ROOT.parent):
        raise ModuleIOError("private data root must be outside the public Git checkout")
    module = root / module_id
    if module.is_symlink():
        raise ModuleIOError("module workspace must not be a symlink")
    if not module.resolve().is_relative_to(root):
        raise ModuleIOError("module workspace escapes private data root")
    return module


def resolve_input(
    contract: ModuleIOContract,
    private_data_root: Path,
    role: str,
    *,
    explicit_path: str | Path | None = None,
) -> ResolvedInput:
    """Select explicit file first, otherwise the declared module-local default.

    Absolute explicit files may be external, including an earlier module's
    output. Authorization of such paths is the caller's responsibility.
    Relative explicit files are anchored inside THIS module's input directory.
    Invalid explicit input fails closed; it never silently falls back.
    """
    if role not in contract.input_roles:
        raise ModuleIOError(f"{contract.module_id}: unknown input role {role!r}")
    input_dir = _module_space(private_data_root, contract.module_id) / "input"
    if input_dir.is_symlink():
        raise ModuleIOError("input directory must not be a symlink")
    if explicit_path is None:
        selected = _relative_file(contract.input_roles[role], role)
        candidate = input_dir / selected
        source = "default"
    else:
        if not isinstance(explicit_path, (str, Path)):
            raise ModuleIOError(f"{role}: explicit path must be a filename or Path")
        raw = str(explicit_path)
        if not raw or raw != raw.strip() or "\x00" in raw:
            raise ModuleIOError(f"{role}: invalid explicit path")
        provided = Path(raw)
        if provided.is_absolute():
            candidate = provided
        else:
            candidate = input_dir / _relative_file(raw, role)
        source = "explicit"
    target = candidate.resolve()
    if source == "default" or (explicit_path is not None
                                 and not Path(str(explicit_path)).is_absolute()):
        if not target.is_relative_to(input_dir.resolve()):
            raise ModuleIOError(f"{role}: input path escapes module input directory")
    if not target.is_file():
        raise ModuleIOError(f"{role}: {source} input file not found")
    return ResolvedInput(role=role, path=target, source=source)


def output_directory(
    contract: ModuleIOContract, private_data_root: Path, run_id: str,
) -> Path:
    """Return the exact isolated run directory. Never pick 'latest' or create it."""
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ModuleIOError("run_id must be an explicit safe identifier")
    base = _module_space(private_data_root, contract.module_id) / "output"
    run = base / run_id
    if base.is_symlink() or run.is_symlink():
        raise ModuleIOError("output path must not be a symlink")
    if not run.resolve().is_relative_to(base.resolve()):
        raise ModuleIOError("output path escapes module output directory")
    return run


def output_file(
    contract: ModuleIOContract, private_data_root: Path,
    run_id: str, filename: str,
) -> Path:
    """Plan one explicitly declared result path; publication is module-owned."""
    if filename not in contract.output_files:
        raise ModuleIOError(f"{contract.module_id}: undeclared output file")
    return output_directory(contract, private_data_root, run_id) / filename
