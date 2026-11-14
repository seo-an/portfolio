#!/usr/bin/env python3
"""Read-only Base prerequisites check; installation remains an explicit uv action."""
from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MIN_PYTHON = (3, 12)
REQUIRED_PACKAGES = {"openpyxl": "3.1.5", "python-calamine": "0.9.1", "korean-lunar-calendar": "0.4.0"}


def check_python(version: tuple[int, ...] | None = None) -> tuple[bool, str]:
    detected = tuple(sys.version_info[:3] if version is None else version)
    supported = detected >= MIN_PYTHON
    details = ".".join(map(str, detected))
    return supported, details


def check_packages(expected: dict[str, str] | None = None) -> list[str]:
    """Return problems; use importlib metadata without running pip or uv."""
    problems = []
    for name, required in (expected or REQUIRED_PACKAGES).items():
        try:
            installed = version(name)
        except PackageNotFoundError:
            problems.append(f"{name}: NOT INSTALLED (expected {required})")
        else:
            if installed != required:
                problems.append(f"{name}: {installed} (expected {required})")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Bhandara Base prerequisites without changing the environment."
    )
    parser.add_argument(
        "--check", action="store_true", help="Check prerequisites without installing anything"
    )
    parser.parse_args(argv)

    supported, detected = check_python()
    if not supported:
        print(f"INCOMPATIBLE: Python {detected}; Base requires Python 3.12+", file=sys.stderr)
        return 2
    problems = check_packages()
    if problems:
        for problem in problems:
            print(f"DEPENDENCY_MISMATCH: {problem}", file=sys.stderr)
        return 2
    print(f"BASE_CHECK_OK: Python {detected}")
    for name, required in REQUIRED_PACKAGES.items():
        print(f"DEPENDENCY_CHECK_OK: {name}=={required}")
    available = [
        module_id for module_id in ("pto-calculator", "worktime-calculator", "payroll-calculator")
        if (Path(__file__).resolve().parent / "bhandara" / module_id / "module.json").is_file()
    ]
    print("No packages were installed or changed. Available modules: "
          + (", ".join(available) if available else "none") + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
