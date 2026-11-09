"""Read required Excel columns and report invalid rows without losing good rows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from bhandara.common.contracts.findings import Finding, RunStatus, Scope, Severity, summarize_status
from bhandara.common.utils.hashing import sha256_file
from bhandara.common.validation.headers import HeaderContractError, is_blank, parse_headers


class SpreadsheetInputError(ValueError):
    """Workbook or worksheet-level failure; caller should record a run finding."""


@dataclass(frozen=True, slots=True)
class SourceRow:
    row_number: int  # one-based Excel row, including the header line
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SheetReadResult:
    source: str
    sheet: str
    source_sha256: str
    rows: tuple[SourceRow, ...]
    findings: tuple[Finding, ...]
    nonempty_rows: int
    rejected_rows: int

    @property
    def accepted_rows(self) -> int:
        return len(self.rows)

    @property
    def status(self) -> RunStatus:
        return summarize_status(self.findings)


def _source_name(path: Path) -> str:
    return path.name  # avoid leaking server-local absolute paths in findings


def _missing_fields(values: dict[str, object]) -> list[str]:
    return [name for name, value in values.items() if is_blank(value)]


def read_required_rows(
    path: str | Path,
    *,
    required_headers: Sequence[str],
    sheet_name: str | None = None,
    header_row: int = 1,
) -> SheetReadResult:
    """Read an XLSX without changing it; reject only rows missing required facts.

    Missing/duplicated required headers or wrong worksheet are sheet-level failures.
    Extra columns, even blank or duplicated extra headers, are deliberately ignored.
    Excel formulas in required cells are rejected: cached values are not evaluated.
    """
    if header_row < 1:
        raise SpreadsheetInputError("header_row must be 1 or greater")
    source = Path(path)
    if source.suffix.lower() not in (".xlsx", ".xlsm"):
        raise SpreadsheetInputError("only XLSX/XLSM input is supported")
    if not source.is_file():
        raise SpreadsheetInputError(f"Excel input is not a file: {_source_name(source)}")
    try:
        digest = sha256_file(source)
        book = load_workbook(source, read_only=True, data_only=False, keep_links=False)
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        raise SpreadsheetInputError(
            f"could not open workbook {_source_name(source)}: {type(exc).__name__}"
        ) from exc
    try:
        if sheet_name is not None and sheet_name not in book.sheetnames:
            raise SpreadsheetInputError(f"worksheet not found: {sheet_name}")
        sheet = book[sheet_name] if sheet_name is not None else book.active
        selected_sheet = sheet.title
        iterator = sheet.iter_rows(min_row=header_row)
        header_cells = next(iterator, None)
        if header_cells is None:
            raise SpreadsheetInputError("worksheet has no header row")
        try:
            mapping = parse_headers([cell.value for cell in header_cells], required_headers)
        except HeaderContractError as exc:
            raise SpreadsheetInputError(f"{selected_sheet}: {exc}") from exc

        accepted: list[SourceRow] = []
        findings: list[Finding] = []
        nonempty = 0
        rejected = 0
        for row_number, cells in enumerate(iterator, start=header_row + 1):
            if not any(not is_blank(cell.value) for cell in cells):
                continue
            nonempty += 1
            values = mapping.project([cell.value for cell in cells])
            invalid = False
            for name, position in zip(mapping.required, mapping.positions):
                if position < len(cells) and cells[position].data_type == "f":
                    findings.append(Finding(
                        code="FORMULA_UNSUPPORTED", severity=Severity.ERROR,
                        scope=Scope.CELL, message="Required source cell is a formula; explicit value needed",
                        source=_source_name(source), sheet=selected_sheet,
                        row_number=row_number, field=name,
                    ))
                    invalid = True
            for name in _missing_fields(values):
                findings.append(Finding(
                    code="REQUIRED_CELL_MISSING", severity=Severity.ERROR,
                    scope=Scope.CELL, message="Required source cell is blank",
                    source=_source_name(source), sheet=selected_sheet,
                    row_number=row_number, field=name,
                ))
                invalid = True
            if invalid:
                rejected += 1
                continue
            accepted.append(SourceRow(row_number=row_number, values=values))
        if nonempty == 0:
            findings.append(Finding(
                code="NO_DATA_ROWS", severity=Severity.ERROR, scope=Scope.RUN,
                message="Worksheet has no populated input rows",
                source=_source_name(source), sheet=selected_sheet,
            ))
        if sha256_file(source) != digest:
            raise SpreadsheetInputError("workbook changed during read; restart with stable input")
        return SheetReadResult(
            source=_source_name(source), sheet=selected_sheet, source_sha256=digest,
            rows=tuple(accepted), findings=tuple(findings),
            nonempty_rows=nonempty, rejected_rows=rejected,
        )
    except (OSError, ValueError, TypeError, BadZipFile) as exc:
        if isinstance(exc, SpreadsheetInputError):
            raise
        raise SpreadsheetInputError(
            f"could not read worksheet {_source_name(source)}: {type(exc).__name__}"
        ) from exc
    finally:
        book.close()
