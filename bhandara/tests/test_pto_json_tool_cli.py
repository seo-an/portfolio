"""Public Paid Time Off Tool JSON CLI: synthetic Excel and selection tests."""
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
TOOL = importlib.import_module("bhandara.paid-time-off.tool_cli")


def write_excel(path: Path, sheets: dict[str, tuple[list, list[list]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    for index, (name, (headers, rows)) in enumerate(sheets.items()):
        sheet = book.active if index == 0 else book.create_sheet(name)
        sheet.title = name
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
    book.save(path)
    book.close()


class PTOJsonToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pto-json-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.outputs = self.root / "output"
        self.json = self.root / "pto.json"
        write_excel(self.inputs / "common/employee.xlsx", {
            "재직자": (["employee_id", "hire_date"], [["E001", "2025-01-01"]]),
            "퇴사자": (["employee_id", "hire_date", "termination_date"], []),
        })
        write_excel(self.inputs / "paid-time-off/attendance-result.xlsx", {
            "근태결과": (
                ["employee_id", "period_start", "period_end", "check_type", "attendance_flag"],
                [["E001", "2025-01-01", "2025-12-31", "연간", "80% 충족"]],
            ),
        })
        write_excel(self.inputs / "paid-time-off/approved-leave.xlsx", {
            "승인휴가": (
                ["request_id", "employee_id", "leave_date", "leave_type", "duration_hours"],
                [["R001", "E001", "2026-11-20", "연차", 8]],
            ),
        })
        self.base = {
            "schema_version": "1.0", "tool": "paid-time-off",
            "run_id": "run-202611", "as_of_date": "2026-11-30",
            "policy_id": "SYNTHETIC_POLICY", "basis": "입사일 기준",
            "input_root": str(self.inputs), "output_root": str(self.outputs),
            "steps": ["entitlement", "deduction-quantity"],
            "files": {
                "employee": "common/employee.xlsx",
                "attendance": "paid-time-off/attendance-result.xlsx",
                "approved_leave": "paid-time-off/approved-leave.xlsx",
            },
        }

    def save(self, **changes):
        value = {**self.base, **changes}
        self.json.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.json

    def invoke(self):
        return subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "bhandara", "paid-time-off",
             "--config", str(self.json)],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def test_real_excel_two_modules_same_run_and_no_other_steps(self):
        self.save()
        response = self.invoke()
        self.assertEqual(response.returncode, 0, response.stderr)
        payload = json.loads(response.stdout)
        self.assertEqual(list(payload["artifacts"]), ["entitlement", "deduction-quantity"])
        directory = self.outputs / "run-202611"
        self.assertTrue((directory / "entitlement-result.xlsx").is_file())
        self.assertTrue((directory / "deduction-quantity-result.xlsx").is_file())
        self.assertFalse((directory / "usage-ledger-result.xlsx").exists())
        book = load_workbook(directory / "entitlement-result.xlsx", read_only=True)
        try:
            self.assertIn("발생상세", book.sheetnames)
        finally:
            book.close()

    def test_cli_rejects_duplicate_run_without_overwriting(self):
        self.save()
        self.assertEqual(self.invoke().returncode, 0)
        original = (self.outputs / "run-202611/entitlement-result.xlsx").read_bytes()
        second = self.invoke()
        self.assertEqual(second.returncode, 2)
        self.assertIn("PTO_TOOL_ERROR", second.stderr)
        self.assertEqual(
            original, (self.outputs / "run-202611/entitlement-result.xlsx").read_bytes(),
        )

    def test_deduction_module_can_run_alone(self):
        self.save(steps=["deduction-quantity"])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.outputs / "run-202611"
        self.assertTrue((folder / "deduction-quantity-result.xlsx").exists())
        self.assertFalse((folder / "entitlement-result.xlsx").exists())

    def test_missing_required_usage_input_fails_before_execution(self):
        self.save(steps=["entitlement", "deduction-quantity", "usage-ledger"])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("grant_references", result.stderr)
        self.assertFalse(self.outputs.exists())

    def test_invalid_order_fails_before_execution(self):
        self.save(steps=["usage-ledger", "entitlement", "deduction-quantity"])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("must run before", result.stderr)

    def test_selected_steps_are_linked_to_real_prior_paths(self):
        ref = self.inputs / "paid-time-off/grant-references.xlsx"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_bytes(b"dummy for API mock")
        self.save(steps=["entitlement", "deduction-quantity", "usage-ledger"],
                  files={**self.base["files"], "grant_references": "paid-time-off/grant-references.xlsx"})
        entry = importlib.import_module("bhandara.paid-time-off.runner")
        usage = importlib.import_module("bhandara.paid-time-off.runner_usage")
        epath = self.outputs / "run-202611/entitlement-result.xlsx"
        dpath = self.outputs / "run-202611/deduction-quantity-result.xlsx"
        upath = self.outputs / "run-202611/usage-ledger-result.xlsx"
        with patch.object(entry, "run_entitlement", return_value={"path": str(epath)}), \
             patch.object(entry, "run_deduction_quantity", return_value={"path": str(dpath)}), \
             patch.object(usage, "run_usage_ledger", return_value={"path": str(upath)}) as mocked:
            result = TOOL.execute(self.json)
        self.assertEqual(result["usage-ledger"], str(upath))
        self.assertEqual(mocked.call_args.kwargs["entitlement_file"], epath)
        self.assertEqual(mocked.call_args.kwargs["deduction_file"], dpath)
        self.assertEqual(mocked.call_args.kwargs["reference_file"], ref)

    def test_external_usage_result_can_be_passed_to_closing(self):
        usage_file = self.inputs / "saved/usage-ledger-result.xlsx"
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        usage_file.write_bytes(b"dummy for API mock")
        self.save(steps=["closing"], closing_id="Closing-4.4-2026",
                  files={**self.base["files"], "usage_result": "saved/usage-ledger-result.xlsx"})
        module = importlib.import_module("bhandara.paid-time-off.runner_closing")
        with patch.object(module, "run_closing", return_value={"path": "/tmp/closing.xlsx"}) as mocked:
            TOOL.execute(self.json)
        self.assertEqual(mocked.call_args.kwargs["usage_file"], usage_file)

    def test_config_rejects_unknown_step_and_missing_file(self):
        self.save(steps=["payroll"])
        self.assertEqual(self.invoke().returncode, 2)
        self.save(files={"employee": "missing.xlsx"}, steps=["entitlement"])
        self.assertEqual(self.invoke().returncode, 2)


if __name__ == "__main__":
    unittest.main()
