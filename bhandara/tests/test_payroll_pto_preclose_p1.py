"""Same PTO exact-fraction check before and after Closing, one Payroll Flow."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import build_contract_scoped_overtime_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.leave_wage_adjustments import (
    LeaveWageAdjustmentError, reconcile_leave_wage_decisions,
)
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.pto_closing_review import (
    PTOClosingReviewError, reconcile_pto_closing,
)
from bhandara.tests.test_payroll_attendance_settlement_p1 import event, wage_plan
from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import (
    ROLES, ROLLUP, source_registry,
)
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_leave_wage_adjustments_p1 import (
    decision, policy_plan,
)
from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
from bhandara.tests.test_payroll_pto_closing_review_p1 import (
    PTOClosingBridgeTests, pto_usage, usage_detail, deduction_detail,
)
from bhandara.tests.test_payroll_segmented_settlement_p1 import contract, plan
from bhandara.worktime.output_excel import write_worktime_xlsx


class PreClosingPTOTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PTOClosingBridgeTests("test_two_independent_same_day_requests_exact_quantity")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.files()
        self.source_as_of = "2026-11-20"
        self.make_provisional()

    def make_provisional(self):
        self.fixture.usage_meta.update({
            "마감 판정 ID": "없음",
            "실행 기준일": self.source_as_of,
            "Deduction SHA256": sha256_file(self.fixture.deduction_path),
            "계산 상태": "계산 완료",
        })
        self.fixture.usage_path.write_bytes(pto_usage.make_usage_workbook(
            summary=[{"employee_id": "0001", "발생일수": 15,
                      "사용일수": self.fixture.closing_qty,
                      "잔여일수": Fraction(15) - self.fixture.closing_qty}],
            details=self.fixture.details, expiry_result=None, issues=[],
            metadata=self.fixture.usage_meta,
        ))

    def review(self, *, claims=None, closing=None):
        return reconcile_pto_closing(
            usage_file=self.fixture.usage_path,
            closing_file=closing,
            deduction_file=self.fixture.deduction_path,
            worktime_rows=self.fixture.worktime,
            pto_claims=self.fixture.claims if claims is None else claims,
            period_from="2026-11-01", period_to="2026-11-30",
        )

    def test_preclosing_uses_same_exact_request_values_and_clear_status(self):
        reviewed = self.review()
        self.assertFalse(reviewed["closing_confirmed"])
        self.assertEqual(reviewed["closing_status"], "마감 전")
        self.assertTrue(reviewed["change_possible"])
        self.assertEqual(reviewed["as_of_date"], "2026-11-20")
        self.assertEqual(reviewed["source_consistency"], "MATCHED_PROVISIONAL_AS_OF")
        self.assertEqual(reviewed["monthly_usage_days"], {"0001": "3/4"})
        self.assertEqual([r["exact_deducted_days"] for r in reviewed["requests"]],
                         ["1/4", "1/2"])
        self.assertTrue(reviewed["multiple_requests_per_workday"])
        self.assertIsNone(reviewed["source_sha256"]["closing"])
        self.assertTrue(reviewed["closing_id"].startswith("PRE_CLOSING:2026-11-20:"))
        self.assertEqual(reviewed["approval_state"], "NOT_APPROVED")

    def test_existing_confirmed_closing_must_remain_strict(self):
        self.fixture.usage_meta.pop("Deduction SHA256")
        self.fixture.usage_meta["마감 판정 ID"] = "Closing-4.4-2026"
        self.fixture.usage_meta["실행 기준일"] = "2026-12-31"
        self.fixture.files()
        reviewed = self.review(closing=self.fixture.closing_path)
        self.assertTrue(reviewed["closing_confirmed"])
        self.assertEqual(reviewed["closing_status"], "마감 확정")
        self.assertFalse(reviewed["change_possible"])
        self.assertEqual(reviewed["closing_id"], "Closing-4.4-2026")
        self.assertEqual(reviewed["monthly_usage_days"], {"0001": "3/4"})
        self.fixture.closing_meta["확정여부"] = "미확정"
        self.fixture.files()
        with self.assertRaisesRegex(PTOClosingReviewError, "confirmation required"):
            self.review(closing=self.fixture.closing_path)

    def test_preclose_requires_usage_asof_and_source_fingerprint(self):
        scenarios = (
            ("실행 기준일", "2026-10-31", "as-of outside"),
            ("실행 기준일", "2026-12-01", "as-of outside"),
            ("마감 판정 ID", "Closing-4.4-2026", "must not claim Closing"),
            ("Deduction SHA256", "a" * 64, "fingerprint mismatch"),
            ("계산 상태", "검토 필요", "unresolved provisional"),
        )
        for key, changed, reason in scenarios:
            original = self.fixture.usage_meta[key]
            with self.subTest(key=key, changed=changed):
                self.fixture.usage_meta[key] = changed
                self.make_provisional() if False else None
                self.fixture.usage_path.write_bytes(pto_usage.make_usage_workbook(
                    summary=[], details=self.fixture.details, expiry_result=None,
                    issues=[], metadata=self.fixture.usage_meta,
                ))
                with self.assertRaisesRegex(PTOClosingReviewError, reason):
                    self.review()
                self.fixture.usage_meta[key] = original
        self.make_provisional()

    def test_provisional_changes_in_snapshot_invalidate_old_wage_plan(self):
        earlier = self.review()
        old_plan = policy_plan(
            decisions=[decision("R1"),
                       decision("R2", treatment="UNPAID_LEAVE", amount=60000)],
            pto_closing_id=earlier["closing_id"],
        )
        self.fixture.usage_meta["run_id"] = "REVISED-SYNTHETIC"
        self.make_provisional()
        newer = self.review()
        self.assertNotEqual(earlier["closing_id"], newer["closing_id"])
        with self.assertRaisesRegex(LeaveWageAdjustmentError, "identity mismatch"):
            reconcile_leave_wage_decisions(
                newer, {"events": []}, wage_plan=old_plan,
            )
        approved = reconcile_leave_wage_decisions(
            newer, {"events": []},
            wage_plan={**old_plan, "pto_closing_id": newer["closing_id"]},
        )
        self.assertEqual(approved["closing_status"], "마감 전")
        self.assertTrue(approved["change_possible"])
        self.assertFalse(approved["earnings_complete"])

    def test_future_approved_deduction_not_counted_before_as_of(self):
        self.fixture.deductions.append(
            deduction_detail("R3", Fraction(1, 8))
            | {"leave_date": "2026-11-25"}
        )
        from bhandara.tests.test_payroll_pto_closing_review_p1 import pto_deduction
        self.fixture.deduction_path.write_bytes(pto_deduction.make_deduction_workbook(
            summaries=[], details=self.fixture.deductions,
            metadata={"정책 ID": "SYNTHETIC", "산정 기준일": "2026-11-30"},
        ))
        self.make_provisional()
        reviewed = self.review()
        self.assertEqual(len(reviewed["requests"]), 2)
        self.assertEqual(reviewed["monthly_usage_days"]["0001"], "3/4")
        self.assertEqual(reviewed["as_of_date"], "2026-11-20")

    def test_approved_request_omission_before_cutoff_still_blocks(self):
        self.fixture.details.pop()
        self.make_provisional()
        with self.assertRaisesRegex(PTOClosingReviewError, "populations differ"):
            self.review()

    def test_future_usage_inside_old_asof_snapshot_must_block(self):
        self.fixture.details.append(
            usage_detail("R3", Fraction(1, 8)) | {"leave_date": "2026-11-25"}
        )
        self.make_provisional()
        with self.assertRaisesRegex(PTOClosingReviewError, "future request"):
            self.review()

    def test_missing_an_external_request_is_not_accepted_with_preclose_label(self):
        with self.assertRaisesRegex(PTOClosingReviewError, "populations differ"):
            self.review(claims=[self.fixture.claims[0]])


class PreClosePayrollFlowE2E(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "payroll").mkdir()
        self.source = PreClosingPTOTests("test_preclosing_uses_same_exact_request_values_and_clear_status")
        self.source.setUp()
        self.addCleanup(self.source.doCleanups)

    def _inputs(self):
        records = {
            "contracts": [contract()],
            "allowance_assignments": [
                {"contract_id": "C-OLD", "allowance_id": "001", "level": "L1"}
            ],
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])],
            "bonus_budget": [], "bonus_allocation": [],
            "overtime_rules": [rate(minimum_minutes=0)],
        }
        for role in ROLES:
            schema = SCHEMA["workbooks"][role]
            book = Workbook()
            book.active.title = schema["sheet"]
            book.active.append(schema["columns"])
            for record in records[role]:
                book.active.append([record.get(name) for name in schema["columns"]])
            book.save(self.root / "payroll" / schema["filename"])
            book.close()
        return read_payroll_inputs(self.root, roles=ROLES)

    def test_existing_one_sheet_and_same_wage_amount_with_preclose_marker(self):
        payroll_inputs = self._inputs()
        worktime = self.root / "worktime-result.xlsx"
        write_worktime_xlsx({
            "schema_version": "0.1", "rows": self.source.fixture.worktime,
        }, worktime)
        reviewed = self.source.review()
        decisions = policy_plan(
            decisions=[
                decision("R1"),
                decision("R2", treatment="UNPAID_LEAVE", amount=60000,
                         fixed=[{"allowance_id": "001", "amount_won": 15000,
                                 "policy_ref": "SYNTHETIC-ALLOWANCE-POLICY"}]),
            ],
            pto_closing_id=reviewed["closing_id"],
        )
        first = event(
            treatment="PAID_LEAVE", amount=0,
            code="ANNUAL_QUARTER", request_id="R1",
            start_at="2026-11-02T09:00", end_at="2026-11-02T11:00",
            approved_minutes=120,
        )
        output = build_contract_scoped_overtime_preview(
            payroll_inputs, worktime,
            settlement_plan=plan(),
            attendance_plan=wage_plan(items=[first], sha=sha256_file(worktime)),
            period_from="2026-11-01", period_to="2026-11-30",
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry([], [], [rate(minimum_minutes=0)]),
            rate_policy=policy(reference_day_minutes_by_contract={"C-OLD": 480}),
            rollup_policy=ROLLUP,
            pto_sources={
                "usage_file": self.source.fixture.usage_path,
                "closing_file": None,
                "deduction_file": self.source.fixture.deduction_path,
                "pto_claims": self.source.fixture.claims,
            },
            pto_wage_plan=decisions,
        )
        row = output["payroll_register"]["rows"][0]
        self.assertEqual(row["base_pay"], 2940000)
        self.assertEqual(row["fixed_allowances:001"], 85000)
        self.assertIn("마감 전", row["review_status"])
        self.assertIn("변동 가능", row["review_status"])
        self.assertIsNone(row["gross_pay"])
        self.assertIsNone(row["net_pay"])
        self.assertEqual(output["status"], "PARTIAL_REVIEW_ONLY")
        self.assertEqual(output["settlement_review"]["pto_closing_status"], "마감 전")
        self.assertEqual(output["pto_wage_review"]["closing_status"], "마감 전")
        result_file = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(output["payroll_register"], result_file)
        book = load_workbook(result_file, read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            keys = [col["key"] for col in output["payroll_register"]["columns"]]
            self.assertEqual(book.active.cell(3, keys.index("review_status") + 1).value,
                             row["review_status"])
            self.assertEqual(book.active.cell(3, keys.index("base_pay") + 1).value,
                             2940000)
        finally:
            book.close()


if __name__ == "__main__":
    unittest.main()
