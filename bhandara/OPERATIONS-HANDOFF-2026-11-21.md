---
document_type: "agent_handoff"
handoff_version: "3.0"
as_of: "2026-11-21"
timezone: "Asia/Seoul"
primary_repo: "seo-an/portfolio"
runtime_repo: "seo-an/agent-config"
calculator_implementation: "MERGED"
slack_native_ack_and_semantic_attendance_review: "USER_REPORTED_LIVE_PASS"
first_last_excel_slack_upload: "LIVE_NOT_VERIFIED"
emergency_delete: "MERGED_BUT_LIVE_NOT_VERIFIED"
---

# Bhandara 최신 인수인계 — 2026-11-21

이 문서는 [11월 20일 기존 인수인계](OPERATIONS-HANDOFF-2026-11-20.md)를 **현재 관찰 상태에 맞춰 보완**한다. 기존 문서는 그 시점의 역사적 현황이며, `Slack 운영 미검증` 문구를 현재 전체 기능이 미동작한다는 뜻으로 읽지 않는다.

세부 Hermes/Slack 코드, 운영 실증 로그, 안전한 서버 정리 절차는 `seo-an/agent-config`의 [Hermes × Bhandara 2026-11-21 인수인계](https://github.com/seo-an/agent-config/blob/main/operations/handoffs/HERMES_BHANDARA_HANDOFF_2026-11-21.md)가 정본이다. 링크 문서가 아직 PR에 있으면 해당 PR 병합 전까지 그 브랜치의 파일을 참고한다.

## 1. 계산기·Tool·Workflow 현재 범위

| 계층/기능 | 구현 판정 | 남은 운영 검증 |
|---|---|---|
| Common / Normalizer | 공개 독립 모듈 구현·테스트, 입력 열·정규화/매핑 계약 존재 | Slack 파일 수신 권한과 모델 독립 호출은 별도 |
| Paid Time Off | 발생·차감·사용 원장, 외부 확정 시 선택 Closing; JSON Tool 병합 | 실제 비공개 운영자 JSON/외부 승인 원본을 통한 운영 |
| Worktime | 스케줄·출입·휴게·근로 사실 검토, `WORKTIME` 10열 Excel; JSON Tool 병합 | 생성 파일의 실제 Slack 전달 E2E |
| Payroll | 7개 분리 입력 Excel·외부 정책/승인 JSON·동적 `PAYROLL` 1시트·검토 JSON; Tool 병합 | 기간·증빙·지급 승인 분리, 복수 Slack 원본 역할 매핑 |
| Workflow | PTO 선택 + Worktime → Payroll; `run/reuse`, 기간·SHA-256·독립 출력 검증 (#80) | Slack을 통한 전체 복합 업무 실행은 검증 전 |
| 구형 경로 철수/파일보존 | 구형 계산기·샘플 정리 (#81), 원본 불변·`xb`·중복 run ID 거부 (#82) | 실원본 보존 계속 유지, `git clean -fdx/-ffdx` 금지 |

단일 Module 요청은 해당 Module만 실행해야 한다. 내부 PTO/Worktime/Payroll Module은 Index에서 검색할 수 있지만 **모든 Module의 별도 모델 실행 인터페이스는 아직 연결되지 않았다**. Tool과 Workflow의 JSON은 운영자가 검증해 준비한 설정만 읽고, Slack에 올린 파일을 자동으로 Payroll 7개 입력에 배정하지 않는다.

## 2. Hermes와의 운영 연결 — 2026-11-21 실제 관찰

| 경로 | 운영 상태 |
|---|---|
| 파일만 Slack에 업로드 | Ananda 고정 ACK 실제 수신 **PASS** |
| 업로드 후 동일 스레드 자연어 검토 | 실제 합성 출입원장 집계 **PASS** |
| 파일 + 자연어 검토 동시 업로드 | 실제 합성 출입원장 집계 **PASS** |
| `&bhandara review attendance` | 실제 합성 8/8건, 출근 후보 3일, 인증 성공/실패 7/1건 **PASS** |
| 일반 자연어 FIFO | 2026-11-21 Hermes 프로세스 재시작 후 `GEARBOX_NATIVE_FIFO_REPLAY_PASSTHROUGH` 및 실제 응답 **PASS** |
| 파일에서 사람별 최초·최종 Excel 생성·Slack 반환 | 코드/합성 테스트 존재, **실제 Slack 파일 수신 E2E 미확인** |
| Slack에서 여러 내부 Module 독립 호출 | **미연결** |
| 다중 Payroll 파일 → 역할 매핑 → 전체 Workflow | **미구현/운영 미검증** |
| `&` 명령 담당·Moksha tombstone·긴급 `&delete` | agent-config #222~#224 병합. **최신 Hermes 이미지 배포·실제 다중봇 E2E 미확인** |

**테스트 데이터:** 2026-11-21 합성 CSV 원본 8건/처리 8건/출근 후보 3일/성공 7·실패 1. 이는 **실제 급여·근태 승인 자료가 아니며** 다른 모든 모듈 검증을 대신하지 않는다.

## 3. 새 대화에서 가장 먼저 할 일

1. **서버 로컬 Git 정리:** 2026-11-21 사용자 결정은 현재 `agent-config` 작업 브랜치의 *미커밋 추적 파일 변경을 전부 폐기*하는 것이다. `sudo git reset --hard HEAD` (현재 저장소에만 적용) → `sudo git switch main` → `sudo git fetch origin` → `sudo git merge --ff-only origin/main` → 병합된 로컬 `feat/ananda-emergency-thread-delete-20261121` 브랜치 `sudo git branch -d ...`. **Git 무시 실원본/결과까지 삭제하는 `git clean`은 금지**.
2. **최신 Hermes 이미지:** 병합 #223·#224 포함 여부와 서버 `main`/clean 상태 확인 후 기존 승인된 `deploy-hermes.sh --plan`→`--apply --build-image --file-lifecycle-e2e` 절차. 아직 사용자로부터 이미지 재빌드 성공 보고를 받지 않았다.
3. **긴급 명령 합성 E2E:** 아난다/칸타카/무찰린다의 멘션이 섞인 스레드에서 `&` 명령 담당을 확인하고, 실제 삭제해도 되는 합성 스레드에 `&moksha`/`&delete` 적용. 성공 기준은 **슬랙 원본·댓글 삭제 + 착수/완료 댓글 0개**. 관리자 User OAuth의 타봇 메시지 실제 삭제는 아직 실증되지 않았다.
4. **Bhandara Excel 진짜 Slack 수신:** 같은 인증된 합성 출입원장에서 `attendance_first_last_excel`을 자연어로 요청하고 실제 XLSX가 같은 스레드에 올라오는지 검증. 완전 동일행 중복검사(`attendance_exact_dedup_review`)와 구별한다.
5. **차기 구현 우선순위:** 복수 Slack 첨부의 정확한 역할·file ID 바인딩과 인증/TTL → 개별 Module 독립 실행기 → 실제 정책 JSON/승인 근거를 갖춘 Tool/Workflow 운영 E2E. 실제 HR 입력은 외부 승인 없이는 지급/확정하지 않는다.

## 4. 구현 원칙

- **Hermes:** 의도·자료·도구·순서를 자율 판단한다. **Capability Index:** 올바른 도구를 찾도록 돕는 선택 가이드이며 자연어를 정규식으로 통제하는 라우터가 아니다. **Tool/Module:** 동일 계약/입력에 대해 예측 가능하고 일관된 결과를 준다. **Gateway:** 인증·접근권한·실행 순서·파일 수명만 보장한다.
- Module → 논리적 Flow → Tool → Workflow는 서로 다른 계층이다. 자연어 질문이 단일 Module을 요구하는데 전체 Tool이나 Payroll Workflow를 자동 실행해서는 안 된다.
- 실직원 데이터, 승인자료, 파일 ID 매핑은 Git/공개 로그에 저장하지 않는다. 서버의 uv Python/독립 Portfolio 실행 환경과 `unittest`를 사용한다.
- 사용자가 서명한 정책/승인 JSON 없이 급여 지급, 세금·보험 신고, Worktime 추정값을 실제 근로 확정으로 처리하지 않는다.

## 5. 참고 문서

- [Portfolio README](../README.md), [Bhandara RUNBOOK](RUNBOOK.md), [Workflow](WORKFLOW.md), [2026-11-20 인수인계(과거 상태)](OPERATIONS-HANDOFF-2026-11-20.md)
- [Agent-config 운영 인수인계](https://github.com/seo-an/agent-config/blob/main/operations/handoffs/HERMES_BHANDARA_HANDOFF_2026-11-21.md)
- [파일 수신/Slack 운영 판정](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/bhandara-go-live-readiness-2026-11-20.md)
- [아난다 긴급 삭제](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/slack-emergency-thread-delete.md)
