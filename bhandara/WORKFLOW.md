# Bhandara Stage 1 — Tool 간 Payroll Workflow

> **상태: Portfolio PR #80 사용자 서버 테스트 및 병합 완료.** 별도 계산 모듈/DB/서버를 만들지 않고 기존 독립 Tool의 호출·파일 인계만 연결한다. 운영 Slack/Gearbox 배포는 이 작업 범위가 아니다.

## 목적과 원칙

- `paid-time-off`와 `worktime`은 독립 Tool이다. 두 결과가 모두 필요하면 PTO → Worktime → Payroll 순서로 실행하며, PTO를 쓰지 않으면 Worktime → Payroll만 실행한다.
- 각 선행 Tool은 **한 번 실행(run)** 또는 **이미 생성한 결과 재사용(reuse)** 중 하나만 선택한다. 최근 파일 자동 검색, 묵시적 파일명 대체, 중복 계산은 없다.
- Payroll은 기존 `payroll.tool_cli.execute()` **딱 한 번만** 호출한다. 7개 원본 XLSX, 10열 WORKTIME, PAYROLL 단일 시트 및 기존 승인/검토 산식은 변경하지 않는다.
- PTO 사용 검토 시 **Usage Ledger + Deduction Quantity + 외부 pto_claims JSON**을 함께 제공한다. Closing은 외부에서 실제 확정한 파일을 **reuse**할 때만 연결한다. 새 PTO Tool의 Closing 출력은 기본적으로 **미확정**이라 직접 연결할 수 없다.
- Worktime 10열은 근태 **사실 자료**다. `verified_work`, `approved_segments`, `evidence_registry`, `rate_policy` 등 승인/증빙 JSON을 자동 생성하거나 추정하지 않는다.
- 재사용 파일은 완전한 경로, 부모 실행 폴더 이름(`run_id`), 대상 급여월의 시작/종료일, SHA-256이 일치해야 한다. Worktime의 직원·일자 및 PTO의 승인·수량 정합성은 **기존 Payroll 검증 Flow**에서도 재확인한다.
- 명시적 `run_id`에 결과 폴더가 있으면 중단한다. 원본이나 기존 결과를 삭제·덮어쓰지 않는다. 앞선 Tool만 성공하고 Payroll이 실패할 수 있으므로 **중간 결과는 남을 수 있으나 전체 성공으로 보고하지 않는다**.

## 단일 명령

```bash
mkdir -p bhandara/data/config
cp bhandara/workflow.example.json bhandara/data/config/workflow.json
# 파일 안의 각 Tool 설정 경로와 payroll_period를 한 번 지정
python3 run.py bhandara workflow

# 별도 설정 위치 사용 시
python3 run.py bhandara workflow --config /private/hr/workflow.json
```

개인 JSON은 원본 경로가 기준이다. Workflow가 Payroll에 넘길 **경로만 담은 임시 JSON**을 만들었다가 실행 종료 후 삭제한다. 승인 원장 데이터, XLSX 내용, 직원 목록을 복사하지 않는다. Workflow 자체의 새 영구 상태파일·DB도 없다.

## 설정 계약

`workflow.example.json`에는 PTO가 필요 없는 기본 예시가 있다. 각 Tool의 설정 `tool/schema_version=.../1.0`은 기존 정본을 재사용한다.

- 최상위 필수: `schema_version: "1.0"`, `workflow: "payroll"`, `payroll_period: "YYYY-MM"`, `run_id: "auto"|명시 ID`, `tools`.
- `tools.payroll.config`: 기존 Payroll 개인 JSON 위치. 필수.
- `tools.worktime`: `{"action":"run","config":"worktime.json"}` 또는 `{"action":"reuse","artifacts":{"output": ...}}`. 필수.
- `tools.paid-time-off`: 선택. `run` 시 PTO 개인 JSON의 `steps`에 `deduction-quantity`, `usage-ledger`가 있어야 하고 `closing`은 포함하지 않는다. `reuse` 시 필수 아티팩트 `usage-ledger`와 `deduction-quantity`; 외부 승인 완료한 `closing`은 선택.
- Payroll의 `source_files`에서 7개 필수 검증 JSON을 명시하며, PTO 선택 시 `pto_claims`를 반드시 추가한다. `pto_claims`를 생성하는 기능은 없다.
- `run`의 Worktime 설정 기간은 급여월 전체와 동일해야 한다. PTO `as_of_date`는 급여월 안에 있어야 한다. 재사용 인계의 `period_from/to`는 **이번 대상 급여월**이고, 확정 Closing 원본 자체가 전체 분기를 다룰 수 있다는 점과 구별한다.
- Payroll 출력 루트는 Worktime/PTO **출력 루트와 서로 겹치지 않게** 둔다. 기존 Payroll Tool은 자신의 `output_root` 내부에 있는 다른 Tool 산출물을 입력으로 받지 않기 때문이다.

권장 폴더 예시: `/private/hr/results/paid-time-off`, `/private/hr/results/worktime`, `/private/hr/results/payroll`. 각 Tool의 `output_root`를 별도의 형제 폴더로 지정한다.

## reuse 인계 계약

Worktime 예시:

```json
{
  "action": "reuse",
  "artifacts": {
    "output": {
      "path": "/private/hr/results/worktime/wt-202611/worktime-result.xlsx",
      "run_id": "wt-202611",
      "period_from": "2026-11-01",
      "period_to": "2026-11-30",
      "sha256": "REPLACE_WITH_LOWERCASE_64_CHARACTER_SHA256"
    }
  }
}
```

PTO reuse에는 같은 구조로 `artifacts.usage-ledger`(`usage-ledger-result.xlsx`), `artifacts.deduction-quantity`(`deduction-quantity-result.xlsx`)를 모두 기재한다. 확정 Closing을 전달한다면 `artifacts.closing`(`closing-result.xlsx`)을 **추가**하고 외부에서 확정된 자료임을 먼저 검증한다. 실행 폴더명과 인계 run ID가 다르거나 SHA가 다르면 **계산 전 차단**한다.

```bash
# 실제 파일의 해시를 복사해 개인 JSON에 붙인다. (Ubuntu)
sha256sum /private/hr/results/worktime/wt-202611/worktime-result.xlsx
# macOS라면: shasum -a 256 /private/hr/results/worktime/wt-202611/worktime-result.xlsx
```

파일의 `employee_id`는 선행 Tool과 Payroll 입력에 대해 기존 Payroll 검증이 교차 확인한다. 단순 SHA만으로 직원 파일의 진위나 승인권한까지 인증하지는 못한다. 이후 Slack 런타임에서 **사용자/채널/스레드/파일 접근권한**을 별도로 확인해야 한다.

## 결과 / 중단 조건

표준 출력 JSON은 `workflow`, `run_id`, `period`, `approval_state=NOT_APPROVED`, `status=PARTIAL_REVIEW_ONLY`, `handoff`(역할별 경로·실행 ID·해시), `artifacts`(기존 Payroll 산출 경로)만 담는다. Payroll 급여액·승인 JSON 전문은 넣지 않는다.

정확한 경로/해시/기간 불일치, Payroll 7종 XLSX 누락, 외부 승인 JSON 누락, PTO 신청 상세 누락, Worktime 출력 단계 누락, 미확정 Closing 연결, 기존 결과 덮어쓰기 시 중단한다. Payroll 내부 검토에서 오류가 나도 지급 승인으로 해석하지 않는다.

## 서버 검증

서버 호스트 절대경로와 Docker 컨테이너 내부 경로를 구분한다.

```bash
cd /opt/agents/config/agent-config/.external/portfolio

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B -m unittest bhandara.tests.test_workflow_tool_handoff -v

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B bhandara/_tests/run.py

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py
sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

**Portfolio Git 병합과 Hermes 운영 전환은 별개**다. Stage 2~3에서 에이전트 인증·실행·회신·TTL 검증을 진행하기 전까지 `agent-config` 수정·배포는 PAUSE.
