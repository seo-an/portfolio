"""One-sheet employer industrial cost and four-branch common employee states E2E."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import build_contract_scoped_overtime_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output import build_employee_payroll_view
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.tests.test_payroll_attendance_settlement_p1 import wage_plan
from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import ROLLUP, source_registry
from bhandara.tests.test_payroll_employer_industrial_insurance import industrial, industrial_plan
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_insurance_candidates_p2 import ALL_ROLES, assessment, assessment_plan
from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
from bhandara.tests.test_payroll_segmented_settlement_p1 import FROM, TO, contract, plan
from bhandara.tests.test_payroll_tax_withholding_p2 import tax_plan
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx


class EmployerCostPayrollFlowTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "payroll").mkdir()
        self.employee_xlsx = self.root / "employee.xlsx"
        employee = Workbook()
        active = employee.active
        active.title = "재직자"
        columns = [
            "employee_id", "national_pension_acquired_on",
            "health_insurance_acquired_on", "employment_insurance_acquired_on",
            "industrial_accident_acquired_on",
        ]
        active.append(columns)
        active.append(["0001", None, "2026-01-10", "미가입", "2026-05-05"])
        employee.create_sheet("퇴사자").append(columns)
        employee.save(self.employee_xlsx)
        employee.close()
        data = {
            "contracts": [contract()],
            "allowance_assignments": [],
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])],
            "bonus_budget": [], "bonus_allocation": [],
            "overtime_rules": [rate(minimum_minutes=0)],
            "deduction_map": [deepcopy(SAMPLES["deduction_map"])],
        }
        for role in ALL_ROLES:
            schema = SCHEMA["workbooks"][role]
            book = Workbook()
            book.active.title = schema["sheet"]
            book.active.append(schema["columns"])
            for row in data[role]:
                book.active.append([row.get(col) for col in schema["columns"]])
            book.save(self.root / "payroll" / schema["filename"])
            book.close()
        self.inputs = read_payroll_inputs(self.root, roles=ALL_ROLES)
        self.wt = self.root / "worktime-result.xlsx"
        write_worktime_xlsx({
            "schema_version": "0.1",
            "rows": [fact(day="2026-11-02", actual_min=480)],
        }, self.wt)

    def run_flow(self, *, employer=True, tax=True, insurance=True, employee=True):
        return build_contract_scoped_overtime_preview(
            self.inputs, self.wt,
            settlement_plan=plan(),
            attendance_plan=wage_plan(items=[], sha=sha256_file(self.wt)),
            period_from=FROM, period_to=TO,
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry([], [], [rate(minimum_minutes=0)]),
            rate_policy=policy(reference_day_minutes_by_contract={"C-OLD": 480}),
            rollup_policy=ROLLUP,
            employee_xlsx=self.employee_xlsx if employee else None,
            insurance_assessment_plan=assessment_plan(records=[assessment(
                national_pension_applicable=False,
                health_insurance_applicable=True,
                employment_insurance_applicable=False,
                longterm_care_applicable=True,
            )]) if insurance else None,
            withholding_plan=tax_plan() if tax else None,
            industrial_assessment_plan=industrial_plan(
                records=[industrial("0001")],
            ) if employer else None,
        )

    def test_admin_company_cost_appears_without_changing_employee_net(self):
        result = self.run_flow()
        worker = result["payroll_register"]["rows"][0]
        self.assertEqual(worker["gross_pay"], 3000000)
        self.assertEqual(worker["deductions:INS_HEALTH_INSURANCE"], 107850)
        self.assertEqual(worker["deductions:INS_LONGTERM_CARE"], 14171)
        self.assertEqual(worker["deductions:TAX_INCOME"], 50000)
        self.assertEqual(worker["deductions:TAX_LOCAL_INCOME"], 5000)
        self.assertEqual(worker["deduction_total"], 177021)
        self.assertEqual(worker["net_pay"], 2822979)
        self.assertIsNone(worker.get("deductions:INS_NATIONAL_PENSION"))
        self.assertIsNone(worker.get("deductions:INS_EMPLOYMENT_INSURANCE"))
        self.assertEqual(worker["employer_industrial"], 21000)
        self.assertEqual(worker["known_company_outlay"], 3021000)
        self.assertEqual(result["employer_cost_review"]["total_candidate_won"], 21000)
        self.assertIn("INSURANCE_NOT_ENROLLED:employment_insurance",
                      result["payroll_register"]["review_flags"]["0001"])
        self.assertFalse(any(
            "industrial_accident" in reason
            for reason in result["payroll_register"]["review_flags"]["0001"]
        ))
        self.assertNotIn("INCOME_TAX_UNVERIFIED",
                         result["payroll_register"]["review_flags"]["0001"])
        self.assertNotIn("LOCAL_INCOME_TAX_UNVERIFIED",
                         result["payroll_register"]["review_flags"]["0001"])
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        out = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(result["payroll_register"], out)
        book = load_workbook(out, read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            keys = [column["key"] for column in result["payroll_register"]["columns"]]
            self.assertEqual(book.active.cell(3, keys.index("employer_industrial") + 1).value, 21000)
            self.assertEqual(book.active.cell(3, keys.index("known_company_outlay") + 1).value, 3021000)
        finally:
            book.close()
        notice = build_employee_payroll_view(result["payroll_register"], employee_id="0001")
        self.assertEqual(notice["rows"][0]["gross_pay"], 3000000)
        self.assertEqual(notice["rows"][0]["net_pay"], 2822979)
        self.assertFalse(any("employer" in key or "outlay" in key for key in notice["rows"][0]))

    def test_company_cost_requires_common_status_no_age_guess(self):
        from bhandara.payroll.contract_scoped_overtime import ContractOvertimeAdapterError
        with self.assertRaisesRegex(ContractOvertimeAdapterError, "common employee.xlsx"):
            self.run_flow(employee=False)

    def test_blank_pension_is_normal_and_no_employer_plan_does_not_change_pay(self):
        result = self.run_flow(employer=False)
        self.assertNotIn("employer_cost_review", result)
        self.assertNotIn("employer_industrial", result["payroll_register"]["rows"][0])
        self.assertEqual(result["payroll_register"]["rows"][0]["net_pay"], 2822979)
        self.assertFalse(any("national_pension" in item
                             for item in result["payroll_register"]["review_flags"]["0001"]))

    def test_missing_tax_or_insurance_creates_only_relevant_review_flags(self):
        result = self.run_flow(tax=False, insurance=False, employer=False)
        reasons = result["payroll_register"]["review_flags"]["0001"]
        self.assertIn("INCOME_TAX_UNVERIFIED", reasons)
        self.assertIn("LOCAL_INCOME_TAX_UNVERIFIED", reasons)
        self.assertIn("INSURANCE_PREMIUM_UNVERIFIED:health_insurance", reasons)
        self.assertIn("INSURANCE_NOT_ENROLLED:employment_insurance", reasons)
        self.assertNotIn("EARNINGS_UNVERIFIED", reasons)
        self.assertNotIn("DEDUCTIONS_UNVERIFIED", reasons)


if __name__ == "__main__":
    unittest.main()
