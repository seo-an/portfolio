# Payroll Calculator

## 목적

Payroll Calculator는 확정된 근로시간 사실, effective-dated Compensation, 월별 Payroll Input, Pay Item Registry, 회사 Payroll Policy와 Operating Config를 결합하여 급여 지급·공제·정산 금액을 계산한다.

원본 출퇴근 기록은 Payroll에서 다시 해석하지 않는다. 근로시간 해석은 Worktime Calculator의 책임이며 사회보험료와 원천세는 별도 Calculator의 책임으로 유지한다.

## 현재 계산 경로

```text
Employment Fact / Pay-item Eligibility / Compensation / Payroll Input / Worktime Result
        ↓
Worktime handoff + Input Contract Validation
        ↓
Operating Input Preparation
        ├─ Compensation: effective period overlap
        ├─ Worktime: resolved work_date range
        └─ Payroll Input: transaction 유지 + origin/payment basis resolve
        ↓
Payroll calculation modules
        ├─ Proration / Eligibility / Effective-date
        ├─ Dependency Graph
        ├─ Worktime-linked premium calculation
        ├─ Absence / unpaid leave deduction
        └─ Weekly holiday calculation
        ↓
Payroll Result
        ↓
Payroll Validation
        ↓
Payroll Run
        ↓
Payroll Totals
        ↓
Final Amount Processing
        ↓
Payable Amount + Settlement Ledger request
```

과거 급여 수정은 기존 계산값을 재사용하지 않는다. 과거 시점의 source fact·Compensation·Policy·rule로 독립 재계산한 Rerun Result와 기존 확정 Historical Payroll Result를 비교하고 차액만 현재 정산월에 반영한다.

## 주요 설정 파일

| 파일 | 책임 |
|---|---|
| `gearbox/registry/pay-item-registry.json` | 급여항목의 의미, 유형, 허용 source, 일할/통상임금/법정 rule 연결 |
| `gearbox/workflow/templates/payroll-calculator/payroll-policy.json` | 회사별 계산 방법과 최종 금액처리 정책 |
| `gearbox/gear/payroll-calculator/operating-config.json` | 급여월 기준으로 어느 기간의 source를 사용할지 결정 |
| `gearbox/workflow/templates/payroll-calculator/compensation.xlsx` | 직원별 effective-dated 고정·계약 보상 |
| `gearbox/workflow/templates/payroll-calculator/payroll-input/yyyy/yyyy-mm.xlsx` | 해당 급여 run의 일회성·변동·조정 transaction |
| `gearbox/gear/worktime-calculator/contracts/worktime-result.json` | Worktime → Payroll 사실값 handoff 계약 |
| `gearbox/workflow/templates/payroll-calculator/settlement-ledger-schema.json` | 이월·소급·조정·절사잔액 거래 계약 |

회사 적용 시 어떤 값을 어디서 변경하는지는 `RUNBOOK.md`를 기준으로 확인한다.

## 핵심 경계

- Registry는 **무슨 급여항목인가**를 정의한다.
- Payroll Policy는 **어떻게 계산하는가**를 정의한다.
- Operating Config는 **어느 기간의 자료를 가져오는가**를 정의한다.
- Compensation과 Payroll Input은 **사실값**이다.
- Worktime Result는 **금액이 아닌 확정 근로시간 사실**이다.
- Payroll Result의 `origin_from/to`는 factual origin이고, `calculation_trace.operating_period`는 source 선택 provenance다. 둘을 자동으로 동일시하지 않는다.
- 계산 중간값은 Decimal 정밀도를 유지하고 회사 절사·반올림은 Final Amount Processing에서 한 번 적용한다.

## 최신 경로와 Legacy 경로

`payroll_run.py`가 최신 Payroll Result 기반 운영 runner다. 이미 계산·승격된 Payroll Results를 모아 Validation을 집계하고 Final Payroll을 실행한다.

`payroll_orchestrator.py`는 이전 통합 경로다. 기존 회귀 테스트와 업무 시나리오 보존을 위해 유지하지만 새 운영 책임을 계속 추가하지 않는다.

`examples/2026-10-payroll-e2e.json`과 `test_payroll_e2e_example.py`도 현재는 legacy orchestrator 회귀 시나리오다. 최신 operational E2E는 실제 input adapter 연결 단계에서 별도로 구성한다.

## 현재 구현 상태

구현됨:

- Pay Item Registry와 source validation
- Compensation / Payroll Input XLSX header contract
- Worktime handoff validation
- Operating Period Resolver와 Operating Input Preparation
- Employment Fact / Pay-item Eligibility fact contract와 validation
- effective-dated Compensation / Eligibility
- 명시된 recurring Compensation 항목 → Dependency Graph → Payroll Result adapter
- 월 고정급 역일수 proration
- Calculation Primitive / Base / Derived / Component / Dependency Graph
- Worktime-linked 연장·야간·휴일 계산
- 결근·무급휴가 공제
- 주휴 판정·금액 처리
- Payroll Result와 operating provenance
- Historical Result ↔ Rerun 차액 소급정산
- Payroll Validation
- Payroll Totals
- Final Amount Processing
- Settlement Ledger 계산 모듈
- 최신 `payroll_run.py`

현재 독립 실행까지 연결됨:

- `run.py normalize`: 원본 CSV/XLSX/JSON 매핑, 직원명부 대조, 검토 보고
- Worktime `run.py calculate`: 직원·일별 근로시간 계산 및 검토용 결과 생성
- Payroll `run.py calculate`: Compensation·Payroll Input·Worktime을 기존 Payroll 엔진으로 연결하고 독립 직원명부와 검토 상태를 확인해 임시 계산서와 검토 리포트 생성
- 입력·처리 모듈은 계산 엔진과 분리하며, Worktime close receipt 확인 기능은 유지

아직 구현 또는 완결되지 않은 부분:

- 통합 Workflow는 이번 브랜치에서 구현되어 서버 검증 대기 중. 회사별 raw source의 명시적 Compensation/Payroll Input XLSX 매핑은 지원하나 모든 사업장 양식의 자동 추정/정규화는 지원하지 않음
- Payroll 엔진의 배치 오류는 Workflow에서 직원별 재시도·정상 직원 임시 대장 보존으로 연결됨 (서버 검증 대기)
- 월 전체 대상자·근무일 완전성 독립 검증, 정산원장 승인·트랜잭션 처리
- Social Insurance Calculator, Withholding Tax Calculator 및 실제 최종 급여 확정 게이트

## 검증 현황 (2026-10-30)

PR #92의 Payroll 단독 실행 CLI는 사용자 서버에서 **전용 `unittest` 12건, Gearbox 전체 회귀 및 인프라 테스트 PASS**를 보고받았다. 이전 2026-10-07의 699건은 과거 테스트 기준이며 최신 전체 건수로 인용하지 않는다. 실제 회사 급여자료의 승인·세무·보험·마감 완결을 보증하지 않는다.

실행:

```bash
cd /opt/agents/config/agent-config
python3 -m unittest discover -s gearbox/_tests/gear/payroll-calculator -p 'test_payroll_standalone_cli.py'
python3 gearbox/_tests/run.py
python3 gearbox/_tests/core_run.py
```

## Worktime 마감 → 최종 급여대장 경로 (v0.1)

`functions/payroll_register.py`의 `run_closed_payroll`은 새 마감 게이트다. 먼저 승인된 Worktime close receipt가 Operating Config에서 정한 근로시간 귀속기간 전체를 덮는지 검사한 뒤 **기존** `payroll_operational_entrypoint.run_operational_payroll`을 호출한다. 새 급여 계산 엔진을 만들거나 Legacy Orchestrator로 우회하지 않는다.

- 원천 월간 근무표/근태 `→` `worktime_source_adapter` `→` `worktime_daily` `→` `worktime_close`
- 마감 receipt 검증 `→` existing operational Payroll `→` 승인 및 차대 검증 `→` `write_final_payroll_register_xlsx`
- 출력 `Final Register`, `Calculation Detail`, `Validation`, `Journal`, `Approval`
- 사업장 계정코드/세금·보험액 승인 근거/사용자 승인은 **필수 입력**이며 자동 산정하지 않는다.
- 금액 절사로 Settlement Ledger append가 필요하면 실제 commit 후 해당 증빙 `ledger_commit_ref`가 있어야 확정 가능하다.

이전 `payroll_output_xlsx.py`는 여전히 **검토용 출력**이며 변경하지 않았다. 새 확정 출력은 변경감지 checksum과 기존 파일 덮어쓰기 방지를 사용한다. checksum은 서명 또는 외부 저장소의 불변 보증은 아니다.

자세한 계약·차단 조건·테스트 명령은 `../worktime-calculator/RUNBOOK.md` 참고.

## Company-wide source adapter (mapping v0.1)

`run.py normalize` is now a standalone preprocessing command. It maps
arbitrary *structured* CSV/XLSX/JSON headers to canonical facts through an
explicit JSON manifest, reconciles records with an independent employee roster,
and writes normalized-input.json plus separate JSON/XLSX review reports.

This is a **partial foundation for the company batch Workflow**, not a final
end-to-end Payroll runner. The existing Worktime, payroll calculation and final
register APIs remain independent and unchanged. The independent Worktime and Payroll calculation CLIs are now available.
Workflow orchestration is implemented in the current branch and awaits server tests.
Employee-isolated Payroll fault continuation and a full-roster provisional
register are implemented in the Workflow (pending server verification).
Remaining tasks are complete period coverage, external payroll-program comparison,
tax/insurance calculation and safe transactional finalization.

See [BATCH-WORKFLOW.md](BATCH-WORKFLOW.md) for the complete intended contract
and runnable source-normalization command.


## Payroll standalone calculate CLI v0.1 (PR #92)

The independent command `python3 gearbox/gear/payroll-calculator/run.py calculate --config <config.json> --output-dir <new-output-dir>` is implemented. It reads Worktime results and Payroll input contracts, reuses the existing operational engine, reconciles an independently supplied employee roster, and emits **review-only** Payroll XLSX/JSON plus separate audit XLSX/JSON. Engine failures produce an error report instead of invented amounts.

It never changes the Settlement Ledger or issues payment approvals. Worktime UNCLOSED/REVIEW, tax/insurance verification and financial approvals are `ACTION_REQUIRED`, so no result is considered finalized. The one-command company Workflow is now implemented in a separate orchestration module (pending server regression); employee-isolated fault recovery is now implemented in Workflow (pending server validation); statutory/final approval gates remain.

See [STANDALONE-CLI.md](STANDALONE-CLI.md) for the input contract, runnable commands, synthetic CLI chain and agent instructions. Existing `run.py normalize` remains supported.


## 회사 전체 급여 Workflow v0.1 — 서버 검증 대기

개별 Gear와 기존 급여 계산 엔진의 독립성을 유지하며, 입력 정규화 → Worktime → Payroll XLSX 정본 연결 → Payroll 결과를 한 명령으로 실행한다. 단계별 실행 이력과 산출물 SHA-256은 Workflow가 기록한다. 비정상 데이터를 임의 승인하지 않고 원본 행 추적과 검토 파일을 보존한다.

**[통합 Workflow 운영책](../../workflow/payroll/RUNBOOK.md)** 에 실제 입력 설정, 1회 실행 명령, 가상 데이터 생성, Payroll 프로그램과의 대조 절차 및 에이전트 요청문을 기록했다. **실무용 계산·대조 자료**는 생산하지만, 실제 지급 확정 승인과 프로그램 차액 대조 자동화는 아직 미구현이다. 현재 서버 전체 테스트는 완료되지 않았다.


## Payroll 직원별 오류 격리 및 임시 급여대장 — 4단계

기존 Payroll 계산 공식과 단독 CLI는 변경하지 않고 Workflow에서 배치 엔진 예외가 발생했을 때만 직원별 재계산을 실행한다. 성공 직원의 급여액은 보존하고 실패 직원은 금액 공란/오류 사유로 표시한다. 대상자 전체가 포함된 `provisional-payroll-register.json/.xlsx`는 기존 급여 프로그램과의 대조용이며, 지급 승인이나 최종 급여 확정이 아니다.

`workflow-config.json`의 `isolate_worker_failures`는 기본 `true`이고, `false`로 설정하면 기존 배치 전체 오류 처리 방식을 적용한다. 원본 정규화나 Worktime이 이미 BLOCKED인 경우 Payroll을 실행하지 않는 안전 장치는 그대로 유지한다. 자세한 처리 조건과 테스트는 [통합 Workflow 운영책](../../workflow/payroll/RUNBOOK.md)을 참고한다. **아직 서버 검증 결과는 확인되지 않았다.**


## Company Policy Catalog와 시나리오 선택 (v0.2)

단일 company_policy_path와 별개로 여러 완전한 정책/상속 정책을 담은 policy_catalog_path를 지원한다. 시나리오를 지정하지 않으면 필수 default_scenario_id를 적용한다. 단독 Payroll 및 통합 Workflow CLI에 --scenario-id가 추가되며 실행 결과에 선택 ID·정책 해시·기본 기준 대비 변경 필드가 남는다. **급여 산식과 법정 정책, 원본 데이터는 바꾸지 않는다.** 자세한 실행·검증은 [POLICY-SCENARIOS.md](POLICY-SCENARIOS.md). 새로운 기능은 PR 브랜치에서 서버 검증 대기 중이다.


## 다중 회사정책 시나리오 비교 (신규 Workflow 기능)

`gearbox/workflow/payroll/run.py compare`는 하나의 정책 카탈로그에서 Default와 여러 Profile을 선택하여 같은 원본·근태 계산 결과로 순차 급여 산정한다. 1회 Normalize/Worktime 후 개별 Payroll 산출물을 보존하고 `scenario-comparison.json/.xlsx`에서 직원·급여항목별/회사 전체 차액과 정책 변경을 보고한다. 누락 계산은 0원으로 바꾸지 않으며 승인이나 Ledger commit을 하지 않는다. 자세한 명령과 테스트는 [SCENARIO-COMPARISON.md](../../workflow/payroll/SCENARIO-COMPARISON.md)를 참고한다. 현재 서버 회귀 테스트는 아직 완료되지 않았다.


## 외부 급여 프로그램 결과 대조 (Workflow, 서버 검증 대기)

기존 Payroll 계산 JSON과 외부 급여 프로그램 XLSX의 직원·급여항목·합계를 명시적 JSON 매핑으로 대조하는 별도의 Workflow 명령이 추가되었다. 기존 계산 엔진과 근태 원천자료를 변경하거나 재실행하지 않는다. 직원 ID·항목 명칭은 추정하지 않으며 사회보험·원천세 미산정 금액은 외부 전용 항목으로 표시한다. 실지급액은 내부 법정 공제가 완성되기 전까지 진단용 비교만 가능하다. 자세한 CLI, 오류 처리, JSON/XLSX 산출물은 [EXTERNAL-RECONCILIATION.md](../../workflow/payroll/EXTERNAL-RECONCILIATION.md)를 참고한다. 이 기능은 아직 서버 검증 대기 중이다.


## 회계식 급여대장·전월 대비 검토용 Excel (신규 Workflow 기능)

외부 급여 프로그램에서 대조할 공통 기준 데이터가 필요할 때 기존 계산 JSON으로부터 별도 Workbook을 생성한다. 계산식은 재실행·변경하지 않으며 직원별 수당·공제/귀속기간/근거, 계정별 차변·대변 분개와 합계 검증, 개인/회사 전체 전월 대비 증감, 증빙 SHA-256을 함께 출력한다. 미산정 보험·세금은 자동 분개하지 않는다. 기존 승인된 Final Register와 구별되는 **검토용 Provisional Accounting Book**이며 지급·전표 승인은 하지 않는다. 명령 및 11개 시트 구조는 [ACCOUNTING-BOOK.md](../../workflow/payroll/ACCOUNTING-BOOK.md)를 참고한다. 서버 검증은 아직 완료되지 않았다.
