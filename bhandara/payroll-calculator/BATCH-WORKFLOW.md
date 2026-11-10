# Payroll Batch Workflow Architecture (Source Adapter v0.1)

## Contract: independent gears, optional composition

The final target is **one command** to run company-wide data normalization → Worktime → Payroll → register + separate review report, while keeping both Worktime and Payroll independently callable. Source and calculation stages must not require the user to copy outputs between them.

This change implements **only the source normalization + evidence/report boundary**. It does **not** claim an end-to-end Payroll workflow, automatic statutory tax/insurance calculation, Worktime closure, or wage approval.

The current implemented command is:

~~~bash
python3 gearbox/gear/payroll-calculator/run.py normalize \
  --input-dir /private/payroll/2026-10 \
  --output-dir /private/payroll/output/2026-10/preparation-01
~~~

Put a JSON file named `manifest.json` in the input directory, or supply `--manifest /path/to/mapping.json`.

See `examples/source-mapping-manifest.example.json` for a mixed CSV / XLSX / JSON mapping. The example is a contract, not example payroll data.

## Input mapping

`manifest.sources` names each independent source. Each source declares:

- `path`: input-directory-relative file path. Traversal outside the input directory is rejected.
- `format`: optional `csv`, `xlsx`, `json`; inferred from file extension when omitted.
- `fields`: **canonical target field → original source column or nested JSON path**, e.g. `"worker_id": {"source": "급여관리ID", "required": true}`.
- `source`: a source column string or ordered list of alternative columns. If multiple alternative columns carry different values on one row, the row is rejected and `SOURCE_ALIAS_CONFLICT` is reported.
- `type`: `str`, `date`, `time`, `datetime`, `decimal`, `int`, `bool`; optional input `format` for date/time parsing. Decimal is serialized losslessly as text.
- `value_map`: explicit source-label → canonical-value mapping; unknown enumerations cause `SOURCE_VALUE_INVALID`. Never silently guess that "휴일" means one classification when the mapping is absent.
- `required` / `default`: default only when explicitly declared; required blank values produce a rejected row and an issue.
- `unique_by`: optional canonical business-key columns for deterministic duplicate detection.
- `sheet`, `header_row`: XLSX worksheet and 1-based heading row.
- `encoding`, `delimiter`: CSV charset (including cp949) and delimiter; UTF-8-BOM default.
- `records_path`: JSON nested list location, e.g. `data.records`.
- `link_to_roster.source_field`: canonical employee identity to reconcile against employee roster, and auto-populate canonical `worker_id`.

Input must already be **structured tabular data**. Extracting arbitrary prose, image-only PDFs, merged-cell forms or inconsistent multi-table workbooks needs a separate parser. Adding a parser must not modify the Worktime or Payroll calculation contracts.

Employee roster is an **independent source**, not inferred from employees who happen to appear in calculated Payroll Results. Both duplicate payroll worker IDs and unknown employees produce blocking errors. The current mapping detects identity consistency; a future batch coordinator will add effective-date employee eligibility, full payout-row completeness and time-period coverage.

## Artifacts and statuses

The command emits:

- `normalized-input.json`: canonical records for every source, row lineage (source name, row number, column mapping, accepted/rejected state), raw file SHA-256.
- `review-report.json`: stages, source row counts, rejects and structured issues.
- `review-report.xlsx`: "Run Summary", "Stages", "Sources", and "Review Required" sheets. Original raw cell values are **not** copied into the audit report.

Mapping errors are isolated per row when safe. A valid row in the same file can still normalize. A failed file leaves a named, visible failed stage rather than vanishing from the workflow. A source or roster with an error has `status=BLOCKED`; the CLI still writes the review report and exits **2**. Clean inputs have `status=READY_FOR_CALCULATION` and exit **0**. Neither status means wages were calculated, approved, or finalized.

No generated output file is silently overwritten. All outputs and source files may contain personal/confidential payroll data: create them in a local private directory **outside Git**, with restricted directory permissions. The command writes files mode 0600 on Unix.

## Independent calculator interfaces and integrated Workflow

The Worktime and Payroll calculate CLIs are implemented (PR #91 and PR #92). The one-command Workflow interface is implemented in the current branch (pending server verification); future close/finalize commands remain targets:

~~~text
worktime-calculator/run.py calculate --normalized ... --config ... --output-dir ...  # IMPLEMENTED
worktime-calculator/run.py close --input ... --approval ...
payroll-calculator/run.py calculate --config ... --output-dir ...  # IMPLEMENTED (review-only)
payroll-calculator/run.py finalize --input ... --approval ...
workflow/payroll/run.py run --config ... --output-dir ...  # IMPLEMENTED (review-only, pending verification)
~~~

The Workflow calls the existing versioned canonical contracts without changing Gear formulas. Worktime and Payroll remain independently callable; the Workflow owns the durable per-stage journal, file artifacts and explicit financial-source handoff. See [Workflow RUNBOOK](../../workflow/payroll/RUNBOOK.md).

Target stage outcomes:

- `PASS`: validated and completed.
- `WARNING`: computed with non-blocking advisory information.
- `REVIEW`: computed provisionally with documented uncertainty; **not finalizable**.
- `ERROR`: cannot compute correctly; retain error, source, worker, stage and impact.
- `SKIPPED`: not calculated due to upstream dependency, with a reason.
- `FINALIZED`: approvals, company policy and all blocking validations pass.

Continuing after failure is a **separate control from approving**. Worktime standalone now preserves unaffected employee/day results and separate review files, without approving/closing the period. Payroll standalone preserves its original review-only contract. The company Workflow now retries each independently declared worker **only after** a batch Payroll calculation exception, preserves unaffected payroll amounts, and writes a full-roster **PROVISIONAL** workbook plus a separate issue report. This is a Workflow-only exception handling layer; the standalone Gear is unchanged. It never calls `build_final_payroll_register` with guessed approvals, fabricates missing amounts, commits Settlement Ledger transactions, or marks uncertain wages as `FINALIZED`. If no workers can be calculated or a transaction cannot be assigned to an employee, the Workflow produces failure reports instead of invented payroll amounts. See [Workflow RUNBOOK](../../workflow/payroll/RUNBOOK.md).

## Existing calculator contracts retained

- Worktime: `worktime_source_adapter.calculate_from_monthly_records`, `worktime_daily.calculate_daily_worktime`, `worktime_close.close_worktime_period`.
- Payroll: `payroll_operational_entrypoint.run_operational_payroll`, `payroll_register.run_closed_payroll`, `write_final_payroll_register_xlsx`.
- Ledger: append-only settlement I/O and deduplication need transactional work at the future batch boundary.

No existing calculation algorithm has been changed by this source adapter.

## Regression

~~~bash
python3 -m unittest discover -s gearbox/_tests/gear/payroll-calculator -p 'test_source_pipeline.py'
python3 gearbox/_tests/run.py
python3 gearbox/_tests/core_run.py
~~~

Tests use temporary synthetic employee data, never real wage records.


## Standalone operating instructions (documented and executable now)

- **Source mapping CLI:** [Payroll RUNBOOK §12](RUNBOOK.md) documents required files, `normalize` command, output artifacts, rejection codes and an agent-ready Korean task request. Copy the private/synthetic fixture files from `examples/source-mapping-demo/` for a reproducible standalone smoke test.
- **Worktime standalone CLI + Python API:** [Worktime standalone CLI runbook](../worktime-calculator/STANDALONE-CLI.md) documents real commands, source mapping, approvals input, review artifacts and a copy-ready agent request. [Worktime RUNBOOK](../worktime-calculator/RUNBOOK.md) retains the lower-level Python API. **Neither automatically closes time records without approvals.**
- **Payroll standalone CLI + Python API:** [Payroll standalone CLI runbook](STANDALONE-CLI.md) describes input file contract, `run.py calculate`, review-only outputs, synthetic generator and agent prompt. [Payroll RUNBOOK §12.6](RUNBOOK.md) retains the lower-level Python API example. Placeholder config: `examples/payroll-standalone-config.example.json`.

Do not confuse a successful `normalize` run with Worktime/Payroll completion. The new one-command Workflow calculates and records reviewable wages for comparison with an external payroll program; it is **not** a pay approval or automatic Settlement Ledger commit. Employee-isolated Payroll engine recovery and final tax/insurance reconciliation remain future work.
