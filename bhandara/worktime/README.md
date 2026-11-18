# Worktime — 신규 Tool 구조 (설계·독립 계산 단계)

> 목표 Module 이름은 **Schedule / Attendance Verification / Worktime Compliance / Attendance Detection**으로 확정합니다. 아직 **Schedule**의 순수 계산 경로만 구현되었고 나머지는 설계 대상입니다. 현재의 `worktime-calculator` 및 Gearbox/Slack 연결은 변경하지 않습니다.

## 계층 및 책임

| Module | 계산 책임 | 하지 않는 일 |
|---|---|---|
| Schedule | 공통 근무 스케줄과 신고된 근태장부의 날짜·시간·휴게 기록 대조 | 지각/연장근로 판정, 출입 인증 신뢰성 판정, 휴가 승인 |
| Attendance Verification | 지문·출입 기록과 신고된 근태장부의 증빙 대조 | 출입 사실을 근로 시작/종료로 자동 확정 |
| Worktime Compliance | 휴게·근로시간 준수 여부와 판단 근거 검토 | 근로시간제 예외·휴게 사실을 임의 승인, 수당 계산 |
| Attendance Detection | 지각·조퇴·연장·야간·휴일근무 후보 탐지 | 급여 확정/수당 지급 승인 |

- Module은 독립 계산 단위, Flow는 Tool 내부 선택적 계산 순서로서 논리적 개념입니다. `flow/` 폴더를 만들지 않습니다.
- Tool `worktime`은 네 Module의 설정·입출력 소유자입니다. Tool 간 Workflow는 추후 Gearbox에서 담당합니다.
- 근태 원본과 출입기 원본은 분리하며, 이 Module들의 결과는 승인·근태 마감·급여 지급의 증거가 아닙니다.
- Worktime Closing은 **보류**합니다.

## 입력 정본 이행 시 주의사항

현재 저장소의 `bhandara/common/io/input_layout.py`에는 `common/employee.xlsx`, `common/id-map.xlsx`만 `common` 입력 역할로 등록돼 있고 Worktime 스케줄은 `worktime/work-schedule.xlsx`에 있습니다. 향후 공통 근무 스케줄을 단일 정본으로 만들되, **PTO에서 쓰는 별도 근태판정·근무제 배정 자료를 무작정 덮어쓰지 않습니다.** 공통 스케줄이 근로제 적용·임시 변경·분할 근무를 어떻게 표현할지 확인한 뒤 전환합니다.

현재 단계는 파일 경로 전환 없이 `schedule/calculation.py`의 순수 계산 인터페이스만 제공하는 단계입니다. 실제 Excel 입출력, 공개 Tool CLI, Gearbox/Slack 연결, 구형 코드 제거는 후속 단계입니다.
