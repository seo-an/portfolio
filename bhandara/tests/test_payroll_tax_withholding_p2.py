"""P2-2 approved income/local withholding and item-level taxable split."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import build_contract_scoped_overtime_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.tax_withholding import (
    PayrollWithholdingError, review_taxability_and_withholding,
)
from bhandara.tests.test_payroll_attendance_settlement_p1 import wage_plan
from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import ROLES, ROLLUP, source_registry
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_insurance_candidates_p2 import (
    ALL_ROLES, assessment_plan,
)
from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
from bhandara.tests.test_payroll_segmented_settlement_p1 import (
    FROM, TO, allocated, contract, employment, plan,
)
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.payroll.settlement_coverage import validate_settlement_coverage
from bhandara.worktime.output_excel import write_worktime_xlsx


def entry(source, item_id, taxable, exempt=0, **changes):
    data = {
        "source": source, "item_id": item_id,
        "taxable_won": taxable, "non_taxable_won": exempt,
        "classification_ref": f"CLASS-{source}-{item_id}",
    }
    data.update(changes)
    return data


def employee(worker="0001", *, classifications=None,
             income=50000, local=5000, **changes):
    data = {
        "employee_id": worker,
        "classifications": [entry("base_pay", "BASE", 3000000)]
            if classifications is None else classifications,
        "income_tax_won": income, "local_income_tax_won": local,
        "withholding_ref": f"WITHHOLD-{worker}",
        "approval_status": "APPROVED",
        "not_pre_deducted": True,
    }
    data.update(changes)
    return data


def tax_plan(*, employees=None, **changes):
    data = {
        "schema_version": "0.1",
        "period_from": FROM, "period_to": TO,
        "policy_ref": "SYNTHETIC-WITHHOLDING-POLICY",
        "source_snapshot_ref": "SYNTHETIC-WITHHOLDING-SNAPSHOT",
        "employees": [employee()] if employees is None else employees,
    }
    data.update(changes)
    return data


def fixed_map(*, category="NON_TAXABLE", policy_ref="SYNTHETIC-MEAL-CAP"):
    data = deepcopy(SAMPLES["fixed_allowance_map"])
    data.update({
        "allowance_name": "식대", "payroll_taxability": category,
        "taxability_policy_ref": policy_ref,
    })
    return data


def selected_coverage(contracts=None, settlement=None):
    return validate_settlement_coverage(
        [contract()] if contracts is None else contracts,
        plan=plan() if settlement is None else settlement,
        period_from=FROM, period_to=TO,
    )


def review(*, report=None, pay_rows=None, fixed=None, assigned=None,
           contracts=None, settlement=None, **overrides):
    return review_taxability_and_withholding(
        [{"employee_id": "0001", "base_pay": 3000000,
          "fixed_allowances": [], "overtime_allowances": [],
          "performance_bonuses": []}] if pay_rows is None else pay_rows,
        selected_coverage(contracts, settlement),
        [fixed_map()] if fixed is None else fixed,
        [] if assigned is None else assigned,
        withholding_plan=tax_plan(
            employees=[employee()] if report is None else report, **overrides,
        ),
        period_from=FROM, period_to=TO,
    )


class TaxWithholdingCoreTests(unittest.TestCase):
    def test_every_pay_item_split_sums_exactly_and_not_inferred(self):
        row = {
            "employee_id": "0001", "base_pay": 3000000,
            "fixed_allowances": [{"item_id": "001", "amount": 100000}],
            "overtime_allowances": [{"item_id": "OT01", "amount": 60000}],
            "performance_bonuses": [{"item_id": "B01", "amount": 10000}],
        }
        splits = [
            entry("base_pay", "BASE", 3000000),
            entry("fixed_allowances", "001", 80000, 20000),
            entry("overtime_allowances", "OT01", 60000),
            entry("performance_bonuses", "B01", 10000),
        ]
        result = review(
            pay_rows=[row],
            assigned=[{"contract_id": "C-OLD", "allowance_id": "001", "level": "L1"}],
            report=[employee(classifications=splits)],
        )
        self.assertEqual(result["employees"][0]["taxable_earnings_won"], 3150000)
        self.assertEqual(result["employees"][0]["non_taxable_earnings_won"], 20000)
        self.assertEqual(result["employees"][0]["candidate_earnings_won"], 3170000)
        self.assertEqual(result["items_by_employee"]["0001"], [
            {"item_id": "TAX_INCOME", "label": "근로소득세", "amount": 50000},
            {"item_id": "TAX_LOCAL_INCOME", "label": "지방소득세", "amount": 5000},
        ])
        self.assertEqual(result["statutory_tax_tables"], "NOT_COMPUTED")
        self.assertFalse(result["deductions_complete"])

    def test_empty_tax_is_explicit_zero_not_missing(self):
        output = review(report=[employee(income=0, local=0)])
        self.assertEqual([x["amount"] for x in output["items_by_employee"]["0001"]], [0, 0])
        self.assertFalse(output["earnings_complete"])

    def test_taxable_fixed_map_forbids_exempt_and_missing_policy_ref_rejected(self):
        row = {"employee_id": "0001", "base_pay": 3000000,
               "fixed_allowances": [{"item_id": "001", "amount": 100000}],
               "overtime_allowances": [], "performance_bonuses": []}
        splits = [
            entry("base_pay", "BASE", 3000000),
            entry("fixed_allowances", "001", 80000, 20000),
        ]
        assigned = [{"contract_id": "C-OLD", "allowance_id": "001", "level": "L1"}]
        for mapping, reason in (
            ([fixed_map(category="TAXABLE")], "TAXABLE map"),
            ([fixed_map(policy_ref=None)], "taxability_policy_ref"),
        ):
            with self.subTest(mapping=mapping), self.assertRaisesRegex(
                PayrollWithholdingError, reason,
            ):
                review(pay_rows=[row], assigned=assigned, fixed=mapping,
                       report=[employee(classifications=splits)])

    def test_ambiguous_duplicate_unknown_or_unapproved_classification_fails(self):
        for records in (
            [employee(classifications=[])],
            [employee(classifications=[
                entry("base_pay", "BASE", 3000000),
                entry("base_pay", "BASE", 3000000),
            ])],
            [employee(classifications=[entry("base_pay", "BASE", 2999999)])],
            [employee(classifications=[entry("base_pay", "BASE", 3000001)])],
            [employee(classifications=[entry("base_pay", "BASE", 2800000, 199999)])],
            [employee(classifications=[entry("base_pay", "UNKNOWN", 3000000)])],
            [employee(classifications=[entry("deductions", "X", 3000000)])],
            [employee(classifications=[entry("base_pay", "BASE", -10)])],
            [employee(classifications=[entry("base_pay", "BASE", 3.1)])],
            [employee(classifications=[entry("base_pay", "BASE", 3000000,
                                             classification_ref="")])],
            [employee(approval_status="PENDING")],
            [employee(not_pre_deducted=False)],
            [employee(income=-1)],
            [employee(local=2.5)],
            [employee(withholding_ref="")],
            [dict(employee(), extra=True)],
            [], [employee(), employee()], [employee(worker="0002")],
        ):
            with self.subTest(records=records), self.assertRaises(PayrollWithholdingError):
                review(report=records)

    def test_plan_period_schema_snapshot_are_explicit(self):
        for changes in (
            {"schema_version": "0.2"},
            {"period_from": "2026-10-01"},
            {"period_to": "2026-12-01"},
            {"policy_ref": ""},
            {"source_snapshot_ref": ""},
            {"extra": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(PayrollWithholdingError):
                review(**changes)

    def test_all_fifty_employees_must_have_exact_classification(self):
        workers = [f"{i:04d}" for i in range(1, 51)]
        contracts = [contract(worker=w, contract_id=f"C-{w}") for w in workers]
        settlement = plan(
            facts=[employment(worker=w) for w in workers],
            allocations=[allocated(worker=w, contract_id=f"C-{w}") for w in workers],
        )
        pay_rows = [
            {"employee_id": w, "base_pay": 3000000, "fixed_allowances": [],
             "overtime_allowances": [], "performance_bonuses": []}
            for w in workers
        ]
        reports = [
            employee(worker=w, income=1000 if w == "0017" else 0,
                     local=100 if w == "0017" else 0)
            for w in workers
        ]
        result = review(
            pay_rows=pay_rows, contracts=contracts, settlement=settlement,
            report=reports,
        )
        self.assertEqual(len(result["employees"]), 50)
        self.assertEqual(sum(
            sum(i["amount"] for i in records) > 0
            for records in result["items_by_employee"].values()
        ), 1)
        with self.assertRaisesRegex(PayrollWithholdingError, "complete employee roster"):
            review(pay_rows=pay_rows, contracts=contracts, settlement=settlement,
                   report=reports[:-1])


class TaxWithholdingExcelE2E(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "payroll").mkdir()

    def put(self, role, rows):
        spec = SCHEMA["workbooks"][role]
        wb = Workbook()
        wb.active.title = spec["sheet"]
        wb.active.append(spec["columns"])
        for item in rows:
            wb.active.append([item.get(column) for column in spec["columns"]])
        wb.save(self.root / "payroll" / spec["filename"])
        wb.close()

    def run_flow(self, *, withholding=None, insurance=None, fixed_category="NON_TAXABLE"):
        data = {
            "contracts": [contract()],
            "allowance_assignments": [
                {"contract_id": "C-OLD", "allowance_id": "001", "level": "L1"},
            ],
            "fixed_allowance_map": [fixed_map(category=fixed_category)],
            "bonus_budget": [], "bonus_allocation": [],
            "overtime_rules": [rate(minimum_minutes=0)],
            "deduction_map": [deepcopy(SAMPLES["deduction_map"])],
        }
        for role in ALL_ROLES:
            self.put(role, data[role])
        inputs = read_payroll_inputs(self.root, roles=ALL_ROLES)
        wt = self.root / "worktime-result.xlsx"
        if not wt.exists():
            write_worktime_xlsx({"schema_version": "0.1",
                                 "rows": [fact(day="2026-11-02", actual_min=480)]}, wt)
        return build_contract_scoped_overtime_preview(
            inputs, wt, settlement_plan=plan(),
            attendance_plan=wage_plan(items=[], sha=sha256_file(wt)),
            period_from=FROM, period_to=TO,
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry([], [], [rate(minimum_minutes=0)]),
            rate_policy=policy(reference_day_minutes_by_contract={"C-OLD": 480}),
            rollup_policy=ROLLUP,
            insurance_assessment_plan=insurance,
            withholding_plan=withholding,
        )

    def tax_plan_for_allowance(self, *, income=50000, local=5000):
        return tax_plan(employees=[employee(
            classifications=[
                entry("base_pay", "BASE", 3000000),
                entry("fixed_allowances", "001", 80000, 20000),
            ], income=income, local=local,
        )])

    def test_existing_seven_xlsx_single_sheet_and_two_tax_deductions(self):
        result = self.run_flow(
            withholding=self.tax_plan_for_allowance(),
            insurance=assessment_plan(),
        )
        row = result["payroll_register"]["rows"][0]
        self.assertEqual(row["deductions:TAX_INCOME"], 50000)
        self.assertEqual(row["deductions:TAX_LOCAL_INCOME"], 5000)
        self.assertEqual(row["deductions:INS_NATIONAL_PENSION"], 142500)
        self.assertEqual(result["tax_withholding_review"]["employees"][0]["taxable_earnings_won"], 3080000)
        self.assertEqual(result["tax_withholding_review"]["employees"][0]["non_taxable_earnings_won"], 20000)
        self.assertEqual(row["gross_pay"], 3100000)
        self.assertEqual(row["deduction_total"], 346521)
        self.assertEqual(row["net_pay"], 2753479)
        self.assertEqual(row["review_status"], "검증요청 · 잠정합계")
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        path = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(result["payroll_register"], path)
        book = load_workbook(path, read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            keys = [col["key"] for col in result["payroll_register"]["columns"]]
            self.assertEqual(book["PAYROLL"].cell(3, keys.index("deductions:TAX_INCOME") + 1).value, 50000)
        finally:
            book.close()

    def test_without_withholding_plan_no_tax_candidates_added(self):
        result = self.run_flow(withholding=None)
        self.assertNotIn("tax_withholding_review", result)
        self.assertFalse(any("TAX_INCOME" in col["key"]
                             for col in result["payroll_register"]["columns"]))

    def test_zero_taxes_do_not_add_columns_and_do_not_mean_final(self):
        result = self.run_flow(withholding=self.tax_plan_for_allowance(income=0, local=0))
        self.assertFalse(any("TAX_INCOME" in col["key"] or "TAX_LOCAL_INCOME" in col["key"]
                             for col in result["payroll_register"]["columns"]))
        self.assertEqual(result["payroll_register"]["rows"][0]["net_pay"], 3100000)
        self.assertEqual(
            result["payroll_register"]["rows"][0]["review_status"],
            "검증요청 · 잠정합계",
        )

    def test_fixed_taxable_map_rejects_external_exempt_decision(self):
        with self.assertRaisesRegex(PayrollWithholdingError, "TAXABLE map"):
            self.run_flow(
                withholding=self.tax_plan_for_allowance(),
                fixed_category="TAXABLE",
            )

    def test_taxable_split_must_follow_actual_pto_adjusted_amount(self):
        # Deliberately misclassified base: fail-closed if post-leave amount differs.
        with self.assertRaisesRegex(PayrollWithholdingError, "equal candidate"):
            self.run_flow(withholding=tax_plan(employees=[employee(
                classifications=[
                    entry("base_pay", "BASE", 2999999),
                    entry("fixed_allowances", "001", 80000, 20000),
                ],
            )]))


if __name__ == "__main__":
    unittest.main()
