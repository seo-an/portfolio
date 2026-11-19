"""Unittest: P1-1 Worktime facts are not payroll pay/approval evidence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.worktime_bridge import (
    WorktimePayrollBridgeError,
    review_worktime_facts,
    build_payroll_worktime_review,
)
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.worktime.output import OUTPUT_FIELDS
from bhandara.worktime.output_excel import write_worktime_xlsx


PERIOD_FROM = "2026-11-01"
PERIOD_TO = "2026-11-30"


def fact(worker="0001", day="2026-11-02", **overrides):
    result = {
        "employee_id": worker, "work_date": day, "schedule_id": "S01",
        "scheduled_min": 480, "actual_min": 480,
        "clock_in_delta_min": 0, "clock_out_delta_min": 0,
        "attendance_type": None, "leave_type": None,
        "leave_request_id": None,
    }
    result.update(overrides)
    return result


def check(rows, ids=("0001",), start=PERIOD_FROM, end=PERIOD_TO):
    return review_worktime_facts(rows, employee_ids=ids,
                                 period_from=start, period_to=end)


class WorktimePayrollBridgeTests(unittest.TestCase):
    def test_exact_day_with_no_deviation_never_becomes_approved_or_payable(self):
        result = check([fact()])
        self.assertEqual(result["rows"][0]["review_codes"], [])
        self.assertEqual(result["rows"][0]["payment_decision"], "NOT_ASSESSED")
        self.assertFalse(result["payable_minutes_calculated"])
        self.assertFalse(result["earnings_complete"])
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        self.assertNotIn("payable_minutes", result["rows"][0])
        self.assertNotIn("amount", result["rows"][0])

    def test_early_and_late_must_not_be_counted_as_paid_overtime(self):
        result = check([fact(clock_in_delta_min=20, clock_out_delta_min=13)])
        self.assertEqual(result["rows"][0]["review_codes"],
                         ["CLOCK_IN_EARLIER", "CLOCK_OUT_LATER"])
        self.assertNotIn("payable_minutes", result["rows"][0])

    def test_actual_above_schedule_marks_candidate_not_approved_time(self):
        result = check([fact(actual_min=530)])
        self.assertEqual(result["rows"][0]["review_codes"], ["ACTUAL_ABOVE_SCHEDULED"])
        self.assertFalse(result["payable_minutes_calculated"])

    def test_shifted_worktime_never_infers_overtime(self):
        result = check([fact(clock_in_delta_min=-15, clock_out_delta_min=15)])
        self.assertEqual(result["rows"][0]["review_codes"],
                         ["CLOCK_OUT_LATER", "CLOCK_IN_LATER"])
        self.assertFalse(result["payable_minutes_calculated"])

    def test_unverified_actual_is_not_zero(self):
        result = check([fact(actual_min=None)])
        self.assertEqual(result["rows"][0]["review_codes"], ["ACTUAL_UNVERIFIED"])
        result = check([fact(actual_min=0)])
        self.assertEqual(result["rows"][0]["review_codes"], [])

    def test_off_day_work_is_only_candidate(self):
        result = check([fact(scheduled_min=0, actual_min=120)])
        self.assertEqual(result["rows"][0]["review_codes"], ["WORK_ON_SCHEDULED_OFF"])

    def test_leave_request_needs_source_check_even_with_more_actual_minutes(self):
        result = check([fact(actual_min=300, leave_type="PAID", leave_request_id="LV01")])
        self.assertEqual(result["rows"][0]["review_codes"], ["LEAVE_SOURCE_REVIEW"])
        self.assertNotIn("amount", result["rows"][0])

    def test_missing_schedule_and_clock_vs_work_conflict(self):
        result = check([fact(scheduled_min=None, actual_min=0, clock_in_delta_min=20)])
        self.assertEqual(result["rows"][0]["review_codes"],
                         ["SCHEDULE_UNVERIFIED", "CLOCK_IN_EARLIER", "VERIFY_CLOCK_VS_WORK_MINUTES"])

    def test_next_day_work_date_restriction(self):
        with self.assertRaisesRegex(WorktimePayrollBridgeError, "outside selected"):
            check([fact(day="2026-12-01")])

    def test_other_worker_and_duplicate_day_block(self):
        with self.assertRaisesRegex(WorktimePayrollBridgeError, "outside selected Payroll"):
            check([fact(worker="0002")])
        with self.assertRaisesRegex(WorktimePayrollBridgeError, "duplicate employee/date"):
            check([fact(), fact()])

    def test_bad_minutes_or_metadata_block(self):
        for row in (
            fact(actual_min=-1),
            fact(actual_min=1.5),
            fact(clock_in_delta_min=float("inf")),
            fact(scheduled_min=True),
            fact(employee_id=1),
            fact(schedule_id="=A1"),
        ):
            with self.subTest(row=row), self.assertRaises(WorktimePayrollBridgeError):
                check([row])
        with self.assertRaisesRegex(WorktimePayrollBridgeError, "exact ten-column"):
            check([dict(fact(), approved=True)])

    def test_empty_rows_report_missing_workers_without_zero_work_assumption(self):
        result = check([], ids=("0001", "0002"))
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["employees_without_worktime_rows"], ["0001", "0002"])
        self.assertFalse(result["earnings_complete"])

    def test_fractional_clock_delta_preserves_review_only_facts(self):
        result = check([fact(clock_out_delta_min=0.25)])
        self.assertEqual(result["rows"][0]["review_codes"], ["CLOCK_OUT_LATER"])

    def test_idempotent_sorted_facts(self):
        rows = [fact(day="2026-11-03"), fact(day="2026-11-02")]
        self.assertEqual([x["work_date"] for x in check(rows)["rows"]],
                         ["2026-11-02", "2026-11-03"])

    def test_worktime_xlsx_and_payroll_preview_join_without_changing_output(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "payroll").mkdir()
            for role, rows in (
                ("contracts", [SAMPLES["contracts"]]),
                ("allowance_assignments", [SAMPLES["allowance_assignments"]]),
                ("fixed_allowance_map", [SAMPLES["fixed_allowance_map"]]),
                ("bonus_budget", []),
                ("bonus_allocation", []),
            ):
                spec = SCHEMA["workbooks"][role]
                book = Workbook()
                book.active.title = spec["sheet"]
                book.active.append(spec["columns"])
                for row in rows:
                    book.active.append([row.get(col) for col in spec["columns"]])
                book.save(folder / "payroll" / spec["filename"])
                book.close()
            inputs = read_payroll_inputs(
                folder, roles=("contracts", "allowance_assignments", "fixed_allowance_map",
                               "bonus_budget", "bonus_allocation"),
            )
            path = folder / "worktime-result.xlsx"
            write_worktime_xlsx({
                "schema_version": "0.1",
                "rows": [fact(clock_in_delta_min=20, clock_out_delta_min=13)],
            }, path)
            merged = build_payroll_worktime_review(
                inputs, path, period_from=PERIOD_FROM, period_to=PERIOD_TO,
            )
            result = merged["payroll_register"]
            self.assertEqual(result["file_name"], "payroll-result.xlsx")
            self.assertIsNone(result["rows"][0]["gross_pay"])
            self.assertIsNone(result["rows"][0]["net_pay"])
            self.assertEqual(result["rows"][0]["review_status"], "PARTIAL_REVIEW_ONLY")
            self.assertEqual(merged["worktime_review"]["rows"][0]["review_codes"],
                             ["CLOCK_IN_EARLIER", "CLOCK_OUT_LATER"])
            self.assertEqual(merged["approval_state"], "NOT_APPROVED")

    def test_wrong_worktime_filename_fails(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with self.assertRaisesRegex(WorktimePayrollBridgeError, "fixed source filename"):
                # Only a minimal fake PayrollInputs is needed: fail before source load
                # once register composition has been patched with a synthetic value.
                from unittest.mock import patch
                with patch("bhandara.payroll.worktime_bridge.build_payroll_review_register",
                           return_value={"rows": []}), patch(
                    "bhandara.payroll.worktime_bridge.select_contracts_for_period",
                    return_value=[{"employee_id": "0001"}],
                ):
                    build_payroll_worktime_review(
                        None, folder / "wrong.xlsx",
                        period_from=PERIOD_FROM, period_to=PERIOD_TO,
                    )


if __name__ == "__main__":
    unittest.main()
