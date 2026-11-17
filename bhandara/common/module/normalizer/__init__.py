"""Public Python API for the independently runnable Common normalizer.

Importing these functions never reads input files or creates output files.
Normalizer does not import Common's utility libraries or other calculators.

Library use:
    from bhandara.common.module.normalizer import transform, read_source

Standalone file processing:
    from bhandara.common.module.normalizer import run_normalizer
"""
from __future__ import annotations

from .paths import NormalizerPathError, NormalizerPaths, resolve_paths
from .runner import (
    NormalizerRunError,
    load_mapping,
    read_source,
    transform,
    run_normalizer,
)

__all__ = (
    "NormalizerPathError",
    "NormalizerPaths",
    "NormalizerRunError",
    "load_mapping",
    "read_source",
    "resolve_paths",
    "run_normalizer",
    "transform",
)
