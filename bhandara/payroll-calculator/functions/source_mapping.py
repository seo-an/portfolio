"""Map heterogeneous tabular inputs into canonical Gearbox facts.

No dynamic evaluation or implicit guessing. Every source cell must be mapped
explicitly; rejected rows and source provenance are retained separately.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from openpyxl import load_workbook


class SourceMappingError(ValueError):
    pass


_MISSING = object()
_SUPPORTED = {"csv", "json", "xlsx"}


def _issue(code: str, source: str, message: str, *,
           row_number: int | None = None, field: str = "",
           severity: str = "ERROR") -> dict[str, Any]:
    return {
        "code": code, "severity": severity, "source": source,
        "row_number": row_number, "field": field, "message": message,
    }


def _field(row: Mapping[str, Any], path: str) -> Any:
    # Exact matching takes precedence: spreadsheet headers can contain dots.
    if path in row:
        return row[path]
    current: Any = row
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _blank(value: Any) -> bool:
    return value is _MISSING or value is None or (
        isinstance(value, str) and not value.strip()
    )


def _column_names(values: list[Any]) -> list[str]:
    names = [str(item).strip() if item is not None else "" for item in values]
    if not names or any(not name for name in names) or len(set(names)) != len(names):
        raise SourceMappingError("source headers must be unique and non-empty")
    return names


def _read_csv(path: Path, spec: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    encoding = str(spec.get("encoding", "utf-8-sig"))
    delimiter = str(spec.get("delimiter", ","))
    if len(delimiter) != 1:
        raise SourceMappingError("CSV delimiter must be a single character")
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            columns = _column_names(next(reader))
        except StopIteration as exc:
            raise SourceMappingError("CSV source is empty") from exc
        rows = []
        previous_end_line = reader.line_num
        for values in reader:
            # CSV reader line numbers track physical lines, including skipped
            # blank lines and multi-line quoted cells.
            number = previous_end_line + 1
            previous_end_line = reader.line_num
            # A physical blank CSV line has no cells and can be ignored.
            # A represented record such as '""' or ',,' still exists and
            # must be validated: dropping it hides missing required fields.
            if not values:
                continue
            if len(values) != len(columns):
                raise SourceMappingError(f"CSV row {number}: column count mismatch")
            rows.append((number, dict(zip(columns, values))))
        return rows


def _read_xlsx(path: Path, spec: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    header_row = spec.get("header_row", 1)
    if type(header_row) is not int or header_row < 1:
        raise SourceMappingError("header_row must be a positive integer")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet_name = spec.get("sheet")
        if sheet_name is not None and sheet_name not in workbook.sheetnames:
            raise SourceMappingError(f"worksheet not found: {sheet_name}")
        sheet = workbook[sheet_name] if sheet_name is not None else workbook.active
        iterator = sheet.iter_rows(min_row=header_row, values_only=True)
        try:
            columns = _column_names(list(next(iterator)))
        except StopIteration as exc:
            raise SourceMappingError("XLSX source has no header row") from exc
        result = []
        for number, values in enumerate(iterator, start=header_row + 1):
            if all(_blank(value) for value in values):
                continue
            if any(not _blank(value) for value in values[len(columns):]):
                raise SourceMappingError(f"XLSX row {number}: unexpected extra columns")
            result.append((number, dict(zip(columns, values))))
        return result
    finally:
        workbook.close()


def _read_json(path: Path, spec: Mapping[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding=str(spec.get("encoding", "utf-8"))) as handle:
        value = json.load(handle)
    records_path = spec.get("records_path")
    if records_path:
        value = _field(value, str(records_path)) if isinstance(value, Mapping) else _MISSING
    if not isinstance(value, list):
        raise SourceMappingError("JSON rows must be a list or records_path must select a list")
    rows = []
    for number, row in enumerate(value, start=1):
        if not isinstance(row, Mapping):
            raise SourceMappingError(f"JSON row {number}: object required")
        rows.append((number, dict(row)))
    return rows


def _source_path(root: Path, name: Any) -> Path:
    if not isinstance(name, str) or not name.strip():
        raise SourceMappingError("source.path is required")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise SourceMappingError("source path must stay within input directory")
    if not target.is_file():
        raise SourceMappingError(f"source file not found: {name}")
    return target


def _read_rows(root: Path, source: str, spec: Mapping[str, Any]):
    path = _source_path(root, spec.get("path"))
    fmt = str(spec.get("format", path.suffix.lstrip("."))).lower()
    if fmt not in _SUPPORTED:
        raise SourceMappingError(f"{source}: unsupported source format {fmt}")
    readers = {"csv": _read_csv, "json": _read_json, "xlsx": _read_xlsx}
    return path, readers[fmt](path, spec)


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
    if kind == "str":
        return str(value).strip()
    if kind == "date":
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        parsed = datetime.strptime(str(value).strip(), fmt).date() if fmt else date.fromisoformat(str(value).strip())
        return parsed.isoformat()
    if kind == "time":
        if isinstance(value, datetime):
            parsed = value.timetz()
        elif isinstance(value, time):
            parsed = value
        else:
            parsed = datetime.strptime(str(value).strip(), fmt).time() if fmt else time.fromisoformat(str(value).strip())
        if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
            raise ValueError("clock time must have naive minute precision")
        return parsed.isoformat(timespec="minutes")
    if kind == "datetime":
        parsed = value if isinstance(value, datetime) else (
            datetime.strptime(str(value).strip(), fmt) if fmt else datetime.fromisoformat(str(value).strip())
        )
        if parsed.second or parsed.microsecond:
            raise ValueError("datetime must have minute precision")
        return parsed.isoformat(timespec="minutes")
    if kind == "decimal":
        if isinstance(value, bool):
            raise ValueError("boolean is not a decimal")
        number = Decimal(str(value).strip().replace(",", ""))
        if not number.is_finite():
            raise ValueError("non-finite decimal")
        return format(number, "f")
    if kind == "int":
        if isinstance(value, bool):
            raise ValueError("boolean is not an integer")
        number = Decimal(str(value).strip().replace(",", ""))
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("integer required")
        return int(number)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1", "yes", "y"):
            return True
        if text in ("false", "0", "no", "n"):
            return False
        raise ValueError("boolean mapping requires explicit value_map or true/false")
    raise SourceMappingError(f"unsupported field type: {kind}")


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
