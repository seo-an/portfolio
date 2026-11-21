"""Single PTO Module contract: synthetic inputs and no implicit Flow calls."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[2]
MODULE = importlib.import_module("bhandara.paid-time-off.module_cli")
TOOL = importlib.import_module("bhandara.paid-time-off.tool_cli")


class StandalonePtoModuleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="pto-single-module-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.input_root = self.root / "input"
        self.output_root = self.root / "output"
        self.config = self.root / "private.json"
        self.input_root.mkdir()
        self.base = {
            "schema_version": "1.0", "tool": "paid-time-off",
            "run_id": "synthetic-001", "as_of_date": "2026-11-30",
            "policy_id": "SYNTHETIC_REVIEW",
            "input_root": str(self.input_root),
            "output_root": str(self.output_root),
            "steps": ["deduction-quantity"], "files": {},
        }

    def save(self, **changes):
        self.config.write_text(json.dumps({**self.base, **changes}),
                               encoding="utf-8")

    def invoke(self, name="deduction-quantity", tool="paid-time-off"):
        return subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "bhandara", tool,
             "--config", str(self.config), "--module", name],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def test_deduction_alone_generates_only_one_real_excel(self):
        file = self.input_root / "approved-leave.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.title = "승인휴가"
        sheet.append(("request_id", "employee_id", "leave_date",
                      "leave_type", "duration_hours"))
        sheet.append(("SYN-001", "SYN-EMP", "2026-11-20", "연차", 8))
        book.save(file)
        book.close()
        self.save(files={"approved_leave": "approved-leave.xlsx"})
        done = self.invoke()
        self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result["module"], "deduction-quantity")
        self.assertEqual(list(result["artifacts"]), ["deduction-quantity"])
        self.assertFalse(result["approved"])
        folder = self.output_root / "synthetic-001"
        output = folder / "deduction-quantity-result.xlsx"
        self.assertTrue(output.is_file())
        self.assertEqual([p.name for p in folder.iterdir()],
                         ["deduction-quantity-result.xlsx"])
        workbook = load_workbook(output, read_only=True)
        try:
            self.assertIn("차감상세", workbook.sheetnames)
        finally:
            workbook.close()
        self.assertEqual(self.invoke().returncode, 2)
        self.assertTrue(output.is_file())

    def test_never_reduces_multi_step_config_to_implicit_single_step(self):
        self.save(steps=["entitlement", "deduction-quantity"])
        with patch.object(MODULE, "_dispatch_single") as dispatched:
            result = self.invoke()
        # Subprocess verifies the same boundary; no runner needs to start.
        self.assertEqual(result.returncode, 2)
        self.assertIn("MODULE_SCOPE_NOT_AUTHORIZED", result.stderr)
        dispatched.assert_not_called()
        self.assertFalse(self.output_root.exists())

    def test_exact_module_dispatch_does_not_execute_sibling_runners(self):
        modules = {
            "entitlement": "_run_entitlement",
            "deduction-quantity": "_run_deduction",
            "usage-ledger": "_run_usage",
            "closing": "_run_closing",
        }
        for name, expected in modules.items():
            with self.subTest(name=name):
                self.save(steps=[name])
                config = {
                    "steps": [name], "output_root": self.output_root,
                    "run_id": "safe-1",
                }
                with (
                    patch.object(TOOL, "_read_config", return_value=config),
                    patch.object(MODULE, "ensure_tool_workspace"),
                    patch.object(TOOL, "_run_entitlement", return_value=Path("/synthetic/a.xlsx")) as ent,
                    patch.object(TOOL, "_run_deduction", return_value=Path("/synthetic/b.xlsx")) as ded,
                    patch.object(TOOL, "_run_usage", return_value=Path("/synthetic/c.xlsx")) as usage,
                    patch.object(TOOL, "_run_closing", return_value=Path("/synthetic/d.xlsx")) as closing,
                ):
                    output = MODULE.execute_module(self.config, module=name)
                self.assertEqual(list(output), [name])
                for method, mocked in {
                    "_run_entitlement": ent, "_run_deduction": ded,
                    "_run_usage": usage, "_run_closing": closing,
                }.items():
                    self.assertEqual(mocked.call_count, int(method == expected))

    def test_wrong_tool_or_unknown_module_fail_closed(self):
        self.save()
        self.assertEqual(self.invoke("calculation").returncode, 2)
        self.assertIn("MODULE_UNKNOWN", self.invoke("calculation").stderr)
        self.assertEqual(self.invoke(tool="payroll").returncode, 2)
        self.assertEqual(self.invoke(tool="worktime").returncode, 2)
        self.assertFalse(self.output_root.exists())

    def test_bad_config_error_does_not_leak_private_paths(self):
        self.save(files={"employee": "private-employee-name.xlsx"})
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("MODULE_INPUT_OR_EXECUTION_FAILED", result.stderr)
        self.assertNotIn("private-employee-name", result.stderr)


if __name__ == "__main__":
    unittest.main()
