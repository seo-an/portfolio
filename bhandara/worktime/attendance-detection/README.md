# Attendance Detection — 근태 이벤트 후보 탐지 (v0.1)

> **스케줄·근태장부·장치 출입 후보·검증된 실근로 구간을 구분하는 독립 계산 Module**입니다. 출입기 기록이나 근태장부 시각이 실근로 확정값 또는 승인된 근무시간이라는 가정은 절대 하지 않습니다.

## 다른 Worktime Module과 구분

- **Schedule**: 스케줄과 신고 근태장부의 기록 일치 여부만 대조.
- **Attendance Verification**: 근태장부와 출입기 인증 원본의 증빙 대조.
- **Worktime Compliance**: 확인된 근로·휴게시간을 적용 규정에 대조하고 적합성 검토.
- **Attendance Detection**: 지각·조퇴·근태누락·추가 체류·확인된 연장·야간·휴일근로의 **검토 후보**를 탐지.

`closing`, 연장근무 승인·급여 확정·법률 위반 판정은 이 Module의 책임이 아닙니다.

## 처리 방식

독립 함수:

```python
from importlib import import_module

detector = import_module("bhandara.worktime.attendance-detection")
report = detector.detect_attendance(
    schedule_rows, attendance_rows,
    period_from="2026-11-16",
    period_to="2026-11-22",
    candidate_rows=normalized_access_candidates,
    verified_work_intervals=external_verified_work_intervals,
)
```

### 1. Schedule 입력

`employee_id`, `work_date`, `day_type`(`WORK/OFF/HOLIDAY`), `scheduled_start`, `scheduled_end`, 선택 `worker_id`, `source_ref`, `_row_number`.

- 근무일(`WORK`)은 예정 시작과 종료가 필수입니다.
- 휴무·휴일(`OFF/HOLIDAY`)은 예정 시각이 비어 있어도 됩니다. 당일 근무 기록이 있다면 *휴무/휴일 체류 후보*로 분류하며 임금 지급 여부를 확정하지 않습니다.
- 시각은 `HH:MM`, `HH:MM:SS` 또는 `YYYY-MM-DDTHH:MM[:SS]`. 익일 종료 시각은 **날짜 포함**이 필수이며, 임의로 익일 퇴근을 추측하지 않습니다.
- 분할 스케줄이 같은 직원·날짜에 여러 행이면 **자동 병합하지 않고** `DUPLICATE_SCHEDULE`로 검토합니다.

### 2. Attendance ledger 입력

`employee_id`, `work_date`, `clock_in`, `clock_out`, 선택 `worker_id`, 출처 필드.

장부 출퇴근 시각으로 **지각/조퇴 또는 예정 외 체류 후보**를 찾을 수 있지만, 장부 구간 전체가 실제 근무한 시간이라고 판단하지 않습니다. 따라서 결과 코드에 `REPORTED`/`PRESENCE`가 붙습니다.

### 3. Device candidate 입력 (선택)

업체 공통 `access-events.xlsx` v0.2의 `Attendance Candidates` 시트와 같은 구조의 행을 받습니다.

`employee_id`, `worker_id`, `work_date`, `arrival_time`, `departure_time`, `arrival_basis`, `departure_basis`, `candidate_status`, **`confirmed=false`**, `evidence_event_ids`.

- 미확정 첫 출입·마지막 출입은 **근무 시작·끝이나 승인 근로시간으로 사용하지 않습니다.**
- 장부가 없으면 `MISSING_ATTENDANCE_RECORD`를 유지하면서 `DEVICE_PRESENCE_UNCONFIRMED`를 별도 표시합니다. 출입기 자료만으로 자동으로 출퇴근 장부를 생성하거나 결근을 취소하지 않습니다.
- `worker_id`가 다른 데이터 원본과 불일치하면 해당 직원·날짜 검토 대상으로 남깁니다.

### 4. Verified work intervals (선택)

실제 작업이 별도 절차에서 확인된 구간만 전달합니다.

| 필드 | 요구 사항 |
|---|---|
| `employee_id`, `work_date` | 직원과 시작 기준 근무일 |
| `start`, `end` | 작업 구간 시각 (익일 종료 시 날짜 명시) |
| `verified` | **반드시 `true`**. 출입기 추정이나 근태장부만으로 생성 금지 |
| `evidence_ref` | 실제 작업을 확인한 독립 증빙 참조 필수 |
| `worker_id`, `source_ref`, `_row_number` | 있으면 신원 및 출처 추적에 활용 |

중복·겹치는 구간, 증빙 미확인, 잘못된 시각은 해당 일자 `REVIEW_REQUIRED`이며 **작업 시간 자동 합산을 중지**합니다. 검증된 작업은 출입장부 구간 바깥에서 발생할 수 있으므로, 외근·원격근무 증빙을 임의로 버리지 않습니다.

## 탐지 코드

| 코드 | 계산 근거 | 의미 |
|---|---|---|
| `LATE_ARRIVAL_REPORTED_CANDIDATE` | 장부 ↔ 예정 시작 | 지각 신고 후보 |
| `EARLY_LEAVE_REPORTED_CANDIDATE` | 장부 ↔ 예정 종료 | 조퇴 신고 후보 |
| `MISSING_ATTENDANCE_RECORD` | 예정 근무 있음, 장부 없음 | **장부 누락** (결근 확정 아님) |
| `PRE_SHIFT_PRESENCE_CANDIDATE` | 장부 | 시작 전 체류 |
| `POST_SHIFT_PRESENCE_CANDIDATE` | 장부 | 종료 후 체류 |
| `NIGHT_PRESENCE_CANDIDATE` | 장부 | 야간 시간대의 신고 체류 |
| `REST_DAY_PRESENCE_CANDIDATE`, `HOLIDAY_PRESENCE_CANDIDATE` | 장부 | 휴무/휴일에 신고된 체류 |
| `UNSCHEDULED_PRESENCE_CANDIDATE` | 장부 | 스케줄 없는 신고 체류 |
| `DEVICE_PRESENCE_UNCONFIRMED` | 출입기 후보 | 출입 기록만 있는 미확정 후보 |
| `EXTENDED_WORK_CANDIDATE` | **증빙 확인된 작업 구간** | 예정 구간 바깥 실제 근로 후보(연장근로 승인 아님) |
| `NIGHT_WORK_CANDIDATE` | **증빙 확인된 작업 구간** | 야간 작업 후보 |
| `REST_DAY_WORK_CANDIDATE`, `HOLIDAY_WORK_CANDIDATE` | **증빙 확인된 작업 구간** | 휴무/휴일 작업 후보 |
| `UNSCHEDULED_WORK_CANDIDATE` | **증빙 확인된 작업 구간** | 예정되지 않은 작업 후보 |

`duration_seconds`는 정확한 시각 차를 초 단위로 표현합니다. 원본의 초를 임의로 반올림하지 않습니다. 예정 시간 밖의 체류시간과 실제 작업시간은 **서로 다른 코드**이며, 급여·연장근로수당의 승인 시간이 아닙니다.

행 결과 `NO_FINDINGS/CANDIDATES_FOUND/REVIEW_REQUIRED` 및 전체 실행 결과 `PASS/REVIEW_REQUIRED`를 반환합니다. `PASS`는 **제공된 입력 범위에서 후보가 없다는 뜻**일 뿐 실제 근무 완료·근태 승인·원본 수집 완전성 검증을 의미하지 않습니다. `approved=false`, `verified_work_hours=false`, `payroll_finalizable=false`가 항상 유지됩니다.

## Tool 기본 설정

`bhandara/worktime/user_settings.py`의 `ATTENDANCE_DETECTION_DEFAULTS`:

```python
ATTENDANCE_DETECTION_DEFAULTS = {
    "late_grace_min": 0,
    "early_leave_grace_min": 0,
    "outside_schedule_grace_min": 0,
    "night_start": "22:00",
    "night_end": "06:00",
}
```

호출 시 `policy={...}` 매핑으로 개별 값만 재정의할 수 있습니다. 임의의 누락 정책이나 적용 시간제를 이 Module이 추론하지 않습니다. 위는 **기본 탐지 창**이며 근로시간제의 법적 적용 및 수당 가산 정책을 자동 확정하는 값이 아닙니다.

## 업체별 표준 Excel에서 곧바로 실행

```python
report = detector.detect_attendance_xlsx(
    schedule_rows, attendance_rows,
    "/private/output/access-events.xlsx",
    period_from="2026-11-16",
    period_to="2026-11-22",
)
```

- `Access Events` 원본을 직접 근로시간으로 계산하지 않고 `Attendance Candidates`만 미확정 자료로 받습니다.
- `Source Review`의 `UNMAPPED/REJECTED/REVIEW_REQUIRED` 행이 있으면 전체 결과도 검토 대상으로 남깁니다. 경비설정·인식실패처럼 올바르게 `EXCLUDED`된 기록은 정상 제외로 집계합니다.
- 업체 이름에 의존하지 않으므로 CAPS/세콤/KT텔레캅 등 모두 같은 입력 인터페이스로 처리할 수 있습니다.

## 보류 계약

- 승인 연차·대휴·외근·일정 변경을 자동으로 정상 처리하는 규칙과 법정 휴일의 달력 날짜 판정은 외부 정책·확정 자료 연동 시 결정합니다.
- `work_date`는 근무 시작 기준입니다. 익일이 별도 휴일인 경우 휴일에 해당하는 부분을 나누는 판정은 달력·적용 정책 추가 후 처리합니다.
- 동일일 다중 스케줄 및 근무형태별 연장근로 인정 기준은 외부에서 확정해야 합니다.
- 실제 Excel 결과 보고서, 공개 Tool CLI, Gearbox/Slack, Payroll 연결, 구형 Worktime 제거 및 Closing은 후속 단계입니다.

## 합성 테스트

```bash
python3 -m unittest bhandara.tests.test_worktime_attendance_detection -v
```
