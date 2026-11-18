"""Synthetic Closing tests: year-opening retention, quarterly YTD and Excel."""
from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date
from fractions import Fraction
from pathlib import Path

from openpyxl import load_workbook

calc = importlib.import_module("bhandara.paid-time-off.closing.calculation")
runner = importlib.import_module("bhandara.paid-time-off.runner_closing")
usage = importlib.import_module("bhandara.paid-time-off.runner_usage")


def grant(identifier, *, employee="E001", kind="연차",
          grant_date="2026-01-01", avail="1", remain="1",
          expires="2027-12-31", source_type="신규연차", start=None):
    return {
        "grant_id": identifier, "employee_id": employee,
        "leave_type": kind, "grant_date": grant_date,
        "available_days": avail, "remaining_days": remain,
        "valid_from": start or grant_date, "expires_on": expires,
        "source_ref": identifier, "source_type": source_type,
    }


def used(request_id, day, days, *, kind="연차", status="사용"):
    return {
        "employee_id": "E001", "leave_type": kind,
        "request_id": request_id, "leave_date": day,
        "차감일수": days, "처리구분": status,
    }


def expired(kind, day, qty, status="만료"):
    return {
        "employee_id": "E001", "expires_on": day,
        "expiry_days": qty, "status": status,
    }


class ClosingArithmeticTests(unittest.TestCase):
    def quarter1(self):
        # Opening year balance: 5 days - 2 carried shortage = 3.
        # Jan use 1, Mar compensatory use 0.5, end-March expiry 4.
        sources = [
            grant("OLD", grant_date="2025-01-01", start="2025-01-01",
                  avail="5", remain="4", expires="2026-03-31",
                  source_type="기초인계"),
            grant("ANNUAL", avail="15", remain="15"),
            grant("COMP", kind="대휴", grant_date="2026-03-01",
                  source_type="신규대휴", avail="1.5", remain="1"),
        ]
        details = [
            used("R1", "2026-01-12", "1"),
            used("R2", "2026-03-10", "0.5", kind="대휴"),
            used("R0", "2025-11-15", "2", status="인계부족"),
        ]
        return calc.calculate_closing(
            closing_id="Closing-1.4-2026", source_grants=sources,
            usage_details=details,
            expiry_rows=[
                expired("연차", "2026-03-31", "4"),
                expired("연차", "2027-12-31", "0", "이월"),
                expired("대휴", "2027-12-31", "0", "이월"),
            ],
            usage_summaries=[{"employee_id": "E001", "잔여일수": "14"}],
            name_map={"E001": "홍길동"},
        )

    def test_q1_opening_is_january_1_and_unused_months_are_blank(self):
        result = self.quarter1()
        row = result["report"][0]
        self.assertEqual(row["name"], "홍길동")
        self.assertEqual(row["발생연차일수"], 15)
        self.assertEqual(row["기초이월잔여일수"], 3)
        self.assertEqual(row["대휴발생일수"], Fraction(3, 2))
        self.assertEqual(row["총확보휴가일수"], Fraction(39, 2))
        self.assertEqual(row["미사용만료일수"], 4)
        self.assertEqual(row["1월"], 1)
        self.assertEqual(row["2월"], 0)
        self.assertEqual(row["3월"], Fraction(1, 2))
        self.assertIsNone(row["4월"])
        self.assertIsNone(row["12월"])
        self.assertEqual(row["누적사용일수"], Fraction(3, 2))
        self.assertEqual(row["마감잔여일수"], 14)
        self.assertEqual(row["마감상태"], "초과사용")
        self.assertEqual(next(x for x in result["carry_rows"]
                              if x["grant_id"] == "OLD")["available_days"], 0)
        self.assertEqual(result["shortage_rows"][0]["request_id"], "R0")
        self.assertEqual(result["shortage_rows"][0]["shortage_days"], 2)

    def test_q2_keeps_q1_opening_and_accumulates_ytd_only_once(self):
        q1 = self.quarter1()["report"]
        sources = [
            grant("OLD", grant_date="2025-01-01", start="2025-01-01",
                  avail="0", remain="0", expires="2026-03-31",
                  source_type="기초인계"),
            grant("ANNUAL", avail="15", remain="14",
                  source_type="기초인계"),
            grant("COMP", kind="대휴", grant_date="2026-03-01",
                  avail="1", remain="0", source_type="기초인계"),
            grant("ANNUAL2", grant_date="2026-04-01",
                  avail="2", remain="2"),
            grant("COMP2", kind="대휴", grant_date="2026-05-01",
                  avail="1", remain="1", source_type="신규대휴"),
        ]
        result = calc.calculate_closing(
            closing_id="Closing-2.4-2026", source_grants=sources,
            usage_details=[
                used("R3", "2026-04-10", "1"),
                used("R4", "2026-05-10", "1", kind="대휴"),
                used("R0", "2025-11-15", "2", status="인계부족"),
            ],
            expiry_rows=[
                expired("연차", "2026-03-31", "0", "잔여 없음"),
                expired("연차", "2027-12-31", "0", "이월"),
            ],
            usage_summaries=[{"employee_id": "E001", "잔여일수": "15"}],
            name_map={"E001": "홍길동"},
            previous_rows=q1, previous_closing_id="Closing-1.4-2026",
        )
        row = result["report"][0]
        self.assertEqual(row["발생연차일수"], 17)
        self.assertEqual(row["기초이월잔여일수"], 3)
        self.assertEqual(row["대휴발생일수"], Fraction(5, 2))
        self.assertEqual(row["총확보휴가일수"], Fraction(45, 2))
        self.assertEqual(row["미사용만료일수"], 4)
        self.assertEqual(row["1월"], 1)
        self.assertEqual(row["3월"], Fraction(1, 2))
        self.assertEqual(row["4월"], 1)
        self.assertEqual(row["5월"], 1)
        self.assertEqual(row["6월"], 0)
        self.assertIsNone(row["7월"])
        self.assertEqual(row["누적사용일수"], Fraction(7, 2))
        self.assertEqual(row["마감잔여일수"], 15)
        self.assertEqual(row["마감상태"], "초과사용")

    def test_q3_promotion_external_flags_only(self):
        args = {
            "closing_id": "Closing-3.4-2026",
            "source_grants": [grant("A", avail="15", remain="15")],
            "usage_details": [],
            "expiry_rows": [expired("연차", "2027-12-31", "0", "이월")],
            "usage_summaries": [{"employee_id": "E001", "잔여일수": "15"}],
            "name_map": {"E001": "홍길동"},
        }
        pending = calc.calculate_closing(**args)
        self.assertEqual(pending["report"][0]["마감상태"], "자료확인 필요")
        self.assertIsNone(pending["report"][0]["마감잔여일수"])
        reviewed = calc.calculate_closing(
            **args, promotion_flags={"E001": True})
        self.assertEqual(reviewed["report"][0]["마감상태"], "사용촉진 검토")
        self.assertEqual(reviewed["report"][0]["마감잔여일수"], 15)
        normal = calc.calculate_closing(
            **args, promotion_flags={"E001": False})
        self.assertEqual(normal["report"][0]["마감상태"], "정상")

    def test_current_shortage_is_deducted_by_month_not_twice_in_opening(self):
        result = calc.calculate_closing(
            closing_id="Closing-1.4-2026",
            source_grants=[grant("A", avail="2", remain="0")],
            usage_details=[used("R1", "2026-01-10", "2"),
                           used("R2", "2026-02-10", "3", status="부족")],
            expiry_rows=[],
            usage_summaries=[{"employee_id": "E001", "잔여일수": "-3"}],
            name_map={"E001": "홍길동"},
        )
        row = result["report"][0]
        self.assertEqual(row["기초이월잔여일수"], 0)
        self.assertEqual(row["누적사용일수"], 5)
        self.assertEqual(row["마감잔여일수"], -3)
        self.assertEqual(row["마감상태"], "초과사용")
        self.assertEqual(result["shortage_rows"][0]["shortage_days"], 3)

    def test_negative_opening_is_real_excel_number_and_exact_machine_text(self):
        result = calc.calculate_closing(
            closing_id="Closing-1.4-2026", source_grants=[],
            usage_details=[used("R0", "2025-11-15", "3", status="인계부족")],
            expiry_rows=[],
            usage_summaries=[{"employee_id": "E001", "잔여일수": "-3"}],
            name_map={"E001": "홍길동"},
        )
        self.assertEqual(result["report"][0]["기초이월잔여일수"], -3)
        self.assertEqual(result["report"][0]["마감잔여일수"], -3)
        self.assertEqual(result["report"][0]["마감상태"], "초과사용")
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "closing.xlsx"
            file.write_bytes(runner.make_closing_workbook(
                result, {"참조 ID": "Closing-1.4-2026",
                         "확정여부": "미확정"}))
            book = load_workbook(file)
            try:
                self.assertEqual(book["마감보고"]["D2"].value, -3)
                self.assertEqual(book["마감보고"]["U2"].value, -3)
                self.assertEqual(book["마감보고"]["U2"].data_type, "n")
                self.assertIn("(", book["마감보고"]["U2"].number_format)
            finally:
                book.close()
            exact = usage.read_rows(
                file, "_수량정본",
                ("employee_id", "기초이월잔여일수", "마감잔여일수"))
            self.assertEqual(exact[0]["기초이월잔여일수"], "-3")
            self.assertEqual(exact[0]["마감잔여일수"], "-3")

    def test_period_errors_and_partial_summaries_do_not_silently_finalize(self):
        data = calc.calculate_closing(
            closing_id="Closing-4.4-2026",
            source_grants=[grant("A", avail="1", remain="1")],
            usage_details=[],
            expiry_rows=[],
            usage_summaries=[{"employee_id": "E001", "잔여일수": None}],
            name_map={"E001": "홍길동"},
            input_issues=[{"employee_id": "E001",
                           "source": "input", "reason": "기간 누락"}],
        )
        self.assertEqual(data["report"][0]["마감상태"], "자료확인 필요")
        self.assertIsNone(data["report"][0]["마감잔여일수"])
        with self.assertRaisesRegex(ValueError, "바로 앞 분기"):
            calc.calculate_closing(
                closing_id="Closing-4.4-2026", source_grants=[],
                usage_details=[], expiry_rows=[], usage_summaries=[],
                name_map={}, previous_closing_id="Closing-1.4-2026",
            )


class ClosingExcelContractTests(unittest.TestCase):
    def setUp(self):
        self.base = importlib.import_module(
            "bhandara.tests.test_paid_time_off_usage_excel")
        self.fixture = self.base.ExcelUsageTests(
            "test_full_relations_and_distinct_expiry_carryover")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        employee_file = self.fixture.inputs / "common" / "employee.xlsx"
        self.base.write_tables(employee_file, {
            "재직자": (
                ["employee_id", "name", "hire_date"],
                [["E001", "홍길동", "2025-01-01"]]),
            "퇴사자": (
                ["employee_id", "name", "hire_date", "termination_date"], []),
        })
        self.employee_file = employee_file
        self.usage_data = self.fixture.run_usage()
        self.source = Path(self.usage_data["path"])

    def test_template_header_order_annual_amounts_and_no_automatic_approval(self):
        result = runner.run_closing(
            closing_id="Closing-4.4-2026", policy_id="SYNTHETIC",
            run_id="closing-e2e", usage_file=self.source,
            employee_file=self.employee_file, output_root=self.fixture.out,
        )
        row = result["report"][0]
        self.assertEqual(row["발생연차일수"], 15)
        self.assertEqual(row["기초이월잔여일수"], 2)
        self.assertEqual(row["대휴발생일수"], Fraction(3, 2))
        self.assertEqual(row["미사용만료일수"], Fraction(9, 2))
        self.assertEqual(row["누적사용일수"], 2)
        self.assertEqual(row["마감잔여일수"], 12)
        self.assertEqual(row["마감상태"], "초과사용")
        book = load_workbook(result["path"], read_only=False)
        try:
            self.assertEqual([x.value for x in book["마감보고"][1]],
                             list(calc.REPORT_COLUMNS))
            self.assertEqual(len(calc.REPORT_COLUMNS), 22)
            self.assertEqual(book["마감보고"]["C2"].value, 15)
            self.assertEqual(book["마감보고"]["D2"].value, 2)
            self.assertEqual(book["마감보고"]["U2"].value, 12)
            self.assertEqual(book["마감보고"]["V2"].value, "초과사용")
            self.assertEqual(book["마감보고"]["H2"].value, 0)
            self.assertEqual(book["마감보고"]["M2"].value, 1)  # June
            self.assertEqual(book["마감보고"]["R2"].value, 1)  # November
            self.assertEqual(book["인계자료"].sheet_state, "hidden")
            self.assertEqual(book["미상계부족"].sheet_state, "hidden")
            self.assertEqual(book["_수량정본"].sheet_state, "hidden")
            self.assertEqual(dict(book["정책정보"].values)["확정여부"],
                             "미확정")
            self.assertNotEqual(book["마감보고"]["U2"].data_type, "f")
        finally:
            book.close()
        with self.assertRaisesRegex(
            usage.UsageInputError, "확정된 상태가 아닙니다"
        ):
            usage._read_carry(Path(result["path"]))
        with self.assertRaises(runner.ClosingInputError):
            runner.run_closing(
                closing_id="Closing-4.4-2026", policy_id="SYNTHETIC",
                run_id="closing-e2e", usage_file=self.source,
                employee_file=self.employee_file,
                output_root=self.fixture.out)

    def test_handoff_after_explicit_approval_preserves_exhausted_ids_and_debt(self):
        output = runner.run_closing(
            closing_id="Closing-4.4-2026", policy_id="SYNTHETIC",
            run_id="handoff", usage_file=self.source,
            employee_file=self.employee_file, output_root=self.fixture.out,
        )
        book = load_workbook(output["path"])
        try:
            sheet = book["정책정보"]
            for row in sheet.iter_rows(min_row=2):
                if row[0].value == "확정여부":
                    row[1].value = "확정"  # external operator approval
            book.save(output["path"])
        finally:
            book.close()
        grants, shortages, ref, end = usage._read_carry(Path(output["path"]))
        self.assertEqual(ref, "Closing-4.4-2026")
        self.assertEqual(end, date(2026, 12, 31))
        by_id = {g["grant_id"]: g for g in grants}
        self.assertEqual(by_id["OLD-01"]["available_days"], "0")
        self.assertEqual(by_id["OLD-ZERO"]["available_days"], "0")
        self.assertEqual(by_id["C001"]["available_days"], "0")
        self.assertEqual(by_id[self.fixture.grant_id]["available_days"], "15")
        self.assertEqual(len(shortages), 1)
        self.assertEqual(shortages[0]["request_id"], "OLD-R")
        self.assertEqual(int(shortages[0]["shortage_days"]), 3)

    def test_mismatched_closing_period_is_rejected(self):
        with self.assertRaisesRegex(runner.ClosingInputError, "Closing ID"):
            runner.run_closing(
                closing_id="Closing-3.4-2026", policy_id="TEST",
                run_id="wrong", usage_file=self.source,
                employee_file=self.employee_file,
                output_root=self.fixture.out)


if __name__ == "__main__":
    unittest.main()
