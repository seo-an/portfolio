"""Synthetic tests for Common PERSON MAP and the Worktime vendor bridge."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from bhandara.common.io.input_layout import InputLayoutError
from bhandara.common.io.security_person_map import read_security_person_map
from bhandara.worktime.access_source import read_access_events_xlsx
from bhandara.worktime.vendor_adapters import normalize_vendor_excel


PERSON_HEADERS = [
    "employee_id", "name", "security_department_id", "security_id",
    "worker_id", "payroll_id", "security_person_id", "main_area",
]
PERSONS = [
    ["E001", "동명이", "1001", "CAPS", "W001", "P001", "001", "a0001"],
    ["E002", "동명이", "1002", "CAPS", "W002", "P002", "001", None],
    ["E001", "동명이", "1001", "SECOM", "W001", "P001", "9001", "a0001"],
    ["E003", "예시삼", "2601", "SECOM", "W003", "P003", "003", None],
]


def _write_map(
    path: Path, persons: list[list] | None = None,
    departments: list[list] | None = None,
) -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "PERSON MAP"
    sheet.append(PERSON_HEADERS + ["user_extra_column"])
    for row in persons if persons is not None else PERSONS:
        sheet.append(list(row) + ["extra value ignored"])
    dep = book.create_sheet("DEPARTMENT MAP")
    dep.append(["department", "security_department_id"])
    for row in departments if departments is not None else [
        ["R&D", "1001"], ["Sales", "1002"], ["HR", "2601"]
    ]:
        dep.append(row)
    area = book.create_sheet("AREA Map")
    area.append(["area", "security_area_id"])
    area.append(["본관", "a0001"])
    try:
        book.save(path)
    finally:
        book.close()


def _write_secom(path: Path) -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "기록"
    sheet.append(["사번", "성명", "부서", "출입구명", "일시", "인증방식"])
    sheet.append(["9001", "동명이", "R&D", "테스트출입구", "2026-11-19 09:00:13", "지문"])
    sheet.append(["9001", "동명이", "R&D", "테스트출입구", "2026-11-19 18:00:20", "지문"])
    try:
        book.save(path)
    finally:
        book.close()


class SecurityPersonMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="bhandara-person-map-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.mapping = self.root / "id-map.xlsx"
        _write_map(self.mapping)

    def test_one_employee_may_have_one_row_per_vendor(self):
        caps = read_security_person_map(self.mapping, vendor="CAPS")
        self.assertEqual(caps["employee_count"], 3)
        self.assertEqual(len(caps["identities"]), 2)
        self.assertEqual({r["employee_id"] for r in caps["identities"]}, {"E001", "E002"})
        self.assertEqual({r["employee_number"] for r in caps["identities"]}, {"001"})
        self.assertEqual({r["department"] for r in caps["identities"]}, {"R&D", "Sales"})
        self.assertEqual(caps["issues"], [])

        secom = read_security_person_map(self.mapping, vendor="secom")
        self.assertEqual(len(secom["identities"]), 2)
        self.assertEqual(
            {r["employee_id"]: r["employee_number"] for r in secom["identities"]},
            {"E001": "9001", "E003": "003"},
        )
        self.assertEqual(secom["issues"], [])

    def test_extra_columns_are_ignored(self):
        caps = read_security_person_map(self.mapping, vendor="caps")
        self.assertNotIn("user_extra_column", caps["identities"][0])

    def test_unsupported_extra_column_formula_is_not_read(self):
        from openpyxl import load_workbook
        book = load_workbook(self.mapping)
        try:
            book["PERSON MAP"]["I2"] = "=1/0"
            book.save(self.mapping)
        finally:
            book.close()
        result = read_security_person_map(self.mapping, vendor="CAPS")
        self.assertEqual(len(result["identities"]), 2)

    def test_formula_in_supported_field_is_rejected(self):
        from openpyxl import load_workbook
        book = load_workbook(self.mapping)
        try:
            book["PERSON MAP"]["G2"] = "=1+1"
            book.save(self.mapping)
        finally:
            book.close()
        with self.assertRaisesRegex(InputLayoutError, "formula in supported column"):
            read_security_person_map(self.mapping, vendor="CAPS")

    def test_vendor_repeated_across_people_is_valid(self):
        result = read_security_person_map(self.mapping, vendor="CAPS")
        self.assertEqual(len(result["identities"]), 2)

    def test_person_and_worker_must_be_consistent_across_vendors(self):
        persons = [list(p) for p in PERSONS]
        persons[2][4] = "WRONG"
        _write_map(self.mapping, persons=persons)
        with self.assertRaisesRegex(InputLayoutError, "conflicting identities"):
            read_security_person_map(self.mapping, vendor="CAPS")

    def test_same_employee_and_vendor_twice_is_rejected(self):
        persons = [list(p) for p in PERSONS]
        persons.append(["E001", "동명이", "1002", "CAPS", "W001", "P001", "099", None])
        _write_map(self.mapping, persons=persons)
        with self.assertRaisesRegex(InputLayoutError, "duplicate employee and security vendor"):
            read_security_person_map(self.mapping, vendor="CAPS")

    def test_same_vendor_department_person_cannot_belong_to_two_employees(self):
        persons = [list(p) for p in PERSONS]
        persons[1][2] = "1001"
        _write_map(self.mapping, persons=persons)
        with self.assertRaisesRegex(InputLayoutError, "duplicate vendor/department/person key"):
            read_security_person_map(self.mapping, vendor="CAPS")

    def test_incomplete_department_is_reviewed_only_for_selected_vendor(self):
        _write_map(self.mapping, departments=[
            ["R&D", "1001"], ["Sales", "1002"], [None, "2601"]
        ])
        caps = read_security_person_map(self.mapping, vendor="CAPS")
        self.assertEqual(caps["issues"], [])
        secom = read_security_person_map(self.mapping, vendor="SECOM")
        self.assertEqual(len(secom["identities"]), 1)
        self.assertIn("SECURITY_DEPARTMENT_UNMAPPED",
                      {x["code"] for x in secom["issues"]})

    def test_missing_pair_does_not_get_invented(self):
        persons = [list(p) for p in PERSONS]
        persons[3][6] = None
        _write_map(self.mapping, persons=persons)
        result = read_security_person_map(self.mapping, vendor="SECOM")
        self.assertEqual(len(result["identities"]), 1)
        self.assertIn("SECURITY_PERSON_KEY_MISSING",
                      {x["code"] for x in result["issues"]})

    def test_telecop_alias(self):
        persons = [list(p) for p in PERSONS]
        persons[3][3] = "telecop"
        _write_map(self.mapping, persons=persons)
        result = read_security_person_map(self.mapping, vendor="KT_TELECOP")
        self.assertEqual(result["vendor"], "KT_TELECOP")
        self.assertEqual(result["identities"][0]["employee_id"], "E003")

    def test_worktime_vendor_adapter_reads_common_workbook(self):
        source = self.root / "vendor.xlsx"
        output = self.root / "access-events.xlsx"
        _write_secom(source)
        report = normalize_vendor_excel(
            source, output, vendor="SECOM",
            sheet_name="기록", id_map_path=self.mapping,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["normalized_events"], 2)
        self.assertEqual(report["identity_mapping_reviews"], [])
        standardized = read_access_events_xlsx(output)
        self.assertEqual(len(standardized["events"]), 2)
        self.assertEqual({row["employee_id"] for row in standardized["events"]}, {"E001"})
        self.assertEqual({row["worker_id"] for row in standardized["events"]}, {"W001"})


if __name__ == "__main__":
    unittest.main()
