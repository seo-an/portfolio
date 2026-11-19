# Payroll P1-5b-2b-1 — PTO Closing·복수 사용신청 **읽기 전용 대조**

2026-11-20. **이번 단계는 지급/공제 금액 결정이 아닌 기존 PTO 산출물의 진위 미인증 내부 일치검사다.** 신규 Payroll의 7개 Excel, Worktime의 10열, 단일 PAYROLL Excel, PTO Tool의 파일 형식/계산 코어 모두 변경하지 않는다.

## 사용한 기존 정본

- `paid-time-off/deduction-quantity-result.xlsx`: `차감상세`의 `request_id, employee_id, leave_date, leave_type, 상태, _exact_numerator, _exact_denominator`. **정확한 분자/분모**로 사용 일수를 확인한다. 사람이 보는 `차감일수`는 무한소수 표시가 잘렸을 수 있으므로 합계 정본으로 사용하지 않는다.
- `paid-time-off/usage-ledger-result.xlsx`: `사용상세`에서 같은 신청의 `grant_id`별 배정·`차감일수` 표기·`처리구분`을 대조하고 `정책정보`의 마감 판정 ID/기준일/계산 완료 상태를 확인한다. `검토사항`이 있으면 차단한다.
- `paid-time-off/closing-result.xlsx`: `정책정보.확정여부=확정`, `참조 ID=Closing-Q.4-YYYY`, `마감 기준일`, `사용내역 SHA256`, `검토 필요 건수=0` 및 숨김 `_수량정본`의 직원별 **월간 정확 사용일수**를 확인한다. `마감보고`의 직원 목록 및 `마감상태`도 교차검증한다.
- `worktime-result.xlsx`: 기존 10열 중 직원·일자·예정분·휴가 신청 ID와 유형을 이용하여 하루 복수 PTO 신청의 **대표 참조 하나 이상**가 Worktime의 1개 신청 ID와 일치하는지 확인한다. 새로운 Worktime 열을 만들지 않는다.

## 기간의 안전 경계

Payroll 기간은 **정확히 한 달**이어야 하며, **확정된 Closing의 현재 분기 안에 해당 월이 있어야 한다.** 예를 들어 2026년 11월 급여에는 `Closing-4.4-2026`을 사용할 수 있다(분기말 12월 31일 마감·외부 확정 후). 반면 2026년 9월 자료를 Q4 마감과 직접 대조하는 행위는 차단한다. 이 자료가 있다 해도 11월 급여를 11월 말에 즉시 확정할 수 있다는 뜻은 아니다.

Q4 PTO Usage에는 이전 분기에서 인계된 수량이 포함될 수 있으므로, **요청별 상세와 월별 수량은 해당 Closing의 현재 분기 안의 월에 대해서만** 독립적으로 검증한다. 1~3분기 자료를 같은 Q4 파일에서 무리하게 재구성하지 않는다.

## 복수 신청 입력(별도 PTO 승인 상세 참조)

Worktime 10열에는 1명의 하루에 신청 ID 하나만 있다. 따라서 Payroll 내부에만 전달하는 `pto_claims` 목록에서 같은 날의 모든 PTO 신청을 각각 표현한다.

```json
[
  {
    "employee_id": "0001",
    "request_id": "LV-A",
    "leave_date": "2026-11-02",
    "pto_leave_type": "연차",
    "worktime_code": "ANNUAL_QUARTER",
    "start_at": "2026-11-02T09:00",
    "end_at": "2026-11-02T11:00",
    "approved_minutes": 120,
    "minutes_per_pto_day": 480
  },
  {
    "employee_id": "0001",
    "request_id": "LV-B",
    "leave_date": "2026-11-02",
    "pto_leave_type": "연차",
    "worktime_code": "ANNUAL_HALF",
    "start_at": "2026-11-02T13:00",
    "end_at": "2026-11-02T17:00",
    "approved_minutes": 240,
    "minutes_per_pto_day": 480
  }
]
```

위의 분모 480분은 **예시 외부 정책값**이다. PTO Deduction Quantity가 적용한 직원별 1일 기준시간과 맞아야 하며 Payroll이 Worktime의 출퇴근차이나 `scheduled_min`에서 분모를 추측하지 않는다.

사용 상세가 동일 요청을 여러 grant ID로 나눠 배정한 경우에도 **동일 신청/날짜/휴가종류의 합**으로 대조한다. 단, 사용상세의 수치는 사람용 최대 7자리 소수 절사이므로 각 배정행마다 허용 오차 **1/10,000,000일** 이내에서만 표시 정합성을 비교한다. **정확 수량 검사는 `deduction-quantity-result.xlsx`의 분자·분모와 Closing의 숨김 정본 간에 진행**한다.

한 날짜의 복수 PTO 시작/종료 시간은 서로 겹치면 안 되며, 사용분 합계는 해당 Worktime의 `scheduled_min`을 넘을 수 없다. 그날 Worktime의 단일 `leave_request_id`/`leave_type`은 `pto_claims` 중 **적어도 한 신청과 정확히 일치**해야 한다. 다른 휴가유형/직원, 승인 누락/취소 요청, 날짜·ID·수량 불일치는 계산을 차단한다.

## Flow 연결

```python
from bhandara.payroll.contract_scoped_overtime import build_contract_scoped_overtime_preview

result = build_contract_scoped_overtime_preview(
    inputs, "/secure/worktime/worktime-result.xlsx",
    settlement_plan=settlement_plan,
    attendance_plan=attendance_plan,
    period_from="2026-11-01", period_to="2026-11-30",
    verified_work=verified_work,
    approved_segments=approved_segments,
    evidence_registry=evidence_registry,
    rate_policy=rate_policy,
    rollup_policy=rollup_policy,
    pto_sources={
        "usage_file": "/secure/pto/usage-ledger-result.xlsx",
        "closing_file": "/secure/pto/closing-result.xlsx",
        "deduction_file": "/secure/pto/deduction-quantity-result.xlsx",
        "pto_claims": pto_claims
    }
)
pto_review = result["pto_closing_review"]
```

`pto_sources`는 **선택적**이다. 전달하지 않으면 기존 P1-5b-2a 공개 Flow 결과가 그대로 유지된다. 전달하면 기존 Flow가 **한 번 파싱한 Worktime**을 PTO 검토에도 공유한다. 세 PTO 파일은 읽기만 하며 변경·복사·새 원장 생성 없음. `pto_closing_review`에는 직원별 월간 사용수량과 신청별 정확 수량·파일 해시가 기록된다.

### 이번에 의도적으로 하지 않은 것

- Closing이 확정되었다는 사실만으로 **연차·대휴의 유급/무급 여부, 사용촉진 면책, 미사용연차수당 지급, 휴가 관련 고정수당 차감** 등을 계산하지 않는다.
- Worktime 일별 1개 신청 ID를 Payroll P1-5b-1이 하나의 승인 휴가 사건으로 처리하는 기존 계약은 변경하지 않는다. **복수 PTO 신청의 대조 성공이 모든 신청의 지급·감액 처리를 완료했다는 의미는 아니다.** 기존 Payroll의 근태 사건은 기존 단일 사건으로 처리하고, 추가 신청은 PTO 검토 증빙으로만 남긴다.
- `Closing-4.4-2026`이 **12월 31일 이후에 확정**되어야 11월 건을 교차검증할 수 있다. 사용 시점에 마감이 없다면 이번 자료로 통과할 수 없다. 장차 실무 월별 처리에는 **확정된 사용신청+Deduction Quantity를 기준으로 하는 잠정 검토 경로**를 별도로 구분해야 한다.
- PTO 사용량/Closing은 **현금 급여의 과세·공제/정산 정본이 아니다**. 회사 규칙 및 외부 지급 결정·상세원장 진위·실제 서명 권한은 독립 검증 대상이다.
- 신규 Flow는 \`PARTIAL_REVIEW_ONLY\`, \`NOT_APPROVED\`, \`earnings_complete=False\`, \`deductions_complete=False\` 및 **지급합계·공제합계·실지급액 공란**을 유지한다.

**다음 P1-5b-2b-2:** 복수 PTO 승인별 **급여지급 처리(유급/무급)**, 기본급과 고정수당의 중복감액 금지, 사규별 고정수당 감액 정책을 결합한다. 이후 P2 보험·세금, P3 JSON CLI/전체 E2E, Gearbox 운영 전환, 마지막 레거시 3종 철수. `agent-config` 변경 PAUSE.

테스트: `python3 -m unittest bhandara.tests.test_payroll_pto_closing_review_p1 -v`. 기존 결합 Flow와 Bhandara 전체 `unittest`, Gearbox 기능/인프라 회귀 필수.
