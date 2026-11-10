# Bhandara — Development / Operations RUNBOOK

**상태 (2026-11-10):** 공개 Base·PTO·Worktime·Payroll 독립 모듈 이전과 Hermes 서버 회귀검증·PR 병합을 마쳤다. 기존 Gearbox 운영 Pipeline은 그대로다. 현재 **모듈별 Base+1 격리 실행과 Worktime JSON → Payroll 데이터 계약 인계**를 검증하는 별도 PR 진행 중이며 서버 테스트 전이다. 계산식·정책·예외처리 개선은 후속 별도 프로젝트에서 실시한다.

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

- The **PTO v0.1.0 calculation engine** is now published in `bhandara/pto-calculator/src/`, migrated from the legacy Gearbox snapshot without editing the calculation function bodies. The legacy PTO Gear **also remains in Gearbox** as the active operating Pipeline. Worktime은 portfolio PR #6으로 기존 파일 그대로 이전하고 서버 검증·병합했다. Payroll은 portfolio PR #7으로 기존 계산 함수 이전과 회귀 검증 후 병합했다.
- No module may directly import another business calculator. Common functions may be imported only after their semantics match.
- `bhandara/pto-calculator/module.json` and `config.json` are now implemented with a PTO-specific public CLI dispatch (`run.py bhandara pto-calculator`). General automatic module discovery and cross-module JSON interchange are **not implemented**; Worktime is a direct CLI dispatch using the unchanged normalized-input.json contract. Payroll is a published opt-in CLI dispatch retaining the original normalize/calculate contracts.
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
- **Adapter status:** `agent-config` PR #144 merged its **opt-in Preview Adapter**, 20 tests and existing functional/infrastructure regressions passed, and a real synthetic two-employee CLI smoke returned `PASS`, 0 findings, `approved=false`, `finalizable=false`. Ananda의 합성 전용 Hermes Tool/Slack 호출은 검증되었고, 기존 PTO Registry·Gear·운영 Pipeline은 변경하지 않았다. 실제 운영 전환은 별도 설계 및 사용자 승인이 필요하다.

## Execution privacy and current limitations

- Hermes container: public source clone `/opt/agent-config/.external/portfolio` (read-only); private work data `/opt/data/bhandara` (host `/opt/agents/data/hermes/bhandara`). **The host `/opt/agents/data/bhandara` is not mounted into Hermes by the current Compose configuration.**
- The public PTO CLI's JSON can contain employee identifiers and grant details; unlike the private legacy Tooth, the local-only input adapter does not randomly pseudonymize IDs. Never copy real inputs, outputs, receipts or private Golden baselines to either Git repository or Slack.
- PTO v0.1.0 is anniversary-basis accrual/review only. It is not a full fiscal-year PTO balance, usage, payout, retirement settlement, legal compliance or payroll approval system.
- Base `ArtifactBatch` uses per-file atomic publication and rollback during handled exceptions; **crash recovery and one-transaction atomic publication across multiple files remain unimplemented**. The collision suffix is spelled `pto-result(1).json` (no space).

## Worktime Calculator — 무수정 코드 이전 완료

- 원본 `agent-config/gearbox/gear/worktime-calculator`의 **7개 함수 파일**, `run.py`, 원본 계약 JSON 및 예시 설정 JSON을 **바이트 단위로 동일하게 복사**했다.
- 변경은 Portfolio 최상위 `run.py`의 Worktime 명령 전달과 공개 모듈의 `module.json`·README·이전 검증 테스트에 한정한다. 계산식·예외처리·기존 Worktime 마감/검토 판단은 수정하지 않는다.
- [Worktime README](worktime-calculator/README.md)에서 원래 `normalized-input.json` 입력 계약과 실행·검증 명령을 확인한다. 외부 Source Mapping 정규화기는 이번 이전에 포함하지 않는다.
- `migration-manifest.json`의 원본 Git blob SHA 10개 확인과, 동일 합성 입력으로 기존 Worktime 진입점과 Portfolio 진입점이 낸 JSON·XLSX **내용 일치**만 이번 PR의 통과 기준으로 삼는다.
- 2026-11-10 Hermes 서버 이전 테스트와 기존 회귀 테스트 PASS 보고 후 portfolio PR #6을 병합했다. 새로운 기능·오류 격리·정책 개선 작업은 별도 프로젝트에서 다룬다.

## Payroll Calculator — 소스 이전 PR (서버 검증 대기)

- 원본 `agent-config/gearbox/gear/payroll-calculator` 추적 파일 85개 전체 복사, 77개 Git blob SHA 완전 일치. 8개 import·경로 참조만 변경했고, `migration-manifest.json`에서 역변환하여 원본 SHA가 일치하는지 테스트한다.
- 기존 `gearbox.core.date_interval`·`gearbox.diagnostics.contract`은 이미 공개된 동일 Base 함수에 연결한다. `gearbox.core.xlsx`와 diagnostics catalog 사본을 공개 Base로 이전하고 2026 정책/급여항목 registry 원본 JSON도 독립 모듈의 `resources/`에 보존한다.
- `run.py bhandara payroll-calculator`는 원본 `calculate`·`normalize` CLI를 새 포트폴리오 최상위 진입점에서 전달한다. 기존 Worktime close 계약, payroll 검토용 산출물 및 종료코드는 유지한다.
- [Payroll 이전 실행서](payroll-calculator/MIGRATION.md)의 테스트만 수행한다. 계산 로직·정책 개선, 사용자 데이터 연결, 운영 정본 전환, Payroll Workflow 수정은 포함하지 않는다.

## 세 계산기 독립 설치 상호배타 검증 (서버 검증 대기)

- 개별 설치에 Base와 해당 계산기 하나만 남기고 **서로 다른 임시 루트에서 합성 CLI를 실행**한다. PTO, Worktime, Payroll의 독립성은 정상 계산 기능을 다시 검토하는 작업과 구분한다.
- Payroll의 `worktime_close.py` 직접 참조 두 곳은 바이트가 동일한 **공통 Base의 검증 함수**로 경로만 연결한다. 원본 Worktime 코드는 유지하고 Payroll 원본 SHA 역변환 테스트도 계속 수행한다.
- Worktime과 Payroll을 함께 설치하지 않고도 **버전이 명시된 Worktime 결과 JSON 파일을 Payroll로 인계**할 수 있는지 테스트한다. 실제 근태 마감·급여 지급 승인을 수행하지 않는다.
- 자세한 명령과 판정 조건: [상호배타 검증 문서](MODULE-ISOLATION.md).
