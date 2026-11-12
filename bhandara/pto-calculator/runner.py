"""Public PTO CLI: legacy arithmetic retained, new local input/output boundary."""
from __future__ import annotations

import importlib
import json
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from bhandara.common.contracts.findings import Finding, RunStatus, Scope, Severity, summarize_status
from bhandara.common.runtime.artifacts import ArtifactBatch
from bhandara.common.runtime.receipt import build_receipt
from bhandara.common.utils.hashing import sha256_file
from .src.input_adapter import PTOInputError, load_pto_inputs


MODULE_ID = "pto-calculator"
MODULE_VERSION = "0.1.1"
MODULE_DIR = Path(__file__).resolve().parent
LOCAL_DATA_DIR = MODULE_DIR.parent / "data" / MODULE_ID
LEGAL_BASIS_FILE = MODULE_DIR / "resources" / "legal-basis.json"


def legal_basis_reference() -> dict[str, str]:
    """Bind every result to the reviewed sources without claiming legal finality."""
    with LEGAL_BASIS_FILE.open("r", encoding="utf-8") as stream:
        source = json.load(stream)
    return {
        "basis_id": source["basis_id"],
        "basis_version": source["basis_version"],
        "reviewed_at": source["reviewed_at"],
        "source_sha256": sha256_file(LEGAL_BASIS_FILE),
        "status": "review_only",
    }


class PTORunError(ValueError):
    """Invalid local CLI invocation or broken module contract."""


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise PTORunError(f"{field} must be YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise PTORunError(f"{field} must be YYYY-MM-DD") from exc
    if result.isoformat() != value:
        raise PTORunError(f"{field} must use canonical YYYY-MM-DD")
    return result


def load_config(path: Path) -> tuple[dict[str, Any], date, date, set[str]]:
    """Strict versioned settings. A wrong period must never produce a false PASS."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PTORunError(f"unable to read PTO config: {type(exc).__name__}") from exc
    if not isinstance(config, dict) or config.get("schema_version") != "1.0":
        raise PTORunError("config schema_version 1.0 required")
    period = config.get("period")
    if not isinstance(period, dict) or set(period) != {"from", "to"}:
        raise PTORunError("config.period requires exactly from and to dates")
    start = _date(period["from"], "period.from")
    end = _date(period["to"], "period.to")
    if start > end:
        raise PTORunError("period.from must be on/before period.to")
    if (end - start).days > 366 * 30:
        raise PTORunError("period exceeds 30 years; reduce the requested window")
    if not isinstance(config.get("files"), dict):
        raise PTORunError("config.files must be an object")
    allowlist = config.get("employee_allowlist", [])
    if (not isinstance(allowlist, list)
            or any(not isinstance(x, str) or not x.strip() or x != x.strip()
                   for x in allowlist)
            or len(allowlist) != len(set(allowlist))):
        raise PTORunError("employee_allowlist must be a list of unique employee IDs")
    return config, start, end, set(allowlist)


def _excel_safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _append_rows(sheet, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    sheet.append(columns)
    for row in rows:
        sheet.append([_excel_safe(row.get(column)) for column in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def make_workbook(payload: dict[str, Any], findings: list[Finding]) -> bytes:
    """Review-only XLSX. JSON is the authoritative exact-value artifact."""
    book = Workbook()
    try:
        sheet = book.active
        sheet.title = "Summary"
        _append_rows(sheet, ("field", "value"), [
            {"field": "Module", "value": MODULE_ID},
            {"field": "Status", "value": payload["status"]},
            {"field": "Legal basis version", "value": payload["legal_basis"]["basis_version"]},
            {"field": "Legal basis checked at", "value": payload["legal_basis"]["reviewed_at"]},
            {"field": "Period start", "value": payload["period"]["from"]},
            {"field": "Period end", "value": payload["period"]["to"]},
            {"field": "Calculated employees", "value": len(payload["results"])},
            {"field": "Review/error findings", "value": len(findings)},
            {"field": "Finalizable", "value": False},
            {"field": "Approved", "value": False},
        ])
        grant_rows: list[dict[str, Any]] = []
        unresolved_rows: list[dict[str, Any]] = []
        for employee in payload["results"]:
            ident = employee["employee_id"]
            for record in employee["grants"]:
                grant_rows.append({"employee_id": ident, **record})
            for record in employee["unresolved_grants"]:
                unresolved_rows.append({"employee_id": ident, **record})
        grants = book.create_sheet("Grants")
        for record in grant_rows:
            if record.get("raw_days") is not None:
                record["raw_days"] = str(record["raw_days"])
        _append_rows(grants, ("employee_id", "grant_date", "grant_type",
                             "service_year", "raw_days", "eligibility"), grant_rows)
        unresolved = book.create_sheet("Unresolved")
        for record in unresolved_rows:
            record["unresolved_reasons"] = json.dumps(
                record["unresolved_reasons"], default=str, ensure_ascii=False
            )
        _append_rows(unresolved, ("employee_id", "grant_date", "grant_type",
                                  "period_start", "period_end",
                                  "unresolved_reasons"), unresolved_rows)
        review = book.create_sheet("Review Required")
        _append_rows(review, ("code", "severity", "scope", "source",
                              "sheet", "row_number", "field", "message"),
                     [finding.to_dict() for finding in findings])
        output = BytesIO()
        book.save(output)
        return output.getvalue()
    finally:
        book.close()


def _employee_status(employee_id: str, status: str,
                     grants: int | None = None, unresolved: int | None = None) -> dict[str, Any]:
    return {
        "employee_id": employee_id, "status": status,
        "grants": grants, "unresolved": unresolved,
    }


def calculate_bundle(bundle, *, start: date, end: date,
                     employee_allowlist: set[str]) -> tuple[list[dict], list[dict], list[Finding]]:
    """Catch one employee failure without changing the legacy calculation formulas."""
    results: list[dict] = []
    statuses: list[dict] = []
    findings = list(bundle.findings)
    # The package directory has a hyphen; importlib supports its exact name
    # without mutating sys.path or importing any other business module.
    engine = importlib.import_module("bhandara.pto-calculator.src.engine")
    employees = bundle.handoff["employees"]
    listed = {row["employee_id"] for row in employees if isinstance(row.get("employee_id"), str)}
    unknown = employee_allowlist - listed
    if unknown:
        raise PTORunError("employee_allowlist contains IDs absent from supplied roster")
    selected = [row for row in employees
                if not employee_allowlist or row["employee_id"] in employee_allowlist]
    if not selected:
        # The input adapter already reported an empty/invalid roster. Publish
        # a review receipt rather than losing the error evidence.
        return results, statuses, findings
    for employee in selected:
        ident = employee["employee_id"]
        if bundle.global_block or ident in bundle.blocked_employee_ids:
            statuses.append(_employee_status(ident, "ERROR"))
            continue
        try:
            record = engine.calculate_employee(
                employee, bundle.handoff, start_date=start, end_date=end
            )
        except Exception as exc:
            findings.append(Finding(
                code="PTO_EMPLOYEE_CALCULATION_FAILED",
                severity=Severity.ERROR, scope=Scope.EMPLOYEE_PERIOD,
                message=f"Employee PTO computation failed: {type(exc).__name__}; review source inputs",
            ))
            statuses.append(_employee_status(ident, "ERROR"))
            continue
        results.append(record)
        pending = len(record["unresolved_grants"])
        if pending:
            findings.append(Finding(
                code="PTO_ELIGIBILITY_UNRESOLVED", severity=Severity.REVIEW,
                scope=Scope.EMPLOYEE_PERIOD,
                message="PTO grant eligibility is unresolved; do not finalize",
            ))
        statuses.append(_employee_status(
            ident, "REVIEW_REQUIRED" if pending else "CALCULATED",
            grants=len(record["grants"]), unresolved=pending,
        ))
    return results, statuses, findings


def run_pto(*, config_path: Path, input_dir: Path,
            output_dir: Path) -> tuple[RunStatus, dict[str, Path]]:
    config, start, end, allowed = load_config(config_path)
    if not input_dir.is_dir():
        raise PTORunError("input directory does not exist")
    if input_dir.resolve() == output_dir.resolve() or output_dir.resolve().is_relative_to(input_dir.resolve()):
        raise PTORunError("output directory cannot be the input directory or inside it")
    bundle = load_pto_inputs(input_dir, config["files"])
    results, employee_statuses, findings = calculate_bundle(
        bundle, start=start, end=end, employee_allowlist=allowed
    )
    status = summarize_status(findings)
    if bundle.global_block and status != RunStatus.ERROR:
        raise PTORunError("unassignable global input error not recorded")
    payload = {
        "schema_version": "1.0",
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "legacy_engine_source_commit": "296f909dd84bbdb6196be84568bd0e60775c7dbd",
        "legal_basis": legal_basis_reference(),
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "status": status.value,
        "finalizable": False,
        "approved": False,
        "source_hashes": bundle.source_hashes,
        "results": results,
        "employee_statuses": employee_statuses,
    }
    review = {
        "schema_version": "1.0", "status": status.value,
        "finalizable": False, "approved": False,
        "employee_statuses": employee_statuses,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }
    # Detect modifications after parsing and before output, in addition to the
    # per-workbook before/after hash check.
    for label, file_path in bundle.sources.items():
        if sha256_file(file_path) != bundle.source_hashes[label]:
            raise PTORunError("source file changed during PTO calculation")
    input_files = {
        "config": config_path,
        "legal_basis": LEGAL_BASIS_FILE,
        **bundle.sources,
    }
    names = ("pto-result.json", "pto-review.json", "pto-result.xlsx", "pto-run.json")
    with ArtifactBatch(output_dir, names) as batch:
        batch.write_json("pto-result.json", payload)
        batch.write_json("pto-review.json", review)
        batch.write_bytes("pto-result.xlsx", make_workbook(payload, findings))
        receipt = build_receipt(
            module_id=MODULE_ID, module_version=MODULE_VERSION,
            input_files=input_files, output_sha256=batch.staged_hashes(),
            findings=findings,
        )
        batch.write_json("pto-run.json", receipt)
        committed = batch.commit()
    return status, committed
