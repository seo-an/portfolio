"""P3-1: one JSON invocation, seven Excel inputs, reviewed candidate output."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from openpyxl import load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.tool_cli import PayrollToolError, _config, execute, main
from bhandara.tests.test_payroll_attendance_settlement_p1 import wage_plan
from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import (
    ROLLUP, source_registry,
)
from bhandara.tests.test_payroll_employer_cost_flow import EmployerCostPayrollFlowTests
from bhandara.tests.test_payroll_employer_industrial_insurance import (
    industrial, industrial_plan,
)
from bhandara.tests.test_payroll_insurance_candidates_p2 import assessment, assessment_plan
from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
from bhandara.tests.test_payroll_segmented_settlement_p1 import (
    FROM, TO, plan,
)
from bhandara.tests.test_payroll_tax_withholding_p2 import tax_plan


def _json_file(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


class PayrollJSONToolCLITests(unittest.TestCase):
    def setUp(self):
        self.fixture = EmployerCostPayrollFlowTests(
            "test_admin_company_cost_appears_without_changing_employee_net"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output_root = Path(temp.name) / "output"
        rate_row = rate(minimum_minutes=0)
        self.sources = {
            "settlement_plan": plan(),
            "attendance_plan": wage_plan(items=[], sha=sha256_file(self.fixture.wt)),
            "verified_work": [],
            "approved_segments": [],
            "evidence_registry": source_registry([], [], [rate_row]),
            "rate_policy": policy(
                reference_day_minutes_by_contract={"C-OLD": 480}
            ),
            "rollup_policy": deepcopy(ROLLUP),
            "insurance_assessment_plan": assessment_plan(records=[assessment(
                national_pension_applicable=False,
                health_insurance_applicable=True,
                longterm_care_applicable=True,
                employment_insurance_applicable=False,
            )]),
            "withholding_plan": tax_plan(),
            "industrial_assessment_plan": industrial_plan(
                records=[industrial("0001")]
            ),
        }
        self.config = {
            "schema_version": "1.0", "tool": "payroll",
            "run_id": "synth-review-202611",
            "payroll_period": "2026-11",
            "input_root": str(self.root),
            "output_root": str(self.output_root),
            "steps": ["review", "output"],
            "files": {
                "worktime": "worktime-result.xlsx",
                "employee": "employee.xlsx",
            },
            "source_files": {},
        }
        for name, value in self.sources.items():
            file = self.root / "payroll" / "decisions" / (name + ".json")
            _json_file(file, value)
            self.config["source_files"][name] = str(file.relative_to(self.root))
        self.config_path = self.root / "payroll-cli-test.json"
        self.save()

    def save(self):
        _json_file(self.config_path, self.config)

    def test_real_seven_excels_json_sources_employer_separate_and_one_sheet(self):
        result = execute(self.config_path)
        self.assertEqual(set(result), {"review", "output"})
        xlsx = Path(result["output"])
        self.assertEqual(xlsx.name, "payroll-result.xlsx")
        self.assertEqual(xlsx.parent.name, "synth-review-202611")
        wb = load_workbook(xlsx, read_only=True)
        try:
            self.assertEqual(wb.sheetnames, ["PAYROLL"])
            columns = [
                wb["PAYROLL"].cell(2, i).value
                for i in range(1, wb["PAYROLL"].max_column + 1)
            ]
            values = {
                label: wb["PAYROLL"].cell(3, i + 1).value
                for i, label in enumerate(columns)
            }
            self.assertEqual(values["지급합계"], 3000000)
            self.assertEqual(values["공제합계"], 177021)
            self.assertEqual(values["실지급액"], 2822979)
            self.assertEqual(values["산재보험료(사업주)"], 21000)
            self.assertEqual(values["회사 비용(확인분)"], 3021000)
            self.assertTrue(values["검토상태"].startswith("검증요청"))
        finally:
            wb.close()
        report = json.loads(Path(result["review"]).read_text(encoding="utf-8"))
        self.assertEqual(report["employee_count"], 1)
        self.assertEqual(report["approval_state"], "NOT_APPROVED")
        self.assertEqual(report["company_cost"]["known_amount_total_won"], 3021000)
        self.assertIn(
            "INSURANCE_NOT_ENROLLED:employment_insurance",
            report["review_flags"]["0001"],
        )
        self.assertFalse(any(
            "industrial_accident" in v for v in report["review_flags"]["0001"]
        ))
        self.assertEqual(len(report["source_sha256_by_role"]), 19)

    def test_repeated_run_id_is_rejected_without_overwriting_files(self):
        outputs = execute(self.config_path)
        original = sha256_file(Path(outputs["output"]))
        with self.assertRaisesRegex(PayrollToolError, "already exists"):
            execute(self.config_path)
        self.assertEqual(sha256_file(Path(outputs["output"])), original)

    def test_review_only_does_not_write_payroll_excel(self):
        self.config["steps"] = ["review"]
        self.save()
        results = execute(self.config_path)
        self.assertEqual(set(results), {"review"})
        self.assertFalse((Path(results["review"]).parent / "payroll-result.xlsx").exists())

    def test_output_only_does_not_write_intermediate_json(self):
        self.config["steps"] = ["output"]
        self.save()
        results = execute(self.config_path)
        self.assertEqual(set(results), {"output"})
        self.assertFalse((Path(results["output"]).parent / "payroll-review.json").exists())

    def test_partial_sources_leave_tax_and_pension_unverified_not_zero(self):
        for optional in (
            "insurance_assessment_plan", "withholding_plan",
            "industrial_assessment_plan",
        ):
            self.config["source_files"].pop(optional)
        self.save()
        outputs = execute(self.config_path)
        report = json.loads(Path(outputs["review"]).read_text(encoding="utf-8"))
        flags = report["review_flags"]["0001"]
        self.assertIn("INCOME_TAX_UNVERIFIED", flags)
        self.assertIn("INSURANCE_PREMIUM_UNVERIFIED:health_insurance", flags)
        self.assertIn("INSURANCE_NOT_ENROLLED:employment_insurance", flags)
        self.assertNotIn("EARNINGS_UNVERIFIED", flags)
        self.assertIsNone(report["company_cost"]["known_amount_total_won"])

    def test_missing_json_data_source_blocks_without_creating_output(self):
        self.config["source_files"].pop("settlement_plan")
        self.save()
        with self.assertRaisesRegex(PayrollToolError, "verification source"):
            execute(self.config_path)
        self.assertFalse(self.output_root.exists())

    def test_wrong_period_duplicate_step_and_foreign_option_are_rejected(self):
        for changes in (
            {"payroll_period": "2026-11-19"},
            {"steps": ["output", "review"]},
            {"steps": ["review", "review"]},
            {"steps": ["bogus"]},
            {"run_id": "../escaped"},
            {"extra": "unknown"},
        ):
            with self.subTest(change=changes):
                self.config.update(changes)
                self.save()
                with self.assertRaises(PayrollToolError):
                    execute(self.config_path)
                self.assertFalse(self.output_root.exists())
                for key in changes:
                    self.config.pop(key, None)
                self.config.update({
                    "payroll_period": "2026-11",
                    "steps": ["review", "output"],
                    "run_id": "synth-review-202611",
                })
        self.save()

    def test_tampered_attendance_sha_blocks_without_silent_pay(self):
        path = self.root / self.config["source_files"]["attendance_plan"]
        broken = json.loads(path.read_text(encoding="utf-8"))
        broken["worktime_sha256"] = "f" * 64
        _json_file(path, broken)
        with self.assertRaises(ValueError):
            execute(self.config_path)
        self.assertFalse(self.output_root.exists())

    def test_root_dispatch_and_json_cli_fail_closed(self):
        from run import main as root_main
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(
                root_main(["bhandara", "payroll", "--config", str(self.config_path)]), 0
            )
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(
                root_main(["bhandara", "payroll", "--config", str(self.config_path),
                           "--period", "2026-11"]), 2
            )
        self.assertTrue((self.output_root / "synth-review-202611" /
                         "payroll-result.xlsx").is_file())

    def test_main_uses_nonzero_for_invalid_plan(self):
        self.config["source_files"]["attendance_plan"] = "missing.json"
        self.save()
        with redirect_stderr(StringIO()):
            self.assertEqual(main(self.config_path), 2)
        self.assertFalse(self.output_root.exists())


if __name__ == "__main__":
    unittest.main()
