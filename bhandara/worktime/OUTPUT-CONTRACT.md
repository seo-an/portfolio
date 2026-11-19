# Worktime 단일 결과 Output v0.1 — 사실 자료 계약

> Worktime의 결과물은 **직원·일자별 스케줄과 확인된 시간 사실**이다. 급여 반영시간, 임금, 연장수당, 공제, 유급휴가 시간의 결합 계산, 승인 상태를 산출하지 않는다.

## 파일 및 데이터 책임

- 사람이 검토하는 자료와 Payroll 인계자료를 서로 따로 계산하지 않는다.
- 정규화된 한 행을 `worktime-result.xlsx`의 `WORKTIME` 한 시트에 기록한다.
- 출력 파일 Writer/Reader는 `bhandara/worktime/output_excel.py`에 있다.
- `build_worktime_result`는 Schedule 매핑 결과, Attendance Verification 결과, Worktime Compliance 결과, 외부 근태/휴가 사실을 **직원×근무일** 기준으로 조인한다.
- 독립 Module의 기존 `status`, `review_codes`는 그대로 유지하지만 **최종 결과 표에는 상태·판정 컬럼을 넣지 않는다.**

## 정확한 열(열 순서 고정)

| 열 | 값 | 계산/입력 원칙 |
|---|---|---|
| employee_id | 직원 ID | Common 식별자 |
| work_date | YYYY-MM-DD | 근무 귀속일 |
| schedule_id | 개별 스케줄 ID 또는 공란 | `SCHEDULE MAP` 참조 |
| scheduled_min | 0 이상 정수 또는 공란 | 스케줄의 소정근로분, 명시적 비근무일은 0 |
| actual_min | 0 이상 정수 또는 공란 | 외부에서 **검증된** 실제 근로분만 사용 |
| clock_in_delta_min | 부호 있는 분 또는 공란 | 예정 출근 − 장부 출근 |
| clock_out_delta_min | 부호 있는 분 또는 공란 | 장부 퇴근 − 예정 퇴근 |
| attendance_type | 문자열 또는 공란 | **외부 확정 근태 사실**을 그대로 전달 |
| leave_type | 문자열 또는 공란 | **외부 확정** 유급/무급 등 구분 |
| leave_request_id | 문자열 또는 공란 | 휴가 원신청 내용 참조 |

분 단위를 사용하며 진짜 0과 미확정 공란(`null`)을 구별한다. 유급·무급 휴가시간은 원신청 ID로 조회하므로 이 표에 중복 보관하지 않는다.

### 부호 규칙

| 상황 | clock_in_delta_min | clock_out_delta_min |
|---|---:|---:|
| 조기출근 20분·지연퇴근 13분 | +20 | +13 |
| 지각 15분·조기퇴근 30분 | -15 | -30 |
| 예정과 일치 | 0 | 0 |

Attendance Verification **내부**의 부호는 종전 계약(`장부−예정`)을 유지한다. **최종 Output 생성 시에만 출근 부호를 뒤집는다.** 이는 단순 시각 차이이고 승인된 근로시간이 아니다. `actual_min`에 그 시간이 이미 포함되었는지 여부를 고려한 급여 반영은 Payroll이 수행한다.

### 근태·휴가와 실제 근로

가상 사례: 소정 480분, 유급반차 신청 `LV001`, 검증된 실제 300분. 결과에는 소정 480, 실제 300, 외부 휴가구분 `PAID`, 신청 ID `LV001`만 남긴다. **300+휴가 240−480=60** 같은 계산은 Worktime에서 하지 않는다. Payroll이 휴가 신청 원장, 지급 규칙, 근로시간 겹침을 검토해 계산한다.

무단결근, 미승인 휴가, 기록 누락은 Worktime에서 시각 차이로 추정하여 생성하지 않는다. 외부 근태 원장에서 제공한 사실만 `attendance_type`에 기록한다.

## 누락·경계 조건

- 확인되지 않은 실제 근로시간: `actual_min=null`, 결근·0시간으로 추정 금지.
- 명시적 휴무일: `scheduled_min=0`; 미배정일: `scheduled_min=null`.
- 일반 `ACCESS` 첫/마지막 시각: 장부 출퇴근값 대신 사용하지 않음.
- 익일 퇴근: Attendance Verification에서 명시적 날짜를 가진 예정/기록만 비교.
- 동일 직원·날짜의 중복 입력: 출력 거부. 임의 선택·합산 금지.
- 분할근무·복수 휴가 신청 같은 **다중 구간**은 v0.1 단일 행 계약 밖이다. 자료 손실 없는 확장 계약을 후속 설계한다.
- 결과의 시간 변화량과 `actual_min`을 합산·차감하는 판단은 Payroll의 첫 단계에서만 수행한다.

## 현행 구현 범위

현재 코드는 새 Schedule 매핑 Reader와 **순수 출력 조인, Excel Writer/Reader**를 제공한다. JSON 기반 선택적 Flow/Tool CLI는 구현하였으나 Gearbox 자동 인계, 실제 회사 자료 결재·사용은 연결하지 않는다. 기존 `worktime-calculator` 및 `payroll-calculator`를 전환하지 않는다. 출력 Excel은 구조화된 독립 인계 파일이며 **구형 Payroll JSON과 동일한 스키마라고 주장하지 않는다.**

테스트: `python -m unittest bhandara.tests.test_worktime_schedule_mapping bhandara.tests.test_worktime_output_v01 -v`.

추가 상세: [스케줄 ID 계약](SCHEDULE-MAP-CONTRACT.md), [Worktime 기존 책임](README.md).

선택적 JSON CLI 설정과 실제 Excel 입력 열은 [TOOL-CLI.md](TOOL-CLI.md)에 정의합니다. 최종 WORKTIME 한 시트 계약은 그대로 유지합니다.
