"""Synthetic unittest coverage for Tool allocation and independent expiry decisions."""
from __future__ import annotations

import importlib
import unittest
from datetime import date
from fractions import Fraction

allocation = importlib.import_module("bhandara.paid-time-off.allocation")
expiry = importlib.import_module(
    "bhandara.paid-time-off.expiry-carryover.calculation")


def grant(identifier, *, employee="E001", kind="연차", grant_date="2026-01-01",
          amount="1", start="2026-01-01", end="2026-12-31", source="ENT"):
    return dict(grant_id=identifier, employee_id=employee, leave_type=kind,
                grant_date=grant_date, available_days=amount, valid_from=start,
                expires_on=end, source_ref=source)


def request(identifier, *, employee="E001", kind="연차",
            day="2026-10-01", amount="1"):
    return dict(request_id=identifier, employee_id=employee, leave_type=kind,
                leave_date=day, deduction_days=amount)


class ToolAllocationTests(unittest.TestCase):
    def run_allocation(self, grants, requests, as_of=date(2026, 11, 18)):
        return allocation.allocate_usage(grants, requests, as_of_date=as_of)

    def test_earliest_expiry_then_grant_date_then_id(self):
        grants = [
            grant("G9", grant_date="2026-01-01", end="2026-12-31"),
            grant("G2", grant_date="2026-01-01", end="2026-10-31"),
            grant("G3", grant_date="2026-02-01", end="2026-10-31"),
            grant("G1", grant_date="2026-01-01", end="2026-10-31"),
        ]
        result = self.run_allocation(grants, [request("R1", amount="3")])
        self.assertEqual([r["grant_id"] for r in result["allocations"]],
                         ["G1", "G2", "G3"])
        self.assertTrue(all(r["status"] == "사용" for r in result["allocations"]))

    def test_use_date_must_be_within_externally_provided_window(self):
        grants = [
            grant("EARLY", end="2026-09-30"),
            grant("LATER", start="2026-11-01"),
        ]
        result = self.run_allocation(grants, [request("R1")])
        self.assertEqual(result["allocations"][0]["grant_id"], None)
        self.assertEqual(result["allocations"][0]["status"], "부족")
        self.assertEqual(result["shortages"][("E001", "연차")], Fraction(1))

    def test_no_cross_type_use_and_negative_shortage(self):
        grants = [grant("C1", kind="대휴", amount="10"),
                  grant("A1", amount="2")]
        result = self.run_allocation(grants, [request("R1", amount="5")])
        self.assertEqual([(r["grant_id"], r["allocated_days"])
                          for r in result["allocations"]],
                         [("A1", Fraction(2)), (None, Fraction(3))])
        self.assertEqual(result["shortages"][("E001", "연차")], Fraction(3))
        annual = next(r for r in result["summary"] if r["leave_type"] == "연차")
        self.assertEqual(annual["shortage_balance"], -3)
        self.assertEqual(annual["net_remaining_days"], -3)
        self.assertFalse(result["future_shortages"])
        self.assertEqual(next(r for r in result["balances"]
                              if r["grant_id"] == "C1")["remaining_days"], 10)

    def test_future_booking_does_not_reduce_actual_balance(self):
        grants = [grant("G1", amount="5")]
        requests = [request("Rpast", day="2026-11-10", amount="2"),
                    request("Rfuture", day="2026-12-10", amount="3")]
        result = self.run_allocation(grants, requests)
        self.assertEqual([r["status"] for r in result["allocations"]],
                         ["사용", "예약"])
        self.assertEqual(result["balances"][0]["remaining_days"], 3)
        self.assertEqual(result["balances"][0]["reserved_days"], 3)
        self.assertEqual(result["balances"][0]["remaining_after_reservations"], 0)

    def test_cancelled_request_is_not_rolled_back_with_plus_entry(self):
        grants = [grant("G1", amount="1", end="2026-10-31"),
                  grant("G2", amount="1", end="2026-12-31")]
        original = self.run_allocation(grants, [
            request("R1", day="2026-10-01"),
            request("R2", day="2026-10-15"),
        ])
        self.assertEqual([r["grant_id"] for r in original["allocations"]],
                         ["G1", "G2"])
        updated = self.run_allocation(grants, [
            request("R2", day="2026-10-15"),
        ])
        self.assertEqual([r["grant_id"] for r in updated["allocations"]], ["G1"])
        self.assertFalse(any(r["allocated_days"] < 0
                             for r in updated["allocations"]))

    def test_future_shortage_is_separate_from_actual_shortage(self):
        result = self.run_allocation([], [
            request("R1", amount="2", day="2026-11-01"),
            request("R2", amount="3", day="2026-12-01"),
        ])
        self.assertEqual(result["shortages"][("E001", "연차")], 2)
        self.assertEqual(result["future_shortages"][("E001", "연차")], 3)

    def test_future_confirmed_grant_only_usable_on_valid_date(self):
        grants = [grant("G2027", grant_date="2027-01-01",
                        start="2027-01-01", end="2027-12-31",
                        amount="15")]
        result = self.run_allocation(grants, [
            request("R1", day="2026-12-30", amount="1"),
            request("R2", day="2027-01-02", amount="1"),
        ])
        self.assertEqual([r["status"] for r in result["allocations"]],
                         ["예약부족", "예약"])
        self.assertEqual(result["balances"][0]["reserved_days"], 1)

    def test_fraction_stays_exact_and_negative_is_not_auto_offset(self):
        result = self.run_allocation(
            [grant("G1", amount="1")],
            [request("R1", amount=Fraction(4, 3))])
        self.assertEqual(result["shortages"][("E001", "연차")], Fraction(1, 3))
        self.assertEqual(allocation.quantity_text(Fraction(-1, 3)),
                         "-0.3333333")
        newer = self.run_allocation(
            [grant("G1", amount="1"), grant("G2", amount="15",
                grant_date="2027-01-01", start="2027-01-01",
                end="2027-12-31")],
            [request("R1", amount=Fraction(4, 3))])
        self.assertEqual(newer["shortages"][("E001", "연차")], Fraction(1, 3))
        self.assertEqual(next(r for r in newer["balances"]
                              if r["grant_id"] == "G2")["remaining_days"], 15)

    def test_duplicate_grant_blocks_bucket_instead_of_fabricating_shortage(self):
        result = self.run_allocation([
            grant("G1"), grant("G1")], [request("R1")])
        self.assertEqual(result["blocked_groups"], [("E001", "연차")])
        self.assertFalse(result["allocations"])
        self.assertFalse(result["shortages"])
        self.assertTrue(any("중복" in x["reason"] for x in result["issues"]))

    def test_invalid_validity_blocks_only_affected_bucket(self):
        broken = grant("Gbad")
        broken["expires_on"] = None
        result = self.run_allocation(
            [broken, grant("Cgood", kind="대휴")],
            [request("R1"), request("R2", kind="대휴")])
        self.assertEqual(result["blocked_groups"], [("E001", "연차")])
        self.assertEqual(len(result["allocations"]), 1)
        self.assertEqual(result["allocations"][0]["grant_id"], "Cgood")

    def test_request_date_duplicate_and_invalid_quantity_excluded(self):
        result = self.run_allocation(
            [grant("G1", amount="5")],
            [request("R1"), request("R1"),
             request("R2", amount="-2")])
        self.assertEqual(result["blocked_groups"], [("E001", "연차")])
        self.assertEqual(result["allocations"], [])
        self.assertEqual(result["shortages"], {})


class ExpiryCarryoverTests(unittest.TestCase):
    def test_closing_id_derives_period_without_repeated_date(self):
        expectations = {
            "Closing-1.4-2025": date(2025, 3, 31),
            "Closing-2.4-2025": date(2025, 6, 30),
            "Closing-3.4-2025": date(2025, 9, 30),
            "Closing-4.4-2025": date(2025, 12, 31),
            "Closing-1.4-2024": date(2024, 3, 31),
        }
        for identifier, day in expectations.items():
            self.assertEqual(expiry.closing_boundary(identifier), day)
        for invalid in ("Closing-5.4-2025", "Closing-1/4-2025",
                        "Closing-1.5-2025", "Closing-4.4-0000"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                expiry.closing_boundary(invalid)

    def test_expiry_vs_carryover_and_compensation_is_only_review(self):
        balances = [
            {**grant("A1", end="2026-12-31"), "remaining_days": Fraction(3)},
            {**grant("A2", end="2027-06-30"), "remaining_days": Fraction(2)},
            {**grant("C1", kind="대휴", end="2026-12-31"),
             "remaining_days": Fraction(1)},
            {**grant("ZERO"), "remaining_days": Fraction(0)},
        ]
        result = expiry.evaluate_expiry_carryover(
            balances, closing_id="Closing-4.4-2026",
            balance_as_of=date(2026, 12, 31))
        self.assertEqual([x["status"] for x in result["entries"]],
                         ["만료", "이월", "만료", "잔여 없음"])
        self.assertEqual(result["expiry_days"], 4)
        self.assertEqual(result["carryover_days"], 2)
        self.assertTrue(result["entries"][0]["compensation_review"])
        self.assertFalse(result["entries"][2]["compensation_review"])
        self.assertFalse(result["cash_payment_approved"])

    def test_expiry_requires_input_dates_and_never_guesses(self):
        broken = {**grant("A1"), "remaining_days": 2}
        broken["expires_on"] = None
        ok = {**grant("A2"), "remaining_days": 1}
        result = expiry.evaluate_expiry_carryover(
            [broken, ok], closing_id="Closing-4.4-2026",
            balance_as_of=date(2026, 12, 31))
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["grant_id"], "A2")
        self.assertEqual(result["errors"][0]["status"], "계산 제외")

    def test_pre_boundary_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "기준일"):
            expiry.evaluate_expiry_carryover(
                [], closing_id="Closing-4.4-2026",
                balance_as_of=date(2026, 11, 18))

    def test_negative_grant_balance_is_not_the_shortage_record(self):
        result = expiry.evaluate_expiry_carryover(
            [{**grant("A1"), "remaining_days": -3}],
            closing_id="Closing-4.4-2026",
            balance_as_of=date(2026, 12, 31))
        self.assertEqual(len(result["entries"]), 0)
        self.assertIn("음수 부족분", result["errors"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
