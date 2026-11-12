# 급여 계산기 사용 안내서 — 계약금액부터 기본급 산정까지

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

## 2. pay-contract.xlsx — 무엇을 입력하나요?

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

## 3. pay-contract-components.xlsx — 기본급과 포함 수당 분리

| contract_id | pay_item_code | monthly_amount |
|---|---|---:|
| CTR-0006 | position_allowance | 150000 |
| CTR-0006 | meal_allowance | 100000 |

**월급계약 350만 원 예시:** 월 계약 총액 3,500,000원 − 직책수당 150,000원 − 식대 100,000원
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
