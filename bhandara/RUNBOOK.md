# Bhandara — Development / Operations RUNBOOK

**Status:** Phase 1 directory bootstrap; no calculators or complete Base yet.
**Authority:** Approved Bhandara architecture handoff v2.0 (2026-11-06). This
RUNBOOK is a public summary, not evidence that future interfaces exist.

## Ownership and compatibility

1. `seo-an/portfolio` owns reusable, deterministic calculation/normalization tools.
   It must not require Hermes, Slack, Google Drive, cloud APIs, or credentials.
2. `seo-an/agent-config` is the Python/dependency runtime Source of Truth. Use its
   `uv`-managed Hermes Python for runtime compatibility tests; never treat the Ubuntu
   host Python as a substitute. `requirements.txt` here is the approved dependency subset.
3. Gearbox owns authentication, source acquisition, approval, scheduling, orchestration,
   safe CLI delegation, and result transport. The future Hermes Adapter must execute
   the same Bhandara CLI as an ordinary user, from a local, ignored Portfolio clone.
4. Runtime employee and payroll data belong in restricted folders **outside both Git
   repositories** in Hermes. Local users may use the ignored `bhandara/data/` directory.

## Public module boundaries

- Each business module owns its own policy/calculation semantics; it must not import
  another business module. Shared code goes only in `bhandara/common/` when the
  responsibility and meaning are genuinely identical.
- `module.json` is a versioned public input/output contract. `config.json` is
  user-supplied execution configuration. Cross-module exchange is a versioned JSON
  result, not an imported Python function. Exact schemas are **not yet finalized**.
- Inputs select required headers; extra Excel columns should be ignored. Preserve
  original source files and row references. Do not silently infer missing approvals.
- Isolate errors at the smallest defensible scope (cell, row, person/day, person/period,
  or run). Preserve unaffected results; do not turn unknown wages into zero.
- Output files are not overwritten. If names collide, all files from a single run
  share the next `(1)`, `(2)`, ... suffix. Atomic reservations and failure recovery
  are **future Base implementation tasks**, not capabilities of this bootstrap.
- A calculation is not approval, payroll payment, tax settlement, or ledger commit.

## Development order and verification

- **Phase 0 baseline:** Existing Gearbox Golden input/output sets for PTO and
  Worktime/Payroll are stored privately on the server, not in this public repo.
  The 2026-11-09 baseline uses agent-config commit
  `296f909dd84bbdb6196be84568bd0e60775c7dbd`, Hermes image 1.2.0, Python 3.14.9.
  Baseline existence and hashes alone do not prove numerical equivalence.
- **Phase 1:** Preserve existing calculation behavior; bootstrap structure, then
  migrate approved paths behind compatibility boundaries. Do not silently adjust
  formulas, attendance interpretation, or review/approval status.
- **Phase 2:** Implement Base contracts, common CLI, input/output validation, and PTO
  as the first candidate. Then test via the existing Hermes Adapter boundary.
- **Later:** Worktime, Payroll, and potentially raw attendance normalizer, with separate
  behavior-change PRs where required.

Use Python `unittest`, never pytest. Portfolio bootstrap checks:

```sh
python3 -m unittest discover -s bhandara/tests -p 'test_*.py' -v
python3 install.py --check
python3 run.py --help
```

On the server, test each actual PR branch directly, not a worktree or Draft PR.
For changes involving the private Gearbox, also run its approved functionality and
core/infrastructure suite and compare Golden semantic results before recommending Merge.
No Git SSH pushes from the runtime server; no unapproved merge or deployment.
