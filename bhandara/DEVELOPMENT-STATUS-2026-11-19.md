# Bhandara 개발 현황 — 2026-11-19

> PR #54·#55·#56·#57은 모두 main 병합 확인. 신규 PTO/Worktime은 JSON 설정으로 독립 실행 가능하나, Gearbox/Slack 운영 호출은 별개이며 미연결. 사용자 서버 테스트에서 #56·#57 모두 통과 보고. 다음 본선은 신규 Payroll Tool 설계.

## 1. 확정 아키텍처

**Module → Flow(논리적 조합) → Tool → Workflow(Gearbox)**

- Module: 독립 계산·검증 책임.
- Flow: 같은 Tool 안의 선택적 단계 조합. 별도의 물리 flow 폴더를 만들지 않는다.
- Tool: paid-time-off, worktime, 향후 payroll. 독립 Python과 JSON 설정, 입력·출력 소유.
- Workflow: 여러 Tool의 연결, Slack/Hermes 파일 인증·권한·임시캐시·후속 회신을 담당하는 Gearbox.
- Common: 식별 매핑과 파일/입력 정규화용 공유 기능.
- 기존 pto-calculator, worktime-calculator, payroll-calculator는 구형 호환 경로로 남겨둔다.

## 2. 완료와 미완료

| 영역 | 구현 완료 | 아직 남은 것 |
|---|---|---|
| Common | 5시트 ID 매핑(ID_MAP, EXTERNAL, PERSON MAP, DEPARTMENT MAP, AREA MAP), 업체별 식별 연동, 수동 합성 샘플 생성 | 현장 특수 포맷 발생 시 계약 추가 |
| Paid Time Off | Entitlement, Deduction Quantity, Allocation, Expiry/Carryover, Usage Ledger, Closing, Excel, JSON 선택 Flow/CLI (#56) | Use Promotion, 실제 HR 운영 검증, Gearbox 연결 |
| Worktime | Schedule, Attendance Verification, Worktime Compliance, Schedule ID 매핑, Worktime 10컬럼 Excel, JSON 선택 Flow/CLI (#55·#57) | 현장 입력 인증·권한, Gearbox 연결, Closing, 다중 근무·복수 휴가 |
| Payroll 구형 | payroll-calculator 검토용 계산/계약·지급항목/과세 후보 | 새 Worktime 결과를 직접 구형 Worktime JSON처럼 사용할 수 없음 |
| Payroll 신규 | 아직 개발하지 않음 | Module/Flow, 시간의 급여 반영 해석, 결과·급여대장·JSON CLI 설계 |
| Agent 운영 | 기존 Gearbox/Slack 접수 및 구형 도구 연결 | 신규 Tool 운영 어댑터, 파일 수신 ACK 이후 후속 명령 무응답 진단 |

병합 PR: [#54](https://github.com/seo-an/portfolio/pull/54), [#55](https://github.com/seo-an/portfolio/pull/55), [#56](https://github.com/seo-an/portfolio/pull/56), [#57](https://github.com/seo-an/portfolio/pull/57).

## 3. JSON 중심 CLI

사용자는 명령 옵션을 매번 수정하지 않는다. 기준일·경로·정책·단계 선택을 공개 Git에서 제외된 JSON으로 보관한다.

| Tool | 고정 실행 명령 | 기본 JSON 위치 | 단계 |
|---|---|---|---|
| Paid Time Off | python3 run.py bhandara paid-time-off | bhandara/data/config/paid-time-off.json | entitlement, deduction-quantity, usage-ledger, closing |
| Worktime | python3 run.py bhandara worktime | bhandara/data/config/worktime.json | schedule, attendance-verification, worktime-compliance, output |

- JSON 예제: [PTO](paid-time-off/config.example.json), [Worktime](worktime/config.example.json).
- 사용법: [PTO CLI](paid-time-off/TOOL-CLI.md), [Worktime CLI](worktime/TOOL-CLI.md).
- 자동 run ID는 기존 산출물을 덮어쓰지 않는다.
- 명시하지 않은 단계는 실행하지 않는다. 이전 결과를 재사용하려면 정확한 파일을 JSON에 지정한다.
- 신규 CLI는 Slack의 기존 명령 실행 경로와 자동 연결된 것이 아니다.

## 4. Worktime 결과 — Payroll로 전달할 확정된 사실

최종 파일: **worktime-result.xlsx**, **WORKTIME 시트 하나**, 다음 10열만 사용.

| 열 | 의미 |
|---|---|
| employee_id | 직원 식별자 |
| work_date | 근무 귀속일 |
| schedule_id | 개별 근무 일정 ID |
| scheduled_min | 소정 근로분 |
| actual_min | 외부 확인된 실제 근로분 |
| clock_in_delta_min | 예정 출근 − 장부 출근 |
| clock_out_delta_min | 장부 퇴근 − 예정 퇴근 |
| attendance_type | 외부 확정 근태구분 |
| leave_type | 외부 확정 유급·무급 등 휴가구분 |
| leave_request_id | 휴가 원신청 ID |

**시간 관련 컬럼은 소정·실제·출근Δ·퇴근Δ 네 개로 고정.** 합계 차이, 급여 반영시간, 연장/야간 승인, 금액, 검토/상태 판정은 이 최종 결과에 넣지 않는다.

- 조기출근: 출근Δ 양수, 지각: 출근Δ 음수.
- 지연퇴근: 퇴근Δ 양수, 조기퇴근: 퇴근Δ 음수.
- Attendance Verification 내부의 차이 부호(장부−예정)는 유지하고 최종 Output의 출근 부호만 반전.
- 미확정 실제근로는 null; 확정된 0분과 혼동하지 않는다.
- Schedule ID의 DAY/NIGHT/SHIFT와 근로시간제 worktime_system은 다르다.
- 반차 사례: 소정 480, 유급반차 원신청 240, 실제 300일 때 급여 반영 여부/추가 60분 계산은 **Payroll 시작 단계**에서 신청 범위와 근로시간 겹침을 확인하여 결정한다.
- 시각 변화량을 실제 근로분에 무조건 합산하면 중복 계산 위험.
- 출입기 일반 ACCESS는 미확정 후보이며 근로 승인과 급여 근거가 아니다.

관련: [스케줄 매핑](worktime/SCHEDULE-MAP-CONTRACT.md), [최종 출력](worktime/OUTPUT-CONTRACT.md).

## 5. 다음 본선: Payroll 신규 설계

1. 구형 payroll-calculator에서 재사용 가능한 계약 입력·지급항목·산정 로직·과세 후보·Excel 생성을 **소스 코드 기준** 조사. 불필요한 복제 금지.
2. 첫 Payroll 단계가 Worktime 네 시간 사실, 휴가 신청 ID로 조회한 실제 신청시간, 계약·정책을 받아 급여 반영시간을 결정한다. Worktime에 이 책임을 떠넘기지 않는다.
3. 야간·휴일·연장, 소정 미달, 무급휴가, 무단결근, 반차 후 초과근로, 미확정/누락의 처리 기준과 Module 경계를 설계하며 승인이나 차감 근거를 추정하지 않는다.
4. 지급항목 계산, 과세/비과세 검토, 공제, 급여대장 Excel 등은 이후 Payroll 단계에서 분리.
5. 설계 → Module 구현 → Output → JSON CLI → unittest → PR/서버 검증의 순서. 신규 payroll Tool은 아직 없다.

## 6. 병행 운영 트랙: Excel 첨부 ACK 이후 후속 무응답

- **사용자 보고:** 에이전트가 Slack 파일 첨부에 수신 안내만 하고 후속 검토 요청 또는 대화가 진행되지 않는 현상. 인과관계와 재현 조건은 미확인.
- **의도된 행동:** 업로드만으로 원본 내용을 분석하거나 영구 저장하지 않는다. 지원되는 후속 명시 검토/저장 요청은 **새 메시지**로 도착하면 기존 인증·권한·만료 규칙으로 처리되어야 한다. 후속 응답 중단은 별도 운영 문제다.
- **2026-11-16 현행 문서 계약:** 일반 업로드는 Hermes 기본 임시 문서 캐시 24시간(당시 확인값), 명시된 검토 대상으로 선택되면 최초 업로드 시각부터 3시간, S3 백업 제외, Drive 영구 저장은 별도 명시 요청. 임시 캐시와 영구 저장은 구분한다. 모든 파일을 자동 3시간 캐시로 바꾸지 않는다.
- **다음 진단:** 합성 Excel로 업로드 ACK → 같은 스레드 별도 검토 메시지 → 인바운드 이벤트·후크·권한 영수증·TTL·모델 턴 생성·Slack 아웃바운드를 단계별로 확인. ACK-only가 문제의 원인이라고 단정하지 않는다.
- 다음 연결: 새 Tool JSON 입력·출력 계약 vs Gearbox 구형 어댑터를 비교하고, 브리지·호환성 게이트·합성 E2E를 구축. 실제 운영 전환은 별도 승인.
- 운영 정본은 [agent-config 파일 수신 보관 안내](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/command-scoped-file-lifecycle.md)이며 ACK 후속 진단 문서를 별도 준비한다.

## 7. 변함없는 규칙

- Flow는 논리적이고 Tool 간 인계는 Gearbox Workflow 소유.
- 개인 인사·급여 원본은 공개 Git/테스트 영구 저장 금지; 실제 사용 전 합성자료로 테스트.
- 휴가 승인/상계/급여 확정·법률 최종 판단을 계산기로 자동 승인하지 않는다.
- PTO 상계는 외부 확정 지시가 있어도 발생근거와 미상계부족 두 시트가 모두 있어야 한다. 자동 API 구현 금지.
- 공개 샘플 Excel은 명시적 승인 없이 자동 갱신/덮어쓰기 금지.
- Git 브랜치 → 구현·unittest → PR → 서버 브랜치 직접 검증 → 사용자 병합 → 서버 main 갱신/정리. Draft/worktree/서버 push 요구 금지.
- Portfolio: /opt/agents/config/agent-config/.external/portfolio, 컨테이너: /opt/agent-config/.external/portfolio.
- 공통 uv Python: /opt/hermes/.venv/bin/python. 시스템 Python에 패키지 설치하지 않는다.
- Bhandara unittest 전체, Gearbox 기능(gearbox/_tests/run.py)과 인프라(gearbox/_tests/core_run.py)를 검증하고 **버전 변경 시 호환성 확인 필수**.
- AWS Parameter Store가 환경변수 정본. SSM 쓰기 권한 또는 S3 백업 읽기 IAM은 사전 사용자 승인 필요.

**다음 대화:** 신규 Payroll 설계가 최우선. Slack 파일 ACK 이후 후속 무응답·신규 Tool 운영 연결은 별도 병행 트랙.
