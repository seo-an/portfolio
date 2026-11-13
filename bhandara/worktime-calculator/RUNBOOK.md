# 근무시간 계산기 사용 안내서 — Excel 준비부터 결과 확인까지


## 내 설정 파일 하나만 수정하는 독립 실행

`bhandara/worktime-calculator/user_settings.py`의 문자열만 변경하세요.
`PERIOD` 기본값은 예시이므로 실제 분석 월로 수정해야 합니다.

| 변수 | 기본값 | 입력 가능한 값 |
|---|---|---|
| `PERIOD` | `"2026-06"` | `"YYYY-MM"` 형식의 월 |
| `EMPLOYEES_FILE` | `"common/employee.xlsx"` | 직원명부 Excel 상대 경로 |
| `IDENTITY_FILE` | `"common/id-map.xlsx"` | ID_MAP 시트가 있는 Excel 상대 경로 |
| `SCHEDULE_FILE` | `"worktime/work-schedule.xlsx"` | 예정근무 Excel 상대 경로 |
| `ATTENDANCE_FILE` | `"worktime/attendance.xlsx"` | 출퇴근 Excel 상대 경로 |

모든 파일을 `bhandara/data/input/` 아래에 준비하고 프로젝트 루트에서 실행합니다.

```bash
python run.py bhandara worktime-calculator
```

필요하면 `--input-dir`와 `--output-dir`로 별도 입출력 폴더를 지정합니다.
기존 `--normalized` + `--config`의 외부 전체 설정 방식은 그대로 유지되고
`user_settings.py` 값과 섞지 않습니다. `--period`를 명시하면
기존 고정 Excel 역할 경로 방식입니다.

설정이 잘못되면 `SETTINGS_INVALID`로 차단합니다. 계산 결과는
근태 승인·기간 마감이 아니라 **검토용**이며, 비표준 근무형태를
임의로 표준근로시간제 승인 처리하지 않습니다.

---

## 간편 모드: Excel 직접 읽기

[80명 공통 샘플](../examples/sample/input/)의
`common/employee.xlsx`, `common/id-map.xlsx(ID_MAP 시트)`,
`worktime/work-schedule.xlsx`, `worktime/attendance.xlsx`를
표준 폴더에 두고 다음과 같이 실행합니다.

```bash
python run.py bhandara worktime-calculator --period 2026-06
```

실행 결과에는 출처 해시·행번호를 보존한 `normalized-input.json`도 생깁니다.
캡스·세콤·KT 형태의 **가상 출입 원본 Excel**은 참고·검토 자료로 별도 보관하며,
메뉴 미선택이나 중복 태그를 자동으로 출퇴근 확정하지 않습니다.
아래의 JSON 직접 준비 방식은 기존의 고급 사용자용 계약 설명입니다.

## 직원과 외부 인력을 같은 근태 Excel로 처리하기

외부 인력이 실제로 시간제·일급제 업무를 제공하고 그 실적을 근거로
계약대가를 검토해야 한다면 **새 근태 Excel을 만들 필요가 없습니다.**
기존 파일 3개만 사용합니다.

### 1. `common/id-map.xlsx` — `EXTERNAL` 시트 추가(선택)

원래 **`ID_MAP` 시트는 사내 직원 전용**으로 그대로 유지합니다.
외부 인력이 있는 경우에만 같은 파일에 `EXTERNAL` 시트를 추가하세요.

| worker_id | security_id |
|---|---|
| EXT-W001 | SEC-EXT-001 |
| EXT-W002 | SEC-EXT-002 |

- **`worker_id`**는 Worktime과 Payroll 계약을 연결할 식별자입니다.
- **`security_id`**는 출입기·근태 원본과 연결하는 식별자입니다.
- 두 열은 공란·중복 불가이며, `ID_MAP` 직원의 사번·worker_id·security_id와
  충돌하면 차단합니다.
- `party_id`(외부 계약 상대방)는 **Payroll 계약의 Contracts 시트에서만**
  작성합니다. Worktime에는 보수 단가나 계약 유형을 중복 기록하지 않습니다.
- 외부 인력이 없다면 `EXTERNAL` 시트는 만들지 않아도 됩니다.

### 2. `worktime/work-schedule.xlsx`와 `worktime/attendance.xlsx`

두 파일에서 기존 `employee_id` 열을 **그대로 유지**하고,
맨 오른쪽에 `worker_id` 열을 추가하면 됩니다. 일반 직원과 외부
인력을 같은 시트의 여러 행으로 기록합니다.

| employee_id | worker_id | work_date | 예시 |
|---|---|---|---|
| E001 | (빈칸) | 2026-06-02 | 직원 근무표·근태 |
| (빈칸) | EXT-W001 | 2026-06-02 | 외부 인력 근무표·근태 |

- 직원 행은 `employee_id`만 입력합니다. 기존 Excel에는
  `worker_id` 열 자체가 없어도 됩니다.
- 외부 인력 행은 `worker_id`만 입력합니다. 반드시
  `EXTERNAL` 시트에 등록되어 있어야 합니다.
- **한 행에 두 ID를 동시에 입력하거나 둘 다 비워 두면 차단**됩니다.
- 나머지 예정시간·근태시간·휴게시간·근무일 헤더는 기존 파일과 동일합니다.
- Worktime이 외부 인력을 계산할 때 필요한 내부 연결키는
  `worker_id`에서 자동 생성합니다. 실제 직원으로 등록하거나
  `common/employee.xlsx`에 옮겨 적는 작업은 **하지 않습니다.**

실행은 평소와 같습니다.

```bash
python run.py bhandara worktime-calculator --period 2026-06
```

출력 `worktime-result.json`의 `covered_worker_ids`에는 직원·외부 인력이
모두 포함됩니다. `source_hashes.identity_map`에는 `id-map.xlsx`의
원본 SHA-256도 남습니다. 외부 인력의 근무시간은 승인 완료가 아닌
**검토용 계산 사실**이며, 법정 근로시간·급여·청구 승인으로 간주하지
않습니다.

Payroll에서는 해당 결과 파일을 다음과 같이 **명시적으로** 전달합니다.

```bash
python run.py bhandara payroll-calculator \
  --period 2026-07 \
  --worktime-result /실제경로/worktime-result.json
```

Payroll의 `pay-contract.xlsx` → `Contracts`에는 해당 외부 인력의
`worker_id`, `party_id`, `relationship_type`을 입력합니다.
Payroll 직원 급여에는 이 외부 인력이 포함되지 않으며,
`contract-basis-review`에서 추정 대가만 검토합니다.

**CAPS·세콤의 출입 태그만으로 출퇴근을 확정하지 않습니다.**
근무표와 출퇴근 Excel은 검증된 정규화 사실을 입력한 것으로 보고
추가 검토를 표시합니다. Worktime 계산은 용역 청구·지급 승인과 별개입니다.

---

Worktime(근무시간) 계산기는 **직원별 근무표와 출퇴근 정보를 받아 일별 근무시간을 계산하고, 확인이 필요한 항목을 표시**합니다. 이 문서는 실제 입력 자료를 준비하는 사람을 위한 설명입니다. 설치·코드·테스트 명령은 [Worktime README](README.md)에 있습니다.

> **기본 사용:** 표준 경로의 Excel을 읽습니다. 고급 사용자에게는 기존 정규화 JSON 입력도 제공합니다.

## 1. 무엇을 준비하나요?

| 파일 | 확장자 | 내용 | 직접 수정하는 사람 |
|---|---|---|---|
| **`normalized-input.json`** | `.json` | 직원명부, 예정 근무표, 실제 근태 및 원본 연결 기록 | 일반적으로 원본 정규화 담당자·도구가 생성 |
| **`worktime-config.json`** | `.json` | 계산기간, 직원별 근로제·적용 기준, 승인 참조 | 계산을 준비하는 담당자 |
| `review-report.json` | `.json` | 원본 정규화 중 발견된 문제 목록 | 정규화 과정에서 생성한 경우 함께 보관 |

**이하 설명은 고급 JSON 직접 입력 방식입니다.** 위의 간편 Excel 모드에서는 `common/id-map.xlsx`의 `ID_MAP`(직원)과 선택 `EXTERNAL`(외부 인력) 시트가 사용됩니다. 엑셀 원본을 가지고 있다면 별도 정규화 도구(예: 동일 포트폴리오의 Payroll `normalize` 기능 또는 회사의 별도 매핑 절차)를 이용해 요구되는 형태의 JSON을 만든 뒤 Worktime에 전달합니다. 다만 **Payroll 모듈을 함께 설치해야 한다는 의미는 아닙니다.** 외부에서 준비된 JSON 파일만 있으면 Worktime 단독 실행이 가능합니다.

## 2. 폴더는 이렇게 준비하세요

```text
내 문서/반다라-작업/근무시간/2026-09/
├── 입력/
│   ├── normalized-input.json
│   └── review-report.json        ← 정규화 결과에 있을 때만
├── 설정/
│   └── worktime-config.json
└── 결과-01/                      ← 실행 후 새로 만들어질 폴더
```

**가상 자료를 바로 보고 싶다면** 계산기 안의 다음 두 파일을 열어 보세요.

- [정규화된 가상 근태 JSON](examples/normalized-input.demo.json)
- [가상 직원 근로제·승인 설정 JSON](examples/worktime-config.approved.demo.json)

두 파일에는 `E01`·`E02`라는 가상 직원이 들어 있습니다. 예제에 **승인 참조 형태의 문자열이 포함되어 있더라도 실제 인사 승인 또는 근태 마감 기록은 아닙니다.**

## 3. `normalized-input.json`은 어떤 모양인가요?

구조를 이해하기 위한 **일부만** 발췌한 예입니다. 실제 실행에는 원본 예제의 전체 `sources`, `rows`, `lineage` 구조가 필요합니다.

```json
{
  "schema_version": "0.1",
  "status": "READY_FOR_CALCULATION",
  "batch_id": "sample-batch",
  "sources": {
    "employees": {
      "rows": [
        { "employee_id": "E01", "worker_id": "EP0001" }
      ],
      "source_sha256": "원본 정규화 과정에서 생성된 값",
      "lineage": [
        { "status": "ACCEPTED", "row_number": 2, "issue_codes": [] }
      ]
    }
  }
}
```

| 항목 | 무엇을 뜻하나요? |
|---|---|
| `employee_id` | 근태 원본에서 쓰는 직원 식별값 |
| `worker_id` | 급여 등 다른 업무 시스템으로 넘길 때 사용할 직원 식별값 |
| `work_date` | `2026-09-15`와 같은 실제 근무일 |
| `scheduled_start/end` | 출근·퇴근 **예정** 시간 |
| `clock_in/out` | 실제 출퇴근 기록 |
| `break_min` | 휴게시간. 시간 단위가 아니라 **분** |
| `day_type` | `WORK`(근무), `OFF`(휴무), `HOLIDAY`(휴일) 등 원본 분류 |
| `lineage` | 어떤 원본 행이 받아들여졌는지 기록하는 연결 정보 |
| `source_sha256` | 원본 출처 확인을 위한 해시. **임의로 작성·위조하지 않음** |

`sources` 안에는 `employees`, `schedule`, `attendance`의 세 데이터 묶음이 들어갑니다. **직원명부의 `employee_id`는 예정 근무표와 실제 근태에도 동일하게 적혀야** 합니다. 직원·날짜가 연결되지 않으면 근무시간이 제대로 산출되지 않거나 검토 대상으로 분류됩니다.

**주의:** 가상 예제의 `source_sha256`은 합성 테스트용 식별 문자열입니다. 실제 회사 자료를 처리할 때는 **정규화 과정에서 실제 파일 출처와 원본 행 기록을 생성**해야 합니다. 단순히 가상 JSON의 이름·날짜만 대량으로 바꾸거나 `lineage`·원본 해시를 임의로 만들어 실무 자료라고 간주하지 마세요.

## 4. `worktime-config.json`에서 무엇을 바꾸나요?

다음은 제공된 설정 예제에서 일부 항목을 가져온 것입니다. **기존 틀을 복사해서** 해당 회사의 실제 기준에 맞게 작성하세요.

```json
{
  "schema_version": "0.1",
  "period_from": "2026-09-15",
  "period_to": "2026-09-15",
  "worktime_assignments": {
    "E01": {
      "worktime_system": "standard",
      "rule_ref": "labor_standard_50_53"
    }
  },
  "approvals": []
}
```

| 수정할 곳 | 바뀌는 내용 | 주의 |
|---|---|---|
| `period_from`, `period_to` | 계산할 날짜 범위 | 입력 JSON의 근태 날짜도 해당 범위에 있어야 함 |
| `worktime_assignments`의 `"E01"` | 해당 직원에게 근로제를 배정 | `normalized-input.json`에 있는 직원 ID와 정확히 일치 |
| `worktime_system` | 적용할 근로제 | 예제의 `standard`를 무조건 회사 전체에 적용하지 않음 |
| `rule_ref` | 참조할 근로시간 규칙 | 기존 규칙 코드와 실제 적용 기준을 확인 |
| `approvals` | 날짜별 승인 참조 | **실제 승인 근거가 없으면 가짜 참조를 만들지 말 것**. `[]`는 승인 목록이 없음을 뜻함 |

승인 자료를 실제로 전달받았다면 형식은 다음과 같습니다.

```json
{
  "employee_id": "E01",
  "work_date": "2026-09-15",
  "attendance_approval_ref": "실제 승인 식별값"
}
```

이는 **`approvals` 목록 안에 들어가는 객체의 예**입니다. 위 객체만으로는 전체 설정 JSON이 아닙니다. 승인 대상 직원·날짜와 원본 근무기록이 일치해야 하며, 참조 문자열을 적는 것만으로 실제 승인을 대신하지 않습니다.

**중요:** 근로제와 법정기준 관련 값은 단순한 보기 옵션이 아닙니다. 잘 모르는 경우 예제 값을 임의로 바꾸기보다 회사 담당자에게 확인하세요.

## 5. 엑셀 자료만 있을 때는 어떻게 하나요?

1. 직원명부, 근무표, 출퇴근 기록을 **원본 그대로** 안전한 업무 폴더에 보관합니다.
2. 원본 정규화 도구에 **직원 ID·근무일·열 이름·자료 형식**을 대응시키는 매핑 파일을 지정합니다.
3. 생성된 `normalized-input.json`의 직원·근무표·근태 개수와 `review-report.json`의 오류를 확인합니다.
4. 수정이 필요한 원본은 해당 Excel에서 고치고 **다시 정규화**합니다. 정규화 결과 JSON의 출처·행 정보를 임의로 덮어쓰지 않습니다.
5. 준비된 `normalized-input.json`과 `worktime-config.json`을 Worktime에 전달합니다.

드래그 앤 드롭 화면은 없지만, 표준 Excel 입력에서 CLI 정규화는 자동으로 수행됩니다. 이 부분은 기존 기능 이전 후 별도 개선 과제로 남아 있습니다.

## 6. 결과 파일은 어디서 확인하나요?

결과 폴더에 다음 파일이 생성됩니다.

| 파일 | 어디에 쓰나요? |
|---|---|
| **`worktime-review.xlsx`** | Excel에서 근무시간·누락·검토 항목을 확인 |
| `worktime-result.json` | 일별 근무시간 계산 결과. Payroll로 넘길 수 있는 **파일 계약** |
| `worktime-review.json` | 검토·누락 사유, 원본 행에 대한 확인 사항 |

Excel 결과의 `Summary`는 전체 요약, `Daily Worktime`은 직원·날짜별 계산, `Processing`은 처리 내용, `Review Required`는 검토할 항목입니다.

계산 결과가 `CALCULATED_UNCLOSED`라면 **시간을 계산했지만 근태 마감은 하지 않았다**는 뜻입니다. `REVIEW_REQUIRED`이면 보고서에서 원본 근무표·출퇴근 기록·승인 참조를 확인하세요.

## 7. 다른 급여 프로그램으로 넘길 때

Worktime에서 만든 `worktime-result.json`을 Payroll 프로그램의 설정 중 `worktime_result_path`에 지정합니다. **Worktime 계산기 코드를 Payroll 폴더에 복사할 필요는 없습니다.** JSON 파일만 전달하면 됩니다.

미마감 Worktime 결과를 전달하더라도 Payroll이 자동으로 승인·마감·급여 확정 처리하지는 않습니다. 자세한 내용은 [급여 사용 안내](../payroll-calculator/RUNBOOK.md)를 확인하세요.

## 8. 자주 묻는 질문

**Q. 시트 이름은 뭘로 해야 하나요?** 간편 Excel 모드에서는 `id-map.xlsx`에 `ID_MAP`(필수)과 `EXTERNAL`(외부 인력 있을 때만)을 사용합니다. 근무표·근태표는 첫 번째 시트를 읽으며, 고급 JSON 직접 실행은 Excel 시트를 읽지 않습니다.

**Q. 직원이 추가되면 어디를 바꾸나요?** 정규화된 직원명부·근무표·근태뿐 아니라 설정의 `worktime_assignments`도 해당 직원에 맞춰야 합니다. 예제의 `E01`만 바꿔서는 실제 근태를 추가한 것이 아닙니다.

**Q. 시간을 수정했는데 계산이 바뀌지 않아요.** `scheduled_start/end`(예정)과 `clock_in/out`(실제) 중 어느 값을 바꿨는지, JSON을 저장했는지, 전달된 파일 경로가 맞는지 확인하세요.

**Q. 다른 계산기 없이도 사용할 수 있나요?** 네. **Base + Worktime**만 있으면 됩니다. 다만 입력에 필요한 **정규화된 JSON을 누군가 또는 별도 절차가 준비해야** 합니다.
