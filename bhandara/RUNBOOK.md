# Bhandara — Development / Operations RUNBOOK

**Status (2026-11-09):** Base (portfolio PR #3), the first public PTO Calculator v0.1.0 (portfolio PR #4), and the private Gearbox PTO Preview Adapter (agent-config PR #144) have all been **merged and tested**. The architecture is governed by Bhandara Handoff v3.0 (2026-11-09). The **Hermes Tool/Slack registration, existing PTO Pipeline cutover, and Worktime/Payroll publication remain incomplete**.

## Ownership and compatibility

1. `seo-an/portfolio` owns publicly reusable and deterministic calculator/normalizer functions and the shared Base. No Hermes, Slack, Google Drive, authentication, or cloud dependency in public calculations.
2. `seo-an/agent-config` owns the Python/dependency runtime Source of Truth. The reference runtime is the `uv`-managed Hermes image `multi-agents-hermes:1.2.0` with Python `3.14.9`, `openpyxl==3.1.5`, and `korean-lunar-calendar==0.4.0`. Never use the host Ubuntu Python as proof of Hermes compatibility.
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

- The **PTO v0.1.0 calculation engine** is now published in `bhandara/pto-calculator/src/`, migrated from the legacy Gearbox snapshot without editing the calculation function bodies. The legacy PTO Gear **also remains in Gearbox** as the active operating Pipeline. Worktime and Payroll are not yet published Bhandara modules.
- No module may directly import another business calculator. Common functions may be imported only after their semantics match.
- `bhandara/pto-calculator/module.json` and `config.json` are now implemented with a PTO-specific public CLI dispatch (`run.py bhandara pto-calculator`). General automatic module discovery and cross-module JSON interchange are **not implemented**; do not imply Worktime/Payroll are runnable through the public CLI.
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

## PTO first public module — migration gate (passed for synthetic baseline)

- Source: agent-config `296f909dd84bbdb6196be84568bd0e60775c7dbd`, PTO `run.py` and 22 `functions` modules. Source content matches current agent-config main as checked on 2026-11-09. Import ownership changed without editing formulas.
- Public engine: `bhandara/pto-calculator/src/`; unchanged legacy diagnostics and date primitives are in `bhandara/common/`.
- Public CLI: `python run.py bhandara pto-calculator --config ... --input-dir ... --output-dir ...`; inputs and outputs must remain outside Git. See [PTO README](pto-calculator/README.md).
- **Verified before merge (2026-11-09):** Hermes Python 3.14.9, `openpyxl 3.1.5`, `korean-lunar-calendar 0.4.0`; 60/60 Bhandara `unittest` PASS, synthetic CLI execution and **`PTO_GOLDEN_PASS`** for the 2026-07 E001/E005/E020 fixture (private Golden; not committed).
- **Adapter status:** `agent-config` PR #144 merged its **opt-in Preview Adapter**, 20 tests and existing functional/infrastructure regressions passed, and a real synthetic two-employee CLI smoke returned `PASS`, 0 findings, `approved=false`, `finalizable=false`. This Adapter is **not registered as a Hermes Tool/Slack action**, and the legacy PTO Registry, existing Gear, Pipeline and Hermes service routing are unchanged. Registering the Tool and switching the active pipeline require separate PRs and user approval.

## Execution privacy and current limitations

- Hermes container: public source clone `/opt/agent-config/.external/portfolio` (read-only); private work data `/opt/data/bhandara` (host `/opt/agents/data/hermes/bhandara`). **The host `/opt/agents/data/bhandara` is not mounted into Hermes by the current Compose configuration.**
- The public PTO CLI's JSON can contain employee identifiers and grant details; unlike the private legacy Tooth, the local-only input adapter does not randomly pseudonymize IDs. Never copy real inputs, outputs, receipts or private Golden baselines to either Git repository or Slack.
- PTO v0.1.0 is anniversary-basis accrual/review only. It is not a full fiscal-year PTO balance, usage, payout, retirement settlement, legal compliance or payroll approval system.
- Base `ArtifactBatch` uses per-file atomic publication and rollback during handled exceptions; **crash recovery and one-transaction atomic publication across multiple files remain unimplemented**. The collision suffix is spelled `pto-result(1).json` (no space).
