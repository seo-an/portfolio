"""Validation and loading helpers for payroll workbook input contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from bhandara.common.contracts.payroll_diagnostic_catalog import get_common_diagnostic
from bhandara.common.contracts.pto_diagnostics import ACTION_REQUIRED, BLOCKED, ERROR, build_diagnostic


COMPENSATION_IDENTITY_COLUMNS = ("worker_id", "effective_from", "effective_to")
PAYROLL_INPUT_COLUMNS = (
    "worker_id",
    "pay_item_code",
    "amount",
    "quantity",
    "origin_pay_item_code",
    "origin_from",
    "origin_to",
    "note",
)


class PayrollInputError(RuntimeError):
    """Base error for actionable payroll input failures."""


class RequiredInputFileNotFoundError(PayrollInputError):
    """Raised when a required payroll workbook is missing."""

    def __init__(self, path: str | Path, expected: str) -> None:
        self.path = Path(path)
        self.expected = expected
        common = get_common_diagnostic("INPUT_FILE_NOT_FOUND")
        self.diagnostic = build_diagnostic(
            "INPUT_FILE_NOT_FOUND",
            ERROR,
            common["message"],
            states=[BLOCKED, ACTION_REQUIRED],
            category="ARTIFACT",
            action="Add or synchronize the workbook and retry.",
            context={"path": str(self.path), "expected": self.expected},
        )
        super().__init__(
            "\n".join(
                [
                    "[payroll-calculator] Required input file not found",
                    "",
                    f"File: {self.path}",
                    f"Expected: {self.expected}",
                    "Action: Add or synchronize the workbook and retry.",
                ]
            )
        )


class InputContractError(PayrollInputError):
    """Raised when a workbook exists but violates its declared contract."""

    def __init__(self, message: str) -> None:
        super().__init__(f"[payroll-calculator] Input contract validation failed: {message}")


def require_input_file(path: str | Path, expected: str) -> Path:
    resolved = Path(path)
    if not resolved.is_file():
        raise RequiredInputFileNotFoundError(resolved, expected)
    return resolved


def read_headers(path: str | Path, expected: str = "Payroll workbook") -> list[str]:
    workbook_path = require_input_file(path, expected)
    workbook = load_workbook(workbook_path, read_only=True, data_only=False)
    try:
        sheet = workbook.active
        header_rows = list(
            sheet.iter_rows(min_row=1, max_row=1, values_only=True)
        )
        headers = header_rows[0] if header_rows else ()
        return [str(value).strip() if value is not None else "" for value in headers]
    finally:
        workbook.close()


def validate_compensation_headers(headers: list[str], registry: dict[str, Any]) -> list[str]:
    if headers[:3] != list(COMPENSATION_IDENTITY_COLUMNS):
        raise InputContractError(f"compensation must start with {COMPENSATION_IDENTITY_COLUMNS}")

    codes = {item["code"]: item for item in registry["items"]}
    seen: set[str] = set()
    for code in headers[3:]:
        if not code:
            raise InputContractError("compensation contains an empty header")
        if code in seen:
            raise InputContractError(f"duplicate compensation column: {code}")
        seen.add(code)
        item = codes.get(code)
        if item is None:
            raise InputContractError(f"unknown compensation pay item: {code}")
        if "compensation" not in item["allowed_sources"]:
            raise InputContractError(f"{code} is not allowed from compensation")
        if item["type"] != "지급":
            raise InputContractError(f"{code} must be a payment item")
    return headers


def validate_payroll_input_headers(headers: list[str]) -> list[str]:
    if headers != list(PAYROLL_INPUT_COLUMNS):
        raise InputContractError(f"payroll input headers must be {PAYROLL_INPUT_COLUMNS}")
    return headers


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def validate_payroll_input_row(
    row: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one externally supplied payroll transaction row."""
    worker_id = row.get("worker_id")
    pay_item_code = row.get("pay_item_code")
    if not _has_value(worker_id):
        raise InputContractError("worker_id is required")
    if not _has_value(pay_item_code):
        raise InputContractError("pay_item_code is required")

    amount = row.get("amount")
    quantity = row.get("quantity")
    if not _has_value(amount) and not _has_value(quantity):
        raise InputContractError("amount or quantity must be provided")

    origin_from = row.get("origin_from")
    origin_to = row.get("origin_to")
    if _has_value(origin_from) != _has_value(origin_to):
        raise InputContractError(
            "origin_from and origin_to must be provided together"
        )

    if registry is not None:
        items = {item["code"]: item for item in registry["items"]}
        item = items.get(str(pay_item_code))
        if item is None:
            raise InputContractError(f"unknown payroll input pay item: {pay_item_code}")
        if "payroll_input" not in item.get("allowed_sources", []):
            raise InputContractError(
                f"{pay_item_code} is not allowed from payroll_input"
            )
        if item.get("trace_origin") and not _has_value(row.get("origin_pay_item_code")):
            raise InputContractError(
                f"{pay_item_code} requires origin_pay_item_code"
            )

    return row
