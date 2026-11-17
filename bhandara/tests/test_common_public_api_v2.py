"""One-shot acceptance: Common library API + standalone Normalizer CLI + isolation.

All fixtures are synthetic. Never reads employee data or modifies other tools.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bhandara.common.module import normalizer

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "bhandara" / "common" / "module" / "normalizer"
EXPECTED_PUBLIC_API = {
    "load_mapping", "read_source", "transform", "run_normalizer",
    "resolve_paths", "NormalizerRunError", "NormalizerPathError",
    "NormalizerPaths",
}


def prepare_synthetic_input(root: Path) -> tuple[Path, Path]:
    folder = root / "common-normalizer" / "input"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "source.csv"
    mapping = folder / "mapping.json"
    source.write_text(
        "staff_number,worked_minutes\nE001,450\nE002,480\n",
        encoding="utf-8",
    )
    mapping.write_text(json.dumps({
        "schema_version": "1.0", "source_format": "csv",
        "fields": {"employee_id": "staff_number", "minutes": "worked_minutes"},
        "required": ["employee_id"],
    }), encoding="utf-8")
    return source, mapping


def invoke_portfolio_cli(data_root: Path, run_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / "run.py"), "bhandara",
         "common-normalizer", "--data-root", str(data_root), "--run-id", run_id],
        cwd=ROOT, text=True, capture_output=True, check=False, timeout=40,
    )


class CommonPublicApiAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="bhandara-common-public-api-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.private = self.root / "private"
        self.source, self.mapping = prepare_synthetic_input(self.private)

    def test_normalizer_is_importable_beside_existing_common_libraries(self) -> None:
        """All three are available to PTO/Worktime/Payroll consumers."""
        from bhandara.common.io import tabular
        from bhandara.common.validation import scalars
        from bhandara.common.module.normalizer import (
            load_mapping, read_source, transform, run_normalizer,
        )
        from bhandara.common.module.normalizer import runner
        self.assertTrue(callable(tabular.read_csv_rows))
        self.assertTrue(callable(scalars.convert_scalar))
        self.assertEqual(set(normalizer.__all__), EXPECTED_PUBLIC_API)
        self.assertIs(load_mapping, runner.load_mapping)
        self.assertIs(read_source, runner.read_source)
        self.assertIs(transform, runner.transform)
        self.assertIs(run_normalizer, runner.run_normalizer)
        self.assertFalse((SRC / "output" / "side-effect-from-import").exists())
        parsed_mapping = load_mapping(self.mapping)
        transformed, issues = transform(read_source(self.source, parsed_mapping),
                                        parsed_mapping)
        self.assertEqual(issues, [])
        self.assertEqual(
            transformed[0],
            {"source_row": 2, "values": {
                "employee_id": "E001", "minutes": "450",
            }},
        )

    def test_imported_api_and_cli_produce_equivalent_results(self) -> None:
        """Same transformation whether imported as library or executed via CLI."""
        status, artifacts = normalizer.run_normalizer(
            self.private, run_id="library-001",
        )
        self.assertEqual(status, "PASS")
        command = invoke_portfolio_cli(self.private, "cli-001")
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertIn("NORMALIZER_STATUS: PASS", command.stdout)
        self.assertIn("normalizer-result.json", command.stdout)
        self.assertEqual(
            json.loads(artifacts["normalizer-result.json"].read_text(encoding="utf-8")),
            json.loads((
                self.private / "common-normalizer" / "output" /
                "cli-001" / "normalizer-result.json"
            ).read_text(encoding="utf-8")),
        )
        self.assertTrue((self.private / "common-normalizer" / "output" /
                         "library-001" / "normalizer-run.json").is_file())
        self.assertFalse((self.private / "pto-calculator").exists())
        self.assertFalse((self.private / "worktime-calculator").exists())
        self.assertFalse((self.private / "payroll-calculator").exists())

    def test_normalizer_works_when_only_its_package_is_installed(self) -> None:
        """No Common io/validation/runtime libs, other calculators or Gearbox."""
        installed = self.root / "standalone"
        package = installed / "bhandara" / "common" / "module" / "normalizer"
        package.mkdir(parents=True)
        for relative in (
            "bhandara/__init__.py",
            "bhandara/common/__init__.py",
            "bhandara/common/module/__init__.py",
        ):
            target = installed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        for filename in (
            "__init__.py", "runner.py", "paths.py", "user_settings.py", "module.json",
        ):
            shutil.copy2(SRC / filename, package / filename)
        for folder in ("input", "output"):
            (package / folder).mkdir()
            shutil.copy2(SRC / folder / ".gitkeep",
                         package / folder / ".gitkeep")
        self.assertFalse((installed / "bhandara" / "common" / "io").exists())
        self.assertFalse((installed / "bhandara" / "common" / "validation").exists())
        self.assertFalse((installed / "bhandara" / "pto-calculator").exists())
        self.assertFalse((installed / "gearbox").exists())

        # -I removes inherited Python path; only the isolated installation is added.
        probe = r"""
import importlib.util
import json
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from bhandara.common.module.normalizer import (
    load_mapping, read_source, transform, run_normalizer,
)
assert importlib.util.find_spec("bhandara.common.io") is None
assert importlib.util.find_spec("bhandara.common.validation") is None
private = Path(sys.argv[2])
cfg = load_mapping(private / "common-normalizer/input/mapping.json")
rows, issues = transform(
    read_source(private / "common-normalizer/input/source.csv", cfg), cfg,
)
assert len(rows) == 2 and not issues
status, paths = run_normalizer(private, run_id="isolated")
assert status == "PASS"
result = json.loads(paths["normalizer-result.json"].read_text())
assert result["records"][0]["values"]["employee_id"] == "E001"
print("NORMALIZER_ISOLATED_IMPORT_AND_RUN=PASS")
"""
        command = subprocess.run(
            [sys.executable, "-I", "-B", "-c", probe, str(installed), str(self.private)],
            cwd=installed, text=True, capture_output=True, check=False, timeout=40,
        )
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertIn("NORMALIZER_ISOLATED_IMPORT_AND_RUN=PASS", command.stdout)
        self.assertTrue((self.private / "common-normalizer" / "output" /
                         "isolated" / "normalizer-result.json").is_file())

    def test_missing_explicit_input_is_not_silently_replaced(self) -> None:
        with self.assertRaisesRegex(normalizer.NormalizerPathError, "not found"):
            normalizer.run_normalizer(
                self.private, run_id="missing", source_path="absent.csv",
            )
        self.assertFalse((self.private / "common-normalizer" /
                          "output" / "missing").exists())


if __name__ == "__main__":
    unittest.main()
