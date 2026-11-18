"""Synthetic profiles modeled after the user-supplied CAPS/SECOM/KT sample.

No employee names/identifiers from the supplied workbook are checked into Git.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from bhandara.worktime.access_source import (
    ACCESS_SHEET, CANDIDATE_SHEET, EVENT_COLUMNS, CANDIDATE_COLUMNS,
    read_access_events_xlsx, verify_attendance_xlsx,
)
from bhandara.worktime.vendor_adapters import (
    PROFILES, VendorSourceError, normalize_vendor_excel, normalize_vendor_rows,
)


class VendorAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-security-adapter-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identities = [
            {"department": "R&D", "employee_number": "001",
             "employee_id": "E001", "worker_id": "W001", "name": "동명이"},
            {"department": "Sales", "employee_number": "001",
             "employee_id": "E002", "worker_id": "W002", "name": "동명이"},
            {"department": "HR", "employee_number": "2601",
             "employee_id": "E003", "worker_id": "W003", "name": "예시삼"},
            {"department": "Design", "employee_number": "2605",
             "employee_id": "E004", "worker_id": "W004", "name": "예시사"},
        ]

    def caps(self, employee_number="001", department="R&D",
             name="동명이", stamp="09:00:13", mode="출입", row_number=2):
        return {
            "사원번호": employee_number, "성명": name, "부서": department,
            "일자": "2026-11-16", "시간": stamp,
            "단말기명": "Synthetic Gate", "상태": mode,
            "_row_number": row_number,
        }

    def secom(self, stamp="2026-11-16 09:00:13", method="지문",
              name="예시삼", row_number=2, **extras):
        return {
            "카드번호": 100001, "사번": 2601,
            "성명": name, "부서": "HR", "일시": stamp,
            "출입구명": "Synthetic Reader", "인증방식": method,
            "_row_number": row_number, **extras,
        }

    def kt(self, stamp="2026-11-16 오전 08:50:33",
           method="지문", row_number=2, **extras):
        return {
            "순번": row_number - 1, "사번": 2605,
            "이름": "예시사", "부서": "Design", "일시": stamp,
            "장치명": "Synthetic Gate", "인증구분": method,
            "_row_number": row_number, **extras,
        }

    def normalize(self, vendor, rows, identities=None):
        return normalize_vendor_rows(
            rows, vendor=vendor,
            identities=self.identities if identities is None else identities,
            source_ref="SYNTHETIC-RAW",
        )

    def write_source(self, vendor, rows, sheet_name="원본기록"):
        path = self.root / f"{vendor}-source.xlsx"
        book = Workbook()
        try:
            sheet = book.active
            sheet.title = sheet_name
            profile = PROFILES[vendor]
            headers = list(profile.required)
            if rows:
                headers += [key for key in rows[0]
                            if key not in headers and not key.startswith("_")]
            sheet.append(headers)
            for row in rows:
                sheet.append([row.get(key) for key in headers])
            book.save(path)
        finally:
            book.close()
        return path

    def run_file(self, vendor, rows):
        source = self.write_source(vendor, rows)
        output = self.root / f"{vendor}-standard.xlsx"
        status = normalize_vendor_excel(
            source, output,
            vendor=vendor, identities=self.identities,
            sheet_name="원본기록",
        )
        return status, read_access_events_xlsx(output)

    def test_profiles_covered_by_uploaded_three_vendor_headers(self):
        self.assertEqual(set(PROFILES), {"CAPS", "SECOM", "KT_TELECOP"})
        self.assertEqual(PROFILES["CAPS"].mode_column, "상태")
        self.assertEqual(PROFILES["SECOM"].auth_method_column, "인증방식")
        self.assertEqual(PROFILES["KT_TELECOP"].auth_method_column, "인증구분")

    def test_caps_explicit_clock_and_rest_modes_are_separate(self):
        rows = [
            self.caps(mode="출근(인증)", row_number=2),
            self.caps(mode="외출", stamp="12:04:20", row_number=3),
            self.caps(mode="복귀", stamp="12:58:19", row_number=4),
            self.caps(mode="퇴근(인증)", stamp="18:02:01", row_number=5),
        ]
        _, normalized = self.run_file("CAPS", rows)
        self.assertEqual([r["mode"] for r in normalized["events"]],
                         ["CLOCK_IN", "OUTING", "RETURN", "CLOCK_OUT"])
        c = normalized["attendance_candidates"][0]
        self.assertEqual(c["candidate_status"], "EXPLICIT_PAIR")
        self.assertEqual(c["arrival_time"], "2026-11-16T09:00:13")
        self.assertEqual(c["departure_time"], "2026-11-16T18:02:01")
        self.assertFalse(c["confirmed"])
        self.assertEqual(normalized["events"][0]["auth_method"], "UNKNOWN")

    def test_security_set_and_failed_auth_excluded_even_at_bounds(self):
        rows = [
            self.caps(mode="세트(경비시작)", stamp="07:00:10", row_number=2),
            self.caps(mode="출입", stamp="08:52:11", row_number=3),
            self.caps(mode="출입", stamp="18:05:30", row_number=4),
            self.caps(mode="인식실패", stamp="23:59:59", row_number=5),
        ]
        status, normalized = self.run_file("CAPS", rows)
        self.assertEqual(status["excluded"], 2)
        self.assertEqual(status["status"], "PASS")
        self.assertEqual(normalized["status"], "PASS")
        self.assertEqual(len(normalized["events"]), 2)
        self.assertEqual([x["status"] for x in normalized["source_reviews"]],
                         ["EXCLUDED", "EXCLUDED"])
        candidate = normalized["attendance_candidates"][0]
        self.assertEqual(candidate["arrival_time"], "2026-11-16T08:52:11")
        self.assertEqual(candidate["departure_time"], "2026-11-16T18:05:30")

    def test_department_and_number_disambiguate_same_name(self):
        rows = [
            self.caps(department="R&D", employee_number="001",
                      stamp="09:00:00", row_number=2),
            self.caps(department="R&D", employee_number="001",
                      stamp="18:00:00", row_number=3),
            self.caps(department="Sales", employee_number="001",
                      stamp="08:30:00", row_number=4),
            self.caps(department="Sales", employee_number="001",
                      stamp="17:30:00", row_number=5),
        ]
        _, normalized = self.run_file("CAPS", rows)
        candidate = normalized["attendance_candidates"]
        self.assertEqual(len(candidate), 2)
        self.assertEqual({x["employee_id"] for x in candidate}, {"E001", "E002"})
        self.assertEqual({x["worker_id"] for x in candidate}, {"W001", "W002"})

    def test_secom_two_fingerprint_events_are_inferred_not_approved(self):
        rows = [
            self.secom(stamp="2026-11-16 08:45:12", row_number=2),
            self.secom(stamp="2026-11-16 18:32:01", row_number=3),
        ]
        _, normalized = self.run_file("SECOM", rows)
        self.assertEqual([r["mode"] for r in normalized["events"]], ["ACCESS", "ACCESS"])
        self.assertTrue(all(r["auth_method"] == "FINGERPRINT"
                            for r in normalized["events"]))
        self.assertEqual(normalized["attendance_candidates"][0]["candidate_status"],
                         "INFERRED_PAIR")
        self.assertFalse(normalized["attendance_candidates"][0]["confirmed"])

    def test_kt_korean_am_pm_and_seconds_preserved(self):
        rows = [
            self.kt(stamp="2026-11-16 오전 08:50:33", row_number=2),
            self.kt(stamp="2026-11-16 오후 06:10:45", row_number=3),
        ]
        _, normalized = self.run_file("KT_TELECOP", rows)
        self.assertEqual(normalized["events"][1]["event_time"], "2026-11-16T18:10")
        self.assertEqual(normalized["events"][1]["event_timestamp"],
                         "2026-11-16T18:10:45")
        self.assertEqual(normalized["attendance_candidates"][0]["departure_time"],
                         "2026-11-16T18:10:45")

    def test_kt_noon_and_midnight(self):
        rows = [
            self.kt(stamp="2026-11-16 오전 12:10:00", row_number=2),
            self.kt(stamp="2026-11-16 오후 12:10:00", row_number=3),
        ]
        events, _ = self.normalize("KT_TELECOP", rows)
        self.assertEqual(events[0]["event_timestamp"], "2026-11-16T00:10:00")
        self.assertEqual(events[1]["event_timestamp"], "2026-11-16T12:10:00")

    def test_first_last_chronological_not_sheet_order(self):
        events, _ = self.normalize("SECOM", [
            self.secom(stamp="2026-11-16 18:15:45", row_number=2),
            self.secom(stamp="2026-11-16 08:30:11", row_number=3),
            self.secom(stamp="2026-11-16 12:15:20", row_number=4),
        ])
        from bhandara.worktime.access_source import _candidates
        c = _candidates(events)[0]
        self.assertEqual(c["arrival_time"], "2026-11-16T08:30:11")
        self.assertEqual(c["departure_time"], "2026-11-16T18:15:45")

    def test_one_access_is_single_candidate_without_departure(self):
        _, normalized = self.run_file("SECOM", [self.secom()])
        c = normalized["attendance_candidates"][0]
        self.assertEqual(c["candidate_status"], "SINGLE_ACCESS")
        self.assertEqual(c["departure_time"], "")

    def test_partial_explicit_does_not_borrow_generic_access(self):
        rows = [
            self.caps(mode="출근(인증)", row_number=2),
            self.caps(mode="출입", stamp="18:10:00", row_number=3),
        ]
        _, normalized = self.run_file("CAPS", rows)
        c = normalized["attendance_candidates"][0]
        self.assertEqual(c["candidate_status"], "PARTIAL_EXPLICIT")
        self.assertEqual(c["departure_time"], "")

    def test_outing_return_alone_do_not_generate_clock_candidates(self):
        rows = [
            self.caps(mode="외출", stamp="12:00:00", row_number=2),
            self.caps(mode="복귀", stamp="12:30:00", row_number=3),
        ]
        _, normalized = self.run_file("CAPS", rows)
        c = normalized["attendance_candidates"][0]
        self.assertEqual(c["candidate_status"], "NO_ATTENDANCE_CANDIDATE")

    def test_failure_in_secom_auth_method_is_excluded(self):
        rows = [
            self.secom(stamp="2026-11-16 07:00:00",
                       method="인식실패", row_number=2),
            self.secom(stamp="2026-11-16 09:00:00",
                       method="지문", row_number=3),
            self.secom(stamp="2026-11-16 18:00:00",
                       method="지문", row_number=4),
        ]
        _, normalized = self.run_file("SECOM", rows)
        self.assertEqual(len(normalized["events"]), 2)
        self.assertEqual(normalized["source_reviews"][0]["status"], "EXCLUDED")
        self.assertEqual(normalized["attendance_candidates"][0]["arrival_time"],
                         "2026-11-16T09:00:00")

    def test_unknown_raw_mode_does_not_become_access(self):
        events, reviews = self.normalize("CAPS", [
            self.caps(mode="업체미정의코드", row_number=2),
        ])
        self.assertEqual(events, [])
        self.assertEqual(reviews[0]["status"], "REVIEW_REQUIRED")

    def test_unmapped_department_number_is_not_guessed_by_name(self):
        events, reviews = self.normalize("CAPS", [
            self.caps(department="Sales", employee_number="999",
                      row_number=2),
        ])
        self.assertEqual(events, [])
        self.assertEqual(reviews[0]["issue_codes"],
                         "DEPARTMENT_EMPLOYEE_NUMBER_UNMAPPED")

    def test_identity_name_conflict_is_reviewed(self):
        events, reviews = self.normalize("CAPS", [
            self.caps(name="다른이름", row_number=2),
        ])
        self.assertEqual(events, [])
        self.assertEqual(reviews[0]["issue_codes"], "EMPLOYEE_NAME_CONFLICT")

    def test_duplicate_dept_number_mapping_is_rejected(self):
        with self.assertRaises(VendorSourceError):
            self.normalize("CAPS", [self.caps()],
                           identities=self.identities + [self.identities[0]])

    def test_unknown_auth_method_does_not_become_fingerprint(self):
        _, normalized = self.run_file("SECOM", [
            self.secom(method="신규인증방식", row_number=2),
        ])
        self.assertEqual(normalized["events"][0]["auth_method"], "UNKNOWN")
        self.assertEqual(normalized["source_reviews"][0]["issue_codes"],
                         "AUTH_METHOD_UNMAPPED")
        self.assertEqual(normalized["status"], "REVIEW_REQUIRED")

    def test_vendor_profiles_produce_identical_excel_columns(self):
        samples = {
            "CAPS": [self.caps(), self.caps(stamp="18:00:00", row_number=3)],
            "SECOM": [self.secom(), self.secom(stamp="2026-11-16 18:00:00", row_number=3)],
            "KT_TELECOP": [self.kt(), self.kt(stamp="2026-11-16 오후 06:00:00", row_number=3)],
        }
        from openpyxl import load_workbook
        headers = []
        for vendor, rows in samples.items():
            status, normalized = self.run_file(vendor, rows)
            self.assertEqual(status["normalized_events"], 2)
            book = load_workbook(status["output_path"], read_only=True)
            try:
                headers.append((
                    tuple(book.sheetnames),
                    tuple(cell.value for cell in book[ACCESS_SHEET][1]),
                    tuple(cell.value for cell in book[CANDIDATE_SHEET][1]),
                ))
            finally:
                book.close()
        self.assertEqual(headers[0], headers[1])
        self.assertEqual(headers[0], headers[2])
        self.assertEqual(headers[0][1], EVENT_COLUMNS)
        self.assertEqual(headers[0][2], CANDIDATE_COLUMNS)

    def test_standard_excel_is_consumable_by_attendance_module(self):
        status, normalized = self.run_file("CAPS", [
            self.caps(mode="출근(인증)", row_number=2),
            self.caps(mode="퇴근(인증)", stamp="18:00:00", row_number=3),
        ])
        ledger = [{
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16",
            "clock_in": "09:00", "clock_out": "18:00",
        }]
        result = verify_attendance_xlsx(
            ledger, status["output_path"],
            period_from="2026-11-16", period_to="2026-11-16",
        )
        self.assertEqual(len(result["attendance_candidates"]), 1)
        self.assertEqual(result["attendance_candidates"][0]["candidate_status"],
                         "EXPLICIT_PAIR")
        # CAPS sample does not supply authentication *method*, so no false
        # fingerprint verification is permitted even with an explicit clock mode.
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_documented_optional_secom_status_column_is_obeyed(self):
        events, reviews = self.normalize("SECOM", [
            self.secom(row_number=2, 구분="출근"),
            self.secom(stamp="2026-11-16 18:00:00",
                       row_number=3, 구분="퇴근"),
        ])
        self.assertFalse(reviews)
        self.assertEqual([row["mode"] for row in events],
                         ["CLOCK_IN", "CLOCK_OUT"])

    def test_invalid_kt_am_pm_marked_for_review(self):
        events, reviews = self.normalize("KT_TELECOP", [
            self.kt(stamp="2026-11-16 오후 13:30:00", row_number=2),
        ])
        self.assertEqual(events, [])
        self.assertEqual(reviews[0]["status"], "REVIEW_REQUIRED")

    def test_existing_output_never_overwritten(self):
        rows = [self.secom(), self.secom(stamp="2026-11-16 18:00:00", row_number=3)]
        self.run_file("SECOM", rows)
        with self.assertRaises(ValueError):
            self.run_file("SECOM", rows)


if __name__ == "__main__":
    unittest.main()
