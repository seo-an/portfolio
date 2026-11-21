"""Explicit single Paid Time Off Module entrypoint.

This is a module-only adapter, not a fallback to the full Tool Flow.
The private operator config must authorize exactly one requested step.
Other PTO modules, Worktime, Payroll and Workflow are never invoked.
"""
from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
import sys

from bhandara.common.runtime.workspace import ensure_tool_workspace

MODULES = frozenset({"entitlement", "deduction-quantity", "usage-ledger", "closing"})


class ModuleScopeError(ValueError):
    """A caller tried to widen or invent the operator-authorized module scope."""


def _dispatch_single(config: dict, module: str) -> Path:
    """Invoke only the domain runner named by the validated module ID."""
    tool = import_module("bhandara.paid-time-off.tool_cli")
    if module == "entitlement":
        return tool._run_entitlement(config)
    if module == "deduction-quantity":
        return tool._run_deduction(config)
    if module == "usage-ledger":
        return tool._run_usage(config, {})
    if module == "closing":
        return tool._run_closing(config, {})
    raise ModuleScopeError("MODULE_UNKNOWN")


def execute_module(config_path: str | Path, *, module: str) -> dict[str, str]:
    """Run exactly one configured Module with no implicit prerequisites.

    A dependent Module must consume explicitly named prior-result files;
    it must not create earlier entitlement, deduction or usage results.
    """
    if type(module) is not str or module not in MODULES:
        raise ModuleScopeError("MODULE_UNKNOWN")
    tool = import_module("bhandara.paid-time-off.tool_cli")
    config = tool._read_config(Path(config_path).resolve())
    if config["steps"] != [module]:
        raise ModuleScopeError("MODULE_SCOPE_NOT_AUTHORIZED")
    if (config["output_root"] / config["run_id"]).exists():
        raise ModuleScopeError("MODULE_RUN_ID_EXISTS")
    ensure_tool_workspace("paid-time-off")
    result = _dispatch_single(config, module)
    return {module: str(result)}


def main(config_path: str | Path, *, module: str) -> int:
    try:
        artifacts = execute_module(config_path, module=module)
    except ModuleScopeError as exc:
        print(f"PTO_MODULE_BLOCKED: {exc}", file=sys.stderr)
        return 2
    except Exception:
        # Do not expose private paths, source IDs, contents or policy details.
        print("PTO_MODULE_BLOCKED: MODULE_INPUT_OR_EXECUTION_FAILED", file=sys.stderr)
        return 2
    print(json.dumps({
        "tool": "paid-time-off", "module": module,
        "review_only": True, "approved": False, "artifacts": artifacts,
    }, ensure_ascii=False))
    return 0
