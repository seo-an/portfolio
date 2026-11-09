"""Small, reusable review/error contract; never silently approve a calculation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable


class Severity(StrEnum):
    REVIEW = "REVIEW"
    ERROR = "ERROR"


class RunStatus(StrEnum):
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ERROR = "ERROR"


class Scope(StrEnum):
    CELL = "CELL"
    ROW = "ROW"
    EMPLOYEE_DAY = "EMPLOYEE_DAY"
    EMPLOYEE_PERIOD = "EMPLOYEE_PERIOD"
    RUN = "RUN"


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    scope: Scope
    message: str
    source: str | None = None
    sheet: str | None = None
    row_number: int | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.severity, Severity) or not isinstance(self.scope, Scope):
            raise ValueError("finding severity/scope must be valid enum values")
        if not self.code or not self.code.strip():
            raise ValueError("finding code is required")
        if self.row_number is not None and self.row_number < 1:
            raise ValueError("row_number must be positive")
        if not self.message or not self.message.strip():
            raise ValueError("finding message is required")

    def to_dict(self) -> dict:
        """Structured diagnostics without any raw cell values or employee names."""
        return asdict(self)


def summarize_status(findings: Iterable[Finding]) -> RunStatus:
    highest = RunStatus.PASS
    for finding in findings:
        if finding.severity == Severity.ERROR:
            return RunStatus.ERROR
        if finding.severity == Severity.REVIEW:
            highest = RunStatus.REVIEW_REQUIRED
    return highest
