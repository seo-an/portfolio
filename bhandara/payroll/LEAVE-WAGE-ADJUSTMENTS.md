# Payroll P1-5b-2b-2 — 복수 PTO 휴가 지급결정·고정수당 감액 후보

> 이번 단계는 **급여 후보의 정확한 결합**만 한다. 기존 PTO 발생·차감·Closing 계산을 재작성하지 않고, Worktime 10열·Payroll 7종 입력 Excel 및 단일 PAYROLL XLSX를 유지한다. 이 경로에 제출되는 PTO Closing은 해당 분기 말 이후 **외부 확정된 자료**여야 한다. 당월 미마감 급여 정산 경로는 아직 미구현이다.

## 외부 승인 근거가 필요한 이유

PTO의 사용일수(예: `1/4`일)는 급여에서 얼마를 차감해야 하는지 결정하지 않는다. 유급 연차·대휴의 실제 급여 포함 여부, 무급휴가의 차감 기준, 특정 수당의 출근조건은 각각 **회사 정책과 외부 승인 임금결정**의 문제다. 이번 계산기는 금액을 자동 도출하지 않고, 승인된 원 단위 금액과 참조 ID가 있을 때만 기존 급여대장의 **기본급 후보·고정수당 후보**를 조정한다.

외부에서 한 달 전체 지급액이 이미 감소된 계약금액을 넣었다면 다시 감액하지 않는다. `base_not_pre_adjusted=true`와 `fixed_not_pre_adjusted=true`는 **기존 기본급/수당에 해당 금액이 사전 차감되지 않았음**을 외부가 증빙한 경우에만 승인할 수 있는 선언이다. 실제 승인자의 신원·권한/서명은 아직 코드가 인증하지 않는다.

## 마감 전에도 동일한 임금결정 경로 사용

[마감 전/확정 PTO 대조](PTO-CLOSING-REVIEW.md)에 따라 `pto_sources["closing_file"]=None`이면 `pto_closing_review["closing_status"]`가 **`마감 전`**이 된다. 이때도 각 PTO 요청의 정확 수량과 신청/승인 증빙은 같은 검증을 수행하며, `pto_wage_plan`의 임금결정·기본급/고정수당 **중복차감 방지**도 같은 함수를 사용한다.

다만 이 경우 `pto_wage_plan["pto_closing_id"]`는 기존 정식 Closing ID가 아니라 `pto_closing_review["closing_id"]`의 **`PRE_CLOSING:<as_of_date>:<Usage SHA256>`** 값을 받아야 한다. 원본 Usage가 바뀌면 이전 승인금액 자료를 자동 재사용할 수 없다. 결과의 `closing_status="마감 전"` 및 `change_possible=True`는 지급액 확정이 아니라 **월말에 변동할 수 있는 잠정 검토**를 뜻한다.

## 입력 계약

신규 필수 Excel을 추가하지 않는다. [기존 PTO 검증 경로](PTO-CLOSING-REVIEW.md)의 `pto_sources`와 함께 다음 **선택적 in-memory `pto_wage_plan`**을 전달한다.

```json
{
  "schema_version": "0.1",
  "pto_closing_id": "Closing-4.4-2026",
  "policy_ref": "SYNTHETIC-LEAVE-WAGE-POLICY",
  "decisions": [
    {
      "employee_id": "0001",
      "request_id": "R1",
      "leave_date": "2026-11-02",
      "pto_leave_type": "연차",
      "treatment": "PAID_LEAVE",
      "base_reduction_won": 0,
      "fixed_reductions": [],
      "approval_status": "APPROVED",
      "approval_ref": "SYNTHETIC-PAYROLL-R1",
      "evidence_ref": "SYNTHETIC-LEDGER-R1",
      "base_not_pre_adjusted": true,
      "fixed_not_pre_adjusted": true
    },
    {
      "employee_id": "0001",
      "request_id": "R2",
      "leave_date": "2026-11-02",
      "pto_leave_type": "연차",
      "treatment": "UNPAID_LEAVE",
      "base_reduction_won": 60000,
      "fixed_reductions": [
        {
          "allowance_id": "001",
          "amount_won": 15000,
          "policy_ref": "SYNTHETIC-ALLOWANCE-ABSENCE-POLICY"
        }
      ],
      "approval_status": "APPROVED",
      "approval_ref": "SYNTHETIC-PAYROLL-R2",
      "evidence_ref": "SYNTHETIC-LEDGER-R2",
      "base_not_pre_adjusted": true,
      "fixed_not_pre_adjusted": true
    }
  ]
}
```

위 값은 **임의로 정한 합성 예시**이며 실제 연차가 무급이라는 판단이나 법정 공제액 예시가 아니다. 모든 PTO 승인 신청에 대해 정확히 **한 개의 지급결정**이 있어야 한다. 제출하지 않은 신청·중복·실제 PTO 명세에 없는 신청은 거절한다. 유급휴가라면 기본급 차감 후보는 반드시 0원이고 이 경로에서는 고정수당 감액도 허용하지 않는다. 유급휴가의 특정 성과수당 삭감 등 별도 합법적 근거가 필요한 사항은 이 계약이 자동 처리하지 않는다.

## 중복차감·고정수당 보호

- P1-5b-1에서 대표 Worktime 휴가 신청 ID로 이미 기본급을 차감한 경우 그 신청의 `treatment`, 외부 차감액과 신규 PTO 지급결정이 **정확히 일치**해야 하고 **다시 차감하지 않는다**. 다르면 거부한다.
- 같은 날 두 번째·세 번째 PTO 신청의 기본급 감액은 **외부에서 명시적으로 승인된 액수만** 더한다. Worktime 한 날짜 1개 휴가 ID를 변경하지 않는다.
- 고정수당은 기존 P1-5a의 직원별 수당 ID·Level 배정을 통해 이미 만들어진 **실제 수당 후보액**에서만 감액한다. 수당이 없는 직원, ID가 잘못된 수당, 음수 급여가 되는 감액은 모두 차단한다. 같은 수당에 여러 신청의 감액이 있으면 합산 검증하고 **한 번만 반영**한다.
- 실제 다른 Payroll 감액 흐름에서 같은 수당을 이미 감액했다는 사실은 `fixed_not_pre_adjusted`가 외부에서 확인돼야 한다. 현재 신규 Flow는 **P1-5b-1에서 고정수당을 감액하지 않았으므로** 이 경로에서만 고정수당 후보 조정을 수행한다.
- [PTO Closing 상세](PTO-CLOSING-REVIEW.md)에서 검증된 모든 `pto_claims`의 시작·종료 시간과 승인 초과근무 구간도 **전체 비교**한다. Worktime의 대표 휴가 신청만 비교해서 다른 신청의 시간 중첩을 놓치지 않도록 한다.

## 단일 Flow 결합

```python
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
    pto_sources=pto_sources,
    pto_wage_plan=pto_wage_plan,
)
# result["pto_closing_review"]: 수량·기간·원장 대조
# result["pto_wage_review"]: 신청별 지급결정과 기본급·고정수당 감액 근거
# result["payroll_register"]: 기존 단일 PAYROLL 출력용 후보 대장
```

`pto_wage_plan`이 없으면 기존 Flow의 금액·검토 상태에 변경이 없다. 제공됐는데 `pto_sources`가 없으면 중단한다. 외부 승인된 감액 결과는 **직원별 항목 목록에 반영한 뒤** 기존 `build_payroll_register()`를 한 번만 호출한다.

**예시:** 기본급 3,000,000원, 고정수당(001) 100,000원, 같은 날 유급 2시간 + 별도 무급 4시간(기본급 차감 60,000원·수당 차감 15,000원)이 **독립적으로 승인됐다면**, 기본급 후보 **2,940,000원**, 수당 후보 **85,000원**. 단, 지급합계·공제합계·실지급액은 계속 공란, `PARTIAL_REVIEW_ONLY`, `NOT_APPROVED`, `earnings_complete=False`다.

## 여전히 남은 일

법적 통상임금/수당별 휴가 감액 가능성 및 정책의 실제 승인권한 확인, 복수 PTO 신청 이외의 휴가·결근·출퇴근 오류 처리, 당월 **PTO Closing 이전**의 잠정 자료 검증, 미사용 연차수당의 청구권 판단, 휴일 판정, 보험·세금/공제 및 실지급액은 다음 단계. 운영 권한/서명·S3 보관 및 Gearbox 연결도 아직 안 했다.

**다음:** P1 근거 신뢰성·당월 미마감 경로 정리 → P2 보험·원천세·공제 → P3 독립 Tool CLI·합성 E2E 및 레거시 전환/삭제. 이번 PR은 \`agent-config\` 및 PTO/Worktime 계산 코드를 건드리지 않는다.

테스트: `python3 -m unittest bhandara.tests.test_payroll_leave_wage_adjustments_p1 -v`, 전체 Bhandara 및 Gearbox 기능/인프라 회귀.
