"""Synthetic, review-only tests for the new Payroll composition primitives."""
import unittest
from decimal import Decimal

from bhandara.payroll.core import (
    PayrollCoreError, allocate_performance_bonus, build_partial_payroll,
    resolve_contract_pay, resolve_fixed_allowances, resolve_deduction_mapping,
)


def contract(employee="E001", **overrides):
    row = dict(employee_id=employee, contract_id=f"C-{employee}",
               pay_basis="MONTHLY", amount_type="BASE", contract_amount=3000000,
               daily_base_rate=100000, deduction_code="INS-2026-A",
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


    def deduction_policy(self, **overrides):
        row = dict(deduction_code="INS-2026-A", national_pension="0.0475",
                   health_insurance="0.03595", longterm_care="0.1314",
                   employment_insurance="0.009", source_ref="EXAMPLE")
        row.update(overrides)
        return row

    def test_deduction_policy_referenced_from_contract_only(self):
        policies = [self.deduction_policy()]
        resolved = resolve_deduction_mapping(self.contracts, policies)
        self.assertEqual(resolved["E001"]["deduction_code"], "INS-2026-A")
        self.assertEqual(resolved["E002"]["rates"]["longterm_care"], Decimal("0.1314"))
        self.assertNotIn("employee_id", policies[0])
        self.assertNotIn("deduction_total", resolved["E001"])

    def test_deduction_policy_follows_new_contract_code(self):
        changed = resolve_contract_pay([
            contract("E001", contract_id="C-NEW", deduction_code="INS-2026-B")
        ])
        result = resolve_deduction_mapping(
            changed, [self.deduction_policy(deduction_code="INS-2026-B")])
        self.assertEqual(result["E001"]["deduction_code"], "INS-2026-B")

    def test_deduction_missing_duplicate_and_invalid_rates_block(self):
        policy = self.deduction_policy()
        with self.assertRaisesRegex(PayrollCoreError, "duplicated deduction"):
            resolve_deduction_mapping(self.contracts, [policy, policy])
        with self.assertRaisesRegex(PayrollCoreError, "unknown deduction_code"):
            resolve_deduction_mapping(self.contracts, [])
        with self.assertRaisesRegex(PayrollCoreError, "rate must be 0..1"):
            resolve_deduction_mapping(self.contracts, [
                self.deduction_policy(longterm_care="1.5")
            ])
        with self.assertRaises(PayrollCoreError):
            resolve_deduction_mapping(self.contracts, [
                self.deduction_policy(health_insurance=None)
            ])

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
