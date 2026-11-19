"""P0-2/3 regression: exact declared cycles and label-based partial register."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.payroll.contract_period import (
    PayrollPeriodError, select_contracts_for_period,
)
from bhandara.payroll.input_excel import PayrollInputError, read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.review_adapter import (
    PayrollPreviewError, build_payroll_review_register,
)
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES


ROLES = (
    "contracts", "allowance_assignments", "fixed_allowance_map",
    "bonus_budget", "bonus_allocation",
)
FROM, TO = "2026-11-01", "2026-11-30"


def contract(employee="0001", **updates):
    row = deepcopy(SAMPLES["contracts"])
    row["employee_id"] = employee
    row["contract_id"] = f"C-{employee}"
    row.update(updates)
    return row


class PayrollPeriodPreviewP0Tests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "payroll").mkdir()

    def put(self, role, rows):
        spec = SCHEMA["workbooks"][role]
        book = Workbook()
        sheet = book.active
        sheet.title = spec["sheet"]
        sheet.append(spec["columns"])
        for row in rows:
            sheet.append([row.get(key) for key in spec["columns"]])
        book.save(self.root / "payroll" / spec["filename"])
        book.close()

    def prepare(self, *, contracts=None, allowance_assignments=None, allowance_map=None,
                bonus_budgets=None, bonus_allocations=None):
        files = {
            "contracts": [contract()] if contracts is None else contracts,
            "allowance_assignments": [] if allowance_assignments is None else allowance_assignments,
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])] if allowance_map is None else allowance_map,
            "bonus_budget": [] if bonus_budgets is None else bonus_budgets,
            "bonus_allocation": [] if bonus_allocations is None else bonus_allocations,
        }
        for role, rows in files.items():
            self.put(role, rows)
        return read_payroll_inputs(self.root, roles=ROLES)

    def view(self, inputs):
        return build_payroll_review_register(inputs, period_from=FROM, period_to=TO)

    def test_exact_period_selects_only_current_without_faking_legal_effective_dates(self):
        rows = [
            contract(calculation_period_from="2026-10-01",
                     calculation_period_to="2026-10-31", contract_id="OLD"),
            contract(contract_id="NEW"),
            contract(employee="0002", calculation_period_from="2026-12-01",
                     calculation_period_to="2026-12-31"),
        ]
        selected = select_contracts_for_period(rows, period_from=FROM, period_to=TO)
        self.assertEqual([row["contract_id"] for row in selected], ["NEW"])

    def test_two_contracts_inside_period_require_explicit_segmentation(self):
        rows = [
            contract(contract_id="OLD", calculation_period_to="2026-11-15"),
            contract(contract_id="NEW", calculation_period_from="2026-11-16"),
        ]
        with self.assertRaisesRegex(PayrollPeriodError, "partial coverage"):
            select_contracts_for_period(rows, period_from=FROM, period_to=TO)

    def test_single_partial_contract_and_missing_exact_period_block(self):
        with self.assertRaisesRegex(PayrollPeriodError, "partial coverage"):
            select_contracts_for_period(
                [contract(calculation_period_to="2026-11-20")],
                period_from=FROM, period_to=TO,
            )
        with self.assertRaisesRegex(PayrollPeriodError, "no exact matching"):
            select_contracts_for_period(
                [contract(calculation_period_from="2026-12-01",
                          calculation_period_to="2026-12-31")],
                period_from=FROM, period_to=TO,
            )

    def test_multiple_identical_rows_cannot_select_one_silently(self):
        with self.assertRaisesRegex(PayrollPeriodError, "multiple selected"):
            select_contracts_for_period(
                [contract(contract_id="V1"), contract(contract_id="V2")],
                period_from=FROM, period_to=TO,
            )

    def test_monthly_cycle_cannot_be_weekly_and_nonstandard_annual_is_blocked(self):
        with self.assertRaisesRegex(PayrollPeriodError, "WEEKLY requires seven"):
            select_contracts_for_period(
                [contract(pay_basis="WEEKLY")], period_from=FROM, period_to=TO,
            )
        with self.assertRaisesRegex(PayrollPeriodError, "explicit schedule policy"):
            select_contracts_for_period(
                [contract(pay_basis="ANNUAL", installments_per_year=24)],
                period_from=FROM, period_to=TO,
            )

    def test_supported_weekly_and_monthly_annual_cycles(self):
        rows = select_contracts_for_period(
            [contract(pay_basis="ANNUAL", installments_per_year=12,
                      contract_amount=36000000)],
            period_from=FROM, period_to=TO,
        )
        self.assertEqual(len(rows), 1)
        weekly = select_contracts_for_period(
            [contract(pay_basis="WEEKLY", calculation_period_from="2026-11-02",
                      calculation_period_to="2026-11-08")],
            period_from="2026-11-02", period_to="2026-11-08",
        )
        self.assertEqual(len(weekly), 1)

    def test_unverified_period_strings_fail(self):
        for start, end in [("2026-11-31", TO), ("2026-11-30", FROM),
                           ("2026-11-1", TO), (FROM, "2026-11-31")]:
            with self.subTest(start=start, end=end), self.assertRaises(PayrollPeriodError):
                select_contracts_for_period([contract()], period_from=start, period_to=end)

    def test_fifty_employees_dynamic_columns_with_no_false_totals(self):
        employees = [contract(f"{i:04d}") for i in range(1, 51)]
        name = deepcopy(SAMPLES["fixed_allowance_map"])
        data = self.prepare(
            contracts=employees,
            allowance_assignments=[dict(contract_id="C-0017", allowance_id="001", level="L1")],
            allowance_map=[name],
            bonus_budgets=[dict(bonus_id="BON", bonus_name="프로젝트 성과급",
                                project_id="PROJECT", team_id=None, budget_amount=10000)],
            bonus_allocations=[
                dict(bonus_id="BON", employee_id="0001", allocation_ratio="0.3"),
                dict(bonus_id="BON", employee_id="0002", allocation_ratio="0.7"),
            ],
        )
        view = self.view(data)
        self.assertEqual(len(view["rows"]), 50)
        keys = [column["key"] for column in view["columns"]]
        self.assertEqual(keys.count("fixed_allowances:001"), 1)
        self.assertIn("performance_bonuses:BON", keys)
        self.assertEqual(sum(row.get("fixed_allowances:001") is not None for row in view["rows"]), 1)
        self.assertEqual(view["rows"][16]["fixed_allowances:001"], 100000)
        self.assertEqual(view["rows"][0]["performance_bonuses:BON"], 3000)
        self.assertEqual(view["rows"][1]["performance_bonuses:BON"], 7000)
        for row in view["rows"]:
            self.assertIsNone(row["gross_pay"])
            self.assertIsNone(row["net_pay"])
            self.assertIsNone(row["deduction_total"])
            self.assertEqual(row["review_status"], "PARTIAL_REVIEW_ONLY")
        self.assertEqual(view["approval_state"], "NOT_APPROVED")
        self.assertNotIn("deductions:national_pension", keys)

    def test_actual_review_xlsx_single_sheet_with_blank_totals(self):
        data = self.prepare(
            allowance_assignments=[dict(contract_id="C-0001", allowance_id="001", level="L1")],
        )
        result = self.view(data)
        path = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(result, path)
        book = load_workbook(path)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            sheet = book["PAYROLL"]
            keys = [col["key"] for col in result["columns"]]
            self.assertEqual(sheet.cell(2, keys.index("fixed_allowances:001") + 1).value, "자격수당")
            self.assertIsNone(sheet.cell(3, keys.index("gross_pay") + 1).value)
            self.assertIsNone(sheet.cell(3, keys.index("net_pay") + 1).value)
        finally:
            book.close()

    def test_level_differences_share_one_item_column(self):
        standard = deepcopy(SAMPLES["fixed_allowance_map"])
        elevated = dict(standard, level="L2", amount=200000)
        data = self.prepare(
            contracts=[contract("0001"), contract("0002")],
            allowance_map=[standard, elevated],
            allowance_assignments=[
                dict(contract_id="C-0001", allowance_id="001", level="L1"),
                dict(contract_id="C-0002", allowance_id="001", level="L2"),
            ],
        )
        view = self.view(data)
        self.assertEqual([col["key"] for col in view["columns"]].count("fixed_allowances:001"), 1)
        self.assertEqual([r["fixed_allowances:001"] for r in view["rows"]], [100000, 200000])

    def test_name_mismatch_across_levels_and_unsafe_label_block(self):
        rate = deepcopy(SAMPLES["fixed_allowance_map"])
        second = dict(rate, level="L2", allowance_name="다른수당")
        with self.assertRaisesRegex(PayrollInputError, "inconsistent labels"):
            self.prepare(allowance_map=[rate, second])
        with self.assertRaisesRegex(PayrollInputError, "safe text label"):
            self.prepare(allowance_map=[dict(rate, allowance_name="@SUM(A1:A2)")])
        with self.assertRaisesRegex(PayrollInputError, "required value missing"):
            self.prepare(bonus_budgets=[dict(SAMPLES["bonus_budget"], bonus_name=None)])

    def test_different_ids_same_label_are_disambiguated_by_output(self):
        first = deepcopy(SAMPLES["fixed_allowance_map"])
        second = dict(first, allowance_id="002", amount=200000)
        data = self.prepare(
            contracts=[contract("0001"), contract("0002")],
            allowance_map=[first, second],
            allowance_assignments=[
                dict(contract_id="C-0001", allowance_id="001", level="L1"),
                dict(contract_id="C-0002", allowance_id="002", level="L1"),
            ],
        )
        view = self.view(data)
        labels = [col["label"] for col in view["columns"] if col.get("source") == "fixed_allowances"]
        self.assertEqual(labels, ["자격수당 [001]", "자격수당 [002]"])

    def test_renegotiated_contract_does_not_inherit_old_allowance(self):
        old = contract(contract_id="C-OLD", calculation_period_from="2026-10-01",
                       calculation_period_to="2026-10-31")
        new = contract(contract_id="C-NEW", contract_amount=3500000)
        data = self.prepare(
            contracts=[old, new],
            allowance_assignments=[dict(contract_id="C-OLD", allowance_id="001", level="L1")],
        )
        view = self.view(data)
        self.assertNotIn("fixed_allowances:001", [c["key"] for c in view["columns"]])
        self.assertEqual(view["rows"][0]["base_pay"], 3500000)

    def test_total_contract_reconciliation_is_not_bypassed(self):
        data = self.prepare(
            contracts=[contract(amount_type="TOTAL", declared_base_amount=2900000)],
            allowance_assignments=[dict(contract_id="C-0001", allowance_id="001", level="L1")],
        )
        view = self.view(data)
        self.assertEqual(view["rows"][0]["base_pay"], 2900000)
        data = self.prepare(
            contracts=[contract(amount_type="TOTAL", declared_base_amount=2800000)],
            allowance_assignments=[dict(contract_id="C-0001", allowance_id="001", level="L1")],
        )
        with self.assertRaisesRegex(ValueError, "TOTAL base"):
            self.view(data)

    def test_bonus_for_nonselected_worker_is_not_silently_paid(self):
        old = contract("0002", calculation_period_from="2026-10-01",
                       calculation_period_to="2026-10-31")
        data = self.prepare(
            contracts=[contract(), old],
            bonus_budgets=[dict(SAMPLES["bonus_budget"])],
            bonus_allocations=[dict(SAMPLES["bonus_allocation"], employee_id="0002")],
        )
        with self.assertRaisesRegex(ValueError, "missing budget or contract"):
            self.view(data)

    def test_missing_earnings_role_fails_instead_of_assuming_zero(self):
        self.put("contracts", [contract()])
        data = read_payroll_inputs(self.root, roles=("contracts",))
        with self.assertRaisesRegex(PayrollPreviewError, "requires every earnings input role"):
            self.view(data)


if __name__ == "__main__":
    unittest.main()
