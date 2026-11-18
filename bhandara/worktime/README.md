# Worktime — 신규 Tool 구조 (설계·독립 계산 단계)

> 목표 Module 이름은 **Schedule / Attendance Verification / Worktime Compliance / Attendance Detection**으로 확정합니다. **Schedule**, **Attendance Verification**, **Worktime Compliance**, **Attendance Detection** 네 Module의 독립 순수 계산 경로가 구현되어 있습니다. 현재의 `worktime-calculator` 및 Gearbox/Slack 연결은 변경하지 않습니다.

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

현재 단계는 기존 파일 경로 전환 없이 `schedule/calculation.py`, `attendance-verification/calculation.py`, `worktime-compliance/calculation.py`, `attendance-detection/calculation.py`의 독립 순수 계산 경로를 제공합니다. 업체별 변환 결과 Excel은 Tool 내부 `access_source.py`의 표준 규격으로 읽고 씁니다. 실제 Excel 입출력, 공개 Tool CLI, Gearbox/Slack 연결, 구형 코드 제거는 후속 단계입니다.

## Attendance Verification v0.1

장부의 출퇴근 시각과 정규화된 출입 인증 이벤트를 대조합니다. 출입기 업체의 원본 코드·인증 방법을 추측하지 않고 `auth_status=SUCCESS` 및 명시적으로 허용된 `auth_method`만 출퇴근 인증 근거로 사용합니다. 일반 출입은 미확정 후보로만 보존합니다. [상세 계약](attendance-verification/README.md)을 참고하세요.

## Worktime Compliance v0.1

휴게의 법정 최소 충족 여부, 회사 예정 휴게시간 초과, 일/주 기준 근로시간 초과 후보를 외부 검증된 분 단위 증빙으로 검토합니다. 실제 근무·휴게 근거가 없으면 법 위반으로 단정하지 않습니다. 비표준 근로시간제와 주간 범위 불완전 자료도 별도 검토 대상으로 남깁니다. [상세 계약](worktime-compliance/README.md).

## Attendance Detection v0.1

스케줄과 신고 근태장부로 지각·조퇴·근태누락·근무시간 외 **체류 후보**를 찾고, 외부에서 별도로 검증한 `verified_work_intervals`가 있을 때만 연장·야간·휴무·휴일 **실근로 후보**를 별도 산출합니다. 원본 출입기에서 추정된 첫·마지막 이벤트는 미확정 근거로만 보존하며 근로시간으로 자동 승격하지 않습니다. 업체 공통 Excel v0.2의 `Attendance Candidates`를 `detect_attendance_xlsx()`에서 받을 수 있습니다. 기본 규칙은 Tool의 `user_settings.py`에서 수정할 수 있습니다.

[상세 계약](attendance-detection/README.md).

## 업체별 Excel 정규화 계약

CAPS·세콤·KT텔레캅 등 어떤 업체에서 추출해도 **Access Events / Attendance Candidates / Source Review / Metadata** 4개 시트와 열·enum이 동일한 표준 v0.2 `access-events.xlsx`를 사용합니다. 원본 초 단위 시각은 `event_timestamp`에 보존하고, 첫/마지막 유효 일반 출입은 `Attendance Candidates`에서 미확정 후보로 제공합니다. 표준 Writer/Reader는 [access_source.py](access_source.py)에 있고 [계약 문서](ACCESS-EXCEL-CONTRACT.md)를 따릅니다. 실제 업로드한 세 업체의 관찰된 헤더를 대상으로 한 어댑터는 [vendor_adapters](vendor_adapters/)에 있으며, 다른 원본 버전·코드표는 별도 검증이 필요합니다.
