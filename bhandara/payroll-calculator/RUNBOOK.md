# Payroll Calculator 운영 가이드

## 1. 목적

이 문서는 Payroll Calculator를 운영·검토·버전관리할 때 참고하는 운영 기준이다.

Payroll Calculator는 원본 근태를 해석하지 않는다. Worktime Calculator가 확정한 근로시간 사실값과 Compensation, 월별 Payroll Input, Pay Item Registry, 적용 Policy를 결합하여 급여 계산을 수행한다.

사회보험료와 원천세는 별도 Calculator의 책임이다.

## 2. 기준 정보

| 구분 | 파일 | 역할 |
|---|---|---|
| 급여항목 정의 | `gearbox/registry/pay-item-registry.json` | 급여항목 code, 성격, 허용 source, Worktime 연결관계 |
| 근로시간 법정기준 | `gearbox/policy/labor/<year>.json` | 해당 버전에서 확인한 근로시간 관련 법정 기준 |
| 급여 회사정책 | `gearbox/workflow/templates/payroll-calculator/payroll-policy.json` | 지급일, 지급시기, 일할계산, 금액처리 등 회사별 정책 |
| Worktime 결과 계약 | `gearbox/gear/worktime-calculator/contracts/worktime-result.json` | Payroll로 전달되는 근로시간 사실값 |
| 고정·계약 보상 | `compensation.xlsx` | 직원별 effective-dated 보상정보 |
| 월별 변동 입력 | `payroll-input/yyyy/yyyy-mm.xlsx` | 일회성 지급·공제·소급·조정 입력 |

RUNBOOK은 위 파일의 내용을 대체하는 Source of Truth가 아니다. 코드/JSON/XLSX contract와 RUNBOOK 내용이 다르면 운영 전에 차이를 확인한다.

## 3. 법령 검증 기록

법령 기반 Policy에는 최소한 다음 정보를 기록한다.

- `verified_date`: 해당 Policy 작성·검토 시 현행 법령을 확인한 날짜
- `law_name`: 확인한 법령명
- `law_effective_date`: 확인 당시 현행 법령 시행본의 시행일
- `legal_basis.article`: 해당 rule의 근거 조
- `legal_basis.paragraph`: 계산 또는 판정에 직접 필요한 경우 해당 항

예:

```json
{
  "legal_verification": {
    "verified_date": "2026-10-06",
    "law_name": "근로기준법",
    "law_effective_date": "2026-10-02"
  }
}
```

법 개정이 확인되면 과거 Policy를 임의로 덮어써 과거 계산의 재현성을 없애지 않는다. 적용시점에 따라 새 Policy version/file을 만들고 기존 파일을 보관한다.

법령 검토 시에는 현재 시행 중인 법령만 계산 Policy 후보로 사용한다. 과거 계산 재현이 필요한 경우 해당 기간에 적용되던 보관 Policy를 사용한다.

## 3.1 회사 적용 시 무엇을 어디서 바꾸는가

회사 도입 시에는 먼저 변경하려는 값의 성격을 구분한다. 계산 방법, 자료 조회기간, 급여항목 정의, 직원별 사실값을 같은 파일에 섞지 않는다.

| 바꾸려는 내용 | 수정 위치 | 대표 key / column | 비고 |
|---|---|---|---|
| 급여 지급일 | `payroll-policy.json` | `pay_schedule.pay_day` | 현재 계산 모듈 전체에서 직접 소비되는 범위는 별도 확인 |
| 기본급 일할 방식 | `payroll-policy.json` | `proration.base_salary.method` | v0.1은 `역일수`만 지원 |
| 최종 지급액 절사 단위 | `payroll-policy.json` | `amount_processing.unit` | 예: 10 → 10원 단위 |
| 최종 금액처리 방식 | `payroll-policy.json` | `amount_processing.method` | v0.1은 `절사`만 지원 |
| 절사 잔액 처리 | `payroll-policy.json` | `amount_processing.remainder.*` | Ledger transaction과 정산월 결정 |
| 통상임금 월 기준시간 | `payroll-policy.json` | `ordinary_wage.monthly_basis_hours` | `company_policy_required`이면 회사 도입 전 확정 필요 |
| 급여항목별 통상임금 정책 | `payroll-policy.json` | `ordinary_wage.pay_items` | Registry가 `회사정책`/별도판정인 항목에 사용 |
| 연장·야간·휴일의 기본 1.0 부분 처리 | `payroll-policy.json` | `worktime_pay.base_component_policy.*` | `별도지급/기지급/중첩` 계약에 맞춤 |
| Worktime을 당월/전월 중 어느 기간에서 가져올지 | `operating-config.json` | `source_rules.worktime.payment_basis` | 계산식이 아니라 source 조회기간 |
| Compensation 조회 기준 | `operating-config.json` | `source_rules.compensation.payment_basis` | 기본값 current |
| 특정 급여항목만 다른 지급기준 적용 | `operating-config.json` | `pay_item_rules.<code>` | source 기본값보다 우선 |
| 새로운 당월/이월형 기간 규칙 | `operating-config.json` | `payment_basis.*.period_rule` | 현재 `calendar_month + offset_months`만 지원 |
| 직원별 기본급·고정수당 금액 | `compensation.xlsx` | 급여항목 code column | 회사정책 파일이 아니라 compensation fact |
| 입사·퇴사 재직기간 | `employment-fact-schema.json` 계약 | `worker_id, employment_from, employment_to` | Compensation effective period와 별개 |
| 급여항목별 자격기간·지급개시 | `pay-item-eligibility-schema.json` 계약 | `worker_id, pay_item_code, eligibility_from/to, payable_rule` | Compensation 금액 유효기간과 별개 |
| 성과급·일회성 지급·기타공제 | 월별 `payroll-input/...xlsx` | `pay_item_code, amount/quantity` | 해당 급여 run의 transaction |
| 소급·전기조정의 실제 귀속기간 | 월별 Payroll Input | `origin_from, origin_to` | 둘을 항상 함께 입력 |
| 급여항목의 지급/공제/정산 성격 | `pay-item-registry.json` | `type` | 회사별 금액값이 아니라 시스템 분류 계약 |
| 급여항목이 들어올 수 있는 source | Registry | `allowed_sources` | 입력 검증 경계 |
| 법정 rule 연결 항목 | Registry | `legal_lock, legal_rule` | 회사 편의로 임의 변경하지 않음 |

**판단 기준:** “얼마를/어떻게 계산할까?”는 Payroll Policy, “어느 기간 자료를 볼까?”는 Operating Config, “이 항목은 무엇인가?”는 Registry, “이 직원에게 실제로 얼마/언제 적용됐나?”는 Compensation 또는 Payroll Input이다.

## 3.2 Pay Item Registry 상세

파일: `gearbox/registry/pay-item-registry.json`

Registry는 회사별 금액을 저장하는 파일이 아니다. 급여항목의 **의미와 계산 경계**를 정의한다.

| key | 의미 | 운영 시 주의 |
|---|---|---|
| `code` | 시스템 급여항목 식별자 | XLSX와 계산 모듈이 참조하므로 임의 rename 금지 |
| `label` | 사람용 표시명 | code와 의미가 어긋나지 않게 관리 |
| `type` | `지급/공제/정산` | Payroll Result의 direction 결정에 사용 |
| `category` | 업무상 분류 | 계산 direction과는 별도 |
| `obligation` | 법정/계약/회사정책 성격 | 법적 근거와 회사정책 구분 |
| `legal_lock` | 법정 rule과 연결된 항목 여부 | true 항목은 회사 편의로 계산 의미를 변경하지 않음 |
| `legal_rule` | 적용 법정 rule 식별자 | 법령 policy와 연결 |
| `variability` | 고정/변동/회사정책 | 항목 성격 |
| `proration` | 일할계산 가능/불가/회사정책/원항목추적 | 실제 계산 method는 Payroll Policy가 담당 |
| `ordinary_wage` | 통상임금 산입 성격 | `회사정책`, `별도판정`이면 별도 policy 필요 |
| `allowed_sources` | 해당 항목을 생성할 수 있는 source | 단순 설명이 아니라 Input Contract validation에 사용 |
| `worktime_linked` | Worktime 사실과 연결되는지 | true라고 Payroll이 원본 근태를 재해석하는 것은 아님 |
| `worktime_source` | 연결되는 Worktime fact | 예: overtime_hours |
| `trace_origin` | 원항목·원귀속기간 추적 필수 여부 | true면 origin 정보가 Result/Input에서 필수 |

새 회사에 항목이 없다는 이유로 기존 code를 다른 의미로 재사용하지 않는다. 새 의미가 필요하면 Registry에 새 code를 추가하고 source/policy/test를 함께 검토한다.

## 3.3 Payroll Policy 상세

파일: `gearbox/workflow/templates/payroll-calculator/payroll-policy.json`

이 파일은 **회사별 계산 방법**을 표현한다. 템플릿의 `company_policy_required`는 기본값이 아니라 “도입 전에 회사 기준을 확인해야 함”을 뜻한다.

### `pay_schedule`

- `pay_day`: 회사 급여 지급일.
- `missing_day_adjustment`: 해당 일자가 달력에 없을 때 처리 원칙.
- `pay_day_adjustment`: 휴일 등 지급일 조정 원칙.

현재 이 값들은 운영계약으로 보존되며 모든 값이 최신 calculation path에서 자동 실행되는 것은 아니다. 실제 지급일 산출 adapter 연결 전에는 “파일에 값이 있으므로 자동 적용된다”고 가정하지 않는다.

### `pay_period`

- `basis`: 급여기간의 기본 단위. 현재 템플릿은 `달력월`.
- `payment_timing`: 급여정책의 표시용 지급시기.

**주의:** source별 당월/이월 조회는 이 값이 아니라 `operating-config.json`에서 결정한다.

### `proration`

예: `proration.base_salary.method = 역일수`.

현재 v0.1의 기본급 proration은 급여월의 역일수를 분모로 사용한다. 지원하지 않는 method를 문서상 값만 바꿔 우회하지 않는다. 새 방식이 필요하면 계산 모듈과 테스트를 먼저 확장한다.

### `amount_processing`

- `unit`: 최종 지급액 처리 단위. 10이면 10원 단위.
- `method`: 현재 `절사`.
- `apply_at`: 현재 `최종지급액`. 개별 급여항목마다 절사하지 않는다.
- `remainder.handling`: 절사 잔액 처리. 현재 `settlement_ledger`.
- `remainder.transaction_type`: Ledger에 남길 거래유형. 현재 `rounding_carry`.
- `remainder.settlement_month`: 누적 carry를 정산할 월.
- `remainder.annual_settlement`: 정산월에 누적 잔액을 확정하는 단위/방식.

예를 들어 회사가 최종 지급액을 100원 단위 절사한다면 지원 범위 안에서는 `amount_processing.unit`을 100으로 바꾼다. “항목별 100원 절사”는 같은 설정 변경이 아니라 계산계약 변경이다.

### `ordinary_wage`

- `monthly_basis_hours`: 통상시급 계산에 사용할 회사 적용 월 기준시간.
- `pay_items`: Registry에서 회사정책 또는 별도판정으로 둔 항목의 회사별 산입 판단.

`company_policy_required` 상태로 실제 운영 계산을 확정하지 않는다.

### `worktime_pay.base_component_policy`

연장·야간·휴일 계산에서 가산분 외 기본 1.0 부분을 어떻게 처리할지 정한다.

- `별도지급`: 기본 1.0 부분을 해당 계산에서 추가 지급.
- `기지급`: 기본급 등 다른 항목에 이미 지급된 것으로 보고 추가하지 않음.
- `중첩`: 해당 premium의 중첩 의미를 유지.

현재 템플릿의 `company_policy_required` 항목은 회사의 임금구성과 지급방식을 확인해 결정한다.

### `effective_basis`

`amount_processing = settlement_date`는 최종 절사·잔액처리 정책을 급여 귀속기간이 아니라 실제 정산 시점에 유효한 policy로 적용한다는 계약이다. 과거 급여를 재계산할 때 과거 계산정책 전체를 현재 정책으로 덮어쓴다는 뜻이 아니다.

## 3.4 Operating Config 상세

파일: `gearbox/gear/payroll-calculator/operating-config.json`

이 파일은 **계산식이 아니라 source 조회기간**을 결정한다.

우선순위:

```text
explicit origin
    > explicit payment basis
    > pay item rule
    > source rule
```

### `payment_basis`

현재 기본 basis:

- `current`: 급여월과 같은 달, `offset_months=0`.
- `carryover`: 급여월의 직전 달, `offset_months=-1`.

예: payroll_period가 2026-10이면 current는 10/1~10/31, carryover는 9/1~9/30이다.

현재 resolver는 `period_rule.type=calendar_month`만 지원한다. “전월 21일~당월 20일” 같은 cutoff는 JSON 값만 억지로 바꾸지 않고 새 period rule 구현이 필요하다.

### `source_rules`

source 전체의 기본 조회 기준이다.

- `compensation.payment_basis=current`: 급여월과 겹치는 보상 history 조회.
- `worktime.payment_basis=carryover`: 직전 월 Worktime 사실 조회.
- `payroll_input.payment_basis=current`: 현재 run transaction의 기본 attribution.

회사가 당월 근태를 당월 급여에 반영한다면 지원 범위 안에서는:

```json
"worktime": {
  "payment_basis": "current"
}
```

로 변경한다. Worktime 계산 코드 수정은 필요 없다.

### `pay_item_rules`

source 기본규칙보다 특정 급여항목의 지급기준을 우선시키고 싶을 때 사용한다. `null`이면 별도 override가 없다는 뜻이다.

예를 들어 어떤 항목만 carryover로 운영하려면 해당 code에 `"carryover"`를 지정한다. Registry에 없는 임의 code를 추가해 우회하지 않는다.

### 명시적 origin

Payroll Input의 `origin_from/origin_to`가 함께 있으면 가장 높은 우선순위다. 이는 실제 귀속 사실을 보존하기 위한 override이며 “historical origin이므로 현재 run에서 제외”한다는 뜻이 아니다.

### XLSX 읽기와 Payroll 계약의 경계

XLSX 파일을 행 dictionary로 읽는 일반적인 mechanics는 `gearbox/core/xlsx.py`를 재사용한다. Payroll은 raw reader를 사용하고, 파일 존재 여부·필수 header·column 순서·Registry 기반 pay-item 허용 여부 등 Payroll 고유 입력 계약은 `input_contracts.py`에서 별도로 검증한다.

따라서 Core의 XLSX reader 재사용을 Payroll 입력 계약의 공통화로 해석하지 않는다. Payroll contract 오류와 actionable missing-file 오류는 계속 Payroll Gear가 소유한다.

## 3.5 Compensation XLSX 계약

템플릿: `gearbox/workflow/templates/payroll-calculator/compensation.xlsx`

첫 세 column은 순서까지 고정한다.

```text
worker_id | effective_from | effective_to | <Registry pay item columns...>
```

- `worker_id`: canonical worker identity.
- `effective_from`: 해당 보상 row 적용 시작일.
- `effective_to`: 종료일. 공란이면 open-ended.
- 이후 column: Registry에서 `allowed_sources`에 `compensation`이 있고 `type=지급`인 code만 허용.

한 직원의 보상기간이 중첩되면 추정하지 않고 오류 처리한다. 월중 급여 변경은 기존 row를 덮어쓰지 않고 effective period를 나누어 history로 남긴다.

Compensation은 회사 전체의 계산정책이 아니라 **직원별 계약·고정 보상 사실**이다.

## 3.5.1 Employment Fact와 Pay-item Eligibility 계약

공통 계약: `gearbox/workflow/templates/common/employment-fact-schema.json`

Payroll Eligibility 계약: `gearbox/gear/payroll-calculator/contracts/pay-item-eligibility-schema.json`

세 종류의 날짜는 서로 다른 사실이므로 자동 추론하지 않는다.

| 날짜 | 의미 |
|---|---|
| `employment_from/to` | 해당 worker의 재직 사실 기간 |
| `effective_from/to` | Compensation 금액이 유효한 기간 |
| `eligibility_from/to` | 특정 pay item을 받을 자격 사실 기간 |

`payable_rule`은 eligibility 사실을 바꾸는 값이 아니라 실제 지급개시 정책이다. 현재 지원값은 `from_eligibility_date`, `next_month`, `eligibility_month_full`이다.

v0.1 Employment는 worker별 단일 interval, Eligibility는 worker+pay_item별 단일 interval만 지원한다. 재입사 또는 자격 중단·재취득처럼 여러 interval이 필요한 경우 하나의 연속기간으로 합성하지 않는다. 이는 v0.2 history 확장 대상으로 남긴다.

기존 PTO의 `employee.xlsx`/prepared handoff는 현재 `employee_id, hire_date, termination_date`를 직접 소비하는 기존 계약이다. 새 Employment Fact를 만들었다는 이유로 이를 이미 `worker_id` 공통 계약으로 migration 완료한 것으로 간주하지 않는다.

### Compensation Calculation Adapter

`functions/compensation_calculation_adapter.py`는 새 계산공식을 소유하지 않는다. 다음 기존 모듈을 조합한다.

```text
prepared Compensation
    + Employment Fact
    + optional Eligibility Fact
    + 명시적 pay_item_codes
        ↓
Dependency Graph
        ↓
Proration / Eligibility Resolver
        ↓
calculated_result_adapter
        ↓
Payroll Result
```

운영상 중요한 규칙:

- Compensation row가 있더라도 Employment Fact가 없으면 월 전체 재직으로 추정하지 않고 실패한다.
- Registry에서 `compensation` source가 허용된 모든 항목을 자동으로 같은 방식으로 계산하지 않는다.
- 호출자가 `pay_item_codes`를 명시하며, 해당 항목에 필요한 회사 proration policy가 없으면 기존 계산계약이 실패한다.
- Eligibility fact는 calculation trace에 남지만 Payroll Result의 factual `origin_from/to`로 자동 복사하지 않는다.
- Operating Input Preparation이 결정한 source period는 `calculation_trace.operating_period`에 보존한다.

## 3.6 Payroll Input XLSX 계약

템플릿: `gearbox/workflow/templates/payroll-calculator/payroll-input/yyyy/yyyy-mm.xlsx`

header는 아래 8개를 순서까지 정확히 사용한다.

```text
worker_id
pay_item_code
amount
quantity
origin_pay_item_code
origin_from
origin_to
note
```

- `worker_id`: canonical worker identity.
- `pay_item_code`: Registry code.
- `amount`: 외부에서 확정된 금액. quantity 기반 계산이면 비울 수 있음.
- `quantity`: 수량/횟수 등 계산 입력. amount가 없으면 quantity가 있어야 함.
- `origin_pay_item_code`: 소급·전기조정의 원 급여항목.
- `origin_from/origin_to`: factual origin. 둘 중 하나만 입력할 수 없음.
- `note`: 운영 메모.

Registry의 `allowed_sources`에 `payroll_input`이 없는 항목은 입력할 수 없다. `trace_origin=true`인 정산항목은 `origin_pay_item_code`와 origin period를 보존한다.

Payroll Input은 **현재 급여 run에 들어온 transaction source**다. 10월 파일에 6월 귀속 성과급이 있고 origin이 6월이라고 해서 Operating Preparation이 해당 row를 제거하지 않는다.

## 3.7 Worktime Result 계약

계약: `gearbox/gear/worktime-calculator/contracts/worktime-result.json`

grain은 `worker_id + work_date`다. Payroll은 다음 사실을 전달받는다.

- identity/provenance: `worker_id, work_date, worktime_system, rule_ref`
- 시간: `scheduled_hours, worked_hours, ordinary_hours, overtime_hours, night_hours`
- 휴일: `holiday_work_hours_within_8, holiday_work_hours_over_8`
- 기타: `absence_hours, late_minutes, early_leave_minutes`
- 검증: `validation_flags`

`ERROR` flag가 있으면 Payroll handoff를 차단한다. `WARNING/REVIEW`는 값을 전달하되 상태를 보존한다.

야간시간은 연장/휴일시간과 중첩될 수 있으므로 Payroll에서 임의로 중복 제거하지 않는다.

회사별 “근태를 당월에 쓸지 전월에 쓸지”는 Worktime Result를 수정하는 문제가 아니라 `operating-config.source_rules.worktime.payment_basis` 문제다.

## 3.8 Payroll Result / Trace 계약

Payroll Result의 핵심:

- `worker_id, payroll_period, pay_item_code`
- Registry 기반 `item_type, direction`
- 양수 magnitude의 `calculated_amount`
- 선택적 `origin_pay_item_code, origin_from, origin_to`
- `source`
- `calculation_trace`

`origin_from/to`는 **금액의 실제 귀속 사실**이다. Operating Config가 source를 선택한 기간은 `calculation_trace.operating_period`에 저장하며 자동으로 origin으로 복사하지 않는다.

이미 계산된 Compensation/Worktime 결과는 `calculated_result_adapter.py`가 재계산하지 않고 Payroll Result로 승격하며 원 계산 결과를 `calculation_trace.calculation`에 보존한다.

Payroll Input은 `payroll_result_adapter.py`가 Result로 승격한다.

## 3.9 Payroll Run Input Adapter

파일: `gearbox/gear/payroll-calculator/functions/payroll_run_input.py`

`build_payroll_run_input()`은 한 급여 run에 필요한 source를 **계산 전에** 조립한다. 금액 계산 책임은 갖지 않는다.

입력:

- `payroll_period`: 지급 run 식별 월, `YYYY-MM`.
- `compensation_path`: Compensation XLSX.
- `payroll_input_path`: 해당 run의 Payroll Input XLSX.
- `worktime_rows`: Worktime Calculator Result payload.
- `registry`: Pay Item Registry.
- `operating_config`: source 기간 운영계약.

처리 순서:

```text
Compensation XLSX ── header/source contract ─┐
Payroll Input XLSX ─ header + row contract ─┼─→ Operating Input Preparation
Worktime Result ──── handoff validation ────┘
                                              ↓
                                      Payroll Run Input
```

반환 구조:

```text
payroll_period
compensation
  ├─ period
  └─ rows
worktime
  ├─ period
  └─ rows
payroll_input
  ├─ payroll_period
  ├─ source
  └─ rows[]
       ├─ row
       └─ period
```

Compensation과 Worktime은 resolved source period에 맞는 row만 남긴다. Payroll Input은 현재 run의 transaction이므로 historical `origin_from/to`가 있더라도 row를 제거하지 않고 해당 origin을 provenance resolution에 보존한다.

이 adapter에서 Payroll Input의 각 row에 `validate_payroll_input_row()`를 적용한다. 따라서 header가 맞더라도 Registry에 없는 code, `payroll_input` source가 허용되지 않은 code, 불완전한 origin pair 등은 run 진입 전에 차단된다.

예를 들어 `overtime_pay`는 Registry상 Payroll Calculator/Worktime 연동 계산이 소유하므로 Payroll Input XLSX에 수기 금액으로 넣어 우회할 수 없다.

회사별 Worktime 당월/이월 전환은 adapter 코드를 수정하지 않고 `operating-config.json > source_rules.worktime.payment_basis`를 변경한다.

현재 adapter는 **source calculation을 실행하지 않는다.** 다음 operational coordination 단계가 이 prepared input을 각 계산 모듈에 전달하여 Payroll Results를 생성한다.

## 3.8.1 Operational Composition

파일: `functions/payroll_operational_composition.py`

source별 계산 adapter가 만든 Payroll Results를 한 급여 run으로 합친 뒤 worker별로 `payroll_run.run_worker_payroll()`을 한 번씩 호출한다. 이 모듈은 Compensation, Worktime, Payroll Input의 계산식을 소유하지 않는다.

```text
Compensation Results ─┐
Worktime Results ─────┼─→ batch integrity → worker grouping → payroll_run
Payroll Input Results ┘
```

Batch 경계:

- 요청 `payroll_period`와 다른 Result가 하나라도 섞이면 실패한다. `payroll_totals`의 worker/period filtering에 기대어 잘못된 Result를 조용히 버리지 않는다.
- `worker_id`가 없는 Result는 실패한다.
- 같은 worker의 같은 `pay_item_code`가 여러 줄 존재하는 것은 허용한다. Worktime 일별 결과나 component별 결과가 정상적으로 여러 줄일 수 있기 때문이다.
- Result가 없는 worker에 validation 또는 settlement adjustment만 전달하면 실패한다.
- source별 result 묶음의 key는 composition 입력 그룹이며 Result 내부의 factual `source` provenance를 덮어쓰지 않는다.
- worker별 validation은 기존 Payroll Validation 계약에 따라 ERROR/ACTION_REQUIRED/INFO/WARNING으로 처리한다.
- settlement adjustment는 worker별로만 전달하며 다른 worker에게 전파하지 않는다.

현재 이 모듈까지 연결되면 **이미 계산된 세 source Result → worker별 Final Payroll** 경로가 닫힌다. 아직 source 파일부터 세 계산 adapter를 자동 호출하는 최상위 file-based operational entrypoint와 Settlement Ledger read/write I/O는 별도 단계다.

## 3.9 Validation과 Payroll Run

최신 runner: `gearbox/gear/payroll-calculator/functions/payroll_run.py`

runner는 source별 계산을 다시 수행하지 않는다. 이미 계산된 Payroll Results와 validations를 받아 다음만 수행한다.

```text
Payroll Results
    ↓
Validation 집계
    ├─ ERROR → final calculation 차단
    ├─ ACTION_REQUIRED → 계산 허용 / 자동확정 금지
    └─ INFO·WARNING → 계산·자동확정 허용
    ↓
Payroll Totals
    ↓
Final Amount Processing
```

`ACTION_REQUIRED`의 금액 결과는 검토를 위해 보존한다. `can_auto_finalize=false`는 계산금액이 무효라는 뜻이 아니라 운영자가 후속조치를 결정해야 한다는 뜻이다.

## 3.10 Settlement Ledger

계약: `gearbox/workflow/templates/payroll-calculator/settlement-ledger-schema.json`

Ledger는 append-only 거래원장으로 취급한다.

주요 column:

- `transaction_id`: unique transaction.
- `worker_id`: canonical worker.
- `transaction_type`: rounding_carry, advance, retroactive_pay, retroactive_deduction, prior_period_adjustment, rounding_settlement.
- `origin_period`: 거래 최초 발생/귀속기간.
- `origin_pay_item_code`: 원 급여항목.
- `amount`: 항상 양수.
- `direction`: 지급/공제.
- `settlement_period`: 실제 반영 급여기간.
- `settlement_batch_id`: 여러 거래의 정산 batch.
- `related_transaction_id`: 원거래와 후속 정산거래 연결.

미정산/부분정산/정산완료 status는 저장값이 아니라 원거래와 related transaction으로 계산한다.

Final Amount Processing의 절사 remainder는 `rounding_carry` ledger request로 생성된다. 현재 최신 operational path에는 Ledger read/write I/O와 settlement period assignment가 아직 완전히 연결되지 않았다.

## 4. 용어 및 데이터 정의

법률용어 대응은 **시스템 값이 법적 의미와 동일하게 확정된 경우에만** 적는다. 법적 판단을 위해 추가 가공이나 조건 판정이 필요한 값에는 법률용어를 억지로 대응시키지 않는다.

| Key / column | 시스템에서의 의미 | 법률용어 대응 또는 활용 | 사용 위치 |
|---|---|---|---|
| `worker_id` | Gearbox 내부 canonical 인적 식별자 | — | Worktime Result, compensation.xlsx, payroll input, Settlement Ledger |
| `employee_id` | CAPS·WEHAGO 등 외부/사내 시스템 사번 연결키. nullable | — | worker identity / external mapping |
| `work_date` | 근로 사실이 귀속되는 날짜 | — | `worktime-result.json` |
| `overtime_hours` | Worktime이 연장근로로 확정한 시간 | 연장근로시간 | `worktime-result.json` |
| `night_hours` | Worktime이 22:00~06:00 구간의 야간근로로 확정한 시간 | 야간근로시간 | `worktime-result.json` |
| `holiday_work_hours_within_8` | 휴일근로 중 8시간 이내 구간 | 휴일근로시간 중 8시간 이내 구간 | `worktime-result.json` |
| `holiday_work_hours_over_8` | 휴일근로 중 8시간 초과 구간 | 휴일근로시간 중 8시간 초과 구간 | `worktime-result.json` |
| `ordinary_hours` | Worktime의 일반 근로시간 분류값 | 법정 계산의 입력으로 사용될 수 있음 | `worktime-result.json` |
| `absence_hours` | 결근으로 분류된 시간량 | 공제 정책의 입력으로 사용될 수 있음 | `worktime-result.json` |
| `late_minutes` | 지각으로 분류된 분 단위 시간량 | 공제 정책의 입력으로 사용될 수 있음 | `worktime-result.json` |
| `early_leave_minutes` | 조퇴로 분류된 분 단위 시간량 | 공제 정책의 입력으로 사용될 수 있음 | `worktime-result.json` |
| `base_salary` | 직원별 기본급 금액 | — | `compensation.xlsx` |
| `effective_from` | 보상정보 적용 시작일 | — | `compensation.xlsx` |
| `effective_to` | 보상정보 적용 종료일; 공란이면 open-ended | — | `compensation.xlsx` |
| `pay_item_code` | Registry의 급여항목 식별 code | — | monthly payroll input |
| `origin_pay_item_code` | 소급·조정의 원 급여항목 | — | monthly payroll input |
| `origin_from/origin_to` | 소급·조정 대상 금액의 원 귀속기간 | — | monthly payroll input |
| `calculation_period` | 사용자가 계산을 요청한 정확한 기간 | — | Payroll calculation/result |
| `payroll_period` | 회사 급여정책상 급여 귀속기간 | — | Payroll calculation/result |
| `payment_date` | 해당 급여의 실제 지급 예정일 | — | Payroll calculation/result |

## 5. Worktime → Payroll 책임 경계

Payroll은 원본 출퇴근 기록을 다시 해석하지 않는다.

```text
Raw attendance
    ↓
Worktime Calculator
    ↓
validated Worktime Result
    ↓
Payroll Calculator
```

Worktime의 `validation_flags` 처리:

- `ERROR`: Payroll handoff 차단
- `WARNING`: 값과 함께 전달
- `REVIEW`: 값과 함께 전달하되 검토 필요 상태 유지

야간근로는 연장근로 또는 휴일근로와 시간적으로 중첩될 수 있으므로 중복을 제거하지 않는다.

휴일근로는 `holiday_work_hours_within_8`과 `holiday_work_hours_over_8`을 금액 계산 직전까지 별도로 보존한다.

## 6. Compensation 적용기간 판정

Compensation은 행 순서가 아니라 다음 관계로 선택한다.

```text
worker_id + work_date
        ↓
effective_from <= work_date <= effective_to
        ↓
exactly one compensation row
```

다음 상태에서는 추정하지 않고 실패한다.

- 해당 날짜의 보상정보 없음
- 동일 날짜에 두 개 이상의 보상기간 중첩
- 잘못된 날짜
- 음수 보상금액

월중 보상 변경은 날짜별로 각기 다른 Compensation row를 선택한다.

## 7. Payroll 입력 규칙

`compensation.xlsx`는 반복적으로 적용되는 계약·고정 보상을 저장한다.

월별 `payroll-input/yyyy/yyyy-mm.xlsx`는 일회성·변동·소급·조정 입력에 사용한다.

소급 또는 전기조정 항목은 필요한 경우 `origin_pay_item_code`와 `origin_from/origin_to`를 사용하여 원래 급여항목과 실제 귀속기간을 추적한다.

Registry의 `allowed_sources`는 해당 급여항목이 들어올 수 있는 허용 경계를 뜻한다. 실제 표준 Excel template에 모든 허용 항목이 반드시 column으로 존재해야 한다는 뜻은 아니다.

## 8. 오류 메시지

운영 로그와 CLI에서는 의미를 빠르게 구분하기 위해 다음 표기를 사용한다.

| 표시 | 의미 |
|---|---|
| 🚨 | 필수 resource 누락 등 실행을 시작하거나 계속할 수 없는 상태 |
| ❌ | contract 또는 deterministic validation 실패 |
| ⚠️ | 계산을 중단하지 않는 경고 |
| ✅ | 정상 완료 |

예:

```text
🚨 [payroll-calculator] Required input file not found

File: .../compensation.xlsx
Expected: Employee compensation workbook
Action: Add or synchronize the workbook and retry.
```

필수 XLSX가 없을 때 mock/fallback 값으로 계산을 계속하지 않는다.

## 9. Payroll Validation 상태와 자동처리 경계

Payroll Calculator는 계산 결과와 운영상 후속조치 필요 여부를 분리한다. Validation severity는 다음 네 단계로 사용한다.

| severity | 의미 | 계산 | 자동확정/후속처리 |
|---|---|---|---|
| `INFO` | 정보성 상태 | 가능 | 가능 |
| `WARNING` | 주의·검토가 권장되는 상태 | 가능 | 가능 |
| `ACTION_REQUIRED` | 계산 결과는 유효하지만 사람이 별도 조치를 결정해야 하는 상태 | 가능 | 금지 |
| `ERROR` | 안전하게 계산을 계속할 수 없는 상태 | 금지 | 금지 |

`ACTION_REQUIRED`는 단순 경고보다 강하다. 결과와 계산근거는 보존하지만 시스템이 그 결과를 자동 상계·회수·확정하는 근거로 사용하지 않는다. 각 `ACTION_REQUIRED` validation에는 운영자가 수행해야 할 `action`을 함께 기록한다.

이 severity는 현재 **Payroll Gear 내부 계약**이다. 다른 Gear의 상태값과 이름이나 의미를 억지로 통합하지 않는다.

- Worktime의 `REVIEW`: 추가 법적·기간 평가가 필요하지만 Worktime → Payroll handoff 자체를 차단하지 않는 상태
- PTO의 `UNDETERMINED`: 해당 PTO 판정을 확정할 수 없는 도메인 결과 상태
- Payroll의 `ACTION_REQUIRED`: 금액 계산은 가능하지만 자동 후속처리를 허용하지 않는 운영 상태

세 패턴이 여러 Gear에서 관찰되더라도 공통 Teeth 계약으로 승격하는 것은 실제 재사용 계약이 충분히 확인된 뒤 결정한다.

### 소속 변경·파견 등으로 Eligibility가 중단되는 경우

파견·소속 변경 등으로 동일 급여항목의 eligibility가 중단되거나 적용 주체가 달라지는 경우에는 하나의 연속 eligibility interval로 합성하지 않고 **기간을 나누어 별도 계산**한다.

향후 employee XLSX에서 파견 여부와 파견 시작·종료기간 등 effective-dated fact를 확인할 수 있게 되면 해당 사실을 기준으로 계산 대상 구간을 분리한다. 현재 v0.1에서는 이를 위한 새 employee XLSX column이나 multiple-eligibility schema를 선제적으로 만들지 않고 운영계약으로만 유지한다.

### Eligibility 종료와 지급 시작의 충돌

Eligibility fact와 지급정책은 별도로 보존한다. 특히 `next_month`처럼 정책상 지급 시작일이 실제 eligibility 종료일보다 늦어지는 경우, 종료된 자격을 open-ended 지급구간으로 바꾸지 않는다.

예: eligibility가 2026-10-16~2026-10-31이고 `payable_rule=next_month`이면 정책상 시작 후보는 2026-11-01이지만 그 전에 자격이 종료되었으므로 `payable_status=NOT_PAYABLE`이다. 계산 결과는 0원, proration segment는 빈 목록으로 유지한다.

eligibility가 다음 달까지 이어지는 경우에는 실제 종료일까지의 구간만 지급한다. open-ended eligibility는 정책상 지급 시작일부터 계속 가능한 구간으로 유지한다. 정책이 지급 시작일을 앞당기는 `eligibility_month_full`의 경우에도 원래 `eligibility_from/to` 사실은 trace에서 변경하지 않는다.

### 퇴직 후 소급정산

과거 급여를 재계산할 때 기존 확정 Historical Payroll Result는 **비교 기준**으로만 사용한다. Rerun Result는 기존 계산금액을 재사용하지 않고, 해당 과거 시점의 source fact·Compensation·Policy·rule을 다시 적용하여 독립적으로 재계산한다. 이후 Historical Payroll Result와 Rerun Result의 차액만 정산한다.

- 차액이 추가 지급이면 `retroactive_pay`로 현재 정산월에 지급할 수 있다.
- 차액이 공제 방향이고 근로자가 정산월 시작 전에 이미 퇴직했다면 `POST_TERMINATION_RECOVERY_REQUIRED` / `ACTION_REQUIRED`를 생성한다.
- 이 경우 시스템은 회수할 금액과 원 급여항목·귀속기간을 계산·보존하지만 **현재 급여에서 자동 상계하거나 자동 회수 처리하지 않는다.**
- 운영자는 실제 회수 가능 여부와 절차를 확인한 뒤 별도로 처리한다.
- 정산월 중 퇴직 예정이거나 재직 중인 근로자의 소급공제는 위 사유만으로 `ACTION_REQUIRED`가 되지 않는다.

Validation summary에서 `ERROR`가 있으면 `can_calculate=false`, `ACTION_REQUIRED`만 있으면 `can_calculate=true`이지만 `can_auto_finalize=false`로 처리한다.

## 10. 버전 관리

법령 또는 회사정책 변경 시 다음을 구분한다.

**법령 변경**
- 적용일 확인
- 새 versioned Policy 작성
- 기존 Policy 보관
- 영향받는 rule/test 확인
- 과거 기간 계산에는 당시 적용 Policy 사용

**회사정책 변경**
- 적용 시작일 확인
- `amount_processing`은 급여 귀속기간을 분할하지 않고 `settlement_date`에 유효한 정책을 적용
- 직전 계산영향 정책과 값이 다르면 계산을 중단하지 않고 `⚠️ POLICY_CHANGE`로 검토 요청
- 기존 결과의 재현 가능성을 훼손하지 않도록 version 관리
- proration, pay schedule, amount processing 등 영향범위 확인

**Contract 변경**
- Registry / JSON contract / XLSX header / parser / tests의 영향범위를 함께 확인

문서 자동 동기화는 현재 구현하지 않는다. 전체 Gearbox 문서 dependency를 별도로 조사한 뒤 공통 documentation-sync 규칙을 설계한다.

## 11. 현재 구현 상태

구현됨:
- Pay Item Registry와 Payroll Input/Compensation/Employment/Eligibility 계약
- Operating Config 기반 source 기간 결정과 Operating Input Preparation
- Compensation/Worktime/Payroll Input 계산·Result adapter
- 결근공제·주휴 specialized operational calculation
- requested-period가 월 고정급 자체를 축소하지 않는 calendar-day proration
- effective-dated Compensation 및 Eligibility v0.1
- Payroll Calculation Stage와 Operational Composition 분리
- Payroll Validation, Payroll Totals, Final Payroll
- configurable 최종지급액 절사 및 원정밀도 carry
- Settlement Ledger lifecycle, XLSX append-only boundary, review workbook 출력
- file-based Operational Payroll Pipeline
- Historical Rerun: 과거 source fact와 당시 Policy/rule을 사용한 독립 재계산
- Historical Result와 rerun Result의 aggregate 비교 및 소급지급/소급공제 생성
- Historical Rerun Result의 현재 급여 Composition 직접 합류
- 퇴직 후 소급공제의 `ACTION_REQUIRED` 전파와 자동확정 차단

Historical Rerun은 과거 확정 결과를 계산 입력으로 재사용하지 않는다. 저장된 Historical Payroll Result는 비교 baseline으로만 사용하고, rerun은 해당 과거기간의 source fact·Compensation·Operating Config·회사 Policy·법령 Policy로 Calculation Stage를 다시 실행한다.

비교 grain은 기본적으로 `worker_id + pay_item_code`의 historical run 총액이다. 동일 항목의 Worktime 행 수가 달라져도 개별 행을 억지로 짝짓지 않는다. 명시적 factual `origin_from/to`가 있는 Result는 서로 다른 origin을 합치지 않는다.

Historical Rerun 경로:

```text
Historical source facts
+ Historical Compensation
+ Historical Operating Config
+ Historical Company Policy
+ Historical Legal Policy
        ↓
Payroll Calculation Stage
        ↓
Recalculated Payroll Results
        ↓
Aggregate Historical Comparison
        ↑
Stored Historical Payroll Results
        ↓
retroactive_pay / retroactive_deduction
        ↓
Current Operational Payroll source group: historical_rerun
        ↓
Composition → Validation → Final Payroll
```

Historical Calculation Stage 자체는 Composition, Final Payroll, Settlement Ledger consumption/write를 수행하지 않는다. 생성된 retroactive Result를 현재 정산월 Operational Payroll에 명시적으로 전달한 뒤에만 현재월 Composition과 Final Payroll에 합류한다.

현재 feature branch의 전체 회귀 기준은 문서 하단의 실행환경 회귀 테스트 절을 따른다. 테스트 통과는 현재 contract/fixture 범위의 deterministic regression을 뜻하며 실제 회사 급여 운영의 법적·운영적 완결성을 선언하지 않는다.

아직 구현하지 않음:
- Payroll Policy history의 운영 저장/로딩 계약
- heterogeneous worker / 월중 보상변경 / 복수 급여기간 integration 확대
- Eligibility v0.2: 재입사·자격 중단/재취득 등 multiple interval
- manual historical adjustment escape hatch + WARNING
- 사회보험료 계산(별도 Calculator)
- 원천세 계산(별도 Calculator)

## 12. 실행환경 회귀 테스트

저장소의 공통 Gearbox runner를 회귀 기준으로 사용한다.

```bash
cd /opt/agents/config/agent-config
python3 gearbox/_tests/run.py
```

2026-10-07 `payroll-operating-contract-v0.1`에서 사용자가 직접 확인한 최신 기준:

```text
Teeth                         5
Legal Change Alert           12
PTO Calculator              171
Payroll Calculator          380
Infrastructure Plugins        5
Gateway Adapter              19
Git Contribution Validation  36
Protocol                     95
Workflow                     18
전체                         772 / 772 PASS
```

위 772건은 Historical Rerun 경로와 함께 Core XLSX raw/strict 계약, Payroll XLSX reader characterization 및 Core reader 재사용까지 포함하여 사용자가 직접 확인한 전체 회귀 기준이다. 해당 실행에서는 이전에 관찰된 Settlement Ledger XLSX 관련 ResourceWarning도 재현되지 않았다.

이 수치는 현재 contract/fixture 범위의 deterministic regression 기준이다. 실제 회사 급여 운영의 법적·운영적 완결성을 선언하는 값은 아니다.

### Operating Config와 계산 진입점의 경계

`operating-config.json`과 `operating_period_resolver.py`는 급여월을 기준으로 Compensation, Worktime, Payroll Input의 조회·귀속기간을 결정한다. 이 책임은 계산식 자체가 아니라 **입력 준비 단계**에 둔다.

현재 `payroll_orchestrator.py`는 이미 기간이 선별된 `compensation_rows`, `worktime_items`, `variable_items` 등을 받으며 Operating Period Resolver를 직접 호출하지 않는다. 따라서 현 v0.1에서 resolver가 존재한다는 사실만으로 실제 운영 입력이 자동으로 당월/이월 규칙에 맞게 필터링된다고 가정하면 안 된다.

향후 운영 연결은 다음 경계를 유지한다.

```text
payroll_period + operating-config
        ↓
Operating Input Preparation
        ├─ Compensation 조회기간 결정
        ├─ Worktime 조회기간 결정
        └─ Payroll Input origin/payment basis 결정
        ↓
계약 검증·기간 필터링된 입력
        ↓
Payroll calculation / orchestration
```

Operating Input Preparation은 명시적 `origin_from/origin_to` → 명시적 payment basis → pay item rule → source rule 우선순위를 사용한다. 계산 Orchestrator가 원본 파일 탐색이나 기본 귀속기간 추론까지 소유하도록 확장하지 않는다.

Operating Input Preparation v0.1은 `operating_input_preparation.py`로 구현한다.

- Compensation: resolver가 정한 기간과 effective period가 겹치는 history row를 선택한다.
- Worktime: resolver가 정한 기간 안의 `work_date`만 선택한다.
- Payroll Input: 해당 급여 run에 들어온 transaction은 유지하고, `origin_from/origin_to`와 payment basis를 귀속 trace로 resolve한다. 과거 귀속이라는 이유로 현재 지급월 transaction을 제거하지 않는다.
- 당월/이월 여부와 pay-item별 override는 코드에 고정하지 않고 `operating-config.json` 변경으로 switching한다.

Operating period와 factual origin은 같은 값으로 취급하지 않는다. `period_from/to`는 해당 source가 이번 급여 run에 선택된 운영 근거이고, `origin_from/to`는 실제 귀속 사실이다. 기본 source/pay-item rule로 결정된 운영기간을 Payroll Result의 `origin_from/to`에 자동 복사하지 않는다.

Payroll Input은 `payroll_result_adapter.py`를 통해 `calculation_trace.operating_period`에 `source`, `payment_basis`, `period_from/to`, `period_resolution`을 보존한다. 명시적 `origin_from/to`가 있는 transaction만 Result의 factual origin에도 해당 값을 유지한다.

`operating_trace.py`는 source별 계산 로직을 통합하지 않는다. Compensation, Worktime, Payroll Input의 계산 의미는 각각 유지하고, 계산 결과를 Payroll Result로 승격할 때 운영기간 provenance를 기존 calculation trace에 병합하는 최소 공통 helper만 제공한다. 현재는 Payroll Gear 내부 공통 모듈이며 Teeth로 승격하지 않는다.

`calculated_result_adapter.py`는 이미 계산이 끝난 Compensation·Worktime 등 source 결과를 재계산하지 않고 Payroll Result로 승격한다. 계산 결과의 `worker_id`, `pay_item_code`, `calculated_amount`를 공통 최소 계약으로 사용하며, 원 계산 결과 전체는 `calculation_trace.calculation`에 보존한다. Operating period가 전달되면 `calculation_trace.operating_period`에 추가하고 factual origin은 caller가 명시한 경우에만 설정한다. Compensation의 prorated recurring 결과도 이 계약을 만족하도록 `worker_id`를 보존한다.

기존 `payroll_orchestrator.py`는 Operating Input Preparation보다 먼저 만들어진 통합 경로이며, 입력의 period-resolution provenance를 Payroll Result 계약으로 승격시키는 최신 경로는 아니다. 따라서 새 adapter를 legacy orchestrator에 직접 결합하지 않는다. 기존 경로는 회귀 호환을 위해 유지하고, 실제 운영 연결은 `Payroll Result → Payroll Totals → Final Payroll` 경로를 기준으로 구성한다.

`payroll_run.py`는 최신 Payroll Result 경로의 운영 runner다. source별 Compensation/Worktime/Payroll Input 계산을 다시 소유하지 않고, 이미 계산·승격된 Payroll Result를 수집하여 Payroll Validation을 집계한 뒤 `Payroll Totals → Final Payroll`을 한 번 실행한다. `ERROR`가 있으면 final calculation을 차단하고, `ACTION_REQUIRED`는 금액 계산을 허용하되 `can_auto_finalize=false`로 자동확정을 금지한다. 기존 `payroll_orchestrator.py`는 회귀 호환을 위해 유지하며 새 운영 기능을 계속 누적하지 않는다.

## 13. 운영 점검표

Payroll 계산 전:

1. 계산 대상 기간을 확인한다.
2. 해당 기간에 적용되는 법령/회사 Policy version을 확인한다.
3. Policy의 `verified_date`와 `law_effective_date`를 확인한다.
4. 필수 XLSX와 JSON이 존재하는지 확인한다.
5. Worktime Result에 blocking ERROR가 없는지 확인한다.
6. 대상 직원의 Compensation이 계산기간 전체에 대해 유효하게 resolve되는지 확인한다.
7. 월별 Payroll Input의 Registry code와 origin 정보가 contract에 맞는지 확인한다.

법 개정 사실이 확인되었거나 현재 Policy의 법령 검증 시점 이후 개정 가능성이 의심되면 계산 규칙을 임의 수정하지 말고 먼저 법령을 재확인한 뒤 새 Policy version을 작성한다.

## Operational Worktime target rows와 reference history

Payroll Run Input은 Worktime을 두 용도로 구분한다.

- `worktime`: Operating Config의 지급 기준 기간을 적용한 계산 대상 rows. 연장·야간·휴일근로 등 이번 급여의 Worktime 연동 지급항목 계산에 사용한다.
- `worktime_history`: Worktime handoff 검증을 통과한 전체 입력 rows. 결근공제와 주휴처럼 실제 발생일의 근태 사실을 조회해야 하는 reference 계산에 사용한다.

두 집합을 합치거나 `worktime`의 기간 필터를 완화하지 않는다. 예를 들어 10월 급여가 Worktime carryover 기준으로 9월 연장근로를 지급하더라도, 10월 결근공제와 주휴 판단은 10월의 attendance fact를 참조해야 한다.

이는 Compensation의 `compensation`(현재 계산 대상)과 `compensation_history`(effective-dated reference lookup)를 분리한 것과 같은 원칙이다.

### Specialized operational inputs

결근공제와 주휴는 Worktime premium 계산에 흡수하지 않는다.

- `absence_events`: 결근·휴가의 명시적 사실. Worktime의 absence_hours만으로 결근공제를 추론하지 않는다.
- `absence_deduction_inputs`: worker별 `scheduled_workdays`, `paid_treatment_days` 등 해당 월 공제 basis.
- `weekly_holiday_inputs`: worker-week별 주휴 판단 입력. labor_status, pay_basis, weekly_scheduled_hours 등을 명시한다.

주휴 resolver가 월급 포함·자격 없음·비적용으로 별도 earning line을 만들지 않는 경우 0원 Payroll Result를 생성하지 않는다. 판단 결과는 `weekly_holiday_resolutions`에 보존한다.


---

## 12. 단독 실행 운영법 — 원본 매핑·정규화 (PR #90)

> **구현 상태 갱신:** `run.py normalize`, Worktime `run.py calculate`, Payroll `run.py calculate` 모두 독립 CLI로 구현됐다. 단, Payroll `run.py calculate`는 검토용 계산만 하며 최종 확정 CLI인 `run.py finalize`와 통합 `workflow/payroll/run.py`는 아직 구현 전이다. 본 12.1~12.3절은 원본 매핑 전용으로 유지한다.

### 12.1 어떤 자료를 넣는가

작업 폴더 예시: `/private/payroll/2026-10/` (실제 회사 급여 원본/직원 개인정보는 Git 저장소 밖에 보관한다).

| 파일 | 필수 여부 | 설명 |
|---|---|---|
| `manifest.json` | 필수 | **원본의 어떤 열이 어떤 표준 필드인지** 명시하는 매핑표, 기간, 자료 목록, 직원 ID 연결 |
| `employees.csv` | 이 예제에서 필수 | 급여 대상자를 정의하는 독립 직원명부. 최소 `employee_id`, `worker_id`로 매핑 |
| `schedule.csv` | 이 예제에서 필요 | 사번, 근무일, 일 구분, 소정 시작/종료·휴게 등 |
| `attendance.csv` | 이 예제에서 필요 | 사번, 날짜, 출퇴근·휴게 원본 |
| 기타 CSV/XLSX/JSON | 필요 시 | 보상정보, 연차 이벤트, 변동급여 등. `manifest.sources`에 추가하여 독립적으로 매핑 가능 |

**위 파일명은 예시일 뿐 고정 파일명 아님.** 회사별 원본 파일명과 열 이름은 `manifest.sources.<이름>.path` 및 `fields`에 지정한다. 예를 들어 `"work_date": {"source": "근무 기준일", "type": "date"}`처럼 작성한다. 사번이 서로 다르면 `link_to_roster.source_field`로 명부에 연결한다.

Excel은 `sheet`와 1부터 시작하는 `header_row`를 지정할 수 있다. CSV는 `encoding`(예: `cp949`), JSON은 `records_path`를 지정한다. 날짜 형식이 ISO가 아니면 `format`을 지정한다(예: `"%Y/%m/%d"`). 값 구분도 `value_map`으로 지정한다(예: `"근무" → "WORK"`). **원본 열을 추측하여 자동 결정하거나 알 수 없는 상태를 임의로 변환하지 않는다.**

혼합형 원본 매핑 예시: `examples/source-mapping-manifest.example.json`. 실제로 **그대로 실행할 수 있는 가상 데이터**는 `examples/source-mapping-demo/`에 있다. 예제 날짜는 2026-09-15, 지급월은 2026-10이다. 소정근로시간과 급여 자체를 산정하는 예제는 아니다.

### 12.2 실행 명령 — 독립 입력 가공

아래는 저장소 루트에서 실행한다.

```bash
cd /opt/agents/config/agent-config

# 저장소에 포함된 비식별 가상 데이터를 실행용 폴더로 복사
mkdir -p /tmp/payroll-source-demo-input
cp gearbox/gear/payroll-calculator/examples/source-mapping-demo/* \
  /tmp/payroll-source-demo-input/

# 오류 없이 변환되면 exit 0, 매핑·직원명부 문제는 리포트 남기고 exit 2
python3 gearbox/gear/payroll-calculator/run.py normalize \
  --input-dir /tmp/payroll-source-demo-input \
  --output-dir /tmp/payroll-source-demo-output
```

실제 회사 자료를 처리할 때에는 경로만 개인/사내 비공개 폴더로 교체한다. 실행 결과:

| 산출 파일 | 내용 |
|---|---|
| `normalized-input.json` | 원본별 표준화된 행과 원본 파일 SHA-256, **원본 행 번호·열 대응 및 ACCEPTED/REJECTED** |
| `review-report.json` | 처리 단계별 PASS/ERROR, 소스별 행 수·오류 항목 |
| `review-report.xlsx` | Run Summary, Stages, Sources, Review Required 탭 |

**검증 포인트:** `normalized-input.json`의 `sources.schedule.rows`, `sources.attendance.rows`에 canonical `employee_id`, `worker_id`, `work_date`가 나오는지 확인한다. `review-report.json`의 `status`가 `READY_FOR_CALCULATION`이면 **입력 매핑 검증만** 통과한 것이다. `BLOCKED`면 오류 사유를 확인해 매핑/원본을 수정하고 **새 출력 폴더로 재실행**한다. 원본에 문제 있는 행을 무시하고 급여를 확정하지 않는다.

```bash
python3 -m json.tool /tmp/payroll-source-demo-output/review-report.json
python3 -m json.tool /tmp/payroll-source-demo-output/normalized-input.json
```

기존 출력 폴더의 `normalized-input.json` 등을 덮어쓰지 않는다. 임금·개인정보가 들어 있는 가공본과 보고서는 Git에 커밋하거나 외부 공개 채널에 업로드하지 않는다.

### 12.3 에이전트에게 단독 가공을 시키는 요청문

아래 요청문에서 `<입력 폴더>`, `<지급월>`, `<새 출력 폴더>`만 실제 값으로 변경한다.

> **Payroll 원본 정규화만 실행해줘.** 저장소의 `gearbox/gear/payroll-calculator/RUNBOOK.md` 12절과 `BATCH-WORKFLOW.md`를 먼저 확인하고, `<입력 폴더>`의 회사 원본과 `manifest.json`을 비교해 열 → canonical 필드 대응을 검증해줘. 반드시 직원명부를 기준으로 ID를 대조하고 지급월은 `<지급월>`이야. 불분명한 열·날짜·근무구분은 추측하지 말고 `SOURCE_VALUE_INVALID` 등 명시적 문제로 보고해줘. `python3 gearbox/gear/payroll-calculator/run.py normalize --input-dir <입력 폴더> --output-dir <새 출력 폴더>`을 실행해줘. `normalized-input.json`, `review-report.json`, `review-report.xlsx`의 경로와 처리 건수, 오류·검토 사항을 알려줘. 원본 파일 변경, 승인 생성, 급여 계산·확정, Settlement Ledger 기록은 **하지 마**. 출력물이 있으면 기존 결과를 덮어쓰지 말고 새 경로를 사용해줘.

에이전트가 서버 실행/파일 쓰기 권한이 없으면 **실행했다고 보고하지 말고** 파일 매핑 제안, 실행 명령 및 확인할 오류만 제공하도록 한다.

### 12.4 Worktime / Payroll을 각각 계산시키는 요청문 (Python API 기준)

**Worktime 계산만:** 다음과 같이 요청한다.

> `gearbox/gear/worktime-calculator/RUNBOOK.md`의 단독 계산 절을 따라 원본 스케줄·근태와 명시된 사번 매핑/승인자료로 `worktime_source_adapter.calculate_from_monthly_records`를 호출해줘. 결과 `rows`, `expected_keys`, `validation_flags`를 별도로 보존해줘. `REVIEW`는 원인과 직원·일자 단위로 기록하고 승인정보를 지어내지 마. 기간 마감은 **실제 마감 승인자료가 있는 경우에만** `worktime_close.close_worktime_period`로 진행해줘. Payroll은 실행하지 마.

**Payroll 계산만:** 다음과 같이 요청한다.

> `gearbox/gear/payroll-calculator/RUNBOOK.md`의 최신 `payroll_operational_entrypoint.run_operational_payroll` 경로를 사용해줘. 확정/검증된 Worktime Result, 회사 정책, 급여항목 Registry, Compensation XLSX, 해당 월 Payroll Input XLSX, 재직·Eligibility facts를 제공할 테니 해당 급여월의 직원별 지급·공제·정산 금액을 계산하고 `payroll_output_xlsx.write_payroll_output_xlsx`로 **검토용 급여 XLSX**를 산출해줘. 직원별 `can_auto_finalize`과 Validation, 누락·계산 불가 사유를 별도로 보고해줘. `payroll_orchestrator.py` 구형 경로는 사용하지 마. 실제 승인 근거 없는 최종 확정, Ledger commit, 은행 지급 처리는 하지 마.

**운영 상태 업데이트(2026-10-30):** 위 두 요청은 초기 Python API 직접 실행 예제다. Worktime과 Payroll 모두 정식 독립 계산 CLI가 구현되었으므로 일반 운영은 각 Gear의 STANDALONE-CLI.md를 따른다. 회사 원본을 하나의 명령으로 가공→Worktime→Payroll로 연결하는 통합 Workflow는 별도 후속 작업이다. 승인자료 없이 성공·확정을 선언하면 안 된다.

### 12.5 PR 검증과 테스트 (서버 브랜치 직접 테스트)

```bash
cd /opt/agents/config/agent-config
git status --short
git fetch origin feat/payroll-source-mapping-report-v1
git switch --track origin/feat/payroll-source-mapping-report-v1

# 실제 소스 매핑·보고서 테스트
python3 -m unittest discover \
  -s gearbox/_tests/gear/payroll-calculator \
  -p 'test_source_pipeline.py'

# Gearbox 전체 단위 및 인프라 테스트
python3 gearbox/_tests/run.py
python3 gearbox/_tests/core_run.py
```

`git switch --track`은 해당 이름의 로컬 브랜치가 없을 때 사용한다. 이미 있으면 `git switch feat/payroll-source-mapping-report-v1` 후 `git pull --ff-only origin feat/payroll-source-mapping-report-v1`을 사용한다. 변경 파일이 있으면 checkout하기 전에 충돌 가능성을 검토한다. **Draft PR/worktree로 검증하지 않는다.**

PR에서 **요청한 기능의 단위 테스트만 통과한 상태**와 회사 월급여 계산의 실제 통합 검증은 구분한다.


### 12.6 Payroll 계산만 독립 실행 — CLI + 기존 Python API

**2026-10-30 서버 검증 완료.** 독립 `run.py calculate` CLI는 실제 구현되었고, 사용자 서버에서 단독 테스트 12건 및 Gearbox 전체·인프라 회귀가 PASS로 보고되었다.

운영 시 가장 먼저 **[Payroll 단독 실행 운영책](STANDALONE-CLI.md)** 을 확인한다. 운영책에 Compensation/Payroll Input XLSX, Worktime 계산 JSON 또는 승인된 close receipt, 회사·법정 Policy, Registry, Employment Facts, 독립 직원명부를 넣는 방법, 오류·검토 결과물, 가상자료 생성, 에이전트 호출 문구를 함께 기록했다.

실제 계산 명령:

```bash
cd /opt/agents/config/agent-config
python3 gearbox/gear/payroll-calculator/run.py calculate \
  --config /private/payroll/2026-10/payroll-config.json \
  --output-dir /private/payroll/output/2026-10/payroll-review-01
```

계산기 내부에서는 기존 `payroll_operational_entrypoint.run_operational_payroll` Python API를 유지하며, 별도 실행기의 `payroll_standalone_input` → `payroll_standalone_runner` → `payroll_standalone_report`가 입출력·직원명부 검증·검토 상태를 처리한다. Python API를 직접 호출하는 방식도 가능하지만, 직접 구현하면 **전체 직원명부 대조, `ACTION_REQUIRED` 부여, 원본 출처 추적과 보안 출력**을 호출자 스스로 보장해야 한다. 과거 Python heredoc 예제는 현재 CLI 설정 계약과 다르므로 운영 명령으로 사용하지 않는다.

이 명령은 **최종 급여대장/급여 승인/세금·보험 확정/정산원장 커밋이 아니라 검토용 임시 계산**이다. `REVIEW_REQUIRED`와 종료 코드 `2`가 정상적인 검토 필요 상태일 수 있으며, 금액을 확인하더라도 결제·송금 승인을 뜻하지 않는다. 오류가 있는 직원 때문에 엔진 전체가 실패하면 추정 급여를 출력하지 않고 실패 리포트만 남긴다.

후속 순서는 Worktime·Payroll 통합 Workflow → 직원별 예외 처리와 임시 산출물 → 세무·보험 및 최종 확정 게이트다.
