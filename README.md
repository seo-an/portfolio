# Portfolio · Bhandara

Public, independently runnable HR calculation tools are being prepared under `bhandara/`.
The goal is for an HR practitioner to provide local Excel files, invoke a single Python
command, and review versioned JSON/XLSX results without creating accounts or connecting an AI agent.

> **Development status — Phase 1 bootstrap only.** This repository currently provides
> the directory layout and a non-destructive environment check. **No PTO, Worktime,
> or Payroll calculator is released here yet.** `run.py` intentionally refuses to
> calculate instead of returning misleading success.

## Architecture

- **Public calculation code:** this repository, `bhandara/<module-id>/`.
- **Shared bootstrap:** the repository-root `requirements.txt`, `install.py`, and `run.py`,
  with common utilities under `bhandara/common/`. Modules must not import each other's code.
- **Private orchestration:** Hermes / Gearbox from `seo-an/agent-config` acquire external
  files, manage permissions, and call the **same local CLI** through an Adapter. Hermes is
  never required for ordinary Bhandara usage.
- **Runtime data:** inputs and generated results must stay out of Git, including this
  repository and `agent-config`. The future local default is
  `bhandara/data/<module-id>/input/` and `output/` (ignored by Git). Never commit
  real employee, attendance, or payroll records.

## Environment and initial checks

The implementation's reference runtime is the `uv`-managed Hermes image
`multi-agents-hermes:1.2.0` with Python `3.14.9` (observed 2026-11-09).
Its package inventory, not this repository, is the **dependency Source of Truth**.
The Phase 1 bootstrap syntax requires Python 3.12 or newer; supported versions for each
calculator will be established by real runtime tests when that calculator is released.

For local use, install [`uv`](https://docs.astral.sh/uv/) using its official instructions.
Create a separate environment; **do not install into the operating system's Python**.
For example, from the repository root on macOS or Linux:

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
.venv/bin/python run.py --help
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
The bootstrap's `requirements.txt` does not yet install anything. `install.py` only
checks prerequisites; it neither invokes `uv` nor changes the Hermes environment.

## Planned operator workflow (not implemented)

1. Read the module's README for exact Excel filename, worksheet name, and required headers.
2. Place files in the module input folder. Additional unrelated Excel columns are allowed.
3. Run `python run.py bhandara <module-id>` using the environment's Python.
4. Inspect JSON, XLSX, and review reports in the output folder. Uncertain calculations
   remain review-only and never imply payroll authorization or accounting close.

The CLI, input contracts, per-record error isolation, and collision-safe versioned outputs
will be implemented and tested separately. See [Bhandara RUNBOOK](bhandara/RUNBOOK.md).
