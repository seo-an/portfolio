#!/usr/bin/env python3
"""Portfolio CLI placeholder: deliberately blocks unavailable calculators."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Public Portfolio CLI (Bhandara calculators are not installed yet)."
    )
    commands = parser.add_subparsers(dest="collection", required=True)
    bhandara = commands.add_parser(
        "bhandara", help="Bhandara HR calculators (not released in this bootstrap)"
    )
    bhandara.add_argument("module_id", help="Requested module identifier")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.collection == "bhandara":
        print(
            f"UNAVAILABLE: {args.module_id!r} is not installed in this Phase 1 bootstrap. "
            "No calculations were performed.",
            file=sys.stderr,
        )
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
