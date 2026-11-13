"""Optional review-only taxability sidecars for the PUBLIC Payroll CLI.

The migrated Payroll calculation engine and legacy result contracts are never
modified. Reads only already-calculated employee Payroll Results and the exact
selected company policy from its config. Outputs are separate JSON/XLSX files.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook

from .functions.payroll_standalone_input import load_standalone_inputs
from .functions.taxability_review import review_payment_taxability


class TaxabilitySidecarError(ValueError):
    pass


def _spreadsheet_cell(value: Any) -> Any:
    """Prevent source or policy reference text from becoming Excel formulas."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    string = str(value)
    return "'" + string if string.startswith(("=", "+", "-", "@")) else string


def _write_xlsx(path: Path, data: Mapping[str, Any]) -> None:
    if path.exists():
        raise TaxabilitySidecarError("taxability review workbook already exists")
    book = Workbook()
    try:
        summary = book.active
        summary.title = "Review Totals"
        summary.append(("field", "value"))
        for key, value in (
            ("status", data["status"]),
            ("payroll_period", data["payroll_period"]),
            ("classified_worker_count", data["classified_worker_count"]),
            ("missing_worker_count", len(data["missing_worker_ids"])),
            ("approved", False),
            ("finalizable", False),
            ("tax_and_insurance_computed", False),
            *sorted(data["totals"].items()),
            ("notice", data["notice"]),
        ):
            summary.append((_spreadsheet_cell(key), _spreadsheet_cell(value)))
        details = book.create_sheet("Taxability Candidates")
        fields = (
            "worker_id", "pay_item_code", "classification",
            "amount", "policy_ref", "source", "reason", "approved",
        )
        details.append(fields)
        for row in data["rows"]:
            details.append([
                _spreadsheet_cell(row.get(field)) for field in fields
            ])
        missing = book.create_sheet("Uncalculated Workers")
        missing.append(("worker_id", "status"))
        for worker in data["missing_worker_ids"]:
            missing.append((_spreadsheet_cell(worker), "NO_FINAL_PAYROLL"))
        for sheet in book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
        os.chmod(path, 0o600)
    finally:
        book.close()


def write_taxability_sidecars(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    scenario_id: str | None = None,
) -> dict[str, str]:
    """Partition provisional employee payments, never modify Payroll outputs.

    No sidecar when the original Payroll calculation was BLOCKED before
    producing a calculation artifact. Existing sidecars are never overwritten.
    """
    output = Path(output_dir)
    calculation = output / "payroll-calculation.json"
    if not calculation.is_file():
        return {}
    if calculation.is_symlink() or output.is_symlink():
        raise TaxabilitySidecarError("unsafe taxability input symlink")
    content = json.loads(calculation.read_text(encoding="utf-8"))
    if content.get("finalizable") is not False or content.get("ledger_committed") is not False:
        raise TaxabilitySidecarError(
            "taxability sidecar requires review-only Payroll calculation"
        )
    data = load_standalone_inputs(config_path, scenario_id=scenario_id)
    if content.get("payroll_period") != data["payroll_period"]:
        raise TaxabilitySidecarError("payroll period mismatch for taxability review")
    report = review_payment_taxability(
        content["composition"], data["company_policy"], data["registry"],
        payroll_period=data["payroll_period"],
        expected_worker_ids=data["expected_worker_ids"],
    )
    json_path = output / "taxability-review.json"
    xlsx_path = output / "taxability-review.xlsx"
    if json_path.exists() or xlsx_path.exists():
        raise TaxabilitySidecarError("taxability review artifact already exists")
    try:
        with json_path.open("x", encoding="utf-8") as handle:
            os.chmod(json_path, 0o600)
            json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        _write_xlsx(xlsx_path, report)
    except Exception:
        json_path.unlink(missing_ok=True)
        xlsx_path.unlink(missing_ok=True)
        raise
    return {
        "taxability_review_json": str(json_path),
        "taxability_review_xlsx": str(xlsx_path),
    }
