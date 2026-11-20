"""Human-discoverable, Git-ignored workspace for JSON Bhandara Tools.

This module creates EMPTY DIRECTORY SHELLS ONLY. It never writes, moves,
deletes, copies, or selects any input. Configured external roots remain
authoritative for a real Tool run.
"""
from __future__ import annotations

import errno
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
TOOLS = frozenset({"paid-time-off", "worktime", "payroll", "workflow"})


class WorkspaceError(ValueError):
    """A workspace directory cannot be safely created."""


def _ensure_directory(path: Path) -> Path:
    """Create a missing directory, never follow a symlink or touch a file."""
    if path.is_symlink():
        raise WorkspaceError("workspace directory cannot be a symlink")
    if path.exists():
        if not path.is_dir():
            raise WorkspaceError("workspace path is not a directory")
        return path
    try:
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError as exc:
        # Fail closed if a concurrent process placed a symlink or a file.
        raise WorkspaceError("workspace directory changed during creation") from exc
    return path


def ensure_tool_workspace(tool: str) -> dict[str, Path]:
    """Create empty directory hints only when the source checkout is writable.

    Hermes mounts .external/portfolio read-only: an EROFS while making
    optional hints is intentionally skipped. The configured input/output
    locations are NEVER replaced with this hint location. Any other
    filesystem error remains fatal; existing files/symlinks fail closed.

    No run_id output directory is created here: Tool executors must reserve
    actual results exclusively, without overwrite.
    """
    if tool not in TOOLS:
        raise WorkspaceError("unknown Bhandara Tool")
    try:
        root = _ensure_directory(DATA_ROOT)
        config = _ensure_directory(root / "config")
        input_root = _ensure_directory(root / "input")
        output_root = _ensure_directory(root / "output")
        _ensure_directory(input_root / "common")
        specific = _ensure_directory(input_root / tool)
        tool_output = _ensure_directory(output_root / tool)
    except OSError as exc:
        if exc.errno != errno.EROFS:
            raise
        # Hermes mounts agent-config (including .external/portfolio) as :ro.
        # Directory hints are OPTIONAL: do not make private, explicitly
        # configured input/output processing depend on writing into code.
        # Never redirect output to an invented location or modify originals.
        return {}
    return {
        "config": config,
        "input": input_root,
        "tool_input": specific,
        "output": output_root,
        "tool_output": tool_output,
    }
