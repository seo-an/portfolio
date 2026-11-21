# Paid Time Off — 독립 Module CLI 운영 계약

> 상태: **PTO 전용 진입점 구현 PR**, 서버 테스트 및 병합 전. 이 CLI를 Hermes 모델 도구와 Slack에 연결한 것은 아니다.

## 목표와 경계

`Module → Flow(논리적) → Tool → Workflow` 구분을 유지한다. PTO Module 하나만 요청하면 해당 Module의 기존 계산 Runner만 호출하고 다른 PTO Module, Worktime, Payroll 또는 Workflow를 실행하지 않는다. 기존 `bhandara paid-time-off` Tool CLI는 변경하지 않는다.

- 호출 가능: `entitlement`, `deduction-quantity`, `usage-ledger`, `closing`
- `use-promotion`: 여전히 미구현
- `expiry-carryover`: 사용 원장 내부 계산 함수로 남으며 별도의 Excel Module이 아니다.
- 미지원: Slack 첨부파일을 JSON 입력 역할로 자동 매핑, 미승인 자료의 근태·급여 확정, 누락된 선행 Module의 임의 실행
- 권한: 운영자가 준비한 **비공개 JSON 경로**만. Hermes가 연결될 때 모델 인자는 Module ID만 받아야 하며 파일 경로, 원본 ID를 받지 않는다.

## 실행

```bash
python3 run.py bhandara paid-time-off \
  --config /private/hr/config/pto-entitlement.json \
  --module entitlement
```

나머지도 `--module deduction-quantity`, `--module usage-ledger`, `--module closing`으로 지정한다. 사용하는 설정 JSON 형식은 기존 [TOOL-CLI.md](TOOL-CLI.md)와 같지만, **`steps`는 정확히 요청한 Module 하나만** 포함해야 한다.

예를 들어 승인된 휴가 신청에 대한 차감 수량만 계산하려면:

```json
{
  "schema_version": "1.0",
  "tool": "paid-time-off",
  "run_id": "auto",
  "as_of_date": "2026-11-30",
  "policy_id": "REVIEWED_POLICY",
  "input_root": "/private/hr/input",
  "output_root": "/private/hr/output",
  "steps": ["deduction-quantity"],
  "standard_daily_hours": 8,
  "files": {
    "approved_leave": "paid-time-off/approved-leave.xlsx"
  }
}
```

`usage-ledger` 단독 실행은 기존 Entitlement와 Deduction **결과 파일** 및 `grant_references`가 명시적으로 필요하다. `closing` 단독 실행은 `closing_id`, `usage_result`, 직원명부 및 필요한 이전 마감 근거가 필요하다. 누락된 경우 다른 Module을 자동 실행하지 않고 중단한다.

## 안전성·출력

- 각 Module의 기존 입력 검증·정책·날짜 조건과 Runner를 재사용한다. 숫자·산식·엑셀 서식은 변경하지 않는다.
- 입력 폴더와 출력 폴더가 같거나 포함 관계면 기존 CLI가 거부한다.
- 이미 존재하는 `run_id` 산출물을 덮어쓰지 않는다.
- 콘솔 실패에는 안정적인 오류 코드만 표시한다. 경로·직원 정보·원장 내용을 노출하지 않는다.
- 정상 출력 JSON의 `artifacts`는 운영자 로컬 CLI에서만 사용한다. 이후 Hermes에 연결하더라도 절대 경로를 사용자 Slack 메시지나 모델 응답에 전달하지 않는다.
- `review_only=true`, `approved=false`. 실행 결과는 지급·휴가 권리 승인이나 신고 확정이 아니다.

## 검증

```bash
cd /opt/agents/config/agent-config/.external/portfolio
sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B -m unittest \
  bhandara.tests.test_pto_single_module_cli -v

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B -m unittest \
  bhandara.tests.test_pto_json_tool_cli -v
```

서버 검증 후 브랜치 PR 병합, Bhandara 호환성 검사, 다음 **Agent-config 별도 브랜치**에서 모델용 `bhandara_run_module` 연결을 진행한다. Slack 네이티브 파일 영수증과 다중 첨부 바인딩은 별도 과제다.
