# Payroll P2-1 — 4대보험 **근로자 부담 후보** 계산

> 기존 **7개 독립 단일시트 Excel**, Worktime 10열, PTO 결과, Payroll **한 시트 동적 급여대장**은 변경하지 않는다. 이미 있는 `deduction-map.xlsx`의 4개 근로자 부담률을 재사용하되, 보험별 **외부 검증 산정기준액**만 별도 메모리/향후 JSON 설정으로 받는다. 실제 보험 신고·납부·원천세·최종 급여 확정 기능은 아니다.

## 입력 자료와 정확한 경계

- `DEDUCTION MAP`: `deduction_code`로 계약을 연결. `national_pension, health_insurance, longterm_care, employment_insurance`는 **근로자 부담 비율(0~1)**, `effective_from/to`는 승인 요율 적용기간, `source_ref`는 외부 정책 참조다.
- `CONTRACTS`: 기존 `deduction_code`를 그대로 사용. 월중 계약이 변경되어도 **전체 기간에 같은 코드**라면 계산 가능. 코드가 변경되면 지금은 임의로 기간 평균을 내지 않고 **정산 정책 미확정 오류**로 차단한다.
- `assessment_plan`: **별도 8번째 Excel이 아닌 선택적 객체**. 직원마다 **국민연금 기준소득월액**, **건강보험 보수월액**, **고용보험 대상 보수**의 세 기준액을 각각 입력하고, 4종 보험 적용 여부를 명시한다. 장기요양은 **계산된 건강보험료**를 기준으로 한다. 해당 기준액에 적용되는 법정 상한/하한, 보험별 가입·자격, 휴직/입퇴사 등은 **반드시 외부에서 판단해 반영**해야 한다.
- `rounding_mode`은 `DOWN` 또는 `HALF_UP`의 **원 단위 후보 처리**만 지원한다. 이는 *외부가 명시한 정산 정책*일 뿐, 실제 법정 반올림 정책을 소프트웨어가 인증하거나 자동 선택하는 것이 아니다.

### 합성 입력 예시

```json
{
  "schema_version": "0.1",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "policy_ref": "SYNTHETIC-INSURANCE-ROUNDING",
  "rounding_mode": "DOWN",
  "longterm_care_base_mode": "ROUNDED_HEALTH_PREMIUM",
  "assessments": [
    {
      "employee_id": "0001",
      "national_pension_basis_won": 3000000,
      "health_insurance_basis_won": 2000000,
      "employment_insurance_basis_won": 1200000,
      "national_pension_applicable": true,
      "health_insurance_applicable": true,
      "longterm_care_applicable": true,
      "employment_insurance_applicable": true,
      "assessment_ref": "SYNTHETIC-ASSESSMENT-0001",
      "applicability_ref": "SYNTHETIC-ELIGIBILITY-0001",
      "approval_status": "APPROVED",
      "not_pre_deducted": true
    }
  ]
}
```

예시에서 사용한 수치는 **실제 한국 보험 요율·법정 산정기준액을 보증하지 않는 합성 값**이다. 유효한 `deduction-map.xlsx`의 4개 비율과 승인 적용기간을 읽은 뒤 아래 순서로 계산한다.

```text
국민연금 후보 = 근로자 기준소득월액 × 국민연금 부담률 → 원 단위
건강보험 후보 = 건강보험 보수월액 × 건강보험 부담률 → 원 단위
장기요양 후보 = 원 단위 건강보험 후보 × 장기요양 부담률 → 원 단위
고용보험 후보 = 고용보험 대상 보수 × 고용보험 부담률 → 원 단위
```

*이 조합은 `ROUNDED_HEALTH_PREMIUM`이라는 명시적 외부 정책이다.* 법령/고지서에서 다른 기준이 필요하면 설정 없이 자동으로 다른 산식을 적용하지 않는다. 일부 보험 적용 제외 직원은 해당 `*_applicable=false`를 **근거 참조와 함께 명시**해야 하며 0원으로 계산한다. 지급액이 0원이라는 이유로 자동 비가입 판정하지 않는다. **건강보험 미적용인데 장기요양만 적용**하도록 제출한 자료는 차단한다.

## Payroll 단일 Flow 연결

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
    insurance_assessment_plan=assessment_plan,
)

# result["insurance_review"]: 보험별 기준액·요율·금액 후보 및 정책근거
# result["payroll_register"]: 기존 PAYROLL 단일 시트 Writer 입력
```

`insurance_assessment_plan`이 없는 경우 **기존 Payroll 결과는 변하지 않는다.** 전달하면 기존 계약·기간 검증 뒤 보험별 근로자 부담 후보를 계산해 **기존 `deductions` 동적 열**에 추가한다. 중간 급여대장을 만들지 않으며 `build_payroll_register()`는 마지막에 한 번만 호출한다.

검증한 사항: 직원 전체 모집단의 정확한 기준액/적용 여부 제공, 승인/산정 근거 문자열, 동일 직원·보험 ID 중복 차단, 계약별 공제코드·요율 적용기간, 음수/소수/누락 기준금액, 요율 재사용, 장기요양 건강보험료 참조, 감면 직원 0원 표시 생략. **50명 중 1명만 부담할 경우 4개 공제 열은 해당 직원 행에만 금액이 들어간다.**

## 완료/미완료 구분

보험료 **후보금액**이 존재해도 `deductions_complete=False`, `earnings_complete=False`, `approval_state=NOT_APPROVED` 유지. **지급합계·공제합계·실지급액은 기존대로 공란**이다. 근로소득세·지방소득세, 그 외 사규 공제, 종전 보험료 정산/환급, 지급 시 과세/비과세 확정, 회사별 실제 신고내역/대상자 자격 검증은 **다음 P2 구현 과제**다.

법적 합산·반올림, 통상임금/세법 적용, 가입 자격/감면·면제 여부는 입력으로 온 정책·산정근거가 실제로 적법한지 검증 후 운영해야 한다. 이 모듈은 `source_ref`·`assessment_ref`·`applicability_ref`를 단순 문자열로 읽을 뿐, 원본 발행권한/진위를 인증하지 않는다.

**테스트:** `python3 -m unittest bhandara.tests.test_payroll_insurance_candidates_p2 -v`, Bhandara 전체 및 Gearbox 기능·인프라 회귀. `agent-config` PAUSE, 서버 브랜치 정리/레거시 철수 보류.
