"""Read-only, fail-closed semantic regression checks for private Golden JSON.

No personally identifying values or monetary amounts appear in default diagnostics.
Only explicitly documented volatile metadata fields are removed. Every other
nested field (including reviews, zero versus null, and calculations) is compared.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_DIFFERENCES = 50

# Checked against Gearbox JSON writers at agent-config commit
# 296f909dd84bbdb6196be84568bd0e60775c7dbd.
PAYROLL_WORKFLOW_FILES = (
    ("workflow-run.json", "workflow-run"),
    ("01-normalized/normalized-input.json", "normalized-input"),
    ("01-normalized/review-report.json", "strict-json"),
    ("02-worktime/worktime-result.json", "worktime-result"),
    ("02-worktime/worktime-review.json", "strict-json"),
    ("04-payroll/payroll-calculation.json", "payroll-calculation"),
    ("04-payroll/payroll-review.json", "payroll-review"),
    ("04-payroll/policy-resolution.json", "policy-resolution"),
    ("04-payroll/provisional-payroll-register.json", "provisional-register"),
)
PROFILES = (
    "strict-json", "workflow-run", "pto-golden", "normalized-input",
    "worktime-result", "payroll-calculation", "payroll-review",
    "policy-resolution", "provisional-register", "payroll-workflow",
)


class GoldenCompareError(ValueError):
    """Malformed JSON, unsupported schema, or missing comparison artifact."""


@dataclass(frozen=True)
class Difference:
    pointer: str
    reason: str


def _pairs_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise GoldenCompareError("duplicate JSON object key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise GoldenCompareError("non-finite JSON number is prohibited")


def read_json(path: Path) -> Any:
    if not path.is_file():
        raise GoldenCompareError(f"JSON input is not a file: {path}")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise GoldenCompareError(f"JSON input exceeds size limit: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(
                handle, object_pairs_hook=_pairs_unique, parse_float=Decimal,
                parse_constant=_nonfinite,
            )
    except (UnicodeError, json.JSONDecodeError, OSError) as exc:
        raise GoldenCompareError(f"invalid or unreadable JSON input: {path} ({type(exc).__name__})") from exc


def _object(data: Any, label: str, fields: tuple[str, ...]) -> dict:
    if not isinstance(data, dict):
        raise GoldenCompareError(f"{label}: JSON object required")
    if any(key not in data for key in fields):
        raise GoldenCompareError(f"{label}: required contract fields missing")
    return data


def _review_only(data: dict, label: str, *, ledger: bool = False) -> None:
    if data["finalizable"] is not False:
        raise GoldenCompareError(f"{label}: finalizable must be false")
    if ledger and data["ledger_committed"] is not False:
        raise GoldenCompareError(f"{label}: ledger_committed must be false")


def project(data: Any, profile: str) -> Any:
    """Return a copy with only known transport metadata excluded."""
    data = copy.deepcopy(data)
    if profile == "strict-json":
        return data
    if profile == "pto-golden":
        root = _object(data, profile, ("baseline", "period", "source_hashes", "results", "source_commit"))
        if not isinstance(root["results"], list) or not root["results"]:
            raise GoldenCompareError("pto-golden: nonempty results list required")
        root.pop("source_commit")  # Original engine's Git commit differs after migration.
        return root
    if profile == "workflow-run":
        root = _object(data, profile, (
            "schema_version", "run_id", "payroll_period", "status", "finalizable",
            "comparison_required", "payment_approved", "ledger_committed",
            "started_at", "updated_at", "config_hashes", "stages",
        ))
        _review_only(root, profile, ledger=True)
        if root["payment_approved"] is not False or root["comparison_required"] is not True:
            raise GoldenCompareError("workflow-run: approval/review guard violated")
        if not isinstance(root["stages"], list) or not root["stages"]:
            raise GoldenCompareError("workflow-run: stages list required")
        for key in ("run_id", "started_at", "updated_at"):
            root.pop(key)
        for index, stage in enumerate(root["stages"]):
            stage = _object(stage, f"stage[{index}]", (
                "name", "status", "record_count", "issue_count", "message",
                "started_at", "ended_at", "artifacts", "artifact_sha256",
            ))
            if not isinstance(stage["artifacts"], dict) or not isinstance(stage["artifact_sha256"], dict):
                raise GoldenCompareError(f"stage[{index}]: artifact dictionaries required")
            stage["artifacts"] = sorted(stage["artifacts"].keys())
            for key in ("started_at", "ended_at", "artifact_sha256"):
                stage.pop(key)
        return root
    if profile == "normalized-input":
        return _object(data, profile, ("schema_version", "status", "sources"))
    if profile == "worktime-result":
        root = _object(data, profile, (
            "schema_version", "status", "finalizable", "rows", "close_receipt",
            "coverage_verified", "source_hashes",
        ))
        _review_only(root, profile)
        if root["close_receipt"] is not None or root["coverage_verified"] is not False:
            raise GoldenCompareError("worktime-result: unexpected close/coverage approval")
        return root
    if profile == "payroll-calculation":
        root = _object(data, profile, (
            "schema_version", "status", "finalizable", "ledger_committed",
            "composition", "expected_worker_ids",
        ))
        _review_only(root, profile, ledger=True)
        return root
    if profile == "payroll-review":
        root = _object(data, profile, (
            "schema_version", "status", "finalizable", "ledger_committed",
            "source_hashes", "issues", "worker_statuses",
        ))
        _review_only(root, profile, ledger=True)
        root.pop("source_hashes")  # Generated XLSX bytes can differ across runs.
        return root
    if profile == "policy-resolution":
        root = _object(data, profile, ("schema_version", "finalizable", "resolved_company_policy"))
        _review_only(root, profile)
        return root
    if profile == "provisional-register":
        root = _object(data, profile, (
            "schema_version", "status", "finalizable", "comparison_required",
            "payroll_period", "rows", "worker_count",
        ))
        _review_only(root, profile)
        if root["comparison_required"] is not True:
            raise GoldenCompareError("provisional-register: review guard violated")
        return root
    raise GoldenCompareError(f"unsupported single-file profile: {profile}")


def _pointer(parent: str, key: str) -> str:
    return parent + "/" + key.replace("~", "~0").replace("/", "~1")


def _diff(expected: Any, actual: Any, pointer: str, out: list[Difference]) -> None:
    if len(out) >= MAX_DIFFERENCES:
        return
    if type(expected) is not type(actual):
        out.append(Difference(pointer or "/", "JSON type changed"))
        return
    if isinstance(expected, dict):
        for key in sorted(expected.keys() | actual.keys()):
            path = _pointer(pointer, key)
            if key not in expected:
                out.append(Difference(path, "unexpected field"))
            elif key not in actual:
                out.append(Difference(path, "missing field"))
            else:
                _diff(expected[key], actual[key], path, out)
            if len(out) >= MAX_DIFFERENCES:
                break
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            out.append(Difference(pointer or "/", "list length changed"))
        for index, (left, right) in enumerate(zip(expected, actual)):
            _diff(left, right, _pointer(pointer, str(index)), out)
            if len(out) >= MAX_DIFFERENCES:
                break
    elif expected != actual:
        out.append(Difference(pointer or "/", "value changed"))


def compare(expected: Path, actual: Path, profile: str) -> list[Difference]:
    """Compare semantic artifacts; never modifies inputs or prints field values."""
    if profile not in PROFILES:
        raise GoldenCompareError(f"unsupported profile: {profile}")
    if profile == "payroll-workflow":
        if not expected.is_dir() or not actual.is_dir():
            raise GoldenCompareError("payroll-workflow: two output directories required")
        differences: list[Difference] = []
        for relative, subtype in PAYROLL_WORKFLOW_FILES:
            part = compare(expected / relative, actual / relative, subtype)
            for entry in part:
                if len(differences) >= MAX_DIFFERENCES:
                    return differences
                differences.append(Difference(f"/{relative}{entry.pointer}", entry.reason))
        return differences
    old = project(read_json(expected), profile)
    new = project(read_json(actual), profile)
    differences: list[Difference] = []
    _diff(old, new, "", differences)
    return differences
