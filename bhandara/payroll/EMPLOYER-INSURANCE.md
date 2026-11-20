# Payroll 보험 가입상태·산재보험 사업주 비용 분리

## 직원 공통정보가 보험 가입상태의 정본

\`common/employee.xlsx\`의 직원별 보험 취득현황이 **가입 여부의 정본**이다. Payroll의 7개 개별 XLSX에는 가입 상태를 중복 기재하지 않는다. 신규 보험상태 Reader는 두 직원시트(\`재직자\`, \`퇴사자\`)의 아래 열을 조회한다.

| 공통 열 | 의미 | 급여 영향 |
|---|---|---|
| \`national_pension_acquired_on\` | 국민연금 취득일 | 가입자에게만 국민연금 **근로자 부담** 후보 |
| \`health_insurance_acquired_on\` | 건강보험 취득일 | 가입자 건강보험·장기요양 **근로자 부담** 후보 |
| \`employment_insurance_acquired_on\` | 고용보험 취득일 | 가입자에게만 고용보험 **근로자 부담** 후보 |
| \`industrial_accident_acquired_on\` | 산재보험 취득일 | **사업주 부담** 후보, 근로자 공제 없음 |

각 열은 **\`YYYY-MM-DD\` 취득일 / 공란(적용 제외) / 문자 \`미가입\`** 중 하나다.

- **취득일**: 대상 기간 마지막 날짜까지 취득했다면 \`ENROLLED\` (단, 소급 취득, 중도 입사 보험료 적용, 실제 가입 자격·납부 월은 별도의 근거로 확정해야 한다).
- **공란**: \`EXCLUDED\` — 외부에서 적용 제외로 판단해 입력했으므로 **정상 미공제**, 누락 경고를 발생시키지 않는다. 고령이라는 이유만으로 Payroll이 자동 공란 처리하지 않는다.
- **\`미가입\`**: \`NOT_ENROLLED\` — 보험료를 임의 공제하지 않고, 국민연금·건강보험·고용보험은 **가입상태 확인 요청** 플래그를 표시한다. 산재보험은 근로자 공제 대상이 아니므로 해당 표시를 **직원 급여** 검토상태에 넣지 않는다.
- **기간 종료 이후 취득일**: 아직 가입 전(\`NOT_YET_ACQUIRED\`)으로 분류하고 해당 기간 보험료를 임의 부과하지 않는다.

**보험료 검증 플래그는 근로자 소득세·지방소득세와 3종 근로자 부담 보험(장기요양은 건강보험 연동)에 한정**한다. 지급되지 않는 수당이나 직원에게 적용되지 않는 기타 공제는 검토 요청이 아니다. 세액·보험료가 별도 승인된 경우에도 최종 지급 승인 상태(\`NOT_APPROVED\`)는 유지한다.

## 회사에만 기록하는 산재보험료

산재보험은 **원칙적으로 사업주 부담**이므로 \`deductions\` 목록에 넣지 않는다. 원 단위 처리 정책은 외부에서 지정하고, 산정기준액·요율의 진위는 확인 근거를 통해 관리한다.

\`\`\`json
{
  "schema_version": "0.1",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "policy_ref": "SYNTHETIC-INDUSTRIAL-POLICY",
  "rounding_mode": "DOWN",
  "assessments": [
    {
      "employee_id": "0001",
      "basis_won": 3000000,
      "approved_total_rate": "0.007",
      "assessment_ref": "SYNTHETIC-REMUNERATION-BASIS",
      "rate_ref": "SYNTHETIC-WORKPLACE-RATE",
      "approval_status": "APPROVED",
      "not_pre_included": true
    }
  ]
}
\`\`\`

**실제 요율이 아니라 합성 예시**다. \`approved_total_rate\`는 해당 사업장/사업종류와 적용기간에 대해 **외부에서 확인한 총 적용요율(필요한 출퇴근 재해 등 해당 항목 포함)**을 받아야 한다. 산재보험료 = \`basis_won × approved_total_rate\`를 명시된 원 단위 정책에 따라 계산한다. 월별 고지·개산/확정·환급 및 일반 직원 외의 특수 노무제공 형태는 이 모듈이 법적으로 판단하지 않는다.

위 예시의 산재보험료는 **21,000원**이며:

| 내부/대외 항목 | 금액 |
|---|---:|
| 직원 세전 지급합계 | 3,000,000원 |
| 산재보험료(사업주 부담) | 21,000원 |
| 회사 지출(현재 확인된 항목) | **3,021,000원** |
| 직원 산재보험 공제액 | **없음** |

**회사 지출(확인분)은 최종 회사 총인건비가 아니다.** 국민연금·건강보험·고용보험의 사업주 부담분이나 추가 퇴직급여 충당액 등은 여기서 계산하지 않는다. 추가 사업주 비용을 나중에 연결하기 전까지 \`employer_cost_complete=False\`로 남긴다.

## 기존 단일 Excel과 직원 안내 보호

별도 8번째 입력 Excel이나 다중 시트를 만들지 않는다. 관리자용 \`payroll-result.xlsx/PAYROLL\`의 기존 **지급합계·공제합계·실지급액**은 근로자 금액만 집계한다. 산재보험료가 산출된 직원만 동적 \`산재보험료(사업주)\` 열이 생성되며, 별도 \`회사 비용(확인분)\` 열은 회사 비용을 보여준다.

**관리자용 PAYROLL 파일을 직원에게 통째로 전달하면 안 된다.** 직원 안내를 만들 때는 \`build_employee_payroll_view(register, employee_id=...)\`가 해당 직원 한 행만 추출하고 회사 산재보험·회사 지출 열을 자동으로 제거한다. 이 함수는 직원별 자료의 **조회용 투영**이며 실제 전송이나 지급/승인을 수행하지 않는다.

### 통합 Flow

\`\`\`python
result = build_contract_scoped_overtime_preview(
    inputs, worktime_xlsx,
    settlement_plan=settlement_plan,
    attendance_plan=attendance_plan,
    period_from="2026-11-01", period_to="2026-11-30",
    verified_work=verified_work, approved_segments=approved_segments,
    evidence_registry=evidence_registry, rate_policy=rate_policy,
    rollup_policy=rollup_policy,
    employee_xlsx="/secure/input/common/employee.xlsx",
    insurance_assessment_plan=insurance_assessment_plan,
    withholding_plan=withholding_plan,
    industrial_assessment_plan=industrial_assessment_plan,
)
admin_register = result["payroll_register"]
company_audit = result["employer_cost_review"]
\`\`\`

- \`industrial_assessment_plan\` 없이 실행하면 기존 결과에는 회사 비용 열이 추가되지 않는다.
- 제공한다면 공통 \`employee.xlsx\`의 보험 취득상태가 필수다. 산재 취득일이 있는 직원은 산정기준액/요율을 빠짐없이 제공해야 한다. 공란/미가입 직원은 비용 0원이고 **산재보험료를 근로자에게 공제하지 않는다.**
- \`industrial_assessment_plan\` 제공 여부와 관계없이 세전 급여총액과 근로자 공제액은 변경하지 않는다. 임금승인·송금·신고/납부는 실행하지 않는다.

테스트: \`python3 -B -m unittest bhandara.tests.test_payroll_employer_industrial_insurance bhandara.tests.test_payroll_employer_cost_flow -v\` 및 \`bhandara/_tests/run.py\`.
