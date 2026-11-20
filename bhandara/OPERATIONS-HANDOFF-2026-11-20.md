---
document_type: "agent_handoff"
handoff_version: "2.0"
as_of: "2026-11-20"
primary_repo: "seo-an/portfolio"
runtime_repo: "seo-an/agent-config"
stage_1: "MERGED_PR_80"
stage_4: "PR_81_PENDING_VALIDATION"
stage_2: "NOT_CONNECTED"
stage_3: "NOT_VALIDATED"
agent_config_edit: "PAUSED_REQUIRES_EXPLICIT_USER_AUTHORIZATION"
server_cleanup: "DEFERRED_BY_USER"
---

# Bhandara 운영 연결 인수인계 — 현재 유효한 작업

## 확정 결정

2026-11-20 사용자가 작업 순서를 **Stage 1 완료 → Stage 4 코드 철수 → Stage 2~3 에이전트 연결·운영 합성 테스트**로 변경했다. Stage 1은 Portfolio PR #80까지 병합·사용자 서버 테스트 PASS. Stage 4의 정리 코드는 별도 [PR #81](https://github.com/seo-an/portfolio/pull/81)에서 검증·병합 대기 중이다. **`agent-config` 수정·실서버 배포는 명시적 사용자 승인 전 PAUSE**다.

## Portfolio 현재 공개 계약

| Tool | 실행 | 입력/출력 |
|---|---|---|
| Paid Time Off | `python3 run.py bhandara paid-time-off` | 발생·차감·Usage Ledger·선택 Closing |
| Worktime | `python3 run.py bhandara worktime` | `worktime-result.xlsx` / 정확히 `WORKTIME` 10열 |
| Payroll | `python3 run.py bhandara payroll` | 7개 독립 Excel + 외부 검증 JSON → `payroll-result.xlsx`, `payroll-review.json` |
| Workflow | `python3 run.py bhandara workflow` | 기존 결과 run ID·기간·SHA-256 명시 검증 후 Payroll Flow 한 번 호출 |

**강제 유지:** 기존 근태/승인 원장을 새로 합성하지 않는다. PTO 사용 검토 시 Usage Ledger + Deduction Quantity + 별도 승인 신청 JSON을 한 세트로 인계한다. Closing은 외부 확정본만 검증·참조한다. Worktime은 근태 사실, 추가수당 승인이 아니다. 지급합계 등은 잠정치이고 최종 `NOT_APPROVED`. 산재보험료는 사업주 비용 전용이며 직원 지급총액에 섞지 않는다. 별도 50인 Golden E2E 구축하지 않는다.

## Stage 4 — PR #81에서 확인할 일

- 신규 Tool과 Common의 호출/검증 경로가 그대로 동작하는지 `unittest` 확인
- CLI에는 위 지원 명령과 `common-normalizer`만 남는지 확인
- 과거 전용 기능을 단순 경로 변경으로 새 Tool에 끼워 넣지 않기
- 공개 README·RUNBOOK·Tool 안내서에서 잘못된 실행법과 링크 정리
- 삭제된 공개 샘플을 새 Tool 지원 샘플인 것처럼 안내하지 않기
- Stage 4 **Git 병합 전후가 에이전트 운영 배포를 의미하지 않음**을 명시

### 사용자 서버 테스트

```bash
cd /opt/agents/config/agent-config/.external/portfolio
git fetch origin
git switch --track origin/refactor/bhandara-retire-legacy-20261120

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B bhandara/_tests/run.py
sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py
sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

## Stage 2 — Hermes·Gearbox·Slack 신규 Tool 연결 (아직 미시작)

**승인:** `agent-config` 편집 재개는 사용자가 명시적으로 지시해야 한다. 서버 배포는 또 별도 승인.

- 인증된 Slack 업로드는 기존 임시 캐시에 등록하고 **ACK만** 회신. 업로드만으로 처리·Drive/S3 장기 저장하지 않음.
- 신규 댓글/메시지의 `&` 접두 명시적 명령으로 실행을 결정하고, team/user/channel/thread/file ID 및 접근 영수증·TTL을 검증.
- 동일 스레드 다중 첨부의 **파일 역할 계약부터 명시**. 무단 첫 파일 자동 선택 금지.
- Hermes 공통 `uv` 관리 Python(`/opt/hermes/.venv/bin/python`)과 `.external/portfolio`를 사용. 새 상시 서버·DB·별도 가상환경 불필요.
- 실제 회사 자료 대신 합성 파일로 요청→입력 검증→Tool 결과→권한별 출력→Slack 같은 스레드 회신 검증.
- 관리자 급여대장을 일반 직원에게 전송하지 않음.

## Stage 3 — ACK 이후 새 검토 요청 무응답 및 보관/권한 검증

업로드 ACK 자체는 정상이다. **후속 새 요청에 무응답인 문제는 다른 사건**으로 진단한다.

| 합성 이벤트 | 기대 |
|---|---|
| 업로드만 | ACK 한 번, 계산 없음 |
| 같은 스레드 새 `&` 요청 | 응답 또는 구체적 거부 사유 |
| 타 사용자/스레드 | 권한 거절 안내 |
| 파일 만료/삭제 후 요청 | 재업로드 안내, 이전 캐시 재사용 차단 |
| Slack 편집/삭제 이벤트 | 새 LLM 턴 없음, 영수증 무효화 |
| 다중 파일 역할 누락 | 올바른 역할 요청, 임의 추측 금지 |
| Tool 오류·시간 초과 | 실패 사유 회신, 무응답 방치 금지 |

진단 순서: Slack 이벤트 수신→중복 gate→세션 admission→파일 영수증/권한→Tool→outbound. `admission_conflict`, 파일 만료, 이벤트 미전달, 전송 실패를 로그 증거 없이 동일 원인으로 가정하지 않는다.

**현행 보관 정책을 임의 변경하지 않는다:** 일반 업로드는 Hermes 현재 기본 24시간, 인증된 근태 검토 선택 파일은 **최초 캐시 시각부터 3시간**, 신규 다중 첨부 Payroll TTL은 별도 합의 필요. S3/Drive 자동 장기 저장 금지. 직원명·사번·급여액·원본 내용·암호를 로그에 쓰지 않는다.

## 남은 작업의 경계

Portfolio Stage 4 병합 후에도 Hermes 런타임이 기존 호출 경로를 참조한다면 **연결 실패할 수 있다**. `agent-config`는 읽어서 영향범위만 확인하고 수정·배포는 Stage 2 승인 후 별도 브랜치·PR로 한다. 사용자가 별도 지시한 **서버 브랜치·캐시·배포 정리는 마지막에 일괄 처리**한다.
