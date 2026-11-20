"""One-command, grouped Bhandara unittest runner.

Run from any working directory:
    python3 -B bhandara/_tests/run.py
or:
    python3 -B -m bhandara._tests.run

This does not replace unittest or change the test modules. Failures retain
standard traceback output and the process exits nonzero on any failure.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = PROJECT_ROOT / "bhandara" / "tests"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TOPICS = (
    ("test_paid_time_off_", "Paid Time Off"),
    ("test_pto_", "Paid Time Off"),
    ("test_worktime_", "Worktime"),
    ("test_payroll_", "Payroll"),
    ("test_integrated_", "Integrated"),
    ("test_common_", "Common"),
    ("test_input_", "Common"),
    ("test_example_", "Examples"),
)


def classify_topic(test_id: str) -> str:
    """Map the original unittest module name to one stable business topic."""
    name = test_id.split(".")[0]
    for prefix, topic in TOPICS:
        if name.startswith(prefix):
            return topic
    return "Other"


class GroupedTestResult(unittest.TestResult):
    """Track per-test outcomes including subtests; no custom test framework."""

    def __init__(self):
        super().__init__()
        self.outcomes: dict[str, str] = {}
        self.by_topic: dict[str, Counter] = defaultdict(Counter)

    def startTest(self, test):
        super().startTest(test)
        self.outcomes[test.id()] = "PASS"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "FAIL"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "ERROR"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "SKIP"

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcomes[test.id()] = "SKIP"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = "FAIL"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            result = "FAIL" if issubclass(err[0], AssertionError) else "ERROR"
            if self.outcomes.get(test.id()) != "ERROR":
                self.outcomes[test.id()] = result

    def stopTest(self, test):
        self.by_topic[classify_topic(test.id())][
            self.outcomes.get(test.id(), "ERROR")
        ] += 1
        super().stopTest(test)


def format_summary(result: GroupedTestResult) -> str:
    """Human-readable stable counts by domain and an explicit final status."""
    header = f'{"주제":<18} {"전체":>6} {"PASS":>6} {"FAIL":>6} {"ERROR":>7} {"SKIP":>6}'
    lines = ["", "=" * len(header), "BHANDARA UNITTEST SUMMARY", "=" * len(header),
             header, "-" * len(header)]
    total = Counter()
    for topic in sorted(result.by_topic):
        stats = result.by_topic[topic]
        total.update(stats)
        count = sum(stats.values())
        lines.append(
            f'{topic:<18} {count:>6} {stats["PASS"]:>6} '
            f'{stats["FAIL"]:>6} {stats["ERROR"]:>7} {stats["SKIP"]:>6}'
        )
    lines.extend([
        "-" * len(header),
        f'{"TOTAL":<18} {sum(total.values()):>6} {total["PASS"]:>6} '
        f'{total["FAIL"]:>6} {total["ERROR"]:>7} {total["SKIP"]:>6}',
        "STATUS: PASS" if result.wasSuccessful() else "STATUS: FAIL",
    ])
    return "\n".join(lines)


def run_tests(pattern: str = "test_*.py", *, stream=None) -> bool:
    """One test discovery and execution. Never rerun tests per topic."""
    import io
    output = stream if stream is not None else sys.stdout
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_ROOT), pattern=pattern,
    )
    result = GroupedTestResult()
    suite.run(result)
    if result.failures or result.errors or result.unexpectedSuccesses:
        for label, records in (
            ("FAIL", result.failures), ("ERROR", result.errors),
        ):
            for case, traceback in records:
                print(f"\n{label}: {case.id()}\n{traceback}", file=output)
        for case in result.unexpectedSuccesses:
            print(f"\nUNEXPECTED PASS: {case.id()}", file=output)
    print(format_summary(result), file=output)
    return result.wasSuccessful()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bhandara topic-grouped unittest")
    parser.add_argument(
        "--pattern", default="test_*.py",
        help="unittest filename discovery glob (default: test_*.py)",
    )
    args = parser.parse_args(argv)
    return 0 if run_tests(args.pattern) else 1


if __name__ == "__main__":
    raise SystemExit(main())
