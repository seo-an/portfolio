# Payroll P1-1 — Worktime 근무 사실 검토 인계

## 목적과 경계

Worktime의 `worktime-result.xlsx` / `WORKTIME` **단일 10열**을 Payroll에서 검토하기 위한 별도 도구 연결이다. 원본 열과 Worktime 구현은 변경하지 않는다. **출퇴근 시각의 차이, `actual_min - scheduled_min`, 휴무일 출근은 수당 지급을 결정하지 않는다.** 승인·근로 구간·야간 시각대·휴가 원장 등은 아직 이 입력에 없다.

현재 P1-1은 **잠재 검토 항목 표시와 기간/ID 검증만** 수행한다. 시간별 지급액·연장근로 가산·일급→분 환산·휴가 차감·퇴직/입사 정산·완료 승인 같은 P1-2/P2 기능을 구현하지 않는다.

## 입력

- P0의 `PayrollInputs`: 기존 5개 수당·성과급 역할을 검증한 결과. 그 안의 계약은 `select_contracts_for_period`로 대상 산정기간에 일치해야 한다.
- `worktime-result.xlsx`: Worktime Tool이 생성한 파일을 별도 명시적 경로로 받는다. `input_root/payroll`의 **여덟 번째 필수 Excel 파일이 아니다**.
- 대상 `period_from` / `period_to`: Worktime 결과의 날짜와 선택된 Payroll 계약기간에 일치해야 한다.

검증: `WORKTIME` 한 시트만 존재하는지, ID가 Excel 텍스트인지, 사용자/기간 범위, 직원×일자 중복, 일별 10열 정확성, 분의 0·`null` 구별, 부호 있는 출퇴근 차이의 유한 숫자 여부. 원본은 읽기 전용이며 읽는 동안 파일이 바뀌면 중단한다.

## 검토 코드 — 지급 판정 아님

| 코드 | 의미 |
|---|---|
| `ACTUAL_UNVERIFIED` | 검증된 실제근로 분수 없음. 0분으로 처리 금지 |
| `SCHEDULE_UNVERIFIED` | 예정근로 분수 없음. 휴무일로 처리 금지 |
| `ACTUAL_ABOVE_SCHEDULED` | 확인된 실제 분수가 예정 분수보다 큼. 승인된 초과근로는 아님 |
| `WORK_ON_SCHEDULED_OFF` | 예정 0분·실제 근로 양수. 법적 휴일 지급 대상이라는 결론은 아님 |
| `CLOCK_IN_EARLIER`, `CLOCK_OUT_LATER` | 예정 대비 조기 출근·지연 퇴근 시각 |
| `CLOCK_IN_LATER`, `CLOCK_OUT_EARLIER` | 예정 대비 지각·조기 퇴근 시각 |
| `LEAVE_SOURCE_REVIEW` | 유급/무급 등 휴가 구분·신청 ID 원장과 대조 필요 |
| `VERIFY_CLOCK_VS_WORK_MINUTES` | 실제근로 0분과 조기출근/지연퇴근 시각 차이의 교차 검토 필요 |

해당 코드가 없어도 *승인 완료*가 아니며, 검토 행의 `payment_decision=NOT_ASSESSED`, 전체 `payable_minutes_calculated=False`이다. Worktime 행이 없는 직원은 `employees_without_worktime_rows`에 나타나며, **무단결근·0시간 근로로 추정하지 않는다.** 사람용 Payroll 대장에는 Worktime 검토 컬럼을 새로 추가하지 않는다.

## 순수 함수·조합 호출

```python
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.worktime_bridge import build_payroll_worktime_review

inputs = read_payroll_inputs(
    "/secure/input",
    roles=("contracts", "allowance_assignments", "fixed_allowance_map",
           "bonus_budget", "bonus_allocation"),
)
result = build_payroll_worktime_review(
    inputs,
    "/secure/worktime/worktime-result.xlsx",
    period_from="2026-11-01",
    period_to="2026-11-30",
)
# result["payroll_register"]: 기존 P0 검토용 단일 급여대장 데이터
# result["worktime_review"]: 메모리상 근무 사실 검토 코드
```

사람용 `payroll-result.xlsx`는 기존 `write_payroll_result_xlsx`를 호출하여 출력한다. P1-1은 **별도 Excel을 생성하지 않는다**. `payroll_register`의 수당·공제 완료 플래그는 여전히 거짓이며 지급합계·실지급액은 공란이다.

## P1-2에서 필요한 별도 검증

- 직원별 **승인된 실제 근로구간(시작/종료 일시, 익일 구간 포함)**과 승인/거절 정보 및 증빙 ID
- 예정근로 구간·휴게·법정 휴일·야간 시간대·유급 휴가 원신청과의 교차 검증
- 현행 `overtime-rules.xlsx`의 `rule_id`와 대상 근로구간 매칭, 중복 가산 정책 및 `daily_base_rate`의 **시간 환산 분모/절사 정책**
- 대상 근로자·사업장별 정책 적용 범위, 중간 재계약/입퇴사 분할

현재 7개 XLSX 스키마에는 **근로 승인 구간 자체가 없다**. Worktime의 10열에 승인/급여 칼럼을 억지로 붙이지 않는다. P1-2 인수인계 시 검증된 별도 증빙의 경로·형태·정본과 책임을 확정한 뒤 계산을 구현한다.

## 테스트·운영

```bash
python3 -m unittest bhandara.tests.test_payroll_worktime_bridge_p1 -v
python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
```

Tool 계약이 변경되면 Gearbox 기능 및 인프라 호환성 검사 필수. `agent-config`는 PAUSE 중이며, 실제 Slack·실직원 데이터 연결이나 운영 설정을 변경하지 않는다.

## P1-2의 추가 연결

[OVERTIME-CANDIDATES.md](OVERTIME-CANDIDATES.md)의 승인구간·근로검증구간 및 분 환산 정책을 **외부에서 명시적으로** 전달한 경우만 P1-2 계산 후보를 만들 수 있다. P1-1 사실 검토와 별개이며, Worktime 10열의 시간 차이만으로 급여를 계산하지 않는다. 모든 금액은 `PARTIAL_REVIEW_ONLY` 상태로 표시된다.
