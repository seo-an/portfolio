"""Targeted unittest coverage for explicit Bhandara Tool handoffs (no Golden run)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bhandara.workflow import WorkflowError, execute


PERIOD_FROM = "2026-11-01"
PERIOD_TO = "2026-11-30"
SOURCES = (
    "settlement_plan", "attendance_plan", "verified_work",
    "approved_segments", "evidence_registry", "rate_policy", "rollup_policy",
)


class WorkflowHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input"
        self.input.mkdir()
        self.out = self.root / "payroll-output"
        self.worktime_dir = self.root / "worktime-output" / "wt-previous"
        self.worktime_dir.mkdir(parents=True)
        self.worktime = self.worktime_dir / "worktime-result.xlsx"
        self.worktime.write_bytes(b"synthetic worktime placeholder")
        contract = json.loads(
            (Path(__file__).resolve().parents[1] / "payroll" /
             "input-files.json").read_text(encoding="utf-8")
        )
        for detail in contract["workbooks"].values():
            target = self.input / contract["input_directory"] / detail["filename"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic input placeholder")
        self.sources = {}
        for name in SOURCES:
            target = self.input / f"{name}.json"
            target.write_text("[]" if name in ("verified_work", "approved_segments")
                              else "{}", encoding="utf-8")
            self.sources[name] = str(target)
        self.payroll_config = self.root / "payroll.json"
        self.payroll = {
            "schema_version": "1.0", "tool": "payroll", "run_id": "auto",
            "payroll_period": "2026-11", "steps": ["review", "output"],
            "input_root": str(self.input), "output_root": str(self.out),
            "files": {"worktime": str(self.worktime)},
            "source_files": self.sources,
        }
        self._write(self.payroll_config, self.payroll)
        self.config_path = self.root / "workflow.json"
        self.config = {
            "schema_version": "1.0", "workflow": "payroll",
            "payroll_period": "2026-11", "run_id": "wf-test",
            "tools": {
                "worktime": {"action": "reuse", "artifacts": {
                    "output": self._manifest(self.worktime)
                }},
                "payroll": {"config": str(self.payroll_config)},
            },
        }
        self._save()

    @staticmethod
    def _write(path, doc):
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _manifest(path):
        return {
            "path": str(path), "run_id": path.parent.name,
            "period_from": PERIOD_FROM, "period_to": PERIOD_TO,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def _save(self):
        self._write(self.config_path, self.config)

    def test_reuse_calls_only_payroll_once_and_writes_no_extra_source(self):
        def inspect(path):
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(doc["run_id"], "wf-test")
            self.assertEqual(doc["files"]["worktime"], str(self.worktime))
            self.assertEqual(doc["source_files"], self.sources)
            return {"review": str(self.out / "wf-test/payroll-review.json")}
        with patch("bhandara.payroll.tool_cli.execute", side_effect=inspect) as payroll:
            response = execute(self.config_path)
        payroll.assert_called_once()
        self.assertEqual(response["approval_state"], "NOT_APPROVED")
        self.assertEqual(response["handoff"]["worktime"]["run_id"], "wt-previous")

    def test_hash_mismatch_stops_before_payroll(self):
        self.config["tools"]["worktime"]["artifacts"]["output"]["sha256"] = "0" * 64
        self._save()
        with patch("bhandara.payroll.tool_cli.execute") as payroll:
            with self.assertRaisesRegex(WorkflowError, "SHA256"):
                execute(self.config_path)
        payroll.assert_not_called()

    def test_wrong_period_stops_before_payroll(self):
        self.config["tools"]["worktime"]["artifacts"]["output"]["period_from"] = "2026-10-01"
        self._save()
        with patch("bhandara.payroll.tool_cli.execute") as payroll:
            with self.assertRaisesRegex(WorkflowError, "기간"):
                execute(self.config_path)
        payroll.assert_not_called()

    def test_missing_approval_source_stops_before_upstream(self):
        self.payroll["source_files"].pop("approved_segments")
        self._write(self.payroll_config, self.payroll)
        with patch("bhandara.payroll.tool_cli.execute") as payroll:
            with self.assertRaisesRegex(WorkflowError, "외부 승인"):
                execute(self.config_path)
        payroll.assert_not_called()

    def test_reuse_must_name_exact_run_directory(self):
        self.config["tools"]["worktime"]["artifacts"]["output"]["run_id"] = "wrong"
        self._save()
        with self.assertRaisesRegex(WorkflowError, "run_id"):
            execute(self.config_path)

    def test_payroll_output_cannot_contain_reused_source(self):
        self.payroll["output_root"] = str(self.root)
        self._write(self.payroll_config, self.payroll)
        with self.assertRaisesRegex(WorkflowError, "output_root"):
            execute(self.config_path)

    def test_workflow_run_id_does_not_overwrite_prior_result(self):
        (self.out / "wf-test").mkdir(parents=True)
        with patch("bhandara.payroll.tool_cli.execute") as payroll:
            with self.assertRaisesRegex(WorkflowError, "덮어쓰기"):
                execute(self.config_path)
        payroll.assert_not_called()

    def test_run_pto_and_worktime_handoffs_once_without_closing(self):
        pto_dir = self.root / "pto-output" / "pto-run"
        pto_dir.mkdir(parents=True)
        usage = pto_dir / "usage-ledger-result.xlsx"
        deduction = pto_dir / "deduction-quantity-result.xlsx"
        usage.write_bytes(b"synthetic usage")
        deduction.write_bytes(b"synthetic deduction")
        claims = self.input / "pto-claims.json"
        claims.write_text("[]", encoding="utf-8")
        self.payroll["source_files"]["pto_claims"] = str(claims)
        self._write(self.payroll_config, self.payroll)
        pto_cfg = self.root / "pto.json"
        self._write(pto_cfg, {
            "schema_version": "1.0", "tool": "paid-time-off",
            "as_of_date": "2026-11-30",
            "steps": ["deduction-quantity", "usage-ledger"],
        })
        wt_cfg = self.root / "wt.json"
        self._write(wt_cfg, {
            "schema_version": "1.0", "tool": "worktime",
            "period_from": PERIOD_FROM, "period_to": PERIOD_TO,
            "steps": ["output"],
        })
        self.config["tools"]["paid-time-off"] = {
            "action": "run", "config": str(pto_cfg),
        }
        self.config["tools"]["worktime"] = {
            "action": "run", "config": str(wt_cfg),
        }
        self._save()
        invoked = []

        def fake_module(name):
            self.assertIn(name, ("bhandara.paid-time-off.tool_cli",
                                 "bhandara.worktime.tool_cli"))
            def run(path):
                invoked.append(name)
                if "paid-time-off" in name:
                    return {"usage-ledger": str(usage),
                            "deduction-quantity": str(deduction)}
                return {"output": str(self.worktime)}
            return SimpleNamespace(execute=run)

        def inspect(path):
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(doc["files"]["pto_usage"], str(usage))
            self.assertEqual(doc["files"]["pto_deduction"], str(deduction))
            self.assertNotIn("pto_closing", doc["files"])
            self.assertEqual(doc["files"]["worktime"], str(self.worktime))
            return {"output": str(self.out / "wf-test/payroll-result.xlsx")}

        with patch("bhandara.workflow.import_module", side_effect=fake_module):
            with patch("bhandara.payroll.tool_cli.execute", side_effect=inspect) as payroll:
                result = execute(self.config_path)
        self.assertEqual(invoked, ["bhandara.paid-time-off.tool_cli",
                                   "bhandara.worktime.tool_cli"])
        payroll.assert_called_once()
        self.assertEqual(result["status"], "PARTIAL_REVIEW_ONLY")

    def test_unconfirmed_closing_not_forwarded(self):
        cfg = self.root / "pto.json"
        self._write(cfg, {
            "schema_version": "1.0", "tool": "paid-time-off",
            "as_of_date": "2026-11-30",
            "steps": ["deduction-quantity", "usage-ledger", "closing"],
        })
        claims = self.input / "pto-claims.json"
        claims.write_text("[]", encoding="utf-8")
        self.payroll["source_files"]["pto_claims"] = str(claims)
        self._write(self.payroll_config, self.payroll)
        self.config["tools"]["paid-time-off"] = {
            "action": "run", "config": str(cfg),
        }
        self._save()
        with patch("bhandara.workflow.import_module") as modules:
            with self.assertRaisesRegex(WorkflowError, "미확정 Closing"):
                execute(self.config_path)
        modules.assert_not_called()


if __name__ == "__main__":
    unittest.main()
