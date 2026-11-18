# Worktime — 독립 Tool / 세 Module 구성

> **Schedule / Attendance Verification / Worktime Compliance** 세 Module로 단순화했습니다. 별도 Attendance Detection을 만들지 않습니다. 원본 근태·출입기록을 승인된 근로시간·수당으로 자동 확정하지 않습니다.

## 책임과 흐름

| Module | 책임 | 하지 않는 일 |
|---|---|---|
| **Schedule** | 근무 예정일/휴무일과 근태장부 기록 존재 여부 대조 | 출퇴근 시각 차이·사유 판정 |
| **Attendance Verification** | 근태장부 ↔ 출입기 인증 대조. 스케줄 기준 출근·퇴근 시각의 **부호 있는 차이**와 외부 사유를 출처별로 보존 | 단순 출입을 실근로·승인된 조기출근·야근으로 간주 |
| **Worktime Compliance** | 확인된 실제 근로·휴게시간과 적용 정책을 대조. **실제 확인된 휴게−필수 휴게(분)** 차이 보존 | 확인되지 않은 휴게 추정, 법 위반·급여 승인 확정 |

- Module은 독립 계산 단위이고 Flow는 Tool 내부의 논리적인 사용 순서입니다. 물리적 `flow/` 디렉터리를 만들지 않습니다.
- 원본 출입기록은 업체별 `vendor_adapters/`에서 표준 `access-events.xlsx` v0.2로 변환합니다. 출력 시트 `Access Events`, `Attendance Candidates`, `Source Review`, `Metadata`는 업체와 무관하게 동일합니다.
- `Attendance Candidates`의 첫/마지막 출입은 항상 `confirmed=false`입니다. **근태장부와 서로 다른 증빙으로 보존**합니다.
- 시차출퇴근·추가근무 등 **사유는 외부 입력을 그대로 보존**합니다. 기록의 방향(더 일찍/늦게)은 계산 가능하지만 승인된 근로 유형은 자동 확정하지 않습니다.
- 근무 스케줄과 근태장부의 공통 정본 이행, 보고서 Excel, Tool CLI, Gearbox/Slack 연결과 Worktime Closing은 후속 작업으로 보류합니다.
- 기존 `worktime-calculator`는 그대로 유지하며 신 Tool 경로를 검증한 이후에 전환합니다. PTO·Payroll의 별도 입력/계산 계약은 건드리지 않습니다.

## 상세 계약

- [Schedule](schedule/README.md)
- [Attendance Verification](attendance-verification/README.md)
- [Worktime Compliance](worktime-compliance/README.md)
- [업체 공통 출입기 Excel 계약](ACCESS-EXCEL-CONTRACT.md)
- [CAPS·세콤·KT텔레캅 어댑터](vendor_adapters/README.md)

## 입력 참조

현재 `bhandara/common/io/input_layout.py`에서 공통 입력은 `common/employee.xlsx`, `common/id-map.xlsx`입니다. 현재 Worktime 스케줄 입력은 `worktime/work-schedule.xlsx`이고, 공통 스케줄 단일 정본 전환은 근무제 배정·임시변경·분할근무 계약을 확인한 후 진행합니다.
