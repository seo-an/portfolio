"""Standalone Common transform: explicit header mapping into private output files.

Use Common directly for generic input cleanup, or omit it entirely when another
calculator already accepts the caller's data. Never invoke PTO/Worktime/Payroll,
infer company rules, approve records, or use network access.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from bhandara.common.io.input_layout import read_sheet
from bhandara.common.io.module_io import (
    ModuleIOError, load_module_io_contract, output_directory, resolve_input,
)
from bhandara.common.io.tabular import (
    TabularInputError, is_blank_value, read_csv_rows, read_json_rows,
)
from bhandara.common.runtime.artifacts import ArtifactBatch, ArtifactError
from bhandara.common.utils.hashing import sha256_file


class CommonRunError(ValueError):
    """The declared Common input or transformation contract is invalid."""


def load_mapping(path: Path) -> dict[str, Any]:
    """Validate mapping syntax before touching the source data or output."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommonRunError("mapping JSON is unreadable") from exc
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise CommonRunError("mapping schema_version must be 1.0")
    source_format = data.get("source_format")
    if source_format not in ("csv", "xlsx", "json"):
        raise CommonRunError("source_format must be csv, xlsx or json")
    fields = data.get("fields")
    if (not isinstance(fields, dict) or not fields
            or any(not isinstance(k, str) or not k.strip()
                   or not isinstance(v, str) or not v.strip()
                   for k, v in fields.items())):
        raise CommonRunError("fields must map nonempty output names to exact input names")
    if len(set(fields.values())) != len(fields):
        raise CommonRunError("two output fields may not ambiguously share an input name")
    required = data.get("required", [])
    if (not isinstance(required, list)
            or any(not isinstance(name, str) or name not in fields for name in required)
            or len(required) != len(set(required))):
        raise CommonRunError("required must be a unique list of declared output fields")
    if source_format == "xlsx":
        sheet = data.get("sheet")
        if sheet is not None and (not isinstance(sheet, str) or not sheet.strip()):
            raise CommonRunError("sheet must be a nonempty worksheet name")
    for key in ("encoding", "records_path"):
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            raise CommonRunError(f"{key} must be a nonempty string")
    return data


def read_source(path: Path, mapping: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """Read one explicitly declared format, preserving physical source row IDs."""
    source_format = mapping["source_format"]
    if path.suffix.lower() != "." + source_format:
        raise CommonRunError("source extension differs from explicit mapping source_format")
    if source_format == "csv":
        return read_csv_rows(path, {"encoding": mapping.get("encoding", "utf-8-sig")})
    if source_format == "json":
        return read_json_rows(
            path, {"encoding": mapping.get("encoding", "utf-8"),
                   "records_path": mapping.get("records_path")},
        )
    rows = read_sheet(
        path, tuple(mapping["fields"].values()), sheet_name=mapping.get("sheet")
    )
    return [
        (row["_row_number"], {k: v for k, v in row.items() if k != "_row_number"})
        for row in rows
    ]


def transform(
    rows: list[tuple[int, dict[str, Any]]], mapping: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map exact source names, retain row provenance, and reject missing facts.

    No aliases, calculations, inferred approvals or row-specific source values
    are included in issues. A rejected row blocks the whole output handoff.
    """
    fields = mapping["fields"]
    if not rows:
        raise CommonRunError("source contains no data rows")
    # An absent *column* is a structural error, not a nullable field.
    for source_name in fields.values():
        if any(source_name not in values for _, values in rows):
            raise CommonRunError(f"missing declared source column: {source_name}")
    required = set(mapping.get("required", []))
    accepted: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for number, values in rows:
        result = {
            out: values[source].strip() if isinstance(values[source], str)
            else values[source]
            for out, source in fields.items()
        }
        missing = [out for out in required if is_blank_value(result[out])]
        if missing:
            issues.append({
                "code": "COMMON_REQUIRED_VALUE_MISSING",
                "source_row": number,
                "fields": sorted(missing),
            })
        else:
            accepted.append({"source_row": number, "values": result})
    return accepted, issues


def publish(
    *,
    directory: Path, contract_version: str, run_id: str,
    source: Path, mapping_path: Path,
    input_hashes: Mapping[str, str],
    accepted: list[dict[str, Any]], issues: list[dict[str, Any]],
) -> dict[str, Path]:
    """Publish a new run only; reuse of a run ID never overwrites artifacts."""
    status = "BLOCKED" if issues else "PASS"
    names = ("common-result.json", "common-review.json", "common-run.json")
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    try:
        with ArtifactBatch(directory, names) as batch:
            batch.write_json("common-result.json", {
                "schema_version": "1.0",
                "module_id": "common",
                "status": status,
                "approved": False, "finalizable": False,
                "records": accepted,
                "source_sha256": input_hashes["source"],
                "accepted_count": len(accepted),
                "rejected_count": len(issues),
            })
            batch.write_json("common-review.json", {
                "schema_version": "1.0",
                "status": status,
                "approved": False, "finalizable": False,
                "issues": issues,
                "accepted_count": len(accepted),
                "rejected_count": len(issues),
            })
            batch.write_json("common-run.json", {
                "schema_version": "1.0",
                "module_id": "common",
                "module_version": contract_version,
                "run_id": run_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "approved": False, "finalizable": False,
                "input_sha256": dict(input_hashes),
                # No recursive hash of the receipt itself.
                "output_sha256": batch.staged_hashes(),
            })
            if (sha256_file(source) != input_hashes["source"]
                    or sha256_file(mapping_path) != input_hashes["mapping"]):
                raise CommonRunError("input file changed during Common processing")
            return batch.commit()
    except BaseException:
        # Only remove an empty directory created by this invocation.
        try:
            directory.rmdir()
        except OSError:
            pass
        raise


def run_common(
    private_data_root: str | Path, *, run_id: str | None = None,
    source_path: str | Path | None = None,
    mapping_path: str | Path | None = None,
) -> tuple[str, dict[str, Path]]:
    """Independent Common input -> validation/mapping -> private output."""
    contract = load_module_io_contract("common")
    chosen_id = run_id if run_id is not None else uuid4().hex
    destination = output_directory(contract, Path(private_data_root), chosen_id)
    source = resolve_input(
        contract, Path(private_data_root), "source", explicit_path=source_path
    )
    mapping_file = resolve_input(
        contract, Path(private_data_root), "mapping", explicit_path=mapping_path
    )
    input_hashes = {
        "source": sha256_file(source.path),
        "mapping": sha256_file(mapping_file.path),
    }
    config = load_mapping(mapping_file.path)
    rows = read_source(source.path, config)
    accepted, issues = transform(rows, config)
    paths = publish(
        directory=destination,
        contract_version=contract.module_version,
        run_id=chosen_id,
        source=source.path,
        mapping_path=mapping_file.path,
        input_hashes=input_hashes,
        accepted=accepted,
        issues=issues,
    )
    return ("BLOCKED" if issues else "PASS"), paths
