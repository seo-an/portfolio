"""Public synthetic Golden comparisons, unittest only; no private fixtures."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bhandara.common.validation.golden_compare import (
    GoldenCompareError, compare, project,
)


def workflow():
    return {
        "schema_version": "0.1", "run_id": "random-1", "started_at": "time-1",
        "updated_at": "time-1", "payroll_period": "2026-10",
        "status": "REVIEW_REQUIRED", "finalizable": False,
        "comparison_required": True, "payment_approved": False,
        "ledger_committed": False, "config_hashes": {"manifest": "abc"},
        "stages": [{
            "name": "payroll", "status": "REVIEW", "record_count": 2,
            "issue_count": 7, "message": "REVIEW_REQUIRED",
            "started_at": "time-1", "ended_at": "time-1",
            "artifacts": {"calculation_json": "/tmp/a.json", "review_json": "/tmp/b.json"},
            "artifact_sha256": {"calculation_json": "sha1", "review_json": "sha2"},
        }],
    }


def pto():
    return {
        "baseline": "pto-july-2026-three-synthetic-employees",
        "source_commit": "old-git-sha", "period": {"from": "2026-07-01", "to": "2026-07-31"},
        "source_hashes": {"employee.xlsx": "sha"},
        "results": [{"employee_id": "E001", "grants": [{"raw_days": "15"}], "unresolved_grants": []}],
    }


def payroll():
    return {
        "schema_version": "0.1", "status": "REVIEW_REQUIRED",
        "finalizable": False, "ledger_committed": False,
        "composition": {"worker_runs": {"EP0001": {"payable_amount": "3300000"}}},
        "expected_worker_ids": ["EP0001"],
    }


def register():
    return {
        "schema_version": "0.1", "status": "REVIEW_REQUIRED",
        "finalizable": False, "comparison_required": True,
        "payroll_period": "2026-10", "worker_count": 1,
        "rows": [{"worker_id": "EP0001", "status": "CALCULATED_REVIEW", "pay_total": "3300000", "payable_amount": None}],
    }


class GoldenCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, payload):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return target

    def check(self, profile, old, new):
        return compare(self.write("old.json", old), self.write("new.json", new), profile)

    def test_workflow_only_verified_volatile_metadata_ignored(self):
        x = workflow()
        y = copy.deepcopy(x)
        y["run_id"] = "random-2"
        y["started_at"] = y["updated_at"] = "time-2"
        y["stages"][0].update({
            "started_at": "time-2", "ended_at": "time-2",
            "artifacts": {"calculation_json": "/other/a.json", "review_json": "/other/b.json"},
            "artifact_sha256": {"calculation_json": "new", "review_json": "new2"},
        })
        self.assertEqual(self.check("workflow-run", x, y), [])

    def test_workflow_artifact_kinds_must_match(self):
        x = workflow()
        y = copy.deepcopy(x)
        y["stages"][0]["artifacts"].pop("review_json")
        self.assertTrue(self.check("workflow-run", x, y))

    def test_workflow_counts_and_status_cannot_change(self):
        x = workflow()
        y = copy.deepcopy(x)
        y["stages"][0]["issue_count"] = 8
        y["status"] = "BLOCKED"
        paths = [d.pointer for d in self.check("workflow-run", x, y)]
        self.assertIn("/status", paths)
        self.assertIn("/stages/0/issue_count", paths)

    def test_approval_guards_reject_even_equal_bad_values(self):
        x = workflow()
        x["payment_approved"] = True
        with self.assertRaises(GoldenCompareError):
            self.check("workflow-run", x, x)

    def test_workflow_config_hash_change_not_ignored(self):
        x = workflow()
        y = copy.deepcopy(x)
        y["config_hashes"]["manifest"] = "different"
        self.assertTrue(self.check("workflow-run", x, y))

    def test_pto_commit_excluded_but_results_compared(self):
        x = pto()
        y = copy.deepcopy(x)
        y["source_commit"] = "new-git-sha"
        self.assertEqual(self.check("pto-golden", x, y), [])
        y["results"][0]["grants"][0]["raw_days"] = "16"
        self.assertIn("/results/0/grants/0/raw_days", [d.pointer for d in self.check("pto-golden", x, y)])

    def test_pto_unresolved_reason_change_detected(self):
        x = pto()
        x["results"][0]["unresolved_grants"] = [{"reason": "REVIEW"}]
        y = copy.deepcopy(x)
        y["results"][0]["unresolved_grants"][0]["reason"] = "OK"
        self.assertTrue(self.check("pto-golden", x, y))

    def test_pto_input_hash_change_detected(self):
        x = pto()
        y = copy.deepcopy(x)
        y["source_hashes"]["employee.xlsx"] = "changed"
        self.assertTrue(self.check("pto-golden", x, y))

    def test_payroll_monies_must_not_change(self):
        x = payroll()
        y = copy.deepcopy(x)
        y["composition"]["worker_runs"]["EP0001"]["payable_amount"] = "3300010"
        self.assertTrue(self.check("payroll-calculation", x, y))

    def test_payroll_register_null_differs_from_zero(self):
        x = register()
        y = copy.deepcopy(x)
        y["rows"][0]["payable_amount"] = 0
        self.assertTrue(self.check("provisional-register", x, y))

    def test_payroll_register_fails_if_finalizable(self):
        x = register()
        x["finalizable"] = True
        with self.assertRaises(GoldenCompareError):
            self.check("provisional-register", x, x)

    def test_review_source_hash_only_ignored_at_verified_root(self):
        x = {"schema_version": "0.1", "status": "REVIEW_REQUIRED", "finalizable": False,
             "ledger_committed": False, "source_hashes": {"xlsx": "1"},
             "issues": [{"code": "ACTION_REQUIRED", "source_hashes": "business-data"}],
             "worker_statuses": []}
        y = copy.deepcopy(x)
        y["source_hashes"]["xlsx"] = "2"
        self.assertEqual(self.check("payroll-review", x, y), [])
        y["issues"][0]["source_hashes"] = "modified"
        self.assertTrue(self.check("payroll-review", x, y))

    def test_strict_json_number_type_and_list_order(self):
        self.assertTrue(self.check("strict-json", {"n": None}, {"n": 0}))
        self.assertTrue(self.check("strict-json", {"n": 0}, {"n": False}))
        self.assertTrue(self.check("strict-json", {"arr": [1, 2]}, {"arr": [2, 1]}))
        self.assertTrue(self.check("strict-json", {"n": 1}, {"n": 1.0}))

    def test_duplicate_json_keys_fail_closed(self):
        left = self.root / "dup.json"
        left.write_text('{"status": "PASS", "status": "FAILED"}', encoding="utf-8")
        right = self.write("unique.json", {"status": "PASS"})
        with self.assertRaises(GoldenCompareError):
            compare(left, right, "strict-json")

    def test_missing_file_is_invalid(self):
        with self.assertRaises(GoldenCompareError):
            compare(self.root / "nope.json", self.write("other.json", {}), "strict-json")

    def test_cli_differences_exit_one_no_values_leaked(self):
        a = self.write("before.json", {"salary": 10})
        b = self.write("after.json", {"salary": 999999})
        run = subprocess.run([sys.executable, str(ROOT / "run.py"), "compare-golden",
                              "--profile", "strict-json", "--expected", str(a),
                              "--actual", str(b)], cwd=ROOT, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(run.returncode, 1)
        self.assertIn("/salary", run.stdout)
        self.assertNotIn("999999", run.stdout)

    def test_cli_equal_exit_zero(self):
        a = self.write("before.json", {"value": 42})
        b = self.write("after.json", {"value": 42})
        run = subprocess.run([sys.executable, str(ROOT / "run.py"), "compare-golden",
                              "--profile", "strict-json", "--expected", str(a),
                              "--actual", str(b)], cwd=ROOT, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(run.returncode, 0)
        self.assertIn("GOLDEN_PASS", run.stdout)

    def test_cli_invalid_exit_two(self):
        run = subprocess.run([sys.executable, str(ROOT / "run.py"), "compare-golden",
                              "--profile", "strict-json", "--expected", "/not/here",
                              "--actual", "/not/here"], cwd=ROOT, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(run.returncode, 2)
        self.assertIn("GOLDEN_INVALID", run.stderr)

    def test_bundle_changed_row_detected(self):
        old = self.root / "expected"
        new = self.root / "actual"
        sample = {
            "workflow-run.json": workflow(),
            "01-normalized/normalized-input.json": {"schema_version": "0.1", "status": "READY_FOR_CALCULATION", "sources": {}},
            "01-normalized/review-report.json": {"issues": []},
            "02-worktime/worktime-result.json": {"schema_version": "0.1", "status": "REVIEW_REQUIRED", "finalizable": False, "rows": [], "close_receipt": None, "coverage_verified": False, "source_hashes": {}},
            "02-worktime/worktime-review.json": {"issues": []},
            "04-payroll/payroll-calculation.json": payroll(),
            "04-payroll/payroll-review.json": {"schema_version": "0.1", "status": "REVIEW_REQUIRED", "finalizable": False, "ledger_committed": False, "source_hashes": {}, "issues": [], "worker_statuses": []},
            "04-payroll/policy-resolution.json": {"schema_version": "0.1", "finalizable": False, "resolved_company_policy": {}},
            "04-payroll/provisional-payroll-register.json": register(),
        }
        for path, contents in sample.items():
            for folder in (old, new):
                target = folder / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(contents), encoding="utf-8")
        self.assertEqual(compare(old, new, "payroll-workflow"), [])
        modified = copy.deepcopy(sample["04-payroll/provisional-payroll-register.json"])
        modified["rows"][0]["pay_total"] = "bad-amount"
        self.write("actual/04-payroll/provisional-payroll-register.json", modified)
        self.assertTrue(any("pay_total" in d.pointer for d in compare(old, new, "payroll-workflow")))

    def test_profile_never_alters_original_objects(self):
        original = workflow()
        before = copy.deepcopy(original)
        project(original, "workflow-run")
        self.assertEqual(original, before)


if __name__ == "__main__":
    unittest.main()
