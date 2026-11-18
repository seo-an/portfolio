# Schedule — 근무 스케줄과 근태장부의 차이·사유 대조 (계산 계약 0.2)

## 책임 경계

`reconcile_schedule(schedule_rows, attendance_rows, *, period_from, period_to)`는 두 자료에 **어떤 차이가 있는지**만 판단하는 독립 순수 함수입니다. 출근·퇴근·휴게 기록의 일치 여부뿐 아니라 **기록값 − 예정값의 부호 있는 차이(분)**와 사유를 보존하며, 존재·누락·중복도 대조합니다. 이는 시각·기재값의 비교일 뿐 근로시간 합산이 아닙니다.  **지각·결근·승인 연장근로·법 위반 판정은 하지 않습니다.** 실제 출입기 인증 검증도 수행하지 않습니다.

## 입력

- 공통 대상: `employee_id`, `work_date` (정규 `YYYY-MM-DD`), 선택 `source_ref`, `_row_number` (증빙 위치).
- Schedule: `day_type`(`WORK`, `OFF`, `HOLIDAY`), `scheduled_start`, `scheduled_end`(분 단위 `HH:MM`, 휴무라면 둘 다 공란 가능), `break_min`(0 이상 정수 분, 미확인이면 공란).
- Attendance ledger: `clock_in`, `clock_out`(분 단위 `HH:MM`), `break_min`(0 이상 정수 분, 미확인이면 공란). 추가 사유는 선택적 텍스트 열 `clock_in_reason`, `clock_out_reason`, `break_reason`로 **외부에서 제공된 값만 전달**합니다.
- 기간: `period_from`, `period_to` (정규 `YYYY-MM-DD`, 시작일 ≤ 종료일).
- 한 직원·날짜의 근무 구간이 복수인 경우 현재는 중복 검토 대상으로 남깁니다. 근무 구간(`shift_id`) 규약을 정하기 전 자동 병합하지 않습니다.
- 원본 출입기·승인 자료는 여기서 대신 생성하지 않습니다. 승인된 외부 예외가 있더라도 무단으로 두 자료의 값이 같다고 바꾸지 않습니다.

## 출력

```json
{
  "schema_version": "0.1",
  "module": "schedule",
  "status": "REVIEW_REQUIRED",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "rows": [
    {
      "employee_id": "E001",
      "work_date": "2026-11-16",
      "status": "RECORD_DIFFERENT",
      "planned": {"day_type": "WORK", "scheduled_start": "09:00", "scheduled_end": "18:00", "break_min": "60"},
      "recorded": {"clock_in": "09:17", "clock_out": "18:00", "break_min": "60"},
      "different_fields": ["clock_in"],
      "comparisons": {
        "clock_in": {"expected": "09:00", "recorded": "09:17", "delta_minutes": 17, "reason": null},
        "clock_out": {"expected": "18:00", "recorded": "18:00", "delta_minutes": 0, "reason": null},
        "break_min": {"expected": "60", "recorded": "60", "delta_minutes": 0, "reason": null}
      },
      "review_codes": [],
      "schedule_sources": [{"source_ref": "synthetic-schedule", "row_number": 2}],
      "attendance_sources": [{"source_ref": "synthetic-ledger", "row_number": 2}]
    }
  ],
  "source_issues": [],
  "approved": false,
  "notice": "대조 결과만 제공하며 지각·연장근무·휴무·휴가·근태 승인 여부를 확정하지 않습니다."
}
```

### 차이·사유 계약

- `comparisons.clock_in`, `comparisons.clock_out`, `comparisons.break_min` 세 항목이 모든 직원·일자의 결과에 포함됩니다. 각 항목은 `expected`(예정), `recorded`(기록), `delta_minutes`(기록−예정), `reason`(외부에서 입력된 사유)을 포함합니다.
- **09:00 예정 → 08:40 기록이면 `-20`**, **18:00 예정 → 18:16 기록이면 `+16`**. 차이의 부호는 출퇴근 각각 독립적입니다. 두 차이를 더해 연장근로·급여를 산출하지 않습니다.
- 휴게시간 예를 들어 60분 예정 → 75분 기록이면 `+15`이고, 60분 예정 → 45분 기록이면 `-15`입니다. 법정 휴게 위반 여부는 Worktime Compliance가 판단합니다.
- 예정·기록 중 하나가 없으면 `delta_minutes=null`. **모르는 휴게시간은 0으로 보정하지 않습니다.**
- 사유를 전달하지 않으면 `reason=null`; 문자열 외의 잘못된 자료는 `REVIEW_REQUIRED`로 남깁니다. 사유가 있더라도 정합 상태가 저절로 `WORK_MATCH`가 되지는 않습니다. 사유와 승인·인정 여부는 서로 다른 개념입니다.
- `HH:MM`만으로 계산한 시각 차이가 **12시간 이상**이면 자정을 지났는지 알 수 없으므로 `TIME_DELTA_DATE_AMBIGUOUS`로 검토하고 차이는 `null`로 남깁니다. 이 버전은 근무일에 연결된 날짜시각이 없는 심야 기록의 부호를 임의 추측하지 않습니다.
- 기존 `planned`, `recorded`, `different_fields`, 상태명, 원본 출처 필드는 호환성을 위해 유지합니다. `comparisons`만 추가합니다.

### 직원·근무일별 상태

| 상태 | 의미 |
|---|---|
| `WORK_MATCH` | 양측 시간·휴게 **기재값** 일치 (출입 인증이나 승인 확정은 아님) |
| `RECORD_DIFFERENT` | 양측 값이 달라 차이 필드 표시 (지각 판정 아님) |
| `MISSING` | 계획 근무에 대해 근태장부 기록이 없음 (결근 판정 아님) |
| `UNSCHEDULED` | 계획 없이 근태장부 기록이 있음 (휴일근로 승인 아님) |
| `NON_WORK_MATCH` | 예정 시간이 없는 OFF/HOLIDAY와 근태장부 기록 없음 (대조 대상으로만 정상) |
| `REVIEW_REQUIRED` | 중복·불완전·유효하지 않은 행. 해당 직원/일의 자동 일치 판정 금지 |

자료의 날짜/직원 키가 유효하지 않거나 기간 밖이면 `source_issues`에 기록하고 해당 행만 대조에서 제외합니다. 전체의 `status`는 `PASS` 또는 `REVIEW_REQUIRED`이며, 빈 입력은 검증 성공으로 취급하지 않습니다.

### 전체 실행 상태와 휴가 구분

- `PASS`: 전달된 대조 대상의 직원·날짜별 상태가 전부 `WORK_MATCH` 또는 `NON_WORK_MATCH`이고, 원본 검토 이슈가 없는 경우입니다. **기간 전체의 근태 완료·승인 또는 출입기 인증을 의미하지 않습니다.**
- `REVIEW_REQUIRED`: 불일치·누락·미예정 기록·중복 또는 잘못된 입력 등 추가 확인이 필요한 경우입니다.
- `NON_WORK_MATCH`는 예정된 `OFF`/`HOLIDAY`에서 근무 기록이 없다는 사실만 뜻합니다. **휴가 사용 여부는 확정하지 않습니다.**
- `LEAVE_MATCH`는 향후 외부에서 확정된 휴가 근거와 연결하는 계약이 합의될 때 검토할 **예약 명칭**으로, 이번 버전에서는 반환하지 않습니다.

## 계산하지 않는 것과 남은 계약

- 현재 **보고된 근태장부**와 스케줄만 비교합니다. 근태장부가 실제 출입과 부합하는지는 Attendance Verification 책임입니다.
- 야간·익일 종료 근무는 날짜가 명시되지 않은 `HH:MM` 계약의 한계가 있습니다. 시간 비교는 유지하지만 **날짜가 모호한 시각 차이는 계산하지 않습니다.** 익일 근로시간·법적 근로시간 구분은 수행하지 않습니다.
- 복수 교대/분할 근무, 계획 변경 이력 및 외부 확정 휴가·휴무 증빙의 연결 규약은 별도 계약으로 남깁니다.
- 전체 기간의 스케줄 자체가 완전한지 검증하려면 **대상자·대상일 목록**이 별도로 필요합니다. 현재 구현은 *두 입력 중 하나에 존재하는 직원·날짜*만 대조합니다. 양쪽에 모두 누락된 날짜를 정상이라고 주장하지 않습니다.
- 이 Module 자체의 별도 Excel 읽기/쓰기, `worktime-calculator` 호환 실행, 다른 Tool 및 Slack 연결은 제공하지 않습니다.

## 독립 검증

```bash
python3 -m unittest bhandara.tests.test_worktime_schedule -v
```

실제 직원 자료가 아닌 합성 입력을 사용합니다. 서버에서 기능 변경 적용 전에는 해당 브랜치 직접 테스트 및 Gearbox 기능·인프라 호환성 확인이 필요합니다.
