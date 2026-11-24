import importlib
import json
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

preflight = importlib.import_module("bhandara.paid-time-off.input_preflight")
runner = importlib.import_module("bhandara.paid-time-off.runner")


class PtoInputPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private-file.xlsx"

    def workbook(self, sheets):
        book = Workbook()
        book.remove(book.active)
        for name, rows in sheets.items():
            sheet = book.create_sheet(name)
            for row in rows:
                sheet.append(row)
        book.save(self.path)
        book.close()

    def inspect(self):
        before = self.path.read_bytes()
        report = preflight.inspect_input(self.path)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.path])
        self.assertFalse(report["approved"])
        self.assertNotIn("private-file", json.dumps(report))
        return {(x["module"], x["role"]): x for x in report["checks"]}

    def test_employee_shared_role(self):
        self.workbook({"재직자": [("employee_id", "hire_date"), ("SECRET-ID", "2024-01-01")],
                       "퇴사자": [("employee_id", "hire_date")]})
        result = self.inspect()
        for module in ("entitlement", "closing"):
            self.assertEqual(result[module, "employee"]["status"], "MATCH")
        self.assertNotIn("SECRET-ID", json.dumps(result["entitlement", "employee"]))

    def test_closing_only_roster(self):
        self.workbook({"재직자": [("employee_id",), ("123",)],
                       "퇴사자": [("employee_id",)]})
        result = self.inspect()
        self.assertEqual(result["closing", "employee"]["status"], "MATCH")
        self.assertEqual(result["entitlement", "employee"]["status"], "REJECTED")

    def test_missing_approved_headers(self):
        self.workbook({"승인휴가": [("employee_id",)]})
        check = self.inspect()["deduction-quantity", "approved_leave"]
        self.assertEqual(check["status"], "MISSING_HEADERS")
        self.assertTrue(check["missing_headers"])

    def test_complete_approved_headers(self):
        self.workbook({"승인휴가": [runner.APPROVED_LEAVE_COLUMNS]})
        self.assertEqual(self.inspect()["deduction-quantity", "approved_leave"]["status"], "MATCH")

    def test_attendance(self):
        self.workbook({"근태결과": [runner.ATTENDANCE_COLUMNS]})
        self.assertEqual(self.inspect()["entitlement", "attendance"]["status"], "MATCH")

    def test_invalid_workbook(self):
        self.path.write_bytes(b"not a workbook")
        self.assertTrue(all(x["status"] == "REJECTED" for x in self.inspect().values()))

    def test_multiple_roles_not_collapsed(self):
        self.workbook({"근태결과": [runner.ATTENDANCE_COLUMNS],
                       "승인휴가": [runner.APPROVED_LEAVE_COLUMNS]})
        matches = [key for key, check in self.inspect().items() if check["status"] == "MATCH"]
        self.assertEqual(set(matches), {("entitlement", "attendance"),
                                         ("deduction-quantity", "approved_leave")})


if __name__ == "__main__":
    unittest.main()
