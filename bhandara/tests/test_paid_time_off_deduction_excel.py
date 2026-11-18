"""Synthetic tests for the independent PTO deduction-quantity Excel contract."""
from __future__ import annotations

import importlib
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from openpyxl import Workbook, load_workbook

calc = importlib.import_module("bhandara.paid-time-off.deduction-quantity.calculation")
runner = importlib.import_module("bhandara.paid-time-off.runner")

HEADERS = ["request_id", "employee_id", "leave_date", "leave_type", "duration_hours"]


def _write_excel(path: Path, headers: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "승인휴가"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    book.save(path)
    book.close()


def _row(
    request_id="R001", employee_id="E001", leave_date="2026-11-20",
    leave_type="연차", duration_hours=8,
):
    return [request_id, employee_id, leave_date, leave_type, duration_hours]


class PureConversionTests(unittest.TestCase):
    def test_default_eight_hours_and_fractional_hours(self):
        cases = [
            (8, "1"), (4, "0.5"), (2, "0.25"),
            (1, "0.125"), ("1.5", "0.1875"),
        ]
        for hours, expected in cases:
            with self.subTest(hours=hours):
                self.assertEqual(
                    calc.quantity_text(calc.calculate_hours_deduction(hours)),
                    expected,
                )

    def test_external_daily_hours_and_nonterminating_precision(self):
        self.assertEqual(
            calc.calculate_hours_deduction(6, standard_daily_hours=6),
            Fraction(1),
        )
        quantity = calc.calculate_hours_deduction(1, standard_daily_hours=3)
        self.assertEqual(quantity, Fraction(1, 3))
        self.assertEqual(calc.quantity_text(quantity), "0.3333333")
        self.assertEqual(calc.quantity_text(quantity * 3), "1")

    def test_invalid_hours_rejected_in_pure_api(self):
        for hours in ("", None, 0, "-1", "NaN", "Infinity", "=1+1", 9, True):
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                calc.calculate_hours_deduction(hours)
        with self.assertRaises(ValueError):
            calc.calculate_hours_deduction(1, standard_daily_hours=0)

    def test_partial_error_does_not_pollute_exact_summary(self):
        records = [
            dict(zip(HEADERS, _row("R001", "E001", "2026-11-20", "연차", 1))),
            dict(zip(HEADERS, _row("R002", "E001", "2026-11-21", "대휴", 1))),
            dict(zip(HEADERS, _row("R003", "E001", "2026-11-22", "연차", -1))),
        ]
        result = calc.calculate_approved_rows(records)
        self.assertEqual(result["calculated_rows"], 2)
        self.assertEqual(result["excluded_rows"], 1)
        self.assertEqual(result["summaries"][0]["deduction_days"], "0.25")
        self.assertEqual(result["summaries"][0]["status"], "일부 제외")
        self.assertIsNone(result["details"][2]["deduction_days"])


class ExcelContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input_file = self.root / "input" / "paid-time-off" / "approved-leave.xlsx"
        self.output_root = self.root / "output"

    def run_excel(self, rows, headers=None, run_id="sample", daily_hours=8):
        _write_excel(self.input_file, headers or HEADERS, rows)
        return runner.run_deduction_quantity(
            policy_id="테스트정책", run_id=run_id,
            input_root=self.root / "input", output_root=self.output_root,
            standard_daily_hours=daily_hours,
        )

    def test_default_input_workbook_approved_leave_and_three_sheets(self):
        result = self.run_excel([
            _row("R001", "E001", "2026-11-20", "연차", 8),
            _row("R002", "E001", "2026-12-20", "연차", 4),  # future approved
            _row("R003", "E001", "2026-12-21", "대휴", "1.5"),
            _row("R004", "E002", "2026-12-22", "대휴", 2),
        ])
        self.assertEqual(result["summaries"][0]["deduction_days"], "1.6875")
        self.assertEqual(result["summaries"][1]["deduction_days"], "0.25")
        self.assertEqual(result["policy"]["기준시간 출처"], "기본값 8시간")
        book = load_workbook(result["path"], data_only=True)
        try:
            self.assertEqual(book.sheetnames, ["차감요약", "차감상세", "정책정보"])
            self.assertEqual(book["차감상세"]["G2"].value, "1")
            self.assertEqual(book["차감상세"]["G3"].value, "0.5")
            self.assertNotIn("발생일수", [c.value for c in book["차감요약"][1]])
        finally:
            book.close()

    def test_different_dates_same_request_allowed_same_date_duplicate_excluded(self):
        result = self.run_excel([
            _row("R001", "E001", "2026-11-20", "연차", 8),
            _row("R001", "E001", "2026-11-21", "연차", 4),
            _row("R002", "E001", "2026-11-22", "연차", 2),
            _row("R002", "E001", "2026-11-22", "연차", 2),
            _row("R003", "E002", "2026-11-22", "대휴", 3),
        ])
        self.assertEqual(result["summaries"][0]["deduction_days"], "1.5")
        self.assertEqual(result["summaries"][0]["excluded_rows"], 2)
        self.assertEqual(result["summaries"][0]["status"], "일부 제외")
        self.assertEqual(result["summaries"][1]["deduction_days"], "0.375")
        self.assertEqual(result["details"][2]["status"], "계산 제외")
        self.assertEqual(result["details"][3]["status"], "계산 제외")
        self.assertIn("중복", result["details"][2]["reason"])

    def test_missing_invalid_formula_unknown_type_and_other_valid_rows(self):
        result = self.run_excel([
            _row("R001", "E001", "2026-11-20", "연차", 8),
            _row(None, "E001", "2026-11-21", "연차", 4),
            _row("R003", "E001", "2026-11-22", "연차", -1),
            _row("R004", "E001", "2026-11-23", "병가", 2),
            _row("R005", "E001", "not-a-date", "대휴", 2),
            _row("R006", "E001", "2026-11-25", "연차", "=1+1"),
            _row("R007", None, "2026-11-26", "연차", 1),
            _row("R008", "E002", "2026-11-27", "대휴", 2),
        ])
        self.assertEqual(result["policy"]["계산 건수"], 2)
        self.assertEqual(result["policy"]["제외 건수"], 6)
        self.assertEqual(result["summaries"][0]["deduction_days"], "1")
        self.assertEqual(result["summaries"][0]["status"], "일부 제외")
        self.assertEqual(result["summaries"][1]["deduction_days"], "0.25")
        self.assertTrue(all(
            row["deduction_days"] is None
            for row in result["details"] if row["status"] == "계산 제외"
        ))
        self.assertIn("Excel 수식 입력 불가", result["details"][5]["reason"])
        book = load_workbook(result["path"])
        try:
            formula_cell = book["차감상세"]["F7"]
            self.assertNotEqual(formula_cell.data_type, "f")
        finally:
            book.close()

    def test_missing_required_header_reports_each_row_without_abort(self):
        result = self.run_excel(
            [["R001", "E001", "2026-11-20", "연차"]],
            headers=HEADERS[:-1],
        )
        self.assertEqual(result["policy"]["누락 헤더"], "duration_hours")
        self.assertEqual(result["policy"]["계산 건수"], 0)
        self.assertEqual(result["details"][0]["status"], "계산 제외")
        self.assertIsNone(result["summaries"][0]["deduction_days"])

    def test_custom_policy_hour_default_and_overwrite_guard(self):
        result = self.run_excel(
            [_row("R001", "E001", "2026-11-20", "연차", 6)],
            daily_hours=6,
        )
        self.assertEqual(result["summaries"][0]["deduction_days"], "1")
        self.assertEqual(result["policy"]["기준시간 출처"], "호출 시 지정값")
        with self.assertRaises(runner.EntitlementInputError):
            runner.run_deduction_quantity(
                policy_id="테스트정책", run_id="sample",
                approved_file=self.input_file, output_root=self.output_root,
            )

    def test_invalid_explicit_file_and_malformed_workbook_not_silent_fallback(self):
        with self.assertRaises(runner.EntitlementInputError):
            runner.run_deduction_quantity(
                policy_id="테스트정책", run_id="missing",
                input_root=self.root / "input",
                approved_file=self.root / "missing.xlsx",
                output_root=self.output_root,
            )
        _write_excel(self.input_file, HEADERS, [_row()])
        with self.assertRaises(runner.EntitlementInputError):
            runner.run_deduction_quantity(
                policy_id="테스트정책", run_id="bad/../id",
                approved_file=self.input_file, output_root=self.output_root,
            )


if __name__ == "__main__":
    unittest.main()
