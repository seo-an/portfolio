"""P1-5b-2b-2: independently approved wage decisions never double-reduce PTO."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import (
    build_contract_scoped_overtime_preview,
)
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.leave_wage_adjustments import (
    LeaveWageAdjustmentError, reconcile_leave_wage_decisions,
)
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.tests.test_payroll_attendance_settlement_p1 import event, wage_plan
from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import (
    ROLES, ROLLUP, source_registry,
)
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
from bhandara.tests.test_payroll_pto_closing_review_p1 import PTOClosingBridgeTests
from bhandara.tests.test_payroll_segmented_settlement_p1 import contract, plan
from bhandara.worktime.output_excel import write_worktime_xlsx


def decision(request, *, amount=0, treatment="PAID_LEAVE",
             fixed=None, **override):
    data = {
        "employee_id": "0001", "request_id": request,
        "leave_date": "2026-11-02", "pto_leave_type": "연차",
        "treatment": treatment, "base_reduction_won": amount,
        "fixed_reductions": [] if fixed is None else fixed,
        "approval_status": "APPROVED",
        "approval_ref": f"PAY-APPROVAL-{request}",
        "evidence_ref": f"PAY-LEDGER-{request}",
        "base_not_pre_adjusted": True,
        "fixed_not_pre_adjusted": True,
    }
    data.update(override)
    return data


def policy_plan(*, decisions=None, **overrides):
    plan_value = {
        "schema_version": "0.1",
        "pto_closing_id": "Closing-4.4-2026",
        "policy_ref": "EXTERNAL-PTO-WAGE-POLICY",
        "decisions": [] if decisions is None else decisions,
    }
    plan_value.update(overrides)
    return plan_value


class LeaveWageDecisionTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.fixture = PTOClosingBridgeTests("test_two_independent_same_day_requests_exact_quantity")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.files()
        self.pto_review = self.fixture.review()
        self.attendance_review = {
            "events": [{
                "event_id": "EV1", "employee_id": "0001",
                "work_date": "2026-11-02", "event_kind": "LEAVE",
                "base_reduction_won": 0,
            }]
        }

    def review(self, decisions):
        return reconcile_leave_wage_decisions(
            self.pto_review, self.attendance_review,
            wage_plan=policy_plan(decisions=decisions),
        )

    def valid(self, **kwargs):
        settings = {"treatment": "UNPAID_LEAVE", "amount": 60000}
        settings.update(kwargs)
        return [decision("R1"), decision("R2", **settings)]

    def test_mixed_paid_unpaid_on_same_day_independent_money(self):
        reviewed = self.review(self.valid(fixed=[
            {"allowance_id": "001", "amount_won": 15000,
             "policy_ref": "ALLOWANCE-ABSENCE-POLICY"}
        ]))
        self.assertEqual(reviewed["base_reductions_by_employee"], {"0001": 60000})
        self.assertEqual(reviewed["fixed_reductions_by_employee"]["0001"], {"001": 15000})
        self.assertFalse(reviewed["earnings_complete"])

    def test_reject_missing_or_extra_decisions_unapproved_or_amount_errors(self):
        cases = (
            [decision("R1")],
            self.valid() + [decision("OTHER")],
            self.valid(approval_status="PENDING"),
            self.valid(base_not_pre_adjusted=False),
            self.valid(fixed_not_pre_adjusted=False),
            self.valid(amount=-1),
            self.valid(amount=60.5),
            self.valid(amount=0),
            [decision("R1", amount=10), decision("R2", treatment="UNPAID_LEAVE", amount=60000)],
            self.valid(fixed=[{"allowance_id": "001", "amount_won": 0,
                               "policy_ref": "POLICY"}]),
            self.valid(fixed=[{"allowance_id": "001", "amount_won": 10,
                               "policy_ref": "POLICY"},
                              {"allowance_id": "001", "amount_won": 20,
                               "policy_ref": "POLICY"}]),
            self.valid(fixed=[{"allowance_id": "001", "amount_won": 10,
                               "policy_ref": ""}]),
            self.valid(approval_ref=""),
            self.valid(evidence_ref=""),
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(LeaveWageAdjustmentError):
                self.review(values)

    def test_unconfirmed_snapshot_or_different_closing_or_unknown_field_block(self):
        for args in (
            {"pto_closing_id": "Closing-3.4-2026"},
            {"policy_ref": ""},
            {"schema_version": "2"},
            {"extra": 1},
        ):
            with self.subTest(args=args), self.assertRaises(LeaveWageAdjustmentError):
                reconcile_leave_wage_decisions(
                    self.pto_review, self.attendance_review,
                    wage_plan=policy_plan(decisions=self.valid(), **args),
                )
        bad = dict(self.pto_review, closing_confirmed=False)
        with self.assertRaisesRegex(LeaveWageAdjustmentError, "confirmed"):
            reconcile_leave_wage_decisions(
                bad, self.attendance_review,
                wage_plan=policy_plan(decisions=self.valid()),
            )


class LeaveWageExcelFlowTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "payroll").mkdir()
        fixture = PTOClosingBridgeTests("test_two_independent_same_day_requests_exact_quantity")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.files()
        self.fixture = fixture

    def prepare(self, *, include_fixed=True):
        values = {
            "contracts": [contract()],
            "allowance_assignments": (
                [{"contract_id": "C-OLD", "allowance_id": "001", "level": "L1"}]
                if include_fixed else []),
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])],
            "bonus_budget": [], "bonus_allocation": [],
            "overtime_rules": [rate(minimum_minutes=0)],
        }
        for role in ROLES:
            schema = SCHEMA["workbooks"][role]
            book = Workbook()
            book.active.title = schema["sheet"]
            book.active.append(schema["columns"])
            for record in values[role]:
                book.active.append([record.get(name) for name in schema["columns"]])
            book.save(self.root / "payroll" / schema["filename"])
            book.close()
        return read_payroll_inputs(self.root, roles=ROLES)

    def run_flow(self, decisions=None, *, anchor_amount=0,
                 anchor_treatment="PAID_LEAVE", include_fixed=True,
                 wage_present=True, pto_present=True):
        inputs = self.prepare(include_fixed=include_fixed)
        worktime = self.root / "worktime-result.xlsx"
        if not worktime.exists():
            write_worktime_xlsx(
                {"schema_version": "0.1", "rows": self.fixture.worktime},
                worktime,
            )
        sha = sha256_file(worktime)
        first = event(
            treatment=anchor_treatment, amount=anchor_amount,
            code="ANNUAL_QUARTER", request_id="R1",
            start_at="2026-11-02T09:00", end_at="2026-11-02T11:00",
            approved_minutes=120,
        )
        return build_contract_scoped_overtime_preview(
            inputs, worktime, settlement_plan=plan(),
            attendance_plan=wage_plan(items=[first], sha=sha),
            period_from="2026-11-01", period_to="2026-11-30",
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry([], [], [rate(minimum_minutes=0)]),
            rate_policy=policy(
                reference_day_minutes_by_contract={"C-OLD": 480},
            ),
            rollup_policy=ROLLUP,
            pto_sources=({
                "usage_file": self.fixture.usage_path,
                "closing_file": self.fixture.closing_path,
                "deduction_file": self.fixture.deduction_path,
                "pto_claims": self.fixture.claims,
            } if pto_present else None),
            pto_wage_plan=(
                policy_plan(decisions=decisions)
                if wage_present else None
            ),
        )

    def test_existing_paid_anchor_and_extra_unpaid_reduce_base_once_and_fixed(self):
        fixed = [{"allowance_id": "001", "amount_won": 15000,
                  "policy_ref": "SYNTHETIC-ALLOWANCE-PRORATION"}]
        result = self.run_flow(decisions=[decision("R1"),
            decision("R2", treatment="UNPAID_LEAVE", amount=60000, fixed=fixed)])
        register = result["payroll_register"]
        row = register["rows"][0]
        self.assertEqual(row["base_pay"], 2940000)
        self.assertEqual(row["fixed_allowances:001"], 85000)
        self.assertIsNone(row["gross_pay"])
        self.assertIsNone(row["deduction_total"])
        self.assertIsNone(row["net_pay"])
        self.assertEqual(row["review_status"], "PARTIAL_REVIEW_ONLY")
        self.assertEqual(result["settlement_review"]["employees"][0]["base_reduction_candidate"], 60000)
        self.assertEqual(result["pto_wage_review"]["base_reductions_by_employee"]["0001"], 60000)
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        target = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(register, target)
        book = load_workbook(target)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
        finally:
            book.close()

    def test_paid_leave_plus_unpaid_anchor_no_double_base_charge(self):
        reviewed = self.run_flow(
            decisions=[
                decision("R1", treatment="UNPAID_LEAVE", amount=40000),
                decision("R2", treatment="UNPAID_LEAVE", amount=60000),
            ],
            anchor_amount=40000, anchor_treatment="UNPAID_LEAVE",
        )
        self.assertEqual(reviewed["payroll_register"]["rows"][0]["base_pay"], 2900000)
        self.assertEqual(reviewed["settlement_review"]["employees"][0]["base_reduction_candidate"], 100000)

    def test_conflicting_anchor_decision_and_wrong_treatment_block(self):
        with self.assertRaisesRegex(LeaveWageAdjustmentError, "conflicts"):
            self.run_flow(decisions=[
                decision("R1", treatment="UNPAID_LEAVE", amount=40000),
                decision("R2", treatment="UNPAID_LEAVE", amount=60000),
            ])
        with self.assertRaisesRegex(LeaveWageAdjustmentError, "conflicts"):
            self.run_flow(decisions=[
                decision("R1", treatment="PAID_LEAVE"),
                decision("R2", treatment="UNPAID_LEAVE", amount=60000),
            ], anchor_amount=40000, anchor_treatment="UNPAID_LEAVE")

    def test_fixed_allowance_missing_or_excessive_reduction_fails_before_output(self):
        for include_fixed, value in ((False, 10000), (True, 100001)):
            with self.subTest(allowance=include_fixed), self.assertRaisesRegex(
                LeaveWageAdjustmentError, "fixed allowance"
            ):
                self.run_flow(decisions=[
                    decision("R1"),
                    decision("R2", treatment="UNPAID_LEAVE", amount=60000,
                             fixed=[{"allowance_id": "001", "amount_won": value,
                                     "policy_ref": "EXPLICIT-ALLOWANCE-POLICY"}]),
                ], include_fixed=include_fixed)

    def test_no_optional_plan_preserves_existing_review_amounts(self):
        result = self.run_flow(wage_present=False)
        self.assertNotIn("pto_wage_review", result)
        self.assertEqual(result["payroll_register"]["rows"][0]["base_pay"], 3000000)
        self.assertEqual(result["payroll_register"]["rows"][0]["fixed_allowances:001"], 100000)

    def test_no_silent_without_verified_pto_sources(self):
        from bhandara.payroll.contract_scoped_overtime import ContractOvertimeAdapterError
        with self.assertRaisesRegex(ContractOvertimeAdapterError, "verified PTO sources"):
            self.run_flow(
                decisions=[decision("R1"),
                           decision("R2", treatment="UNPAID_LEAVE", amount=60000)],
                pto_present=False,
            )


if __name__ == "__main__":
    unittest.main()
