"""P1-3 unit/e2e: separate reference records cannot contradict claimed approval."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from bhandara.payroll.evidence_reconciliation import (
    EvidenceReconciliationError, reconcile_overtime_evidence,
)
from bhandara.payroll.evidence_preview import build_reconciled_overtime_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_overtime_candidates_p1 import (
    approved, policy, rate, verified,
)
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx


START, END = "2026-11-01", "2026-11-30"


def registry(*, works=None, approvals=None):
    work = verified()
    segment = approved()
    source_work = [dict(work, status="VERIFIED")] if works is None else works
    source_approvals = [dict(segment, status="CURRENT")] if approvals is None else approvals
    return {
        "schema_version": "0.1",
        "period_from": START, "period_to": END,
        "source_system": "SYNTHETIC-HR-APPROVAL-REGISTER",
        "snapshot_ref": "SNAPSHOT-SYNTHETIC-01",
        "work_verifications": source_work,
        "approvals": source_approvals,
        "classifications": [{
            "classification_ref": "CLASSIFIED-SYNTHETIC",
            "segment_id": "A001", "rule_id": "OT01",
            "category": "OVERTIME", "policy_ref": "EXAMPLE-ONLY",
            "status": "VERIFIED",
        }],
        "base_inclusions": [{
            "base_inclusion_ref": "BASE-EXCLUSION-SYNTHETIC",
            "segment_id": "A001",
            "base_pay_includes_time": False,
            "status": "VERIFIED",
        }],
    }


def reconcile(*, work=None, segment=None, source=None, rules=None):
    return reconcile_overtime_evidence(
        verified_work=[verified()] if work is None else work,
        approved_segments=[approved()] if segment is None else segment,
        registry=registry() if source is None else source,
        overtime_rules=[rate()] if rules is None else rules,
        period_from=START, period_to=END,
    )


class PayrollEvidenceReconciliationTests(unittest.TestCase):
    def test_matching_registry_is_still_not_authenticated_or_payment_approved(self):
        result = reconcile()
        self.assertEqual(result["claim_consistency"], "MATCHED_SOURCE_RECORDS")
        self.assertEqual(result["source_authenticity"], "NOT_AUTHENTICATED_BY_THIS_MODULE")
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        self.assertEqual(result["work_reference_count"], 1)
        self.assertEqual(result["approval_reference_count"], 1)

    def test_rejected_claim_modifications_do_not_pass_by_matching_reference_only(self):
        for change in (
            {"employee_id": "0002"},
            {"end_at": "2026-11-02T17:30"},
            {"start_at": "2026-11-02T17:10"},
            {"rule_id": "FAKE"},
            {"approval_status": "REVOKED"},
            {"base_pay_includes_time": True},
            {"work_evidence_id": "W999"},
        ):
            with self.subTest(change=change), self.assertRaises(EvidenceReconciliationError):
                reconcile(segment=[approved(**change)])
        with self.assertRaises(EvidenceReconciliationError):
            reconcile(work=[verified(end_at="2026-11-02T18:30")])

    def test_revoked_or_unverified_independent_records_stop_all_computation(self):
        for table, status in (
            ("work_verifications", "PENDING"),
            ("approvals", "REVOKED"),
            ("classifications", "PENDING"),
            ("base_inclusions", "UNKNOWN"),
        ):
            data = registry()
            data[table][0]["status"] = status
            with self.subTest(table=table), self.assertRaises(EvidenceReconciliationError):
                reconcile(source=data)

    def test_unapproved_source_record_stops_run(self):
        data = registry()
        data["approvals"][0]["approval_status"] = "PENDING"
        with self.assertRaisesRegex(EvidenceReconciliationError, "APPROVED"):
            reconcile(source=data)

    def test_classification_rule_and_policy_provenance_mismatch(self):
        for field, value in (
            ("rule_id", "H01"), ("category", "NIGHT"), ("policy_ref", "UNTRUSTED"),
            ("segment_id", "A002"),
        ):
            data = registry()
            data["classifications"][0][field] = value
            with self.subTest(field=field), self.assertRaises(EvidenceReconciliationError):
                reconcile(source=data)
        with self.assertRaises(EvidenceReconciliationError):
            reconcile(rules=[rate(policy_ref="POLICY-CHANGED")])

    def test_missing_or_wrong_base_inclusion_source(self):
        data = registry()
        data["base_inclusions"] = []
        with self.assertRaises(EvidenceReconciliationError):
            reconcile(source=data)
        data = registry()
        data["base_inclusions"][0]["base_pay_includes_time"] = True
        with self.assertRaises(EvidenceReconciliationError):
            reconcile(source=data)
        data = registry()
        data["base_inclusions"][0]["segment_id"] = "OTHER"
        with self.assertRaises(EvidenceReconciliationError):
            reconcile(source=data)

    def test_duplicate_references_and_unknown_registry_keys(self):
        data = registry()
        data["work_verifications"].append(deepcopy(data["work_verifications"][0]))
        with self.assertRaisesRegex(EvidenceReconciliationError, "duplicate key"):
            reconcile(source=data)
        data = registry()
        data["approvals"].append(deepcopy(data["approvals"][0]))
        with self.assertRaisesRegex(EvidenceReconciliationError, "duplicate key"):
            reconcile(source=data)
        data = registry()
        data["unexpected"] = True
        with self.assertRaisesRegex(EvidenceReconciliationError, "exact envelope"):
            reconcile(source=data)

    def test_claims_outside_payroll_period_fail_even_if_snapshot_agrees(self):
        shifted = verified(work_date="2026-12-01", start_at="2026-12-01T17:00",
                           end_at="2026-12-01T18:00")
        data = registry(works=[dict(shifted, status="VERIFIED")])
        with self.assertRaisesRegex(EvidenceReconciliationError, "outside payroll period"):
            reconcile(work=[shifted], segment=[], source=data)

    def test_period_and_missing_source_snapshot_fail_closed(self):
        data = registry()
        data["period_from"] = "2026-10-01"
        with self.assertRaisesRegex(EvidenceReconciliationError, "period mismatch"):
            reconcile(source=data)
        data = registry()
        data["snapshot_ref"] = ""
        with self.assertRaisesRegex(EvidenceReconciliationError, "snapshot_ref"):
            reconcile(source=data)

    def test_empty_claim_sets_have_zero_verified_refs_not_approved_zero_pay(self):
        data = registry(works=[], approvals=[])
        data["classifications"] = []
        data["base_inclusions"] = []
        result = reconcile(work=[], segment=[], source=data)
        self.assertEqual(result["work_reference_count"], 0)
        self.assertEqual(result["approval_reference_count"], 0)
        self.assertEqual(result["approval_state"], "NOT_APPROVED")

    def test_reconciled_e2e_dynamic_payroll_remains_partial(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "payroll").mkdir()
            roles = ("contracts", "allowance_assignments", "fixed_allowance_map",
                     "bonus_budget", "bonus_allocation", "overtime_rules")
            for role in roles:
                spec = SCHEMA["workbooks"][role]
                book = Workbook()
                sheet = book.active
                sheet.title = spec["sheet"]
                sheet.append(spec["columns"])
                samples = [] if role in ("bonus_budget", "bonus_allocation") else [SAMPLES[role]]
                for item in samples:
                    sheet.append([item.get(field) for field in spec["columns"]])
                book.save(root / "payroll" / spec["filename"])
                book.close()
            inputs = read_payroll_inputs(root, roles=roles)
            source = root / "worktime-result.xlsx"
            write_worktime_xlsx(
                {"schema_version": "0.1", "rows": [fact(actual_min=540)]}, source,
            )
            result = build_reconciled_overtime_preview(
                inputs, source, period_from=START, period_to=END,
                verified_work=[verified()], approved_segments=[approved()],
                evidence_registry=registry(), rate_policy=policy(),
            )
            self.assertEqual(result["payroll_register"]["rows"][0]["overtime_allowances:OT01"], 18750)
            self.assertIsNone(result["payroll_register"]["rows"][0]["gross_pay"])
            self.assertIsNone(result["payroll_register"]["rows"][0]["net_pay"])
            self.assertEqual(result["evidence_review"]["source_authenticity"], "NOT_AUTHENTICATED_BY_THIS_MODULE")
            self.assertEqual(result["status"], "PARTIAL_REVIEW_ONLY")
            self.assertEqual(result["approval_state"], "NOT_APPROVED")


if __name__ == "__main__":
    unittest.main()
