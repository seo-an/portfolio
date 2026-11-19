"""P1-5a: declared employment coverage and split contract salary previews."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.payroll.contract_period import select_contracts_for_period, PayrollPeriodError
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.segmented_settlement import (
    SettlementPreviewError, build_segmented_settlement_preview,
)
from bhandara.payroll.settlement_coverage import (
    SettlementCoverageError, validate_settlement_coverage,
)
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES


FROM, TO = "2026-11-01", "2026-11-30"
ROLES = (
    "contracts", "allowance_assignments", "fixed_allowance_map",
    "bonus_budget", "bonus_allocation",
)


def contract(worker="0001", contract_id="C-OLD", **updates):
    row = deepcopy(SAMPLES["contracts"])
    row.update({
        "employee_id": worker, "contract_id": contract_id,
        "pay_basis": "MONTHLY", "contract_amount": 3000000,
        "amount_type": "BASE", "declared_base_amount": None,
        "calculation_period_from": FROM, "calculation_period_to": TO,
        "payment_date": "2026-12-10",
    })
    row.update(updates)
    return row


def employment(worker="0001", hired="2024-01-01", terminated=None, **updates):
    row = {
        "employee_id": worker, "hired_on": hired, "terminated_on": terminated,
        "status": "VERIFIED", "evidence_ref": f"VERIFIED-{worker}",
    }
    row.update(updates)
    return row


def allocated(contract_id="C-OLD", start=FROM, end=TO, worker="0001", **updates):
    row = {
        "employee_id": worker, "contract_id": contract_id,
        "segment_from": start, "segment_to": end,
        "approval_status": "APPROVED",
        "approval_ref": f"APPROVAL-{contract_id}",
        "policy_ref": "EXTERNAL-CALENDAR-DAYS-SYNTHETIC",
    }
    row.update(updates)
    return row


def plan(*, facts=None, allocations=None, **updates):
    row = {
        "schema_version": "0.1", "period_from": FROM, "period_to": TO,
        "snapshot_ref": "SYNTHETIC-EMPLOYMENT-SNAPSHOT",
        "proration_method": "CALENDAR_DAYS", "rounding_mode": "DOWN",
        "employment_facts": [employment()] if facts is None else facts,
        "allocations": [allocated()] if allocations is None else allocations,
    }
    row.update(updates)
    return row


def split():
    return [
        contract(contract_id="C-OLD", calculation_period_to="2026-11-15"),
        contract(contract_id="C-NEW", contract_amount=3600000,
                 calculation_period_from="2026-11-16"),
    ]


def split_plan(**updates):
    return plan(allocations=[
        allocated(contract_id="C-OLD", end="2026-11-15"),
        allocated(contract_id="C-NEW", start="2026-11-16"),
    ], **updates)


class SettlementCoverageP15aTests(unittest.TestCase):
    def coverage(self, rows=None, spec=None, start=FROM, end=TO):
        return validate_settlement_coverage(
            [contract()] if rows is None else rows,
            plan=plan() if spec is None else spec,
            period_from=start, period_to=end,
        )

    def test_p0_still_rejects_mid_cycle_without_new_plan(self):
        with self.assertRaisesRegex(PayrollPeriodError, "partial coverage"):
            select_contracts_for_period(split(), period_from=FROM, period_to=TO)

    def test_two_contracts_approved_cover_entire_month(self):
        result = self.coverage(split(), split_plan())
        self.assertEqual(result["denominator_days"], 30)
        self.assertEqual([s["days"] for s in result["segments_by_employee"]["0001"]], [15, 15])
        self.assertEqual(result["source_authenticity"], "NOT_AUTHENTICATED_BY_THIS_MODULE")
        self.assertFalse(result["earnings_complete"])

    def test_hire_inside_month_requires_explicit_employment_proof(self):
        spec = plan(facts=[employment(hired="2026-11-11")],
                    allocations=[allocated(start="2026-11-11")])
        result = self.coverage(spec=spec)
        self.assertEqual(result["segments_by_employee"]["0001"][0]["days"], 20)
        with self.assertRaisesRegex(SettlementCoverageError, "gap or overlap"):
            self.coverage(spec=plan(facts=[employment(hired="2026-11-11")]))

    def test_termination_inside_month_must_end_on_last_employed_day(self):
        spec = plan(facts=[employment(terminated="2026-11-20")],
                    allocations=[allocated(end="2026-11-20")])
        result = self.coverage(spec=spec)
        self.assertEqual(result["segments_by_employee"]["0001"][0]["days"], 20)
        with self.assertRaisesRegex(SettlementCoverageError, "fully covered"):
            self.coverage(spec=plan(facts=[employment(terminated="2026-11-20")],
                                    allocations=[allocated(end="2026-11-19")]))

    def test_missing_middle_contract_day_blocks_instead_of_assuming_unpaid_leave(self):
        rows = split()
        spec = plan(allocations=[
            allocated(end="2026-11-15"),
            allocated(contract_id="C-NEW", start="2026-11-17"),
        ])
        with self.assertRaisesRegex(SettlementCoverageError, "gap or overlap"):
            self.coverage(rows, spec)

    def test_partial_contract_not_in_plan_is_not_silently_ignored(self):
        with self.assertRaisesRegex(SettlementCoverageError, "missing declared"):
            self.coverage(split(), plan(allocations=[allocated(end="2026-11-15")]))

    def test_wrong_contract_worker_or_outside_declared_dates_blocks(self):
        rows = split()
        for changed in (
            allocated(contract_id="DOES-NOT-EXIST", end="2026-11-15"),
            allocated(contract_id="C-NEW", start=FROM, end="2026-11-15"),
            allocated(contract_id="C-OLD", start="2026-10-31", end="2026-11-15"),
            allocated(contract_id="C-OLD", worker="0002", end="2026-11-15"),
        ):
            with self.subTest(changed=changed), self.assertRaises(SettlementCoverageError):
                self.coverage(rows, plan(allocations=[changed]))

    def test_refusal_for_unsupported_policy_missing_refs_or_unapproved(self):
        for update in (
            {"rounding_mode": "DEFAULT"},
            {"proration_method": "SCHEDULED_DAYS"},
            {"snapshot_ref": ""},
            {"period_from": "2026-10-01"},
            {"allocations": [allocated(approval_status="PENDING")]},
            {"allocations": [allocated(policy_ref="")]},
            {"allocations": [allocated(approval_ref="")]},
            {"employment_facts": [employment(status="PENDING")]},
            {"employment_facts": [employment(evidence_ref="")]},
            {"unexpected": 1},
        ):
            with self.subTest(update=update), self.assertRaises(SettlementCoverageError):
                self.coverage(spec=plan(**update))

    def test_duplicate_allocation_ref_and_missing_employment_block(self):
        spec = split_plan()
        spec["allocations"][1]["approval_ref"] = "APPROVAL-C-OLD"
        with self.assertRaisesRegex(SettlementCoverageError, "duplicate approval"):
            self.coverage(split(), spec)
        with self.assertRaisesRegex(SettlementCoverageError, "missing employee"):
            self.coverage(spec=plan(facts=[]))

    def test_reversed_or_noncanonical_dates_and_nonemployed_employee_block(self):
        for date in ("2026-11-31", "2026-11-1", "2026/11/01"):
            with self.subTest(date=date), self.assertRaises(SettlementCoverageError):
                self.coverage(spec=plan(facts=[employment(hired=date)]))
        with self.assertRaisesRegex(SettlementCoverageError, "outside payroll"):
            self.coverage(spec=plan(facts=[employment(terminated="2026-10-01")]))
        with self.assertRaisesRegex(SettlementCoverageError, "termination before hire"):
            self.coverage(spec=plan(facts=[employment(hired="2026-11-20",
                                                       terminated="2026-11-01")]))

    def test_mixed_payment_dates_and_unexpected_cycle_block(self):
        rows = split()
        rows[1]["payment_date"] = "2026-12-20"
        with self.assertRaisesRegex(SettlementCoverageError, "different payment"):
            self.coverage(rows, split_plan())
        with self.assertRaisesRegex(SettlementCoverageError, "incompatible pay-cycle"):
            self.coverage([contract(pay_basis="WEEKLY")])

    def test_weekly_proportional_cycle_requires_exact_week(self):
        start, end = "2026-11-02", "2026-11-08"
        row = contract(pay_basis="WEEKLY", contract_amount=700000,
                       calculation_period_from=start, calculation_period_to=end)
        spec = plan(
            period_from=start, period_to=end,
            facts=[employment(hired="2026-11-04")],
            allocations=[allocated(start="2026-11-04", end=end)],
        )
        result = self.coverage([row], spec, start, end)
        self.assertEqual(result["denominator_days"], 7)
        self.assertEqual(result["segments_by_employee"]["0001"][0]["days"], 5)

    def test_employee_different_from_contract_does_not_gain_extra_wages(self):
        with self.assertRaisesRegex(SettlementCoverageError, "duplicate or unselected"):
            self.coverage(spec=plan(facts=[employment(), employment(worker="0002")]))


class SegmentedSettlementPreviewP15aTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "payroll").mkdir()

    def prepare(self, *, contracts=None, assignments=None, mapping=None,
                budgets=None, allocations=None):
        data = {
            "contracts": [contract()] if contracts is None else contracts,
            "allowance_assignments": [] if assignments is None else assignments,
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])] if mapping is None else mapping,
            "bonus_budget": [] if budgets is None else budgets,
            "bonus_allocation": [] if allocations is None else allocations,
        }
        for role, rows in data.items():
            schema = SCHEMA["workbooks"][role]
            book = Workbook()
            book.active.title = schema["sheet"]
            book.active.append(schema["columns"])
            for row in rows:
                book.active.append([row.get(field) for field in schema["columns"]])
            book.save(self.root / "payroll" / schema["filename"])
            book.close()
        return read_payroll_inputs(self.root, roles=ROLES)

    def view(self, inputs, spec=None, start=FROM, end=TO):
        return build_segmented_settlement_preview(
            inputs, settlement_plan=plan() if spec is None else spec,
            period_from=start, period_to=end,
        )

    def test_split_base_and_fixed_allowances_aggregate_by_item_before_rounding(self):
        mapping = [
            deepcopy(SAMPLES["fixed_allowance_map"]),
            dict(SAMPLES["fixed_allowance_map"], level="L2", amount=200000),
        ]
        data = self.prepare(
            contracts=split(), mapping=mapping,
            assignments=[
                dict(contract_id="C-OLD", allowance_id="001", level="L1"),
                dict(contract_id="C-NEW", allowance_id="001", level="L2"),
            ],
        )
        preview = self.view(data, split_plan())
        row = preview["payroll_register"]["rows"][0]
        self.assertEqual(row["base_pay"], 3300000)
        self.assertEqual(row["fixed_allowances:001"], 150000)
        self.assertIsNone(row["gross_pay"])
        self.assertIsNone(row["deduction_total"])
        self.assertIsNone(row["net_pay"])
        self.assertEqual(row["review_status"], "PARTIAL_REVIEW_ONLY")
        self.assertEqual(preview["status"], "PARTIAL_REVIEW_ONLY")
        self.assertEqual(preview["settlement_review"]["employment_coverage"],
                         "DECLARED_COVERAGE_MATCHED")
        self.assertEqual(preview["settlement_review"]["employees"][0]["segments"][0]["days"], 15)
        result_file = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(preview["payroll_register"], result_file)
        book = load_workbook(result_file)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            keys = [col["key"] for col in preview["payroll_register"]["columns"]]
            self.assertEqual(book.active.cell(3, keys.index("base_pay") + 1).value, 3300000)
            self.assertEqual(book.active.cell(3, keys.index("fixed_allowances:001") + 1).value, 150000)
        finally:
            book.close()

    def test_hire_and_termination_prorate_without_assuming_leave_deduction(self):
        data = self.prepare()
        hired = self.view(
            data, plan(facts=[employment(hired="2026-11-11")],
                       allocations=[allocated(start="2026-11-11")]),
        )
        fired = self.view(
            data, plan(facts=[employment(terminated="2026-11-20")],
                       allocations=[allocated(end="2026-11-20")]),
        )
        self.assertEqual(hired["payroll_register"]["rows"][0]["base_pay"], 2000000)
        self.assertEqual(fired["payroll_register"]["rows"][0]["base_pay"], 2000000)
        for value in (hired, fired):
            self.assertEqual(value["settlement_review"]["unpaid_leave_adjustments"], "NOT_ASSESSED")
            self.assertIsNone(value["payroll_register"]["rows"][0]["net_pay"])

    def test_annual_12_installments_cycle_rate_can_be_prorated(self):
        data = self.prepare(contracts=[contract(
            pay_basis="ANNUAL", contract_amount=36000000, installments_per_year=12,
        )])
        result = self.view(
            data, plan(facts=[employment(hired="2026-11-16")],
                       allocations=[allocated(start="2026-11-16")]),
        )
        self.assertEqual(result["payroll_register"]["rows"][0]["base_pay"], 1500000)

    def test_employee_item_period_rounding_not_per_contract_segment(self):
        data = self.prepare(contracts=[
            contract(contract_id="C-OLD", contract_amount=1001,
                     calculation_period_to="2026-11-15"),
            contract(contract_id="C-NEW", contract_amount=1001,
                     calculation_period_from="2026-11-16"),
        ])
        result = self.view(data, split_plan())
        self.assertEqual(result["payroll_register"]["rows"][0]["base_pay"], 1001)

    def test_bonus_paid_once_from_external_budget_allocation_not_prorated(self):
        data = self.prepare(
            budgets=[dict(SAMPLES["bonus_budget"], budget_amount=1000)],
            allocations=[dict(SAMPLES["bonus_allocation"], allocation_ratio=1)],
        )
        value = self.view(
            data, plan(facts=[employment(hired="2026-11-11")],
                       allocations=[allocated(start="2026-11-11")]),
        )
        bonus_id = SAMPLES["bonus_budget"]["bonus_id"]
        self.assertEqual(value["payroll_register"]["rows"][0][f"performance_bonuses:{bonus_id}"], 1000)
        self.assertIsNone(value["payroll_register"]["rows"][0]["gross_pay"])

    def test_taxability_change_across_contracts_blocks_one_column_aggregation(self):
        first = deepcopy(SAMPLES["fixed_allowance_map"])
        second = dict(first, level="L2", amount=200000, payroll_taxability="NON_TAXABLE")
        data = self.prepare(
            contracts=split(), mapping=[first, second],
            assignments=[
                dict(contract_id="C-OLD", allowance_id="001", level="L1"),
                dict(contract_id="C-NEW", allowance_id="001", level="L2"),
            ],
        )
        with self.assertRaisesRegex(SettlementPreviewError, "classification changed"):
            self.view(data, split_plan())

    def test_full_month_single_contract_matches_original_p0_preview_base(self):
        data = self.prepare()
        value = self.view(data)
        self.assertEqual(value["payroll_register"]["rows"][0]["base_pay"], 3000000)
        self.assertFalse(value["settlement_review"]["earnings_complete"])
        self.assertEqual(value["settlement_review"]["source_authenticity"],
                         "NOT_AUTHENTICATED_BY_THIS_MODULE")

    def test_two_workers_one_month_one_contract_split_no_duplicate_output_ids(self):
        data = self.prepare(contracts=[
            *split(), contract(worker="0002", contract_id="C-0002"),
        ])
        spec = split_plan(
            facts=[employment(), employment(worker="0002")],
        )
        spec["allocations"].append(allocated(
            worker="0002", contract_id="C-0002",
        ))
        out = self.view(data, spec)
        self.assertEqual(len(out["payroll_register"]["rows"]), 2)
        self.assertEqual([r["employee_id"] for r in out["payroll_register"]["rows"]],
                         ["0001", "0002"])
        self.assertEqual(out["payroll_register"]["rows"][1]["base_pay"], 3000000)


if __name__ == "__main__":
    unittest.main()
