"""Unittest for dynamic, two-tier, review-only Payroll output."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from bhandara.payroll.output import (
    FILENAME, PayrollOutputError, build_payroll_register,
)
from bhandara.payroll.output_excel import write_payroll_result_xlsx


def employee(employee_id="E001", **overrides):
    result = {
        "employee_id": employee_id,
        "base_pay": 3000000,
        "fixed_allowances": [],
        "overtime_allowances": [],
        "performance_bonuses": [],
        "deductions": [],
        "earnings_complete": True,
        "deductions_complete": True,
    }
    result.update(overrides)
    return result


def item(item_id, label, amount):
    return {"item_id": item_id, "label": label, "amount": amount}


class PayrollDynamicRegisterTests(unittest.TestCase):
    def _keys(self, result):
        return [column["key"] for column in result["columns"]]

    def test_one_of_fifty_receives_allowance(self):
        employees = [employee(f"E{i:03d}") for i in range(1, 51)]
        employees[16]["fixed_allowances"] = [item("001", "자격수당", 100000)]
        result = build_payroll_register(employees)
        key = "fixed_allowances:001"
        self.assertEqual(len(result["rows"]), 50)
        self.assertEqual(self._keys(result).count(key), 1)
        self.assertEqual(sum(row[key] is not None for row in result["rows"]), 1)
        self.assertEqual(result["rows"][16][key], 100000)
        self.assertIsNone(result["rows"][0][key])

    def test_empty_categories_disappear_but_totals_stay(self):
        result = build_payroll_register([employee()])
        keys = self._keys(result)
        self.assertEqual(keys, [
            "employee_id", "base_pay", "gross_pay",
            "deduction_total", "net_pay", "review_status",
        ])
        self.assertEqual(result["rows"][0]["net_pay"], 3000000)
        self.assertEqual(result["rows"][0]["review_status"], "REVIEW_REQUIRED")
        self.assertEqual(result["approval_state"], "NOT_APPROVED")

    def test_all_zero_items_do_not_create_column(self):
        result = build_payroll_register([employee(fixed_allowances=[item("A", "식대", 0)])])
        self.assertNotIn("fixed_allowances:A", self._keys(result))

    def test_negative_settlement_creates_column(self):
        result = build_payroll_register([
            employee(fixed_allowances=[item("A", "소급 정산", -25000)])
        ])
        self.assertIn("fixed_allowances:A", self._keys(result))
        self.assertEqual(result["rows"][0]["gross_pay"], 2975000)

    def test_bonuses_and_overtime_follow_stable_group_order(self):
        result = build_payroll_register([
            employee(overtime_allowances=[item("OT", "연장근로", 45000)],
                     performance_bonuses=[item("B", "프로젝트 성과급", 100000)],
                     fixed_allowances=[item("A", "식대", 200000)],
                     deductions=[item("NPS", "국민연금", 150000)])
        ])
        keys = self._keys(result)
        self.assertLess(keys.index("fixed_allowances:A"), keys.index("overtime_allowances:OT"))
        self.assertLess(keys.index("overtime_allowances:OT"), keys.index("performance_bonuses:B"))
        self.assertLess(keys.index("performance_bonuses:B"), keys.index("gross_pay"))
        self.assertLess(keys.index("gross_pay"), keys.index("deductions:NPS"))
        self.assertEqual(result["rows"][0]["gross_pay"], 3345000)
        self.assertEqual(result["rows"][0]["net_pay"], 3195000)

    def test_same_id_different_levels_share_column(self):
        result = build_payroll_register([
            employee("E001", fixed_allowances=[item("Q", "자격수당", 100000)]),
            employee("E002", fixed_allowances=[item("Q", "자격수당", 200000)]),
        ])
        self.assertEqual(self._keys(result).count("fixed_allowances:Q"), 1)
        self.assertEqual([r["fixed_allowances:Q"] for r in result["rows"]], [100000, 200000])

    def test_same_display_name_distinct_id_gets_disambiguation(self):
        result = build_payroll_register([
            employee("E001", fixed_allowances=[item("001", "자격수당", 100000)]),
            employee("E002", fixed_allowances=[item("002", "자격수당", 200000)]),
        ])
        labels = [c["label"] for c in result["columns"] if c.get("source") == "fixed_allowances"]
        self.assertEqual(labels, ["자격수당 [001]", "자격수당 [002]"])

    def test_same_id_with_different_display_name_is_rejected(self):
        with self.assertRaisesRegex(PayrollOutputError, "inconsistent label"):
            build_payroll_register([
                employee("E001", fixed_allowances=[item("001", "자격수당", 100000)]),
                employee("E002", fixed_allowances=[item("001", "기술수당", 100000)]),
            ])

    def test_deduction_unverified_does_not_invent_net_pay(self):
        result = build_payroll_register([
            employee(deductions_complete=False,
                     deductions=[item("PENSION", "국민연금", 50000)])
        ])
        row = result["rows"][0]
        self.assertEqual(row["gross_pay"], 3000000)
        self.assertEqual(row["deductions:PENSION"], 50000)
        self.assertIsNone(row["deduction_total"])
        self.assertIsNone(row["net_pay"])
        self.assertEqual(row["review_status"], "PARTIAL_REVIEW_ONLY")

    def test_earnings_unverified_does_not_invent_net_pay(self):
        row = build_payroll_register([employee(earnings_complete=False)])["rows"][0]
        self.assertIsNone(row["gross_pay"])
        self.assertEqual(row["deduction_total"], 0)
        self.assertIsNone(row["net_pay"])

    def test_omitted_completion_flags_are_not_assumed_true(self):
        data = employee()
        data.pop("deductions_complete")
        with self.assertRaisesRegex(PayrollOutputError, "explicit boolean"):
            build_payroll_register([data])

    def test_duplicates_and_invalid_amount_rejected(self):
        with self.assertRaisesRegex(PayrollOutputError, "duplicate employee_id"):
            build_payroll_register([employee(), employee()])
        with self.assertRaisesRegex(PayrollOutputError, "duplicate item_id"):
            build_payroll_register([employee(fixed_allowances=[
                item("Q", "자격수당", 10), item("Q", "자격수당", 20)])])
        with self.assertRaisesRegex(PayrollOutputError, "integer KRW"):
            build_payroll_register([employee(base_pay="1000.1")])
        with self.assertRaisesRegex(PayrollOutputError, "integer KRW"):
            build_payroll_register([employee(base_pay=float("nan"))])

    def test_generated_column_order_does_not_depend_on_employee_order(self):
        first = employee("E001", fixed_allowances=[item("ZZ", "후순위", 100)])
        second = employee("E002", fixed_allowances=[item("AA", "선순위", 200)])
        a = build_payroll_register([first, second])
        b = build_payroll_register([second, first])
        self.assertEqual(self._keys(a), self._keys(b))

    def test_optional_employee_name_column(self):
        result = build_payroll_register([
            employee("E001", employee_name="가상 직원"),
            employee("E002"),
        ])
        self.assertEqual(self._keys(result)[:2], ["employee_id", "employee_name"])
        self.assertIsNone(result["rows"][1]["employee_name"])

    def test_writer_has_exact_single_sheet_and_two_tier_headers(self):
        result = build_payroll_register([
            employee("E001", employee_name="가상A", fixed_allowances=[
                item("A", "식대", 200000), item("B", "자격수당", 100000)]),
            employee("E002", employee_name="가상B"),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / FILENAME
            write_payroll_result_xlsx(result, path)
            book = load_workbook(path, read_only=False, data_only=True)
            try:
                self.assertEqual(book.sheetnames, ["PAYROLL"])
                ws = book["PAYROLL"]
                keys = self._keys(result)
                a_col = keys.index("fixed_allowances:A") + 1
                b_col = keys.index("fixed_allowances:B") + 1
                self.assertEqual(ws.cell(1, a_col).value, "고정수당")
                self.assertEqual(ws.cell(2, a_col).value, "식대")
                self.assertEqual(ws.cell(2, b_col).value, "자격수당")
                self.assertIsNone(ws.cell(4, a_col).value)
                self.assertTrue(any(rng.min_col == a_col and rng.max_col == b_col
                                    and rng.min_row == 1 for rng in ws.merged_cells.ranges))
                self.assertEqual(ws.freeze_panes, "C3")
                net_col = keys.index("net_pay") + 1
                self.assertEqual(ws.cell(3, net_col).value, 3300000)
            finally:
                book.close()

    def test_writer_does_not_overwrite_and_rejects_wrong_result(self):
        result = build_payroll_register([employee()])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / FILENAME
            write_payroll_result_xlsx(result, path)
            with self.assertRaisesRegex(PayrollOutputError, "already exists"):
                write_payroll_result_xlsx(result, path)
            with self.assertRaisesRegex(PayrollOutputError, "fixed output filename"):
                write_payroll_result_xlsx(result, Path(tmp) / "wrong.xlsx")
            invalid = deepcopy(result)
            invalid["approval_state"] = "APPROVED"
            with self.assertRaisesRegex(PayrollOutputError, "contract"):
                write_payroll_result_xlsx(invalid, Path(tmp) / "other.xlsx")


if __name__ == "__main__":
    unittest.main()
