"""Internal synthetic seed fixture for old input-contract regression tests.

This is not a second published sample. The only user-facing Excel is
bhandara/examples/sample/input, regenerated with the current schema.
"""
from __future__ import annotations

import tempfile
import importlib
import shutil
from pathlib import Path

from bhandara.examples.sample._seed import build_shared_input

_TEMP = tempfile.TemporaryDirectory(prefix="bhandara-contract-seed-")
ROOT = Path(_TEMP.name)
build_shared_input(ROOT)
SEED_INPUT = ROOT / "input"

# Older Payroll input/contract compatibility tests need a valid predecessor
# Worktime handoff. Recreate it from the deterministic seed, not from a
# separately committed public legacy spreadsheet.
worktime = importlib.import_module("bhandara.worktime-calculator.shared_excel")
handoff_dir = ROOT / "worktime-result"
status = worktime.run_shared_excel(SEED_INPUT, "2026-06", handoff_dir)
if status not in (0, 2):
    raise RuntimeError("synthetic legacy contract Worktime handoff failed")
shutil.copy2(
    handoff_dir / "worktime-result.json",
    SEED_INPUT / "payroll/worktime-result.json",
)
