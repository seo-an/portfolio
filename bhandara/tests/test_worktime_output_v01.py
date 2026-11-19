"""Unittest: factual Worktime handoff; no approval, status or payroll valuation."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from bhandara.worktime.output import (
    OUTPUT_FIELDS, WorktimeOutputError, build_worktime_result,
)
from bhandara.worktime.output_excel import read_worktime_xlsx, write_worktime_xlsx


FROM = "2026-11-01"
TO = "2026-11-30"
DAY = "2026-11-03"


def av(rows):
    return {"module": "attendance-verification", "period_from": FROM,
            "period_to": TO, "rows": rows}


def wc(rows):
    return {"module": "worktime-compliance", "period_from": FROM,
            "period_to": TO, "daily": rows}


def plan(employee="E001", *, minutes=480, schedule_id="DAY_A"):
    return {"employee_id": employee, "work_date": DAY,
            "scheduled_min": minutes, "schedule_id": schedule_id, "day_type": "WORK"}


def match(employee, clock_in_seconds, clock_out_seconds):
    return {"employee_id": employee, "work_date": DAY,
            "time_deviations": {
                "clock_in": {"ledger_vs_expected": {
                    "delta_seconds": clock_in_seconds}},
                "clock_out": {"ledger_vs_expected": {
                    "delta_seconds": clock_out_seconds}},
            }}


def worked(employee, minutes, codes=()):
    return {"employee_id": employee, "work_date": DAY,
            "worked_min": minutes, "review_codes": list(codes)}


class WorktimeOutputTests(unittest.TestCase):
    def assemble(self, plans=None, verified=None, actual=None, facts=None):
        return build_worktime_result(
            plans if plans is not None else [plan()],
            av(verified if verified is not None else [match("E001", -1200, 780)]),
            wc(actual if actual is not None else [worked("E001", 480)]),
            period_from=FROM, period_to=TO, attendance_facts=facts or [],
        )

    def test_four_fixed_time_columns_and_signs(self):
        row = self.assemble()["rows"][0]
        self.assertEqual(
            tuple(row),
            OUTPUT_FIELDS,
        )
        self.assertEqual([row[name] for name in (
            "scheduled_min", "actual_min", "clock_in_delta_min", "clock_out_delta_min")],
            [480, 480, 20, 13],
        )
        self.assertNotIn("status", row)
        self.assertNotIn("approval_ref", row)
        self.assertNotIn("overtime_min", row)
        self.assertNotIn("payable_min", row)

    def test_lateness_and_early_departure_are_negative(self):
        row = self.assemble(verified=[match("E001", 900, -1800)])["rows"][0]
        self.assertEqual((row["clock_in_delta_min"], row["clock_out_delta_min"]),
                         (-15, -30))

    def test_leave_and_extra_60_are_not_valued_in_worktime(self):
        output = self.assemble(
            verified=[],
            actual=[worked("E001", 300)],
            facts=[{"employee_id": "E001", "work_date": DAY,
                    "attendance_type": "LEAVE", "leave_type": "PAID",
                    "leave_request_id": "LV001"}],
        )
        row = output["rows"][0]
        self.assertEqual(row["scheduled_min"], 480)
        self.assertEqual(row["actual_min"], 300)
        self.assertEqual(row["leave_request_id"], "LV001")
        self.assertEqual(row["leave_type"], "PAID")
        self.assertNotIn("leave_min", row)
        self.assertNotIn("difference_min", row)
        self.assertIsNone(row["clock_in_delta_min"])

    def test_unverified_missing_work_is_null_not_zero(self):
        row = self.assemble(actual=[worked("E001", 0, ["WORK_EVIDENCE_UNVERIFIED"])])["rows"][0]
        self.assertIsNone(row["actual_min"])
        verified_zero = self.assemble(actual=[worked("E001", 0)])["rows"][0]
        self.assertEqual(verified_zero["actual_min"], 0)

    def test_rest_review_does_not_erase_verified_work_minutes(self):
        row = self.assemble(actual=[worked(
            "E001", 480, ["REST_SHORTFALL_REVIEW"])])["rows"][0]
        self.assertEqual(row["actual_min"], 480)

    def test_off_and_unscheduled_are_not_the_same(self):
        result = self.assemble(
            plans=[{"employee_id": "E001", "work_date": DAY,
                    "day_type": "OFF", "schedule_id": None, "scheduled_min": 0}],
            verified=[match("E002", None, None)], actual=[],
        )
        by_id = {x["employee_id"]: x for x in result["rows"]}
        self.assertEqual(by_id["E001"]["scheduled_min"], 0)
        self.assertIsNone(by_id["E002"]["scheduled_min"])
        self.assertIsNone(by_id["E002"]["actual_min"])

    def test_external_attendance_not_inferred(self):
        row = self.assemble(verified=[], actual=[])["rows"][0]
        self.assertIsNone(row["attendance_type"])
        self.assertIsNone(row["leave_request_id"])
        self.assertIsNone(row["actual_min"])

    def test_duplicate_external_fact_rejected(self):
        entry = {"employee_id": "E001", "work_date": DAY,
                 "attendance_type": "LEAVE", "leave_request_id": "LV001"}
        with self.assertRaisesRegex(WorktimeOutputError, "duplicate"):
            self.assemble(facts=[entry, entry])

    def test_mismatched_period_rejected(self):
        with self.assertRaisesRegex(WorktimeOutputError, "period mismatch"):
            build_worktime_result(
                [plan()],
                av([match("E001", 0, 0)]),
                {"module": "worktime-compliance", "period_from": "2026-10-01",
                 "period_to": TO, "daily": []},
                period_from=FROM, period_to=TO,
            )

    def test_write_read_one_sheet_and_no_overwrite(self):
        result = self.assemble(
            facts=[{"employee_id": "E001", "work_date": DAY,
                    "attendance_type": "WORK"}],
        )
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "worktime-result.xlsx"
            self.assertEqual(write_worktime_xlsx(result, path), path)
            self.assertEqual(read_worktime_xlsx(path), result["rows"])
            book = load_workbook(path, read_only=True)
            try:
                self.assertEqual(book.sheetnames, ["WORKTIME"])
                self.assertEqual(tuple(cell.value for cell in book["WORKTIME"][1]), OUTPUT_FIELDS)
            finally:
                book.close()
            with self.assertRaisesRegex(WorktimeOutputError, "already exists"):
                write_worktime_xlsx(result, path)

    def test_reader_rejects_formulas_and_extra_columns(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "worktime-result.xlsx"
            write_worktime_xlsx(self.assemble(), path)
            book = load_workbook(path)
            book.active["D2"] = "=8*60"
            book.save(path)
            book.close()
            with self.assertRaises(WorktimeOutputError):
                read_worktime_xlsx(path)
            book = load_workbook(path)
            sheet = book.active
            sheet["D2"] = 480
            sheet["K1"] = "unexpected"
            book.save(path)
            book.close()
            with self.assertRaises(WorktimeOutputError):
                read_worktime_xlsx(path)


if __name__ == "__main__":
    unittest.main()
