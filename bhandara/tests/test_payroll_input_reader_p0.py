"""Synthetic fail-closed tests for Payroll's independent role readers."""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from bhandara.payroll.input_excel import PayrollInputError, read_payroll_inputs
from bhandara.payroll.core import (resolve_contract_pay, resolve_fixed_allowances,
                                   allocate_performance_bonus, resolve_deduction_mapping)


SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "payroll" / "input-files.json").read_text())
SAMPLES = {
    "contracts": dict(employee_id="0001", contract_id="C01", pay_basis="MONTHLY",
                      contract_amount=3000000, amount_type="BASE", installments_per_year=None,
                      declared_base_amount=None, daily_base_rate=100000, deduction_code="D01",
                      calculation_period_from="2026-11-01", calculation_period_to="2026-11-30",
                      payment_date="2026-12-05"),
    "allowance_assignments": dict(contract_id="C01", allowance_id="001", level="L1"),
    "fixed_allowance_map": dict(allowance_id="001", allowance_name="자격수당", level="L1", amount=100000,
                                payroll_taxability="TAXABLE", taxability_policy_ref=None),
    "deduction_map": dict(deduction_code="D01", national_pension=0.0475,
                          health_insurance=0.03595, longterm_care=0.1314,
                          employment_insurance=0.009, effective_from="2026-01-01",
                          effective_to="2026-12-31", source_ref="PUBLIC-EXAMPLE"),
    "overtime_rules": dict(rule_id="OT01", category="OVERTIME", qualifying_from=None,
                           qualifying_to=None, minimum_minutes=30, daily_rate_multiplier=1.5,
                           policy_ref="EXAMPLE-ONLY"),
    "bonus_budget": dict(bonus_id="B01", bonus_name="성과급", team_id="T01", project_id=None,
                         budget_amount=1000),
    "bonus_allocation": dict(bonus_id="B01", employee_id="0001", allocation_ratio=1),
}


class PayrollExcelInputP0Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "payroll").mkdir()

    def put(self, role, rows=None, *, sheet=None, headers=None):
        spec = SCHEMA["workbooks"][role]
        book = Workbook()
        ws = book.active
        ws.title = sheet or spec["sheet"]
        columns = headers if headers is not None else spec["columns"]
        ws.append(columns)
        for row in rows if rows is not None else [SAMPLES[role]]:
            ws.append([row.get(field) for field in columns])
        path = self.root / "payroll" / spec["filename"]
        book.save(path)
        book.close()
        return path

    def all(self):
        for role in SAMPLES:
            self.put(role)

    def test_all_seven_roles_bind_to_existing_core_without_approval(self):
        self.all()
        result = read_payroll_inputs(self.root)
        self.assertEqual(set(result.roles), set(SAMPLES))
        contracts = resolve_contract_pay(result.for_role("contracts"))
        fixed = resolve_fixed_allowances(contracts, result.for_role("fixed_allowance_map"),
                                         result.for_role("allowance_assignments"))
        bonus = allocate_performance_bonus(contracts, result.for_role("bonus_budget"),
                                           result.for_role("bonus_allocation"))
        rates = resolve_deduction_mapping(contracts, result.for_role("deduction_map"))
        self.assertEqual(fixed["0001"][0]["amount"], Decimal(100000))
        self.assertEqual(bonus["0001"][0]["amount"], Decimal(1000))
        self.assertEqual(rates["0001"]["rates"]["national_pension"], Decimal("0.0475"))
        self.assertNotIn("deduction_total", rates["0001"])

    def test_selected_roles_only_require_their_own_file(self):
        self.put("contracts")
        result = read_payroll_inputs(self.root, roles=["contracts"])
        self.assertEqual(result.for_role("contracts")[0]["employee_id"], "0001")
        self.assertEqual(result.roles, ("contracts",))
        with self.assertRaisesRegex(PayrollInputError, "missing workbook"):
            read_payroll_inputs(self.root)

    def test_roles_must_be_unique_known_and_nonempty(self):
        for roles in ([], ["contracts", "contracts"], ["garbage"]):
            with self.subTest(roles=roles), self.assertRaises(PayrollInputError):
                read_payroll_inputs(self.root, roles=roles)

    def test_wrong_sheet_and_second_sheet_fail(self):
        path = self.put("contracts", sheet="WRONG")
        with self.assertRaisesRegex(PayrollInputError, "exactly one sheet"):
            read_payroll_inputs(self.root, roles=["contracts"])
        path = self.put("contracts")
        from openpyxl import load_workbook
        book = load_workbook(path)
        book.create_sheet("EXTRA")
        book.save(path)
        book.close()
        with self.assertRaisesRegex(PayrollInputError, "exactly one sheet"):
            read_payroll_inputs(self.root, roles=["contracts"])

    def test_missing_duplicate_header_and_formula_fail(self):
        columns = SCHEMA["workbooks"]["contracts"]["columns"]
        self.put("contracts", headers=columns[:-1])
        with self.assertRaisesRegex(PayrollInputError, "missing required header: payment_date"):
            read_payroll_inputs(self.root, roles=["contracts"])
        self.put("contracts", headers=columns + ["employee_id"])
        with self.assertRaises(PayrollInputError):
            read_payroll_inputs(self.root, roles=["contracts"])
        self.put("contracts", rows=[dict(SAMPLES["contracts"], contract_amount="=3000000")])
        with self.assertRaisesRegex(PayrollInputError, "formula unsupported"):
            read_payroll_inputs(self.root, roles=["contracts"])

    def test_numeric_identifier_rejected_instead_of_losing_leading_zero(self):
        self.put("contracts", rows=[dict(SAMPLES["contracts"], employee_id=1)])
        with self.assertRaisesRegex(PayrollInputError, "ID must be Excel text"):
            read_payroll_inputs(self.root, roles=["contracts"])

    def test_bad_date_missing_required_field_or_invalid_amount_rejected(self):
        for changed in (dict(payment_date="2026-02-30"), dict(daily_base_rate=None),
                        dict(contract_amount="1.5"), dict(calculation_period_from="2026-12-01")):
            with self.subTest(changed=changed):
                self.put("contracts", rows=[dict(SAMPLES["contracts"], **changed)])
                with self.assertRaises(PayrollInputError):
                    read_payroll_inputs(self.root, roles=["contracts"])

    def test_annual_and_total_require_fields_only_when_needed(self):
        for change in (dict(pay_basis="ANNUAL"), dict(amount_type="TOTAL")):
            self.put("contracts", rows=[dict(SAMPLES["contracts"], **change)])
            with self.assertRaises(PayrollInputError):
                read_payroll_inputs(self.root, roles=["contracts"])
        self.put("contracts", rows=[dict(SAMPLES["contracts"], pay_basis="ANNUAL",
                                         installments_per_year=12, amount_type="TOTAL",
                                         declared_base_amount=250000)])
        self.assertEqual(len(read_payroll_inputs(self.root, roles=["contracts"]).for_role("contracts")), 1)

    def test_duplicate_contract_id_and_overlapping_periods_block(self):
        row = SAMPLES["contracts"]
        self.put("contracts", rows=[row, dict(row, employee_id="0002")])
        with self.assertRaisesRegex(PayrollInputError, "duplicate key"):
            read_payroll_inputs(self.root, roles=["contracts"])
        self.put("contracts", rows=[row, dict(row, contract_id="C02",
                                  calculation_period_from="2026-11-15",
                                  calculation_period_to="2026-12-15")])
        with self.assertRaisesRegex(PayrollInputError, "overlapping declared periods"):
            read_payroll_inputs(self.root, roles=["contracts"])

    def test_optional_zero_row_workbook_is_valid(self):
        self.put("allowance_assignments", rows=[])
        self.assertEqual(read_payroll_inputs(self.root, roles=["allowance_assignments"])
                         .for_role("allowance_assignments"), ())
        self.put("contracts", rows=[])
        with self.assertRaisesRegex(PayrollInputError, "at least one"):
            read_payroll_inputs(self.root, roles=["contracts"])

    def test_cross_file_reference_and_exact_bonus_allocation(self):
        self.put("contracts")
        self.put("allowance_assignments", rows=[dict(SAMPLES["allowance_assignments"], contract_id="BAD")])
        with self.assertRaisesRegex(PayrollInputError, "unmatched"):
            read_payroll_inputs(self.root, roles=["contracts", "allowance_assignments"])
        self.put("bonus_budget")
        self.put("bonus_allocation", rows=[dict(SAMPLES["bonus_allocation"], allocation_ratio=0.9)])
        with self.assertRaisesRegex(PayrollInputError, "sum must equal 1"):
            read_payroll_inputs(self.root, roles=["bonus_budget", "bonus_allocation"])
        self.put("bonus_allocation", rows=[dict(SAMPLES["bonus_allocation"], allocation_ratio=1.5)])
        with self.assertRaisesRegex(PayrollInputError, "ratio must be 0..1"):
            read_payroll_inputs(self.root, roles=["bonus_allocation"])

    def test_bonus_scope_requires_exactly_one_of_team_or_project(self):
        self.put("bonus_budget", rows=[dict(SAMPLES["bonus_budget"], team_id=None, project_id=None)])
        with self.assertRaisesRegex(PayrollInputError, "exactly one"):
            read_payroll_inputs(self.root, roles=["bonus_budget"])
        self.put("bonus_budget", rows=[dict(SAMPLES["bonus_budget"], team_id="T", project_id="P")])
        with self.assertRaises(PayrollInputError):
            read_payroll_inputs(self.root, roles=["bonus_budget"])

    def test_modified_file_during_read_is_blocked(self):
        self.put("contracts")
        with patch("bhandara.payroll.input_excel.sha256_file", side_effect=["before", "after"]):
            with self.assertRaisesRegex(PayrollInputError, "changed during read"):
                read_payroll_inputs(self.root, roles=["contracts"])

    def test_preserved_physical_row_numbers_after_blank_row(self):
        self.put("contracts", rows=[SAMPLES["contracts"], {}, dict(SAMPLES["contracts"],
                              employee_id="0002", contract_id="C02", daily_base_rate=None)])
        with self.assertRaisesRegex(PayrollInputError, "row 4, daily_base_rate"):
            read_payroll_inputs(self.root, roles=["contracts"])


if __name__ == "__main__":
    unittest.main()
