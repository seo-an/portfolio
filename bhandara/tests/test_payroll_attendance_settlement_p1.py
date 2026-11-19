"""P1-5b: verified external leave/attendance amounts and Worktime facts."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.attendance_reconciliation import (
    AttendanceSettlementError, reconcile_attendance_adjustments,
)
from bhandara.payroll.attendance_preview import build_attendance_adjusted_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.segmented_settlement import SettlementPreviewError
from bhandara.payroll.settlement_coverage import validate_settlement_coverage
from bhandara.payroll.worktime_bridge import WorktimePayrollBridgeError
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_overtime_candidates_p1 import approved
from bhandara.tests.test_payroll_segmented_settlement_p1 import (
    FROM, TO, ROLES, allocated, contract, employment, plan, split, split_plan,
)
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx


DAY = "2026-11-02"


def event(*, worker="0001", day=DAY, contract_id="C-OLD",
          treatment="PAID_LEAVE", code="ANNUAL_HALF",
          request_id="LV001", amount=0, **overrides):
    item = {
        "event_id": f"EV-{worker}-{day}", "employee_id": worker,
        "work_date": day, "contract_id": contract_id,
        "event_kind": "ATTENDANCE" if treatment == "UNPAID_ABSENCE" else "LEAVE",
        "worktime_code": code, "leave_request_id": request_id,
        "start_at": f"{day}T13:00", "end_at": f"{day}T17:00",
        "approved_minutes": 240, "treatment": treatment,
        "base_reduction_won": amount, "base_amount_not_pre_adjusted": True,
        "approval_status": "APPROVED", "approval_ref": f"AP-{worker}-{day}",
        "policy_ref": "EXTERNAL-SETTLEMENT-POLICY",
        "evidence_ref": f"HRIS-SNAPSHOT-{worker}-{day}",
    }
    if treatment == "UNPAID_ABSENCE":
        item["leave_request_id"] = None
    item.update(overrides)
    return item


def wage_plan(*, items=None, sha="a"*64, **updates):
    source = {
        "schema_version": "0.1", "period_from": FROM, "period_to": TO,
        "snapshot_ref": "HR-LEAVE-2026-11-SYNTHETIC",
        "settlement_snapshot_ref": "SYNTHETIC-EMPLOYMENT-SNAPSHOT",
        "worktime_sha256": sha,
        "absence_codes": ["ABSENCE"],
        "events": [] if items is None else items,
    }
    source.update(updates)
    return source


def leave_fact(**updates):
    row = fact(day=DAY, scheduled_min=480, actual_min=240,
               leave_type="ANNUAL_HALF", leave_request_id="LV001")
    row.update(updates)
    return row


def absence_fact(**updates):
    row = fact(day=DAY, scheduled_min=480, actual_min=240,
               attendance_type="ABSENCE", leave_type=None, leave_request_id=None)
    row.update(updates)
    return row


def coverage(*, contracts=None, settlement=None):
    return validate_settlement_coverage(
        [contract()] if contracts is None else contracts,
        plan=plan() if settlement is None else settlement,
        period_from=FROM, period_to=TO,
    )


def verify(*, items=None, worktime=None, selected=None, settlement=None, overtime=None):
    return reconcile_attendance_adjustments(
        coverage(contracts=selected, settlement=settlement),
        [leave_fact()] if worktime is None else worktime,
        attendance_plan=wage_plan(items=[event()] if items is None else items),
        worktime_sha256="a"*64,
        approved_overtime_segments=overtime,
    )


class AttendanceSettlementEvidenceTests(unittest.TestCase):
    def test_paid_half_day_uses_approved_leave_but_never_deducts_wages(self):
        result = verify()
        self.assertEqual(result["base_reductions_by_employee"]["0001"], 0)
        self.assertEqual(result["events"][0]["approved_minutes"], 240)
        self.assertEqual(result["leave_eligibility"], "NOT_ASSESSED")
        self.assertEqual(result["external_source_authenticity"], "NOT_AUTHENTICATED_BY_THIS_MODULE")
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        self.assertEqual(result["overtime_overlap_review"], "NOT_ASSESSED")

    def test_unpaid_leave_requires_authorized_exact_won_and_never_infers_minutes(self):
        e = event(treatment="UNPAID_LEAVE", amount=60000)
        result = verify(items=[e])
        self.assertEqual(result["base_reductions_by_employee"]["0001"], 60000)
        self.assertEqual(result["events"][0]["approved_minutes"], 240)
        for broken in (event(treatment="UNPAID_LEAVE", amount=0),
                       event(treatment="UNPAID_LEAVE", amount=-1),
                       event(treatment="UNPAID_LEAVE", amount=1.5),
                       event(treatment="PAID_LEAVE", amount=60000)):
            with self.subTest(broken=broken), self.assertRaises(AttendanceSettlementError):
                verify(items=[broken])

    def test_authorized_absence_requires_separate_attendance_type_and_actual_min(self):
        e = event(treatment="UNPAID_ABSENCE", code="ABSENCE",
                  amount=50000)
        result = verify(items=[e], worktime=[absence_fact()])
        self.assertEqual(result["base_reductions_by_employee"]["0001"], 50000)
        with self.assertRaisesRegex(AttendanceSettlementError, "unverified actual minutes"):
            verify(items=[e], worktime=[absence_fact(actual_min=None)])
        with self.assertRaisesRegex(AttendanceSettlementError, "attendance/leave conflict"):
            verify(items=[e], worktime=[leave_fact(attendance_type="ABSENCE")])

    def test_no_money_from_short_worktime_day_without_authorized_event(self):
        result = verify(items=[], worktime=[fact(actual_min=120)])
        self.assertEqual(result["base_reductions_by_employee"], {})
        self.assertEqual(result["worktime_missing_days"], "NOT_ASSERTED_COMPLETE")
        self.assertEqual(result["final_earnings_status"], "INCOMPLETE")

    def test_no_silent_leave_omission_even_if_external_plan_empty(self):
        with self.assertRaisesRegex(AttendanceSettlementError, "unmatched leave"):
            verify(items=[])
        with self.assertRaisesRegex(AttendanceSettlementError, "unmatched leave"):
            verify(items=[], worktime=[fact(leave_type="ANNUAL")])

    def test_declared_absence_code_without_adjustment_is_not_ignored(self):
        with self.assertRaisesRegex(AttendanceSettlementError, "absence code without reviewed"):
            verify(items=[], worktime=[absence_fact()])
        with self.assertRaisesRegex(AttendanceSettlementError, "absence code is not declared"):
            verify(items=[event(treatment="UNPAID_ABSENCE", code="NO_SHOW", amount=50000)],
                   worktime=[absence_fact(attendance_type="NO_SHOW")])
        with self.assertRaisesRegex(AttendanceSettlementError, "absence status conflicts"):
            verify(worktime=[leave_fact(attendance_type="ABSENCE")])

    def test_unclassified_attendance_is_reviewed_but_not_paid_or_deducted(self):
        result = verify(items=[], worktime=[fact(attendance_type="LATE")])
        self.assertEqual(result["base_reductions_by_employee"], {})
        self.assertEqual(result["unclassified_attendance"], [{
            "employee_id": "0001", "work_date": DAY, "attendance_type": "LATE",
        }])

    def test_mismatched_leave_metadata_claim_blocks(self):
        for change in (
            {"leave_request_id": "OTHER"},
            {"worktime_code": "UNPAID"},
            {"event_kind": "ATTENDANCE"},
            {"treatment": "UNPAID_ABSENCE"},
            {"approval_status": "PENDING"},
            {"policy_ref": ""},
            {"approval_ref": ""},
            {"evidence_ref": ""},
            {"base_amount_not_pre_adjusted": False},
            {"base_amount_not_pre_adjusted": 1},
            {"work_date": "2026-11-03"},
            {"contract_id": "OTHER"},
            {"employee_id": "0002"},
        ):
            with self.subTest(change=change), self.assertRaises(AttendanceSettlementError):
                verify(items=[event(**change)])

    def test_missing_worktime_record_and_schedule_block_adjustment(self):
        with self.assertRaisesRegex(AttendanceSettlementError, "Worktime day missing"):
            verify(worktime=[])
        for edit in (
            {"scheduled_min": None},
            {"scheduled_min": 0},
            {"scheduled_min": 120},
        ):
            with self.subTest(edit=edit), self.assertRaisesRegex(
                AttendanceSettlementError, "scheduled-minute"
            ):
                verify(worktime=[leave_fact(**edit)])

    def test_date_duration_and_duplicate_day_or_id_errors(self):
        cases = (
            event(approved_minutes=120),
            event(start_at="2026-11-02T17:00", end_at="2026-11-02T13:00"),
            event(start_at="2026-11-02T13:00", end_at="2026-11-03T14:00"),
            event(start_at="2026-11-01T13:00", end_at="2026-11-01T17:00"),
            event(start_at="2026-11-02T13:00:05"),
            event(start_at="2026-11-30T22:00", end_at="2026-12-01T02:00",
                  approved_minutes=240, work_date="2026-11-30"),
        )
        for item in cases:
            with self.subTest(item=item), self.assertRaises(AttendanceSettlementError):
                verify(items=[item])
        with self.assertRaisesRegex(AttendanceSettlementError, "duplicate event_id"):
            verify(items=[event(), event()])
        with self.assertRaisesRegex(AttendanceSettlementError, "multiple events"):
            verify(items=[event(), event(event_id="EV-DIFFERENT")])

    def test_leaves_on_two_distinct_days_and_same_request_cannot_switch_worker_or_code(self):
        second = event(
            event_id="EV002", day="2026-11-03",
            start_at="2026-11-03T13:00", end_at="2026-11-03T17:00",
            approval_ref="AP002", evidence_ref="S002",
            treatment="UNPAID_LEAVE", amount=60000,
        )
        first = event(treatment="UNPAID_LEAVE", amount=40000)
        rows = [leave_fact(), leave_fact(work_date="2026-11-03")]
        result = verify(items=[first, second], worktime=rows)
        self.assertEqual(result["base_reductions_by_employee"]["0001"], 100000)
        bad = dict(second, worktime_code="SICK")
        with self.assertRaisesRegex(AttendanceSettlementError, "leave reference/type mismatch"):
            verify(items=[first, bad], worktime=rows)

    def test_mid_cycle_contract_change_must_match_day_assignment(self):
        e = event(
            day="2026-11-17", contract_id="C-NEW",
            start_at="2026-11-17T13:00", end_at="2026-11-17T17:00",
            treatment="UNPAID_LEAVE", amount=60000,
        )
        row = leave_fact(work_date="2026-11-17")
        result = verify(items=[e], worktime=[row],
                        selected=split(), settlement=split_plan())
        self.assertEqual(result["events"][0]["contract_id"], "C-NEW")
        with self.assertRaisesRegex(AttendanceSettlementError, "contract assignment mismatch"):
            verify(items=[dict(e, contract_id="C-OLD")], worktime=[row],
                   selected=split(), settlement=split_plan())
        overnight = event(
            start_at="2026-11-15T23:00", end_at="2026-11-16T01:00",
            approved_minutes=120, work_date="2026-11-15", contract_id="C-OLD",
        )
        with self.assertRaisesRegex(AttendanceSettlementError, "crosses a contract change"):
            verify(items=[overnight], worktime=[leave_fact(work_date="2026-11-15")],
                   selected=split(), settlement=split_plan())

    def test_fingerprint_and_settlement_source_mismatch_block(self):
        for change in (
            {"worktime_sha256": "b"*64},
            {"worktime_sha256": "NOT-A-HASH"},
            {"settlement_snapshot_ref": "DIFFERENT"},
            {"period_to": "2026-12-01"},
            {"snapshot_ref": ""},
            {"events": None},
            {"absence_codes": []},
            {"absence_codes": ["ABSENCE", "ABSENCE"]},
            {"absence_codes": ["=FORMULA"]},
            {"unexpected": True},
        ):
            with self.subTest(change=change), self.assertRaises(AttendanceSettlementError):
                reconcile_attendance_adjustments(
                    coverage(), [leave_fact()],
                    attendance_plan=wage_plan(items=[event()], **change),
                    worktime_sha256="a"*64,
                )

    def test_approved_overtime_overlap_blocks_even_if_leave_was_paid(self):
        overtime = approved(
            start="2026-11-02T15:00", end="2026-11-02T16:00",
        )
        with self.assertRaisesRegex(AttendanceSettlementError, "overlaps paid/unpaid"):
            verify(overtime=[overtime])
        overtime["start_at"] = "2026-11-02T17:00"
        overtime["end_at"] = "2026-11-02T18:00"
        result = verify(overtime=[overtime])
        self.assertEqual(result["overtime_overlap_review"], "LISTED_SEGMENTS_NO_OVERLAP")
        self.assertEqual(result["final_earnings_status"], "INCOMPLETE")

    def test_unapproved_overtime_not_mistaken_for_approved_and_no_payment_combined(self):
        overtime = approved(approval_status="PENDING")
        with self.assertRaisesRegex(AttendanceSettlementError, "not approved"):
            verify(overtime=[overtime])

class AttendanceSettlementPreviewE2ETests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "payroll").mkdir()

    def put(self, role, rows):
        spec = SCHEMA["workbooks"][role]
        book = Workbook()
        book.active.title = spec["sheet"]
        book.active.append(spec["columns"])
        for row in rows:
            book.active.append([row.get(key) for key in spec["columns"]])
        book.save(self.root / "payroll" / spec["filename"])
        book.close()

    def prepare(self, *, contracts=None, allowance_assignments=None,
                allowance_map=None, bonus_budgets=None, bonus_allocations=None):
        sources = {
            "contracts": [contract()] if contracts is None else contracts,
            "allowance_assignments": [] if allowance_assignments is None else allowance_assignments,
            "fixed_allowance_map": ([deepcopy(SAMPLES["fixed_allowance_map"])]
                                    if allowance_map is None else allowance_map),
            "bonus_budget": [] if bonus_budgets is None else bonus_budgets,
            "bonus_allocation": [] if bonus_allocations is None else bonus_allocations,
        }
        for role, rows in sources.items():
            self.put(role, rows)
        return read_payroll_inputs(self.root, roles=ROLES)

    def worktime(self, rows):
        source = self.root / "worktime-result.xlsx"
        write_worktime_xlsx({"schema_version": "0.1", "rows": rows}, source)
        return source, sha256_file(source)

    def preview(self, inputs, path, sha, *, settlement=None, items=None,
                overtime=None, **plan_changes):
        return build_attendance_adjusted_preview(
            inputs, path, settlement_plan=plan() if settlement is None else settlement,
            attendance_plan=wage_plan(
                items=[event()] if items is None else items, sha=sha, **plan_changes,
            ),
            period_from=FROM, period_to=TO,
            approved_overtime_segments=overtime,
        )

    def test_paid_leave_one_sheet_preserves_base_and_review_flags(self):
        inputs = self.prepare()
        path, sha = self.worktime([leave_fact()])
        out = self.preview(inputs, path, sha)
        row = out["payroll_register"]["rows"][0]
        self.assertEqual(row["base_pay"], 3000000)
        self.assertIsNone(row["gross_pay"])
        self.assertIsNone(row["deduction_total"])
        self.assertIsNone(row["net_pay"])
        self.assertEqual(row["review_status"], "PARTIAL_REVIEW_ONLY")
        self.assertEqual(out["attendance_review"]["events"][0]["base_reduction_won"], 0)
        self.assertEqual(out["settlement_review"]["paid_leave_verification"],
                         "LISTED_EVENTS_MATCH_WORKTIME_NOT_AUTHENTICATED")
        self.assertFalse(out["settlement_review"]["earnings_complete"])
        self.assertEqual(out["approval_state"], "NOT_APPROVED")

    def test_unpaid_leave_affects_base_only_with_explicit_amount(self):
        inputs = self.prepare(
            allowance_assignments=[
                {"contract_id": "C-OLD", "allowance_id": "001", "level": "L1"},
            ],
        )
        path, sha = self.worktime([leave_fact()])
        out = self.preview(
            inputs, path, sha,
            items=[event(treatment="UNPAID_LEAVE", amount=60000)],
        )
        row = out["payroll_register"]["rows"][0]
        self.assertEqual(row["base_pay"], 2940000)
        self.assertEqual(row["fixed_allowances:001"], 100000)
        self.assertIsNone(row["gross_pay"])
        self.assertIsNone(row["net_pay"])
        audit = out["settlement_review"]["employees"][0]
        self.assertEqual(audit["base_before_attendance_adjustment"], 3000000)
        self.assertEqual(audit["base_reduction_candidate"], 60000)
        self.assertEqual(out["attendance_review"]["base_reductions_by_employee"]["0001"], 60000)
        output = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(out["payroll_register"], output)
        book = load_workbook(output)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            self.assertEqual(book.active.cell(3, 2).value, 2940000)
        finally:
            book.close()

    def test_split_contract_unpaid_absence_and_single_worktime_file(self):
        inputs = self.prepare(contracts=split())
        day = "2026-11-17"
        path, sha = self.worktime([
            absence_fact(work_date=day),
        ])
        outgoing = event(
            day=day, contract_id="C-NEW",
            start_at=f"{day}T13:00", end_at=f"{day}T17:00",
            treatment="UNPAID_ABSENCE", code="ABSENCE",
            amount=50000,
        )
        out = self.preview(
            inputs, path, sha, settlement=split_plan(), items=[outgoing],
        )
        self.assertEqual(out["payroll_register"]["rows"][0]["base_pay"], 3250000)
        self.assertEqual(out["settlement_review"]["employees"][0]["base_before_attendance_adjustment"], 3300000)

    def test_no_event_never_infers_absence_from_early_clock_or_short_day(self):
        inputs = self.prepare()
        path, sha = self.worktime([fact(actual_min=0, scheduled_min=480,
                                        clock_in_delta_min=-15)])
        out = self.preview(inputs, path, sha, items=[])
        self.assertEqual(out["payroll_register"]["rows"][0]["base_pay"], 3000000)
        self.assertEqual(out["attendance_review"]["base_reductions_by_employee"], {})
        self.assertIsNone(out["payroll_register"]["rows"][0]["net_pay"])

    def test_modified_worktime_sha_blocks_before_money(self):
        inputs = self.prepare()
        path, sha = self.worktime([leave_fact()])
        with self.assertRaisesRegex(AttendanceSettlementError, "fingerprint mismatch"):
            self.preview(inputs, path, "0"*64)

    def test_reduction_exceeds_base_wage_blocks_whole_preview(self):
        inputs = self.prepare()
        path, sha = self.worktime([leave_fact()])
        with self.assertRaisesRegex(SettlementPreviewError, "reduction exceeds"):
            self.preview(
                inputs, path, sha,
                items=[event(treatment="UNPAID_LEAVE", amount=3200000)],
            )

    def test_fifty_employees_only_one_has_unpaid_leave_adjustment(self):
        contracts = [
            contract(worker=f"{index:04d}", contract_id=f"C-{index:04d}")
            for index in range(1, 51)
        ]
        inputs = self.prepare(contracts=contracts)
        settlement = plan(
            facts=[employment(worker=f"{index:04d}") for index in range(1, 51)],
            allocations=[allocated(worker=f"{index:04d}",
                                   contract_id=f"C-{index:04d}")
                         for index in range(1, 51)],
        )
        paid_worker = "0017"
        source = leave_fact(employee_id=paid_worker)
        path, sha = self.worktime([source])
        item = event(
            worker=paid_worker, contract_id="C-0017",
            treatment="UNPAID_LEAVE", amount=25000,
        )
        out = self.preview(inputs, path, sha, settlement=settlement, items=[item])
        rows = out["payroll_register"]["rows"]
        self.assertEqual(len(rows), 50)
        self.assertEqual([r["base_pay"] for r in rows if r["employee_id"] == paid_worker], [2975000])
        self.assertTrue(all(r["base_pay"] == 3000000 for r in rows
                            if r["employee_id"] != paid_worker))
        self.assertTrue(all(r["net_pay"] is None for r in rows))
        self.assertEqual(len(out["worktime_review"]["employees_without_worktime_rows"]), 49)


if __name__ == "__main__":
    unittest.main()
