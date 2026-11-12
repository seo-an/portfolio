"""Map explicitly declared source aliases into canonical Payroll facts.

Generic CSV/XLSX/JSON reading, path validation and scalar coercion are owned
by Bhandara Common. This module retains caller-selected field aliases,
company-provided value maps, rejection lineage and source-specific findings.
No implicit mapping, payroll computation, or approval is performed here.
"""
from __future__ import annotations

import hashlib
from decimal import InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from bhandara.common.io.tabular import (
    MISSING as _MISSING,
    SUPPORTED_FORMATS as _SUPPORTED,
    TabularInputError,
    is_blank_value as _blank,
    lookup_field as _field,
    read_csv_rows as _read_csv,
    read_json_rows as _read_json,
    read_xlsx_rows as _read_xlsx,
    resolve_source_path as _source_path,
)
from bhandara.common.validation.scalars import (
    UnsupportedScalarType,
    convert_scalar,
)


class SourceMappingError(ValueError):
    pass


def _issue(code: str, source: str, message: str, *,
           row_number: int | None = None, field: str = "",
           severity: str = "ERROR") -> dict[str, Any]:
    return {
        "code": code, "severity": severity, "source": source,
        "row_number": row_number, "field": field, "message": message,
    }


def _read_rows(root: Path, source: str, spec: Mapping[str, Any]):
    try:
        path = _source_path(root, spec.get("path"))
        fmt = str(spec.get("format", path.suffix.lstrip("."))).lower()
        if fmt not in _SUPPORTED:
            raise SourceMappingError(f"{source}: unsupported source format {fmt}")
        readers = {"csv": _read_csv, "json": _read_json, "xlsx": _read_xlsx}
        return path, readers[fmt](path, spec)
    except TabularInputError as exc:
        raise SourceMappingError(str(exc)) from exc


def _sources(field_spec: Any) -> tuple[list[str], dict[str, Any]]:
    options = {"source": field_spec} if isinstance(field_spec, (str, list)) else field_spec
    if not isinstance(options, Mapping):
        raise SourceMappingError("field mapping must be a source name or mapping")
    from_values = options.get("source", [])
    names = [from_values] if isinstance(from_values, str) else from_values
    if not isinstance(names, list) or not names or any(
        not isinstance(name, str) or not name.strip() for name in names
    ):
        raise SourceMappingError("field.source must be a nonempty name or list of names")
    if len(set(names)) != len(names):
        raise SourceMappingError("field.source contains duplicate aliases")
    return names, dict(options)


def _convert(value: Any, options: Mapping[str, Any]) -> Any:
    # Business value meaning is explicitly supplied by this source's mapping,
    # never guessed by the generic Bhandara scalar converter.
    value_map = options.get("value_map")
    if value_map is not None:
        if not isinstance(value_map, Mapping):
            raise SourceMappingError("value_map must be a mapping")
        key = str(value).strip()
        if key not in value_map:
            raise ValueError("value is not included in the declared value_map")
        value = value_map[key]
    kind = str(options.get("type", "str")).lower()
    fmt = options.get("format")
    try:
        return convert_scalar(value, kind=kind, fmt=fmt)
    except UnsupportedScalarType as exc:
        raise SourceMappingError(str(exc)) from exc


def _normalize_row(source: str, number: int, row: Mapping[str, Any],
                   mappings: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    normalized: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []
    selected: dict[str, str] = {}
    for target, field_spec in mappings.items():
        aliases, options = _sources(field_spec)
        available = [(alias, _field(row, alias)) for alias in aliases]
        populated = [(alias, value) for alias, value in available if not _blank(value)]
        if len(populated) > 1 and any(value != populated[0][1] for _, value in populated[1:]):
            issues.append(_issue("SOURCE_ALIAS_CONFLICT", source,
                                 "multiple mapped source columns have conflicting values",
                                 row_number=number, field=target))
            continue
        value = populated[0][1] if populated else _MISSING
        if populated:
            selected[target] = populated[0][0]
        if _blank(value):
            if "default" in options:
                value = options["default"]
            elif options.get("required", False):
                issues.append(_issue("REQUIRED_VALUE_MISSING", source,
                                     "required mapped field has no value",
                                     row_number=number, field=target))
                continue
            else:
                continue
        try:
            normalized[target] = _convert(value, options)
        except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
            issues.append(_issue("SOURCE_VALUE_INVALID", source,
                                 f"mapped value cannot be converted: {type(exc).__name__}",
                                 row_number=number, field=target))
    return normalized, issues, selected


def normalize_source(source: str, spec: Mapping[str, Any], *, input_dir: str | Path) -> dict[str, Any]:
    """Normalize one source while preserving rows, rejects, and diagnostics.

    Invalid rows are rejected from the calculation feed but preserved in lineage
    with their row number and structured errors. No inputs are modified.
    """
    if not isinstance(spec, Mapping):
        raise SourceMappingError("source specification must be a mapping")
    mappings = spec.get("fields")
    if not isinstance(mappings, Mapping) or not mappings:
        raise SourceMappingError("source.fields must contain target mappings")
    if any(not isinstance(field, str) or not field.strip() for field in mappings):
        raise SourceMappingError("target field names must be nonempty strings")
    unique_by = spec.get("unique_by", [])
    if not isinstance(unique_by, list) or any(
        not isinstance(field, str) or field not in mappings for field in unique_by
    ):
        raise SourceMappingError("unique_by must reference mapped target fields")
    root = Path(input_dir).resolve()
    path, raw_rows = _read_rows(root, source, spec)
    findings: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    lineage: list[dict[str, Any]] = []
    seen_keys = set()
    if raw_rows:
        for target, field_spec in mappings.items():
            aliases, options = _sources(field_spec)
            if not any(
                _field(row, alias) is not _MISSING
                for _, row in raw_rows for alias in aliases
            ):
                findings.append(_issue(
                    "SOURCE_COLUMN_UNAVAILABLE", source,
                    "none of the declared source column aliases exists",
                    field=target, severity="ERROR" if options.get("required") else "WARNING",
                ))
    for number, raw in raw_rows:
        row, problems, selected = _normalize_row(source, number, raw, mappings)
        if unique_by and not problems:
            try:
                key = tuple(row[field] for field in unique_by)
            except KeyError:
                problems.append(_issue("UNIQUE_KEY_MISSING", source,
                                       "unique key field is missing", row_number=number))
            else:
                if key in seen_keys:
                    problems.append(_issue("DUPLICATE_SOURCE_KEY", source,
                                           "duplicate normalized business key", row_number=number))
                else:
                    seen_keys.add(key)
        findings.extend(problems)
        accepted_row = not problems
        if accepted_row:
            accepted.append(row)
        lineage.append({
            "source": source, "row_number": number,
            "status": "ACCEPTED" if accepted_row else "REJECTED",
            "selected_columns": selected,
            "issue_codes": [problem["code"] for problem in problems],
        })
    if not raw_rows and not spec.get("allow_empty", False):
        findings.append(_issue("SOURCE_EMPTY", source, "source contains no data rows"))
    return {
        "source": source,
        "source_file": str(path.relative_to(root)),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "total_rows": len(raw_rows),
        "accepted_rows": len(accepted),
        "rejected_rows": len(raw_rows) - len(accepted),
        "rows": accepted,
        "lineage": lineage,
        "issues": findings,
    }
