# Payroll P1-5a — 계약변경·입퇴사 기간 분할과 **일할 후보금액**

## 적용 범위

신규 `payroll/settlement_coverage.py`는 근로자별 **재직 근거와 계약 배정 기간**을 확인하고, `payroll/segmented_settlement.py`는 해당 기간의 **기본급·고정수당 일할 후보금액**을 계산한다. 기존 계약 Reader, 정규 계약금액 Core, 고정수당 매핑 및 단일 급여대장 Writer를 재사용한다.

**중요:** Excel의 `calculation_period_from/to`는 법적 근로계약 유효기간이 아니라 **해당 계약 행에 선언된 급여 산정기간**이다. 실제 입사일·퇴사일·연봉협상 적용일은 별도 `settlement_plan`에서 확인된 뒤 명시해야 한다. 출퇴근·연차 자료로 자동 역산하지 않는다.

이번 구현은 **회사/계약에서 달력 일수 기준 일할 방식이 승인돼 있다는 가정으로 계산하는 후보 함수**다. 이 방식이 한국 법령·취업규칙·근로계약에 맞는지, 각 계약이나 입퇴사·휴가 상황에 적법한지 **이 코드가 검증하거나 보증하지 않는다**.

## 입력 계약

기존 `input_root/payroll/`의 **7개 개별 XLSX 파일·시트·헤더는 그대로 유지**한다. P1-5a는 기존의 5개 지급 역할(`contracts`, `allowance_assignments`, `fixed_allowance_map`, `bonus_budget`, `bonus_allocation`)과 **별도 외부 검증 객체**를 받는다. 새 8번째 Payroll Excel이나 필수 시트를 만들지 않는다.

다음은 **모두 합성자료**인 2026년 11월 예시다.

```json
{
  "schema_version": "0.1",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "snapshot_ref": "SYNTHETIC-EMPLOYMENT-REGISTER",
  "proration_method": "CALENDAR_DAYS",
  "rounding_mode": "DOWN",
  "employment_facts": [
    {
      "employee_id": "0001",
      "hired_on": "2024-01-01",
      "terminated_on": null,
      "status": "VERIFIED",
      "evidence_ref": "SYNTHETIC-EMPLOYMENT-E001"
    }
  ],
  "allocations": [
    {
      "employee_id": "0001",
      "contract_id": "C-OLD",
      "segment_from": "2026-11-01",
      "segment_to": "2026-11-15",
      "approval_status": "APPROVED",
      "approval_ref": "SYNTHETIC-CONTRACT-A",
      "policy_ref": "SYNTHETIC-DAY-PRORATION",
      "amount_basis": "FULL_CYCLE"
    },
    {
      "employee_id": "0001",
      "contract_id": "C-NEW",
      "segment_from": "2026-11-16",
      "segment_to": "2026-11-30",
      "approval_status": "APPROVED",
      "approval_ref": "SYNTHETIC-CONTRACT-B",
      "policy_ref": "SYNTHETIC-DAY-PRORATION",
      "amount_basis": "FULL_CYCLE"
    }
  ]
}
```

위 계약 `C-OLD`와 `C-NEW`는 **기존 CONTRACTS Excel에 각각 별개의 contract_id로 존재**해야 한다. 두 행의 선언 급여기간은 각각 11월 1~15일, 11월 16~30일일 수 있다. 월급 금액은 **월 전체에 대응하는 기준 월급**으로 입력해야 한다. 기존 Core는 이를 계약별 월 전체 금액으로 읽고, **각 배정에 `amount_basis=FULL_CYCLE`이 명시된 경우에만** 외부 승인 배정 기간만큼 P1-5a에서 일할계산한다. 이미 일할계산된 계약금액을 입력했다면 이 경로에서 다시 일할하면 안 된다. 월중 입사자가 계약 Excel에 11월 1~30일 전체 급여기간 하나를 가진 경우에도 배정 구간을 **실제 입사일~말일**로 제한할 수 있다.

### 계산과 원 단위 처리

- `MONTHLY`: 계약 월 전체 기본급 또는 수당액 × 해당 계약 적용 달력일수 ÷ 그 월 전체 일수
- `ANNUAL`: 기존 계약의 연봉 ÷ 명시된 연 지급횟수(12회 월급, 52회 주급에 한함) → 해당 회차 전체금액 × 배정일수 ÷ 회차 일수
- `WEEKLY`: 7일 회차 전체금액 × 배정일수 ÷ 7
- 원 단위 반올림은 **계약별로 먼저 하지 않고**, 직원×기간×수당 ID별 일할금액을 모두 합친 뒤 마지막 한 번 수행한다. `DOWN`(원 미만 절사) 또는 `HALF_UP`(반올림)을 반드시 명시한다.
- `amount_type=TOTAL` 계약은 **일할계산 이전에** 기존 Core에서 계약 월 전체 기본급+고정수당의 총액 일치를 확인한다. 재계약에서 과거 계약의 고정수당을 자동 승계하지 않는다.
- 같은 수당 ID는 계약 버전·Level이 달라도 최종 한 열로 합산한다. 계약 사이에 동일 ID 수당의 **과세 후보구분이나 정책 참조가 달라지면 자동으로 합치지 않고 중단**한다.
- 성과급 예산 배분은 기존 입력값을 **직원 기준으로 단 한 번** 계산하며 달력 일수로 자동 안분하지 않는다. **입퇴사자 보너스 자격·프로젝트 소속은 아직 외부 검증이 필요하다.**

합성 예시: 11월 1~15일 월 기본급 3,000,000원, 16~30일 3,600,000원이라면 기본급 후보는 3,000,000×15/30 + 3,600,000×15/30 = **3,300,000원**이다. 같은 기간 수당 100,000원→200,000원이라면 수당 후보는 **150,000원**이다.

## 중단 조건과 운영 경계

- 직원별 재직 증빙 `VERIFIED` 누락·중복 또는 계약 배정 승인 `APPROVED` 누락·중복
- 계약 ID가 직원·산정기간에 연결되지 않거나 계약 자체의 선언 산정기간을 벗어나는 일할 배정
- 재직 중 대상 기간의 **단 하루라도 배정 누락/중복**. 단순 공백을 무급휴가·결근으로 추정하지 않는다.
- 기간에 걸친 계약이 배정계획에 누락되거나, 동일 계약 ID가 중복 사용되거나, 서로 다른 지급일의 계약을 묵시적으로 합산하는 경우
- 월·주급 회차와 계산기간의 불일치, 기준 분모·원 단위 처리정책 누락, 수당 후보 과세구분 충돌
- **별도 외부 증빙 참조 문자열은 인증이 아니다.** 실제 계약/재직 사실의 서명·권한·시점은 이 계산기 바깥에서 검증해야 한다.

이번 단계에서 **유급·무급휴가 지급/공제, 결근 차감, 연차 잔여와 PTO Closing의 대조, 근태 오류 보정, 휴일급여 정책, 초과근무수당과 신규 일할 계약의 시간별 환산 동기화, 퇴직금/미사용연차수당, 4대보험·원천세는 구현하지 않는다.** P1-5b 및 P2 이후 작업이다. 이 별도 계산 경로는 기존 P1-2/3/4 근로수당 검토 경로를 **자동으로 합산하지 않는다**.

## 순수 함수 사용

```python
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.segmented_settlement import build_segmented_settlement_preview
from bhandara.payroll.output_excel import write_payroll_result_xlsx

inputs = read_payroll_inputs(
    "/secure/input",
    roles=("contracts", "allowance_assignments", "fixed_allowance_map",
           "bonus_budget", "bonus_allocation"),
)
preview = build_segmented_settlement_preview(
    inputs,
    settlement_plan=settlement_plan,
    period_from="2026-11-01",
    period_to="2026-11-30",
)
write_payroll_result_xlsx(
    preview["payroll_register"], "/secure/output/payroll-result.xlsx",
)
# preview["settlement_review"]: 배정된 계약·분수·원 미만 기본급 구성 기록
```

`payroll-result.xlsx`는 기존과 동일한 `PAYROLL` 단일 시트·동적 열 계약이다. **지급합계·공제합계·실지급액은 전부 공란**이며 `earnings_complete=False`, `deductions_complete=False`, `PARTIAL_REVIEW_ONLY` 및 `NOT_APPROVED`를 바꾸지 않는다.

**다음 단계:** [P1-5b-1](ATTENDANCE-SETTLEMENT.md)은 Worktime 휴가·결근 증빙과 외부 원 단위 정산액을 검증해 기본급 후보에 차감하는 별도 조합 함수다. 계약분할된 초과근무·복수 휴가 및 고정수당 정산은 P1-5b-2 잔여. 이후 P2 보험·세금·정산, P3 독립 JSON Tool CLI·전체 E2E, Gearbox 운영 연결 및 레거시 3종의 단계적 철수. `agent-config` 변경 PAUSE, 서버 브랜치 정리 보류.

합성 테스트: `python3 -m unittest bhandara.tests.test_payroll_segmented_settlement_p1 -v`.
