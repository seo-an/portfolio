#!/usr/bin/env python3
"""Public Bhandara CLI: three JSON-driven Tools, Workflow, and Normalizer."""
from __future__ import annotations

import argparse
from importlib import import_module
from pathlib import Path
import sys


TOOLS = frozenset({"paid-time-off", "worktime", "payroll", "workflow"})
CONFIG_NAMES = {
    "paid-time-off": "paid-time-off.json",
    "worktime": "worktime.json",
    "payroll": "payroll.json",
    "workflow": "workflow.json",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bhandara Tool CLI")
    commands = parser.add_subparsers(dest="collection", required=True)
    bhandara = commands.add_parser("bhandara", help="Run a Bhandara Tool")
    bhandara.add_argument("module_id", help="Tool or common-normalizer")
    bhandara.add_argument("--config", help="Private JSON settings path")
    bhandara.add_argument("--module", help="One independently approved Module ID (PTO only)")
    bhandara.add_argument("--data-root", help="Normalizer private workspace")
    bhandara.add_argument("--run-id", help="Normalizer isolated run ID")
    bhandara.add_argument("--source", help="Normalizer source path")
    return parser


def _run_json_tool(args: argparse.Namespace) -> int:
    if args.module is not None:
        if args.module_id != "paid-time-off" or not args.config:
            print("MODULE_INVALID: supported only with PTO --config", file=sys.stderr)
            return 2
        if any((args.data_root, args.run_id, args.source)):
            print("MODULE_INVALID: unexpected normalizer arguments", file=sys.stderr)
            return 2
        module_cli = import_module("bhandara.paid-time-off.module_cli")
        return module_cli.main(args.config, module=args.module)
    if any((args.data_root, args.run_id, args.source)):
        print("TOOL_INVALID: --data-root, --run-id and --source "
              "are common-normalizer-only", file=sys.stderr)
        return 2
    name = args.module_id
    cfg = (Path(args.config) if args.config
           else Path(__file__).resolve().parent / "bhandara" / "data"
           / "config" / CONFIG_NAMES[name])
    if name == "workflow":
        from bhandara.workflow import main as workflow_main
        return workflow_main(cfg)
    tool = import_module(f"bhandara.{name}.tool_cli")
    return tool.main(cfg)


def _run_normalizer(args: argparse.Namespace) -> int:
    if args.module is not None:
        print("MODULE_INVALID: common-normalizer does not accept --module", file=sys.stderr)
        return 2
    from bhandara.common.module.normalizer.runner import (
        NormalizerRunError, run_normalizer,
    )
    from bhandara.common.module.normalizer.paths import NormalizerPathError

    try:
        status, paths = run_normalizer(
            args.data_root, run_id=args.run_id,
            source_path=args.source, mapping_path=args.config,
        )
    except (NormalizerRunError, NormalizerPathError, OSError, ValueError) as exc:
        print(f"NORMALIZER_INVALID: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    print(f"NORMALIZER_STATUS: {status}")
    for name, path in paths.items():
        print(f"NORMALIZER_ARTIFACT: {name} -> {path}")
    return 0 if status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        if argv is None:
            raise
        return int(exc.code)
    if args.collection != "bhandara":
        return 2
    if args.module_id in TOOLS:
        return _run_json_tool(args)
    if args.module_id == "common-normalizer":
        return _run_normalizer(args)
    print(f"UNAVAILABLE: {args.module_id!r} is not a supported Tool. "
          "No calculations were performed.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
