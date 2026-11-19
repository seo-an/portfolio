# Payroll Output 계약 v0.1 — 동적 열을 가진 단일 급여대장

> 현재 구현은 **출력 전용**이다. 지급액·보험료·초과근무수당을 계산하거나 급여를 승인하지 않는다. 입력은 이미 계산·검토된 **금액 항목**이고, 결산·지급 준비를 의미하지 않는다.

## 결과

- 고정 파일명: `payroll-result.xlsx`
- 시트: **`PAYROLL` 하나**
- 헤더: 1행 **항목 그룹**, 2행 **항목명**. 그룹별 해당 열이 2개 이상이면 1행을 병합한다.
- 직원별 1행. 입력 직원 순서를 그대로 유지한다.
- 통상적인 고정 열: `employee_id`, `기본급`, `지급합계`, `공제합계`, `실지급액`, `검토상태`. 직원명이 하나라도 있으면 직원명 열도 생성.
- 열 그룹 순서: **직원정보 → 기본급 → 고정수당 → 초과근무수당 → 성과급 → 지급합계 → 공제 → 공제합계 → 실지급액 → 검토**.

## 변동 열 생성 규칙

1. 전체 직원의 각 지급·공제 항목을 `(group, item_id)`로 식별한다.
2. **한 명이라도 금액이 0이 아니면 열을 생성**한다. 50명 중 1명만 자격수당을 받으면 자격수당 열이 나타난다.
3. 전원 0원이거나 해당 항목 자체가 없으면 **그 열은 생성하지 않는다**.
4. 생성된 열에서 미해당자 또는 금액 0인 사람의 셀은 **공란**이다. 금액 0과 확인되지 않은 금액은 입력 단계에서 구분해야 한다.
5. 음수 소급정산액도 유효한 금액이므로 열을 만든다.
6. 같은 `item_id`의 다른 `level`은 **같은 열**에 합산 전의 개인별 확정 금액을 표시한다. `level`별 열을 따로 만들지 않는다.
7. 같은 그룹의 서로 다른 ID가 같은 표시명을 갖는다면 열 제목에 `[ID]`를 추가한다.
8. 열 순서는 그룹 안에서 `item_id` 문자순으로 고정한다. 월에 따라 실제 발생 항목이 달라지므로 열 수는 변경될 수 있다.

## 출력 모델

`build_payroll_register(rows)`는 직원 dict 행 리스트를 받는다.

```python
{
  "employee_id": "E001",
  "employee_name": "가상직원",    # 선택
  "base_pay": 3000000,
  "fixed_allowances": [
    {"item_id": "002", "label": "식대", "amount": 200000}
  ],
  "overtime_allowances": [
    {"item_id": "OT", "label": "연장근로수당", "amount": 45000}
  ],
  "performance_bonuses": [
    {"item_id": "B01", "label": "프로젝트 성과급", "amount": 300000}
  ],
  "deductions": [
    {"item_id": "NPS", "label": "국민연금", "amount": 150000}
  ],
  "earnings_complete": True,
  "deductions_complete": False
}
```

- 각 리스트에 항목이 없어도 `[]`이다. `earnings_complete`와 `deductions_complete`는 **반드시 명시적 참/거짓**이어야 한다.
- 금액은 원 단위 정수 또는 정수 Decimal 문자열만 허용한다. `None`은 금액 항목에 허용하지 않는다. 입력된 돈은 출력기가 추정하지 않는다.
- 같은 직원/그룹 내 중복 `item_id`는 차단한다. **원장 항목의 합산은 upstream 계산 모듈 책임**이다.
- 한 그룹 내 같은 `item_id`의 표시명 불일치도 차단한다.
- `gross_pay`: 지급항목 전체가 완료됐다고 명시된 직원만 계산한다.
- `deduction_total`: 공제 전체가 완료됐다고 명시된 직원만 계산한다.
- `net_pay`: 두 완료 플래그가 모두 참일 때만 계산한다. 그 외는 **공란**이다.
- 계산 결과가 모두 있어도 상태는 `REVIEW_REQUIRED`이다. 일부 미확정은 `PARTIAL_REVIEW_ONLY`. 결과 문서의 `approval_state`는 `NOT_APPROVED`로 고정된다.

```python
from bhandara.payroll.output import build_payroll_register
from bhandara.payroll.output_excel import write_payroll_result_xlsx

view = build_payroll_register(rows)
write_payroll_result_xlsx(view, "/path/to/empty-existing-directory/payroll-result.xlsx")
```

Writer는 파일 덮어쓰기를 거절하며 `PAYROLL` 시트만 생성한다. 기존 `payroll-calculator`의 급여 산식/계약/파일은 변경하지 않는다.

## 다음 구현 우선순위

출력기 자체의 설계·테스트·병합은 끝났다(PR #60). **다음 구현은 출력 열을 다시 설계하는 것이 아니라** [남은 Payroll 통합 과제](NEXT-STEPS.md)의 Excel Reader 및 코어→Output `item_id/label/amount` Adapter를 만드는 것이다. 초과근무수당·공제액 산정 및 정산 기간 구분이 완료될 때만 `earnings_complete`/`deductions_complete`를 확정한다.

## 후속 입력 연결 시 반드시 필요한 정보

현재 `bhandara/payroll/core.py`의 기본급·고정수당·성과급 계산 결과에는 **출력용 항목 표시명(label)을 일관되게 제공하는 계약이 없다**. 따라서 이번 PR은 외부에서 정규화한 `item_id`, `label`, `amount`를 입력받는 독립 출력기까지만 구현한다. 고정수당 ID→표시명, 성과급 ID→표시명, 초과근무 카테고리→표시명, 공제 항목별 확정 금액을 어떤 데이터에서 연결할지는 다음 입력/산정 연결 작업에서 정한다. 이 정보가 없이 이름을 임의 추측하지 않는다.

또한 `payroll` 독립 Tool CLI, Worktime 초과근무 정책 적용, 실제 4대보험 공제 산출, 연차·입퇴사 일할 산정, 법적 비과세 검증, 사용자 승인, Gearbox 운영연결은 **아직 미구현**이다. `agent-config` 수정은 PAUSE 중이다.

## 테스트

```bash
python3 -m unittest bhandara.tests.test_payroll_dynamic_output_v01 -v
```

그다음 전체 Bhandara unittest 및 Gearbox 호환성 검증을 수행한다.
