#!/usr/bin/env python3
"""Independent Payroll CLI: raw source normalization or review-only calculation.

Commands never issue approvals, close Worktime, commit Ledger transactions or
publish an authorized final payroll register.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running this file directly sets sys.path[0] to payroll-calculator, not the
# repository root. The migrated engine uses Bhandara's public common modules.
# Keep both the portfolio package and local function imports available.
REPO_ROOT = Path(__file__).resolve().parents[2]
FUNCTIONS = Path(__file__).resolve().parent / "functions"
for module_root in (REPO_ROOT, FUNCTIONS):
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

from batch_reporting import BatchReportError, write_batch_outputs
from source_pipeline import BatchInputError, load_manifest, prepare_batch_inputs
from payroll_standalone_report import write_standalone_outputs


def normalize_command(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir).resolve()
    manifest_path = Path(args.manifest).resolve() if args.manifest else input_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    bundle = prepare_batch_inputs(manifest, input_dir=input_dir)
    output = write_batch_outputs(args.output_dir, bundle)
    print(f"Input preparation: {bundle['status']}")
    print(f"Sources: {len(bundle['source_results'])}, issues: {len(bundle['issues'])}")
    for label, filename in output.items():
        print(f"{label}: {filename}")
    return 0 if bundle["status"] == "READY_FOR_CALCULATION" else 2


def calculate_command(args: argparse.Namespace) -> int:
    result = None
    problem = None
    try:
        # Normalize must remain independent of the Payroll engine and its
        # external imports. Import the heavier calculation modules only here.
        from payroll_standalone_input import load_standalone_inputs
        from payroll_standalone_runner import run_standalone_payroll

        inputs = load_standalone_inputs(args.config, scenario_id=args.scenario_id)
        result = run_standalone_payroll(inputs)
    except Exception as exc:
        # Retain evidence even when the existing calculation Gear raises.
        # Exceptions are never interpreted as a valid amount or approval.
        problem = exc
    output = write_standalone_outputs(args.output_dir, result, error=problem)
    for label, filename in output.items():
        print(f"{label}: {filename}")
    if problem is not None:
        print(f"Payroll BLOCKED: {type(problem).__name__}: {problem}", file=sys.stderr)
        return 2
    assert result is not None
    print(f"Payroll: {result['status']} (review only, not finalized)")
    if result.get("policy_selection") and result["policy_selection"].get("scenario_id"):
        selected = result["policy_selection"]
        print(f"Policy scenario: {selected['scenario_id']} "
              f"(profile={selected['profile_id']}, kind={selected['scenario_kind']}, "
              f"source={selected['selection_source']})")
    print(f"Workers calculated: {len(result['composition']['worker_runs'])}; "
          f"review/error findings: {len(result['issues'])}")
    # This CLI cannot finalize tax, insurance, approvals or ledger, even with
    # fully calculated amounts. Report review-required as a nonzero exit code.
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Payroll inputs or calculate an independent review-only Payroll")
    sub = parser.add_subparsers(dest="command", required=True)
    normalize = sub.add_parser("normalize", help="Map company source files into canonical rows")
    normalize.add_argument("--input-dir", required=True, help="Directory containing raw source files")
    normalize.add_argument("--manifest", help="JSON mapping manifest; defaults to input-dir/manifest.json")
    normalize.add_argument("--output-dir", required=True, help="New output directory for canonical rows/reports")

    calculate = sub.add_parser("calculate", help="Calculate review-only Payroll from explicit local file inputs")
    calculate.add_argument("--config", required=True, help="JSON file declaring monthly Payroll inputs")
    calculate.add_argument("--scenario-id", help="Override config/catalog default Payroll policy scenario")
    calculate.add_argument("--output-dir", required=True, help="New, private output directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "normalize":
            return normalize_command(args)
        if args.command == "calculate":
            return calculate_command(args)
    except (BatchInputError, BatchReportError, OSError, ValueError) as exc:
        print(f"Payroll CLI failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
