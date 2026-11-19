# Payroll P1-5b-2a — 계약 변경일별 승인 초과근무 수당 후보 연결

> **핵심 설계:** 이미 확정된 PTO·Worktime·Payroll Core 및 입력/출력 파일 규격은 변경하지 않는다. **신규 어댑터만 추가**해 P1-5a 일할 기본급, P1-5b-1 승인 근태 차감 후보, P1-2/3/4 검증된 초과근무수당 후보를 **같은 기존 PAYROLL 한 시트**에 표시한다. 지급/신고는 아직 승인하지 않는다.

## 왜 별도 어댑터가 필요한가?

기존 `overtime_candidates.calculate_overtime_candidates()`는 **직원당 선택된 단일 계약**의 일급 및 `reference_day_minutes_by_contract`를 사용한다. 그러나 11월 1~15일과 16~30일의 계약이 다르면 각각 **계약 단가를 달리 적용**해야 한다. 11월의 한 계약을 고정해서 모든 승인 분수에 곱하면 잘못된 수당 금액이 나온다.

신규 `contract_scoped_overtime.py`는 P1-5a `settlement_plan`에서 직원별 승인 계약 구간을 확인한 뒤, **검증근로 `verified_work`, 승인 구간 `approved_segments`를 계약 단위로 묶어** 기존 P1-2 순수 계산 함수를 변경 없이 재사용한다. P1-3 별도 출처 원장과의 필드·상태 일치 검사를 선행하고, P1-5b-1 승인 휴가/결근과 승인 추가근로 구간이 겹치면 차단한다.

승인근로구간·검증근로구간이 **계약 변경일을 가로지르면 임의로 분을 쪼개지 않는다.** 원본 증빙 발급/승인 경계에서 해당 날짜별 근거를 명시적으로 분리해 다시 제공해야 한다.

## 함수 및 정책 (별도 8번째 Excel 불필요)

```python
from bhandara.payroll.contract_scoped_overtime import build_contract_scoped_overtime_preview
from bhandara.payroll.output_excel import write_payroll_result_xlsx

rate_policy = {
    "multiplier_semantics": "TOTAL_RATE",
    "rounding_scope": "EMPLOYEE_RULE_PERIOD",
    "rounding_mode": "DOWN",
    "reference_day_minutes_by_contract": {
        "C-OLD": 480,
        "C-NEW": 480
    },
    "rule_labels": {"OT01": "연장근로수당"}
}
rollup_policy = {
    "mode": "ROUND_PER_CONTRACT_RULE_THEN_SUM",
    "policy_ref": "SYNTHETIC-ROUNDING-REFERENCE"
}
result = build_contract_scoped_overtime_preview(
    inputs, "/secure/worktime/worktime-result.xlsx",
    settlement_plan=settlement_plan,
    attendance_plan=attendance_plan,
    period_from="2026-11-01",
    period_to="2026-11-30",
    verified_work=verified_work,
    approved_segments=approved_segments,
    evidence_registry=evidence_registry,
    rate_policy=rate_policy,
    rollup_policy=rollup_policy,
)
write_payroll_result_xlsx(
    result["payroll_register"], "/secure/output/payroll-result.xlsx"
)
```

`rate_policy`는 P1-2 확정 API 그대로이고, 연장+야간 중복가산이 필요하면 기존 P1-4 `overlap_policy`를 그 객체에 넣는다. `evidence_registry`는 [P1-3 근거 원장 대조](EVIDENCE-RECONCILIATION.md)와 같은 구조다. `attendance_plan`은 [P1-5b-1 근태정산](ATTENDANCE-SETTLEMENT.md)에서 요구하는 Worktime 해시·계약 스냅샷·휴가/결근 근거를 반드시 갖춰야 한다.

### 원 단위 반올림 정책의 차이

- 기존 단일 계약: `EMPLOYEE_RULE_PERIOD` 단위로 원 단위 처리
- 새 계약분할 어댑터: **각 계약별로** 기존 단일 계약 함수를 호출해 `EMPLOYEE_RULE_PERIOD` 내역을 원 단위 처리한 뒤, **동일 직원·수당 ID끼리** 원 단위 합산
- 같은 직원이 월중 단가 변경된 경우 이 방식과 모든 계약의 소수점 금액을 합산하여 마지막 한 번 원 단위 처리하는 방식은 **최종 1원 이상 차이날 수 있다.**
- 이 차이를 묵시적으로 선택하지 않기 위해 `rollup_policy.mode=ROUND_PER_CONTRACT_RULE_THEN_SUM`을 반드시 제공하도록 했다. `policy_ref`는 실제 회사/계약의 승인된 정책에 연결해야 하는 **참조 문자열**로, 코드가 정책의 진위·법적 적정성을 인증하지는 않는다.

### 합성 예시

11월 14일 C-OLD의 일급 96,000원, 17일 C-NEW의 일급 192,000원, 각 기준 480분, 승인 추가근로 60분씩, 총 배율 1.5이며 해당 기본임금이 기본급에 **미포함**됐다고 외부에서 확인한 경우:

| 구간 | 후보액 |
|---|---:|
| C-OLD 승인 60분 | 18,000원 |
| C-NEW 승인 60분 | 36,000원 |
| 동일 `OT01` 수당 후보 합계 | **54,000원** |

급여대장에는 기존 `overtime_allowances:OT01` 단일 항목 열만 표시한다. **두 계약의 단가 변경 기록은 `overtime_candidate_review.contract_scopes`에서만** 확인할 수 있다. 연장·야간 분수를 단순 더해 독립 근로시간으로 취급하지 않는다.

## 안전 조건

- 임의 직원·계약에 확인되지 않은 검증근로/승인근로를 연결하지 않음
- 계약분할/재직 기간 밖의 근로 또는 승인구간, 계약 변경일을 가로지르는 구간은 계산 중단
- 검증근로와 승인구간이 다른 계약에 귀속되면 계산 중단
- P1-3 출처원장의 승인 취소·분류/기준급 포함 여부 불일치 차단
- Worktime 실제근로 분이 `null`이거나, 일별 확인된 근로구간의 합이 `actual_min`을 초과하면 기존 P1-2 함수에서 차단
- Worktime의 휴가·결근 승인구간과 제출된 승인 초과근로가 겹치면 차단
- `overtime_rules.xlsx`와 P1-2 일급·분모 정책을 그대로 사용. 승인된 가산 분류·원단위·중복가산 정책이 없으면 임의 규칙을 만들어 적용하지 않음
- 근거 자료가 없다는 이유로 초과근무가 `0`으로 확정되거나, 종전 기본급을 무단 상속하는 행동 금지

**중요 한계:** 이 구현은 입력된 모든 승인구간에 **올바른 계약 기준 단가를 연결**했는지를 확인하는 어댑터다. 외부 원장 자체의 진위·원장 누락·법정 휴일/통상임금 요율·고정수당의 근태 감액·복수 휴가 및 PTO Closing 원장 정합성은 인증하지 않는다. 따라서 `earnings_complete=False` / `deductions_complete=False`, `PARTIAL_REVIEW_ONLY`, `NOT_APPROVED` 유지. 지급합계·공제합계·실지급액은 공란.

## 다음 순서

P1-5b-2b에서 **복수 휴가 신청/상세구간과 PTO Closing 대조**, **고정수당의 근태 감액 조건**을 신규 어댑터로 정의한다. 신규 Worktime 10열은 변경하지 않고, 외부 휴가 상세원장의 원천을 연결하는 방향이다. 이후 P2 보험·세금/공제, P3 Payroll JSON Tool CLI 및 전체 E2E, Gearbox/Hermes 운영 전환/비교 검증, 마지막 레거시 삭제.

**확정 모듈 보호:** 신규 `contract_scoped_overtime.py`와 독립 테스트만 추가하고, 기존 `overtime_candidates.py`, `overtime_stacking.py`, `evidence_reconciliation.py`, `segmented_settlement.py`, `attendance_reconciliation.py`, PTO, Worktime, 출력 Writer 등은 수정하지 않는다.

테스트: `python3 -m unittest bhandara.tests.test_payroll_contract_scoped_overtime_p1 -v`.