"""Synthetic end-to-end tests of the negotiated PTO entitlement Excel contract."""
from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

from openpyxl import Workbook, load_workbook

calc = importlib.import_module("bhandara.paid-time-off.entitlement.calculation")
runner = importlib.import_module("bhandara.paid-time-off.runner")


def write_excel(path: Path, sheets: dict[str, list[list]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    first = True
    for name, rows in sheets.items():
        sheet = book.active if first else book.create_sheet()
        sheet.title = name
        first = False
        for row in rows:
            sheet.append(row)
    book.save(path)
    book.close()


class EntitlementCalculationTests(unittest.TestCase):
    def test_attendance_lookup_only_uses_declared_flag(self):
        rows = [
            dict(employee_id="E001", period_start="2025-01-01",
                 period_end="2025-01-31", check_type="월간", attendance_flag="개근"),
            dict(employee_id="E001", period_start="2025-02-01",
                 period_end="2025-02-28", check_type="월간", attendance_flag="미개근"),
        ]
        idx = calc.build_flag_index(rows)
        summary, detail = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 1, 1),
            as_of_date=date(2025, 3, 1), basis="1년 미만 기준", flag_index=idx,
        )
        self.assertEqual(summary["calculation_result"], "1")
        self.assertEqual(summary["granted_days"], "1.0")
        self.assertEqual(len(detail), 1)
        self.assertEqual(detail[0]["grant_type"], "월별 발생")
        self.assertEqual(detail[0]["calculation_result"], "1")

    def test_missing_flag_is_undetermined_not_approved(self):
        summary, rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 1, 1),
            as_of_date=date(2025, 2, 1), basis="입사일 기준", flag_index={},
        )
        self.assertEqual(summary["status"], "판정 안됨")
        self.assertIsNone(summary["granted_days"])
        self.assertEqual(rows[0]["status"], "판정 안됨")
        self.assertIsNone(rows[0]["calculation_result"])

    def test_annual_service_year_includes_extra_day(self):
        # Older employee flags are intentionally absent: only the current
        # calendar year's January grant must be calculated.
        idx = {
            ("E001", "연간", date(2027, 1, 1), date(2027, 12, 31)): "ELIGIBLE"
        }
        summary, detail = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 1, 1),
            as_of_date=date(2028, 12, 31), basis="입사일 기준",
            flag_index=idx,
        )
        self.assertEqual([r["calculation_result"] for r in detail], ["16"])
        self.assertEqual([r["grant_date"] for r in detail], ["2028-01-01"])
        self.assertEqual(summary["calculation_result"], "16")
        self.assertEqual(summary["granted_days"], "16.0")
    def test_first_year_under_80_no_double_grant(self):
        idx = {("E001", "연간", date(2025, 1, 1), date(2025, 12, 31)): "NOT_ELIGIBLE"}
        for m in range(1, 13):
            start = calc.add_months(date(2025, 1, 1), m - 1)
            end = calc.add_months(date(2025, 1, 1), m) - __import__("datetime").timedelta(days=1)
            idx[("E001", "월간", start, end)] = "ELIGIBLE"
        summary_2025, rows_2025 = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 1, 1),
            as_of_date=date(2025, 12, 31), basis="입사일 기준", flag_index=idx,
        )
        summary_2026, rows_2026 = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 1, 1),
            as_of_date=date(2026, 12, 31), basis="입사일 기준", flag_index=idx,
        )
        self.assertEqual(summary_2025["calculation_result"], "11")
        self.assertEqual(len(rows_2025), 11)
        self.assertEqual(summary_2026["calculation_result"], "1")
        self.assertEqual(len(rows_2026), 1)
        self.assertEqual(rows_2026[0]["grant_type"], "80% 미달 월별 발생")
    def test_nonterminating_decimal_truncated_but_exact_rounding(self):
        self.assertEqual(calc.quantity_text(Fraction(1, 3)), "0.3333333")
        self.assertEqual(calc.quantity_text(Fraction(1, 8)), "0.125")
        self.assertEqual(calc.round_final(Fraction(1, 3), 1), "0.3")
        self.assertEqual(calc.round_final(Fraction(1, 3), 0), "0")
        self.assertEqual(calc.round_final(Fraction(1, 2), 0), "1")
        raw = calc.prorated_quantity(base_days=15, numerator=1, denominator=7)
        self.assertEqual(calc.quantity_text(raw), "2.1428571")
        self.assertEqual(calc.round_final(raw, 1), "2.1")

    def test_final_only_rounding_after_aggregation(self):
        parts = [Fraction("2.14"), Fraction("3.14")]
        self.assertEqual(calc.round_final(sum(parts), 1), "5.3")
        self.assertNotEqual(
            sum((Fraction(calc.round_final(p, 1)) for p in parts), Fraction(0)),
            Fraction(calc.round_final(sum(parts), 1)),
        )

    def test_proration_three_modes_and_validation(self):
        for method in sorted(calc.METHODS):
            result = calc.prorated_quantity(
                base_days="15", numerator=101, denominator=251, method=method)
            self.assertEqual(calc.round_final(result, 1), "6.0")
        for kwargs in (
            dict(base_days=15, numerator=4, denominator=0),
            dict(base_days=15, numerator=5, denominator=4),
            dict(base_days=15, numerator=-1, denominator=4),
            dict(base_days=15, numerator=1.4, denominator=4),
        ):
            with self.assertRaises(ValueError):
                calc.prorated_quantity(**kwargs)

    def test_duplicate_flag_period_rejected(self):
        row = {"employee_id": "E001", "period_start": "2025-01-01",
               "period_end": "2025-01-31", "check_type": "월간",
               "attendance_flag": "개근"}
        with self.assertRaises(ValueError):
            calc.build_flag_index([row, row])

    def test_fiscal_first_year_monthly_before_next_fiscal_boundary(self):
        hire = date(2026, 5, 18)
        idx = {}
        for offset in range(7):
            start = calc.add_months(hire, offset)
            end = calc.add_months(hire, offset + 1) - timedelta(days=1)
            idx[("E001", "월간", start, end)] = "ELIGIBLE"

        for cutoff, expected in (
            (date(2026, 11, 30), 6),
            (date(2026, 12, 31), 7),
        ):
            with self.subTest(cutoff=cutoff):
                summary, rows = calc.calculate_employee(
                    employee_id="E001", hire_date=hire,
                    as_of_date=cutoff, basis="회계연도 기준",
                    flag_index=idx,
                )
                self.assertEqual(summary["status"], "계산 완료")
                self.assertEqual(summary["calculation_result"], str(expected))
                self.assertEqual(summary["granted_days"], f"{expected}.0")
                self.assertEqual(len(rows), expected)
                self.assertTrue(all(row["grant_type"] == "월별 발생" for row in rows))
                self.assertTrue(all(row["basis"] == "회계연도 기준" for row in rows))
                self.assertEqual(rows[0]["grant_date"], "2026-06-18")
                self.assertEqual(rows[-1]["grant_date"], (
                    "2026-11-18" if expected == 6 else "2026-12-18"
                ))

    def test_fiscal_first_year_missing_monthly_flag_is_not_zero(self):
        summary, rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2026, 5, 18),
            as_of_date=date(2026, 6, 18),
            basis="회계연도 기준", flag_index={},
        )
        self.assertEqual(summary["status"], "판정 안됨")
        self.assertIsNone(summary["granted_days"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["grant_type"], "월별 발생")
        self.assertIsNone(rows[0]["calculation_result"])
        self.assertEqual(rows[0]["reason"], "근태 판정 누락·미확정")

    def test_fiscal_initial_proration_not_later_years(self):
        idx = {
            ("E001", "연간", date(2026, 7, 1), date(2026, 12, 31)): "ELIGIBLE",
            ("E001", "연간", date(2027, 1, 1), date(2027, 12, 31)): "ELIGIBLE",
        }
        # Monthly anniversaries after the fiscal boundary remain separate
        # from the initial prorated fiscal grant.
        hire = date(2026, 7, 1)
        for offset in range(5, 11):
            start = calc.add_months(hire, offset)
            end = calc.add_months(hire, offset + 1) - timedelta(days=1)
            idx[("E001", "월간", start, end)] = "ELIGIBLE"
        facts = dict(period_start="2026-07-01", period_end="2026-12-31",
                     method="소정근로일 기준", numerator=125, denominator=250,
                     base_days=15)
        first, first_rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2026, 7, 1),
            as_of_date=date(2027, 12, 31), basis="회계연도 기준", flag_index=idx,
            proration_facts=facts,
        )
        self.assertEqual(first["granted_days"], "13.5")
        prorated = [r for r in first_rows
                    if r["grant_type"] == "최초 회계연도 비례"]
        monthly = [r for r in first_rows if r["grant_type"] == "월별 발생"]
        self.assertEqual(len(prorated), 1)
        self.assertEqual(prorated[0]["grant_date"], "2027-01-01")
        self.assertEqual(prorated[0]["calculation_result"], "7.5")
        self.assertEqual(len(monthly), 6)
        self.assertEqual(monthly[-1]["grant_date"], "2027-06-01")
        self.assertEqual(len({r["grant_id"] for r in first_rows}), 7)
        # 2028 requires only 2027's annual flag; no 2026 proration evidence.
        future, future_rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2026, 7, 1),
            as_of_date=date(2028, 12, 31), basis="회계연도 기준", flag_index=idx,
        )
        self.assertEqual(future["status"], "계산 완료")
        self.assertEqual(future["calculation_result"], "15")
        self.assertEqual(future_rows[0]["grant_type"], "회계연도 정기 발생")
        self.assertEqual(future_rows[0]["grant_date"], "2028-01-01")
    def test_fiscal_grant_for_hire_before_fiscal_start_same_year(self):
        idx = {("E001", "연간", date(2026, 1, 1), date(2026, 3, 31)): "ELIGIBLE"}
        hire = date(2026, 1, 1)
        for offset in range(3):
            start = calc.add_months(hire, offset)
            end = calc.add_months(hire, offset + 1) - timedelta(days=1)
            idx[("E001", "월간", start, end)] = "ELIGIBLE"
        facts = dict(period_start="2026-01-01", period_end="2026-03-31",
                     method="달력일 기준", numerator=90, denominator=365)
        summary, rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2026, 1, 1),
            as_of_date=date(2026, 4, 1), basis="회계연도 기준", flag_index=idx,
            fiscal_year_start="04-01", proration_method="달력일 기준",
            proration_facts=facts,
        )
        prorated = [r for r in rows if r["grant_type"] == "최초 회계연도 비례"]
        monthly = [r for r in rows if r["grant_type"] == "월별 발생"]
        self.assertEqual(len(prorated), 1)
        self.assertEqual(prorated[0]["grant_date"], "2026-04-01")
        self.assertEqual([r["grant_date"] for r in monthly],
                         ["2026-02-01", "2026-03-01", "2026-04-01"])
        self.assertEqual(summary["status"], "계산 완료")

    def test_anniversary_previous_year_is_not_counted(self):
        idx = {
            ("E001", "연간", date(2025, 7, 15), date(2026, 7, 14)): "ELIGIBLE",
        }
        summary, detail = calc.calculate_employee(
            employee_id="E001", hire_date=date(2023, 7, 15),
            as_of_date=date(2026, 12, 31), basis="입사일 기준",
            flag_index=idx,
        )
        self.assertEqual(summary["calculation_result"], "16")
        self.assertEqual([r["grant_date"] for r in detail], ["2026-07-15"])
        self.assertEqual(summary["status"], "계산 완료")

    def test_monthly_grants_filtered_to_cutoff_year(self):
        idx = {}
        for m in range(1, 12):
            start = calc.add_months(date(2025, 7, 1), m - 1)
            end = calc.add_months(date(2025, 7, 1), m) - __import__("datetime").timedelta(days=1)
            idx[("E001", "월간", start, end)] = "ELIGIBLE"
        summary, details = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 7, 1),
            as_of_date=date(2026, 12, 31),
            basis="1년 미만 기준", flag_index=idx,
        )
        self.assertEqual(summary["calculation_result"], "6")
        self.assertEqual(len(details), 6)
        self.assertEqual(details[0]["grant_date"], "2026-01-01")
        self.assertEqual(details[-1]["grant_date"], "2026-06-01")

    def test_cutoff_midyear_excludes_later_grant(self):
        idx = {
            ("E001", "연간", date(2025, 7, 1), date(2026, 6, 30)): "ELIGIBLE",
        }
        for offset in range(11):
            start = calc.add_months(date(2025, 7, 1), offset)
            end = calc.add_months(date(2025, 7, 1), offset + 1) - __import__("datetime").timedelta(days=1)
            idx[("E001", "월간", start, end)] = "NOT_ELIGIBLE"
        before, before_rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 7, 1),
            as_of_date=date(2026, 6, 30), basis="입사일 기준",
            flag_index=idx,
        )
        after, after_rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 7, 1),
            as_of_date=date(2026, 7, 1), basis="입사일 기준",
            flag_index=idx,
        )
        self.assertEqual(before["calculation_result"], "0")
        self.assertEqual(before_rows, [])
        self.assertEqual(after["calculation_result"], "15")
        self.assertEqual(len(after_rows), 1)

    def test_fiscal_recurring_annual_bonus_uses_real_hire_date(self):
        hire = date(2025, 7, 1)
        for year, expected in ((2027, "15"), (2028, "15"), (2029, "16")):
            idx = {
                ("E001", "연간", date(year-1, 1, 1), date(year-1, 12, 31)): "ELIGIBLE"
            }
            summary, rows = calc.calculate_employee(
                employee_id="E001", hire_date=hire,
                as_of_date=date(year, 12, 31), basis="회계연도 기준",
                flag_index=idx,
            )
            self.assertEqual(summary["calculation_result"], expected)
            self.assertEqual(rows[0]["calculation_result"], expected)
            self.assertEqual(rows[0]["grant_date"], f"{year}-01-01")
            self.assertEqual(len(rows), 1)

    def test_fiscal_regular_with_april_year_start(self):
        idx = {
            ("E001", "연간", date(2026, 4, 1), date(2027, 3, 31)): "ELIGIBLE",
        }
        summary, rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2026, 1, 1),
            as_of_date=date(2027, 12, 31), basis="회계연도 기준",
            flag_index=idx, fiscal_year_start="04-01",
        )
        self.assertEqual(summary["calculation_result"], "15")
        self.assertEqual(rows[0]["grant_date"], "2027-04-01")
        self.assertEqual(rows[0]["period_start"], "2026-04-01")
        self.assertEqual(rows[0]["period_end"], "2027-03-31")

    def test_fiscal_under_80_monthly_grant_without_double_award(self):
        idx = {
            ("E001", "연간", date(2026, 1, 1), date(2026, 12, 31)): "NOT_ELIGIBLE"
        }
        for month in range(1, 13):
            start = date(2026, month, 1)
            end = calc.add_months(start, 1) - __import__("datetime").timedelta(days=1)
            idx[("E001", "월간", start, end)] = (
                "NOT_ELIGIBLE" if month == 12 else "ELIGIBLE"
            )
        summary, rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2024, 7, 1),
            as_of_date=date(2027, 12, 31), basis="회계연도 기준",
            flag_index=idx,
        )
        self.assertEqual(summary["calculation_result"], "11")
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r["grant_type"] == "80% 미달 월별 발생" for r in rows))

    def test_fiscal_annual_flag_missing_yields_undetermined(self):
        summary, rows = calc.calculate_employee(
            employee_id="E001", hire_date=date(2025, 7, 1),
            as_of_date=date(2027, 12, 31), basis="회계연도 기준",
            flag_index={},
        )
        self.assertEqual(summary["status"], "판정 안됨")
        self.assertIsNone(summary["granted_days"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reason"], "직전 회계연도의 연간 근태 판정 누락·미확정")

    def test_negative_attendance_or_invalid_dates_fail(self):
        with self.assertRaises(ValueError):
            calc.build_flag_index([dict(employee_id="E001", period_start="2025-02-01",
                                        period_end="2025-01-01", check_type="월간",
                                        attendance_flag="개근")])
        with self.assertRaises(ValueError):
            calc.build_flag_index([dict(employee_id="E001", period_start="2025-01-01",
                                        period_end="2025-01-31", check_type="연간",
                                        attendance_flag="개근")])


class EntitlementWorkbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_excel(self.root / "common" / "employee.xlsx", {
            "재직자": [
                ["employee_id", "hire_date", "termination_date", "work_system"],
                ["E001", "2025-01-01", None, "DAY"],
            ],
            "퇴사자": [
                ["employee_id", "hire_date", "termination_date", "work_system"],
                ["E002", "2024-01-01", "2024-05-01", "DAY"],
            ],
        })
        write_excel(self.root / "paid-time-off" / "attendance-result.xlsx", {
            "근태결과": [
                ["employee_id", "period_start", "period_end",
                 "check_type", "attendance_flag"],
                ["E001", "2025-01-01", "2025-01-31", "월간", "개근"],
                ["E001", "2025-02-01", "2025-02-28", "월간", "판정 안됨"],
            ],
        })

    def test_parallel_sheets_and_policy_last(self):
        result = runner.run_entitlement(
            as_of_date=date(2025, 3, 1), basis="1년 미만 기준",
            policy_id="TEST-2025", run_id="synthetic-01",
            input_root=self.root, output_root=self.root / "output",
        )
        book = load_workbook(result["path"], read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["발생요약", "발생상세", "정책정보"])
            summary = list(book["발생요약"].values)
            self.assertEqual(summary[0], ("employee_id", "basis", "계산결과", "발생연차", "상태"))
            self.assertEqual(summary[1][4], "판정 안됨")
            self.assertIsNone(summary[1][3])
            detail = list(book["발생상세"].values)
            self.assertEqual(detail[1][6], "1")
            self.assertEqual(detail[2][7], "판정 안됨")
            self.assertEqual(list(book["정책정보"].values)[1], ("정책 ID", "TEST-2025"))
        finally:
            book.close()

    def test_workbook_cutoff_year_is_single_policy_period(self):
        write_excel(self.root / "common" / "employee.xlsx", {
            "재직자": [
                ["employee_id", "hire_date", "termination_date"],
                ["E001", "2023-01-01", None],
            ],
            "퇴사자": [
                ["employee_id", "hire_date", "termination_date"],
                ["E002", "2024-01-01", "2024-05-01"],
            ],
        })
        write_excel(self.root / "paid-time-off" / "attendance-result.xlsx", {
            "근태결과": [
                list(runner.ATTENDANCE_COLUMNS),
                ["E001", "2025-01-01", "2025-12-31", "연간", "80% 충족"],
            ],
        })
        result = runner.run_entitlement(
            as_of_date=date(2026, 12, 31), basis="입사일 기준",
            policy_id="TEST-2026", run_id="year-scope",
            input_root=self.root, output_root=self.root / "output",
        )
        book = load_workbook(result["path"], read_only=True)
        try:
            summary = list(book["발생요약"].values)
            self.assertEqual(summary[1][0], "E001")
            self.assertEqual(summary[1][2], "16")
            self.assertEqual(summary[1][3], "16.0")
            detail = list(book["발생상세"].values)
            self.assertEqual(len(detail), 2)
            self.assertEqual(detail[1][5], "2026-01-01")
            policy = dict(list(book["정책정보"].values)[1:])
            self.assertEqual(policy["산정 기준일"], "2026-12-31")
            self.assertEqual(policy["산정 기간 시작일"], "2026-01-01")
            self.assertEqual(policy["산정 기간 종료일"], "2026-12-31")
        finally:
            book.close()

    def test_same_run_id_never_overwrites(self):
        kwargs = dict(as_of_date=date(2025, 3, 1), basis="1년 미만 기준",
                      policy_id="TEST", run_id="same",
                      input_root=self.root, output_root=self.root / "output")
        runner.run_entitlement(**kwargs)
        with self.assertRaises(runner.EntitlementInputError):
            runner.run_entitlement(**kwargs)

    def test_retiree_source_is_not_ignored(self):
        roster = runner.read_employee_roster(self.root / "common" / "employee.xlsx")
        self.assertEqual({r["employee_id"] for r in roster}, {"E001", "E002"})
        self.assertEqual(next(r["termination_date"] for r in roster
                              if r["employee_id"] == "E002"), date(2024, 5, 1))

    def test_empty_or_wrong_approval_flag_does_not_guess(self):
        with self.assertRaises(ValueError):
            calc.build_flag_index([dict(employee_id="E001", period_start="2025-01-01",
                                        period_end="2025-01-31", check_type="월간",
                                        attendance_flag="ELIGIBLE")])

    def test_empty_attendance_flag_becomes_undetermined(self):
        write_excel(self.root / "paid-time-off" / "attendance-result.xlsx", {
            "근태결과": [
                list(runner.ATTENDANCE_COLUMNS),
                ["E001", "2025-01-01", "2025-01-31", "월간", None],
            ],
        })
        result = runner.run_entitlement(
            as_of_date=date(2025, 2, 1), basis="1년 미만 기준",
            policy_id="T", run_id="empty-flag",
            input_root=self.root, output_root=self.root / "output",
        )
        e001 = next(row for row in result["summaries"] if row["employee_id"] == "E001")
        self.assertEqual(e001["status"], "판정 안됨")
        self.assertIsNone(e001["granted_days"])

    def test_no_explicit_file_fallback(self):
        with self.assertRaises(runner.EntitlementInputError):
            runner.run_entitlement(
                as_of_date=date(2025, 3, 1), basis="1년 미만 기준",
                policy_id="T", run_id="missing",
                input_root=self.root, output_root=self.root / "output",
                attendance_file=self.root / "absent.xlsx",
            )

    def test_excel_formula_rejected(self):
        write_excel(self.root / "paid-time-off" / "attendance-result.xlsx", {
            "근태결과": [
                list(runner.ATTENDANCE_COLUMNS),
                ["E001", "2025-01-01", "2025-01-31", "월간", "=TRUE()"],
            ],
        })
        with self.assertRaises(runner.EntitlementInputError):
            runner.run_entitlement(
                as_of_date=date(2025, 3, 1), basis="1년 미만 기준",
                policy_id="T", run_id="formula",
                input_root=self.root, output_root=self.root / "output",
            )


if __name__ == "__main__":
    unittest.main()
