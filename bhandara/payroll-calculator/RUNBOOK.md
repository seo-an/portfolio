# 급여 계산기 사용 안내서 — 계약 사실과 지급항목을 분리해 계산하기


## 내 설정 파일 하나만 수정하는 독립 실행

`bhandara/payroll-calculator/user_settings.py`를 열고 문자열만 바꿉니다.
일반 사용자는 급여 산식을 수정하거나 JSON 설정 파일을 만들지 않아도
기본 Excel 폴더 구조로 **검토용 계산**을 실행할 수 있습니다.

| 변수 | 기본값 | 입력 가능한 값 |
|---|---|---|
| `PERIOD` | `"2026-07"` | `"YYYY-MM"` 형식의 급여월 |
| `EMPLOYEES_FILE` | `"common/employee.xlsx"` | 직원명부 Excel 상대 경로 |
| `IDENTITY_FILE` | `"common/id-map.xlsx"` | 사번 대응 ID_MAP Excel 상대 경로 |
| `CONTRACTS_FILE` | `"payroll/pay-contract.xlsx"` | 계약금액 Excel 상대 경로(있을 때 적용) |
| `COMPENSATION_FILE` | `"payroll/compensation.xlsx"` | 기존 월 보상액 Excel 상대 경로(계약 파일이 없을 때 적용) |
| `PAYROLL_INPUT_FILE` | `"payroll/payroll-input.xlsx"` | 월별 수당·공제 Excel 상대 경로 |
| `COMPANY_POLICY_FILE` | `"payroll/company-policy.json"` | **회사 계산 정책을 명시한 입력 파일** 상대 경로 |
| `WORKTIME_RESULT_FILE` | `"payroll/worktime-result.json"` | 검증 대상 Worktime 결과 상대 경로 |

자료를 `bhandara/data/input/`에 놓고 프로젝트 루트에서 실행합니다.

```bash
python run.py bhandara payroll-calculator
```

필요시 `--input-dir`, `--output-dir`을 지정할 수 있습니다.
`--config`를 명시하면 외부 전체 JSON 설정을 우선하며
`user_settings.py`와 섞지 않습니다. `--period`를 명시하면 기존
공통 Excel 입력 계약으로 계산합니다.

**이번 1차 설정 도입 범위는 기간·파일 역할입니다.** 회사별 지급
정책값 자체는 아직 입력 `company-policy.json`으로 전달해야 합니다.
다음 단계에서 허용된 **정책 선택 문자열**을 검토·도입할 예정이며,
현재 없는 지급 정책을 기본값으로 가정하지 않습니다.
근태가 없거나 정책에 근거가 부족하면 임의 지급액을 확정할 수 없습니다.
모든 결과는 검토용이며 승인·세금/보험 산출·원장 반영을 하지 않습니다.

---

**일반 사용자는 JSON 파일 경로를 편집할 필요가 없습니다.** 이 안내서는 연봉·월급·시급·일급 계약을 입력하고 월별 검토용 급여를 계산하는 방법을 설명합니다.

> 실제 급여 지급·세금 신고·근태 마감·법정 수당 최종 승인을 대신하지 않습니다. 특히 시급·일급의 연장·야간·휴일 가산수당과 유급주휴는 현재 별도 검토 대상입니다.

## 1. 필요한 Excel을 어디에 두나요?

[실제 Excel 샘플](../examples/sample/input/) 폴더를 아래처럼 `bhandara/data/input/`에 복사합니다.

```text
bhandara/data/input/
├── common/
│   ├── employee.xlsx                 직원명부
│   └── id-map.xlsx                   ID_MAP 시트
└── payroll/
    ├── pay-contract.xlsx            계약유형·계약금액 (필수)
    ├── pay-contract-components.xlsx 포함된 월 고정수당 (필수, 없으면 헤더만)
    ├── payroll-input.xlsx           성과급·월별 조정 (필수)
    ├── company-policy.json          회사별 계산 정책 (필수)
    ├── worktime-result.json         Worktime 계산결과 (필수)
    ├── service-contracts.xlsx       별도 용역계약 (선택)
    └── service-work-records.xlsx    용역 제공 시간·일수 (선택)
```

기본 입력은 `pay-contract.xlsx`입니다. 예전의 `compensation.xlsx`는
계약서에서 월 기본급을 도출해 **자동 생성하는 중간 결과**가 되었어요.
단, `pay-contract.xlsx`가 없는 기존 사용자는 월 급여액을 직접 적는
`compensation.xlsx` 방식도 계속 사용할 수 있습니다.

## 새로운 권장 계약 입력: Excel 하나에 2개 시트

새로운 계약 파일은 `payroll/pay-contract.xlsx` 하나에 **`Contracts`** 와
**`Components`** 두 시트를 만듭니다. 샘플은
[계약 사실 분리 예제 Excel](examples/contract-v2-two-sheet.demo.xlsx)에서
바로 열어 볼 수 있습니다. 이 예제는 구조를 설명하는 가상 직원 2명 자료이며,
80명 전체 실행용 입력은 아닙니다.

**Contracts 시트** (표시는 핵심 열만 발췌):

| contract_id | employee_id | pay_basis | contract_amount | amount_type | relationship_type |
|---|---|---|---:|---|---|
| CTR-BASE-001 | E001 | MONTHLY | 3500000 | BASE | REGULAR_EMPLOYEE |
| CTR-TOTAL-002 | E002 | MONTHLY | 3500000 | TOTAL | FIXED_TERM_EMPLOYEE |

실제 Excel에는 이 외에도 `effective_from`, `effective_to`,
`standard_day_hours` 열이 있어야 합니다. 이름은 정확히 일치해야 하고,
빈 `effective_to`는 계약이 계속 적용됨을 의미합니다.

**Components 시트**:

| contract_id | pay_item_code | monthly_amount |
|---|---|---:|
| CTR-BASE-001 | position_allowance | 150000 |
| CTR-BASE-001 | meal_allowance | 100000 |
| CTR-TOTAL-002 | base_salary | 3250000 |
| CTR-TOTAL-002 | position_allowance | 150000 |
| CTR-TOTAL-002 | meal_allowance | 100000 |

두 직원 모두 기본급과 수당을 **더하는 단일 지급항목 계산 구조**를 사용하지만,
계약 사실은 다르게 해석합니다.

- `BASE`: 계약금액 3,500,000원이 기본급. 수당 250,000원을 더해 **3,750,000원**.
- `TOTAL`: 계약금액 3,500,000원이 수당 포함 총액. 명시된 기본급 3,250,000원과 수당 250,000원을 더한 결과가 **3,500,000원**인지 검증.
- `RATE`: 시급·일급의 단가를 뜻하며, 기존 Worktime 시간·일수 검증을 유지합니다. 시급·일급 행의 `amount_type`은 `RATE`를 사용합니다.

`TOTAL`에서 `base_salary` 행을 누락하거나 항목의 합계가 계약금액과
다르면 계산을 차단합니다. **계약총액에서 수당을 빼 기본급을 임의 추정하지 않습니다.**
연봉의 경우 계약금액을 12개월에 균등 분할한다는 기존 검토 전제를 유지합니다.

`relationship_type`은
[계약 유형 코드표](resources/contract-types.json)에서 이름을 관리합니다.
ID의 `E`, `SVC` 같은 접두어로 법적 관계를 추정하지 않습니다.
**이 단계에서는 근로자 유형의 Payroll 계산만 v2로 실행합니다.**
독립 용역·외부 법인의 통합 입력은 후속 Worktime 인계 정리까지 마친 뒤 지원하며,
현재의 두 용역 파일은 기존 모드에서만 사용합니다.

**과세·비과세 판정은 아직 자동화하지 않았습니다.**
지급항목의 합계를 구했다고 원천세·보험 또는 비과세 요건이 확정된 것은 아닙니다.
세무 분류는 별도 정책과 검증이 붙기 전까지 미판정으로 취급합니다.

### 기존 샘플 사용자에게

현재 [80명 공통 샘플](../examples/sample/input/)은 여전히 **구형 단일 시트**
`pay-contract.xlsx` + `pay-contract-components.xlsx` 구조입니다.
호환성을 유지하기 위해 기존 방식도 그대로 지원합니다.

새로운 두 시트 방식에서는 `pay-contract-components.xlsx`가 필요 없습니다.
기존 자료의 `contract_amount`를 새 방식으로 옮길 때에는 계약서 원문이
기본급(`BASE`)인지 수당 포함 총액(`TOTAL`)인지 먼저 확인해야 합니다.
`amount_type`을 공란으로 두거나 추측해 채우면 안 됩니다.

---

## 2. 기존 단일 시트 pay-contract.xlsx — 무엇을 입력하나요?

엑셀의 **활성 시트**, 1행에 아래 **영문 헤더 그대로** 입력합니다. 두 번째 행부터 값입니다.

| contract_id | employee_id | pay_basis | contract_amount | effective_from | effective_to | standard_day_hours |
|---|---|---|---:|---|---|---:|
| CTR-0001 | E001 | ANNUAL | 37200000 | 2026-01-01 | | |
| CTR-0002 | E002 | MONTHLY | 2900000 | 2026-01-01 | | |
| CTR-0003 | E003 | HOURLY | 13450 | 2026-01-01 | | 8 |
| CTR-0004 | E004 | DAILY | 136000 | 2026-01-01 | | 8 |

- `employee_id`는 `common/id-map.xlsx`에 있는 **내부 직원번호**입니다.
- `pay_basis`: `ANNUAL` 연봉, `MONTHLY` 월급, `HOURLY` 시급, `DAILY` 일급.
- `contract_amount`에는 해당 단위의 **원 계약금액**을 입력합니다. 연봉·월급의 총액에 포함된 고정수당은 다음 Excel에 별도로 기록합니다.
- `effective_from`과 `effective_to`는 계약 적용기간입니다. 계속 적용 중이면 종료일은 비웁니다.
- `standard_day_hours`는 시급·일급 계약일 때 **계약상 하루 기준시간**입니다.
- 동일 직원의 계약기간이 겹치거나 계약이 없으면 계산을 차단합니다.

## 3. 기존 pay-contract-components.xlsx — 기본급과 포함 수당 분리

| contract_id | pay_item_code | monthly_amount |
|---|---|---:|
| CTR-0006 | position_allowance | 150000 |
| CTR-0006 | meal_allowance | 100000 |

**구형 방식(수당 포함 총액)에서 월급계약 350만 원 예시:** 월 계약 총액 3,500,000원 − 직책수당 150,000원 − 식대 100,000원
= **월 기본급 3,250,000원**. 기존 엔진에는 기본급, 직책수당, 식대를 별도의 급여항목으로 전달합니다.

연봉계약 역시 **연 계약 총액 ÷ 12 − 포함된 월 고정수당**으로 기본급을 구합니다. **현재는 연봉을 12개월에 동일하게 나누어 지급한다는 전제**만 지원하며, 13회 지급·성과급 포함·별도 상여 지급 계약은 그대로 적용하면 안 됩니다. 계산 결과에 `ANNUAL_12_EQUAL_INSTALLMENTS_ASSUMED` 검토 표시가 남습니다.
고정수당을 계약 총액에서 빼지 않고 또 지급하면 이중 계산이 됩니다.
지금 지원하는 분리 항목은 `position_allowance`와 `meal_allowance`입니다.
수당이 전혀 없어도 파일을 삭제하지 말고 **1행 헤더만 남겨두세요**.

## 4. 시급·일급 계약은 어떻게 계산하나요?

- **시급** = 계약 시급 × `Worktime.ordinary_hours`의 월간 합계
- **일급** = 계약 일급 × 계약상 하루 기준시간을 충족한 일수
- 기준시간 미충족, 결측 근태, 근태 승인 전 상태는 검토해야 합니다.
- **연장·야간·휴일 가산수당과 유급주휴분은 계산하지 않았습니다.** 0원이라는 뜻이 아닙니다. 기존 월급제 시간급 환산식을 억지로 적용하지 않기 위해 미산정으로 기록합니다.

샘플 `company-policy.json`은 **2026년 7월 급여에 6월 근태를 참조**하도록 되어 있습니다.
다른 달과 회사의 지급 귀속 규칙은 별도 확인이 필요합니다.
출입기 인증 자체는 승인된 근태가 아닙니다.

## 5. 프리랜서/용역계약은 별도로 검토합니다

선택 파일 `service-contracts.xlsx`에 가상 용역계약 8건이 들어 있습니다.
`service_contract_id`, `external_vendor_id`, `pay_basis`,
`contract_amount`, `effective_from`, `effective_to` 등을 기록합니다.
근로자 급여와 용역대가, 원천징수, 실질 근로자성 판단은 서로 다른 문제입니다.
따라서 **이 파일의 계약은 직원 급여 결과에 포함하지 않고 검토용으로만 표시**합니다.
용역 실적이 있는 경우 선택 파일 `service-work-records.xlsx`에 `service_contract_id`, `service_date`, `billable_hours`, `billable_days`, `source_reference`를 입력합니다. 시급형은 시간, 일급형은 일수를 곱해 **검토용 용역대가 추정액**을 별도 산출합니다. 계약 금액과 근로자 급여를 합치지 않으며, 지급 증빙·원천징수 검토 전에는 승인되지 않습니다. 실적 파일이 없으면 추정액을 0원으로 확정하지 않고 미제공으로 표시합니다.

가상 예: `SVC-001`은 일급 230,000원 × 제공 3일 = **690,000원**, `SVC-002`는 시급 37,000원 × 제공 22시간 = **814,000원**입니다. 실제 승인·지급 증빙은 아닙니다.

해당 계약이 없는 사용자는 이 파일을 생략해도 됩니다.

## 6. 급여 실행하기

프로젝트 루트에서:

```bash
python run.py bhandara payroll-calculator --period 2026-07
```

변동 수당은 `payroll-input.xlsx`에 입력하며, 이 파일의 첫 번째 열은
`employee_id`가 아닌 **`worker_id`**입니다. 공통 `ID_MAP` 시트에서 관계를 확인하세요.

실행 후 `bhandara/data/output/payroll-calculator/`에서 다음을 확인합니다.

| 파일 | 내용 |
|---|---|
| `contract-basis-review.xlsx` | **계약유형·원 금액·시간/일수·기본급·계산 규칙·검토 항목** |
| `contract-derived-compensation.xlsx` | 기존 Payroll에 넘긴 **실제 월 기준 보상액** |
| `payroll-calculation.xlsx` | 기존 Payroll에서 계산한 직원별 급여 초안 |
| `payroll-review.xlsx` | 미확정·검토 항목 |
| `contract-basis-review.json` | 계약 원본 해시와 계약별 산정 근거·프리랜서 별도 검토 기록 |

결과는 **`REVIEW_REQUIRED`(종료 코드 2)**일 수 있고, 승인·지급 완료를 의미하지 않습니다.
출력은 매번 새 폴더에 보관해 앞선 결과를 덮어쓰지 않습니다.

## 7. 기존 JSON·compensation.xlsx 사용자는?

`pay-contract.xlsx`를 사용하지 않는 경우 기존 `compensation.xlsx`와
`payroll-config.json` 경로 지정 방식은 계속 동작합니다.
이 고급 실행 방식의 코드 계약 및 예제는 [Payroll 개발자 README](README.md)와
[사용자 JSON 템플릿](examples/payroll-config.user-template.json)을 참고하세요.

## 8. 직원별 계산 오류 격리(고급 모드)

회사에서 제공한 `payroll-config.json`과 Excel을 사용하는 고급 모드에서만
`--isolate-worker-failures` 옵션을 추가할 수 있습니다.

```bash
python run.py bhandara payroll-calculator \
  --config /private/payroll-config.json \
  --output-dir /private/payroll-review-2026-10 \
  --isolate-worker-failures
```

- 전체 급여 계산이 예외로 실패한 경우에만 각 직원을 분리해 다시 계산합니다.
  정상 계산에는 이 옵션을 넣어도 기존 계산 결과가 바뀌지 않습니다.
- 한 명만 실패하면 정상 직원의 계산 결과는 남기고, 실패 직원은 **금액을
  0으로 채우지 않고 누락/검토 대상으로 표시**합니다.
- 직원명부에 없는 급여 원천 행, 매칭 불가한 직원 데이터, 전원 계산 실패는
  **전체 차단**합니다. 누락을 무시하고 지급 가능한 명부를 만들지 않습니다.
- 부분 성공이어도 상태는 `BLOCKED`, `finalizable=false`,
  `ledger_committed=false`입니다. 산출물은 반드시 담당자 확인 후 사용하세요.
- `--period`로 Excel 폴더만 지정하는 간편 모드에서는 아직 사용하지
  않습니다. 옵션 지원은 고급 `--config` 실행에 한정됩니다.

이 기능은 Bhandara 안에서 완결되며 Gearbox나 AWS가 설치되어 있지 않아도
독립 실행할 수 있습니다.
