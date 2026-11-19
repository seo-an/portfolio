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
- 신규 Worktime의 **스케줄 ID 매핑 Reader**, **단일 일자별 사실 Output Excel Writer/Reader**는 구현했습니다. JSON 기반 선택적 Flow/Tool CLI를 **PR #57에서 구현·테스트·병합**했으며, Gearbox/Slack 운영 연동과 Worktime Closing은 후속 작업입니다.
- Output은 소정·실제·출근 변화량·퇴근 변화량 네 시간 컬럼과 스케줄 ID·외부 근태/휴가 참조만 보존하며, 상태·급여 반영시간·수당 판정 컬럼을 만들지 않습니다.
- 기존 `worktime-calculator`는 그대로 유지하며 신 Tool 경로를 검증한 이후에 전환합니다. PTO·Payroll의 별도 입력/계산 계약은 건드리지 않습니다.

## 상세 계약

- [Schedule](schedule/README.md)
- [스케줄 ID 매핑 계약](SCHEDULE-MAP-CONTRACT.md)
- [Worktime 최종 결과 10컬럼 계약](OUTPUT-CONTRACT.md)
- [Attendance Verification](attendance-verification/README.md)
- [Worktime Compliance](worktime-compliance/README.md)
- [업체 공통 출입기 Excel 계약](ACCESS-EXCEL-CONTRACT.md)
- [CAPS·세콤·KT텔레캅 어댑터](vendor_adapters/README.md)
- [현재 실행·검증 실행서](RUNBOOK.md)
- [JSON 기반 선택적 Tool CLI](TOOL-CLI.md)

## 입력 참조

신규 보안업체 원본 정규화는 `common/id-map.xlsx`의 `PERSON MAP`, `DEPARTMENT MAP`, `AREA MAP`에서 **선택 업체(`security_id`) 행**을 가져옵니다. 같은 직원이 복수 업체에 등록되어 있으면 행이 반복될 수 있습니다. 추가 업체 전용 열은 읽지 않습니다. 자세한 사항은 [Common 보안업체 매핑 계약](../common/SECURITY-PERSON-MAP.md)에 있습니다.

구형 `ID_MAP`의 `read_id_map()` 계약은 유지하므로 구형 계산기 운영 경로를 변경하지 않습니다.

현재 `bhandara/common/io/input_layout.py`에서 공통 입력은 `common/employee.xlsx`, `common/id-map.xlsx`입니다. 현재 Worktime 스케줄 입력은 `worktime/work-schedule.xlsx`입니다. 신규 Tool의 `SCHEDULE MAP` + `ASSIGNMENTS` 시트를 읽는 경로가 추가되었으며, **구형 첫 시트는 그대로 둡니다.** 독립 CLI는 구현되었으나 실제 회사 자료 E2E·운영 연결 및 분할근무/다중 휴가 범위 확장은 후속 과제입니다.
