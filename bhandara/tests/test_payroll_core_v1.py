"""Synthetic, review-only tests for the new Payroll composition primitives."""
import unittest
from decimal import Decimal

from bhandara.payroll.core import (
    PayrollCoreError, allocate_performance_bonus, build_partial_payroll,
    resolve_contract_pay, resolve_fixed_allowances,
)


def contract(employee="E001", **overrides):
    row = dict(employee_id=employee, contract_id=f"C-{employee}",
               pay_basis="MONTHLY", amount_type="BASE", contract_amount=3000000,
               daily_base_rate=100000,
               payment_date="2026-12-05", calculation_period_from="2026-11-01",
               calculation_period_to="2026-11-30")
    row.update(overrides)
    return row


class PayrollCoreV1Tests(unittest.TestCase):
    def setUp(self):
        self.contracts = resolve_contract_pay([contract(), contract("E002")])
        self.map = [dict(allowance_id="001", level="L1", amount=100000,
                         payroll_taxability="TAXABLE"),
                    dict(allowance_id="001", level="L2", amount=200000,
                         payroll_taxability="TAXABLE"),
                    dict(allowance_id="002", level="L1", amount=150000,
                         payroll_taxability="NON_TAXABLE", taxability_policy_ref="TEST-MEAL")]

    def test_base_plus_mapped_fixed_allowance(self):
        rows = resolve_fixed_allowances(self.contracts, self.map, [
            dict(contract_id="C-E001", allowance_id="001", level="L2"),
            dict(contract_id="C-E001", allowance_id="002", level="L1")])
        self.assertEqual(sum(v["amount"] for v in rows["E001"]), Decimal(350000))
        self.assertEqual(rows["E001"][1]["payroll_taxability"], "NON_TAXABLE")

    def test_total_requires_explicit_base_and_reconciles(self):
        valid = resolve_contract_pay([contract(amount_type="TOTAL", declared_base_amount=2800000)])
        allowances = resolve_fixed_allowances(valid, self.map, [
            dict(contract_id="C-E001", allowance_id="001", level="L2")])
        self.assertEqual(valid["E001"]["base_pay"] + allowances["E001"][0]["amount"], 3000000)
        with self.assertRaises(PayrollCoreError):
            resolve_contract_pay([contract(amount_type="TOTAL")])
        with self.assertRaises(PayrollCoreError):
            resolve_fixed_allowances(valid, self.map, [])

    def test_annual_instalments_are_explicit(self):
        annual = resolve_contract_pay([contract(pay_basis="ANNUAL", contract_amount=36000000,
                                                installments_per_year=12)])
        self.assertEqual(annual["E001"]["base_pay"], 3000000)
        with self.assertRaises(PayrollCoreError):
            resolve_contract_pay([contract(pay_basis="ANNUAL", contract_amount=36000000)])

    def test_weekly_is_supported(self):
        self.assertEqual(resolve_contract_pay([contract(pay_basis="WEEKLY", contract_amount=700000)])
                         ["E001"]["base_pay"], 700000)

    def test_duplicate_contract_and_allowance_block(self):
        with self.assertRaises(PayrollCoreError):
            resolve_contract_pay([contract(), contract()])
        with self.assertRaises(PayrollCoreError):
            resolve_fixed_allowances(self.contracts, self.map, [
                dict(contract_id="C-E001", allowance_id="001", level="L1"),
                dict(contract_id="C-E001", allowance_id="001", level="L2")])

    def test_contract_id_uniqueness_required(self):
        with self.assertRaisesRegex(PayrollCoreError, "duplicate contract_id"):
            resolve_contract_pay([contract(), contract("E002", contract_id="C-E001")])

    def test_new_contract_does_not_inherit_old_allowance_assignment(self):
        negotiated = resolve_contract_pay([
            contract(employee="E001", contract_id="C-NEW", contract_amount=3300000)
        ])
        with self.assertRaisesRegex(PayrollCoreError, "unknown or expired contract"):
            resolve_fixed_allowances(negotiated, self.map, [
                dict(contract_id="C-E001", allowance_id="001", level="L1")
            ])
        new = resolve_fixed_allowances(negotiated, self.map, [
            dict(contract_id="C-NEW", allowance_id="001", level="L1")
        ])
        self.assertEqual(new["E001"][0]["amount"], Decimal(100000))

    def test_selected_contract_requires_no_daily_minutes(self):
        selected = resolve_contract_pay([contract()])
        self.assertNotIn("standard_day_minutes", selected["E001"])
        rows = resolve_fixed_allowances(selected, self.map, [
            dict(contract_id="C-E001", allowance_id="001", level="L1")
        ])
        self.assertEqual(rows["E001"][0]["level"], "L1")

    def test_missing_allowance_level_blocks(self):
        with self.assertRaises(PayrollCoreError):
            resolve_fixed_allowances(self.contracts, self.map, [
                dict(contract_id="C-E001", allowance_id="999", level="L1")])

    def test_bonus_two_sources_and_exact_sum(self):
        budgets = [dict(bonus_id="B1", team_id="T1", project_id="", budget_amount=1000000),
                   dict(bonus_id="B2", team_id="", project_id="P1", budget_amount=100000)]
        assignments = [dict(bonus_id="B1", employee_id="E001", allocation_ratio="0.3"),
                       dict(bonus_id="B1", employee_id="E002", allocation_ratio="0.7"),
                       dict(bonus_id="B2", employee_id="E001", allocation_ratio="1")]
        bonuses = allocate_performance_bonus(self.contracts, budgets, assignments)
        self.assertEqual(sum(v["amount"] for v in bonuses["E001"]), 400000)
        self.assertEqual(bonuses["E002"][0]["amount"], 700000)
        preview = build_partial_payroll(self.contracts, {}, bonuses)
        self.assertEqual(preview[0]["partial_gross_pay"], 3400000)
        self.assertEqual(preview[0]["status"], "PARTIAL_REVIEW_ONLY")

    def test_bonus_integer_remainder_is_conserved(self):
        bonuses = allocate_performance_bonus(self.contracts, [dict(bonus_id="B", team_id="T", budget_amount=101)],
                                             [dict(bonus_id="B", employee_id="E001", allocation_ratio="0.5"),
                                              dict(bonus_id="B", employee_id="E002", allocation_ratio="0.5")])
        self.assertEqual([bonuses[x][0]["amount"] for x in ("E001", "E002")], [51, 50])

    def test_bonus_incomplete_budget_blocked(self):
        with self.assertRaises(PayrollCoreError):
            allocate_performance_bonus(self.contracts,
                                       [dict(bonus_id="B", team_id="T", budget_amount=100)],
                                       [dict(bonus_id="B", employee_id="E001", allocation_ratio="0.9")])

    def test_bonus_requires_exactly_one_scope(self):
        with self.assertRaises(PayrollCoreError):
            allocate_performance_bonus(self.contracts,
                                       [dict(bonus_id="B", team_id="T", project_id="P", budget_amount=100)], [])

    def test_invalid_amount_or_rate_is_blocked(self):
        with self.assertRaises(PayrollCoreError):
            resolve_contract_pay([contract(daily_base_rate=0)])
        with self.assertRaises(PayrollCoreError):
            resolve_fixed_allowances(self.contracts,
                                     [dict(allowance_id="001", level="L1", amount=100,
                                           payroll_taxability="WRONG")], [])


if __name__ == "__main__":
    unittest.main()
