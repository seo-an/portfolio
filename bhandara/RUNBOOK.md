# Bhandara — Development / Operations RUNBOOK

**Status:** PR #3 implements the public Base contract and tests, while calculators and Hermes Adapter are not released. The broader architecture follows the Bhandara handoff v2.0 (2026-11-06).

## Ownership and compatibility

1. `seo-an/portfolio` owns publicly reusable and deterministic calculator/normalizer functions and the shared Base. No Hermes, Slack, Google Drive, authentication, or cloud dependency in public calculations.
2. `seo-an/agent-config` owns the Python/dependency runtime Source of Truth. The reference runtime is the `uv`-managed Hermes image `1.2.0` with Python `3.14.9` and `openpyxl==3.1.5`. Never use the host Ubuntu Python as proof of Hermes compatibility.
3. Gearbox owns authentication, data acquisition, approval, scheduling, orchestration, and future CLI delegation. No private credentials in public module files.
4. Employee and payroll data must remain in private runtime directories **outside both Git repositories** on Hermes; local users may use the Git-ignored `bhandara/data/` directory.

## Public Base

See [Base contract](BASE-CONTRACT.md) for fully specified function APIs, exceptions, sample usage, private output handling, error status classification, and important limitations.

- `common/validation/headers.py`: only required Excel columns are validated; extra columns, blank extra headers, and duplicate extra names are ignored. Missing/duplicate **required** headers stop the sheet.
- `common/io/xlsx.py`: safe XLSX read with source SHA, original Excel row numbers, per-row errors and unaffected accepted rows; no formula evaluation or silent missing-value filling.
- `common/contracts/findings.py`: generic `Finding` and `PASS` / `REVIEW_REQUIRED` / `ERROR`, **not approval**.
- `common/runtime/artifacts.py`: identical `(1)`, `(2)` suffix across one run's files; exclusive reservations; per-file atomic publication and rollback on normal exceptions. Not an all-files-at-once filesystem transaction; sudden process termination recovery is not yet implemented.
- `common/runtime/receipt.py` and `common/utils/hashing.py`: source/output SHA-256 and review-only provenance.

## Calculation boundaries

- The actual PTO/Worktime/Payroll calculation functions **remain in Gearbox**. Moving them is a later, independently tested PR.
- No module may directly import another business calculator. Common functions may be imported only after their semantics match.
- `module.json`/`config.json`, public CLI calculator dispatch, and versioned JSON interchange contracts will be implemented in later module PRs.
- Unclear inputs, missing approvals, calculation errors, employee-level review, and settlement ledger decisions are **not automatically corrected or approved**. A calculation must never itself authorize payment, tax filing, or ledger posting.
- The private Golden baselines created 2026-11-09 use `agent-config` commit `296f909dd84bbdb6196be84568bd0e60775c7dbd`; hash preservation and semantic comparison are separate evidence. See [Golden comparison contract](GOLDEN-COMPARISON.md).

## Verification

```sh
# From the portfolio root; use its local env or Hermes uv-managed interpreter
python -m unittest discover -s bhandara/tests -p 'test_*.py' -v
python install.py --check
python run.py --help
```

For a PR, test its actual branch directly on the server. Do not use worktrees/Draft PR testing. Use `unittest`, never pytest. No SSH Git Push from the server. Compare future migrated calculators with the privately stored Golden baselines before Merge; do not claim legality, calculation equivalence, or actual payroll-program reconciliation merely from code tests.
