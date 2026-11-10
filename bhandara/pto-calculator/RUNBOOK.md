# 연차 계산기 사용 안내서 — 엑셀 준비부터 결과 확인까지

**이 문서는 개발자가 아니어도 연차 계산기에 넣을 Excel과 설정 파일을 준비할 수 있도록 작성했습니다.** 설치·Python 실행 명령·코드·테스트 결과는 [연차 계산기 README](README.md)를 참고하세요.

> **계산 범위:** 입사일을 기준으로 발생하는 연차 내역을 검토합니다. 휴가 **사용 잔액, 회계연도 기준 전환·정산, 퇴직 시 수당, 최종 승인**을 처리하는 도구는 아닙니다.

## 1. 무엇을 준비하나요?

가장 쉬운 방법은 [합성 예제 생성 안내](README.md#합성-데이터로-시험해-보기)에 따라 만들어지는 **가상 직원 2명의 Excel**을 열고 파일 모양을 먼저 확인하는 것입니다. 실제 자료를 넣을 때에는 예제와 구분된 새 폴더를 사용하세요.

| 파일 이름 | 용도 | 언제 필요한가 |
|---|---|---|
| **`employee.xlsx`** | 직원 ID, 입사일·퇴사일 | 기본 필수 |
| **`work-schedule.xlsx`** | 반복되는 근무표의 기본 규칙 | 기본 필수 |
| **`work-schedule-assignment.xlsx`** | 직원별 어느 근무표를 언제부터 적용하는지 | 기본 필수 |
| `work-records/2026/2026-07-schedule.xlsx` | 2026년 7월 실제 배정 스케줄 | 설정에 해당 파일을 지정했다면 필요 |
| `work-records/2026/2026-07-attendance.xlsx` | 2026년 7월 출퇴근 기록 | 설정에 해당 파일을 지정했다면 필요 |
| `employee-events.xlsx` | 휴가·승인 등 직원 이벤트 | 필요한 경우 선택 |

**Excel 저장 형식은 `.xlsx`**입니다. 시트 이름은 자유롭게 정할 수 있고, **현재 활성 시트**를 읽습니다. 엑셀을 저장하기 전에 자료가 있는 시트를 선택해 두세요. 1행에는 아래와 같이 **영문 열 제목**, 2행부터 데이터를 입력합니다.

## 2. 폴더를 이렇게 정리하세요

아래의 `입력` 폴더를 연차 계산기에 알려주면 내부의 상대 경로를 따라 파일을 찾습니다. **프로그램 설치 폴더에 직원 원본 자료를 넣을 필요가 없습니다.**

```text
내 문서/반다라-작업/연차/2026-07/
├── 입력/
│   ├── employee.xlsx
│   ├── work-schedule.xlsx
│   ├── work-schedule-assignment.xlsx
│   └── work-records/
│       └── 2026/
│           ├── 2026-07-schedule.xlsx
│           └── 2026-07-attendance.xlsx
├── 설정/
│   └── config.json
└── 결과-01/                 ← 실행 후 생성하는 새 폴더
```

`work-records`의 `2026`과 `2026-07`은 예시 연도·월입니다. 다른 기간을 계산하려면 **실제 있는 파일 이름에 맞게 JSON 경로도 함께 바꿔야** 합니다.

## 3. 각 Excel에 무엇을 입력하나요?

아래는 **가상 직원**의 입력 형식을 보여주는 예입니다. 표에 보이는 영문 열 이름은 **한글로 번역하거나 임의로 고치지 마세요**. 열 순서는 연차 계산기에서는 자유롭지만, 필요한 열은 모두 있어야 합니다. 추가 메모 열은 무시됩니다.

### 3.1 `employee.xlsx` — 직원명부

| employee_id | hire_date | termination_date | work_system |
|---|---|---|---|
| E001 | 2026-06-01 | *(빈칸)* | FIXED |
| E005 | 2026-01-01 | *(빈칸)* | FIXED |

`employee_id`는 직원 식별값으로, **다른 Excel에도 똑같이** 써야 합니다. `hire_date`는 입사일, `termination_date`는 퇴사일(재직 중이면 빈칸), `work_system`은 근무형태를 표현하는 코드입니다. 날짜는 `YYYY-MM-DD` 또는 Excel 날짜 셀로 작성하세요.

### 3.2 `work-schedule.xlsx` — 기본 근무표

| schedule_id | work_system | sequence | day_type | shift_code | start_time | end_time | break_min | scheduled_work_hours | note |
|---|---|---|---|---|---|---|---|---|---|
| FIXED_7 | FIXED | 1 | WORK | DAY | 09:00 | 18:00 | 60 | 8 | *(빈칸)* |
| FIXED_7 | FIXED | 6 | OFF | *(빈칸)* | *(빈칸)* | *(빈칸)* | *(빈칸)* | 0 | *(빈칸)* |

`schedule_id`는 근무표 이름, `sequence`는 반복 순서, `day_type`은 근무일(`WORK`) 또는 휴무일(`OFF`) 등의 코드입니다. `break_min`은 **휴게시간(분)**입니다. 위 표는 **1번과 6번 순서만 발췌한 예시**이므로 7일 반복 근무표라면 필요한 순서를 모두 작성해야 합니다.

### 3.3 `work-schedule-assignment.xlsx` — 직원별 근무표 적용

| employee_id | schedule_id | effective_from | effective_to | cycle_anchor_date | start_sequence | note |
|---|---|---|---|---|---|---|
| E001 | FIXED_7 | 2026-01-01 | *(빈칸)* | 2026-07-01 | 1 | *(빈칸)* |

`employee_id`는 직원명부와, `schedule_id`는 기본 근무표와 일치해야 합니다. `effective_from/to`는 적용기간, `cycle_anchor_date`는 반복 순서의 기준일, `start_sequence`는 그날 적용할 순서입니다. 예시가 없는 다른 직원도 해당하는 근무표 배정 행을 준비합니다.

### 3.4 월별 스케줄과 출퇴근 기록

**스케줄 Excel**

| employee_id | work_date | schedule_id | shift_code | scheduled_start | scheduled_end | break_min | scheduled_work_hours | day_type | note |
|---|---|---|---|---|---|---|---|---|---|
| E001 | 2026-07-01 | FIXED_7 | DAY | 09:00 | 18:00 | 60 | 8 | WORK | *(빈칸)* |

**근태 Excel**

| employee_id | work_date | clock_in | clock_out | break_min | source | note |
|---|---|---|---|---|---|---|
| E001 | 2026-07-01 | 09:00 | 18:00 | 60 | HR | *(빈칸)* |

`work_date`는 근무일, `clock_in/out`은 실제 출퇴근 시각입니다. **근무표의 예정시간과 실제 근태시간은 다른 자료**입니다. 날짜·직원 ID가 서로 연결되도록 작성합니다. 자료가 없거나 불확실하면 계산기가 **검토 필요**로 표시할 수 있으니 없는 승인을 임의로 만들지 마세요.

선택 파일인 `employee-events.xlsx`를 사용하는 경우 1행에 `request_id, employee_id, event_type, event_date, unit, status, note`를 사용합니다. 이벤트 코드는 회사의 실제 승인자료와 기존 입력 계약을 확인해 넣어야 하며, 단순히 ‘연차 사용’이라고 한글로 적으면 자동 인식한다고 가정하면 안 됩니다.

## 4. `config.json`에서 무엇을 바꾸나요?

계산기 폴더의 [전체 설정 틀](config.json)을 **복사한 뒤 작업 폴더의 `설정/config.json`으로 저장**하고 내용만 수정하세요. 설정 파일을 새로 처음부터 작성할 필요는 없습니다.

```json
{
  "schema_version": "1.0",
  "period": {
    "from": "2026-07-01",
    "to": "2026-07-31"
  },
  "files": {
    "employees": "employee.xlsx",
    "schedule": "work-schedule.xlsx",
    "assignments": "work-schedule-assignment.xlsx",
    "monthly_schedule": [
      "work-records/2026/2026-07-schedule.xlsx"
    ],
    "attendance": [
      "work-records/2026/2026-07-attendance.xlsx"
    ],
    "events": null
  },
  "employee_allowlist": []
}
```

| 어디를 바꾸나요? | 바뀌는 결과 | 주의 |
|---|---|---|
| `period.from` / `period.to` | 계산할 날짜 범위 | `YYYY-MM-DD`. 시작일이 종료일보다 늦으면 안 됨 |
| `files.employees` | 직원명부 Excel 위치 | `입력/` 폴더를 기준으로 한 상대 경로 |
| `files.schedule` | 기본 근무표 Excel 위치 | 파일명이 실제와 같아야 함 |
| `files.assignments` | 직원별 근무표 배정 위치 | 위와 동일 |
| `files.monthly_schedule` | 읽을 월별 스케줄 목록 | 월이 바뀌면 `2026-07` 등의 경로도 수정 |
| `files.attendance` | 읽을 월별 출퇴근 목록 | 여러 달이면 경로를 쉼표로 구분하여 여러 개 기재 |
| `files.events` | 이벤트 Excel | 사용하지 않으면 `null`, 사용할 때는 실제 경로 문자열 |
| `employee_allowlist` | 계산할 직원 대상 | `[]` 전체 직원 / `["E001"]` 지정 직원만 |

**주요 실수:** `period`만 8월로 바꾸고 `files.attendance`를 7월 파일 그대로 두면, 8월 근태가 자동으로 선택되지 않습니다. **계산기간, 월별 경로, 실제 Excel 내용**을 함께 맞춰 주세요.

**JSON 편집:** 항목 이름을 바꾸지 말고, 텍스트·파일 경로는 큰따옴표 안에 적습니다. 마지막 항목 뒤 쉼표는 지우고, `null`을 `"null"`로 변경하지 마세요.

## 5. 실행 후 무엇을 확인하나요?

실행에 필요한 입력 폴더와 설정 파일 위치, **새 결과 폴더 이름**을 준비한 다음 [README의 실행 안내](README.md#3-cli-실행)를 따르면 됩니다. 실제로 사용하는 사람은 다음 **결과 Excel**을 먼저 확인하면 됩니다.

| 생성 파일 | 열어 볼 곳 |
|---|---|
| `pto-result.xlsx` | Excel로 열어 전체 요약·발생 내역·검토 항목 확인 |
| `pto-result.json` | 정확한 숫자 및 다른 시스템 연계용 계산 결과 |
| `pto-review.json` | 오류·검토 필요 사유 |
| `pto-run.json` | 입력·출력 이력 기록, 승인증이 아님 |

`pto-result.xlsx` 안에는 `Summary`, `Grants`, `Unresolved`, `Review Required` 시트가 있습니다. **발생하지 않았다고 표시된 항목이나 검토 필요 항목을 0일로 확정하지 마세요.**

**`PASS`는 계산 완료를 나타낼 뿐 최종 연차 승인이나 법적 적합성 확정이 아닙니다.**

## 6. 자주 묻는 질문

**Q. 시트 이름을 ‘직원명부’로 바꿔도 되나요?** 가능하지만 해당 시트를 **활성 시트로 선택한 뒤 저장**해야 합니다. 위의 영문 **열 제목**은 그대로 둡니다.

**Q. 근태 Excel이 없으면 어떻게 되나요?** 지정된 파일 자체가 없으면 입력 오류가 발생할 수 있습니다. 자료가 원래 없는 경우에는 설정의 사용 목록을 검토해야 하며, **출근율 확인이 불가능한 과거 기간은 검토 필요**로 남을 수 있습니다.

**Q. 다른 부서 직원만 계산하고 싶어요.** `employee_allowlist`에 해당 `employee_id`들을 기재합니다. 부서명을 자동 검색하는 기능이 아니라 **직원 ID 목록 기준**입니다.

**Q. Excel의 셀을 합치거나 1행 위에 제목을 써도 되나요?** 권장하지 않습니다. **1행은 영문 열 제목 전용**, 2행부터 실제 데이터를 넣으세요.

**Q. 결과가 다르게 보이면?** 먼저 입력 `employee_id`가 파일들 사이에서 정확히 같은지, 계산기간과 월별 파일 경로가 맞는지 확인하세요. 값 수정 후에는 **새 결과 폴더**로 다시 실행합니다.
