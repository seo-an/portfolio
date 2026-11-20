---
document_type: "agent_handoff"
handoff_version: "2.1"
as_of: "2026-11-20"
primary_repo: "seo-an/portfolio"
runtime_repo: "seo-an/agent-config"
portfolio_tool_workflow: "MERGED_PR_80"
portfolio_legacy_retirement: "MERGED_PR_81"
portfolio_workspace_protection: "MERGED_PR_82"
agent_config_semantic_slack: "MERGED_PR_211_SYNTHETIC_TESTS_PASS"
agent_config_safe_sync: "PR_212_PENDING_MERGE"
runtime_deployment: "NOT_VERIFIED"
live_slack_e2e: "NOT_VERIFIED"
server_cleanup: "NOT_YET_EXECUTED"
---

# Bhandara 운영 인수인계 (2026-11-20 상태 정정)

이 문서는 이전 Stage 1~4 작업의 현재 상태를 **완료된 코드와 운영 검증으로 구분**한 최신 인수인계다. 이전의 “Stage 2 미시작”, “PR #81 검증 대기”, “agent-config 편집 PAUSE” 등은 더 이상 정확하지 않다. 운영 전환의 검증 절차와 실제 합성 Slack 시나리오는 [agent-config 운영 판정서](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/bhandara-go-live-readiness-2026-11-20.md)를 따르며, 해당 문서가 담긴 PR #212가 병합되기 전에는 [PR #212 브랜치의 정본](https://github.com/seo-an/agent-config/pull/212)을 참고한다.

## 1. 완료된 코드와 테스트

| 대상 | 상태 | 한계 |
|---|---|---|
| Paid Time Off | 발생·차감·Usage Ledger·선택 Closing; 독립 JSON Tool 구현·병합 | 외부 확정 자료 없으면 상계·급여 반영 승인 불가 |
| Worktime | 스케줄·출입 검토·휴게·근로 사실 10열 Excel; 독립 JSON Tool 구현·병합 | 출입 원본으로 미확인 근로·급여를 추정하지 않음 |
| Payroll | 7개 별도 입력 Excel + 정책·승인 JSON → 잠정 단일 `PAYROLL` 시트·검토 JSON | 원천징수/보험 신고·임금 지급 승인 아님 |
| Workflow | PTO 선택 + Worktime → Payroll, run/reuse/기간/SHA-256 인계 구현·병합(#80) | Payroll은 승인된 입력과 서로 분리된 Tool별 출력 루트 필요 |
| 구형 계산기 정리 | 구형 계산 경로/전용 샘플 제거 병합(#81) | 기존 삭제된 CLI와 혼용 금지 |
| 저장 보호 | Excel 원본 불변, 신규 결과 `xb`, 같은 실행 ID 거부, Git ignore 및 자동 안내 폴더 (#82) | 기존 동기화 스크립트는 별도 안전 패치 필요 |
| Slack Index 및 파일 Module | agent-config #211 병합; 자연어 Tool Index, ACK 후 새 요청, Ananda 출입원장 3종, 최초·최종 Excel 전송 합성 검증 | 실제 Hermes 운영 배포 및 Slack E2E 미검증 |

사용자는 단계별 서버 합성 테스트(신규 Excel 3건, Index 9건, Portfolio 보존 9건) 통과 및 PR #211·#82 병합을 보고했다. **실제 Slack/실사용자 자료 검증을 의미하지 않는다.**

## 2. 역할과 범위

- **Module:** 단일 기능. 사용자가 하나만 요청하면 명시적으로 연결된 해당 Module만 사용. 현재 Hermes 모델이 직접 실행 가능한 첨부 파일 Module은 Ananda의 `attendance_source_audit`, `attendance_exact_dedup_review`, `attendance_first_last_excel`이며 출입 원장 1개만 인증해 처리한다.
- **Flow:** 하나의 Tool 설정 JSON `steps`에 따라 선택된 Module만 실행. 내부 PTO·Worktime·Payroll Module은 Index에서 검색 가능하지만 **별개 모델 호출 엔드포인트는 미연결**. 지원하지 않는 단일 Module을 전체 Tool로 바꾸면 안 된다.
- **Tool:** Paid Time Off, Worktime, Payroll 각각 `run.py bhandara <tool>`. 사전 준비한 비공개 JSON에서만 입력·기간·승인 정책을 받고, 임의 Slack 파일명을 자동 연결하지 않는다.
- **Workflow:** 사용자가 명시적으로 여러 Tool을 연결하라고 요청하고, 개별 JSON·입력·근거가 완비된 경우에만 실행. 승인·정합성 검증에 실패하면 중단.
- **Index:** 모델이 `bhandara_capabilities(focus="all")`로 기능을 검색하고 정확한 ID로 `focus` 재확인. **Index는 권한 부여나 실행 그 자체가 아님**. 모호한 경우 이미 합의된 설명을 반복 질문하지 않는다.
- **Muchalinda:** 일반적인 `검토해줘`가 Ananda 네이티브 감사로 잘못 라우팅되던 코드는 수정·테스트됨. 그러나 Muchalinda가 Ananda의 비공개 HR 원본을 직접 열 권한을 얻은 것은 아니다. 필요하면 인증된 Ananda 경로 안내.

## 3. 데이터·폴더·덮어쓰기 원칙

```text
bhandara/data/                 # Git 무시: 실제 입력·승인 JSON·결과
  config/                      # 사용자 사전 설정 JSON
  input/common/                # 공통 employee.xlsx 등
  input/paid-time-off/         # PTO 입력
  input/worktime/              # 근태/출입 원본
  input/payroll/               # 급여 Excel 7개 및 승인 JSON
  output/paid-time-off/<run_id>/
  output/worktime/<run_id>/
  output/payroll/<run_id>/
```

각 Tool을 처음 실행 시도하면 해당 `input/<tool>`, `output/<tool>`, `input/common`, `config` 안내 폴더만 자동 생성한다. **입력 또는 설정이 없어도 디렉터리만 준비**하며 원본을 생성·수정·이동·삭제하지 않는다. 새 실행 ID에만 결과 생성. 기존 `run_id`의 산출물은 덮어쓰지 않는다. 외부 비공개 입력 경로를 JSON에 명시했다면 그 설정이 우선한다.

`bhandara/data/config`에 복사한 예시 JSON은 `input_root: "../input"`, 각 Tool `output_root: "../output/<tool>"`이다. 서로 같은 출력 루트를 사용하면 Workflow가 다른 Tool의 결과를 Payroll 출력 내부 원본으로 간주해 거부할 수 있으므로 **형제 출력 루트**가 필수다. 기존 개인 JSON은 자동 수정하지 않으며 필요한 경우 사용자가 직접 경로를 검토한다.

**서버 업데이트 안전 차단:** 구형 `update-bhandara-server.sh --apply`는 `git clean -ffdx`로 ignored 입력/결과를 삭제할 수 있다. [agent-config PR #212](https://github.com/seo-an/agent-config/pull/212)의 보존 수정이 병합·서버 최신화되기 전에는 사용 금지. `git clean -fdx`, `git clean -ffdx`, 대량 캐시 삭제 금지. 신규 안전 스크립트는 추적 코드만 reset하고 ignored/untracked 파일을 보존한다.

## 4. 남은 운영 업무

1. #212 및 이 문서·기본 출력 루트 보완 PR의 서버 테스트, 병합.
2. 실제 서버의 `agent-config`·`.external/portfolio` 최신 `main` 동기화, 변경 전 보존 대상 점검. 실행 중 Bhandara 작업 없는 시간에 진행.
3. 전체 기능/인프라 테스트 및 Hermes v0.23 패치 검사. 필요 시 기존 승인 배포 절차에 따라 **명시적으로** 이미지 재빌드/적용. `ATTENDANCE_SLACK_ENABLED` 옵션 설정 확인.
4. 합성 Slack: Ananda에 파일만 전송하면 ACK, 별도 요청으로 첫/마지막 Excel 실제 수신, 재업로드 없이 후속 요청, Muchalinda 일반 검토가 권한 오호출 없이 안내하는지 검증.
5. 실제 Slack 통합 검증 완료 후에만 운영 상태를 `E2E_PASS`로 갱신. 다중 첨부 Payroll 역할 매핑·모든 내부 Module Slack 단독 실행은 별도 과제.

**금지:** 실직원·급여 원본을 Git·일반 로그·비공개가 아닌 Slack 채널에 붙여 검증, 강제 캐시 삭제, S3 읽기 정책·SSM 쓰기 역할 무단 부착, 서버에서 GitHub push, Draft PR/worktree 검증.
