"""New Worktime Tool: JSON-only CLI, real synthetic Module composition."""
from __future__ import annotations

from datetime import date
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.worktime.access_source import write_access_events_xlsx
from bhandara.worktime.output_excel import read_worktime_xlsx


ROOT = Path(__file__).resolve().parents[2]
TOOL = importlib.import_module("bhandara.worktime.tool_cli")
START = "2026-11-16"
END = "2026-11-22"
POLICY = {
    "schema_version": "0.1", "policy_ref": "SYNTHETIC_POLICY",
    "daily_standard_min": 480, "weekly_standard_min": 2400,
    "weekly_limit_min": 3120, "rest_every_work_min": 240,
    "rest_per_block_min": 30, "break_overrun_tolerance_min": 0,
}


def workbook(path: Path, data: dict[str, tuple[list, list[list]]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    for n, (sheet_name, (headers, rows)) in enumerate(data.items()):
        sheet = book.active if n == 0 else book.create_sheet(sheet_name)
        sheet.title = sheet_name
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
    book.save(path)
    book.close()


class JSONWorktimeToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worktime-json-tool-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.outputs = self.root / "output"
        self.config = self.root / "config.json"
        workbook(self.inputs / "worktime/work-schedule.xlsx", {
            "LEGACY": (["keep_legacy"], [["unchanged"]]),
            "SCHEDULE MAP": (
                ["schedule_id", "schedule_type", "scheduled_start", "scheduled_end",
                 "end_day_offset", "break_min", "scheduled_min", "valid_from", "valid_to"],
                [["DAY_A", "DAY", "09:00", "18:00", 0, 60, 480, "2026-01-01", "2026-12-31"]]),
            "ASSIGNMENTS": (
                ["employee_id", "work_date", "schedule_id", "day_type"],
                [["E001", START, "DAY_A", "WORK"]]),
        })
        workbook(self.inputs / "worktime/attendance.xlsx", {
            "Attendance": (
                ["employee_id", "work_date", "clock_in", "clock_out", "break_min"],
                [["E001", START, "08:40", "18:13", 60]],
            ),
        })
        workbook(self.inputs / "worktime/verified-work.xlsx", {
            "DAILY": (
                ["employee_id", "work_date", "actor_type", "worktime_system",
                 "policy_ref", "worked_min", "worked_verified", "worked_evidence_ref",
                 "rest_min", "rest_verified", "rest_evidence_ref",
                 "rest_within_workday_verified", "rest_coverage_complete",
                 "rest_coverage_ref", "planned_break_min"],
                [["E001", START, "EMPLOYEE", "standard", "SYNTHETIC_POLICY",
                  480, True, "WORK-SOURCE", 60, True, "REST-SOURCE",
                  True, True, "COVERAGE", 60]],
            ),
            "WEEKLY COVERAGE": (
                ["employee_id", "week_start", "coverage_complete",
                 "evidence_ref", "exception_status"],
                [["E001", START, True, "FULL-WEEK", "NONE"]],
            ),
        })
        workbook(self.inputs / "worktime/attendance-facts.xlsx", {
            "ATTENDANCE FACTS": (
                ["employee_id", "work_date", "attendance_type",
                 "leave_type", "leave_request_id"],
                [["E001", START, "WORK", None, None]],
            ),
        })
        vendor = self.inputs / "worktime/access-events.xlsx"
        write_access_events_xlsx(
            vendor, [
                {"event_id": "IN1", "employee_id": "E001", "worker_id": "EP0001",
                 "work_date": START, "event_time": f"{START}T08:40",
                 "mode": "CLOCK_IN", "direction": "IN",
                 "auth_status": "SUCCESS", "auth_method": "FINGERPRINT",
                 "device_id": "DEVICE", "source_vendor": "SYNTHETIC",
                 "source_ref": "SYNTHETIC_SOURCE", "source_row_number": 2},
                {"event_id": "OUT1", "employee_id": "E001", "worker_id": "EP0001",
                 "work_date": START, "event_time": f"{START}T18:13",
                 "mode": "CLOCK_OUT", "direction": "OUT",
                 "auth_status": "SUCCESS", "auth_method": "FINGERPRINT",
                 "device_id": "DEVICE", "source_vendor": "SYNTHETIC",
                 "source_ref": "SYNTHETIC_SOURCE", "source_row_number": 3},
            ], [], source_vendor="SYNTHETIC", source_sha256="a" * 64,
            source_file="synthetic-raw.xlsx",
        )
        self.base = {
            "schema_version": "1.0", "tool": "worktime",
            "run_id": "example", "period_from": START, "period_to": END,
            "input_root": str(self.inputs), "output_root": str(self.outputs),
            "steps": ["schedule", "attendance-verification",
                      "worktime-compliance", "output"],
            "files": {
                "schedule": "worktime/work-schedule.xlsx",
                "attendance": "worktime/attendance.xlsx",
                "access_events": "worktime/access-events.xlsx",
                "verified_work": "worktime/verified-work.xlsx",
                "attendance_facts": "worktime/attendance-facts.xlsx",
            },
            "policy": POLICY,
        }

    def save(self, **kwargs):
        self.config.write_text(json.dumps({**self.base, **kwargs},
                                          ensure_ascii=False), encoding="utf-8")

    def invoke(self):
        return subprocess.run([sys.executable, str(ROOT / "run.py"),
                               "bhandara", "worktime", "--config", str(self.config)],
                              cwd=ROOT, capture_output=True, text=True, timeout=30)

    def test_all_modules_composed_into_single_factual_sheet(self):
        self.save()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(list(data["artifacts"]), self.base["steps"])
        root = self.outputs / "example"
        self.assertEqual(sorted(x.name for x in root.iterdir()), [
            "attendance-verification-result.json", "schedule-result.json",
            "worktime-compliance-result.json", "worktime-result.xlsx",
        ])
        rows = read_worktime_xlsx(root / "worktime-result.xlsx")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["scheduled_min"], 480)
        self.assertEqual(row["actual_min"], 480)
        self.assertEqual(row["clock_in_delta_min"], 20)
        self.assertEqual(row["clock_out_delta_min"], 13)
        self.assertEqual(row["attendance_type"], "WORK")
        self.assertNotIn("status", row)
        book = load_workbook(root / "worktime-result.xlsx", read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["WORKTIME"])
        finally:
            book.close()

    def test_schedule_only_is_selectable(self):
        self.save(steps=["schedule"])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([p.name for p in (self.outputs / "example").iterdir()],
                         ["schedule-result.json"])

    def test_output_can_use_explicit_prior_module_json(self):
        self.save()
        self.assertEqual(self.invoke().returncode, 0)
        old = self.outputs / "example"
        self.save(run_id="only-output", steps=["output"], files={
            "schedule": "worktime/work-schedule.xlsx",
            "attendance_verification_result": str(old / "attendance-verification-result.json"),
            "compliance_result": str(old / "worktime-compliance-result.json"),
            "attendance_facts": "worktime/attendance-facts.xlsx",
        })
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = read_worktime_xlsx(self.outputs / "only-output/worktime-result.xlsx")
        self.assertEqual(rows[0]["clock_in_delta_min"], 20)

    def test_no_implicit_approval_or_status_in_factual_result(self):
        self.save()
        self.assertEqual(self.invoke().returncode, 0)
        row = read_worktime_xlsx(self.outputs / "example/worktime-result.xlsx")[0]
        for name in ("approval", "status", "payable_min", "overtime_min", "leave_min"):
            self.assertNotIn(name, row)

    def test_no_existing_output_overwrite(self):
        self.save()
        self.assertEqual(self.invoke().returncode, 0)
        again = self.invoke()
        self.assertEqual(again.returncode, 2)
        self.assertIn("already exists", again.stderr)

    def test_missing_verified_work_is_not_guessed_from_access(self):
        self.save(files={k: v for k, v in self.base["files"].items()
                         if k != "verified_work"})
        self.assertEqual(self.invoke().returncode, 2)
        self.assertFalse(self.outputs.exists())

    def test_invalid_step_order_rejected(self):
        self.save(steps=["output", "attendance-verification",
                         "worktime-compliance"])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("must precede output", result.stderr)

    def test_unverified_actual_is_null(self):
        path = self.inputs / "worktime/verified-work.xlsx"
        book = load_workbook(path)
        book["DAILY"]["G2"] = False
        book.save(path)
        book.close()
        self.save()
        output = self.invoke()
        self.assertEqual(output.returncode, 0, output.stderr)
        row = read_worktime_xlsx(self.outputs / "example/worktime-result.xlsx")[0]
        self.assertIsNone(row["actual_min"])


if __name__ == "__main__":
    unittest.main()
