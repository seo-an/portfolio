"""Regression tests for Payroll known totals and the topic-grouped unittest runner."""
from __future__ import annotations

import unittest
from bhandara.payroll.output import build_payroll_register
from bhandara._tests.run import GroupedTestResult, classify_topic, format_summary


def employee(*, earnings=False, deductions=False, deductions_rows=None):
    return {
        "employee_id": "0001",
        "base_pay": 3000000,
        "fixed_allowances": [
            {"item_id": "MEAL", "label": "식대", "amount": 100000},
        ],
        "overtime_allowances": [
            {"item_id": "OVT", "label": "초과근무", "amount": 75000},
        ],
        "performance_bonuses": [],
        "deductions": [] if deductions_rows is None else deductions_rows,
        "earnings_complete": earnings,
        "deductions_complete": deductions,
    }


class KnownPayrollTotalsTests(unittest.TestCase):
    def test_incomplete_totals_are_known_sum_not_final_payment(self):
        row = employee(deductions_rows=[
            {"item_id": "NPS", "label": "연금", "amount": 140000},
        ])
        result = build_payroll_register([row], show_partial_totals=True)
        view = result["rows"][0]
        self.assertEqual(view["gross_pay"], 3175000)
        self.assertEqual(view["deduction_total"], 140000)
        self.assertEqual(view["net_pay"], 3035000)
        self.assertEqual(view["review_status"], "검증요청 · 잠정합계")
        self.assertEqual(
            result["review_flags"]["0001"],
            ["EARNINGS_UNVERIFIED", "DEDUCTIONS_UNVERIFIED"],
        )
        self.assertTrue(result["totals_are_provisional"])
        self.assertEqual(result["approval_state"], "NOT_APPROVED")

    def test_blank_dynamic_items_do_not_disappear_from_totals(self):
        second = employee(deductions_rows=[])
        second["employee_id"] = "0002"
        second["fixed_allowances"] = []
        second["overtime_allowances"] = []
        out = build_payroll_register([employee(), second], show_partial_totals=True)
        a, b = out["rows"]
        self.assertEqual(a["gross_pay"], 3175000)
        self.assertEqual(b["gross_pay"], 3000000)
        self.assertIsNone(b["fixed_allowances:MEAL"])
        self.assertIsNone(b["overtime_allowances:OVT"])
        self.assertEqual(b["deduction_total"], 0)
        self.assertEqual(b["net_pay"], 3000000)
        self.assertIn("DEDUCTIONS_UNVERIFIED", out["review_flags"]["0002"])

    def test_complete_totals_stay_review_required_and_not_approved(self):
        out = build_payroll_register(
            [employee(earnings=True, deductions=True)],
            show_partial_totals=True,
        )
        self.assertEqual(out["rows"][0]["gross_pay"], 3175000)
        self.assertEqual(out["rows"][0]["net_pay"], 3175000)
        self.assertEqual(out["rows"][0]["review_status"], "REVIEW_REQUIRED")
        self.assertFalse(out["totals_are_provisional"])
        self.assertEqual(out["review_flags"]["0001"], [])
        self.assertEqual(out["approval_state"], "NOT_APPROVED")

    def test_standalone_legacy_preview_keeps_blank_totals_by_default(self):
        out = build_payroll_register([employee()])
        self.assertIsNone(out["rows"][0]["gross_pay"])
        self.assertIsNone(out["rows"][0]["net_pay"])
        self.assertEqual(out["rows"][0]["review_status"], "PARTIAL_REVIEW_ONLY")
        with self.assertRaisesRegex(ValueError, "explicit boolean"):
            build_payroll_register([employee()], show_partial_totals=1)


class GroupedRunnerTests(unittest.TestCase):
    def test_classification_by_business_domain(self):
        self.assertEqual(
            classify_topic("test_payroll_insurance_candidates_p2.Any.test_one"), "Payroll"
        )
        self.assertEqual(
            classify_topic("test_worktime_output.Any.test_one"), "Worktime"
        )
        self.assertEqual(
            classify_topic("test_paid_time_off_closing.Any.test_one"), "Paid Time Off"
        )
        self.assertEqual(
            classify_topic("test_integrated_v2_example.Any.test_one"), "Integrated"
        )
        self.assertEqual(classify_topic("test_other.Any.test_one"), "Other")

    def test_counts_and_nonzero_exit_flag_for_failure_and_skip(self):
        class MiniTests(unittest.TestCase):
            def test_pass(self):
                self.assertTrue(True)

            def test_fail(self):
                self.fail("synthetic failure")

            @unittest.skip("synthetic skip")
            def test_skip(self):
                pass

            def test_subtest_failure(self):
                with self.subTest(i=1):
                    self.assertEqual(1, 2)

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(MiniTests)
        result = GroupedTestResult()
        suite.run(result)
        self.assertFalse(result.wasSuccessful())
        topic = result.by_topic["Other"]
        self.assertEqual(topic["PASS"], 1)
        self.assertEqual(topic["FAIL"], 2)
        self.assertEqual(topic["SKIP"], 1)
        self.assertEqual(sum(topic.values()), 4)
        self.assertIn("STATUS: FAIL", format_summary(result))


if __name__ == "__main__":
    unittest.main()
