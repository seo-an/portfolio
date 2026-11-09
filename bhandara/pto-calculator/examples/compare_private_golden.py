#!/usr/bin/env python3
"""Compare a private synthetic PTO Golden to the standalone public PTO result.

Never prints individual records or monetary values. Refuses unrecognized baseline
shapes instead of skipping mismatches. Run only on locally stored synthetic data.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bhandara.common.validation.golden_compare import (
    Difference, GoldenCompareError, _diff, read_json,
)


def _result_list(value, *, label: str) -> list[dict]:
    if isinstance(value, dict):
        rows = []
        for key, item in sorted(value.items()):
            if not isinstance(item, dict) or item.get("employee_id") != key:
                raise GoldenCompareError(f"{label}: keyed result must contain matching employee_id")
            rows.append(item)
    elif isinstance(value, list):
        rows = value
    else:
        raise GoldenCompareError(f"{label}: result records must be list or keyed object")
    if any(not isinstance(row, dict) or not isinstance(row.get("employee_id"), str) for row in rows):
        raise GoldenCompareError(f"{label}: each result must have employee_id")
    ids = [row["employee_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise GoldenCompareError(f"{label}: duplicate employee_id")
    return sorted(rows, key=lambda row: row["employee_id"])


def _period_dates(data: object, label: str) -> tuple[str, str]:
    if not isinstance(data, dict) or len(data) != 2:
        raise GoldenCompareError(f"{label}: two-date period object required")
    entries = []
    for value in data.values():
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise GoldenCompareError(f"{label}: period dates must be YYYY-MM-DD")
        entries.append(value)
    return tuple(sorted(entries))


def _hashes(data: object, label: str) -> list[str]:
    if not isinstance(data, dict) or not data:
        raise GoldenCompareError(f"{label}: nonempty source_hashes object required")
    values = list(data.values())
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
           for value in values):
        raise GoldenCompareError(f"{label}: SHA-256 values required")
    return sorted(values)


def check(baseline_path: Path, candidate_path: Path) -> list[Difference]:
    baseline, candidate = read_json(baseline_path), read_json(candidate_path)
    for label, value in (("baseline", baseline), ("candidate", candidate)):
        if not isinstance(value, dict):
            raise GoldenCompareError(f"{label}: JSON object required")
        for field in ("results", "period", "source_hashes"):
            if field not in value:
                raise GoldenCompareError(f"{label}: missing {field}")
    if candidate.get("module_id") != "pto-calculator" or candidate.get("approved") is not False or candidate.get("finalizable") is not False:
        raise GoldenCompareError("candidate: invalid PTO producer or approval guard")
    differences = []
    if _period_dates(baseline["period"], "baseline") != _period_dates(candidate["period"], "candidate"):
        differences.append(Difference("/period", "period dates changed"))
    if _hashes(baseline["source_hashes"], "baseline") != _hashes(candidate["source_hashes"], "candidate"):
        differences.append(Difference("/source_hashes", "source fingerprint multiset changed"))
    expected = _result_list(baseline["results"], label="baseline")
    actual = _result_list(candidate["results"], label="candidate")
    _diff(expected, actual, "/results", differences)
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    try:
        differences = check(args.baseline, args.candidate)
    except (GoldenCompareError, OSError) as exc:
        print(f"PTO_GOLDEN_INVALID: {exc}", file=sys.stderr)
        return 2
    if differences:
        print(f"PTO_GOLDEN_DIFF: {len(differences)} differences")
        for entry in differences[:50]:
            print(f"  {entry.pointer}: {entry.reason}")
        return 1
    print("PTO_GOLDEN_PASS: source hashes, period and per-employee results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
