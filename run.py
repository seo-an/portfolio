#!/usr/bin/env python3
"""Portfolio CLI placeholder: deliberately blocks unavailable calculators."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Public Portfolio CLI (Bhandara calculators are not installed yet)."
    )
    commands = parser.add_subparsers(dest="collection", required=True)
    bhandara = commands.add_parser(
        "bhandara", help="Bhandara HR calculators (not released in this bootstrap)"
    )
    bhandara.add_argument("module_id", help="Requested module identifier")
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
