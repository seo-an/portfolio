#!/usr/bin/env python3
"""Server-only parity gate for the preserved PRIVATE synthetic PTO Golden.

This command reads the original Gearbox synthetic fixture on its existing
read-only mount and stores all outputs in a private temporary directory.
It does not upload fixture contents or reveal result values.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()

    if not args.fixture_root.is_dir() or not args.baseline.is_file():
        print("PTO_GOLDEN_INVALID: synthetic fixture directory or Golden JSON not found",
              file=sys.stderr)
        return 2

    runner = importlib.import_module("bhandara.pto-calculator.runner")
    verifier = importlib.import_module(
        "bhandara.pto-calculator.examples.compare_private_golden"
    )
    config = {
        "schema_version": "1.0",
        "period": {"from": "2026-07-01", "to": "2026-07-31"},
        "files": {
            "employees": "employee.xlsx",
            "schedule": "work-schedule.xlsx",
            "assignments": "work-schedule-assignment.xlsx",
            "monthly_schedule": ["work-records/2026/2026-07-schedule.xlsx"],
            "attendance": ["work-records/2026/2026-07-attendance.xlsx"],
            "events": None,
        },
        "employee_allowlist": ["E001", "E005", "E020"],
    }
    with TemporaryDirectory(prefix="bhandara-pto-golden-gate-") as private_dir:
        root = Path(private_dir)
        config_path = root / "config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        config_path.chmod(0o600)
        try:
            status, outputs = runner.run_pto(
                config_path=config_path,
                input_dir=args.fixture_root,
                output_dir=root / "output",
            )
            if status.value == "ERROR":
                print("PTO_GOLDEN_INVALID: candidate had input/calculation errors",
                      file=sys.stderr)
                return 2
            differences = verifier.check(
                args.baseline,
                outputs["pto-result.json"],
            )
        except Exception as exc:
            print(f"PTO_GOLDEN_INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        if differences:
            print(f"PTO_GOLDEN_DIFF: {len(differences)} differences")
            for entry in differences[:50]:
                print(f"  {entry.pointer}: {entry.reason}")
            return 1
    print("PTO_GOLDEN_PASS: synthetic E001/E005/E020 July 2026 parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
