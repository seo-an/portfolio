"""Company-level batch input preparation and explicit roster reconciliation.

This boundary does not calculate wages or finalize a payroll run. It emits
canonical rows, complete provenance, and actionable findings for each source.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from .source_mapping import SourceMappingError, normalize_source
except ImportError:
    from source_mapping import SourceMappingError, normalize_source


class BatchInputError(ValueError):
    pass


def _finding(code: str, message: str, *, source: str,
             row_number: int | None = None, field: str = "",
             severity: str = "ERROR") -> dict[str, Any]:
    return {
        "code": code, "message": message, "source": source,
        "row_number": row_number, "field": field, "severity": severity,
    }


def load_manifest(path: str | Path) -> dict[str, Any]:
    file = Path(path)
    with file.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "0.1":
        raise BatchInputError("manifest schema_version must be 0.1")
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise BatchInputError("manifest.sources must be a nonempty object")
    return manifest


def _reconcile_roster(sources: dict[str, dict[str, Any]],
                      specs: Mapping[str, Any], roster_spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    roster_name = roster_spec.get("source", "employees")
    roster_field = roster_spec.get("key", "employee_id")
    worker_field = roster_spec.get("worker_id_field", "worker_id")
    if roster_name not in sources:
        return [_finding("ROSTER_SOURCE_MISSING", "roster source is not present",
                         source=str(roster_name))]
    roster_rows = sources[roster_name]["rows"]
    roster_lineage = [entry for entry in sources[roster_name]["lineage"]
                      if entry["status"] == "ACCEPTED"]
    roster: dict[str, str] = {}
    worker_ids: set[str] = set()
    findings: list[dict[str, Any]] = []
    for row, origin in zip(roster_rows, roster_lineage):
        number = origin["row_number"]
        key = str(row.get(roster_field) or "").strip()
        worker_id = str(row.get(worker_field) or "").strip()
        if not key or not worker_id:
            findings.append(_finding(
                "ROSTER_ID_MISSING", "roster requires both business key and worker_id",
                source=roster_name, row_number=number))
        elif key in roster or worker_id in worker_ids:
            findings.append(_finding(
                "ROSTER_DUPLICATE_KEY", "roster business key or worker_id is duplicated",
                source=roster_name, row_number=number))
        else:
            roster[key] = worker_id
            worker_ids.add(worker_id)
    if not roster:
        findings.append(_finding(
            "ROSTER_EMPTY", "no valid employees in roster",
            source=roster_name))
    for name, result in sources.items():
        if name == roster_name:
            continue
        link = specs[name].get("link_to_roster")
        if link is None:
            # Worker-level facts must match the roster even without a join.
            # employee_id requires an explicit link_to_roster declaration.
            accepted = []
            for row, entry in zip(
                result["rows"], [line for line in result["lineage"]
                                 if line["status"] == "ACCEPTED"]
            ):
                finding = None
                if "worker_id" in row and str(row["worker_id"]) not in worker_ids:
                    finding = _finding(
                        "UNKNOWN_ROSTER_MEMBER", "worker_id absent from roster",
                        source=name, row_number=entry["row_number"], field="worker_id")
                elif "employee_id" in row:
                    finding = _finding(
                        "ROSTER_LINK_REQUIRED", "employee_id requires link_to_roster mapping",
                        source=name, row_number=entry["row_number"], field="employee_id")
                if finding is not None:
                    result["issues"].append(finding)
                    findings.append(finding)
                    entry["status"] = "REJECTED"
                    entry["issue_codes"].append(finding["code"])
                    result["rejected_rows"] += 1
                else:
                    accepted.append(row)
            result["rows"] = accepted
            result["accepted_rows"] = len(accepted)
            continue
        if not isinstance(link, Mapping) or not str(link.get("source_field", "")).strip():
            raise BatchInputError(f"{name}.link_to_roster.source_field required")
        key_field = str(link["source_field"])
        accept: list[dict[str, Any]] = []
        index = 0
        for entry in result["lineage"]:
            if entry["status"] != "ACCEPTED":
                continue
            row = result["rows"][index]
            index += 1
            foreign = str(row.get(key_field, "")).strip()
            if not foreign or foreign not in roster:
                finding = _finding(
                    "UNKNOWN_ROSTER_MEMBER", "source references an employee absent from roster",
                    source=name, row_number=entry["row_number"], field=key_field)
                result["issues"].append(finding)
                findings.append(finding)
                entry["status"] = "REJECTED"
                entry["issue_codes"].append("UNKNOWN_ROSTER_MEMBER")
                result["rejected_rows"] += 1
                continue
            worker_id = roster[foreign]
            if "worker_id" in row and str(row["worker_id"]) != worker_id:
                finding = _finding(
                    "WORKER_ID_CONFLICT", "mapped worker_id conflicts with roster",
                    source=name, row_number=entry["row_number"], field="worker_id")
                result["issues"].append(finding)
                findings.append(finding)
                entry["status"] = "REJECTED"
                entry["issue_codes"].append("WORKER_ID_CONFLICT")
                result["rejected_rows"] += 1
                continue
            row["worker_id"] = worker_id
            entry["linked_roster_key"] = foreign
            accept.append(row)
        result["rows"] = accept
        result["accepted_rows"] = len(accept)
    return findings


def prepare_batch_inputs(
    manifest: Mapping[str, Any],
    *,
    input_dir: str | Path,
) -> dict[str, Any]:
    """Normalize all declared source files and retain failure details.

    Never silently delete a failed source. A bundle with ERROR findings is
    ineligible for payroll finalization regardless of any provisional results.
    """
    if manifest.get("schema_version") != "0.1":
        raise BatchInputError("unsupported manifest schema_version")
    period = manifest.get("payroll_period")
    if not isinstance(period, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise BatchInputError("payroll_period must be YYYY-MM")
    specs = manifest.get("sources")
    if not isinstance(specs, Mapping) or not specs:
        raise BatchInputError("manifest.sources must be a nonempty object")
    results: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    stages = []
    for name, spec in specs.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(spec, Mapping):
            raise BatchInputError("source names and specs must be mappings")
        try:
            result = normalize_source(name, spec, input_dir=input_dir)
        except (SourceMappingError, OSError, ValueError, KeyError) as exc:
            error = _finding("SOURCE_READ_FAILED",
                             f"source failed to load or map: {type(exc).__name__}: {exc}",
                             source=name)
            result = {
                "source": name, "source_file": str(spec.get("path", "")),
                "source_sha256": "", "total_rows": 0, "accepted_rows": 0,
                "rejected_rows": 0, "rows": [], "lineage": [], "issues": [error],
            }
        results[name] = result
        stages.append({
            "stage": f"normalize:{name}",
            "status": "ERROR" if any(f["severity"] == "ERROR" for f in result["issues"]) else "PASS",
            "input_count": result["total_rows"],
            "output_count": result["accepted_rows"],
        })
        findings.extend(result["issues"])
    roster_config = manifest.get("roster", {"source": "employees"})
    if not isinstance(roster_config, Mapping):
        raise BatchInputError("manifest.roster must be an object")
    # Roster errors in source input also make the entire batch non-finalizable.
    roster_findings = _reconcile_roster(results, specs, roster_config)
    findings.extend(roster_findings)
    if roster_findings:
        stages.append({"stage": "reconcile_roster", "status": "ERROR",
                       "input_count": None, "output_count": None})
    else:
        stages.append({"stage": "reconcile_roster", "status": "PASS",
                       "input_count": None, "output_count": None})
    # Source-level issues may have changed during roster reconciliation.
    for stage in stages:
        if stage["stage"].startswith("normalize:"):
            name = stage["stage"].partition(":")[2]
            if any(f["severity"] == "ERROR" for f in results[name]["issues"]):
                stage["status"] = "ERROR"
                stage["output_count"] = results[name]["accepted_rows"]
    blocking = any(f["severity"] in ("ERROR", "REVIEW") for f in findings)
    fingerprint = json.dumps(
        {
            "manifest": manifest,
            "input_hashes": {name: result["source_sha256"] for name, result in results.items()},
        },
        sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"),
    )
    return {
        "schema_version": "0.1",
        "payroll_period": period,
        "batch_id": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        "status": "BLOCKED" if blocking else "READY_FOR_CALCULATION",
        "finalizable": False,  # Input preparation must never grant finalization.
        "source_results": results,
        "issues": findings,
        "stages": stages,
    }
