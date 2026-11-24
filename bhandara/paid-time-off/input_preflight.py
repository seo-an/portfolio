"""Read-only PTO upload preflight using the existing domain readers.

No calculation, workspace creation, file mutation, or source row output.
A match is per consumer module, not an assertion of cross-file consistency.
"""
from importlib import import_module
from pathlib import Path
import json
import argparse

_runner = import_module("bhandara.paid-time-off.runner")
_usage = import_module("bhandara.paid-time-off.runner_usage")
_closing = import_module("bhandara.paid-time-off.runner_closing")


def _approved(path):
    _, missing = _runner._read_approved_leave(path)
    # The standalone calculator intentionally diagnoses missing headers;
    # pool admission is stricter about structural completeness only.
    return ("MISSING_HEADERS", tuple(missing)) if missing else ("MATCH", ())


def _previous(path):
    meta = _usage._policy(path)
    ref = meta.get("참조 ID")
    end = _usage._carry_reference(ref)
    if not ref.startswith("Closing-") or end.month == 12:
        raise ValueError("not a same-year preceding quarter")
    next_id = f"Closing-{end.month // 3 + 1}.4-{end.year}"
    _closing._previous(path, next_id, ref)


def _read(reader, path):
    reader(path)
    return "MATCH", ()


# Each entry reuses the actual consumer's reader, including their differences.
# Only upload roles are classified; generated results retain their own lineage.
READERS = {
    ("entitlement", "employee"): _runner.read_employee_roster,
    ("entitlement", "attendance"): _runner._read_attendance,
    ("entitlement", "proration"): _runner._read_proration,
    ("deduction-quantity", "approved_leave"): _approved,
    ("usage-ledger", "grant_references"): _usage._verified_references,
    ("usage-ledger", "carry_in"): _usage._read_carry,
    ("closing", "employee"): _closing._roster,
    ("closing", "previous_closing"): _previous,
    ("closing", "promotion"): _closing._promotion,
}


def inspect_input(path: str | Path) -> dict:
    """Return only fixed role/module labels, statuses and known header names.

    Reader acceptance is not full calculation readiness or approval. Period,
    cross-file IDs, quantities and other calculation checks remain in runners.
    """
    path = Path(path)
    checks = []
    for (module, role), reader in READERS.items():
        status, missing = "REJECTED", ()
        if path.is_file() and path.suffix.lower() in (".xlsx", ".xlsm"):
            try:
                status, missing = (reader(path) if reader is _approved
                                   else _read(reader, path))
            except Exception:
                # Reader errors can include employee IDs, paths and values.
                pass
        checks.append({"module": module, "role": role, "status": status,
                       "missing_headers": list(missing)})
    # Transport success is independent of workbook acceptance: a valid
    # response can report zero matches or multiple candidate roles.
    return {"schema_version": "1.0", "tool": "paid-time-off",
            "operation": "inspect_input", "status": "OK",
            "checks": checks, "review_only": True, "approved": False}


def main():
    parser = argparse.ArgumentParser(description="Read-only PTO input preflight")
    parser.add_argument("file")
    args = parser.parse_args()
    print(json.dumps(inspect_input(args.file), ensure_ascii=False))


if __name__ == "__main__":
    main()
