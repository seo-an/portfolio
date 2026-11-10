# 급여 계산기 사용 안내서 — 엑셀과 설정 파일을 직접 준비하는 방법

이 문서는 인사·총무·급여 담당자가 **어떤 파일을 준비하고, 어디에 저장하고, 무엇을 수정하며, 결과를 어떻게 확인하는지** 설명합니다. Python 설치·실행 명령·코드·테스트와 이전 이력은 [급여 계산기 README](README.md)에 따로 정리합니다.

> **중요:** Payroll은 **검토용 급여 금액만 계산**합니다. 계산이 정상이어도 `REVIEW_REQUIRED`가 표시되고, **급여 지급·세금 신고·회계 확정이나 승인**을 대신하지 않습니다. 이 모듈에 포함된 2026년 정책 JSON도 현재 법령·회사 기준에 맞는지 별도로 검토해야 합니다.

## 1. 급여 계산을 위해 어떤 파일이 필요한가요?

처음 사용하는 사람은 [Payroll 합성 예제 생성 안내](README.md#2-첫-실행--payroll만으로-합성-급여-계산하기)에 따라 **가상 직원 2명의 파일**을 먼저 만들어 열어 보세요. `compensation.xlsx`, `payroll-input.xlsx`, `employment-facts.json`, `company-policy.json`, `payroll-config.json` 등이 실제로 어떤 모양인지 확인할 수 있습니다.

| 준비할 파일 | 확장자 | 용도 |
|---|---|---|
| **`compensation.xlsx`** | `.xlsx` | 직원별 기본급 등 고정·계약 보상 |
| **`payroll-input.xlsx`** | `.xlsx` | 이번 급여월의 수당·공제·조정 등 입력 |
| **`employment-facts.json`** | `.json` | 입사·퇴사 등 직원 고용 사실 |
| **`worktime-result.json`** | `.json` | 이미 계산된 근무시간 사실값(선택 가능한 Worktime 인계 방식 중 하나) |
| **`company-policy.json`** | `.json` | 해당 회사에서 적용하는 계산 방식 |
| **`payroll-config.json`** | `.json` | 급여월, 직원 범위, 위 입력 파일들의 위치 |
| `pay-item-registry.json` | `.json` | 어떤 급여항목을 사용할 수 있는지 정의하는 기준 |
| `operating-config.json` | `.json` | 급여월별 원본을 어느 기간에서 가져오는지 정하는 기준 |
| `2026.json` 등 | `.json` | 기존 법정 계산 기준 스냅샷. **현행 적합성 별도 확인 필요** |

급여 계산기 하나만 설치해도 됩니다. **Base + Payroll 코드**가 필요하고, 근무시간 자료는 다른 계산기 **프로그램 자체가 아닌 JSON 결과 파일**로 전달받을 수 있습니다.

## 2. 폴더와 파일은 어디에 두나요?

가장 쉬운 방법은 **설정 파일과 대부분의 입력 파일을 같은 폴더에 두는 것**입니다. 아래는 2026년 10월 급여를 계산하는 예시입니다.

```text
내 문서/반다라-작업/급여/2026-10/
├── 입력/
│   ├── payroll-config.json          ← 이 폴더의 파일 위치를 안내하는 설정
│   ├── compensation.xlsx            ← 보상 Excel
│   ├── payroll-input.xlsx           ← 월별 수당·공제 Excel
│   ├── employment-facts.json        ← 직원 입·퇴사
│   ├── worktime-result.json         ← 별도로 전달받은 근무시간 결과
│   ├── company-policy.json          ← 해당 회사의 급여 정책
│   └── resources/
│       ├── pay-item-registry.json
│       ├── operating-config.json
│       └── policy/
│           └── 2026.json
└── 결과-01/                          ← 새 계산 결과 폴더
```

`resources/`의 세 JSON은 프로그램 폴더에서 필요한 것을 **복사해서** 위 위치에 둘 수 있습니다.

| 가져올 원본(프로그램 폴더 안) | 내 작업 폴더의 복사 위치 |
|---|---|
| `bhandara/payroll-calculator/resources/pay-item-registry.json` | `입력/resources/pay-item-registry.json` |
| `bhandara/payroll-calculator/operating-config.json` | `입력/resources/operating-config.json` |
| `bhandara/payroll-calculator/resources/policy/2026.json` | `입력/resources/policy/2026.json` |

**복사본을 쓴다는 것은 그 기준이 법적으로 확정됐다는 뜻이 아닙니다.** 실제 급여 계산 전에는 회사 규정과 해당 시점의 법령 기준을 검토해야 합니다. 실제 직원·임금 파일은 프로그램 저장소나 공개 GitHub가 아닌 **개인정보 보호가 가능한 업무 폴더**에 보관하세요.

## 3. 급여용 엑셀은 어떻게 만드나요?

급여 계산에 직접 넣는 두 Excel의 확장자는 **`.xlsx`**입니다. 시트 이름은 `Sheet1`, `급여`, `보상` 등 자유롭지만 **프로그램은 활성 시트 하나를 읽으므로**, 자료가 있는 시트를 선택해 저장하세요. **1행이 영문 열 제목**, 2행부터 실제 데이터입니다.

### 3.1 `compensation.xlsx` — 직원별 기본급·고정 보상

| worker_id | effective_from | effective_to | base_salary |
|---|---|---|---|
| EP0001 | 2026-01-01 | *(빈칸)* | 3200000 |
| EP0002 | 2026-01-01 | *(빈칸)* | 2800000 |

- **처음 세 열은 순서까지 고정:** `worker_id`, `effective_from`, `effective_to`.
- 네 번째 열부터는 `base_salary` 등의 **급여항목 코드**를 적습니다. 항목 코드는 `pay-item-registry.json`에 등록되어 있고 보상 원본에서 허용된 것만 사용해야 합니다. 임의로 `기본급`, `수당` 등 한글 제목으로 바꾸지 마세요.
- `effective_from/to`는 **그 보상 조건이 적용되는 기간**입니다. `effective_to`가 없는 계속 적용 조건은 예시처럼 빈칸으로 둘 수 있습니다.
- 금액은 숫자 셀에 적고 원화기호 `₩`나 문자 `원`을 내용에 붙이지 않는 것이 안전합니다. 표시 형식은 Excel에서 별도로 지정할 수 있습니다.
- **직원이 여러 번 나타난다면** 적용기간이 서로 중복되지 않는지 확인하세요.

### 3.2 `payroll-input.xlsx` — 월별 지급·공제·조정

**아래 여덟 열의 이름과 순서를 정확히 지켜야 합니다.** 임의로 열을 추가하거나 순서를 바꾸면 기존 입력 계약에서 차단될 수 있습니다.

| worker_id | pay_item_code | amount | quantity | origin_pay_item_code | origin_from | origin_to | note |
|---|---|---|---|---|---|---|---|
| EP0001 | performance_bonus | 100000 | *(빈칸)* | *(빈칸)* | *(빈칸)* | *(빈칸)* | 가상 성과급 |

- `worker_id`: 보상 Excel과 **동일한 직원 ID**.
- `pay_item_code`: 급여항목 레지스트리에 등록된 영문 코드. 이 입력 원본에 허용되는 항목이어야 합니다.
- `amount` 또는 `quantity`: 계산에 필요한 금액 또는 수량 가운데 **적어도 하나**가 있어야 합니다.
- `origin_from`과 `origin_to`: 소급·귀속기간을 직접 지정할 때는 **두 값을 함께** 입력해야 합니다.
- `origin_pay_item_code`: 기존 항목의 정산·소급처럼 원래 항목을 추적해야 하는 경우 사용합니다. 모든 항목에서 필수인 것은 아닙니다.
- `note`: 사람이 읽는 메모입니다. 계산값을 대신하지 않습니다.

**흔한 실수:** 지급액을 적으면서 `pay_item_code`에 한글 이름을 써 넣는 것, 또는 보상 Excel의 `worker_id`와 서로 다르게 적는 것입니다.

## 4. 고용 사실과 근무시간 JSON은 어디서 가져오나요?

### 4.1 `employment-facts.json` — 재직·퇴직 정보

**완전한 JSON 배열 형식**의 가상 예시입니다.

```json
[
  {
    "worker_id": "EP0001",
    "employment_from": "2026-01-01",
    "employment_to": null
  },
  {
    "worker_id": "EP0002",
    "employment_from": "2026-01-01",
    "employment_to": null
  }
]
```

`employment_from`은 입사일, `employment_to`는 고용 종료일입니다. 현재 재직 중이라 종료일이 없다면 `null`을 사용할 수 있습니다. **Excel과 JSON의 `worker_id`는 모두 일치**해야 합니다. `null`을 문자열 `"null"`로 바꾸지 마세요.

### 4.2 `worktime-result.json` — 근무시간 결과

이 파일은 **Worktime에서 만든 결과 JSON을 받아 사용하는 것이 원칙**입니다. Payroll만 사용하는 경우에도 별도의 회사 근태 결과 파일을 준비해야 합니다. 예제 학습용으로는 프로그램에 포함된 `examples/payroll-standalone-demo/worktime-result.synthetic.json`을 복사해서 구조를 살펴볼 수 있습니다.

**중요:** 이 합성 예제는 실제 승인·근태 마감 데이터가 아닙니다. 실제 사용 시 출퇴근 사실과 계산기간을 검증하고, 미마감이면 그대로 **검토 상태**로 둡니다.

## 5. `payroll-config.json` — 어디를 수정하면 되나요?

**직접 새로 만들지 않아도 됩니다.** [사용자용 설정 틀](examples/payroll-config.user-template.json)을 `입력/payroll-config.json`으로 복사하면, 위 폴더 구성과 맞는 상대경로가 미리 채워져 있습니다.

```json
{
  "schema_version": "0.1",
  "payroll_period": "2026-10",
  "expected_worker_ids": ["EP0001", "EP0002"],
  "compensation_path": "compensation.xlsx",
  "payroll_input_path": "payroll-input.xlsx",
  "worktime_result_path": "worktime-result.json",
  "registry_path": "resources/pay-item-registry.json",
  "operating_config_path": "resources/operating-config.json",
  "company_policy_path": "company-policy.json",
  "legal_policy_path": "resources/policy/2026.json",
  "employment_facts_path": "employment-facts.json",
  "recurring_pay_item_codes": ["base_salary"]
}
```

| 바꾸는 항목 | 결과가 어떻게 달라지나요? |
|---|---|
| **`payroll_period`** | 대상 급여월. 예: `"2026-11"`. **기간 관련 원본 파일·정책 내용까지 자동 교체하지는 않습니다.** |
| **`expected_worker_ids`** | 이번에 계산할 직원의 독립 명부. Excel·근태 JSON의 직원 ID와 일치해야 함 |
| `compensation_path` | 어느 보상 Excel을 읽을지 결정 |
| `payroll_input_path` | 어느 월별 수당·공제 Excel을 읽을지 결정 |
| `worktime_result_path` | 어느 근무시간 JSON을 사용할지 결정 |
| `company_policy_path` | 어떤 회사별 급여 계산 정책 파일을 사용할지 결정 |
| `registry_path` | 어떤 급여항목 정의를 적용할지 결정 |
| `operating_config_path` | 어떤 원본 기간·지급 기준을 적용할지 결정 |
| `legal_policy_path` | 어떤 법정 기준 스냅샷을 적용할지 결정. **적합성 확인 필수** |
| `employment_facts_path` | 어느 직원 입·퇴사 JSON을 사용할지 결정 |
| `recurring_pay_item_codes` | 반복 계산할 급여항목 코드 목록. 레지스트리·회사 정책과 일치해야 함 |

**경로를 쓰는 쉬운 법:** 설정 파일과 같은 `입력` 폴더에 있는 `compensation.xlsx`는 이름만 적어도 됩니다. 하위 폴더에 있는 파일은 `resources/pay-item-registry.json`처럼 **슬래시(`/`)로 연결**합니다.

**JSON을 고칠 때:** 텍스트 값은 큰따옴표로 감싸고, 필드 사이에 쉼표를 넣되 마지막 항목 뒤 쉼표는 넣지 않습니다. `schema_version` 등 영문 키의 철자를 수정하지 마세요.

**근무시간 입력 방식을 바꾸려면:** `worktime_result_path`, `worktime_rows_path`, `worktime_closes_path` 가운데 **하나만** 사용합니다. 예제의 결과 JSON 방식이 가장 이해하기 쉽습니다. 승인된 근태 마감 Receipt가 없는 상태에서 `worktime_closes_path`를 임의로 만들어 사용하지 마세요.

## 6. `company-policy.json`에서는 무엇을 바꾸나요?

이 파일은 **회사별 계산 기준**입니다. [합성 급여 예제 생성 안내](README.md#2-첫-실행--payroll만으로-합성-급여-계산하기)의 `generate.py`가 만들어 주는 `company-policy.json`을 열어 형태를 살펴보면 됩니다. 아래 일부 항목의 의미는 다음과 같습니다.

| 설정 항목 | 뜻 | 수정 전 확인할 사항 |
|---|---|---|
| `proration.base_salary.method` | 기본급의 일할 계산 방식 | 회사 취업규칙·급여 규정 |
| `ordinary_wage.monthly_basis_hours` | 통상시급 산정에 쓰는 월 기준시간 | 근로제·계약·법령 |
| `worktime_pay.base_component_policy` | 연장·야간·휴일 관련 기본분 반영 기준 | 포괄·비포괄 및 지급 규정 |
| `amount_processing.unit` | 금액 최종 처리 단위 | 실제 지급 기준 |
| `amount_processing.method` | 절사·반올림 등의 처리 방식 | 원단위 처리 기준 |
| `amount_processing.remainder` | 절사 잔액·정산 처리 관련 정책 | 정산원장과 승인 절차 |

**이 항목은 단순한 화면 옵션이 아니라 급여 계산 결과를 바꾸는 기준**입니다. 가상 예제의 `monthly_basis_hours: 200` 등 수치를 모든 회사에 적용해도 된다는 뜻이 아닙니다. 승인된 회사 규정과 법정 기준을 확인하지 않았다면 임의로 수정해 실급여로 사용하지 마세요.

`operating-config.json`은 **급여월과 근무시간의 귀속기간 관계**를 정의합니다. 예제에는 Worktime 입력이 전월 기준(`carryover`)인 규칙이 있습니다. **`payroll_period`만 변경하고 근태 파일이 이전 달 자료 그대로인 상태**를 방치하지 마세요.

## 7. 한글 열 제목이 있는 기존 엑셀을 그대로 쓰고 싶어요

**급여 계산 모드의 두 `.xlsx` 파일은 위 고정 영문 헤더를 사용합니다.** 한글 제목을 그대로 두고 싶다면 별도 제공된 **원본 정규화 기능**을 이용합니다.

예시 파일은 프로그램의 `examples/source-mapping-demo/` 폴더에 있습니다.

```text
source-mapping-demo/
├── employees.csv          ← 사번, 급여ID, 입사일
├── schedule.csv           ← 직원코드, 근무일, 구분, 시작, 종료, 휴게분
├── attendance.csv         ← ID, 날짜, 출근, 퇴근, 휴게분
└── manifest.json          ← 어떤 한글 열을 어떤 표준 필드로 바꿀지
```

**CSV(`.csv`)는 Excel에서 저장할 때 UTF-8로 인코딩**하세요. 원본 정규화는 `.csv`, `.xlsx`, `.json` 형식을 지원합니다. `.xls`는 지원 목록에 포함되지 않습니다.

`manifest.json`에서 자주 수정하는 곳은 다음과 같습니다.

| 항목 | 수정하면 달라지는 것 |
|---|---|
| `sources.employees.path` | 읽을 직원명부 파일. `employees.csv` → `employees.xlsx` 등 |
| `sources.schedule.path` | 읽을 근무표 파일 |
| `sources.attendance.path` | 읽을 출퇴근 기록 파일 |
| `fields.employee_id.source` 등 `source` | 원본 Excel/CSV **열 제목**과 표준 직원 ID 등을 연결 |
| `value_map` | 원본의 `근무`·`휴무`·`휴일` 등의 값을 `WORK`·`OFF`·`HOLIDAY`로 연결 |
| `sheet` | 원본 `.xlsx`에서 **특정 시트 이름**을 지정할 때 사용. 없으면 활성 시트 |
| `header_row` | 원본 `.xlsx`의 열 제목이 위치한 행 번호. 생략 시 1행 |

예를 들어 기존 Excel에 `"근무일자"`라는 제목이 있다면, `manifest.json`의 해당 필드 매핑을 `"source": "근무일자"`로 수정합니다. **원본 열 제목과 공백까지 정확히 일치**해야 합니다. `path`가 `.xlsx`면 실제 파일도 그 이름으로 저장해야 합니다.

**오해하지 마세요:** 원본 정규화 결과가 자동으로 `compensation.xlsx`·`payroll-input.xlsx`를 만들어 급여 계산까지 이어 주는 것은 아닙니다. **정규화와 급여 계산은 별도 단계**이며, 각각 필요한 파일 계약에 맞춰 준비해야 합니다.

## 8. 결과를 어디서 확인하나요?

새 `결과-01` 폴더에 다음 파일이 생성될 수 있습니다.

| 결과 파일 | 먼저 확인할 부분 |
|---|---|
| **`payroll-calculation.xlsx`** | `Summary`: 직원별 합계 / `Calculation Detail`: 급여항목별 계산 / `Validation`: 검토 사항 |
| **`payroll-review.xlsx`** | `Run Summary`: 전체 상태 / `Worker Coverage`: 직원별 계산 여부 / `Review Required`: 검토할 오류 |
| `payroll-calculation.json` | 정확한 계산 결과, 다른 프로그램으로 넘길 자료 |
| `payroll-review.json` | 직원별 오류 코드·미처리 자료 |
| `policy-resolution.json` | 실제 선택된 정책·시나리오 |

**`REVIEW_REQUIRED`라고 표시되어도 `payroll-calculation.xlsx`가 생성되어 있으면 검토용 계산이 수행된 경우일 수 있습니다.** 반대로 `BLOCKED`라면 계산 없이 `payroll-review.xlsx`만 생길 수 있습니다. **결과 파일의 존재·상태·오류 사유를 함께** 보세요.

모든 금액은 검토용이며, 실제 지급 전에는 근태 승인·급여 확인·세금·사회보험·회계 검토를 별도로 해야 합니다.

## 9. 자주 묻는 질문

**Q. 시트 이름을 `급여대장`으로 바꿔도 될까요?** 계산용 Excel은 시트 이름보다 **활성 시트**가 중요합니다. 다만 해당 시트의 **1행 영문 헤더와 순서**를 반드시 지켜야 합니다.

**Q. 고정급 직원은 `payroll-input.xlsx`를 생략해도 되나요?** 아니요. 기존 급여 계산 계약은 `payroll_input_path`를 요구합니다. 변동 지급이 없다면 **빈 데이터 행을 가진 정확한 헤더의 Excel**이 가능한지 원본 계약을 먼저 확인하고, 파일 자체를 삭제해서는 안 됩니다.

**Q. 지급액이 0원이나 공란이면 자동으로 기본급을 넣어 주나요?** 기존 계산 정책과 급여항목 설정에 따라 달라집니다. **누락을 임의로 기본값이나 승인으로 바꾸지 않습니다.**

**Q. 회사 정책 파일은 어디서 얻나요?** 실제 회사 규정을 근거로 작성해야 합니다. 예제는 JSON의 **형식을 보여줄 뿐 정책의 적법성·적합성을 보증하지 않습니다.**

**Q. 월만 바꿨는데 지난달 수당이 계산돼요.** `payroll_period`와 `operating-config.json`의 지급·귀속기간 규칙, `payroll-input.xlsx`의 원본 기간을 함께 확인하세요.

**Q. 업무에 바로 사용할 수 있나요?** 내부 검토용 계산과 차이 확인에는 활용할 수 있지만, **이 도구만으로 급여를 확정하거나 신고·송금하지 마세요.** 회사별 정책과 계산 결과의 별도 검토가 필요합니다.
