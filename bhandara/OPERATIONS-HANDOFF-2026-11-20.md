---
document_type: "agent_handoff"
handoff_version: "1.0"
as_of: "2026-11-20"
primary_repo: "seo-an/portfolio"
runtime_repo: "seo-an/agent-config"
subject: "Bhandara 3-Tool operational integration, stages 1-4"
implementation_status: "STAGE1_PR_PENDING_VALIDATION"
portfolio_cli_status: "IMPLEMENTED_AND_USER_TESTED"
runtime_connection_status: "NOT_CONNECTED"
agent_config_edit: "PAUSED_REQUIRES_EXPLICIT_USER_AUTHORIZATION"
server_branch_cleanup: "DEFERRED_BY_USER"
mandatory_50_person_golden_e2e: false
---

# Bhandara 운영 연결 인수인계 — 1~4단계

> **새 대화 시작용 문서.** 이미 완료된 Payroll P0~P3 기능을 다시 설계하거나 같은 계산을 중복 구현하지 않는다. 현재 과제는 **① Tool 간 Workflow → ② Gearbox/Hermes·Slack 연결 → ③ 운영 오류·보관 검증 → ④ 레거시 철수**다. 실제 작업은 아직 시작하지 않았으며 이 문서는 계획과 인수인계만 확정한다.

## 0. 검증된 현재 상태와 결정

| 구분 | 상태 | 의미 |
|---|---|---|
| Portfolio PR #78 | **MERGED / USER SERVER TEST PASS** | 신규 Payroll JSON Tool CLI까지 독립 실행 계약 구현 |
| 신규 `paid-time-off` | **독립 CLI 구현·검증 완료** | PTO 발생·차감·사용원장·선택적 Closing 내부 Flow |
| 신규 `worktime` | **독립 CLI 구현·검증 완료** | 스케줄/출입/근태 검증 및 10열 Worktime Excel |
| 신규 `payroll` | **독립 CLI 구현·검증 완료** | 7개 입력 XLSX + Worktime/선택 PTO + 외부 검증 JSON, 단일 급여대장 |
| 세 Tool 간 Workflow | **미구현** | 상호 호출 순서·파일 경로 인계·실패 중단을 연결할 차례 |
| Gearbox/Hermes 신규 Tool 운영 호출 | **NOT_CONNECTED** | 기존 `agent-config` 코드·설정의 승인 없는 수정 금지 |
| Slack 파일 수신만 했을 때 ACK | **의도된 기존 동작** | 업로드만으로 내용 분석/계산/장기보관하지 않는다 |
| 파일 수신 후 **새 검토 요청에 무응답** | **원인 미확인** | ACK 정상 동작과 분리해 합성자료로 재현·진단 |
| 서버 브랜치·캐시·배포 정리 | **이번 작업에서 제외** | 사용자가 나중에 한 번에 정리하기로 결정 |
| 50명 Golden E2E·새 계산 모듈 | **필수 과제에서 제외** | 개별·통합 unittest가 이미 통과함. 실제 계약 변경에 따른 표적 회귀만 수행 |

**설계 용어**

- `Module` = 독립 계산/검증 기능.
- `Flow` = 한 Tool 안에서 Module을 선택·조합하는 논리적 단계. **`flow/` 물리 폴더를 만들지 않는다.**
- `Tool` = `paid-time-off` / `worktime` / `payroll` 등 독립 실행 단위.
- `Workflow` = 서로 다른 Tool의 호출 순서 및 산출물 인수인계.
- `Common` = 직원정보·매핑 등의 공통 정본. 동일 가입정보를 Payroll에 중복 저장하지 않는다.

**절대 유지할 사용자 합의**

1. **저비용·경량 연결**: 새 상시 데몬, 복잡한 DB, 새 계산기, 50명 Golden 전용 시스템을 만들지 않는다. 기존 Python·JSON·파일 결과를 활용한다.
2. **실행 옵션 대신 개인 JSON**: 기간과 경로는 각 Tool 설정 JSON에서 관리하며 사용자가 매번 CLI 인수를 손으로 고치지 않는다.
3. **파일 규격 고정**: Payroll 7개의 독립 단일시트 Excel, Worktime `worktime-result.xlsx` 10열, Payroll `payroll-result.xlsx`의 `PAYROLL` 단일 시트·동적 헤더를 유지한다.
4. **급여 상태 정직하게 표현**: 산출된 금액의 잠정 지급합계·공제합계·실지급 차액은 표시하되, 보험료/소득세 등의 미확인 사항만 검토 플래그. 미해당 수당·기타 공제 공란은 정상. `NOT_APPROVED`는 지급 승인 아님.
5. **사업주 비용 경계**: 산재보험료는 회사 비용으로만 별도 산출·기록. 근로자 지급합계/공제합계/실지급액에서 제외하고 직원용 출력에서 숨긴다. 전체 회사 총인건비 계산은 **다른 모듈의 미래 책임**이며 Payroll에 추가하지 않는다.
6. **원본/개인정보 보호**: 실제 직원·급여 파일, 승인 참조, 결과를 공개 Git이나 일반 로그에 넣지 않는다. 인증되지 않은 파일 경로·Slack 이벤트로 원본 접근권한을 부여하지 않는다.
7. **`agent-config` PAUSE**: 수정·배포·환경변수/SSM·Gearbox 라우팅 연결은 사용자의 **명시적 재개 지시 후** 별도 브랜치에서 수행. GitHub 읽기/문서 검토는 허용.
8. **서버 정리 일괄 보류**: 브랜치 삭제, 운영 이미지 배포, 서버 파일/캐시 정리는 이 인수인계 작업 범위가 아니다.

## 1. 단계 ① — Portfolio Tool 간 Workflow 연결

**목표:** 신규 Tool 호출의 **순서·입력 참조·실패 처리만** 정한다. 내부 계산 로직은 변경하지 않는다.

### 최소 호출 순서

```text
Common 직원·계약·승인 자료
    ├── Paid Time Off ─── entitlement / deduction-quantity / usage-ledger
    │                     └── closing (마감 확정인 경우만)
    └── Worktime ──────── schedule / attendance-verification /
                          worktime-compliance / output
                              │
             [필수 결과·승인 자료 검증]
                              ▼
                          Payroll
                  review + output (단일 계산)
                              ▼
       payroll-result.xlsx / payroll-review.json
```

- PTO와 Worktime은 서로 **독립**이며 필요한 자료가 준비되면 어느 쪽이 먼저 실행돼도 된다.
- Payroll 시작 전에 **Worktime 결과와 필수 외부 승인/정책 JSON**이 있어야 한다.
- PTO 사용검토를 호출한다면 **`usage-ledger-result.xlsx` + `deduction-quantity-result.xlsx` + PTO 신청 상세 JSON**을 한 세트로 인계한다. Closing은 확정됐을 때만 제공. 없으면 동일 경로에서 **마감 전·변동 가능**으로 처리한다.
- Worktime의 10열은 **근무 사실**이지 수당 지급 승인 데이터가 아니다. `verified_work`·`approved_segments`·`evidence_registry` 같은 외부 근로/승인 원장을 Worktime 결과에서 추정해 생성하지 않는다.
- 다른 Tool의 최신 파일을 자동 검색하거나 파일명으로 임의 매핑하지 말고, **정확한 실행 run ID/기간/경로/해시**를 명시해 인수인계한다.
- 한 번 계산해 이미 있는 산출물을 재사용할 수 있으면 다시 계산하지 않는다. 필요한 선행 단계가 없으면 안전하게 중단하고 필요한 입력 역할을 알려준다.
- 오류 시 **새 원본 생성이나 부분 결과를 성공으로 보고하지 않는다**. 기존 결과·원본 덮어쓰기 금지.

### 실제 독립 명령·설정 정본

| Tool | 호출 명령 | 설정 파일 | 주 출력 |
|---|---|---|---|
| PTO | `python3 run.py bhandara paid-time-off` | `bhandara/data/config/paid-time-off.json` | `deduction-quantity-result.xlsx`, `usage-ledger-result.xlsx`, 선택 `closing-result.xlsx` |
| Worktime | `python3 run.py bhandara worktime` | `bhandara/data/config/worktime.json` | `worktime-result.xlsx` (`WORKTIME` 10열) |
| Payroll | `python3 run.py bhandara payroll` | `bhandara/data/config/payroll.json` | `payroll-result.xlsx` (`PAYROLL` 1시트), `payroll-review.json` |

상세: [PTO CLI](paid-time-off/TOOL-CLI.md) · [Worktime CLI](worktime/TOOL-CLI.md) · [Payroll CLI](payroll/TOOL-CLI.md) · [Payroll 인풋 7종](payroll/input-files.json).

**권장 구현:** 독립 Tool 3개를 순서대로 호출하는 얇은 Workflow 진입점 또는 기존 호출자 내부의 **작은 handoff 함수**. JSON 설정의 실행 기간·파일 역할을 확인하고, 다음 Tool의 설정에 이미 산출된 **명시 경로만** 연결한다. 별도 Worktime/PTO 계산기를 재구현하지 않는다. 결과/근거 파일의 복제·영구 저장은 피한다.

**Stage 1 완료 기준**

- [ ] 필요한 Tool만 지정한 순서로 호출하고 불필요한 Tool을 실행하지 않는다.
- [ ] 기간·직원 ID·원본 해시·출력 역할 불일치 시 정확한 사유로 실패한다.
- [ ] Closing이 없어도 PTO 검토가 필요한 당월 Payroll은 `마감 전` 표시 후 진행한다.
- [ ] Payroll 7종 원본과 `PAYROLL` 출력 스키마가 바뀌지 않는다.
- [ ] 기존 세 Tool 및 전체 Bhandara unittest가 통과한다.
- [ ] 변경사항은 `seo-an/portfolio`의 별도 브랜치·일반 PR로만 반영한다.

## 2. 단계 ② — Gearbox/Hermes·Slack 운영 연결

**시작 전 사용자 승인 필요:** **`agent-config` PAUSE 해제 지시를 먼저 받는다.** Stage 1만으로 Slack 신규 Tool 실행을 활성화했다고 말하지 않는다.

### 현행 코드와 충돌하지 않을 입력 경로

1. **업로드**: 인증된 Slack 파일 메시지는 수신·임시 캐시 등록 후 **정형 ACK만** 반환한다. 업로드 자체를 근태/급여 실행 명령으로 취급하지 않는다.
2. **명시적 실행 요청**: 새 댓글·메시지의 Tool/기간/작업 범위를 확인한다. 현재 사용자 커스텀 명령 접두사는 **`&`**. 이전 `!`/`!!` 예제는 현행 사용자 명령이 아니다.
3. **인증**: Slack 팀/실제 사용자/채널/스레드/파일 ID·캐시 영수증 및 만료를 검증한다. 텍스트에 적힌 경로, 이름, 내용 유사성은 권한 증명이 아니다.
4. **입력 역할 연결**: `employee.xlsx`, PTO/Worktime 파일, Payroll 7종, 외부 승인지정 JSON을 **정확한 역할**로 매핑한다. 현행 네이티브 검토 경로는 **동일 스레드 다중파일을 지원하지 않는다**. 무조건 선택하거나 최신 첨부를 추측하지 말고, 다중 파일 계약을 별도 설계·권한 검증 후 추가한다.
5. **실행**: Hermes Docker 내 **`/opt/hermes/.venv/bin/python`**을 사용, `agent-config/.external/portfolio`의 신규 Tool CLI를 안전한 하위 프로세스로 호출. 다른 venv나 새 상시 프로세스를 생성하지 않는다.
6. **회신**: 작업 ID·상태·검토 요청·산출물 링크/안전한 첨부를 같은 인증 스레드에 반환한다. 실패·권한 누락·입력 누락은 성공 ACK와 구분한다.
7. **결과 보호**: 관리자 급여대장에 있는 산재보험료·회사 비용은 직원 안내에 전달하지 않는다. 회사용 급여 파일은 승인된 관리 권한에서만 공유. 승인·송금·신고를 실행하지 않는다.

### 현행 파일 보관 정책 — 변경하지 않고 재사용

- **파일만 업로드한 경우**: Hermes 기본 임시 캐시(현행 문서상 **24시간**)이고 내용 검토/Tool 실행 없음.
- **인증된 근태 검토로 파일을 실제 선택한 경우**: **최초 캐시 생성 시각부터 3시간**. 후속 요청이 기한을 다시 연장하지 않는다. 만료 이후 새로운 읽기 거부; 호스트 청소 타이머는 약 1분 간격.
- **삭제/편집 이벤트**: 이벤트가 전달된 경우 과거 명령 재실행 없이 캐시 접근 영수증을 무효화. *실제 Slack 이벤트 전달*은 별도 검증 필요.
- **Google Drive 장기보관**: 사용자가 인증된 저장 요청을 명시한 경우에만, 원격 메타데이터를 확인한 뒤 로컬 사본 정리 시도. Payroll 업로드를 자동으로 Drive/S3에 저장하지 않는다.
- **PTO/Payroll 다중 파일 실행에 이 정책을 그대로 적용할 수 있는지** 별도 확인. **모든 업로드를 무조건 3시간으로 바꾸지 않는다.** 정식 새 입력 작업에 대한 TTL·중간산출물 처리·삭제/백업 제외가 필요하면 사용자와 별도 계약을 확정한다.

**Stage 2 완료 기준**

- [ ] 사용자 명시 승인 후 `seo-an/agent-config` 별도 브랜치에서 작업한다.
- [ ] 인증된 후속 명령만 신규 Tool을 호출한다. 파일만 올리면 ACK에서 종료한다.
- [ ] 여러 입력 파일의 역할·권한·유효기간이 불명확하면 계산을 시작하지 않는다.
- [ ] Tool 성공/실패 결과가 원 요청 스레드로 돌아온다. 실자료는 사용하지 않고 합성자료로 확인한다.
- [ ] Bhandara 정확 버전과 Gearbox 계약을 함께 확인한다.
- [ ] 별도 운영 배포 승인을 받기 전에는 컨테이너 이미지 재배포·SSM 변경을 하지 않는다.

참조 정본(읽기 전용): [파일 수신/만료](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/command-scoped-file-lifecycle.md), [Slack 입력 go-live](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/bhandara-slack-input-go-live.md), [버전 호환성](https://github.com/seo-an/agent-config/blob/main/gearbox/adapters/bhandara/VERSION_COMPATIBILITY.md).

## 3. 단계 ③ — Slack ACK 이후 무응답·권한·보관 운영 안정화

**문제:** 파일만 받았을 때 정형 ACK를 하는 것은 의도된 정상 동작이다. **별도의 새로운 검토 요청을 보냈는데 답이 없는 현상**은 미해결이며, ACK 동작을 수정해 자동계산시키는 방식으로 우회하지 않는다.

### 합성 E2E 진단 순서

| 케이스 | 예상 결과 | 실패 시 조사 경계 |
|---|---|---|
| 합성 파일만 업로드 | ACK 1회, LLM 분석/자동 계산 없음 | 네이티브 업로드 분기·파일 receipt |
| 같은 스레드 새 댓글에 명시적 검토 | 요청 인증 후 응답/검토 또는 구체적인 차단 사유 | Slack event 수신 → 명령 routing → 세션 admission → Tool 호출 → outbound |
| 다른 스레드·다른 사용자 | 접근 차단 안내 | Slack team/user/channel/thread/file ID |
| 파일 만료 후 검토 | 다시 업로드 요청 | 영수증 유효기간·캐시 타이머 |
| 삭제·편집 이벤트 | 새 모델 턴 없이 영수증 무효화 | 이벤트가 실제 전송됐는지·중복 이벤트 gate |
| 삭제 뒤 새 검토 | `파일 없음` 고정 안내 | stale receipt·삭제 후 접근 차단 |
| 승인 없는 다중 파일 | 역할 불명으로 실행 거절 | 입력 선택·파일 역할 매핑 |
| Tool 내부 오류 | 실패 사유·재시도 지침을 스레드로 회신 | 실행 결과·시간제한·메시지 전송 오류 |

**진단 원칙:** 사용자 메시지를 다시 수신했는지부터 확인. `RuntimeStoreError: admission_conflict`, Slack 중복/수정 이벤트 차단, 권한 영수증 만료, Tool 실패, Slack outbound 실패를 **증거 없이 같은 원인으로 단정하지 않는다**. 로그에는 직원명·급여액·파일 본문·개인식별자·원본 경로·비밀키를 출력하지 않는다. 네트워크·권한 실패에는 정해진 사용자용 오류 회신을 제공하고 **무응답 방치하지 않는다**.

**Stage 3 완료 기준**

- [ ] 후속 **새 메시지**가 실제로 처리되고 답변 또는 차단사유를 반환한다.
- [ ] 수신·검증·실행·회신 단계별 최소 진단 상태가 남는다(민감 원본 제외).
- [ ] 삭제·만료·다른 스레드·중복 요청에서 재실행/원본 재사용이 발생하지 않는다.
- [ ] 인증된 근태 검토 3시간/기본 파일 24시간 등 현재 선택적 보관 정책을 위반하지 않는다.
- [ ] 합성파일 E2E와 Bhandara·Gearbox 기능/인프라 회귀가 통과한다.
- [ ] 운영 배포는 계획·명시 승인 후만 수행한다.

## 4. 단계 ④ — 레거시 철수 및 문서/호출 경로 정리

**현재는 삭제 금지.** 구형 `pto-calculator`, `worktime-calculator`, `payroll-calculator` 및 Gearbox 기존 의존 경로가 남아 있다. 새 Tool 코드가 병합됐어도 **운영 라우팅 전환 확인 전 구형 호출을 없애지 않는다**.

**순서**

1. 구형 CLI·모듈·설정·Gearbox 어댑터·문서·예제의 **실제 참조처**를 검색해 인벤토리화한다.
2. 각 호출의 현재 입력/출력 계약을 신규 Tool이 처리할 수 있는지 확인한다. 신기능이 아직 미지원인 참조를 무조건 제거하지 않고 사용 여부를 판단한다.
3. Stage 1~3의 새 호출·Slack 회신·버전 호환성이 통과하면, **각 구형 Tool을 별도 일반 PR**로 라우팅 교체 → 회귀 → 제거한다. 일괄 삭제로 숨은 운영 호출을 깨뜨리지 않는다.
4. 신규 문서·샘플·설치 스크립트에 남은 구형 필수 의존을 최신화한다. 기존 결과 비교를 위한 **기존 검증·회귀 테스트**는 유지하되, **별도 50명 Golden E2E를 새 철수 필수조건으로 추가하지 않는다.**
5. 최종 사용자 테스트·병합 후 운영 배포/서버 cleanup은 **사용자가 정한 시점에 한 번에** 진행한다. 이번 문서 PR에서는 아무것도 삭제하지 않는다.

**Stage 4 완료 기준**

- [ ] 새 CLI/Tool이 운영에서 실제로 선택되며 구형 호출 경로가 남지 않는다.
- [ ] 각 레거시 철수 PR의 독립 실행·버전 호환성·Gearbox 회귀가 통과한다.
- [ ] README/RUNBOOK·샘플이 새 CLI를 안내하며 구형 명령은 역사 기록으로만 남는다.
- [ ] 실제 직원/급여 자료·백업/임시파일을 코드 삭제 작업의 대상으로 취급하지 않는다.
- [ ] 사용자가 서버 정리를 승인한 뒤 정리/배포하고, 롤백 경로를 확인한다.

정본: [레거시 철수 계획](LEGACY-RETIREMENT.md).

## 5. 검증·PR·운영 명령 (참고용; 지금 실행하지 않음)

**사용자 서버 경로에서 브랜치를 직접 검사한다.** Draft PR이나 worktree로 서버 테스트하지 않고, 서버에서 GitHub로 push 요구도 하지 않는다.

```bash
# Bhandara 주제별 전체 unittest
sudo docker exec -w /opt/agent-config/.external/portfolio \
  hermes /opt/hermes/.venv/bin/python -B bhandara/_tests/run.py

# Gearbox 기능 회귀
sudo docker exec -w /opt/agent-config \
  hermes /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py

# Gearbox 인프라 회귀
sudo docker exec -w /opt/agent-config \
  hermes /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

모듈 버전 또는 입출력 계약을 변경할 때에는 [Gearbox 버전 호환성](https://github.com/seo-an/agent-config/blob/main/gearbox/adapters/bhandara/VERSION_COMPATIBILITY.md)을 매번 재검증. 정책/승인 미확정인데 결과를 `APPROVED`로 승격하지 않는다.

**프로젝트별 Git 작업 방식:** 별도 branch → 코드/문서+`unittest` → 일반 PR → 사용자가 서버에서 해당 PR 브랜치 직접 테스트 → 사용자 merge → 필요한 시점에 운영 배포/서버 branch cleanup. `agent-config`의 운영 변경은 별도 승인 필요.

## 6. 남겨야 하는 일과 다음 대화의 첫 작업

| 우선순위 | 작업 | 저장소 | 현재 단계 |
|---|---|---|---|
| **1** | 세 Tool Workflow 호출 순서·파일 인계 규칙/가벼운 어댑터 검토·구현 | `seo-an/portfolio` | **NOT_STARTED** |
| **2** | 인증 Slack 후속 명령 → Gearbox → 신규 Tool → 회신 | `seo-an/agent-config` | **PAUSED**, 사용자 재개 승인 필요 |
| **3** | 업로드 ACK 후 별도 검토 요청 무응답 재현·안전한 응답/TTL·삭제 검증 | `seo-an/agent-config` | **NOT_VERIFIED / PAUSED** |
| **4** | 구형 계산기 참조 제거·각 도구 별도 PR로 철수 | 두 저장소 | **BLOCKED_BY_STAGE_2_3** |
| 후순위 | PTO Use Promotion, Worktime Closing/복수 구간 등 독립 기능 잔여 | `seo-an/portfolio` | Workflow 필수 전제 아님 |
| 별도 프로젝트 | 회사 총인건비·회계 분석 | 추후 모듈 | Payroll에 추가하지 않음 |
| 마지막 | 서버 브랜치/캐시·운영 배포 정리 | 서버 | **DEFERRED_BY_USER** |

**다음 대화에서 우선할 지시:** “이 인수인계서 기준으로 **Stage 1(Portfolio의 최소 Workflow 호출·결과 인계)**부터 진행. 새 계산기/Golden E2E/DB 없이, 기존 세 Tool의 JSON 경로 계약을 유지할 것. `agent-config`는 내가 명시적으로 재개하기 전까지 수정하지 말 것.”

### 최종 주의

- **서류에 적힌 계획은 구현/배포 완료가 아니다.**
- **파일 업로드 ACK는 계산 실행 성공이 아니다.**
- **잠정 급여 합계는 실제 임금 지급 승인액이 아니다.**
- **관리자 급여대장과 직원 안내용 데이터는 다르다.**
- **서버 정리는 사용자 지시에 따라 지금 하지 않는다.**
