#!/usr/bin/env python3
"""Portfolio CLI for published Bhandara modules and Golden comparisons."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Public Portfolio CLI: PTO, Worktime and Golden comparisons."
    )
    commands = parser.add_subparsers(dest="collection", required=True)
    bhandara = commands.add_parser(
        "bhandara", help="Run an installed Bhandara module"
    )
    bhandara.add_argument("module_id", help="Requested module identifier")
    bhandara.add_argument("--config", help="Path to module config JSON")
    bhandara.add_argument("--input-dir", help="Local Excel input directory")
    bhandara.add_argument("--normalized", help="Worktime canonical normalized-input.json")
    bhandara.add_argument("--output-dir", help="Local output directory")
    compare = commands.add_parser(
        "compare-golden", help="Compare two private Golden JSON artifacts or Payroll output folders"
    )
    compare.add_argument("--profile", required=True, choices=(
        "strict-json", "workflow-run", "pto-golden", "normalized-input",
        "worktime-result", "payroll-calculation", "payroll-review",
        "policy-resolution", "provisional-register", "payroll-workflow",
    ))
    compare.add_argument("--expected", required=True, help="Existing Golden file/output directory")
    compare.add_argument("--actual", required=True, help="New candidate file/output directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.collection == "bhandara":
        if args.module_id == "pto-calculator":
            from importlib import import_module
            from pathlib import Path
            from bhandara.common.contracts.findings import RunStatus
            from bhandara.common.runtime.artifacts import ArtifactError

            module = import_module("bhandara.pto-calculator.runner")
            config = Path(args.config) if args.config else module.MODULE_DIR / "config.json"
            inputs = Path(args.input_dir) if args.input_dir else module.LOCAL_DATA_DIR / "input"
            outputs = Path(args.output_dir) if args.output_dir else module.LOCAL_DATA_DIR / "output"
            try:
                status, paths = module.run_pto(
                    config_path=config, input_dir=inputs, output_dir=outputs
                )
            except (module.PTORunError, module.PTOInputError, ArtifactError,
                    OSError, ValueError) as exc:
                print(f"PTO_INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 2
            print(f"PTO_STATUS: {status.value}")
            for name, path in paths.items():
                print(f"PTO_ARTIFACT: {name} -> {path}")
            return {RunStatus.PASS: 0, RunStatus.REVIEW_REQUIRED: 1,
                    RunStatus.ERROR: 2}[status]
        if args.module_id == "worktime-calculator":
            if not all((args.normalized, args.config, args.output_dir)):
                print(
                    "WORKTIME_INVALID: --normalized, --config and --output-dir required",
                    file=sys.stderr,
                )
                return 2
            from importlib import import_module
            worktime = import_module("bhandara.worktime-calculator.run")
            return worktime.main([
                "calculate",
                "--normalized", args.normalized,
                "--config", args.config,
                "--output-dir", args.output_dir,
            ])
        print(
            f"UNAVAILABLE: {args.module_id!r} is not installed in this Phase 1 bootstrap. "
            "No calculations were performed.",
            file=sys.stderr,
        )
        return 2
    if args.collection == "compare-golden":
        from pathlib import Path
        from bhandara.common.validation.golden_compare import GoldenCompareError, compare

        try:
            differences = compare(Path(args.expected), Path(args.actual), args.profile)
        except (GoldenCompareError, OSError) as exc:
            print(f"GOLDEN_INVALID: {exc}", file=sys.stderr)
            return 2
        if differences:
            print(f"GOLDEN_DIFF: {len(differences)} difference(s) (maximum 50 reported)")
            for item in differences:
                print(f"  {item.pointer}: {item.reason}")
            return 1
        print(f"GOLDEN_PASS: {args.profile}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
