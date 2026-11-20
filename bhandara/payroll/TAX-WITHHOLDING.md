# Payroll P2-2 — 지급항목별 과세·비과세 검토 + 근로/지방소득세 공제 후보

> **확정된 7개 독립 Payroll XLSX, Worktime 10열, PTO 결과 형식, 단일 PAYROLL 급여대장**을 그대로 사용한다. 기존 급여 계산과 휴가·초과근무 후보를 모두 조합한 다음 **외부 확인 과세구분 및 원천징수액**을 대조한다. 이 모듈은 **간이세액표·세법상 비과세 한도·근로소득세 계산식을 구현하지 않는다.** 신고·송금·급여승인은 불가능하다.

## 왜 원천세를 자동 산출하지 않는가?

과세·비과세는 사규, 실지급 형태 및 법정 요건·한도에 따라 달라질 수 있다. 단순히 `FIXED ALLOWANCE MAP.payroll_taxability=NON_TAXABLE`이라고 표시됐다고 해당 수당 **전액 비과세**가 되는 것은 아니다. 초과근무·성과급과 기본급에 대해 실제 지급 후보를 반영한 뒤 세무담당자가 확인한 **항목별 과세/비과세 금액을 전액 대조**해야 한다.

그다음 근로소득세·지방소득세는 외부 급여/세무 시스템이 확인·승인한 원 단위 금액을 그대로 받는다. 부양가족·간이세액표·감면세액·원천징수비율·지급시점별 세법 변화 등을 코드가 임의 추측하지 않는다.

## 입력 — 기존 Excel 7개 유지, 선택적인 메모리/향후 JSON 객체

```json
{
  "schema_version": "0.1",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "policy_ref": "SYNTHETIC-WITHHOLDING-POLICY",
  "source_snapshot_ref": "SYNTHETIC-PAYROLL-TAX-SNAPSHOT",
  "employees": [
    {
      "employee_id": "0001",
      "classifications": [
        {
          "source": "base_pay",
          "item_id": "BASE",
          "taxable_won": 3000000,
          "non_taxable_won": 0,
          "classification_ref": "SYNTHETIC-BASE-CLASS"
        },
        {
          "source": "fixed_allowances",
          "item_id": "001",
          "taxable_won": 80000,
          "non_taxable_won": 20000,
          "classification_ref": "SYNTHETIC-FIXED-CLASS"
        }
      ],
      "income_tax_won": 50000,
      "local_income_tax_won": 5000,
      "withholding_ref": "SYNTHETIC-TAX-SYSTEM",
      "approval_status": "APPROVED",
      "not_pre_deducted": true
    }
  ]
}
```

**합성 예시로만 사용.** 위 고정수당은 `allowance_id=001`이 실제로 비과세 적용 가능한 식대 등이라는 뜻이 아니다. 해당 직원의 고정수당 매핑이 `NON_TAXABLE` 또는 `REVIEW`라면 외부 검증 근거가 있는 **일부 또는 전부 비과세 분할 후보**를 사용할 수 있지만, `TAXABLE`이면 비과세 금액을 허용하지 않는다. 비과세 금액이 있다면 해당 `taxability_policy_ref`가 반드시 있어야 한다. 코드가 정책 참조 문자열 자체의 진위를 인증하지는 않는다.

`classifications`는 직원별 실제 **모든** 지급 후보를 빠짐없이 포함해야 한다.

- 기본급: `source="base_pay", item_id="BASE"` 1건
- 고정수당: `source="fixed_allowances", item_id="<allowance_id>"`
- 추가근무/야간·휴일 등: `source="overtime_allowances", item_id="<rule_id>"`
- 성과급: `source="performance_bonuses", item_id="<bonus_id>"`

각 항목별 `taxable_won+non_taxable_won=최종 지급 후보액`이어야 한다. **중도 계약 변경·유급/무급휴가·고정수당 감액·초과근무 합산 이후의 최신 금액**을 비교하므로 예전 계약금액에 대한 과세표를 재활용할 수 없다. 금액이 양수인 임의 추가 항목이나 직원 모집단이 누락되면 거절한다.

## Flow 결합

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
    insurance_assessment_plan=insurance_assessment_plan,
    withholding_plan=withholding_plan
)
# result["tax_withholding_review"]:
#   항목별 과세/비과세 금액, 과세/비과세 합계,
#   외부확인 근로소득세·지방소득세 후보 및 근거
# result["payroll_register"]:
#   기존 deductions:TAX_INCOME / TAX_LOCAL_INCOME 동적 공제 열
```

`withholding_plan` 미제출이면 기존 Flow·Output은 변하지 않는다. 제출한 경우 실지급 기준 금액을 검토하고, **기존 보험료 후보와 함께** `deductions` 항목 리스트에 공제 후보를 넣어 **최종 급여대장 1회** 렌더링한다. 중복 공제 ID·승인되지 않은 직원/근거·보험과 세금 차감의 중복 처리는 차단한다. 50명 중 1명만 세액이 있다면 세금 항목 열은 2개가 생기고 나머지 49명은 공란으로 출력한다.

## 미완료 게이트

이 단계는 **금액 후보를 더한 것**이지 세법상 정산이 완료됐다는 뜻이 아니다. `tax_withholding_review.statutory_tax_tables=NOT_COMPUTED`, `source_authenticity=NOT_AUTHENTICATED_BY_THIS_MODULE`이며, 기존 `earnings_complete=False`, `deductions_complete=False`, `approval_state=NOT_APPROVED`, `PARTIAL_REVIEW_ONLY`를 그대로 유지한다. **지급합계·공제합계·실지급액은 공란**이다.

향후 과세/비과세 판정의 실제 정책 근거 인증, 주민세/지방소득세 신고 정합성, 보험료 정산·기타 공제, 수당/세금 전체 모집단 완전성 및 최종 검수·승인 게이트를 구현해야 한다. P3 독립 JSON Tool CLI/합성 E2E·Gearbox 운영 연결 및 레거시 철수도 아직 미완료다. 사용자의 요청이 없다면 `agent-config`는 수정하지 않는다.

테스트: `python3 -m unittest bhandara.tests.test_payroll_tax_withholding_p2 -v`. 기존 Bhandara 전체 `unittest` 및 Gearbox 기능/인프라 회귀 필수.
