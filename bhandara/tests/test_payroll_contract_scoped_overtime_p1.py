"""P1-5b-2a: split-contract approved overtime must use each contract's own rate."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import (
    ContractOvertimeAdapterError, build_contract_scoped_overtime_preview,
)
from bhandara.payroll.attendance_reconciliation import AttendanceSettlementError
from bhandara.payroll.evidence_reconciliation import EvidenceReconciliationError
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.overtime_candidates import OvertimeCandidateError
from bhandara.tests.test_payroll_attendance_settlement_p1 import (
    event, leave_fact, wage_plan,
)
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_overtime_candidates_p1 import (
    approved, policy, rate, verified,
)
from bhandara.tests.test_payroll_segmented_settlement_p1 import (
    FROM, TO, allocated, contract, employment, plan, split, split_plan,
)
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx


ROLES = (
    "contracts", "allowance_assignments", "fixed_allowance_map",
    "bonus_budget", "bonus_allocation", "overtime_rules",
)
ROLLUP = {"mode": "ROUND_PER_CONTRACT_RULE_THEN_SUM",
          "policy_ref": "SYNTHETIC-CONTRACT-ROUNDING"}
OLD_DAY, NEW_DAY = "2026-11-14", "2026-11-17"


def evidence(day, suffix):
    return verified(
        evidence_id=f"W-{suffix}", start=f"{day}T17:00", end=f"{day}T18:00",
        work_date=day, verification_ref=f"V-{suffix}",
    )


def segment(day, suffix):
    return approved(
        segment_id=f"A-{suffix}", work_evidence_id=f"W-{suffix}",
        start=f"{day}T17:00", end=f"{day}T18:00", work_date=day,
        approval_ref=f"AP-{suffix}", classification_ref=f"CLS-{suffix}",
        base_inclusion_ref=f"BASE-{suffix}",
    )


def source_registry(works, approvals, rules):
    by_rule = {rule["rule_id"]: rule for rule in rules}
    return {
        "schema_version": "0.1", "period_from": FROM, "period_to": TO,
        "source_system": "SYNTHETIC-HR-REGISTER",
        "snapshot_ref": "SNAPSHOT-SYNTHETIC-001",
        "work_verifications": [dict(row, status="VERIFIED") for row in works],
        "approvals": [dict(row, status="CURRENT") for row in approvals],
        "classifications": [
            {
                "classification_ref": row["classification_ref"],
                "segment_id": row["segment_id"], "rule_id": row["rule_id"],
                "category": by_rule[row["rule_id"]]["category"],
                "policy_ref": by_rule[row["rule_id"]]["policy_ref"],
                "status": "VERIFIED",
            } for row in approvals
        ],
        "base_inclusions": [
            {
                "base_inclusion_ref": row["base_inclusion_ref"],
                "segment_id": row["segment_id"],
                "base_pay_includes_time": row["base_pay_includes_time"],
                "status": "VERIFIED",
            } for row in approvals
        ],
    }


class ContractScopedOvertimeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "payroll").mkdir()
        self.workfile = self.root / "worktime-result.xlsx"

    def put(self, role, data):
        schema = SCHEMA["workbooks"][role]
        book = Workbook()
        book.active.title = schema["sheet"]
        book.active.append(schema["columns"])
        for row in data:
            book.active.append([row.get(field) for field in schema["columns"]])
        book.save(self.root / "payroll" / schema["filename"])
        book.close()

    def prepare(self, *, contracts=None, rules=None, assignments=None,
                allowance_map=None, bonuses=None, bonus_allocations=None):
        data = {
            "contracts": split() if contracts is None else contracts,
            "allowance_assignments": [] if assignments is None else assignments,
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])]
                if allowance_map is None else allowance_map,
            "bonus_budget": [] if bonuses is None else bonuses,
            "bonus_allocation": [] if bonus_allocations is None else bonus_allocations,
            "overtime_rules": [rate(minimum_minutes=0)] if rules is None else rules,
        }
        for role, rows in data.items():
            self.put(role, rows)
        return read_payroll_inputs(self.root, roles=ROLES)

    def source_work(self, data=None):
        rows = [
            fact(day=OLD_DAY, actual_min=540),
            fact(day=NEW_DAY, actual_min=540),
        ] if data is None else data
        write_worktime_xlsx({"schema_version": "0.1", "rows": rows}, self.workfile)
        return sha256_file(self.workfile)

    def run_preview(
        self, *, inputs=None, work=None, approvals=None, rules=None,
        settlement=None, adjustments=None, rate_config=None,
        rollup=None, registry=None, sha=None,
    ):
        inp = self.prepare() if inputs is None else inputs
        works = [evidence(OLD_DAY, "OLD"), evidence(NEW_DAY, "NEW")] if work is None else work
        segments = [segment(OLD_DAY, "OLD"), segment(NEW_DAY, "NEW")] if approvals is None else approvals
        active_rules = [rate(minimum_minutes=0)] if rules is None else rules
        if sha is None:
            sha = sha256_file(self.workfile) if self.workfile.is_file() else self.source_work()
        return build_contract_scoped_overtime_preview(
            inp, self.workfile,
            settlement_plan=split_plan() if settlement is None else settlement,
            attendance_plan=wage_plan(items=[] if adjustments is None else adjustments, sha=sha),
            period_from=FROM, period_to=TO,
            verified_work=works, approved_segments=segments,
            evidence_registry=(source_registry(works, segments, active_rules)
                               if registry is None else registry),
            rate_policy=policy(
                reference_day_minutes_by_contract={"C-OLD": 480, "C-NEW": 480},
            ) if rate_config is None else rate_config,
            rollup_policy=ROLLUP if rollup is None else rollup,
        )

    def test_integrated_flow_reads_worktime_and_builds_register_once(self):
        """One Worktime parse, one coverage check, one Output render per run."""
        from unittest.mock import patch
        import bhandara.payroll.contract_scoped_overtime as flow

        inputs = self.prepare()
        fingerprint = self.source_work()
        with (
            patch.object(flow, "read_worktime_xlsx",
                         wraps=flow.read_worktime_xlsx) as read,
            patch.object(flow, "validate_settlement_coverage",
                         wraps=flow.validate_settlement_coverage) as coverage,
            patch.object(flow, "build_payroll_register",
                         wraps=flow.build_payroll_register) as register,
        ):
            result = self.run_preview(inputs=inputs, sha=fingerprint)
        read.assert_called_once_with(self.workfile)
        self.assertEqual(coverage.call_count, 1)
        self.assertEqual(register.call_count, 1)
        self.assertEqual(result["payroll_register"]["rows"][0]["net_pay"], 3337500)
        self.assertEqual(
            result["payroll_register"]["rows"][0]["review_status"],
            "검증요청 · 잠정합계",
        )
        self.assertEqual(len(result["review_requests"]), 1)
        self.assertEqual(result["status"], "PARTIAL_REVIEW_ONLY")

    def test_no_overtime_equals_existing_attendance_preview_register_exactly(self):
        """Existing P1-5b-1 API/output is unchanged by Flow optimization."""
        from bhandara.payroll.attendance_preview import build_attendance_adjusted_preview

        inputs = self.prepare()
        fingerprint = self.source_work(data=[leave_fact()])
        attendance_plan = wage_plan(
            items=[event(treatment="UNPAID_LEAVE", amount=60000)],
            sha=fingerprint,
        )
        previous = build_attendance_adjusted_preview(
            inputs, self.workfile, settlement_plan=split_plan(),
            attendance_plan=attendance_plan, period_from=FROM, period_to=TO,
        )
        combined = build_contract_scoped_overtime_preview(
            inputs, self.workfile, settlement_plan=split_plan(),
            attendance_plan=attendance_plan, period_from=FROM, period_to=TO,
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry([], [], [rate(minimum_minutes=0)]),
            rate_policy=policy(
                reference_day_minutes_by_contract={"C-OLD": 480, "C-NEW": 480},
            ),
            rollup_policy=ROLLUP,
        )
        # Standalone P1-5b-1 still shows blank totals; integrated Flow now
        # displays known sums while retaining *identical item candidates*.
        current = combined["payroll_register"]
        historic = previous["payroll_register"]
        self.assertEqual(current["columns"], historic["columns"])
        for new_row, old_row in zip(current["rows"], historic["rows"]):
            for key, value in old_row.items():
                if key not in {"gross_pay", "deduction_total", "net_pay", "review_status"}:
                    self.assertEqual(new_row[key], value)
            self.assertEqual(new_row["gross_pay"], new_row["net_pay"])
            self.assertEqual(new_row["deduction_total"], 0)
            self.assertEqual(new_row["review_status"], "검증요청 · 잠정합계")
        # None = no overtime evidence submitted; [] = submitted empty
        # approved list. Preserve this existing, intentionally distinct
        # source-review status while comparing all the remaining evidence.
        self.assertEqual(
            previous["attendance_review"]["overtime_overlap_review"],
            "NOT_ASSESSED",
        )
        self.assertEqual(
            combined["attendance_review"]["overtime_overlap_review"],
            "LISTED_SEGMENTS_NO_OVERLAP",
        )
        self.assertEqual(
            {k: v for k, v in combined["attendance_review"].items()
             if k != "overtime_overlap_review"},
            {k: v for k, v in previous["attendance_review"].items()
             if k != "overtime_overlap_review"},
        )
        self.assertEqual(combined["worktime_review"], previous["worktime_review"])
        self.assertEqual(
            combined["settlement_review"]["employees"],
            previous["settlement_review"]["employees"],
        )
        self.assertEqual(combined["payroll_register"]["rows"][0]["gross_pay"], 3240000)

    def test_two_contract_rates_rollup_one_overtime_column_without_touching_core(self):
        rows = split()
        rows[0]["daily_base_rate"] = 96000
        rows[1]["daily_base_rate"] = 192000
        inputs = self.prepare(contracts=rows)
        result = self.run_preview(inputs=inputs)
        item = result["overtime_candidate_review"]["rows"][0]
        self.assertEqual(item["amount"], 54000)
        self.assertEqual(item["minutes"], 120)
        self.assertEqual(item["segment_ids"], ["A-NEW", "A-OLD"])
        self.assertEqual(len(result["overtime_candidate_review"]["contract_scopes"]), 2)
        self.assertEqual([s["contract_id"] for s in
                          result["overtime_candidate_review"]["contract_scopes"]],
                         ["C-NEW", "C-OLD"])
        self.assertEqual([s["candidates"][0]["amount"] for s in
                          result["overtime_candidate_review"]["contract_scopes"]],
                         [36000, 18000])
        view = result["payroll_register"]
        self.assertEqual(view["rows"][0]["base_pay"], 3300000)
        self.assertEqual(view["rows"][0]["overtime_allowances:OT01"], 54000)
        self.assertEqual(view["rows"][0]["gross_pay"], 3354000)
        self.assertEqual(view["rows"][0]["deduction_total"], 0)
        self.assertEqual(view["rows"][0]["net_pay"], 3354000)
        self.assertEqual(view["rows"][0]["review_status"], "검증요청 · 잠정합계")
        self.assertTrue(view["totals_are_provisional"])
        self.assertEqual(result["overtime_candidate_review"]["rollup_mode"],
                         "ROUND_PER_CONTRACT_RULE_THEN_SUM")
        self.assertEqual(result["evidence_review"]["source_authenticity"],
                         "NOT_AUTHENTICATED_BY_THIS_MODULE")
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        path = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(view, path)
        book = load_workbook(path)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            keys = [col["key"] for col in view["columns"]]
            self.assertEqual(book.active.cell(3, keys.index("overtime_allowances:OT01") + 1).value, 54000)
        finally:
            book.close()

    def test_unpaid_leave_and_two_contract_overtime_share_only_one_partial_register(self):
        inputs = self.prepare()
        work_rows = [
            leave_fact(), fact(day=OLD_DAY, actual_min=540),
            fact(day=NEW_DAY, actual_min=540),
        ]
        sha = self.source_work(data=work_rows)
        works = [evidence(OLD_DAY, "OLD"), evidence(NEW_DAY, "NEW")]
        approvals = [segment(OLD_DAY, "OLD"), segment(NEW_DAY, "NEW")]
        result = self.run_preview(
            inputs=inputs, work=works, approvals=approvals, sha=sha,
            adjustments=[event(treatment="UNPAID_LEAVE", amount=60000)],
        )
        view = result["payroll_register"]
        self.assertEqual(view["rows"][0]["base_pay"], 3240000)
        self.assertIn("overtime_allowances:OT01", [col["key"] for col in view["columns"]])
        self.assertEqual(result["attendance_review"]["base_reductions_by_employee"]["0001"], 60000)
        self.assertEqual(view["rows"][0]["gross_pay"], 3277500)
        self.assertEqual(view["rows"][0]["net_pay"], 3277500)
        self.assertEqual(result["attendance_review"]["overtime_overlap_review"],
                         "LISTED_SEGMENTS_NO_OVERLAP")

    def test_reject_approval_crossing_mid_cycle_contract_change(self):
        parent = verified(
            evidence_id="W-X", start="2026-11-15T23:00",
            end="2026-11-16T01:00", work_date="2026-11-15",
            verification_ref="V-X",
        )
        claim = approved(
            segment_id="A-X", work_evidence_id="W-X",
            start="2026-11-15T23:30", end="2026-11-16T00:30",
            work_date="2026-11-15",
            approval_ref="AP-X", classification_ref="CLS-X",
            base_inclusion_ref="BASE-X",
        )
        self.source_work(data=[fact(day="2026-11-15", actual_min=120)])
        with self.assertRaisesRegex(ContractOvertimeAdapterError, "crosses mid-period contract boundary"):
            self.run_preview(
                work=[parent], approvals=[claim],
                sha=sha256_file(self.workfile),
            )

    def test_missing_divisor_for_new_contract_blocks_instead_of_old_rate_inheritance(self):
        self.source_work()
        with self.assertRaisesRegex(OvertimeCandidateError, "reference_day_minutes missing"):
            self.run_preview(
                rate_config=policy(
                    reference_day_minutes_by_contract={"C-OLD": 480},
                ),
                sha=sha256_file(self.workfile),
            )

    def test_no_approval_without_evidence_has_no_overtime_column_and_stays_partial(self):
        self.source_work()
        result = self.run_preview(
            work=[], approvals=[], sha=sha256_file(self.workfile),
        )
        self.assertFalse(result["overtime_candidate_review"]["rows"])
        self.assertFalse(any(
            col["key"].startswith("overtime_allowances:")
            for col in result["payroll_register"]["columns"]
        ))
        self.assertEqual(result["approval_state"], "NOT_APPROVED")

    def test_rollup_policy_is_explicit_and_rate_policy_must_keep_old_rounding_contract(self):
        for bad in (
            {}, {"mode": "SILENT_REPRICE", "policy_ref": "VALID"},
            {"mode": "ROUND_PER_CONTRACT_RULE_THEN_SUM", "policy_ref": ""},
            {"mode": "ROUND_PER_CONTRACT_RULE_THEN_SUM", "policy_ref": "REF", "extra": True},
        ):
            with self.subTest(bad=bad), self.assertRaises(ContractOvertimeAdapterError):
                self.run_preview(rollup=bad)
        with self.assertRaisesRegex(ContractOvertimeAdapterError, "employee/rule/period rounding"):
            self.run_preview(rate_config=policy(rounding_scope="SEGMENT"))

    def test_source_approval_mismatch_or_revocation_is_blocked_before_amount(self):
        works = [evidence(OLD_DAY, "OLD"), evidence(NEW_DAY, "NEW")]
        segments = [segment(OLD_DAY, "OLD"), segment(NEW_DAY, "NEW")]
        registry = source_registry(works, segments, [rate(minimum_minutes=0)])
        registry["approvals"][0]["status"] = "REVOKED"
        with self.assertRaisesRegex(EvidenceReconciliationError, "CURRENT"):
            self.run_preview(work=works, approvals=segments, registry=registry)
        registry["approvals"][0]["status"] = "CURRENT"
        registry["approvals"][1]["rule_id"] = "OTHER"
        with self.assertRaisesRegex(EvidenceReconciliationError, "referenced source values differ"):
            self.run_preview(work=works, approvals=segments, registry=registry)

    def test_work_evidence_must_remain_in_same_contract_as_approved_segment(self):
        works = [evidence(OLD_DAY, "OLD"), evidence(NEW_DAY, "NEW")]
        claim = segment(NEW_DAY, "NEW")
        claim["work_evidence_id"] = "W-OLD"
        registry = source_registry(works, [claim], [rate(minimum_minutes=0)])
        with self.assertRaisesRegex(ContractOvertimeAdapterError, "different contracts"):
            self.run_preview(work=works, approvals=[claim], registry=registry)

    def test_input_leave_and_overtime_overlap_fails_closed(self):
        self.source_work(data=[leave_fact(
            work_date=OLD_DAY, leave_type="ANNUAL_HALF",
            leave_request_id="LV001",
        )])
        single_work = [
            verified(
                evidence_id="W-OLD", work_date=OLD_DAY,
                start=f"{OLD_DAY}T15:00", end=f"{OLD_DAY}T18:00",
                verification_ref="V-OLD",
            ),
        ]
        single_approval = [
            approved(
                segment_id="A-OLD", work_evidence_id="W-OLD",
                work_date=OLD_DAY, start=f"{OLD_DAY}T16:00", end=f"{OLD_DAY}T18:00",
                approval_ref="AP-OLD", classification_ref="CLS-OLD",
                base_inclusion_ref="BASE-OLD",
            ),
        ]
        leave = event(
            day=OLD_DAY, start_at=f"{OLD_DAY}T13:00", end_at=f"{OLD_DAY}T17:00",
        )
        with self.assertRaisesRegex(AttendanceSettlementError, "overlaps paid/unpaid"):
            self.run_preview(
                work=single_work, approvals=single_approval,
                adjustments=[leave], sha=sha256_file(self.workfile),
            )

    def test_review_only_evidence_employees_must_have_worktime_days(self):
        self.source_work(data=[fact(day=OLD_DAY, actual_min=540)])
        with self.assertRaisesRegex(OvertimeCandidateError, "Worktime actual minutes missing"):
            self.run_preview(sha=sha256_file(self.workfile))

    def test_regression_round_contract_level_before_rollup_is_not_global_rounding(self):
        rows = split()
        for row in rows:
            row["daily_base_rate"] = 192  # 1 minute -> 0.6 KRW each at 1.5x
        inputs = self.prepare(contracts=rows, rules=[rate(minimum_minutes=0)])
        works = [
            verified(evidence_id=f"W-{tag}", verification_ref=f"V-{tag}",
                     work_date=day, start=f"{day}T17:00", end=f"{day}T17:01")
            for tag, day in (("OLD", OLD_DAY), ("NEW", NEW_DAY))
        ]
        claims = [
            approved(segment_id=f"A-{tag}", work_evidence_id=f"W-{tag}",
                     work_date=day, start=f"{day}T17:00", end=f"{day}T17:01",
                     approval_ref=f"AP-{tag}", classification_ref=f"CLS-{tag}",
                     base_inclusion_ref=f"BASE-{tag}")
            for tag, day in (("OLD", OLD_DAY), ("NEW", NEW_DAY))
        ]
        self.source_work(data=[
            fact(day=OLD_DAY, actual_min=1), fact(day=NEW_DAY, actual_min=1),
        ])
        result = self.run_preview(
            inputs=inputs, work=works, approvals=claims,
            sha=sha256_file(self.workfile),
        )
        self.assertEqual(result["overtime_candidate_review"]["rows"][0]["amount"], 0)
        self.assertFalse(any(
            col["key"].startswith("overtime_allowances:")
            for col in result["payroll_register"]["columns"]
        ))
        self.assertEqual(result["overtime_candidate_review"]["candidate_rounding"],
                         "PER_CONTRACT_RULE_BEFORE_EMPLOYEE_ROLLUP")

    def test_fifty_employees_one_overtime_column_only_eligible_worker_populated(self):
        full = [
            contract(worker=f"{i:04d}", contract_id=f"C-{i:04d}")
            for i in range(1, 51)
        ]
        person = "0017"
        inputs = self.prepare(contracts=full)
        settlement = plan(
            facts=[employment(worker=f"{i:04d}") for i in range(1, 51)],
            allocations=[
                allocated(worker=f"{i:04d}", contract_id=f"C-{i:04d}")
                for i in range(1, 51)
            ],
        )
        w = verified(
            evidence_id="W17", employee_id=person,
            work_date=OLD_DAY, start=f"{OLD_DAY}T17:00",
            end=f"{OLD_DAY}T18:00", verification_ref="V17",
        )
        a = approved(
            segment_id="A17", work_evidence_id="W17", employee_id=person,
            work_date=OLD_DAY, start=f"{OLD_DAY}T17:00",
            end=f"{OLD_DAY}T18:00", approval_ref="AP17",
            classification_ref="CLS17", base_inclusion_ref="BASE17",
        )
        sha = self.source_work(data=[fact(worker=person, day=OLD_DAY, actual_min=540)])
        result = self.run_preview(
            inputs=inputs, settlement=settlement, work=[w], approvals=[a],
            sha=sha, rate_config=policy(
                reference_day_minutes_by_contract={"C-0017": 480},
            ),
        )
        view = result["payroll_register"]
        self.assertEqual(len(view["rows"]), 50)
        self.assertEqual(
            sum(row.get("overtime_allowances:OT01") is not None for row in view["rows"]), 1
        )
        self.assertIsNone(view["rows"][0].get("overtime_allowances:OT01"))
        self.assertIsNotNone(view["rows"][16]["overtime_allowances:OT01"])
        self.assertTrue(all(
            row["net_pay"] == row["gross_pay"] and row["deduction_total"] == 0
            for row in view["rows"]
        ))
        self.assertEqual(len(result["review_requests"]), 50)


if __name__ == "__main__":
    unittest.main()
