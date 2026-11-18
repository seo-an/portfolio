# Worktime Compliance — 근로·휴게시간 기준 및 부호 있는 휴게 차이 검토 (0.2)

> **독립 순수 계산**입니다. 이 Module은 근태 승인, 연장근무 확정, 휴게 증빙 생성, 임금 산정, 법 위반 최종 판단 및 Closing을 수행하지 않습니다.

## 책임

1. **휴게시간 준수:** 실제 근로시간에 대한 법정 최소 휴게시간 후보를 비교합니다. 실제 휴게시간과 자유 사용·근무 도중 배치 근거가 있어야 합니다. 휴게가 부족해 보여도 전체 휴게 기록의 완전성이 확인되지 않으면 **부족 확정 금지**.
2. **회사 기준 휴게 초과:** 외부 근무표의 `planned_break_min`과 검증된 `rest_min`을 비교합니다. 허용 오차는 `break_overrun_tolerance_min`. **법정 최대 휴게시간이 있다는 의미가 아닙니다.**
3. **일별 근로시간:** 회사에서 확정한 근로시간제/적용 규칙에 따라 일별 8시간 등 표준 기준 초과 후보를 표시합니다. 지각·조퇴·연장근로 승인/시간 산정은 Attendance Detection 담당입니다.
4. **주간 근로시간:** 월요일~일요일 단위의 완결된 근태 자료를 외부에서 `weekly_coverage`로 확인해 준 경우에만 주간 합계를 기준에 대조합니다. 월초·월말에 걸친 불완전 주를 정상으로 판정하지 않습니다.

`worktime_system=standard`와 `actor_type=EMPLOYEE`, 정책 참조가 일치할 때만 표준 적용 규칙으로 검토합니다. 탄력·선택근로제·외부 용역 인력 등은 임의로 표준 법령 적용 대상으로 만들지 않고 `REVIEW_REQUIRED`로 남깁니다.

## 직접 실행 함수

```python
from importlib import import_module

module = import_module("bhandara.worktime.worktime-compliance")
report = module.review_worktime_compliance(
    daily_rows, weekly_coverage, policy,
    period_from="2026-11-16", period_to="2026-11-22",
)
```

### daily_rows (정규화된 근로·휴게 사실)

| 필드 | 의미 |
|---|---|
| `employee_id, work_date` | 직원·일자. `YYYY-MM-DD` |
| `actor_type` | `EMPLOYEE` 또는 `EXTERNAL_SERVICE` |
| `worktime_system, policy_ref` | 외부 확정 근로시간제·적용 정책 |
| `worked_min, worked_verified, worked_evidence_ref` | 실제 근로시간(분), 증빙 확인 및 근거 |
| `rest_min, rest_verified, rest_evidence_ref` | 실제 자유 휴게시간(분), 증빙 확인 및 근거 |
| `rest_within_workday_verified` | 휴게가 근로시간 도중에 주어진 사실 검증 |
| `rest_coverage_complete, rest_coverage_ref` | 실내 휴게 등 전체 기록의 완전성 확인과 증빙. 부족 판정 시 필수 |
| `planned_break_min` | 예정 휴게시간(분). 없는 경우 회사 기준 초과 검토 생략 |
| `four_hour_waiver_ref` | 2026-12-10 이후 **정확히 4시간 근로자의 명시적 미사용 요청** 근거(해당 시만) |
| `source_ref, _row_number` | 출처 파일·행 번호 |

단말기 `OUT/IN`만으로 `rest_verified=true`를 만들면 안 됩니다. 근태장부의 출퇴근 차이만으로 `worked_verified=true`를 만들면 안 됩니다. 이 값들은 증빙 확인 절차를 거친 자료로부터 외부에서 제공받는 계약입니다.

### weekly_coverage (확정된 주간 대상 범위)

`employee_id, week_start`(월요일), `coverage_complete=true/false`, `evidence_ref`, `exception_status=NONE/PRESENT/UNKNOWN`.

- `coverage_complete=true`는 해당 직원의 월요일~일요일 근로 관련 기록이 빠짐없이 조회·검토되었다는 외부의 명시적 근거가 있을 때만 사용합니다.
- `exception_status=NONE`은 한시적 예외 또는 별도 승인할 특례가 없다는 **외부 검토 결과**입니다. 값이 없거나 `PRESENT/UNKNOWN`이면 표준 주간 상한을 근거로 최종 결론을 내리지 않습니다.
- 날짜가 월 경계를 건너면 7일 전체를 입력하거나 미확정 상태로 남겨야 합니다.

### policy (외부에서 검토된 기준)

```json
{
  "schema_version": "0.1",
  "policy_ref": "SYNTHETIC_KR_STANDARD_V1",
  "daily_standard_min": 480,
  "weekly_standard_min": 2400,
  "weekly_limit_min": 3120,
  "rest_every_work_min": 240,
  "rest_per_block_min": 30,
  "break_overrun_tolerance_min": 0
}
```

위 숫자는 **표준 근로시간제에 대한 합성 테스트 정책 예시**입니다. 실제 운용 시 해당 사업장, 근로시간제, 정책 시행일을 검토한 후 `policy_ref`를 설정해야 합니다. 외부 정책을 자동 승인하거나 현재 유효 법률이라고 재해석하지 않습니다. 법정 휴게 최소치는 근로기준법 제54조를 참조하며, 2026-12-10의 정확히 4시간 근로 요청 예외는 별도 근거가 있을 때만 적용합니다.

### 휴게시간의 부호 있는 차이

Schedule에서 휴게시간을 비교하지 않습니다. **확인된 휴게시간**과 외부 정책으로 산출한 **필수 최소 휴게시간**의 차이는 이 Module이 반환합니다.

`daily[].rest_deviation`:

```json
{
  "required_min": 60,
  "recorded_min": 45,
  "delta_min": -15,
  "direction": "NEGATIVE",
  "coverage_complete": true,
  "shortfall_confirmable": true,
  "reason": "업무 중단 불가"
}
```

- **방향:** `delta_min = recorded_min - required_min`. 실제 45분/필수 60분이면 `-15`분, 실제 90분/필수 60분이면 `+30`분입니다.
- **사유:** `daily_rows[].rest_reason` 선택 문자열을 있는 그대로 보존합니다. 비어 있으면 `null`; 사유를 만들어내거나 근무 승인 여부로 취급하지 않습니다.
- **증빙:** 실제 휴게를 검증하지 못한 경우 `delta_min=null`, `direction=UNKNOWN`으로 유지합니다. 필수 휴게시간이 적용될지 결정되지 않은 근로시간제도 `null`입니다.
- **완전성:** 기록된 휴게가 필수보다 짧으면 `delta_min`은 음수로 보존하되, 휴게 기록 전체의 완전성이 확인되지 않았다면 `shortfall_confirmable=false`이며 `REST_SHORTFALL_UNDETERMINED`로 표시합니다. **기록이 적다는 사실과 휴게 부족이 확정됐다는 주장은 구분**합니다.
- **양수 차이:** 필수 최소보다 더 많이 쉬었다는 뜻이지 법정 최대 휴게시간 위반이 아닙니다. 회사가 예정한 휴게시간보다 긴지 여부는 별도 `COMPANY_BREAK_OVERRUN_REVIEW` 규칙에서 처리합니다.
- `approved=false`, `legal_conclusion=false`, `payroll_finalizable=false`는 유지됩니다.

### 결과

`daily[]`는 `worked_min, rest_min, required_rest_min, planned_break_min, review_codes, status`를 기록합니다. `weekly[]`는 `total_worked_min, week_start, week_end, coverage_ref, review_codes, status`를 기록합니다.

대표 코드:
- `REST_SHORTFALL_REVIEW`: 확인된 휴게 부족 후보(완전성 근거 필요)
- `REST_SHORTFALL_UNDETERMINED`: 근거 불완전으로 부족 여부 미판정
- `COMPANY_BREAK_OVERRUN_REVIEW`: 회사 예정 휴게를 초과(법정 위반 아님)
- `DAILY_STANDARD_EXCEEDED_REVIEW`, `WEEKLY_STANDARD_EXCEEDED_REVIEW`: 표준시간 초과 후보
- `WEEKLY_LIMIT_EXCEEDED_REVIEW`: 적용 표준 근로시간제의 주간 총량 기준 초과 후보
- `WORKTIME_SYSTEM_REVIEW`, `WEEKLY_EXCEPTION_REVIEW`, `WEEKLY_COVERAGE_UNVERIFIED`: 한도 판정을 보류해야 하는 사유

`PASS`는 입력된 근로·휴게시간 증빙 및 제공된 정책에 대한 자동 검토상 특이사항이 없음을 뜻하며, 법적 최종 판정은 아닙니다. `REVIEW_REQUIRED`는 추가 확인이 필요함을 뜻합니다. `approved=false`, `legal_conclusion=false`, `payroll_finalizable=false`를 항상 유지합니다.

## 독립 테스트

```bash
python3 -m unittest bhandara.tests.test_worktime_compliance -v
```

외부 인증 기록을 읽어 실제 휴게로 자동 확정하지 않으며, 이 Module은 독립 실행 가능합니다.
