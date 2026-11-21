"""Canonical Access Events XLSX: vendor-independent shape and module handoff."""
from __future__ import annotations

import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from openpyxl import load_workbook

from bhandara.worktime.access_source import (
    ACCESS_SHEET, EVENT_COLUMNS, CANDIDATE_SHEET, CANDIDATE_COLUMNS, META_SHEET, META_COLUMNS,
    REVIEW_COLUMNS, REVIEW_SHEET, AccessWorkbookError,
    read_access_events_xlsx, write_access_events_xlsx, verify_attendance_xlsx,
)

verification = import_module("bhandara.worktime.attendance-verification")


class AccessExcelContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bhandara-access-xlsx-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def event(self, vendor="SYN_CAPS", event_id="IN1", mode="CLOCK_IN",
              event_time="2026-11-16T09:00", source_row_number=2, **kwargs):
        row = {
            "event_id": event_id, "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16", "event_time": event_time,
            "mode": mode, "direction": "UNKNOWN",
            "auth_status": "SUCCESS", "auth_method": "FINGERPRINT",
            "device_id": "SYN-READER", "source_vendor": vendor,
            "source_ref": "SYNTHETIC-SOURCE", "source_row_number": source_row_number,
        }
        row.update(kwargs)
        return row

    def review(self, vendor="SYN_CAPS", row_number=4):
        return {
            "source_vendor": vendor, "source_row_number": row_number,
            "status": "UNMAPPED", "issue_codes": "UNKNOWN_RAW_CODE",
            "source_ref": "SYNTHETIC-SOURCE", "detail": "Fake vendor code",
        }

    def write(self, name="access-events.xlsx", vendor="SYN_CAPS",
              events=None, reviews=None):
        return write_access_events_xlsx(
            self.root / name,
            [self.event(vendor=vendor),
             self.event(vendor=vendor, event_id="OUT1", mode="CLOCK_OUT",
                        event_time="2026-11-16T18:00", source_row_number=3)]
            if events is None else events,
            [] if reviews is None else reviews,
            source_vendor=vendor,
            source_sha256="a" * 64,
            source_file="synthetic-raw.xlsx",
        )

    def test_stable_columns_and_sheet_order(self):
        path = self.write()
        book = load_workbook(path, read_only=True)
        try:
            self.assertEqual(book.sheetnames, [ACCESS_SHEET, CANDIDATE_SHEET, REVIEW_SHEET, META_SHEET])
            self.assertEqual(tuple(cell.value for cell in book[ACCESS_SHEET][1]), EVENT_COLUMNS)
            self.assertEqual(tuple(cell.value for cell in book[CANDIDATE_SHEET][1]), CANDIDATE_COLUMNS)
            self.assertEqual(tuple(cell.value for cell in book[REVIEW_SHEET][1]), REVIEW_COLUMNS)
            self.assertEqual(tuple(cell.value for cell in book[META_SHEET][1]), META_COLUMNS)
        finally:
            book.close()

    def test_different_vendor_inputs_produce_the_same_schema(self):
        paths = [
            self.write("caps-normalized.xlsx", vendor="SYN_CAPS"),
            self.write("kt-normalized.xlsx", vendor="SYN_KT"),
        ]
        headers = []
        for path in paths:
            book = load_workbook(path, read_only=True)
            try:
                headers.append((book.sheetnames,
                    tuple(cell.value for cell in book[ACCESS_SHEET][1])))
            finally:
                book.close()
        self.assertEqual(headers[0], headers[1])

    def test_read_roundtrip_preserves_origin_row_and_sha(self):
        result = read_access_events_xlsx(self.write())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["events"][0]["source_row_number"], 2)
        self.assertEqual(result["events"][0]["_row_number"], 2)
        self.assertEqual(result["events"][0]["normalized_row_number"], 2)
        self.assertEqual(result["metadata"]["source_sha256"], "a" * 64)
        self.assertEqual(result["metadata"]["timezone"], "Asia/Seoul")
        self.assertEqual(result["schema_version"], "0.2")
        self.assertEqual(result["attendance_candidates"][0]["candidate_status"], "EXPLICIT_PAIR")

    def test_normalized_events_feed_attendance_verification_as_is(self):
        events = read_access_events_xlsx(self.write())["events"]
        ledger = [{
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16",
            "clock_in": "09:00", "clock_out": "18:00",
        }]
        result = verification.verify_attendance(
            ledger, events,
            period_from="2026-11-16", period_to="2026-11-16",
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["rows"][0]["status"], "RECORD_MATCH")

    def test_upstream_unmapped_input_never_disappears(self):
        path = self.write(reviews=[self.review()])
        result = read_access_events_xlsx(path)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["source_reviews"][0]["source_row_number"], 4)
        self.assertEqual(result["source_reviews"][0]["issue_codes"], "UNKNOWN_RAW_CODE")

    def test_unknown_auth_method_is_not_changed_to_fingerprint(self):
        events = [self.event(auth_method="UNKNOWN")]
        path = self.write(events=events)
        result = read_access_events_xlsx(path)
        self.assertEqual(result["events"][0]["auth_method"], "UNKNOWN")
        ledger = [{"employee_id": "E001", "worker_id": "EP0001",
                   "work_date": "2026-11-16", "clock_in": "09:00",
                   "clock_out": "18:00"}]
        checked = verification.verify_attendance(
            ledger, result["events"],
            period_from="2026-11-16", period_to="2026-11-16",
        )
        self.assertEqual(checked["status"], "REVIEW_REQUIRED")
        self.assertIn("EVENT_AUTH_METHOD_UNKNOWN",
                      checked["rows"][0]["review_codes"])

    def test_canonical_excel_tool_handoff_preserves_source_reviews(self):
        path = self.write(reviews=[self.review()])
        ledger = [{
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16",
            "clock_in": "09:00", "clock_out": "18:00",
        }]
        report = verify_attendance_xlsx(
            ledger, path, period_from="2026-11-16",
            period_to="2026-11-16",
        )
        self.assertEqual(report["rows"][0]["status"], "RECORD_MATCH")
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertEqual(report["normalized_source"]["normalized_review_count"], 1)
        self.assertEqual(report["source_issues"][0]["code"], "NORMALIZATION_UNMAPPED")

    def test_canonical_excel_tool_handoff_passes_without_reviews(self):
        ledger = [{
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16",
            "clock_in": "09:00", "clock_out": "18:00",
        }]
        report = verify_attendance_xlsx(
            ledger, self.write(), period_from="2026-11-16",
            period_to="2026-11-16",
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["normalized_source"]["source_vendor"], "SYN_CAPS")

    def test_generic_vendor_access_signed_vs_expected_schedule(self):
        path = self.write(name="expected-delta.xlsx", events=[
            self.event(event_id="FIRST", mode="ACCESS",
                       event_time="2026-11-16T08:40",
                       event_timestamp="2026-11-16T08:40:15",
                       source_row_number=2),
            self.event(event_id="LAST", mode="ACCESS",
                       event_time="2026-11-16T18:16",
                       event_timestamp="2026-11-16T18:16:45",
                       source_row_number=3),
        ])
        ledger = [{
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16", "clock_in": "08:40",
            "clock_out": "18:16", "clock_in_reason": "시차출퇴근",
            "clock_out_reason": "업무 마무리",
        }]
        schedule = [{
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16", "day_type": "WORK",
            "scheduled_start": "09:00", "scheduled_end": "18:00",
        }]
        result = verify_attendance_xlsx(
            ledger, path, period_from="2026-11-16",
            period_to="2026-11-16", schedule_rows=schedule,
        )
        deviation = result["rows"][0]["time_deviations"]
        self.assertEqual(deviation["clock_in"]["ledger_vs_expected"]["delta_minutes"], -20)
        self.assertEqual(deviation["clock_out"]["ledger_vs_expected"]["delta_minutes"], 16)
        self.assertEqual(deviation["clock_in"]["device_vs_expected"]["delta_seconds"], -1185)
        self.assertEqual(deviation["clock_out"]["device_vs_expected"]["delta_seconds"], 1005)
        self.assertEqual(deviation["clock_in"]["device_origin"], "UNCONFIRMED_ACCESS_CANDIDATE")
        self.assertFalse(deviation["clock_in"]["device_confirmed_as_work"])
        self.assertEqual(result["rows"][0]["status"], "ACCESS_ONLY")

    def test_writer_rejects_unsupported_raw_vendor_code(self):
        with self.assertRaises(AccessWorkbookError):
            self.write(events=[self.event(mode="LEGACY_CODE_123")])

    def test_writer_requires_unambiguous_source_identity(self):
        with self.assertRaises(AccessWorkbookError):
            self.write(events=[self.event(worker_id="")])
        with self.assertRaises(AccessWorkbookError):
            self.write(events=[self.event(event_time="09:00")])

    def test_duplicate_event_id_rejected_not_deduplicated(self):
        with self.assertRaises(AccessWorkbookError):
            self.write(events=[self.event(), self.event(source_row_number=3)])

    def test_existing_output_never_overwritten(self):
        self.write()
        with self.assertRaises(AccessWorkbookError):
            self.write()

    def test_empty_source_needs_explicit_review(self):
        with self.assertRaises(AccessWorkbookError):
            self.write(events=[], reviews=[])
        path = self.write(events=[], reviews=[self.review()])
        result = read_access_events_xlsx(path)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["events"], [])

    def test_formula_injected_in_workbook_is_rejected(self):
        path = self.write()
        book = load_workbook(path)
        try:
            book[ACCESS_SHEET]["A2"] = "=2+2"
            book.save(path)
        finally:
            book.close()
        with self.assertRaises(AccessWorkbookError):
            read_access_events_xlsx(path)

    def test_metadata_tampering_is_rejected(self):
        path = self.write()
        book = load_workbook(path)
        try:
            book[META_SHEET]["B6"] = "999"
            book.save(path)
        finally:
            book.close()
        with self.assertRaises(AccessWorkbookError):
            read_access_events_xlsx(path)

    def test_only_generic_access_produces_first_and_last_candidates(self):
        path = self.write(events=[
            self.event(event_id="middle", mode="ACCESS",
                       event_time="2026-11-16T12:00", source_row_number=2,
                       event_timestamp="2026-11-16T12:00:45"),
            self.event(event_id="first", mode="ACCESS",
                       event_time="2026-11-16T08:50", source_row_number=3,
                       event_timestamp="2026-11-16T08:50:11"),
            self.event(event_id="last", mode="ACCESS",
                       event_time="2026-11-16T18:10", source_row_number=4,
                       event_timestamp="2026-11-16T18:10:59"),
        ])
        data = read_access_events_xlsx(path)
        candidate = data["attendance_candidates"][0]
        self.assertEqual(candidate["arrival_time"], "2026-11-16T08:50:11")
        self.assertEqual(candidate["departure_time"], "2026-11-16T18:10:59")
        self.assertEqual(candidate["candidate_status"], "INFERRED_PAIR")
        self.assertFalse(candidate["confirmed"])

    def test_clock_in_without_clock_out_uses_last_successful_access(self):
        path = self.write(name="clock-in-access.xlsx", events=[
            self.event(event_id="late", mode="ACCESS",
                       event_time="2026-11-16T18:15",
                       source_row_number=2),
            self.event(event_id="in", mode="CLOCK_IN",
                       event_time="2026-11-16T09:00",
                       source_row_number=3),
            self.event(event_id="outing", mode="OUTING",
                       event_time="2026-11-16T19:40",
                       source_row_number=4),
            self.event(event_id="return", mode="RETURN",
                       event_time="2026-11-16T20:30",
                       source_row_number=5),
            self.event(event_id="failed", mode="ACCESS", auth_status="FAILED",
                       event_time="2026-11-16T23:00",
                       source_row_number=6),
        ])
        c = read_access_events_xlsx(path)["attendance_candidates"][0]
        self.assertEqual(c["arrival_time"], "2026-11-16T09:00:00")
        self.assertEqual(c["departure_time"], "2026-11-16T18:15:00")
        self.assertEqual(c["arrival_basis"], "EXPLICIT_CLOCK_IN")
        self.assertEqual(c["departure_basis"], "INFERRED_LAST_ACCESS")
        self.assertEqual(c["candidate_status"], "PARTIAL_EXPLICIT")
        self.assertEqual(c["evidence_event_ids"], "in,late")
        self.assertFalse(c["confirmed"])

    def test_clock_out_without_clock_in_uses_first_successful_access(self):
        path = self.write(name="access-clock-out.xlsx", events=[
            self.event(event_id="out", mode="CLOCK_OUT",
                       event_time="2026-11-16T18:00", source_row_number=2),
            self.event(event_id="middle", mode="ACCESS",
                       event_time="2026-11-16T12:00", source_row_number=3),
            self.event(event_id="first", mode="ACCESS",
                       event_time="2026-11-16T08:40", source_row_number=4),
        ])
        c = read_access_events_xlsx(path)["attendance_candidates"][0]
        self.assertEqual(c["arrival_time"], "2026-11-16T08:40:00")
        self.assertEqual(c["departure_time"], "2026-11-16T18:00:00")
        self.assertEqual(c["arrival_basis"], "INFERRED_FIRST_ACCESS")
        self.assertEqual(c["departure_basis"], "EXPLICIT_CLOCK_OUT")
        self.assertEqual(c["candidate_status"], "PARTIAL_EXPLICIT")
        self.assertEqual(c["evidence_event_ids"], "first,out")

    def test_single_access_not_reused_and_device_direction_is_respected(self):
        one = self.write(name="single-access.xlsx", events=[
            self.event(event_id="solo", mode="ACCESS",
                       event_time="2026-11-16T09:00"),
        ])
        c = read_access_events_xlsx(one)["attendance_candidates"][0]
        self.assertEqual(c["arrival_basis"], "INFERRED_FIRST_ACCESS")
        self.assertEqual(c["departure_basis"], "MISSING")
        self.assertEqual(c["departure_time"], "")
        known_in = self.write(name="entrance-only.xlsx", events=[
            self.event(event_id="morning", mode="ACCESS", direction="IN",
                       event_time="2026-11-16T09:00", source_row_number=2),
            self.event(event_id="evening", mode="ACCESS", direction="IN",
                       event_time="2026-11-16T18:00", source_row_number=3),
        ])
        c = read_access_events_xlsx(known_in)["attendance_candidates"][0]
        self.assertEqual(c["arrival_basis"], "INFERRED_FIRST_ACCESS")
        self.assertEqual(c["departure_basis"], "MISSING")
        known_out = self.write(name="exit-only.xlsx", events=[
            self.event(event_id="a", mode="ACCESS", direction="OUT",
                       event_time="2026-11-16T09:00", source_row_number=2),
            self.event(event_id="b", mode="ACCESS", direction="OUT",
                       event_time="2026-11-16T18:00", source_row_number=3),
        ])
        c = read_access_events_xlsx(known_out)["attendance_candidates"][0]
        self.assertEqual(c["arrival_basis"], "MISSING")
        self.assertEqual(c["departure_basis"], "MISSING")

    def test_multiple_explicit_punches_choose_boundary_but_remain_review(self):
        path = self.write(name="multi-explicit.xlsx", events=[
            self.event(event_id="in-late", mode="CLOCK_IN",
                       event_time="2026-11-16T09:10", source_row_number=2),
            self.event(event_id="in-early", mode="CLOCK_IN",
                       event_time="2026-11-16T08:55", source_row_number=3),
            self.event(event_id="out-early", mode="CLOCK_OUT",
                       event_time="2026-11-16T17:50", source_row_number=4),
            self.event(event_id="out-late", mode="CLOCK_OUT",
                       event_time="2026-11-16T18:20", source_row_number=5),
        ])
        c = read_access_events_xlsx(path)["attendance_candidates"][0]
        self.assertEqual(c["arrival_time"], "2026-11-16T08:55:00")
        self.assertEqual(c["departure_time"], "2026-11-16T18:20:00")
        self.assertEqual(c["candidate_status"], "MULTIPLE_EXPLICIT_REVIEW")
        self.assertEqual(len(c["evidence_event_ids"].split(",")), 4)
        self.assertFalse(c["confirmed"])

    def test_outing_return_disarm_unknown_and_failed_cannot_make_commute(self):
        path = self.write(name="auxiliary-events.xlsx", events=[
            self.event(event_id="leave", mode="OUTING",
                       event_time="2026-11-16T08:00", source_row_number=2),
            self.event(event_id="back", mode="RETURN",
                       event_time="2026-11-16T18:00", source_row_number=3),
            self.event(event_id="disarm", mode="DISARM",
                       event_time="2026-11-16T07:00", source_row_number=4),
            self.event(event_id="unknown", mode="UNKNOWN",
                       event_time="2026-11-16T19:00", source_row_number=5),
            self.event(event_id="failed", mode="ACCESS", auth_status="FAILED",
                       event_time="2026-11-16T20:00", source_row_number=6),
            self.event(event_id="unverified", mode="ACCESS", auth_status="UNKNOWN",
                       event_time="2026-11-16T21:00", source_row_number=7),
        ])
        result = read_access_events_xlsx(path)
        self.assertEqual(len(result["events"]), 6)
        c = result["attendance_candidates"][0]
        self.assertEqual(c["candidate_status"], "NO_ATTENDANCE_CANDIDATE")
        self.assertEqual(c["arrival_time"], "")
        self.assertEqual(c["departure_time"], "")
        self.assertEqual(c["evidence_event_ids"], "")

    def test_source_exclusions_do_not_block_normalized_success(self):
        excluded = self.review()
        excluded["status"] = "EXCLUDED"
        excluded["issue_codes"] = "SECURITY_SET_EXCLUDED"
        path = self.write(reviews=[excluded])
        normalized = read_access_events_xlsx(path)
        self.assertEqual(normalized["status"], "PASS")
        ledger = [{"employee_id": "E001", "worker_id": "EP0001",
                   "work_date": "2026-11-16", "clock_in": "09:00",
                   "clock_out": "18:00"}]
        handoff = verify_attendance_xlsx(
            ledger, path, period_from="2026-11-16", period_to="2026-11-16",
        )
        self.assertEqual(handoff["status"], "PASS")
        self.assertEqual(handoff["normalized_source"]["excluded_count"], 1)

    def test_candidate_tampering_fails_closed(self):
        path = self.write()
        book = load_workbook(path)
        try:
            book[CANDIDATE_SHEET]["D2"] = "2026-11-16T05:30:00"
            book.save(path)
        finally:
            book.close()
        with self.assertRaises(AccessWorkbookError):
            read_access_events_xlsx(path)

    def test_reader_rejects_unknown_sheet_schema(self):
        path = self.write()
        book = load_workbook(path)
        try:
            book[ACCESS_SHEET]["A1"] = "vendor_personnel_no"
            book.save(path)
        finally:
            book.close()
        with self.assertRaises(AccessWorkbookError):
            read_access_events_xlsx(path)


if __name__ == "__main__":
    unittest.main()
