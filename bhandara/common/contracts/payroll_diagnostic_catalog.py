"""Common diagnostic catalog shared only where semantics are identical."""

from __future__ import annotations

COMMON_DIAGNOSTICS = {
    "REQUIRED_FIELD_MISSING": {
        "message": "A required field is missing.",
    },
    "INPUT_FILE_NOT_FOUND": {
        "message": "A required input file was not found.",
    },
    "DUPLICATE_RECORD": {
        "message": "A record that must be unique appears more than once.",
    },
    "INVALID_DATE_RANGE": {
        "message": "The date range is invalid.",
    },
}


def get_common_diagnostic(code: str) -> dict[str, str] | None:
    item = COMMON_DIAGNOSTICS.get(str(code).upper().strip())
    return dict(item) if item is not None else None
