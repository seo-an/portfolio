# Worktime — JSON 설정 기반 Tool CLI

## 사용 방법

복잡한 명령 옵션을 매번 입력하지 않습니다. 한 번 `config.example.json`을 개인 설정 경로로 복사하고 JSON의 **기간·입출력 경로·선택 단계**만 변경합니다.

```bash
mkdir -p bhandara/data/config
cp bhandara/worktime/config.example.json bhandara/data/config/worktime.json
# 위 JSON을 개인 자료의 실제 위치·정책·기간으로 수정
python3 run.py bhandara worktime
```

별도 설정을 이용하면 `python3 run.py bhandara worktime --config /private/config/worktime.json`을 사용합니다. 신규 Tool은 `--period`, `--input-dir`, `--output-dir`를 받지 않습니다.

`run_id: "auto"`면 실행마다 새 KST ID를 만들어 결과를 덮어쓰지 않습니다. 개인 설정 JSON 및 HR 원본은 공개 Git에 커밋하지 않습니다.

## JSON 계약

필수 키: `schema_version: "1.0"`, `tool: "worktime"`, `period_from`, `period_to`, `input_root`, `output_root`, `run_id`, `steps`, `files`. Compliance를 실행할 때에는 적용 정책 `policy` 객체가 필수입니다.

`steps`는 아래 이름 중 원하는 것만 지정합니다. 선택하지 않은 Module을 몰래 실행하지 않으며, 앞 단계의 기존 파일을 다시 사용할 경우 정확한 경로를 설정합니다.

| 단계 | 실행 역할 | 필요한 입력 | 출력 |
|---|---|---|---|
| `schedule` | 날짜별 스케줄 배정 vs 장부 기록 존재 여부 | `schedule`, `attendance` | `schedule-result.json` |
| `attendance-verification` | 장부·출입기·예정 시각 검증 | `schedule`, `attendance`, `access_events` | `attendance-verification-result.json` |
| `worktime-compliance` | 외부 확인된 근로·휴게와 적용정책 검토 | `verified_work`, `policy` | `worktime-compliance-result.json` |
| `output` | 직원별·일자별 사실만 결합 | `schedule` + 앞 단계 결과 또는 명시된 이전 결과 + 선택 `attendance_facts` | `worktime-result.xlsx` |

`output`에서 Attendance Verification과 Compliance가 `steps`에 없다면 `files.attendance_verification_result`, `files.compliance_result`로 **기존 결과 JSON의 명시적 경로**를 제공해야 합니다. 파일의 모듈명·기간 불일치는 거부합니다.

### Excel 입력 계약

입력 루트 아래 기본 권장 경로는 다음과 같습니다. **정식 구형 샘플 Excel을 자동으로 변환·덮어쓰지 않습니다.** 신규 시트·헤더는 도입할 회사 자료에 맞춰 명시적으로 작성해야 합니다.

**1. `worktime/work-schedule.xlsx`**: 기존 첫 시트를 유지하면서 `SCHEDULE MAP`, `ASSIGNMENTS` 추가. 정확한 헤더는 [스케줄 ID 매핑 계약](SCHEDULE-MAP-CONTRACT.md)을 따릅니다.

**2. `worktime/attendance.xlsx`**의 `Attendance` 시트:

```text
employee_id | work_date | clock_in | clock_out | break_min
```

시각은 `HH:MM` 또는 날짜가 확인된 `YYYY-MM-DDTHH:MM`. 익일 종료나 날짜가 불명확한 기록을 임의 전날과 결합하지 않습니다. 추가 `clock_in_reason`, `clock_out_reason`은 원본 입력으로 받을 수 있으나 지급·승인은 판단하지 않습니다.

**3. `worktime/access-events.xlsx`**: 업체별 원본을 [표준 정규화 계약](ACCESS-EXCEL-CONTRACT.md)에 따라 사전 변환한 4시트 파일. 신규 Tool은 회사별 원본을 이 단계에서 자동 변환하지 않습니다. Source Review의 문제는 기존 `verify_attendance_xlsx` 경로를 통해 계속 보존합니다.

**4. `worktime/verified-work.xlsx`**:

- `DAILY`: `employee_id, work_date, actor_type, worktime_system, policy_ref, worked_min, worked_verified, worked_evidence_ref, rest_min, rest_verified, rest_evidence_ref, rest_within_workday_verified, rest_coverage_complete, rest_coverage_ref` (선택적으로 `planned_break_min, rest_reason, four_hour_waiver_ref` 추가).
- `WEEKLY COVERAGE`: `employee_id, week_start, coverage_complete, evidence_ref, exception_status`.

**이미 외부에서 검증된 실제 근로·휴게 사실**이 입력이어야 합니다. 기록되지 않은 근로시간이나 자유 휴게를 출입기 기록만 보고 만들어서는 안 됩니다. `worktime_system`은 `standard` 같은 근로시간제 구분으로, `DAY` 같은 `schedule_type`과 별개입니다.

**5. `worktime/attendance-facts.xlsx`**의 `ATTENDANCE FACTS`: `employee_id, work_date, attendance_type, leave_type, leave_request_id`.

유급·무급 및 결근 사실은 **외부 확정 구분을 그대로 전달**합니다. 휴가시간 자체는 별도 컬럼을 만들지 않으며 `leave_request_id`로 원신청을 조회합니다. 시트가 제공되지 않으면 구분을 임의로 만들지 않고 공란으로 보존합니다.

### 단일 Output

`WORKTIME` 시트에는 다음 열만 있습니다.

```text
employee_id, work_date, schedule_id,
scheduled_min, actual_min, clock_in_delta_min, clock_out_delta_min,
attendance_type, leave_type, leave_request_id
```

- 출근 Δ = **예정 출근 − 기록 출근**: 조기출근 + / 지각 −
- 퇴근 Δ = **기록 퇴근 − 예정 퇴근**: 지연퇴근 + / 조기퇴근 −
- 소정·실제·출근Δ·퇴근Δ는 **서로 독립**적인 시간 값. 중복 합산은 Payroll이 결정합니다.
- 휴가 승인, 급여반영시간, 수당, 금액, 법 위반·근태 상태 판단 컬럼은 넣지 않습니다.
- 미확인 실제 근로시간은 **공란**, 검증된 실제 0분은 **0**으로 구별합니다.

## 운영 연결과 구형 계산기 분리

본 CLI는 독립 Tool 실행만 담당합니다. 새 Worktime 결과를 구형 `payroll-calculator`의 `worktime-result.json`처럼 전달하지 않습니다. Gearbox/Slack 운영 연동과 현장 자료 처리, 외부 근태 승인, 분할근무/복수 신청의 데이터 계약은 후속입니다.

테스트: `python3 -m unittest bhandara.tests.test_worktime_json_tool_cli -v`, 이후 전체 Gearbox 기능·인프라 회귀를 수행합니다.
