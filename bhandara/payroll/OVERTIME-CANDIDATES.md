# Payroll P1-2 — 승인구간 기반 가산수당 **검토 후보** 계산

## 구현 범위

`overtime_candidates.calculate_overtime_candidates()`는 **별도로 검증된 실제 근로구간**과 **승인된 세부구간**, 기존 `overtime-rules.xlsx`, 계약 기준 일급 및 **명시적인 분 환산·반올림 정책**을 연결해 지급 항목의 **금액 후보**를 계산한다.

`overtime_preview.build_overtime_candidate_preview()`는 기존 P1-1 `worktime-result.xlsx` 검증, P0의 계약 선택, P0의 고정수당/성과급과 결합하고 **기존 `payroll-result.xlsx` / `PAYROLL` 한 시트의 동적 `초과근무수당` 열**에 계산된 후보금액을 표시한다. 원본 Worktime Excel 10열 및 Payroll 7개 입력 파일·시트는 **전혀 변경하지 않는다.** 새 Excel 파일도 만들지 않는다.

이 결과는 실제 지급 결재나 완결된 급여가 **아니다**. `earnings_complete=False`, `deductions_complete=False`, 지급합계·공제합계·실지급액 공란, `PARTIAL_REVIEW_ONLY` 및 `NOT_APPROVED`를 유지한다.

## 데이터 신뢰 경계

- Worktime: 예정/검증된 실제 분과 출퇴근 시각 차이의 **사실**만 제공. `actual_min` 또는 Δ 자체를 추가 지급시간으로 해석하지 않음.
- 외부 검증 근로구간 `verified_work`: 휴게시간을 제외한 실제 근로 시작/종료 시각 및 검증 출처 ID를 **이미 신뢰할 수 있는 외부 시스템이 검증했을 때에만** 제공. 입력 문자열의 출처 진위를 이 코드가 증명하지는 못한다.
- 외부 승인구간 `approved_segments`: 같은 직원·근무일·검증 근로구간에 **완전히 포함되는** 구간, `approval_status=APPROVED`, 결재 참조·분류 참조·기본급 포함 근거를 요구.
- `overtime-rules.xlsx`: 기존 `rule_id/category/qualifying_from/to/minimum_minutes/daily_rate_multiplier/policy_ref` 열을 사용. `NIGHT`는 현행 시트의 `qualifying_from/to`에 22:00~06:00 같은 시각 범위를 명시.
- 명시적 `rate_policy`: **계약마다 다른** 기준 일급의 분 환산 분모, 지급 항목의 한국어 표시명, 원 단위 절사 정책 등. 실제 사용자/사업장별 정책은 아직 확정되지 않았고, 코드의 합성 예시는 법적 가산요율을 확정하지 않는다.

근로구간은 `YYYY-MM-DDTHH:MM` **같은 현지 시각 기준**이다. 시간대 변환·DST 규칙을 암묵적으로 적용하지 않는다. `work_date`는 구간 시작일이며 익일 퇴근도 해당 시작일에 귀속한다. 길이가 0이거나 24시간을 초과하는 구간은 거절한다.

## 외부 순수 입력 계약 예시 (모두 합성 자료)

검증 실제 근로구간(복수 가능):

```python
verified_work = [{
    "evidence_id": "W001",
    "employee_id": "0001",
    "work_date": "2026-11-02",
    "start_at": "2026-11-02T17:00",
    "end_at": "2026-11-02T18:00",
    "verification_ref": "VERIFIED-SYNTHETIC",
}]
```

승인 근로구간(근로구간의 일부 또는 전부):

```python
approved_segments = [{
    "segment_id": "A001",
    "work_evidence_id": "W001",
    "employee_id": "0001",
    "work_date": "2026-11-02",
    "start_at": "2026-11-02T17:00",
    "end_at": "2026-11-02T18:00",
    "rule_id": "OT01",
    "approval_status": "APPROVED",
    "approval_ref": "APPROVED-SYNTHETIC",
    "classification_ref": "CLASSIFIED-SYNTHETIC",
    "base_pay_includes_time": False,
    "base_inclusion_ref": "BASE-EXCLUSION-SYNTHETIC",
}]
```

분 환산·이름 및 원 단위 정책:

```python
rate_policy = {
    "multiplier_semantics": "TOTAL_RATE",
    "rounding_scope": "EMPLOYEE_RULE_PERIOD",
    "rounding_mode": "DOWN",
    "reference_day_minutes_by_contract": {"C01": 480},
    "rule_labels": {"OT01": "연장근로수당"},
}
```

`base_pay_includes_time=False`는 **해당 승인구간의 기준 1배분 임금이 계약 기본급에 이미 포함되지 않았음을 외부 자료로 확인**했다는 의미다. 이 경우 `daily_rate_multiplier` 전부를 추가분으로 계산한다. `True`는 기준 1배분 임금이 이미 지급 기본급에 포함돼 있음을 확인했다는 의미이며, 명시된 **총 배율에서 1을 뺀 가산 부분만** 후보로 계산한다. 예를 들어 기준 1일 96,000원/480분, 승인 60분, 총 배율 1.5일 때:

| 기본급 포함 근거 | 계산 | 금액 후보 |
|---|---|---:|
| 미포함(False) | 96,000 ÷ 480 × 60 × 1.5 | 18,000원 |
| 포함(True) | 96,000 ÷ 480 × 60 × (1.5 − 1) | 6,000원 |

**이 환산·기본급 포함 계약은 합성 테스트에서 동작하는 계산 정책이지, 특정 법령·취업규칙·계약서에 적합하다는 인증이 아니다.** `policy_ref`, `approval_ref`, `classification_ref`, `base_inclusion_ref`는 추적 가능한 ID를 요구하지만, 현재 도구는 외부 원장의 원문/서명/권한까지 검증하지 않는다. 외부 근거가 없으면 실제 급여에는 사용하면 안 된다.

## 적용 중단 조건

- 승인 참조·실근로 검증 참조·분류 근거·기본급 포함 근거가 없거나 승인 상태가 `APPROVED`가 아님.
- 승인구간이 근로 검증구간에서 벗어나거나, 근로 검증구간의 일별 총합이 Worktime `actual_min`보다 큼. `actual_min=None`은 차단하고 0분과 구분.
- 근로 검증구간끼리 중복되는 경우는 계속 차단. 승인 구간끼리 같은 직원의 시간이 겹치면 **기본적으로 차단**하며, P1-4 [명시적 중복가산 정책](OVERTIME-STACKING.md)에 지정한 활성 분류 조합/기본급 포함 여부/기준 1배분 배정 원칙을 모두 통과한 경우에만 **산정 후보**로 처리. 실제 법적 적정성 검증과는 별개.
- 승인구간 길이가 정책 `minimum_minutes`보다 짧음: **0원 처리하지 않고 중단·사람 검토**.
- 야간근로 구간이 `qualifying_from/to`를 벗어남. 익일 06:00 등 시각 자정 넘김 지원. 기존 7개 엑셀의 빈 시각 지정은 야간 판단 근거가 아님.
- 규칙 ID·표시명·계약 ID별 분 환산 분모·원 단위 처리정책이 모호하거나 누락됨.
- 중도 입퇴사/재계약에 따른 산정기간 분할, 외부 휴가·스케줄 및 출근시간 연계 증빙 미검증. P0 기간 검증은 계속 정확 일치만 인정.

**중요:** `HOLIDAY` 분류는 외부 `classification_ref`가 이미 확인했다고 선언할 뿐, 이 코드가 한국 공휴일·사업장 소정휴일 또는 법정 휴일 여부를 판정하지 않는다. 가산 배율의 법적 적정성, 추가근로 한도, 휴게, 복수구간/휴가상계도 이 단계에서는 심사하지 않는다.

## 합성 함수 호출

```python
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.overtime_preview import build_overtime_candidate_preview
from bhandara.payroll.output_excel import write_payroll_result_xlsx

inputs = read_payroll_inputs(
    "/secure/input",
    roles=(
        "contracts", "allowance_assignments", "fixed_allowance_map",
        "bonus_budget", "bonus_allocation", "overtime_rules",
    ),
)

result = build_overtime_candidate_preview(
    inputs, "/secure/worktime/worktime-result.xlsx",
    period_from="2026-11-01", period_to="2026-11-30",
    verified_work=verified_work,
    approved_segments=approved_segments,
    rate_policy=rate_policy,
)

# 기존 동적 단일 Excel; 초과근무 열은 금액이 있으면 생성
write_payroll_result_xlsx(result["payroll_register"],
                          "/secure/output/payroll-result.xlsx")
```

`verified_work` / `approved_segments`는 아직 JSON Tool CLI의 자동 입력 계약이 아니며 외부에서 **검증한 dict 목록**을 함수에 전달한다. 신뢰·권한·보관·기간·원본 버전을 증명하는 정식 Reader, 단계 인계 및 JSON CLI는 후속 구현이다.

## 후속

1. 실제 법정/사규/근로계약 기준 `rate_policy` 및 [P1-4 중복가산 정책](OVERTIME-STACKING.md) 확정: 분 환산 분모, 기본급에 포함된 통상임금 구성, 원 단위 절사·반올림, 대상 근로자 및 사업장별 규칙, 법정 중복가산.
2. 승인 사실과 검증 실제 근로구간의 **정본 Reader/외부 서명/권한** 연결, 스케줄·휴가 겹침과 휴일 분류의 근거 검증.
3. 미승인·부분승인·누락 근로가 없다는 외부 확인이 있어야만 추후 `earnings_complete`를 판정. 현재 값은 **무조건 False**.
4. P2 공제 및 세액·정산, P3 Tool CLI/Workflow/Gearbox는 별도 단계. `agent-config` 변경 PAUSE 유지.

테스트: `python3 -m unittest bhandara.tests.test_payroll_overtime_candidates_p1 -v` 및 전체 Bhandara/Gearbox 회귀.
