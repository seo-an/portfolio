# Worktime 스케줄 ID 매핑 계약 (신규 Tool v0.1)

> 설계 원칙: 실제 근무 일정은 날짜별 **배정**으로, 출퇴근 시간표는 ID별 **정의**로 관리한다. 급여 산정과 근태 상태 판정은 이 매핑의 책임이 아니다.

## 파일 구조

입력은 기존 `worktime/work-schedule.xlsx` 한 파일이다. **구형 첫 시트를 변경하지 않고**, 아래 두 시트를 추가한다. 이전 `worktime-calculator`는 기존 입력을 계속 읽는다. 현재 공개 샘플 Excel에는 새 시트가 없을 수 있으며 **자동 갱신하지 않는다**.

### `SCHEDULE MAP` — 고유 시간표 정의

| 컬럼 | 필수 | 의미 | 예 |
|---|---|---|---|
| schedule_id | O | 변경 불가능한 시간표 식별자 | DAY_A |
| schedule_type | O | 교대/시간대 구분. 근로시간제 `worktime_system`과 별개 | DAY, NIGHT, SHIFT |
| scheduled_start | O | 예정 시작 HH:MM | 09:00 |
| scheduled_end | O | 예정 종료 HH:MM | 18:00 |
| end_day_offset | O | 종료일의 일자 이동(0 또는 1) | 0 |
| break_min | O | 예정 휴게분 | 60 |
| scheduled_min | O | 하루 소정근로분 | 480 |
| valid_from | 열 필수·값 선택 | 해당 ID 사용 시작일 | 2026-01-01 |
| valid_to | 열 필수·값 선택 | 해당 ID 사용 종료일 | 2026-12-31 |

동일한 `schedule_id`를 두 번 정의하지 않는다. 같은 이름의 근무표라도 시간이 변경되면 **새 ID**를 발급한다. 유효기간이 있으면 배정일과 일치해야 한다. 시각·휴게·소정분은 음수일 수 없으며 계획된 시각의 구간 길이를 넘어설 수 없다. 일정 구간 길이와 소정분이 정확히 같아야 하는 것은 아니다.

야간 예시: NIGHT_A / 21:00 / 06:00 / end_day_offset=1 / 휴게 60 / 소정 480. 익일 종료는 사람용 문자 '익일' 대신 숫자 1로 보존한다.

### `ASSIGNMENTS` — 직원의 해당 일자 배정

| 컬럼 | 필수 | 의미 | 예 |
|---|---|---|---|
| employee_id | O | 공통 직원 식별자 | E001 |
| work_date | O | 근무 귀속 날짜 | 2026-11-03 |
| schedule_id | WORK일 필수 | `SCHEDULE MAP` 참조 | DAY_A |
| day_type | O | 근무 예정·비근무일 입력 사실 | WORK, OFF, HOLIDAY |

- 직원×날짜는 하나의 배정만 허용한다. 중복 발생 시 한 행을 임의로 선택하지 않는다.
- `WORK`에는 schedule_id가 필수이고, `OFF`에는 비워 둔다.
- `HOLIDAY`는 사전에 근무 예정이 있으면 schedule_id를 기입하고, 없으면 비운다.
- `OFF`처럼 명시적인 비근무 예정은 소정 0분이며, **배정 자체가 없는 날짜는 소정 0분이 아니라 미확인**이다.
- 분할 근무, 한 날짜에 둘 이상의 독립 근무 배정은 **현재 v0.1에서 지원하지 않는다.** 임의 합산하지 않고 후속 계약으로 다룬다.

## Reader 계약 및 모듈 연결

`bhandara/worktime/schedule/mapping.py`의 `read_schedule_mapping(path, period_from, period_to)`가 날짜별 Schedule 입력행을 반환한다. 이미 구현된 `reconcile_schedule`는 이 입력을 받아 스케줄과 장부 존재 여부를 검증한다.

`for_attendance_verification(rows)`는 야간 종료시각만 근무 익일의 명시적 ISO 시각으로 변환한다. 이는 Attendance Verification용 입력 표현이며 기존 Schedule 입력이나 실제 근로시간을 변경하지 않는다.

구형 `ID_MAP`과 이번 `SCHEDULE MAP`은 관계가 없다. ID 할당·관리, 새 시트의 검증은 새로운 Worktime만 수행한다.

## 변경 금지사항

- 기존 공개 샘플 Excel 자동 교체 금지.
- 출입기 미확정 후보를 근로시간으로 변환 금지.
- 스케줄 시간 차이로 지각/연장 승인 판정 금지.
- Payroll 관련 금액·수당·반영시간 계산 금지.
