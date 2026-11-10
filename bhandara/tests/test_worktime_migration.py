"""Migration-only tests: exact legacy blob identity and relocated CLI parity.

No functionality review or new policy expectations. All records are synthetic.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "bhandara/worktime-calculator"
MANIFEST = MODULE / "migration-manifest.json"


def synthetic_normalized() -> dict:
    employees = [
        {"employee_id": "E01", "worker_id": "EP0001"},
        {"employee_id": "E02", "worker_id": "EP0002"},
    ]
    schedule = [
        {"employee_id": "E01", "worker_id": "EP0001",
         "work_date": "2026-09-15", "day_type": "WORK",
         "scheduled_start": "09:00", "scheduled_end": "18:00", "break_min": 60},
        {"employee_id": "E02", "worker_id": "EP0002",
         "work_date": "2026-09-15", "day_type": "WORK",
         "scheduled_start": "10:00", "scheduled_end": "19:00", "break_min": 60},
    ]
    attendance = [
        {"employee_id": "E01", "worker_id": "EP0001",
         "work_date": "2026-09-15", "clock_in": "09:00",
         "clock_out": "18:00", "break_min": 60},
        {"employee_id": "E02", "worker_id": "EP0002",
         "work_date": "2026-09-15", "clock_in": "10:00",
         "clock_out": "19:00", "break_min": 60},
    ]
    sources = {}
    for name, rows in (
        ("employees", employees), ("schedule", schedule), ("attendance", attendance)
    ):
        sources[name] = {
            "rows": rows, "source_sha256": f"synthetic-{name}",
            "lineage": [
                {"status": "ACCEPTED", "row_number": i + 2, "issue_codes": []}
                for i in range(len(rows))
            ],
        }
    return {
        "schema_version": "0.1", "status": "READY_FOR_CALCULATION",
        "batch_id": "synthetic-worktime-migration", "sources": sources,
    }


def synthetic_config(*, approved: bool) -> dict:
    return {
        "schema_version": "0.1", "period_from": "2026-09-15",
        "period_to": "2026-09-15",
        "worktime_assignments": {
            employee: {
                "worktime_system": "standard", "rule_ref": "labor_standard_50_53",
            }
            for employee in ("E01", "E02")
        },
        "approvals": [
            {"employee_id": employee, "work_date": "2026-09-15",
             "attendance_approval_ref": f"APPROVAL-{employee}"}
            for employee in ("E01", "E02")
        ] if approved else [],
    }


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii")
                        + b"\0" + data).hexdigest()


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )


def _worksheet_values(path: Path) -> dict[str, list[tuple]]:
    wb = load_workbook(path, read_only=True, data_only=False)
    try:
        return {
            sheet.title: [tuple(row) for row in sheet.iter_rows(values_only=True)]
            for sheet in wb.worksheets
        }
    finally:
        wb.close()


class WorktimeMigrationTests(unittest.TestCase):
    def test_all_ten_original_sources_copied_byte_identically(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["migration_type"], "unchanged_copy")
        self.assertEqual(len(manifest["files"]), 10)
        for entry in manifest["files"]:
            with self.subTest(destination=entry["destination"]):
                expected = entry["source_git_blob_sha"]
                path = ROOT / entry["destination"]
                self.assertTrue(path.is_file())
                self.assertEqual(_git_blob_sha(path.read_bytes()), expected)

    def test_public_module_manifest_declares_unclosed_contract(self):
        info = json.loads((MODULE / "module.json").read_text(encoding="utf-8"))
        self.assertEqual(info["module_id"], "worktime-calculator")
        self.assertEqual(info["status"], "review_only")
        self.assertIs(info["non_finalization_guards"]["finalizable"], False)
        self.assertIsNone(info["non_finalization_guards"]["close_receipt"])

    def _run_same_input(self, *, approved: bool, status: str, exit_code: int):
        with tempfile.TemporaryDirectory(prefix="bhandara-worktime-test-") as tmp:
            root = Path(tmp)
            normalized = root / "normalized-input.json"
            config = root / "worktime-config.json"
            normalized.write_text(
                json.dumps(synthetic_normalized(), ensure_ascii=False),
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(synthetic_config(approved=approved), ensure_ascii=False),
                encoding="utf-8",
            )
            legacy_output = root / "legacy"
            public_output = root / "public"
            old = _run_cli([
                str(MODULE / "run.py"), "calculate",
                "--normalized", str(normalized),
                "--config", str(config),
                "--output-dir", str(legacy_output),
            ])
            new = _run_cli([
                str(ROOT / "run.py"), "bhandara", "worktime-calculator",
                "--normalized", str(normalized),
                "--config", str(config),
                "--output-dir", str(public_output),
            ])
            self.assertEqual(old.returncode, exit_code, old.stderr)
            self.assertEqual(new.returncode, exit_code, new.stderr)
            self.assertIn(status, old.stdout)
            self.assertIn(status, new.stdout)
            for filename in ("worktime-result.json", "worktime-review.json"):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        json.loads((legacy_output / filename).read_text()),
                        json.loads((public_output / filename).read_text()),
                    )
            self.assertEqual(
                _worksheet_values(legacy_output / "worktime-review.xlsx"),
                _worksheet_values(public_output / "worktime-review.xlsx"),
            )
            data = json.loads((public_output / "worktime-result.json").read_text())
            self.assertEqual(data["status"], status)
            self.assertIs(data["finalizable"], False)
            self.assertIs(data["coverage_verified"], False)
            self.assertIsNone(data["close_receipt"])
            self.assertEqual(len(data["rows"]), 2)

    def test_existing_standalone_vs_public_dispatch_approved_synthetic(self):
        self._run_same_input(
            approved=True, status="CALCULATED_UNCLOSED", exit_code=0,
        )

    def test_existing_standalone_vs_public_dispatch_review_synthetic(self):
        self._run_same_input(
            approved=False, status="REVIEW_REQUIRED", exit_code=2,
        )

    def test_public_cli_missing_required_args_is_invalid(self):
        result = _run_cli([
            str(ROOT / "run.py"), "bhandara", "worktime-calculator",
        ])
        self.assertEqual(result.returncode, 2)
        self.assertIn("WORKTIME_INVALID", result.stderr)


if __name__ == "__main__":
    unittest.main()
