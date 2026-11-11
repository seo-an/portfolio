"""실제 한국어 README에 기재된 합성 예제 실행 확인.

문서에 제시한 CLI와 제공 예제 JSON/Excel이 동작하는지만 검사한다.
계산 정책·예외처리·기존 Golden 데이터는 검증하거나 수정하지 않는다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
RUN = ROOT / "run.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *args], cwd=ROOT, check=False,
        capture_output=True, text=True, timeout=120,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DocumentationExamplesTests(unittest.TestCase):
    def test_pto_readme_synthetic_demo_runs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bhandara-doc-pto-") as folder:
            root = Path(folder)
            demo = root / "demo"
            generator = (
                ROOT / "bhandara/pto-calculator/examples/generate_demo.py"
            )
            generated = run(str(generator), "--output-dir", str(demo))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            out = root / "result"
            result = run(
                str(RUN), "bhandara", "pto-calculator",
                "--config", str(demo / "config.json"),
                "--input-dir", str(demo / "input"),
                "--output-dir", str(out),
            )
            # The two-person demo intentionally lacks earlier months.
            # Do not mistake missing evidence for a verified full attendance.
            self.assertEqual(result.returncode, 1, result.stderr)
            data = read_json(out / "pto-result.json")
            self.assertEqual(data["status"], "REVIEW_REQUIRED")
            self.assertFalse(data["approved"])
            self.assertFalse(data["finalizable"])
            self.assertEqual(len(data["results"]), 2)

    def test_worktime_readme_json_examples_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bhandara-doc-worktime-") as folder:
            root = Path(folder)
            examples = ROOT / "bhandara/worktime-calculator/examples"
            out = root / "result"
            result = run(
                str(RUN), "bhandara", "worktime-calculator",
                "--normalized", str(examples / "normalized-input.demo.json"),
                "--config", str(examples / "worktime-config.approved.demo.json"),
                "--output-dir", str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = read_json(out / "worktime-result.json")
            self.assertEqual(data["status"], "CALCULATED_UNCLOSED")
            self.assertFalse(data["finalizable"])
            self.assertIsNone(data["close_receipt"])
            self.assertEqual(len(data["rows"]), 2)

    def test_payroll_readme_synthetic_generator_and_calculation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bhandara-doc-payroll-") as folder:
            root = Path(folder)
            examples = ROOT / "bhandara/payroll-calculator/examples"
            generated_input = root / "synthetic-input"
            gen = examples / "payroll-standalone-demo/generate.py"
            worktime_json = examples / (
                "payroll-standalone-demo/worktime-result.synthetic.json"
            )
            created = run(
                str(gen), "--worktime-result", str(worktime_json),
                "--output-dir", str(generated_input),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            result = run(
                str(RUN), "bhandara", "payroll-calculator",
                "--config", str(generated_input / "payroll-config.json"),
                "--output-dir", str(root / "result"),
            )
            # 원본 CLI는 정상적인 검토용 계산에서도 종료 코드 2를 유지한다.
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("REVIEW_REQUIRED", result.stdout)
            calculated = read_json(root / "result/payroll-calculation.json")
            reviewed = read_json(root / "result/payroll-review.json")
            self.assertEqual(calculated["status"], "REVIEW_REQUIRED")
            self.assertFalse(calculated["finalizable"])
            self.assertFalse(calculated["ledger_committed"])
            self.assertEqual(reviewed["status"], "REVIEW_REQUIRED")
            self.assertEqual(len(calculated["composition"]["worker_runs"]), 2)

    def test_payroll_archived_legacy_manuals_have_manifest_provenance(self) -> None:
        module = ROOT / "bhandara/payroll-calculator"
        manifest = read_json(module / "migration-manifest.json")
        index = {entry["source"]: entry for entry in manifest["files"]}
        for name in ("README.md", "RUNBOOK.md"):
            with self.subTest(manual=name):
                source = f"gearbox/gear/payroll-calculator/{name}"
                entry = index[source]
                self.assertEqual(
                    entry["destination"],
                    f"bhandara/payroll-calculator/legacy-source-docs/{name}",
                )
                self.assertTrue((ROOT / entry["destination"]).is_file())
                self.assertTrue((module / name).is_file())


if __name__ == "__main__":
    unittest.main()
