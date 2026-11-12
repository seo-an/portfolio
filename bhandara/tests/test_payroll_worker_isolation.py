"""Public Bhandara Payroll CLI worker isolation tests (synthetic only)."""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from bhandara.tests.test_payroll_migration import _create_synthetic_inputs

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "bhandara/payroll-calculator"


def call(config: Path, output: Path, *, isolate: bool) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(ROOT / "run.py"), "bhandara", "payroll-calculator",
            "--config", str(config), "--output-dir", str(output)]
    if isolate:
        argv.append("--isolate-worker-failures")
    return subprocess.run(argv, cwd=ROOT, check=False,
                          capture_output=True, text=True, timeout=90)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bad_pay_item(root: Path, worker: str, code: str) -> None:
    path = root / "payroll-input.xlsx"
    book = load_workbook(path)
    try:
        sheet = book.active
        sheet.append([worker, code, 1000, None, None, None, None, "synthetic invalid code"])
        book.save(path)
    finally:
        book.close()


class PublicPayrollWorkerIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bhandara-payroll-worker-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = _create_synthetic_inputs(self.root)

    def test_normal_batch_results_unchanged_when_option_enabled(self):
        first = call(self.config, self.root / "normal", isolate=False)
        second = call(self.config, self.root / "isolated", isolate=True)
        self.assertEqual(first.returncode, 2, first.stderr)
        self.assertEqual(second.returncode, 2, second.stderr)
        for name in ("payroll-calculation.json", "payroll-review.json",
                     "policy-resolution.json"):
            self.assertEqual(read(self.root / "normal" / name),
                             read(self.root / "isolated" / name))
        self.assertNotIn("PAYROLL_BATCH_RECOVERY_USED", second.stdout)

    def test_one_worker_failure_preserves_other_result_and_review(self):
        bad_pay_item(self.root, "W2", "UNKNOWN_PAY_ITEM_FOR_SYNTHETIC_TEST")
        baseline = call(self.config, self.root / "baseline", isolate=False)
        self.assertEqual(baseline.returncode, 2)
        self.assertFalse((self.root / "baseline/payroll-calculation.json").exists())
        selected = call(self.config, self.root / "isolated", isolate=True)
        self.assertEqual(selected.returncode, 2, selected.stderr)
        calc = read(self.root / "isolated/payroll-calculation.json")
        review = read(self.root / "isolated/payroll-review.json")
        self.assertEqual(calc["status"], "BLOCKED")
        self.assertEqual(review["status"], "BLOCKED")
        self.assertEqual(set(calc["composition"]["worker_runs"]), {"W1"})
        self.assertEqual(review["expected_workers"], ["W1", "W2"])
        self.assertEqual(review["actual_workers"], ["W1"])
        self.assertTrue(any(item.get("worker_id") == "W2"
                            and item.get("code") == "WORKER_PAYROLL_CALCULATION_FAILED"
                            for item in review["issues"]))
        self.assertTrue((self.root / "isolated/payroll-calculation.xlsx").is_file())
        self.assertIs(review["finalizable"], False)
        self.assertIs(calc["finalizable"], False)
        self.assertIs(review["ledger_committed"], False)
        self.assertFalse(any(self.root.glob(".payroll-worker-isolation-*")))
        self.assertNotIn("W1", selected.stdout)
        self.assertNotIn("W2", selected.stdout)

    def test_all_worker_failures_leave_review_only(self):
        bad_pay_item(self.root, "W1", "UNKNOWN_PAY_ITEM_FOR_SYNTHETIC_TEST")
        bad_pay_item(self.root, "W2", "OTHER_UNKNOWN_PAY_ITEM_FOR_SYNTHETIC_TEST")
        selected = call(self.config, self.root / "isolated", isolate=True)
        self.assertEqual(selected.returncode, 2)
        self.assertFalse((self.root / "isolated/payroll-calculation.json").exists())
        self.assertTrue((self.root / "isolated/payroll-review.xlsx").is_file())
        review = read(self.root / "isolated/payroll-review.json")
        self.assertEqual(review["status"], "BLOCKED")
        self.assertEqual(review["issues"][0]["code"], "PAYROLL_CALCULATION_FAILED")

    def test_unassignable_source_worker_is_not_silently_discarded(self):
        bad_pay_item(self.root, "UNEXPECTED_WORKER", "performance_bonus")
        selected = call(self.config, self.root / "isolated", isolate=True)
        self.assertEqual(selected.returncode, 2)
        self.assertFalse((self.root / "isolated/payroll-calculation.json").exists())
        self.assertEqual(read(self.root / "isolated/payroll-review.json")["status"],
                         "BLOCKED")
        self.assertNotIn("UNEXPECTED_WORKER", selected.stdout)
        self.assertNotIn("UNEXPECTED_WORKER", selected.stderr)

    def test_flag_rejected_outside_direct_payroll_calculate(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "bhandara", "worktime-calculator",
             "--isolate-worker-failures"],
            capture_output=True, text=True, cwd=ROOT, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("PAYROLL_INVALID", proc.stderr)

    def test_public_modules_do_not_import_gearbox(self):
        import ast
        for filename in ("isolation_cli.py", "worker_isolation.py"):
            tree = ast.parse((MODULE / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith("gearbox"))
                if isinstance(node, ast.Import):
                    self.assertTrue(all(
                        not member.name.startswith("gearbox") for member in node.names
                    ))

    def test_isolation_never_retries_if_batch_succeeds(self):
        isolate = importlib.import_module("bhandara.payroll-calculator.isolation_cli")
        expected = object()
        with patch.object(isolate, "load_standalone_inputs", return_value={}), \
             patch.object(isolate, "run_standalone_payroll", return_value=expected), \
             patch.object(isolate, "recover_employee_payroll") as retry:
            result = isolate._calculate_with_optional_recovery(
                self.config, self.root / "unused", None
            )
        self.assertIs(result, expected)
        retry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
