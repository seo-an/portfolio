"""Internal synthetic seed fixture for old input-contract regression tests.

This is not a second published sample. The only user-facing Excel is
bhandara/examples/sample/input, regenerated with the current schema.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from bhandara.examples.sample._seed import build_shared_input

_TEMP = tempfile.TemporaryDirectory(prefix="bhandara-contract-seed-")
ROOT = Path(_TEMP.name)
build_shared_input(ROOT)
SEED_INPUT = ROOT / "input"
