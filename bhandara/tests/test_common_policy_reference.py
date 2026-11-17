"""Common policy-source contract, without installing any business calculator."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bhandara.common.config.policy_reference import (
    PolicyReferenceError,
    default_reference,
    resolve_policy_reference,
)


class PolicyReferenceTests(unittest.TestCase):
    def test_inline_explicit_policy_wins(self) -> None:
        result = resolve_policy_reference("worktime-calculator", "company_policy", {
            "kind": "inline", "value": {"schema_version": "1.0", "rest": "verified"}
        })
        self.assertFalse(result.used_default)
        self.assertEqual(result.value["rest"], "verified")
        self.assertEqual(len(result.sha256), 64)

    def test_portfolio_default_reference_is_used_when_omitted(self) -> None:
        default = default_reference("pto-calculator", "legal_basis")
        self.assertEqual(default["kind"], "file")
        result = resolve_policy_reference("pto-calculator", "legal_basis")
        self.assertTrue(result.used_default)
        self.assertEqual(result.value["basis_id"], "KR-LSA-PTO")

    def test_no_invented_default_for_company_rules(self) -> None:
        self.assertIsNone(default_reference("payroll-calculator", "company_policy"))
        self.assertIsNone(default_reference("worktime-calculator", "labor_policy"))
        with self.assertRaisesRegex(PolicyReferenceError, "POLICY_DEFAULT_UNAVAILABLE"):
            resolve_policy_reference("payroll-calculator", "company_policy")

    def test_prepared_private_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "company.json").write_text('{"name":"test"}', encoding="utf-8")
            result = resolve_policy_reference("payroll-calculator", "company_policy", {
                "kind": "file", "root": "input", "path": "company.json"
            }, input_roots={"input": root})
            self.assertFalse(result.used_default)
            self.assertEqual(result.value, {"name": "test"})

    def test_explicit_missing_file_does_not_use_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(PolicyReferenceError, "POLICY_FILE_UNAVAILABLE"):
                resolve_policy_reference("pto-calculator", "legal_basis", {
                    "kind": "file", "root": "input", "path": "absent.json"
                }, input_roots={"input": Path(directory)})

    def test_unknown_root_and_root_override_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ref = {"kind": "file", "root": "unregistered", "path": "policy.json"}
            with self.assertRaisesRegex(PolicyReferenceError, "POLICY_ROOT_UNKNOWN"):
                resolve_policy_reference("payroll-calculator", "company_policy", ref)
            with self.assertRaisesRegex(PolicyReferenceError, "POLICY_ROOT_INVALID"):
                resolve_policy_reference("pto-calculator", "legal_basis",
                                         input_roots={"portfolio": Path(directory)})

    def test_symlink_and_parent_traversal_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.json").write_text("{}", encoding="utf-8")
            (root / "alias.json").symlink_to(root / "source.json")
            with self.assertRaisesRegex(PolicyReferenceError, "POLICY_SYMLINK_FORBIDDEN"):
                resolve_policy_reference("payroll-calculator", "company_policy", {
                    "kind": "file", "root": "input", "path": "alias.json"
                }, input_roots={"input": root})
            with self.assertRaisesRegex(PolicyReferenceError, "POLICY_PATH_INVALID"):
                resolve_policy_reference("payroll-calculator", "company_policy", {
                    "kind": "file", "root": "input", "path": "../external-not-allowed.json"
                }, input_roots={"input": root})

    def test_invalid_explicit_inline_never_falls_back(self) -> None:
        for ref in ({}, {"kind": "inline", "value": []}, {"kind": "drive", "id": "abc"}):
            with self.subTest(ref=ref):
                with self.assertRaises(PolicyReferenceError):
                    resolve_policy_reference("pto-calculator", "legal_basis", ref)

    def test_duplicate_json_object_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "duplicates.json").write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(PolicyReferenceError):
                resolve_policy_reference("payroll-calculator", "company_policy", {
                    "kind": "file", "root": "input", "path": "duplicates.json"
                }, input_roots={"input": root})


if __name__ == "__main__":
    unittest.main()
