"""P1-4: explicit concurrency by atomic minute intervals, never default stacking."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.payroll.overtime_candidates import OvertimeCandidateError
from bhandara.payroll.overtime_stacking import (
    OvertimeStackingError, review_approved_stacking,
)
from bhandara.payroll.evidence_preview import build_reconciled_overtime_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_overtime_candidates_p1 import (
    approved, calculate, policy, rate, verified, work,
)
from bhandara.tests.test_payroll_evidence_reconciliation_p1 import registry
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx


def stacking_policy(*, sets=None, **overrides):
    spec = {
        "mode": "EXPLICIT_CATEGORY_SETS",
        "policy_ref": "SYNTHETIC-STACK-2026",
        "same_category": "BLOCK",
        "base_component_policy": "CONSISTENT_INCLUSION_SINGLE_OWNER",
        "allowed_category_sets": (
            [{"categories": ["OVERTIME", "NIGHT"],
              "unpaid_base_owner": "OVERTIME"}] if sets is None else sets
        ),
    }
    spec.update(overrides)
    return spec


def night_rule():
    return rate(rule_id="N01", category="NIGHT", qualifying_from="22:00",
                qualifying_to="06:00", minimum_minutes=0,
                daily_rate_multiplier="1.5")


def holiday_rule():
    return rate(rule_id="H01", category="HOLIDAY", qualifying_from=None,
                qualifying_to=None, minimum_minutes=0,
                daily_rate_multiplier="2")


def night_approval(*, start="2026-11-02T22:00",
                   end="2026-11-02T23:00", **overrides):
    return approved(
        segment_id="A002", start=start, end=end, rule_id="N01",
        approval_ref="APPROVED-2",
        classification_ref="CLASS-2",
        base_pay_includes_time=False,
        base_inclusion_ref="BASE-EXCLUDED-2",
        **overrides,
    )


def pair(*, ov_start="2026-11-02T22:00", ov_end="2026-11-02T23:00",
         night_start="2026-11-02T22:00", night_end="2026-11-02T23:00"):
    return [
        approved(start=ov_start, end=ov_end),
        night_approval(start=night_start, end=night_end),
    ]


def candidate(*, approvals=None, config=None, work_segments=None, real_minutes=120,
              other_rules=None):
    choices = [rate(minimum_minutes=0), night_rule()]
    if other_rules:
        choices.extend(other_rules)
    return calculate(
        rules=choices,
        worktime=[work(actual_min=real_minutes)],
        work_segments=work_segments if work_segments is not None else [
            verified(start="2026-11-02T21:00", end="2026-11-02T23:00"),
        ],
        approvals=approvals if approvals is not None else pair(),
        rate_policy=policy(
            rule_labels={"OT01": "연장근로수당", "N01": "야간근로 가산수당",
                         "H01": "휴일근로수당", "OT02": "연장근로수당 2",
                         "E01": "조기근로수당"},
            **({"overlap_policy": config} if config is not None else {}),
        ),
    )


class PayrollOvertimeStackingTests(unittest.TestCase):
    def test_legacy_no_stacking_configuration_still_blocks_overlap(self):
        with self.assertRaisesRegex(OvertimeCandidateError, "stacking policy"):
            candidate()

    def test_explicit_overtime_night_adds_only_one_base_component(self):
        result = candidate(config=stacking_policy())
        items = {row["item_id"]: row for row in result["rows"]}
        self.assertEqual(items["OT01"]["amount"], 18000)
        self.assertEqual(items["N01"]["amount"], 6000)
        self.assertEqual(sum(row["amount"] for row in result["rows"]), 24000)
        self.assertEqual(result["stacking_review"]["status"], "EXPLICIT_POLICY_MATCHED")
        self.assertEqual(result["stacking_review"]["policy_ref"], "SYNTHETIC-STACK-2026")
        self.assertEqual(result["stacking_review"]["overlap_slices"][0]["overlap_minutes"], 60)
        self.assertEqual(result["approval_state"], "NOT_APPROVED")
        self.assertFalse(result["earnings_complete"])
        self.assertFalse(result["payable_minutes_finalized"])

    def test_mixed_base_inclusion_for_the_same_minutes_is_blocked(self):
        rows = pair()
        rows[1]["base_pay_includes_time"] = True
        with self.assertRaisesRegex(OvertimeCandidateError, "inconsistent base-pay inclusion"):
            candidate(approvals=rows, config=stacking_policy())

    def test_both_premiums_only_allowed_when_explicit_policy_approved(self):
        rows = pair()
        rows[0]["base_pay_includes_time"] = True
        rows[1]["base_pay_includes_time"] = True
        result = candidate(approvals=rows, config=stacking_policy())
        self.assertEqual([row["amount"] for row in result["rows"]], [6000, 6000])
        self.assertTrue(result["stacking_review"]["overlap_slices"][0]["base_prepaid"])
        self.assertIsNone(result["stacking_review"]["overlap_slices"][0]["ordinary_base_owner_segment_id"])

    def test_same_category_overlap_blocks_even_if_rules_differ(self):
        two_overtime = rate(rule_id="OT02", category="OVERTIME", minimum_minutes=0)
        a = approved(
            segment_id="A002", rule_id="OT02",
            approval_ref="APPROVED-2", classification_ref="CLASS-2",
            base_pay_includes_time=True, base_inclusion_ref="BASE-2",
            start="2026-11-02T22:00", end="2026-11-02T23:00",
        )
        with self.assertRaisesRegex(OvertimeCandidateError, "same-category"):
            candidate(approvals=[
                approved(start="2026-11-02T22:00", end="2026-11-02T23:00"), a
            ],
                      other_rules=[two_overtime],
                      config=stacking_policy(sets=[{"categories": ["OVERTIME", "NIGHT"],
                                           "unpaid_base_owner": "OVERTIME"}]))

    def test_overlaps_of_early_and_late_not_auto_authorized(self):
        early = rate(rule_id="E01", category="EARLY", minimum_minutes=0)
        rows = pair()
        rows[1]["rule_id"] = "E01"
        with self.assertRaisesRegex(OvertimeCandidateError, "not explicitly permitted"):
            candidate(approvals=rows, other_rules=[early],
                      config=stacking_policy())

    def test_touching_time_boundaries_are_not_overlap(self):
        rows = pair(ov_start="2026-11-02T21:30", ov_end="2026-11-02T22:00",
                    night_start="2026-11-02T22:00", night_end="2026-11-02T22:30")
        result = candidate(approvals=rows)
        self.assertEqual(result["stacking_review"]["status"], "NO_OVERLAP")
        self.assertEqual(result["stacking_review"]["overlap_slices"], [])

    def test_partially_overlapping_intervals_split_exactly(self):
        rows = pair(night_start="2026-11-02T22:30",
                    night_end="2026-11-02T23:30")
        result = candidate(
            approvals=rows,
            config=stacking_policy(),
            work_segments=[verified(start="2026-11-02T21:00",
                                    end="2026-11-02T23:30")],
            real_minutes=150,
        )
        slices = result["stacking_review"]["overlap_slices"]
        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0]["start_at"], "2026-11-02T22:30")
        self.assertEqual(slices[0]["end_at"], "2026-11-02T23:00")
        self.assertEqual(slices[0]["overlap_minutes"], 30)
        self.assertEqual([x["minutes"] for x in result["rows"]], [60, 60])

    def test_triple_combination_requires_its_own_exact_category_set(self):
        rows = pair()
        rows.append(approved(
            segment_id="A003", rule_id="H01",
            start="2026-11-02T22:00", end="2026-11-02T23:00",
            approval_ref="APPROVED-3", classification_ref="CLASS-3",
            base_pay_includes_time=False, base_inclusion_ref="BASE-3",
        ))
        with self.assertRaisesRegex(OvertimeCandidateError, "not explicitly permitted"):
            candidate(approvals=rows, config=stacking_policy(),
                      other_rules=[holiday_rule()])
        result = candidate(
            approvals=rows, other_rules=[holiday_rule()],
            config=stacking_policy(sets=[
                {"categories": ["OVERTIME", "NIGHT", "HOLIDAY"],
                 "unpaid_base_owner": "OVERTIME"},
            ]),
        )
        amounts = {item["item_id"]: item["amount"] for item in result["rows"]}
        self.assertEqual(amounts, {"H01": 12000, "N01": 6000, "OT01": 18000})
        self.assertEqual(result["stacking_review"]["overlap_slices"][0]["categories"],
                         ["HOLIDAY", "NIGHT", "OVERTIME"])

    def test_partial_triple_requires_all_active_sets(self):
        rows = pair()
        rows.append(approved(
            segment_id="A003", rule_id="H01",
            start="2026-11-02T22:30", end="2026-11-02T23:00",
            approval_ref="APPROVED-3", classification_ref="CLASS-3",
            base_pay_includes_time=False, base_inclusion_ref="BASE-3",
        ))
        with self.assertRaisesRegex(OvertimeCandidateError, "not explicitly permitted"):
            candidate(approvals=rows, other_rules=[holiday_rule()],
                      config=stacking_policy(sets=[
                          {"categories": ["OVERTIME", "NIGHT", "HOLIDAY"],
                           "unpaid_base_owner": "OVERTIME"},
                      ]))
        result = candidate(approvals=rows, other_rules=[holiday_rule()],
                           config=stacking_policy(sets=[
                               {"categories": ["OVERTIME", "NIGHT"],
                                "unpaid_base_owner": "OVERTIME"},
                               {"categories": ["OVERTIME", "NIGHT", "HOLIDAY"],
                                "unpaid_base_owner": "OVERTIME"},
                           ]))
        self.assertEqual([x["overlap_minutes"] for x in
                          result["stacking_review"]["overlap_slices"]], [30, 30])

    def test_overnight_overlap_preserves_start_day_and_next_day(self):
        rows = [
            approved(start="2026-11-02T23:00", end="2026-11-03T01:00"),
            night_approval(start="2026-11-02T23:00", end="2026-11-03T01:00"),
        ]
        result = candidate(
            approvals=rows,
            config=stacking_policy(),
            work_segments=[verified(start="2026-11-02T22:00",
                                    end="2026-11-03T01:00")],
            real_minutes=180,
        )
        self.assertEqual(result["stacking_review"]["overlap_slices"][0]["overlap_minutes"], 120)
        self.assertEqual([x["amount"] for x in result["rows"]], [12000, 36000])

    def test_source_stacking_rejects_non_minute_boundaries(self):
        from datetime import datetime
        rows = [{
            "employee_id": "0001", "segment_id": "A001",
            "start_at": datetime(2026, 11, 2, 22, 0, 5),
            "end_at": datetime(2026, 11, 2, 23, 0),
            "category": "OVERTIME", "base_pay_includes_time": False,
        }]
        with self.assertRaisesRegex(OvertimeStackingError, "valid naive interval"):
            review_approved_stacking(rows, overlap_policy=None)

    def test_sub_one_x_overlap_component_cannot_be_hidden_by_other_minutes(self):
        low_night = rate(
            rule_id="N01", category="NIGHT", qualifying_from="22:00",
            qualifying_to="06:00", minimum_minutes=0,
            daily_rate_multiplier="0.5",
        )
        with self.assertRaisesRegex(OvertimeCandidateError, "negative premium"):
            calculate(
                rules=[rate(minimum_minutes=0), low_night],
                worktime=[work(actual_min=120)],
                work_segments=[verified(start="2026-11-02T21:00",
                                        end="2026-11-02T23:00")],
                approvals=pair(),
                rate_policy=policy(
                    rule_labels={"OT01": "연장", "N01": "야간"},
                    overlap_policy=stacking_policy(),
                ),
            )

    def test_no_policy_does_not_block_independent_employees_simultaneously(self):
        from datetime import datetime
        a = {"employee_id": "0001", "segment_id": "A001",
             "start_at": datetime(2026, 11, 2, 22, 0),
             "end_at": datetime(2026, 11, 2, 23, 0),
             "category": "OVERTIME", "base_pay_includes_time": False}
        b = dict(a, employee_id="0002", segment_id="A002", category="NIGHT")
        result = review_approved_stacking([a, b], overlap_policy=None)
        self.assertEqual(result["status"], "NO_OVERLAP")

    def test_invalid_policy_fail_closed_even_without_overlap(self):
        for overrides in (
            {"mode": "ALLOW_ALL"},
            {"same_category": "ALLOW"},
            {"base_component_policy": "COUNT_ALL_BASES"},
            {"policy_ref": ""},
            {"allowed_category_sets": [
                {"categories": ["OVERTIME", "OVERTIME"], "unpaid_base_owner": "OVERTIME"}]},
            {"allowed_category_sets": [
                {"categories": ["OVERTIME", "UNKNOWN"], "unpaid_base_owner": "OVERTIME"}]},
            {"allowed_category_sets": [
                {"categories": ["OVERTIME", "NIGHT"], "unpaid_base_owner": "OVERTIME"},
                {"categories": ["NIGHT", "OVERTIME"], "unpaid_base_owner": "OVERTIME"}]},
            {"allowed_category_sets": [
                {"categories": ["OVERTIME", "NIGHT", "HOLIDAY", "EARLY"],
                 "unpaid_base_owner": "OVERTIME"}]},
            {"allowed_category_sets": [
                {"categories": ["OVERTIME", "NIGHT"], "unpaid_base_owner": "HOLIDAY"}]},
            {"allowed_category_sets": None},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(OvertimeCandidateError):
                candidate(config=stacking_policy(**overrides))
        with self.assertRaises(OvertimeCandidateError):
            candidate(config=dict(stacking_policy(), unexpected=True))

    def test_stacking_slices_never_prove_source_authenticity_or_final_pay(self):
        result = candidate(config=stacking_policy())
        review = result["stacking_review"]
        self.assertEqual(review["legal_compliance"], "NOT_ASSESSED")
        self.assertEqual(review["approval_state"], "NOT_APPROVED")
        self.assertNotIn("gross_pay", result)
        self.assertNotIn("net_pay", result)

    def test_reconciled_worktime_and_payroll_xlsx_with_stacked_columns(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "payroll").mkdir()
            roles = ("contracts", "allowance_assignments", "fixed_allowance_map",
                     "bonus_budget", "bonus_allocation", "overtime_rules")
            for role in roles:
                spec = SCHEMA["workbooks"][role]
                book = Workbook()
                book.active.title = spec["sheet"]
                book.active.append(spec["columns"])
                if role == "overtime_rules":
                    values = [rate(minimum_minutes=0), night_rule()]
                elif role in ("bonus_budget", "bonus_allocation"):
                    values = []
                else:
                    values = [SAMPLES[role]]
                for row in values:
                    book.active.append([row.get(col) for col in spec["columns"]])
                book.save(root / "payroll" / spec["filename"])
                book.close()
            inputs = read_payroll_inputs(root, roles=roles)
            worktime_xlsx = root / "worktime-result.xlsx"
            write_worktime_xlsx(
                {"schema_version": "0.1", "rows": [fact(actual_min=120)]},
                worktime_xlsx,
            )
            work_claims = [verified(start="2026-11-02T21:00",
                                    end="2026-11-02T23:00")]
            approvals = pair()
            source = registry(
                works=[dict(work_claims[0], status="VERIFIED")],
                approvals=[dict(item, status="CURRENT") for item in approvals],
            )
            source["classifications"].append({
                "classification_ref": "CLASS-2", "segment_id": "A002",
                "rule_id": "N01", "category": "NIGHT",
                "policy_ref": "EXAMPLE-ONLY", "status": "VERIFIED",
            })
            source["base_inclusions"].append({
                "base_inclusion_ref": "BASE-EXCLUDED-2", "segment_id": "A002",
                "base_pay_includes_time": False, "status": "VERIFIED",
            })
            result = build_reconciled_overtime_preview(
                inputs, worktime_xlsx, period_from="2026-11-01",
                period_to="2026-11-30",
                verified_work=work_claims, approved_segments=approvals,
                evidence_registry=source,
                rate_policy=policy(
                    rule_labels={"OT01": "연장근로수당", "N01": "야간근로 가산수당"},
                    overlap_policy=stacking_policy(),
                ),
            )
            register = result["payroll_register"]
            self.assertEqual(register["rows"][0]["overtime_allowances:OT01"], 18750)
            self.assertEqual(register["rows"][0]["overtime_allowances:N01"], 6250)
            self.assertIsNone(register["rows"][0]["gross_pay"])
            self.assertIsNone(register["rows"][0]["net_pay"])
            self.assertEqual(register["rows"][0]["review_status"], "PARTIAL_REVIEW_ONLY")
            self.assertEqual(result["approval_state"], "NOT_APPROVED")
            self.assertEqual(result["evidence_review"]["source_authenticity"],
                             "NOT_AUTHENTICATED_BY_THIS_MODULE")
            output = root / "payroll-result.xlsx"
            write_payroll_result_xlsx(register, output)
            book = load_workbook(output)
            try:
                self.assertEqual(book.sheetnames, ["PAYROLL"])
                keys = [col["key"] for col in register["columns"]]
                for key, expected in (
                    ("overtime_allowances:OT01", 18750),
                    ("overtime_allowances:N01", 6250),
                ):
                    col = keys.index(key) + 1
                    self.assertEqual(book.active.cell(3, col).value, expected)
            finally:
                book.close()


if __name__ == "__main__":
    unittest.main()
