"""CAPS-neutral Worktime break review contracts. All input data is synthetic."""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[2]
reviewer = importlib.import_module("bhandara.worktime-calculator.break_review")
batch = importlib.import_module("bhandara.worktime-calculator.functions.worktime_batch")


def synthetic_bundle(events=None, *, break_min=60, day="2026-11-13"):
    if events is None:
        events = []
    def source(rows, label):
        return {
            "rows": rows, "source_sha256": "synthetic-" + label,
            "lineage": [
                {"status": "ACCEPTED", "row_number": i + 2, "issue_codes": []}
                for i in range(len(rows))
            ],
        }
    return {
        "schema_version": "0.1", "batch_id": "synthetic-caps-break",
        "status": "READY_FOR_CALCULATION",
        "sources": {
            "employees": source(
                [{"employee_id": "E001", "worker_id": "EP0001"}], "employees"),
            "schedule": source([{
                "employee_id": "E001", "worker_id": "EP0001",
                "work_date": day, "day_type": "WORK",
                "scheduled_start": "09:00", "scheduled_end": "18:00",
                "break_min": 60, "break_start": "12:00", "break_end": "13:00",
                "scheduled_work_hours": 8,
            }], "schedule"),
            "attendance": source([{
                "employee_id": "E001", "worker_id": "EP0001",
                "work_date": day, "clock_in": "09:00", "clock_out": "18:00",
                "break_min": break_min, "source": "SYNTHETIC_CAPS",
            }], "attendance"),
            "access_events": source(events, "access-events"),
        },
    }


def evt(event_id, at, direction, *, category=None,
        verified=False, ref=None, day="2026-11-13"):
    return {
        "employee_id": "E001", "worker_id": "EP0001", "work_date": day,
        "event_id": event_id, "event_time": at, "direction": direction,
        "classification": category or "UNKNOWN",
        "free_use_confirmed": verified, "verification_ref": ref,
    }


def settings(day="2026-11-13", **kwargs):
    return {
        "schema_version": "0.1", "period_from": day, "period_to": day,
        "worktime_assignments": {
            "E001": {"worktime_system": "standard",
                     "rule_ref": "labor_standard_50_53"},
        },
        "approvals": [],
        **kwargs,
    }


def calculate(bundle, config):
    return batch.calculate_worktime_batch(bundle, config)


class AccessBreakReviewTests(unittest.TestCase):
    def assess(self, events, *, config=None, break_min=60, day="2026-11-13"):
        bundle = synthetic_bundle(events, break_min=break_min, day=day)
        cfg = config or settings(day=day)
        report = reviewer.analyze_access_breaks(bundle, cfg, calculate(bundle, cfg))
        return report["rows"][0], report

    def test_planned_break_exit_is_only_candidate_not_proof(self):
        row, report = self.assess([
            evt("in", "09:00", "IN"), evt("exit", "12:05", "OUT"),
            evt("entry", "12:55", "IN"), evt("out", "18:00", "OUT"),
        ])
        self.assertEqual(row["event_intervals"][0]["classification"],
                         "PLANNED_BREAK_CANDIDATE")
        self.assertEqual(row["verified_rest_min"], 0)
        self.assertIsNone(row["confirmed_shortfall_min"])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertEqual(report["access_events_sha256"], "synthetic-access-events")

    def test_verified_rest_sixty_meets_eight_hour_minimum(self):
        row, _ = self.assess([
            evt("exit", "12:00", "OUT", category="REST_CONFIRMED",
                verified=True, ref="HR-EVIDENCE-1"),
            evt("entry", "13:00", "IN"),
        ])
        self.assertEqual(row["verified_rest_min"], 60)
        self.assertEqual(row["required_break_min"], 60)
        self.assertEqual(row["status"], "PASS_VERIFIED")

    def test_business_trip_does_not_debit_break(self):
        row, _ = self.assess([
            evt("e1", "12:00", "OUT", category="REST_CONFIRMED",
                verified=True, ref="HR-EVIDENCE-1"),
            evt("i1", "13:00", "IN"),
            evt("e2", "15:00", "OUT", category="BUSINESS_OUTING"),
            evt("i2", "15:30", "IN"),
        ])
        self.assertEqual(row["verified_rest_min"], 60)
        self.assertEqual(row["event_intervals"][1]["classification"],
                         "BUSINESS_OUTING")
        self.assertEqual(row["status"], "PASS_VERIFIED")

    def test_personal_outing_never_automatically_becomes_rest(self):
        row, _ = self.assess([
            evt("exit", "12:00", "OUT", category="PERSONAL_OUTING"),
            evt("entry", "12:30", "IN"),
        ])
        self.assertEqual(row["verified_rest_min"], 0)
        self.assertEqual(row["status"], "REVIEW_REQUIRED")

    def test_complete_coverage_with_no_rest_detects_shortfall(self):
        cfg = settings(break_verifications=[{
            "employee_id": "E001", "work_date": "2026-11-13",
            "coverage_complete": True, "evidence_ref": "HR-ALL-REST-CHECKED",
        }])
        row, _ = self.assess([], config=cfg, break_min=0)
        self.assertEqual(row["status"], "SHORTFALL_DETECTED")
        self.assertEqual(row["confirmed_shortfall_min"], 60)
        self.assertFalse(row["approved"])

    def test_even_no_exit_cannot_prove_no_indoor_rest(self):
        row, _ = self.assess([])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIsNone(row["confirmed_shortfall_min"])

    def test_duplicate_unmatched_and_outside_punches_do_not_pass(self):
        row, _ = self.assess([
            evt("e1", "12:00", "OUT", category="REST_CONFIRMED",
                verified=True, ref="HR-1"),
            evt("e2", "12:15", "OUT"),
            evt("i1", "13:00", "IN"),
            evt("i2", "14:00", "IN"),
        ])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("DUPLICATE_OUT_PUNCH", row["review_codes"])

    def test_duplicate_event_id_is_rejected(self):
        bundle = synthetic_bundle([evt("same", "12:00", "OUT"),
                                   evt("same", "13:00", "IN")])
        cfg = settings()
        with self.assertRaisesRegex(reviewer.BreakReviewError, "duplicated"):
            reviewer.analyze_access_breaks(bundle, cfg, calculate(bundle, cfg))

    def test_four_hour_exception_requires_proven_request_and_effective_date(self):
        self.assertEqual(reviewer.legal_break_min(240, reviewer._date("2026-11-13"),
                                                 explicit_request_ref="HR-1"), 30)
        self.assertEqual(reviewer.legal_break_min(240, reviewer._date("2026-12-10"),
                                                 explicit_request_ref="HR-1"), 0)
        self.assertEqual(reviewer.legal_break_min(240, reviewer._date("2026-12-10")), 30)
        self.assertEqual(reviewer.legal_break_min(480, reviewer._date("2026-12-10"),
                                                 explicit_request_ref="HR-1"), 60)

    def test_cli_appends_break_review_only_with_access_source(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            normalized = root / "normalized-input.json"
            config = root / "config.json"
            output = root / "output"
            events = [
                evt("e1", "12:00", "OUT", category="REST_CONFIRMED",
                    verified=True, ref="HR-CERT-1"),
                evt("e2", "13:00", "IN"),
            ]
            normalized.write_text(json.dumps(synthetic_bundle(events)),
                                  encoding="utf-8")
            config.write_text(json.dumps(settings()), encoding="utf-8")
            run = subprocess.run([
                sys.executable, str(ROOT / "run.py"), "bhandara",
                "worktime-calculator", "--normalized", str(normalized),
                "--config", str(config), "--output-dir", str(output),
            ], cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(run.returncode, 2, run.stderr)
            sidecar = json.loads((output / "break-compliance.json").read_text())
            self.assertEqual(sidecar["rows"][0]["status"], "PASS_VERIFIED")
            self.assertFalse(sidecar["finalizable"])
            book = load_workbook(output / "worktime-review.xlsx", read_only=True)
            try:
                self.assertIn("Break Compliance", book.sheetnames)
                self.assertIn("Daily Worktime", book.sheetnames)
            finally:
                book.close()
            pay_json = json.loads((output / "worktime-result.json").read_text())
            self.assertFalse(pay_json["finalizable"])
            self.assertIsNone(pay_json["close_receipt"])

    def test_cli_without_caps_source_keeps_exact_original_artifact_set(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            normalized = root / "normalized-input.json"
            config = root / "config.json"
            output = root / "output"
            bundle = synthetic_bundle()
            bundle["sources"].pop("access_events")
            normalized.write_text(json.dumps(bundle), encoding="utf-8")
            config.write_text(json.dumps(settings()), encoding="utf-8")
            run = subprocess.run([
                sys.executable, str(ROOT / "run.py"), "bhandara",
                "worktime-calculator", "--normalized", str(normalized),
                "--config", str(config), "--output-dir", str(output),
            ], cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertFalse((output / "break-compliance.json").exists())
            book = load_workbook(output / "worktime-review.xlsx", read_only=True)
            try:
                self.assertNotIn("Break Compliance", book.sheetnames)
            finally:
                book.close()


if __name__ == "__main__":
    unittest.main()
