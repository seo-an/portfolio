"""Deterministic receipt shape for private Bhandara execution audit metadata."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bhandara.common.contracts.findings import Finding, RunStatus, summarize_status
from bhandara.common.utils.hashing import sha256_file


RECEIPT_SCHEMA = "1.0"


def build_receipt(
    *,
    module_id: str,
    module_version: str,
    input_files: Mapping[str, str | Path],
    output_sha256: Mapping[str, str],
    findings: Sequence[Finding],
    run_id: str | None = None,
    recorded_at: str | None = None,
) -> dict:
    """Build a review-only run receipt; never infer approval or completion.

    Output SHA values come from ArtifactBatch.staged_hashes(), excluding the
    receipt itself to avoid a circular self-hash.
    """
    if not module_id or not module_id.strip() or not module_version or not module_version.strip():
        raise ValueError("module_id and module_version are required")
    if not input_files or not output_sha256:
        raise ValueError("at least one input and one produced output are required")
    for name, digest in output_sha256.items():
        if not name or len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
            raise ValueError("output file hash must be a lowercase SHA-256 digest")
    status = summarize_status(findings)
    return {
        "schema_version": RECEIPT_SCHEMA,
        "run_id": run_id or uuid4().hex,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "module_id": module_id,
        "module_version": module_version,
        "status": status.value,
        "finalizable": False,
        "approved": False,
        "input_sha256": {
            label: sha256_file(path) for label, path in sorted(input_files.items())
        },
        "output_sha256": dict(sorted(output_sha256.items())),
        "finding_count": len(findings),
        "findings": [entry.to_dict() for entry in findings],
    }
