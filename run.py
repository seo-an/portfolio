#!/usr/bin/env python3
"""Portfolio CLI for published Bhandara modules and Golden comparisons."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Public Portfolio CLI: PTO, Worktime, Payroll and Golden comparisons."
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
    bhandara.add_argument("--operation", choices=("calculate", "normalize"),
                          help="Payroll only; defaults to review-only calculate")
    bhandara.add_argument("--manifest", help="Payroll normalize manifest")
    bhandara.add_argument("--scenario-id", help="Payroll policy scenario override")
    bhandara.add_argument("--isolate-worker-failures", action="store_true",
                          help="Payroll calculate only: retry workers independently after batch failure")
    bhandara.add_argument(
        "--period", help="YYYY-MM for automatic shared Excel input (no JSON editing)")
    bhandara.add_argument(
        "--paths-config", help="Optional advanced JSON role-path overrides")
    bhandara.add_argument(
        "--worktime-result", help="Explicit Worktime result JSON for Payroll Excel mode")
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
        if args.isolate_worker_failures and (
            args.module_id != "payroll-calculator"
            or args.operation == "normalize"
            or args.period is not None
        ):
            print("PAYROLL_INVALID: worker isolation requires direct Payroll calculate mode",
                  file=sys.stderr)
            return 2
        # In Base + single-calculator installations, never pretend an absent
        # calculator exists or leak a Python traceback from import_module().
        if args.module_id in ("pto-calculator", "worktime-calculator", "payroll-calculator"):
            from pathlib import Path
            installed = Path(__file__).resolve().parent / "bhandara" / args.module_id
            if not (installed / "module.json").is_file():
                print(
                    f"UNAVAILABLE: {args.module_id!r} is not installed in this portfolio. "
                    "No calculations were performed.",
                    file=sys.stderr,
                )
                return 2
        shared_root = None
        overrides = None
        if args.period is not None:
            from pathlib import Path
            import json
            from bhandara.common.io.input_layout import (
                DEFAULT_INPUT_ROOT, InputLayoutError, ROLE_PATHS, period_bounds,
            )
            try:
                period_bounds(args.period)
                if args.config or args.normalized or args.manifest:
                    raise InputLayoutError(
                        "--period cannot be combined with legacy --config, "
                        "--normalized or --manifest; use one input mode"
                    )
                if args.operation == "normalize":
                    raise InputLayoutError("Payroll normalize uses --input-dir without --period")
                shared_root = Path(args.input_dir).resolve() if args.input_dir else DEFAULT_INPUT_ROOT
                if args.paths_config:
                    with open(args.paths_config, encoding="utf-8") as stream:
                        data = json.load(stream)
                    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
                        raise InputLayoutError("paths config requires {files: {module: {role: path}}}")
                    overrides = data["files"]
                    for section, values in overrides.items():
                        if section not in ROLE_PATHS or not isinstance(values, dict):
                            raise InputLayoutError(f"unknown input override section: {section}")
                        for key, filename in values.items():
                            if key not in ROLE_PATHS[section] or not isinstance(filename, str):
                                raise InputLayoutError(
                                    f"unknown input role or invalid path: {section}.{key}"
                                )
            except (InputLayoutError, OSError, ValueError, TypeError) as exc:
                print(f"INPUT_INVALID: {exc}", file=sys.stderr)
                return 2
        elif args.paths_config or args.worktime_result:
            print("INPUT_INVALID: --paths-config and --worktime-result require --period", file=sys.stderr)
            return 2
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
                if shared_root is not None:
                    from bhandara.common.io.input_layout import (
                        choose_path, period_bounds, role, write_auto_config,
                    )
                    from datetime import date
                    start, end = period_bounds(args.period)
                    yyyy_mm = args.period
                    yyyy = yyyy_mm[:4]
                    pto_files = {
                        "employees": "common/employee.xlsx",
                        "schedule": "pto/work-schedule.xlsx",
                        "assignments": "pto/work-schedule-assignment.xlsx",
                        "monthly_schedule": [
                            f"pto/work-records/{yyyy}/{yyyy_mm}-schedule.xlsx"
                        ],
                        "attendance": [
                            f"pto/work-records/{yyyy}/{yyyy_mm}-attendance.xlsx"
                        ],
                        "events": None,
                    }
                    if overrides:
                        for role_name, filename in overrides.get("common", {}).items():
                            if role_name == "employees":
                                pto_files["employees"] = filename
                        for role_name, filename in overrides.get("pto", {}).items():
                            if role_name in ("schedule", "assignments", "events"):
                                pto_files[role_name] = filename
                    for key in ("employees", "schedule", "assignments"):
                        choose_path(shared_root, pto_files[key])
                    for key in ("monthly_schedule", "attendance"):
                        for filename in pto_files[key]:
                            choose_path(shared_root, filename)
                    events = pto_files["events"] or "pto/employee-events.xlsx"
                    if (shared_root / events).is_file():
                        pto_files["events"] = events
                    elif pto_files["events"]:
                        choose_path(shared_root, events)
                    outputs = Path(args.output_dir) if args.output_dir else (
                        shared_root.parent / "output" / "pto-calculator"
                    )
                    config = write_auto_config(
                        shared_root,
                        f"pto-auto-{yyyy_mm}.json",
                        {
                            "schema_version": "1.0",
                            "period": {"from": start, "to": end},
                            "files": pto_files,
                            "employee_allowlist": [],
                        },
                        generated_dir=outputs.resolve().parent / "config",
                    )
                    inputs = shared_root
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
            if shared_root is not None:
                from importlib import import_module
                from bhandara.common.io.input_layout import InputLayoutError
                worktime = import_module("bhandara.worktime-calculator.shared_excel")
                from bhandara.common.io.input_layout import next_result_dir
                try:
                    return worktime.run_shared_excel(
                        shared_root, args.period,
                        args.output_dir or str(
                            next_result_dir(shared_root, "worktime-calculator")),
                        overrides=overrides,
                    )
                except (InputLayoutError, ValueError, OSError) as exc:
                    print(f"WORKTIME_INPUT_INVALID: {type(exc).__name__}: {exc}",
                          file=sys.stderr)
                    return 2
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
        if args.module_id == "payroll-calculator":
            from importlib import import_module
            payroll = import_module("bhandara.payroll-calculator.run")
            if shared_root is not None:
                from bhandara.common.io.input_layout import InputLayoutError
                builder = import_module("bhandara.payroll-calculator.shared_excel")
                from bhandara.common.io.input_layout import next_result_dir
                try:
                    output = Path(args.output_dir) if args.output_dir else (
                        next_result_dir(shared_root, "payroll-calculator")
                    )
                    config = builder.prepare_shared_payroll(
                        shared_root,
                        args.period,
                        overrides=overrides,
                        worktime_result_path=(
                            Path(args.worktime_result) if args.worktime_result else None
                        ),
                        generated_dir=output.resolve().parent / "config",
                    )
                except (InputLayoutError, ValueError, OSError) as exc:
                    print(f"PAYROLL_INPUT_INVALID: {type(exc).__name__}: {exc}",
                          file=sys.stderr)
                    return 2
                exit_code = payroll.main([
                    "calculate", "--config", str(config), "--output-dir",
                    str(output),
                ])
                # Contract audit artifacts belong to the same output run.
                # They are not part of the old calculation/approval engine.
                generated = json.loads(config.read_text(encoding="utf-8"))
                if generated.get("contract_review_path") and output.is_dir():
                    import shutil
                    from importlib import import_module
                    report = Path(generated["contract_review_path"])
                    shutil.copy2(report, output / "contract-basis-review.json")
                    shutil.copy2(
                        generated["contract_compensation_path"],
                        output / "contract-derived-compensation.xlsx",
                    )
                    contract = import_module("bhandara.payroll-calculator.contract_adapter")
                    contract.export_review_workbook(
                        report, output / "contract-basis-review.xlsx"
                    )
                    print("CONTRACT_BASE_STATUS: REVIEW_REQUIRED (no payroll approval)")
                    print("CONTRACT_BASE_ARTIFACT: " + str(output / "contract-basis-review.xlsx"))
                return exit_code
            if args.operation == "normalize":
                if not all((args.input_dir, args.output_dir)):
                    print(
                        "PAYROLL_INVALID: normalize requires --input-dir and --output-dir",
                        file=sys.stderr,
                    )
                    return 2
                cli = ["normalize", "--input-dir", args.input_dir,
                       "--output-dir", args.output_dir]
                if args.manifest:
                    cli.extend(["--manifest", args.manifest])
                return payroll.main(cli)
            if not all((args.config, args.output_dir)):
                print(
                    "PAYROLL_INVALID: calculate requires --config and --output-dir",
                    file=sys.stderr,
                )
                return 2
            if args.isolate_worker_failures:
                isolation = import_module("bhandara.payroll-calculator.isolation_cli")
                return isolation.calculate_cli(
                    args.config, args.output_dir, scenario_id=args.scenario_id,
                )
            cli = ["calculate", "--config", args.config,
                   "--output-dir", args.output_dir]
            if args.scenario_id:
                cli.extend(["--scenario-id", args.scenario_id])
            return payroll.main(cli)
        print(
            f"UNAVAILABLE: {args.module_id!r} is not installed in this portfolio. "
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
