# Paid Time Off — JSON 설정 기반 선택적 Tool CLI

> **독립 Tool CLI 구현·검증 완료.** Payroll·Worktime과 서로 자동 호출되는 것은 아니다. 정확한 결과 경로·기간·사용량·마감 여부를 인계하는 **Workflow Stage 1은 아직 미구현**이다. 자세한 다음 작업과 운영/Slack 연결 승인 경계는 [운영 연결 인수인계](../OPERATIONS-HANDOFF-2026-11-20.md)를 따른다.

## 사용 방법

**명령어를 매번 수정하지 않습니다.** `config.example.json`을 사용자 전용 설정 파일 `bhandara/data/config/paid-time-off.json`으로 복사하고, **파일 안의 실행 기준일·경로·실행 단계**를 지정합니다. 실제 HR 원본·사용자 설정은 공개 Git에 커밋하지 않습니다.

```bash
mkdir -p bhandara/data/config
cp bhandara/paid-time-off/config.example.json bhandara/data/config/paid-time-off.json
# 이 JSON에서 input_root/output_root/기간/선택 단계를 지정
python3 run.py bhandara paid-time-off
```

다른 설정 파일을 지정하려면 `--config /private/.../paid-time-off.json`만 선택적으로 사용합니다. `--period`, `--input-dir`, `--output-dir`는 **신규 Tool에서 사용하지 않습니다**.

## JSON 입력 계약

```json
{
  "schema_version": "1.0",
  "tool": "paid-time-off",
  "run_id": "auto",
  "as_of_date": "2026-11-30",
  "policy_id": "REVIEWED_POLICY",
  "input_root": "/private/hr/input",
  "output_root": "/private/hr/output",
  "steps": ["entitlement", "deduction-quantity"],
  "basis": "입사일 기준",
  "standard_daily_hours": 8,
  "files": {
    "employee": "common/employee.xlsx",
    "attendance": "paid-time-off/attendance-result.xlsx",
    "approved_leave": "paid-time-off/approved-leave.xlsx"
  }
}
```

- `as_of_date`: PTO 발생·사용량 계산의 산정 기준일. **월(YYYY-MM)만으로 산정 시점을 추정하지 않습니다.**
- `run_id: "auto"`: 실행마다 서울시간 기반 새 ID를 사용해 기존 결과를 덮어쓰지 않습니다. 명시 ID 지정도 가능하며 기존 파일이 있으면 실패합니다.
- `input_root`, `output_root`: **JSON에서만 지정**. 상대 경로는 설정 JSON 위치 기준. `files` 안의 상대 경로는 `input_root` 기준.
- `steps`: 실행할 단계의 정확한 이름과 순서. 하나만 선택하면 독립 계산, 여러 개면 선택적 Flow. 명시하지 않은 단계는 실행하지 않습니다.
- `files`: 원본 파일 및 외부에서 만든 기존 결과 파일의 정확한 참조. 임의 검색이나 최신 파일 자동 선택을 하지 않습니다.

## 선택 단계 및 의존성

| 단계 | 수행 | 필수 입력·선행 조건 | 생성물 |
|---|---|---|---|
| entitlement | 확정 근태·직원 자료로 발생연차 산정 | `employee`, `attendance`; 정책 설정 | `entitlement-result.xlsx` |
| deduction-quantity | 승인 휴가 신청을 차감일수로 변환 | `approved_leave` | `deduction-quantity-result.xlsx` |
| usage-ledger | 발생, 차감, 외부 발생근거를 연결해 사용 원장 작성 | `grant_references` + 선택된 앞 단계 산출물 또는 `entitlement_result`, `deduction_result` | `usage-ledger-result.xlsx` |
| closing | 명시된 분기 마감 결과 집계 | `closing_id`, 직원명부, 앞 단계 산출물 또는 `usage_result` | `closing-result.xlsx` |

`usage-ledger`에는 기존 `run_usage_ledger`의 Allocation·Source Join이 포함됩니다. `closing_id`가 있으면 **Expiry/Carryover** 계산을 사용 원장 단계에서 호출하고, Closing은 이미 계산된 수량을 다시 산출하지 않습니다. `expiry-carryover` 계산 엔진 자체는 그대로 독립 함수로 유지되며, 이번 CLI에서 별도 파일 결과를 새로 만들어 중복하지 않습니다. `use-promotion`은 여전히 미구현입니다.

예를 들어 기존 Entitlement와 Deduction 결과를 받아 사용 원장만 계산한다면:

```json
{
  "schema_version": "1.0",
  "tool": "paid-time-off",
  "run_id": "auto",
  "as_of_date": "2026-11-30",
  "policy_id": "REVIEWED_POLICY",
  "input_root": "/private/hr/input",
  "output_root": "/private/hr/output",
  "steps": ["usage-ledger"],
  "files": {
    "entitlement_result": "/private/hr/output/previous/entitlement-result.xlsx",
    "deduction_result": "/private/hr/output/previous/deduction-quantity-result.xlsx",
    "grant_references": "paid-time-off/grant-references.xlsx"
  }
}
```

이 경우 `entitlement`, `deduction-quantity`를 다시 실행하지 않습니다. 파일의 기존 계약·기준일 불일치는 해당 Runner가 거부합니다. `carry_in`, `previous_closing`, `promotion`, `proration` 파일도 JSON에 선택적으로 넣습니다.

## 실행하지 않는 기능

- 근태 판정, 휴가 승인/취소 결정, 사용촉진 법적 판단, 자동 상계, 급여·수당 계산
- Gearbox/Slack 운영 실행, 원본 자동 수집, 다른 Tool 호출
- Gearbox/Hermes·Slack 운영 연결 및 실제 직원 원본 처리 (별도 사용자 승인 필요)

실행은 선택적 내부 Flow만 수행합니다. **새 `paid-time-off`는 기존 구형 계산기와 별개**입니다.

검증: `python3 -m unittest bhandara.tests.test_pto_json_tool_cli -v` 및 Gearbox 기능·인프라 회귀 테스트를 함께 실행합니다.
