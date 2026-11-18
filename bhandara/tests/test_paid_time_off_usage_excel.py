"""End-to-end synthetic Excel contract for PTO's optional source/usage Flow."""
from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from openpyxl import Workbook, load_workbook

runner = importlib.import_module("bhandara.paid-time-off.runner")
usage = importlib.import_module("bhandara.paid-time-off.runner_usage")
ent = importlib.import_module("bhandara.paid-time-off.entitlement.calculation")
join = importlib.import_module("bhandara.paid-time-off.source_join")


def write_tables(path: Path, tables: dict[str, tuple[list, list[list]]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    book.remove(book.active)
    for name, (headers, rows) in tables.items():
        sheet = book.create_sheet(name)
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
    book.save(path)
    book.close()


def rows_by_header(path: Path, sheet: str):
    book = load_workbook(path, data_only=True)
    try:
        values = list(book[sheet].values)
        return [dict(zip(values[0], row)) for row in values[1:]]
    finally:
        book.close()


class EntitlementIdentityTests(unittest.TestCase):
    def test_stable_grant_ids_and_reflected_exact_total(self):
        row = {
            "employee_id": "E001", "basis": "회계연도 기준",
            "grant_type": "최초 회계연도 비례", "period_start": "2026-01-01",
            "period_end": "2026-12-31", "grant_date": "2027-01-01",
        }
        identity = ent.grant_identity(row)
        self.assertEqual(identity, ent.grant_identity(dict(reversed(list(row.items())))))
        # Correcting the calculated quantity does not change identity.
        self.assertEqual(identity, ent.grant_identity({**row, "calculation_result": "2.95"}))
        events = [
            ({**row, "calculation_result": "0.3333333"}, Fraction(1, 3)),
            ({**row, "grant_type": "월별 발생",
              "calculation_result": "0.3333333"}, Fraction(1, 3)),
            ({**row, "grant_type": "80% 미달 월별 발생",
              "calculation_result": "0.3333333"}, Fraction(1, 3)),
        ]
        details = ent._apply_reflected_days(events, rounding_digits=1,
                                           unresolved=False)
        self.assertEqual(sum(Fraction(x["reflected_days"]) for x in details),
                         Fraction(1))
        self.assertEqual(sorted(x["reflected_days"] for x in details),
                         ["0.3", "0.3", "0.4"])
        self.assertEqual([x["calculation_result"] for x in details],
                         ["0.3333333"] * 3)
        self.assertEqual([x["grant_id"] for x in details],
                         [ent.grant_identity(x) for x in details])

    def test_undetermined_does_not_publish_partial_reflected_amount(self):
        row = {
            "employee_id": "E001", "basis": "회계연도 기준",
            "grant_type": "회계연도 정기 발생",
            "period_start": "2025-01-01", "period_end": "2025-12-31",
            "grant_date": "2026-01-01", "calculation_result": "15",
        }
        rows = ent._apply_reflected_days(
            [(row, Fraction(15)), ({**row, "grant_type": "최초 회계연도 비례"}, None)],
            rounding_digits=1, unresolved=True)
        self.assertTrue(all(x["reflected_days"] is None for x in rows))


class ExcelUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = self.root / "data"
        self.out = self.root / "out"
        employee = self.inputs / "common" / "employee.xlsx"
        write_tables(employee, {
            "재직자": (["employee_id", "hire_date"],
                      [["E001", "2025-01-01"]]),
            "퇴사자": (["employee_id", "hire_date", "termination_date"], []),
        })
        attendance = self.inputs / "paid-time-off" / "attendance-result.xlsx"
        write_tables(attendance, {
            "근태결과": (["employee_id", "period_start", "period_end",
                      "check_type", "attendance_flag"], [
                      ["E001", "2025-01-01", "2025-12-31",
                       "연간", "80% 충족"]]),
        })
        self.ent_result = runner.run_entitlement(
            as_of_date=date(2026, 12, 31), basis="입사일 기준",
            policy_id="POLICY-2026", run_id="ent", input_root=self.inputs,
            output_root=self.out,
        )
        self.ent_file = Path(self.ent_result["path"])
        self.grant_id = self.ent_result["details"][0]["grant_id"]
        self.assertEqual(self.ent_result["details"][0]["reflected_days"], "15.0")
        self.assertEqual(self.ent_result["summaries"][0]["granted_days"], "15.0")
        self.refs = self.inputs / "paid-time-off" / "grant-references.xlsx"
        self.carry = self.inputs / "paid-time-off" / "carry-in.xlsx"
        self.approved = self.inputs / "paid-time-off" / "approved-leave.xlsx"
        self._write_refs()
        self._write_carry()
        self._write_approved([
            ["R-A", "E001", "2026-11-10", "연차", 8],
            ["R-C", "E001", "2026-06-01", "대휴", 8],
            ["R-FUT", "E001", "2027-01-15", "연차", 8],
            ["R-PRE", "E001", "2025-12-01", "연차", 8],
        ])

    def _write_refs(self, annual_start="2026-01-01", annual_end="2027-06-30",
                    comp_end="2026-12-31"):
        write_tables(self.refs, {
            "발생근거": (
                ["grant_id", "employee_id", "grant_date", "valid_from",
                 "expires_on", "source_ref"], [
                [self.grant_id, None, None, annual_start, annual_end, None],
                ["C001", "E001", "2026-05-01",
                 "2026-05-01", comp_end, "COMP-2026-001"],
            ]),
            "대휴발생": (["source_ref", "반영발생일수"],
                        [["COMP-2026-001", "1.5"]]),
        })

    def _write_carry(self, include_shortages=True):
        write_tables(self.carry, {
            "정책정보": (["항목", "값"],
                       [["참조 ID", "Closing-4.4-2025"], ["확정여부", "확정"]]),
            "인계자료": (
                ["grant_id", "employee_id", "leave_type", "grant_date",
                 "available_days", "valid_from", "expires_on", "source_ref"], [
                ["OLD-01", "E001", "연차", "2025-01-01",
                 5, "2025-01-01", "2026-12-31", "ENT-2025"],
                ["OLD-ZERO", "E001", "연차", "2025-03-01",
                 0, "2025-03-01", "2026-10-31", "ENT-2025"],
            ]),
            "미상계부족": (
                ["request_id", "employee_id", "leave_type", "leave_date",
                 "shortage_days"],
                [["OLD-R", "E001", "연차", "2025-11-15", 3]]
                if include_shortages else []),
        })

    def _write_approved(self, values, daily=8):
        write_tables(self.approved, {
            "승인휴가": (
                ["request_id", "employee_id", "leave_date", "leave_type",
                 "duration_hours"], values),
        })
        self.deduct_result = runner.run_deduction_quantity(
            policy_id="POLICY-2026", run_id=f"deduct-{daily}-{len(values)}",
            output_root=self.out, approved_file=self.approved,
            standard_daily_hours=daily)
        self.deduct_file = Path(self.deduct_result["path"])

    def run_usage(self, *, carry=True, closing="Closing-4.4-2026", run_id="ledger"):
        return usage.run_usage_ledger(
            as_of_date=date(2026, 12, 31), policy_id="POLICY-2026",
            run_id=run_id, entitlement_file=self.ent_file,
            deduction_file=self.deduct_file, reference_file=self.refs,
            carry_in_file=self.carry if carry else None,
            closing_id=closing, output_root=self.out,
        )

    def test_entitlement_grant_columns_and_hidden_deduction_precision(self):
        lines = rows_by_header(self.ent_file, "발생상세")
        self.assertEqual(lines[0]["grant_id"], self.grant_id)
        self.assertEqual(lines[0]["반영발생일수"], "15.0")
        lines = rows_by_header(self.deduct_file, "차감상세")
        self.assertEqual(lines[0]["_exact_numerator"], 1)
        self.assertEqual(lines[0]["_exact_denominator"], 1)
        book = load_workbook(self.deduct_file)
        try:
            self.assertTrue(book["차감상세"].column_dimensions["J"].hidden)
            self.assertTrue(book["차감상세"].column_dimensions["K"].hidden)
        finally:
            book.close()

    def test_full_relations_and_distinct_expiry_carryover(self):
        result = self.run_usage()
        self.assertFalse(result["issues"], result["issues"])
        details = rows_by_header(Path(result["path"]), "사용상세")
        self.assertEqual({r["request_id"] for r in details},
                         {"R-A", "R-C", "R-FUT", "OLD-R"})
        self.assertEqual(next(r["grant_id"] for r in details
                              if r["request_id"] == "R-A"), "OLD-01")
        self.assertEqual(next(r["grant_id"] for r in details
                              if r["request_id"] == "R-FUT"), self.grant_id)
        self.assertEqual(next(r["처리구분"] for r in details
                              if r["request_id"] == "R-FUT"), "예약")
        self.assertEqual(next(r["처리구분"] for r in details
                              if r["request_id"] == "OLD-R"), "인계부족")
        summary = rows_by_header(Path(result["path"]), "사용요약")[0]
        self.assertEqual(summary["employee_id"], "E001")
        self.assertEqual(summary["발생일수"], 21.5)
        self.assertEqual(summary["사용일수"], 2)
        # Quarter close excludes rights expiring on the closing date.
        self.assertEqual(summary["잔여일수"], 12)
        expiry_rows = rows_by_header(Path(result["path"]), "만료이월")
        by_id = {x["grant_id"]: x for x in expiry_rows}
        self.assertEqual(by_id["OLD-01"]["expiry_days"], 4)
        self.assertEqual(by_id["C001"]["expiry_days"], 0.5)
        self.assertEqual(by_id[self.grant_id]["carryover_days"], 15)
        self.assertEqual(by_id["OLD-ZERO"]["status"], "잔여 없음")
        self.assertNotIn("R-PRE", [row["request_id"] for row in details])
        book = load_workbook(result["path"])
        try:
            self.assertEqual(book.sheetnames,
                             ["사용요약", "사용상세", "만료이월", "정책정보"])
        finally:
            book.close()

    def test_negative_balance_is_numeric_and_no_auto_offset(self):
        self._write_refs(annual_start="2027-01-01",
                         annual_end="2027-12-31",
                         comp_end="2026-10-31")
        self._write_approved([["NEG-R", "E001", "2026-11-10", "연차", 8]])
        result = self.run_usage(carry=False, closing=None, run_id="negative")
        summary = rows_by_header(Path(result["path"]), "사용요약")[0]
        self.assertEqual(summary["잔여일수"], -1)
        self.assertEqual(summary["사용일수"], 1)
        self.assertEqual(rows_by_header(Path(result["path"]), "사용상세")[0]
                         ["처리구분"], "부족")
        self.assertFalse(result["expiry"])

    def test_exact_one_third_plus_two_thirds_no_phantom_shortage(self):
        self._write_approved([
            ["Q1", "E001", "2026-06-15", "대휴", 1],
            ["Q2", "E001", "2026-06-16", "대휴", 2],
        ], daily=3)
        result = self.run_usage(carry=False, closing=None, run_id="fraction")
        self.assertFalse(result["issues"], result["issues"])
        self.assertFalse(any(row["처리구분"] == "부족"
                             for row in result["details"]))
        comp = [x for x in result["details"] if x["grant_id"] == "C001"]
        self.assertEqual(len(comp), 2)
        self.assertEqual(sum(
            x["차감일수"] for x in comp), Fraction(1))
        self.assertEqual([x["차감일수"] for x in comp],
                         [Fraction(1, 3), Fraction(2, 3)])
        display = rows_by_header(Path(result["path"]), "사용상세")
        self.assertEqual([x["차감일수"] for x in display
                          if x["grant_id"] == "C001"],
                         [0.3333333, 0.6666666])

    def test_cancelled_request_reallocates_from_latest_snapshot(self):
        initial = self.run_usage(run_id="original")
        self.assertIn("R-A", [x["request_id"] for x in initial["details"]])
        self._write_approved([
            ["R-C", "E001", "2026-06-01", "대휴", 8],
            ["R-FUT", "E001", "2027-01-15", "연차", 8],
        ])
        updated = self.run_usage(run_id="cancelled")
        self.assertNotIn("R-A", [x["request_id"] for x in updated["details"]])
        by_id = {x["grant_id"]: x for x in updated["expiry"]["entries"]}
        self.assertEqual(by_id["OLD-01"]["expiry_days"], 5)
        self.assertNotIn("R-PRE", [x["request_id"] for x in updated["details"]])

    def test_missing_validity_is_not_fabricated(self):
        self._write_refs(annual_end=None)
        result = self.run_usage(carry=False, closing=None, run_id="missing")
        self.assertTrue(result["issues"])
        self.assertEqual(result["policy"]["계산 상태"], "검토 필요")
        summary = rows_by_header(Path(result["path"]), "사용요약")[0]
        self.assertIsNone(summary["잔여일수"])
        self.assertIn("검토사항", load_workbook(result["path"]).sheetnames)

    def test_rejects_stale_entitlement_and_old_deduction_without_exactness(self):
        with self.assertRaisesRegex(usage.UsageInputError, "기준일"):
            usage.run_usage_ledger(
                as_of_date=date(2026, 11, 18), policy_id="TEST", run_id="stale",
                entitlement_file=self.ent_file, deduction_file=self.deduct_file,
                reference_file=self.refs, output_root=self.out)
        book = load_workbook(self.deduct_file)
        try:
            s = book["차감상세"]
            s.delete_cols(10, 2)
            book.save(self.deduct_file)
        finally:
            book.close()
        with self.assertRaisesRegex(usage.UsageInputError, "필수 열 누락"):
            self.run_usage(carry=False, closing=None, run_id="old-deduction")

    def test_closing_snapshot_zero_id_cannot_be_resurrected(self):
        old = {
            "grant_id": self.grant_id, "employee_id": "E001",
            "leave_type": "연차", "grant_date": "2026-01-01",
            "available_days": "0", "valid_from": "2026-01-01",
            "expires_on": "2027-06-30", "source_ref": "ENT",
        }
        ent_row = {**self.ent_result["details"][0]}
        with self.assertRaisesRegex(ValueError, "Closing에 과거 발생 건 누락"):
            join.combine_grant_sources(
                [ent_row], [], [], carry_rows=[],
                closing_end=date(2026, 6, 30))
        combined = join.combine_grant_sources(
            [ent_row], [], [], carry_rows=[old],
            closing_end=date(2026, 6, 30))
        self.assertEqual(len(combined["grants"]), 1)
        self.assertEqual(combined["grants"][0]["available_days"], Fraction(0))


if __name__ == "__main__":
    unittest.main()
