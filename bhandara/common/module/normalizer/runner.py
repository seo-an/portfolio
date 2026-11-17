"""Standalone normalizer: explicit source -> validation/mapping -> output.

Its only internal import is the sibling paths module. There is no dependency
on bhandara.common.io/runtime/config, other calculators or Gearbox.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .paths import NormalizerPathError, resolve_paths, MODULE_ID

RESULT = "normalizer-result.json"
REVIEW = "normalizer-review.json"
RECEIPT = "normalizer-run.json"
VERSION = "0.1.0"


class NormalizerRunError(ValueError):
    """The standalone normalizer cannot safely process the declared input."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> str:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise NormalizerRunError("non-finite number in source")
        return format(value, "f")
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    raise TypeError(f"unsupported source value: {type(value).__name__}")


def load_mapping(path: Path) -> dict[str, Any]:
    """Validate caller-provided exact header map before reading source."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise NormalizerRunError("mapping JSON is unreadable") from exc
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise NormalizerRunError("mapping schema_version must be 1.0")
    if data.get("source_format") not in ("csv", "xlsx", "json"):
        raise NormalizerRunError("source_format must be csv, xlsx or json")
    fields = data.get("fields")
    if (not isinstance(fields, dict) or not fields
            or any(not isinstance(k, str) or not k.strip()
                   or not isinstance(v, str) or not v.strip()
                   for k, v in fields.items())
            or len(set(fields.values())) != len(fields)):
        raise NormalizerRunError("fields must map unique exact input names to output names")
    required = data.get("required", [])
    if (not isinstance(required, list) or len(set(required)) != len(required)
            or any(not isinstance(item, str) or item not in fields
                   for item in required)):
        raise NormalizerRunError("required must list only declared output names")
    for label in ("sheet", "encoding", "records_path"):
        if label in data and (not isinstance(data[label], str)
                              or not data[label].strip()):
            raise NormalizerRunError(f"{label} must be a nonempty string")
    return data


def _valid_headers(raw: list[Any]) -> list[str]:
    names = [str(v).strip() if v is not None else "" for v in raw]
    if not names or any(not name for name in names) or len(names) != len(set(names)):
        raise NormalizerRunError("source headers must be unique and nonempty")
    return names


def _read_csv(path: Path, mapping: Mapping[str, Any]) -> list[tuple[int, dict]]:
    with path.open("r", encoding=mapping.get("encoding", "utf-8-sig"), newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = _valid_headers(next(reader))
        except StopIteration as exc:
            raise NormalizerRunError("CSV source is empty") from exc
        rows = []
        preceding_end = reader.line_num
        for cells in reader:
            row_number = preceding_end + 1
            preceding_end = reader.line_num
            if not cells:
                continue
            if len(cells) != len(header):
                raise NormalizerRunError(f"CSV row {row_number}: column count mismatch")
            rows.append((row_number, dict(zip(header, cells))))
        return rows


def _read_json(path: Path, mapping: Mapping[str, Any]) -> list[tuple[int, dict]]:
    with path.open("r", encoding=mapping.get("encoding", "utf-8")) as handle:
        records = json.load(handle)
    selector = mapping.get("records_path")
    if selector:
        for key in selector.split("."):
            if not isinstance(records, dict) or key not in records:
                raise NormalizerRunError("records_path does not select a JSON array")
            records = records[key]
    if not isinstance(records, list):
        raise NormalizerRunError("JSON source must resolve to an array")
    if any(not isinstance(entry, dict) for entry in records):
        raise NormalizerRunError("JSON array rows must be objects")
    return [(index, row) for index, row in enumerate(records, start=1)]


def _read_xlsx(path: Path, mapping: Mapping[str, Any]) -> list[tuple[int, dict]]:
    # A standalone module may depend on the pinned public Excel reader.
    # It does not import any Common library or another Bhandara calculator.
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        selected = mapping.get("sheet")
        if selected and selected not in book.sheetnames:
            raise NormalizerRunError("declared Excel sheet missing")
        sheet = book[selected] if selected else book.active
        iterator = sheet.iter_rows(values_only=False)
        try:
            header_cells = next(iterator)
        except StopIteration as exc:
            raise NormalizerRunError("XLSX source has no header") from exc
        header = _valid_headers([cell.value for cell in header_cells])
        result = []
        for number, cells in enumerate(iterator, start=2):
            if any(cell.data_type == "f" for cell in cells):
                raise NormalizerRunError(f"XLSX formula at row {number} unsupported")
            values = [cell.value for cell in cells]
            if all(v is None or (isinstance(v, str) and not v.strip()) for v in values):
                continue
            if any(v is not None for v in values[len(header):]):
                raise NormalizerRunError(f"XLSX row {number}: unexpected extra columns")
            result.append((number, dict(zip(header, values))))
        return result
    finally:
        book.close()


def read_source(path: Path, mapping: Mapping[str, Any]) -> list[tuple[int, dict]]:
    fmt = mapping["source_format"]
    if path.suffix.lower() != "." + fmt:
        raise NormalizerRunError("source extension differs from mapping source_format")
    if fmt == "csv":
        return _read_csv(path, mapping)
    if fmt == "json":
        return _read_json(path, mapping)
    return _read_xlsx(path, mapping)


def transform(
    rows: list[tuple[int, dict]], mapping: Mapping[str, Any],
) -> tuple[list[dict], list[dict]]:
    if not rows:
        raise NormalizerRunError("source contains no data rows")
    fields = mapping["fields"]
    for source_name in fields.values():
        if any(source_name not in row for _, row in rows):
            raise NormalizerRunError(f"missing declared source column: {source_name}")
    accepted, issues = [], []
    required = set(mapping.get("required", []))
    for number, row in rows:
        values = {
            out: row[source].strip() if isinstance(row[source], str) else row[source]
            for out, source in fields.items()
        }
        blanks = sorted(name for name in required
                        if values[name] is None or
                        (isinstance(values[name], str) and not values[name].strip()))
        if blanks:
            issues.append({
                "code": "NORMALIZER_REQUIRED_VALUE_MISSING",
                "source_row": number,
                "fields": blanks,
            })
        else:
            accepted.append({"source_row": number, "values": values})
    return accepted, issues


def publish(
    *, directory: Path, run_id: str,
    source: Path, mapping_path: Path, input_hashes: Mapping[str, str],
    accepted: list[dict], issues: list[dict],
) -> dict[str, Path]:
    """Reserve a new run and publish declared outputs without replacing old runs."""
    status = "BLOCKED" if issues else "PASS"
    directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.mkdir(mode=0o700, exist_ok=False)
    try:
        values = {
            RESULT: {
                "schema_version": "1.0", "module_id": MODULE_ID,
                "status": status, "approved": False, "finalizable": False,
                "records": accepted, "source_sha256": input_hashes["source"],
                "accepted_count": len(accepted), "rejected_count": len(issues),
            },
            REVIEW: {
                "schema_version": "1.0", "status": status,
                "approved": False, "finalizable": False,
                "issues": issues, "accepted_count": len(accepted),
                "rejected_count": len(issues),
            },
        }
        hashes = {}
        for name, payload in values.items():
            target = directory / name
            with target.open("x", encoding="utf-8") as handle:
                os.chmod(target, 0o600)
                json.dump(payload, handle, ensure_ascii=False, indent=2,
                          default=_json_value, allow_nan=False)
                handle.write("\n")
            hashes[name] = sha256_file(target)
        receipt = {
            "schema_version": "1.0", "module_id": MODULE_ID,
            "module_version": VERSION, "run_id": run_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "status": status, "approved": False, "finalizable": False,
            "input_sha256": dict(input_hashes),
            "output_sha256": hashes,
        }
        target = directory / RECEIPT
        with target.open("x", encoding="utf-8") as handle:
            os.chmod(target, 0o600)
            json.dump(receipt, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        if (sha256_file(source) != input_hashes["source"]
                or sha256_file(mapping_path) != input_hashes["mapping"]):
            raise NormalizerRunError("input file changed during normalization")
        return {name: directory / name for name in (RESULT, REVIEW, RECEIPT)}
    except BaseException:
        shutil.rmtree(directory)
        raise


def run_normalizer(
    private_data_root: str | Path | None = None,
    *, run_id: str | None = None,
    source_path: str | Path | None = None,
    mapping_path: str | Path | None = None,
) -> tuple[str, dict[str, Path]]:
    chosen = run_id if run_id is not None else uuid4().hex
    paths = resolve_paths(private_data_root, run_id=chosen,
                          source_path=source_path, mapping_path=mapping_path)
    hashes = {
        "source": sha256_file(paths.source),
        "mapping": sha256_file(paths.mapping),
    }
    mapping = load_mapping(paths.mapping)
    accepted, issues = transform(read_source(paths.source, mapping), mapping)
    result = publish(
        directory=paths.output, run_id=chosen, source=paths.source,
        mapping_path=paths.mapping, input_hashes=hashes,
        accepted=accepted, issues=issues,
    )
    return ("BLOCKED" if issues else "PASS"), result
