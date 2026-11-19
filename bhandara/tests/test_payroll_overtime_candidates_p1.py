"""P1-2: independently verified, approved intervals -> pay candidates only."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from bhandara.payroll.overtime_candidates import (
    OvertimeCandidateError, calculate_overtime_candidates,
)
from bhandara.payroll.overtime_preview import build_overtime_candidate_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx


DAY = "2026-11-02"
MONTH_START, MONTH_END = "2026-11-01", "2026-11-30"


def policy(**changes):
    value = {
        "multiplier_semantics": "TOTAL_RATE",
        "rounding_scope": "EMPLOYEE_RULE_PERIOD",
        "rounding_mode": "DOWN",
        "reference_day_minutes_by_contract": {"C01": 480},
        "rule_labels": {"OT01": "연장근로수당"},
    }
    value.update(changes)
    return value


def work(**changes):
    row = {"employee_id": "0001", "work_date": DAY, "actual_min": 540}
    row.update(changes)
    return row


def verified(*, evidence_id="W001", start="2026-11-02T17:00", end="2026-11-02T18:00",
             **changes):
    row = {
        "evidence_id": evidence_id, "employee_id": "0001", "work_date": DAY,
        "start_at": start, "end_at": end,
        "verification_ref": "VERIFIED-SYNTHETIC",
    }
    row.update(changes)
    return row


def approved(*, segment_id="A001", start="2026-11-02T17:00", end="2026-11-02T18:00",
             **changes):
    row = {
        "segment_id": segment_id, "work_evidence_id": "W001",
        "employee_id": "0001", "work_date": DAY,
        "start_at": start, "end_at": end,
        "rule_id": "OT01", "approval_status": "APPROVED",
        "approval_ref": "APPROVED-SYNTHETIC",
        "classification_ref": "CLASSIFIED-SYNTHETIC",
        "base_pay_includes_time": False,
        "base_inclusion_ref": "BASE-EXCLUSION-SYNTHETIC",
    }
    row.update(changes)
    return row


def rate(**changes):
    row = deepcopy(SAMPLES["overtime_rules"])
    row.update(changes)
    return row


def calculate(*, contracts=None, worktime=None, rules=None, work_segments=None,
              approvals=None, rate_policy=None):
    return calculate_overtime_candidates(
        contracts if contracts is not None else {"0001": {
            "contract_id": "C01", "daily_base_rate": 96000}},
        worktime if worktime is not None else [work()],
        rules if rules is not None else [rate()],
        verified_work=work_segments if work_segments is not None else [verified()],
        approved_segments=approvals if approvals is not None else [approved()],
        policy=rate_policy if rate_policy is not None else policy(),
    )


class ApprovedOvertimeCandidateTests(unittest.TestCase):
    def test_explicit_approved_hour_calculates_18000_without_approval_claim(self):
        result = calculate()
        self.assertEqual(result["rows"], [{
            "employee_id": "0001", "item_id": "OT01",
            "label": "연장근로수당", "category": "OVERTIME", "minutes": 60,
            "amount": 18000, "segment_ids": ["A001"],
            "status": "CALCULATED_CANDIDATE_NOT_APPROVED",
        }])
        self.assertFalse(result["earnings_complete"])
        self.assertFalse(result["payable_minutes_finalized"])
        self.assertEqual(result["approval_state"], "NOT_APPROVED")

    def test_approved_minutes_not_clock_delta_or_extra_actual(self):
        result = calculate(worktime=[work(actual_min=600, clock_in_delta_min=90,
                                           clock_out_delta_min=90)])
        self.assertEqual(result["rows"][0]["minutes"], 60)
        self.assertEqual(result["rows"][0]["amount"], 18000)

    def test_base_pay_included_calculates_only_explicit_premium_difference(self):
        result = calculate(approvals=[approved(base_pay_includes_time=True)])
        self.assertEqual(result["rows"][0]["amount"], 6000)

    def test_missing_approval_or_verification_or_policy_rejected(self):
        for change in (
            {"approval_status": "PENDING"},
            {"approval_ref": ""},
            {"classification_ref": ""},
            {"base_inclusion_ref": ""},
            {"work_evidence_id": "NOT-VERIFIED"},
            {"base_pay_includes_time": None},
            {"start_at": "2026-11-02T16:00"},
        ):
            with self.subTest(change=change), self.assertRaises(OvertimeCandidateError):
                calculate(approvals=[approved(**change)])
        with self.assertRaisesRegex(OvertimeCandidateError, "verification_ref"):
            calculate(work_segments=[verified(verification_ref="")])

    def test_worktime_null_versus_zero_and_short_evidence(self):
        for actual in (None, 0, 30):
            with self.subTest(actual=actual), self.assertRaises(OvertimeCandidateError):
                calculate(worktime=[work(actual_min=actual)])
        with self.assertRaisesRegex(OvertimeCandidateError, "missing"):
            calculate(worktime=[])

    def test_minimum_threshold_is_review_block_not_silent_unpaid_zero(self):
        with self.assertRaisesRegex(OvertimeCandidateError, "below minimum"):
            calculate(approvals=[approved(end="2026-11-02T17:20")])

    def test_overnight_night_rule_requires_clock_window(self):
        n = rate(rule_id="N01", category="NIGHT", minimum_minutes=30,
                 qualifying_from="22:00", qualifying_to="06:00", daily_rate_multiplier="1.5")
        a = approved(rule_id="N01", start="2026-11-02T23:00",
                     end="2026-11-03T01:00", base_pay_includes_time=True)
        v = verified(start="2026-11-02T21:00", end="2026-11-03T02:00")
        result = calculate(worktime=[work(actual_min=300)], rules=[n],
                           work_segments=[v], approvals=[a],
                           rate_policy=policy(rule_labels={"N01": "야간근로 가산수당"}))
        self.assertEqual(result["rows"][0]["amount"], 12000)
        self.assertEqual(result["rows"][0]["minutes"], 120)
        with self.assertRaisesRegex(OvertimeCandidateError, "clock window"):
            calculate(rules=[rate(category="NIGHT")])
        with self.assertRaisesRegex(OvertimeCandidateError, "outside qualifying"):
            calculate(worktime=[work(actual_min=300)], rules=[n],
                      work_segments=[v],
                      approvals=[approved(rule_id="N01", start="2026-11-02T21:00",
                                          end="2026-11-02T22:00")],
                      rate_policy=policy(rule_labels={"N01": "야간근로 가산수당"}))

    def test_unrelated_holiday_classification_never_inferred_from_worktime(self):
        holiday = rate(rule_id="H01", category="HOLIDAY",
                       daily_rate_multiplier=2, minimum_minutes=0)
        result = calculate(rules=[holiday],
                           approvals=[approved(rule_id="H01")],
                           rate_policy=policy(rule_labels={"H01": "휴일근로수당"}))
        self.assertEqual(result["rows"][0]["amount"], 24000)
        self.assertEqual(result["rows"][0]["category"], "HOLIDAY")

    def test_overlapping_approvals_even_across_categories_are_blocked(self):
        n = rate(rule_id="N01", category="HOLIDAY", minimum_minutes=0)
        approvals = [
            approved(start="2026-11-02T17:00", end="2026-11-02T17:45"),
            approved(segment_id="A002", rule_id="N01", start="2026-11-02T17:30",
                     end="2026-11-02T18:00"),
        ]
        with self.assertRaisesRegex(OvertimeCandidateError, "overlapping intervals"):
            calculate(rules=[rate(), n], approvals=approvals,
                      rate_policy=policy(rule_labels={"OT01": "연장근로수당", "N01": "휴일근로수당"}))

    def test_overlapping_verified_work_and_duplicate_proof_id_block(self):
        with self.assertRaisesRegex(OvertimeCandidateError, "overlapping intervals"):
            calculate(work_segments=[
                verified(end="2026-11-02T17:40"),
                verified(evidence_id="W002", start="2026-11-02T17:30")])
        with self.assertRaisesRegex(OvertimeCandidateError, "duplicate evidence_id"):
            calculate(work_segments=[verified(), verified()])

    def test_explicit_rounding_modes_and_aggregation_by_employee_rule(self):
        v = [verified(evidence_id="W001", start="2026-11-02T17:00",
                      end="2026-11-02T17:15"),
             verified(evidence_id="W002", start="2026-11-02T17:15",
                      end="2026-11-02T17:30")]
        a = [approved(end="2026-11-02T17:15"),
             approved(segment_id="A002", work_evidence_id="W002",
                      start="2026-11-02T17:15", end="2026-11-02T17:30")]
        r = rate(minimum_minutes=0)
        contracts = {"0001": {"contract_id": "C01", "daily_base_rate": 99999}}
        down = calculate(contracts=contracts, rules=[r], work_segments=v, approvals=a)
        half_up = calculate(contracts=contracts, rules=[r], work_segments=v, approvals=a,
                            rate_policy=policy(rounding_mode="HALF_UP"))
        self.assertEqual(down["rows"][0]["amount"], 9374)
        self.assertEqual(half_up["rows"][0]["amount"], 9375)
        self.assertEqual(down["rows"][0]["minutes"], 30)
        self.assertEqual(down["rows"][0]["segment_ids"], ["A001", "A002"])

    def test_missing_divisor_label_or_multiplier_semantics_blocks(self):
        for changes in (
            {"reference_day_minutes_by_contract": {}},
            {"rule_labels": {}},
            {"rounding_scope": "SEGMENT"},
            {"rounding_mode": "DEFAULT"},
            {"multiplier_semantics": "PREMIUM_ONLY"},
        ):
            with self.subTest(change=changes), self.assertRaises(OvertimeCandidateError):
                calculate(rate_policy=policy(**changes))
        with self.assertRaisesRegex(OvertimeCandidateError, "smaller than included"):
            calculate(rules=[rate(daily_rate_multiplier="0.5")],
                      approvals=[approved(base_pay_includes_time=True)])

    def test_cross_date_or_more_than_24h_and_duplicate_approvals_block(self):
        with self.assertRaisesRegex(OvertimeCandidateError, "work_date must equal"):
            calculate(approvals=[approved(work_date="2026-11-03")])
        with self.assertRaisesRegex(OvertimeCandidateError, "24h"):
            calculate(work_segments=[verified(end="2026-11-04T18:00")])
        with self.assertRaisesRegex(OvertimeCandidateError, "duplicate segment_id"):
            calculate(approvals=[approved(), approved()])

    def test_empty_approvals_cannot_claim_zero_wages_or_completeness(self):
        result = calculate(work_segments=[], approvals=[])
        self.assertEqual(result["rows"], [])
        self.assertFalse(result["earnings_complete"])

    def test_excel_to_payroll_dynamic_candidate_column_stays_partial(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "payroll").mkdir()
            selected_roles = ("contracts", "allowance_assignments", "fixed_allowance_map",
                              "bonus_budget", "bonus_allocation", "overtime_rules")
            for role in selected_roles:
                spec = SCHEMA["workbooks"][role]
                data = [] if role in ("bonus_budget", "bonus_allocation") else [SAMPLES[role]]
                sheet = Workbook()
                sheet.active.title = spec["sheet"]
                sheet.active.append(spec["columns"])
                for row in data:
                    sheet.active.append([row.get(field) for field in spec["columns"]])
                sheet.save(root / "payroll" / spec["filename"])
                sheet.close()
            inputs = read_payroll_inputs(root, roles=selected_roles)
            xlsx = root / "worktime-result.xlsx"
            write_worktime_xlsx(
                {"schema_version": "0.1", "rows": [fact(actual_min=540)]}, xlsx,
            )
            preview = build_overtime_candidate_preview(
                inputs, xlsx, period_from=MONTH_START, period_to=MONTH_END,
                verified_work=[verified()], approved_segments=[approved()],
                rate_policy=policy(),
            )
            view = preview["payroll_register"]
            self.assertEqual(preview["status"], "PARTIAL_REVIEW_ONLY")
            self.assertEqual(preview["approval_state"], "NOT_APPROVED")
            self.assertIn("overtime_allowances:OT01", [column["key"] for column in view["columns"]])
            self.assertEqual(view["rows"][0]["overtime_allowances:OT01"], 18000)
            self.assertIsNone(view["rows"][0]["gross_pay"])
            self.assertIsNone(view["rows"][0]["deduction_total"])
            self.assertIsNone(view["rows"][0]["net_pay"])
            self.assertEqual(view["rows"][0]["review_status"], "PARTIAL_REVIEW_ONLY")
            self.assertEqual(preview["overtime_candidate_review"]["rows"][0]["amount"], 18000)
            output = root / "payroll-result.xlsx"
            write_payroll_result_xlsx(view, output)
            book = load_workbook(output)
            try:
                self.assertEqual(book.sheetnames, ["PAYROLL"])
                col = [x["key"] for x in view["columns"]].index("overtime_allowances:OT01") + 1
                self.assertEqual(book.active.cell(2, col).value, "연장근로수당")
                self.assertEqual(book.active.cell(3, col).value, 18000)
            finally:
                book.close()


if __name__ == "__main__":
    unittest.main()
