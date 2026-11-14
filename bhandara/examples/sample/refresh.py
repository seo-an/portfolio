#!/usr/bin/env python3
"""Replace the canonical public 80-person sample with freshly generated Excel.

This is a one-way refresh of the SAME sample, not a new fixture version.
All files are synthetic. Run with --apply in a disposable CI/branch checkout.
No real employee files, approval records, or external services are accessed.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "bhandara/examples/sample"
GENERATOR = SAMPLE / "generate.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("canonical_sample", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("sample generator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _swap_canonical_input(generated: Path) -> None:
    """Swap entire input tree, including removal of retired contract sheets."""
    source = generated / "input"
    required = (
        "common/employee.xlsx",
        "common/id-map.xlsx",
        "pto/employee-events.xlsx",
        "payroll/pay-contract.xlsx",
        "payroll/company-policy.json",
        "payroll/worktime-result.json",
        "worktime/attendance.xlsx",
    )
    if not all((source / item).is_file() for item in required):
        raise RuntimeError("incomplete synthetic workbook generation")
    if any((source / item).exists() for item in (
        "payroll/pay-contract-components.xlsx",
        "payroll/service-contracts.xlsx",
        "payroll/service-work-records.xlsx",
    )):
        raise RuntimeError("retired contract layout remains in sample")

    current = SAMPLE / "input"
    staged = SAMPLE / ".refresh-input-next"
    backup = SAMPLE / ".refresh-input-prev"
    if staged.exists() or backup.exists():
        raise RuntimeError("incomplete previous sample refresh; manual inspection required")
    shutil.copytree(source, staged)
    try:
        if current.exists():
            os.replace(current, backup)
        try:
            os.replace(staged, current)
        except BaseException:
            if backup.exists() and not current.exists():
                os.replace(backup, current)
            raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    if backup.exists():
        shutil.rmtree(backup)


def refresh_sample(*, apply: bool) -> dict:
    """Regenerate in an isolated directory; apply only on explicit request."""
    with tempfile.TemporaryDirectory(prefix="bhandara-sample-80-") as temp:
        output = Path(temp) / "sample"
        _load_generator().generate(output)
        if apply:
            _swap_canonical_input(output)
            shutil.copy2(output / "test-cases.json", SAMPLE / "test-cases.json")
            shutil.copy2(output / "manifest.json", SAMPLE / "sample-manifest.json")
        return {
            "status": "UPDATED" if apply else "GENERATED_ONLY",
            "employee_count": 80,
            "input_dir": str(SAMPLE / "input" if apply else output / "input"),
            "synthetic_only": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = refresh_sample(apply=args.apply)
    print(
        f"SAMPLE_80={result['status']} "
        "EMPLOYEES=80 SYNTHETIC_ONLY=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
