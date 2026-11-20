# Bhandara 사용 안내서

2026-11-20 기준으로 신규 Tool 세 종류와 Workflow를 안내한다. 개인 JSON 설정에서 기간·입력·출력 경로를 선택하면 명령어를 매월 수정할 필요가 없다. 실무 자료를 입력하기 전 **사용자가 검증한 회사 정책과 승인 자료가 있어야 한다.**

## 1. 설치와 개인 설정

```bash
cd /opt/agents/config/agent-config/.external/portfolio
# 이 경로는 서버 호스트용이다. Docker 컨테이너 내부 경로와 구분한다.
mkdir -p bhandara/data/config
cp bhandara/paid-time-off/config.example.json bhandara/data/config/paid-time-off.json
cp bhandara/worktime/config.example.json bhandara/data/config/worktime.json
cp bhandara/payroll/config.example.json bhandara/data/config/payroll.json
cp bhandara/workflow.example.json bhandara/data/config/workflow.json
```

이 네 개인 JSON은 예시 경로로는 실행되지 않는다. 각 파일에서 기간, 정확한 입력 원본·결과 폴더, 단계, 지급정책·증빙 참조를 설정한다. `bhandara/data/`는 공개 Git의 추적 대상이 아니다. 원본·확정 자료와 출력은 되도록 Git 밖의 비공개 경로에 분리한다.

## 2. 세 Tool 실행

| 명령 | 전제 | 주요 결과 |
|---|---|---|
| `python3 run.py bhandara paid-time-off` | 직원정보·근태 판정·승인 휴가 원장, 필요 시 기초인계·발생자료 | PTO 발생·차감·사용원장, 선택 Closing |
| `python3 run.py bhandara worktime` | 근무표·출퇴근/출입기록·외부 검증 근로자료·회사 정책 | `worktime-result.xlsx`의 `WORKTIME` 한 시트 10열 |
| `python3 run.py bhandara payroll` | Payroll Excel **7개**, Worktime 결과, **필수 외부 승인/정책 JSON 7개**, 선택 PTO 자료 | `payroll-result.xlsx`, `payroll-review.json` |

각 Tool 독립 설명: [Paid Time Off](paid-time-off/TOOL-CLI.md) · [Worktime](worktime/TOOL-CLI.md) · [Payroll](payroll/TOOL-CLI.md).

## 3. Tool 간 Workflow

```text
Common 직원·계약·승인 자료
        ├── Paid Time Off (사용 검토 필요 시)
        └── Worktime (필수)
                ↓ 결과 run_id·기간·경로·SHA-256 확인
             Payroll
                ↓
    payroll-result.xlsx + payroll-review.json
```

```bash
python3 run.py bhandara workflow
```

Workflow의 각 Tool은 `run` 또는 명시적으로 검증된 결과의 `reuse`를 선택할 수 있다. PTO가 필요하지 않으면 생략한다. PTO를 사용할 때는 **Usage Ledger + Deduction Quantity + 별도 승인 신청 상세 JSON**을 한꺼번에 전달한다. 미확정 Closing은 Payroll에 전달하지 않는다. [실행·재사용 상세](WORKFLOW.md).

## 4. 인사·급여 담당자 확인사항

- Worktime 10열은 **실제 관찰·검증한 근무 사실**, 추가수당 승인/지급시간이 아니다.
- Payroll Excel은 직원·계약·수당·공제·성과급 입력 총 **7개 별도 파일**이며 각 파일에 한 시트다. [정본](payroll/input-files.json).
- `verified_work`, `approved_segments`, `evidence_registry`, `rate_policy` 등은 회사가 별도로 검증한 JSON을 참조한다. Worktime 엑셀에서 추정해 자동 생성하지 않는다.
- `PAYROLL` 출력은 직원별 1행이며, 한 명에게라도 값이 있는 수당/공제 항목만 동적 헤더를 만든다. 해당하지 않는 직원 셀은 공란이다. 잠정 합계가 계산돼도 실제 지급 승인과 다르다.
- 회사 비용(확인분)과 산재보험료는 **관리자 전용**. 직원에게 Payroll 관리자 파일 전체를 전송하지 않는다.
- 같은 `run_id`로 결과가 이미 존재하면 기존 결과를 삭제하거나 덮어쓰지 않는다.

## 5. 오류와 운영 범위

입력 누락·일자/직원 ID 불일치·SHA-256 변경·승인 자료 부재가 확인되면 실행하지 않고 원인을 확인한다. Slack에 파일만 올리면 자동 분석하거나 계산하지 않는다. 에이전트 연결, 파일 접근 영수증, 보관기간, 후속 댓글 무응답 재현은 [Stage 2~3 운영 연결](OPERATIONS-HANDOFF-2026-11-20.md)에서 별도 검증한다. **실직원 정보를 사용한 자동 검증은 금지**하고 합성자료로만 운영 테스트한다.

> **전환 경고:** 현재 `agent-config`의 Gearbox 일부 어댑터·테스트는 삭제된 공개 Calculator `module.json`과 구형 CLI를 참조합니다. **Portfolio CI가 모두 PASS여도 Gearbox 전체 회귀는 Stage 2에서 호출 계약을 전환하기 전까지 실패할 수 있습니다.** 활성 `.external/portfolio`를 이 PR 브랜치로 전환하면 구형 Hermes 요청이 실패할 수 있으므로, 실제 운영 프로세스 영향 확인 없이 서버 브랜치를 전환·배포하지 마세요. `agent-config`는 이번 PR에서 수정하지 않습니다.

## 6. 개발·서버 테스트

```bash
cd /opt/agents/config/agent-config/.external/portfolio
sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B bhandara/_tests/run.py

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

위에서 `cd`는 **호스트의 전체 절대경로**, `docker exec -w`는 **컨테이너 내부 경로**다. Gearbox 회귀는 현재 미전환 호출을 발견하는 진단이며 Stage 2 전에는 PASS로 가정하지 않는다. 서버 브랜치 삭제·캐시 삭제·배포는 별도 승인 후 일괄 진행한다.
