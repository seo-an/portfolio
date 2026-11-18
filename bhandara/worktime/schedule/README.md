# Schedule — 근무 예정일과 근태기록 존재 여부 대조 (v0.2)

## 역할

`reconcile_schedule(schedule_rows, attendance_rows, *, period_from, period_to)`는 직원·날짜별 **근무 예정 여부와 근태장부 기록 존재 여부**만 비교합니다. 계획된 출근·퇴근 시각이 실제 시각과 일치하는지는 여기서 계산하지 않습니다. 시간 차이와 사유는 **Attendance Verification**, 확인된 휴게시간 차이는 **Worktime Compliance**가 담당합니다.

## 입력

- `schedule_rows`: `employee_id`, `work_date`, `day_type`(`WORK/OFF/HOLIDAY`), 선택 `scheduled_start`, `scheduled_end`, `break_min`, `source_ref`, `_row_number`.
- `attendance_rows`: `employee_id`, `work_date`, `clock_in`, `clock_out`, `break_min`, 선택 출처.
- `period_from`, `period_to`: `YYYY-MM-DD`.
- 동일 직원·날짜에 계획 또는 근태자료가 중복되면 자동으로 하나를 선택하지 않습니다.
- 휴일이어도 **명시적으로 예정된 근무 시각이 있다면 근무 예정일**로 취급합니다.
- 스케줄이 양쪽에 모두 없는 날짜까지 검사하려면 외부에서 대상 직원·날짜 목록이 제공되어야 합니다. 이 모듈은 누락된 전체 일정을 생성하지 않습니다.

## 직원·날짜별 상태

| 상태 | 의미 |
|---|---|
| `WORK_MATCH` | 해당 날짜는 근무 예정이며 근태장부 기록도 있음. **시각 일치·근로 수행이 확인됐다는 뜻이 아님** |
| `NON_WORK_MATCH` | 휴무/휴일이며 별도 근무 예정이 없고 근태장부 기록도 없음 |
| `MISSING` | 근무 예정일이지만 근태장부 기록이 없음. **결근 확정 아님** |
| `UNSCHEDULED` | 근무 예정이 없거나 스케줄이 없는 날짜에 근태장부 기록이 존재 |
| `REVIEW_REQUIRED` | 원본 중복·시간 형식 오류·불완전한 기록 등 |

전체 실행 상태는 모두 `WORK_MATCH/NON_WORK_MATCH`이고 원본 검토 이슈가 없을 때 `PASS`, 그 외 `REVIEW_REQUIRED`입니다. 이는 근태 승인이나 기간 전체의 완전성 확인이 아닙니다.

기존 `planned`, `recorded`, `different_fields`, `review_codes`, 원본 출처는 호환을 위해 보존합니다. `different_fields`는 v0.2에서 빈 목록이며, 기존 `RECORD_DIFFERENT`는 **더 이상 반환하지 않습니다**. 모든 시각 차이와 사유는 Attendance Verification에서 계산합니다.

## 예시

09:00 출근 예정이고 08:40 출근했다고 신고했더라도 해당 날짜에 근태장부가 있으면 `WORK_MATCH`입니다. 이때 `-20분`은 Schedule이 아니라 Attendance Verification의 `time_deviations.clock_in`에 기록됩니다.

휴무인데 출입기 기록만 있고 **근태장부가 없다면**, Schedule은 `NON_WORK_MATCH`를 유지합니다. 출입기만으로 근태장부를 자동 생성하거나 휴일근무로 판정하지 않습니다. 출입 증빙은 Attendance Verification이 별도로 검토합니다.

```bash
python3 -m unittest bhandara.tests.test_worktime_schedule -v
```

기존 Excel 입출력·공개 CLI·Gearbox 연동은 이 PR에서 바꾸지 않습니다.
