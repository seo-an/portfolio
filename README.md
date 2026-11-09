# Portfolio · Bhandara

Public, independently runnable HR calculation tools are being developed under `bhandara/`. The goal is to provide local Excel inputs and review JSON/XLSX results without a cloud account, AI agent, or external login.

> **Current status — public Base and Golden comparison utilities are available.** No PTO, Worktime, or Payroll calculator has yet been published in this repository. `run.py bhandara <module-id>` deliberately refuses to execute nonexistent calculators.

## Architecture

- **Public, deterministic calculations:** future modules under `bhandara/<module-id>/`, using shared `bhandara/common/` functions only.
- **Current Base:** Excel input/header validation, row/cell error reporting, source SHA-256, coordinated collision-safe artifact naming, and non-finalizing run receipts. [Base contract](bhandara/BASE-CONTRACT.md).
- **Current regression comparator:** `run.py compare-golden` compares existing and candidate private JSON results; it cannot calculate wages or PTO. [Golden comparison contract](bhandara/GOLDEN-COMPARISON.md).
- **Private orchestration:** Hermes/Gearbox from `seo-an/agent-config` acquire external files, handle authentication and approval, and will call future public tools through a local adapter.
- **Local data:** inputs, outputs, Golden results, and real employee records must stay out of both Git repositories. The ignored `bhandara/data/` path may be used locally; the Hermes server should use a restricted data directory outside the code clones.

## Python and dependencies

The deployment reference is uv-managed Hermes `multi-agents-hermes:1.2.0` with Python `3.14.9` (2026-11-09). The environment's approved dependency inventory is the Source of Truth; the public root `requirements.txt` currently pins only `openpyxl==3.1.5` required by Base.

Do not install packages into the Ubuntu system Python. A local separate environment can be created with [`uv`](https://docs.astral.sh/uv/):

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
.venv/bin/python run.py --help
.venv/bin/python -m unittest discover -s bhandara/tests -p 'test_*.py' -v
```

On Windows, use `.venv\Scripts\python.exe`. `install.py --check` only verifies installed prerequisites: it **does not** invoke uv, install packages, or modify Hermes.

## Golden regression comparison

```sh
python run.py compare-golden --profile payroll-workflow \
  --expected /private/golden/output --actual /private/candidate/output
```

This compares nine workflow JSON artifacts (not XLSX cell contents), and never modifies Golden results. For module API contracts and safety boundaries, see [Bhandara RUNBOOK](bhandara/RUNBOOK.md).
