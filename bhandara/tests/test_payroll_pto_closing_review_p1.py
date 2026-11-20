"""Read actual PTO workbook contracts without changing the PTO or Worktime tools."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from fractions import Fraction
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.pto_closing_review import (
    PTOClosingReviewError, reconcile_pto_closing,
)
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact

pto_usage = importlib.import_module("bhandara.paid-time-off.runner_usage")
pto_closing = importlib.import_module("bhandara.paid-time-off.runner_closing")
pto_deduction = importlib.import_module("bhandara.paid-time-off.runner")


def claim(request="R1", *, start="09:00", end="11:00",
          minutes=120, code="ANNUAL_QUARTER", kind="연차", **overrides):
    row = {
        "employee_id": "0001", "request_id": request,
        "leave_date": "2026-11-02", "pto_leave_type": kind,
        "worktime_code": code,
        "start_at": "2026-11-02T" + start,
        "end_at": "2026-11-02T" + end,
        "approved_minutes": minutes,
        "minutes_per_pto_day": 480,
    }
    row.update(overrides)
    return row


def deduction_detail(request="R1", qty=Fraction(1, 4), *, status="계산 완료"):
    return {
        "excel_row": 2, "request_id": request,
        "employee_id": "0001", "leave_date": "2026-11-02",
        "leave_type": "연차", "duration_hours": float(qty * 8),
        "deduction_days": str(qty), "status": status,
        "reason": None, "exact_numerator": str(qty.numerator),
        "exact_denominator": str(qty.denominator),
    }


def usage_detail(request="R1", qty=Fraction(1, 4), *,
                 status="사용", grant="G001"):
    return {
        "employee_id": "0001", "leave_type": "연차",
        "grant_id": grant, "request_id": request,
        "leave_date": "2026-11-02", "차감일수": qty,
        "처리구분": status,
    }


def report_row(qty=Fraction(3, 4), status="정상"):
    row = {
        "employee_id": "0001", "name": "SYNTHETIC",
        "발생연차일수": Fraction(15), "기초이월잔여일수": Fraction(0),
        "대휴발생일수": Fraction(0), "총확보휴가일수": Fraction(15),
        "미사용만료일수": Fraction(0), "누적사용일수": qty,
        "마감잔여일수": Fraction(15) - qty, "마감상태": status,
    }
    row.update({f"{month}월": qty if month == 11 else Fraction(0)
                for month in range(1, 13)})
    return row


class PTOClosingBridgeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.usage_path = self.root / "usage-ledger-result.xlsx"
        self.closing_path = self.root / "closing-result.xlsx"
        self.deduction_path = self.root / "deduction-quantity-result.xlsx"
        self.details = [usage_detail(), usage_detail("R2", Fraction(1, 2))]
        self.deductions = [deduction_detail(), deduction_detail("R2", Fraction(1, 2))]
        self.closing_qty = Fraction(3, 4)
        self.usage_meta = {
            "정책 ID": "SYNTHETIC", "마감 판정 ID": "Closing-4.4-2026",
            "실행 기준일": "2026-12-31", "계산 상태": "계산 완료",
        }
        self.closing_meta = {
            "참조 ID": "Closing-4.4-2026", "확정여부": "확정",
            "마감 기준일": "2026-12-31", "검토 필요 건수": 0,
        }
        self.worktime = [fact(
            worker="0001", day="2026-11-02",
            scheduled_min=480, actual_min=120,
            leave_type="ANNUAL_QUARTER", leave_request_id="R1",
        )]
        self.claims = [
            claim(), claim("R2", start="13:00", end="17:00",
                           minutes=240, code="ANNUAL_HALF"),
        ]

    def files(self):
        self.usage_path.write_bytes(pto_usage.make_usage_workbook(
            summary=[{
                "employee_id": "0001", "발생일수": 15,
                "사용일수": self.closing_qty,
                "잔여일수": Fraction(15) - self.closing_qty,
            }],
            details=self.details, expiry_result=None, issues=[],
            metadata=self.usage_meta,
        ))
        metadata = {
            **self.closing_meta,
            "사용내역 SHA256": sha256_file(self.usage_path),
        }
        self.closing_path.write_bytes(pto_closing.make_closing_workbook(
            result={"report": [report_row(self.closing_qty)],
                    "carry_rows": [], "shortage_rows": [], "issues": []},
            metadata=metadata,
        ))
        self.deduction_path.write_bytes(pto_deduction.make_deduction_workbook(
            summaries=[], details=self.deductions,
            metadata={"정책 ID": "SYNTHETIC",
                      "산정 기준일": "2026-12-31"},
        ))

    def review(self, *, claims=None, worktime=None, start="2026-11-01",
               end="2026-11-30"):
        self.files()
        return reconcile_pto_closing(
            usage_file=self.usage_path,
            closing_file=self.closing_path,
            deduction_file=self.deduction_path,
            worktime_rows=self.worktime if worktime is None else worktime,
            pto_claims=self.claims if claims is None else claims,
            period_from=start, period_to=end,
        )

    def test_two_independent_same_day_requests_exact_quantity(self):
        value = self.review()
        self.assertEqual(value["closing_id"], "Closing-4.4-2026")
        self.assertEqual(value["monthly_usage_days"], {"0001": "3/4"})
        self.assertTrue(value["multiple_requests_per_workday"])
        self.assertEqual([r["exact_deducted_days"] for r in value["requests"]],
                         ["1/4", "1/2"])
        self.assertEqual(value["salary_treatment"], "NOT_ASSESSED")
        self.assertEqual(value["approval_state"], "NOT_APPROVED")
        self.assertFalse(value["earnings_complete"])
        self.assertEqual(len(value["source_sha256"]), 3)

    def test_worktime_can_anchor_second_request_without_new_column(self):
        rows = [dict(self.worktime[0],
                     leave_request_id="R2", leave_type="ANNUAL_HALF")]
        value = self.review(worktime=rows)
        self.assertTrue(value["multiple_requests_per_workday"])

    def test_worktime_missing_anchor_and_overlap_are_blocked(self):
        for row in (
            dict(self.worktime[0], leave_request_id="UNKNOWN"),
            dict(self.worktime[0], leave_type="SICK"),
        ):
            with self.subTest(row=row), self.assertRaisesRegex(
                PTOClosingReviewError, "anchor missing"
            ):
                self.review(worktime=[row])
        with self.assertRaisesRegex(PTOClosingReviewError, "overlapping"):
            self.review(claims=[self.claims[0],
                                claim("R2", start="10:00", end="14:00",
                                      minutes=240)])
        with self.assertRaisesRegex(PTOClosingReviewError, "scheduled"):
            self.review(worktime=[dict(self.worktime[0], scheduled_min=300)])

    def test_missing_extra_request_or_unexpected_claim_cannot_be_ignored(self):
        with self.assertRaisesRegex(PTOClosingReviewError, "populations differ"):
            self.review(claims=[self.claims[0]])
        other = claim("OTHER", start="13:00", end="17:00", minutes=240)
        with self.assertRaisesRegex(PTOClosingReviewError, "populations differ"):
            self.review(claims=[self.claims[0], other])

    def test_wrong_external_minutes_divisor_never_overwrites_pto(self):
        with self.assertRaisesRegex(PTOClosingReviewError, "disagree with exact"):
            self.review(claims=[self.claims[0],
                                dict(self.claims[1], minutes_per_pto_day=600)])
        for bad in (0, -480, 480.0):
            with self.subTest(bad=bad), self.assertRaises(PTOClosingReviewError):
                self.review(claims=[dict(self.claims[0], minutes_per_pto_day=bad),
                                    self.claims[1]])

    def test_exact_monthly_closing_vs_deduction_mismatch_is_blocked(self):
        self.closing_qty = Fraction(1, 2)
        with self.assertRaisesRegex(PTOClosingReviewError, "monthly amount"):
            self.review()

    def test_display_only_seven_decimal_truncation_does_not_change_exact_quantity(self):
        self.details = [usage_detail(qty=Fraction(1, 3))]
        self.deductions = [deduction_detail(qty=Fraction(1, 3))]
        self.closing_qty = Fraction(1, 3)
        claims = [dict(self.claims[0], approved_minutes=160,
                       start_at="2026-11-02T09:00",
                       end_at="2026-11-02T11:40")]
        value = self.review(claims=claims)
        self.assertEqual(value["monthly_usage_days"], {"0001": "1/3"})
        self.assertEqual(value["requests"][0]["exact_deducted_days"], "1/3")

    def test_display_allocation_sum_mismatch_is_blocked(self):
        self.details[1]["차감일수"] = Fraction(1, 4)
        with self.assertRaisesRegex(PTOClosingReviewError, "display disagrees"):
            self.review()

    def test_unconfirmed_or_review_required_closing_never_entitles_wages(self):
        self.closing_meta["확정여부"] = "미확정"
        with self.assertRaisesRegex(PTOClosingReviewError, "confirmation required"):
            self.review()
        self.closing_meta["확정여부"] = "확정"
        self.closing_meta["검토 필요 건수"] = 1
        with self.assertRaisesRegex(PTOClosingReviewError, "source issues"):
            self.review()

    def test_source_snapshot_hash_link_required(self):
        self.files()
        from openpyxl import load_workbook
        book = load_workbook(self.usage_path)
        book["정책정보"]["B2"] = "CHANGED-POLICY"
        book.save(self.usage_path)
        book.close()
        with self.assertRaisesRegex(PTOClosingReviewError, "fingerprint mismatch"):
            reconcile_pto_closing(
                usage_file=self.usage_path, closing_file=self.closing_path,
                deduction_file=self.deduction_path, worktime_rows=self.worktime,
                pto_claims=self.claims, period_from="2026-11-01",
                period_to="2026-11-30",
            )

    def test_not_same_quarter_or_not_full_month_rejected(self):
        with self.assertRaisesRegex(PTOClosingReviewError, "current quarter"):
            self.review(start="2026-09-01", end="2026-09-30")
        with self.assertRaisesRegex(PTOClosingReviewError, "full calendar month"):
            self.review(start="2026-11-01", end="2026-11-29")

    def test_unresolved_deduction_and_reserved_usage_fail_closed(self):
        self.deductions[0]["status"] = "계산 제외"
        with self.assertRaisesRegex(PTOClosingReviewError, "unresolved"):
            self.review()
        self.deductions[0]["status"] = "계산 완료"
        self.details[0]["처리구분"] = "예약"
        with self.assertRaisesRegex(PTOClosingReviewError, "unresolved"):
            self.review()

    def test_duplicate_request_or_invalid_claim_fails(self):
        with self.assertRaisesRegex(PTOClosingReviewError, "duplicate"):
            self.review(claims=[self.claims[0], self.claims[0], self.claims[1]])
        for changed in (
            dict(self.claims[0], leave_date="2026-11-03"),
            dict(self.claims[0], pto_leave_type="MISSING"),
            dict(self.claims[0], approved_minutes=121),
            dict(self.claims[0], start_at="2026-11-02T11:00",
                 end_at="2026-11-02T09:00"),
            dict(self.claims[0], unexpected=True),
        ):
            with self.subTest(changed=changed), self.assertRaises(PTOClosingReviewError):
                self.review(claims=[changed, self.claims[1]])

    def test_existing_payroll_flow_consumes_optional_pto_review_without_extra_output(self):
        """Uses the real XLSX Reader and the same one-pass output pipeline."""
        from openpyxl import Workbook, load_workbook
        from bhandara.payroll.contract_scoped_overtime import (
            build_contract_scoped_overtime_preview,
        )
        from bhandara.payroll.input_excel import read_payroll_inputs
        from bhandara.payroll.output_excel import write_payroll_result_xlsx
        from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import (
            ROLES, ROLLUP, source_registry,
        )
        from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
        from bhandara.tests.test_payroll_attendance_settlement_p1 import event, wage_plan
        from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
        from bhandara.tests.test_payroll_segmented_settlement_p1 import contract, plan
        from bhandara.worktime.output_excel import write_worktime_xlsx

        self.files()
        (self.root / "payroll").mkdir()
        samples = {
            "contracts": [contract()],
            "allowance_assignments": [],
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])],
            "bonus_budget": [], "bonus_allocation": [],
            "overtime_rules": [rate(minimum_minutes=0)],
        }
        for role in ROLES:
            spec = SCHEMA["workbooks"][role]
            book = Workbook()
            book.active.title = spec["sheet"]
            book.active.append(spec["columns"])
            for record in samples[role]:
                book.active.append([record.get(name) for name in spec["columns"]])
            book.save(self.root / "payroll" / spec["filename"])
            book.close()
        inputs = read_payroll_inputs(self.root, roles=ROLES)
        worktime = self.root / "worktime-result.xlsx"
        write_worktime_xlsx(
            {"schema_version": "0.1", "rows": self.worktime}, worktime,
        )
        attendance = event(
            treatment="PAID_LEAVE", amount=0, code="ANNUAL_QUARTER",
            request_id="R1", start_at="2026-11-02T09:00",
            end_at="2026-11-02T11:00", approved_minutes=120,
        )
        result = build_contract_scoped_overtime_preview(
            inputs, worktime,
            settlement_plan=plan(),
            attendance_plan=wage_plan(
                items=[attendance], sha=sha256_file(worktime)
            ),
            period_from="2026-11-01", period_to="2026-11-30",
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry(
                [], [], [rate(minimum_minutes=0)],
            ),
            rate_policy=policy(
                reference_day_minutes_by_contract={"C-OLD": 480},
            ),
            rollup_policy=ROLLUP,
            pto_sources={
                "usage_file": self.usage_path,
                "closing_file": self.closing_path,
                "deduction_file": self.deduction_path,
                "pto_claims": self.claims,
            },
        )
        self.assertTrue(result["pto_closing_review"]["multiple_requests_per_workday"])
        self.assertEqual(result["payroll_register"]["rows"][0]["base_pay"], 3000000)
        self.assertEqual(result["payroll_register"]["rows"][0]["gross_pay"], 3000000)
        self.assertEqual(result["payroll_register"]["rows"][0]["deduction_total"], 0)
        self.assertEqual(result["payroll_register"]["rows"][0]["net_pay"], 3000000)
        self.assertEqual(result["payroll_register"]["rows"][0]["review_status"], "검증요청 · 잠정합계")
        self.assertEqual(result["status"], "PARTIAL_REVIEW_ONLY")
        result_file = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(result["payroll_register"], result_file)
        output = load_workbook(result_file, read_only=True)
        try:
            self.assertEqual(output.sheetnames, ["PAYROLL"])
        finally:
            output.close()

    def test_one_request_day_no_unsupported_multiplicity_claim(self):
        self.details = [self.details[0]]
        self.deductions = [self.deductions[0]]
        self.closing_qty = Fraction(1, 4)
        result = self.review(claims=[self.claims[0]])
        self.assertFalse(result["multiple_requests_per_workday"])


if __name__ == "__main__":
    unittest.main()
