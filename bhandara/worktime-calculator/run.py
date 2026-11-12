#!/usr/bin/env python3
"""Standalone Worktime CLI: canonical source facts -> unclosed daily calculations.

This command cannot approve, period-close, or finalize any payroll.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FUNCTIONS = Path(__file__).resolve().parent / "functions"
if str(FUNCTIONS) not in sys.path:
    sys.path.insert(0, str(FUNCTIONS))

from worktime_batch import WorktimeBatchError, calculate_worktime_batch
from worktime_report import WorktimeReportError, write_worktime_outputs


def _read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def calculate_command(args: argparse.Namespace) -> int:
    source = _read_json(args.normalized)
    config = _read_json(args.config)
    review_path = Path(args.normalized).resolve().with_name("review-report.json")
    review = _read_json(review_path) if review_path.is_file() else None
    result = calculate_worktime_batch(source, config, source_review=review)
    output = write_worktime_outputs(args.output_dir, result)
    print(f"Worktime: {result['status']} (not closed)")
    print(f"Calculated: {len(result['rows'])}; review/error findings: {len(result['issues'])}")
    for name, path in output.items():
        print(f"{name}: {path}")
    return 0 if result["status"] == "CALCULATED_UNCLOSED" else 2


def run_shared_excel(input_root: str | Path, period: str,
                     output_dir: str | Path, *,
                     overrides: dict | None = None) -> int:
    """Accept fixed-name Excel input without a separate normalized JSON step."""
    from .shared_excel import read_shared_worktime

    normalized, config = read_shared_worktime(
        Path(input_root), period, overrides=overrides
    )
    result = calculate_worktime_batch(normalized, config)
    output = write_worktime_outputs(output_dir, result)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    # Unlike an in-memory smoke test, leave the normalized source and mapping
    # configuration as reproducible handoff artifacts.
    for name, payload in (
        ("normalized-input.json", normalized),
        ("worktime-config.json", config),
    ):
        filepath = target / name
        if filepath.exists():
            raise WorktimeBatchError(f"refusing to overwrite existing artifact: {filepath}")
        filepath.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    print(f"Worktime shared Excel: {result['status']} ({len(result['rows'])} daily rows)")
    for key, filepath in output.items():
        print(f"{key}: {filepath}")
    return 0 if result["status"] == "CALCULATED_UNCLOSED" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calculate independent Worktime daily facts; never approve or close a period")
    commands = parser.add_subparsers(dest="command", required=True)
    calculate = commands.add_parser("calculate", help="Worktime calculation from normalized source")
    calculate.add_argument("--normalized", required=True, help="Source-mapping normalized-input.json")
    calculate.add_argument("--config", required=True, help="Worktime assignments, period and approvals")
    calculate.add_argument("--output-dir", required=True, help="New private directory for unclosed results")
    args = parser.parse_args(argv)
    try:
        if args.command == "calculate":
            return calculate_command(args)
    except (WorktimeBatchError, WorktimeReportError, OSError, ValueError, TypeError) as exc:
        print(f"Worktime run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
