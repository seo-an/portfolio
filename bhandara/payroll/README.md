# Payroll Tool — 독립 계산 및 검토

**현재 계약:** 7개의 개별 단일시트 Excel과 검증된 Worktime Excel 및 별도 승인·정책 JSON을 읽어, 기존 계산 Flow를 **한 번** 실행하고 관리자 검토용 급여대장 `payroll-result.xlsx`와 `payroll-review.json`을 출력한다.

세부 JSON 설정은 [TOOL-CLI.md](TOOL-CLI.md), 입력 7종 시트·헤더는 [input-files.json](input-files.json), 출력은 [OUTPUT-CONTRACT.md](OUTPUT-CONTRACT.md)가 정본이다.

## 실행

```bash
mkdir -p bhandara/data/config
cp bhandara/payroll/config.example.json bhandara/data/config/payroll.json
# 기간·입력 7개·승인 JSON·Worktime 산출물의 실제 경로를 확인
python3 run.py bhandara payroll
```

명령의 기간이나 입력 경로를 임의 CLI 인수로 넘기지 않는다. 다른 Tool 결과를 인계하려면 [Bhandara Workflow](../WORKFLOW.md)를 사용한다.

## 입력 경계

- **필수 7개 Excel:** `pay-contract.xlsx`, `allowance-assignments.xlsx`, `fixed-allowance-map.xlsx`, `deduction-map.xlsx`, `overtime-rules.xlsx`, `bonus-budget.xlsx`, `bonus-allocation.xlsx`.
- **필수 Worktime:** `worktime-result.xlsx`의 `WORKTIME` 단일 시트 10열. 스케줄과 출입 차이는 단독으로 초과근무 지급 승인이라고 판단하지 않는다.
- **필수 외부 JSON:** `settlement_plan`, `attendance_plan`, `verified_work`, `approved_segments`, `evidence_registry`, `rate_policy`, `rollup_policy`. 검증된 실제 승인 원장, 정책을 사용자가 명시한다.
- **선택 PTO:** Usage Ledger + Deduction Quantity + `pto_claims` JSON이 한 세트. Closing은 외부 확정본을 제공한 경우에만 추가한다.
- **선택 보험/세금/사업주 비용:** `insurance_assessment_plan`, `withholding_plan`, `industrial_assessment_plan` 등 외부 확인 자료가 있을 때만 사용한다.

## 출력 경계

`PAYROLL`은 한 직원당 한 행을 사용한다. 한 사람이라도 0이 아닌 수당·성과급·공제 금액이 있으면 해당 항목 헤더를 만들고, 미해당자 셀은 공란으로 유지한다. 이미 계산된 값의 지급합계·공제합계·실지급 차액은 잠정 표시하며 **실제 지급 승인액이 아니다**. `NOT_APPROVED` 및 미검토 원장은 계속 남는다.

산재보험료 및 회사 비용(확인분)은 **사업주·관리자 전용**이다. 직원 지급총액/공제합계와 섞지 않으며 직원용 조회에 포함하지 않는다. 총인건비·회계 원가계산은 별도 Tool의 영역이다.

## 세부 계산·검토 계약

- [계약 기간·직원 ID](PERIOD-PREVIEW.md) · [지급 단위](CONTRACT-SCOPED-OVERTIME.md)
- [근태 정산](ATTENDANCE-SETTLEMENT.md) · [실근로 사실](WORKTIME-BRIDGE.md)
- [초과근무 후보](OVERTIME-CANDIDATES.md) · [중복 가산](OVERTIME-STACKING.md)
- [PTO 마감 전·확정 검토](PTO-CLOSING-REVIEW.md) · [휴가별 임금 조정](LEAVE-WAGE-ADJUSTMENTS.md)
- [원장 근거 대조](EVIDENCE-RECONCILIATION.md) · [보험 후보](INSURANCE-CANDIDATES.md)
- [원천징수 검토](TAX-WITHHOLDING.md) · [산재보험 사업주 비용](EMPLOYER-INSURANCE.md)
- [최신 운영 연결 계획](NEXT-STEPS.md)

실직원 급여자료와 승인 원장은 Git/일반 로그에 올리지 않는다. 신규 Hermes·Slack 운영 연결 및 무응답 점검은 아직 남아 있다. 테스트: `python3 -B bhandara/_tests/run.py`.
