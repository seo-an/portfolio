# Worktime Calculator — 독립 모듈 v0.5.0 (이전 엔진 유지)

## Worktime 0.5.0 — 출퇴근 모드와 물리적 방향 분리

CAPS·세콤·KT 원본 업체별 컬럼 해석은 Gearbox 등 비공개 정규화 어댑터가 담당합니다.
공개 Bhandara는 정규화된 `sources.access_events`의 `mode`와 `direction`을
독립적인 필드로 사용합니다.

- `mode=CLOCK_IN/CLOCK_OUT`: 명시적 출퇴근 인증. 내부 외출 구간이나 휴게로 사용하지 않습니다.
- `mode=ACCESS`: 일반 출입 인증. `direction=UNKNOWN`이면 IN/OUT을 추측하지 않고 검토합니다.
- `mode=OUTING/RETURN`: 명시적 외출·복귀 모드의 의미로만 구간을 연결할 수 있습니다. 물리적 단말기 방향은 여전히 `UNKNOWN`이며 자동으로 휴게를 인정하지 않습니다.
- `mode=DISARM`: 경비 해제. 출퇴근·휴게 판정에 사용하지 않습니다.
- `auth_status=FAILED/UNKNOWN`: 인증된 출입으로 계산하지 않으며 검토 사유를 보존합니다.
- 선택적 `sources.attendance_candidates`의 최초 일반 출입 추정값 `INFERRED_FIRST_ACCESS`는 근태 승인이나 급여 계산에 반영하지 않습니다. `confirmed=false`가 필수입니다.
- 정규화 과정의 실패/미매핑/중복 검토 내용이 `access_normalization_review.issues`로 제공되면 전체 상태가 `REVIEW_REQUIRED`이며 승인·마감하지 않습니다.

업체별 출입기·사원번호 매핑·구형 `.xls` 파일 파싱은 공개 모듈에 포함하지 않습니다.
입력 Excel을 추가할 필요는 없고, 검토 결과는 `break-compliance.json`과
`worktime-review.xlsx`의 `Break Compliance` 시트에서 확인합니다.


## Worktime v0.4.0 — CAPS 출입 이벤트 기반 휴게 검토

`time-events.xlsx` 같은 새 입력 시트를 만들지 않습니다. Worktime은 원래 사용하던
`work-schedule.xlsx`와 `attendance.xlsx`를 유지하며, **실제 CAPS 수집 및 업체별
코드 매핑은 Gearbox 등 원본 정규화 담당**이 수행합니다. 공개 계산기는
정규화된 `normalized-input.json`의 선택적 `sources.access_events`만 읽습니다.

- 근무표에는 `break_min` 외에 선택적 `break_start` / `break_end` 열을 추가할 수 있습니다. 해당 구간은 **예정 휴게**일 뿐 실제 휴게 증빙이 아닙니다.
- 출입기 `OUT → IN`으로 확인한 구간이 예정 휴게와 일치하면 `PLANNED_BREAK_CANDIDATE`입니다. 그 자체로 휴게를 확정하지 않습니다.
- 상위 정규화에서 `REST_CONFIRMED` + `free_use_confirmed=true` + `verification_ref`가 제공된 구간만 법정 휴게에 합산합니다.
- `BUSINESS_OUTING`은 업무 외출, `PERSONAL_OUTING`은 개인 외출로 표시하지만 휴게로 자동 차감하지 않습니다.
- `PASS_VERIFIED`: 확인된 휴게가 법정 최소 이상. `SHORTFALL_DETECTED`: 휴게 기록의 **완전성까지 별도로 확인**한 경우에만 확인된 부족분 산출. 그 외 `REVIEW_REQUIRED`.
- 2026-12-10 시행하는 정확히 4시간 근로자의 명시적 요청 예외는 서면 등 확인 가능한 근거가 없는 한 적용하지 않습니다.
- 결과: 기존 `worktime-review.xlsx`에 `Break Compliance` 시트, 별도 `break-compliance.json` 검토용 sidecar. 기존 `worktime-result.json`의 원래 근로시간 엔진과 임금 마감 계약은 유지합니다.
- `access_events`를 전달하지 않은 기존 Excel/JSON 실행은 기존 산출물 구성을 유지합니다. **CAPS 원본을 자동으로 가져오는 기능은 아직 없으며**, 출입이 없다고 사내 휴게가 없었다고 추정하지 않습니다.
- `shared_excel.py`의 근태 `break_min` 공란을 무조건 0분으로 바꾸지 않습니다. 공란에 대한 근로시간은 기존 엔진에서 검토/오류로 처리합니다.

단독 실행과 Gearbox 연결은 여전히 별개이며, **실제 근로시간·Payroll 금액을 새로운 휴게 판정만으로 임의 수정하지 않습니다**. 확인된 휴게와 근태표 `break_min`이 충돌하면 `REPORTED_BREAK_REQUIRES_RECONCILIATION`으로 표기합니다.

### 정규화된 CAPS 이벤트 계약 (개발자 참고)

기존 `normalized-input.json.sources` 아래에 선택적으로 다음 묶음을 붙입니다.

```json
"access_events": {
  "rows": [
    {
      "employee_id": "E001",
      "worker_id": "EP0001",
      "work_date": "2026-11-13",
      "event_id": "DEMO-EXIT-001",
      "event_time": "12:00",
      "direction": "OUT",
      "classification": "REST_CONFIRMED",
      "free_use_confirmed": true,
      "verification_ref": "SYNTHETIC-REVIEW-001"
    },
    {
      "employee_id": "E001",
      "worker_id": "EP0001",
      "work_date": "2026-11-13",
      "event_id": "DEMO-ENTRY-001",
      "event_time": "13:00",
      "direction": "IN",
      "classification": "UNKNOWN"
    }
  ],
  "source_sha256": "실제 원본 정규화 단계에서 생성한 해시",
  "lineage": [
    {"status": "ACCEPTED", "row_number": 2, "issue_codes": []},
    {"status": "ACCEPTED", "row_number": 3, "issue_codes": []}
  ]
}
```

위의 `REST_CONFIRMED`와 `verification_ref`는 가상 검증 상태 예시이며, CAPS 리더가 자동으로 제공한 판정이 아닙니다. 실제로는 검토자가 승인·확인한 증빙이 있을 때만 이 값을 보내야 합니다. `break_verifications` 설정에서 `coverage_complete: true`를 선언하려면 `evidence_ref`가 필수이며, 실내 휴게까지 확인된 경우에만 사용합니다.

**법령 참조:** 근로기준법 제54조(2026-11-13 현재)와 2026-12-10 시행 예정 개정. 법률 판정·금전 확정은 사람이 수행합니다.


## 외부 인력 포함 Worktime Excel 어댑터 (선택 기능)

공통 `common/id-map.xlsx`에 `EXTERNAL` 시트(`worker_id`,
`security_id`)를 선택적으로 추가할 수 있습니다. 기존 직원 `ID_MAP`
시트와 `employee.xlsx`는 직원 전용으로 **변경하지 않습니다**.

동일한 `worktime/work-schedule.xlsx`, `worktime/attendance.xlsx`
첫 시트에 `worker_id` 열을 선택적으로 추가합니다.

- 직원 행: `employee_id`만 기입, 직원 ID_MAP으로 연결.
- 외부 행: `employee_id` 공란, `worker_id` 기입, `EXTERNAL`
  시트에 등록된 ID만 허용.
- 둘 다 기입/둘 다 공란/미등록 ID/직원과 겹치는 ID·출입기 ID는
  `InputLayoutError`로 차단.
- 원본 출처: 직원 Excel, 근무표, 근태표 및 `id-map.xlsx`
  SHA-256 기록. 직원 80명만 있는 기존 입력도 그대로 지원.
- 외부 근무제의 검토 표시는 `EXTERNAL_SERVICE_HOURS_REVIEW_ONLY`로
  생성하며, 근로소득·법정 기준 또는 용역 청구를 승인하지 않음.
- `shared_excel.py` 및 `external_identity.py`에만 신규 입력 로직;
  **이전 Worktime 계산 엔진, Payroll·PTO 코드와 의존성 없음**.

Worktime이 만든 `worktime-result.json`은 이미 지원하는 Payroll
`Contracts`의 외부 `worker_id`와 직접 연결될 수 있습니다. 직원 80명과
외부 근로시간을 같은 파일에서 계산했더라도 Payroll 직원 급여의 대상
`expected_worker_ids`는 80명으로 유지됩니다.

[직접 Excel 준비하는 방법](RUNBOOK.md) ·
[가상 직원 80명+외부 시간제 2명 통합 테스트](../tests/test_worktime_external_shared_excel.py).

## 공통 Excel 고정 경로 자동 입력

`bhandara/data/input/{common,worktime}`의 Excel을 자동으로 읽어
원본 해시·행번호가 있는 정규화 입력을 만들고 기존 계산기를 실행합니다.

```bash
python run.py bhandara worktime-calculator --period 2026-06
```

기존 `run.py calculate --normalized ... --config ...`의 소스는
바이트 단위로 보존되었으며, Excel 어댑터는
`shared_excel.py`에 독립적으로 추가했습니다.
[80명 실물 샘플](../examples/sample/input/).

> **실제 사용하려는 분:** [근무시간 계산기 RUNBOOK](RUNBOOK.md)에 입력 JSON의 준비 방법·직원별 필드·기간·승인 참조 설정·Excel을 직접 넣을 수 없는 한계를 설명했습니다. **이 README는 개발자·설치 담당자용 기술 및 검증 문서**입니다.


**상태 (2026-11-10):** 기존 Worktime 코드 10개 파일의 바이트 동일성 및 합성 JSON·XLSX 결과를 확인해 [Portfolio PR #6](https://github.com/seo-an/portfolio/pull/6)을 병합했다. 이후 **Base + Worktime만 설치한 단독 실행 및 상호배타 테스트**도 Hermes 서버에서 PASS했다. 계산 정책·예외 처리 개선은 별도 프로젝트에서 다룬다.

## 이전 범위

- 원본: `seo-an/agent-config/gearbox/gear/worktime-calculator/`
- 이전: `seo-an/portfolio/bhandara/worktime-calculator/`
- **그대로 복사한 파일 10개:** `functions/` 7개, 기존 `run.py`, `contracts/worktime-result.json`, `examples/standalone-config.demo.json`.
- [migration-manifest.json](migration-manifest.json)에 각 원본 Git blob SHA를 기록했다. `unittest`는 복사본의 **원본 바이트 단위 동일성**을 검증한다. 이전 중 근태 계산식·검토·오류 처리의 내용은 수정하지 않는다.
- 최상위 `portfolio/run.py`에 `bhandara worktime-calculator` 명령의 **단순 전달 기능만** 추가했다. 기존 Worktime `run.py calculate`의 인자·결과·종료 코드가 그대로 사용된다.
- 외부 네트워크·Hermes·Slack·Drive·인증은 계산 모듈의 요구사항이 아니다. 승인된 Python 3.12+ 및 `openpyxl==3.1.5`를 사용한다. 설치는 `requirements.txt` 하나로 관리한다.

## Worktime 모듈만 내려받기

**다른 계산기 없이** `bhandara/common/`(공통 Base)과 `bhandara/worktime-calculator/`, 최상위 실행·설치 파일만 있으면 된다. Git으로 필요한 파일만 받는 예시:

```sh
git clone --depth 1 --sparse https://github.com/seo-an/portfolio.git bhandara-worktime
cd bhandara-worktime
git sparse-checkout set bhandara/common bhandara/worktime-calculator

uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
```

GitHub ZIP으로 직접 복사할 때는 `run.py`, `install.py`, `requirements.txt`, `bhandara/__init__.py`, `bhandara/common/`, `bhandara/worktime-calculator/`만 **원래 위치 그대로** 보존한다. **Worktime 폴더 하나만 복사하면 안 된다.** Base는 필수지만 PTO·Payroll 설치는 필요 없다.

### 제공된 합성 JSON으로 즉시 실행

이전 테스트에서 사용한 것과 같은 구조의 가상 직원 두 명(`E01`, `E02`)에 대한 입력을 `examples/`에 별도 제공한다. **실제 근무 승인 기록이 아니며 오직 독립 실행 확인용**이다.

```sh
.venv/bin/python run.py bhandara worktime-calculator \
  --normalized bhandara/worktime-calculator/examples/normalized-input.demo.json \
  --config bhandara/worktime-calculator/examples/worktime-config.approved.demo.json \
  --output-dir /tmp/bhandara-worktime-demo-result
```

기대되는 정상 예제 상태는 `CALCULATED_UNCLOSED`와 종료 코드 `0`이다. **`approved`라는 예제 파일명의 뜻은 승인 필드가 채워진 합성 입력을 사용한다는 것일 뿐, 실제 승인이나 근태 마감이 완료됐다는 의미가 아니다.** 출력 대상 경로가 이미 존재한다면 새 디렉터리 이름을 지정한다.

## 입력 계약 유지

**원본 Excel을 직접 정규화하지 않는다.** 기존 Worktime 계산기는 이미 정규화된 `normalized-input.json`과 `worktime-config.json`을 받는 구조였다. 이전 후에도 **그대로 유지**한다.

| 입력 | 원래 계약 |
|---|---|
| `normalized-input.json` | Source Mapping 산출물, `schema_version: "0.1"`, 직원·스케줄·근태 `sources`와 `lineage` |
| `review-report.json` | 선택: `normalized-input.json`의 **같은 디렉터리**에 있으면 읽어서 검토 결과에 반영 |
| `worktime-config.json` | `schema_version: "0.1"`, 기간, Worktime 근로제·규칙, 승인 참조 및 원본 이름 매핑. 복사된 `examples/standalone-config.demo.json`은 설정 구조 참고용 |
| `--output-dir` | 존재하지 않는 **새 비공개 폴더**. 기존 결과 덮어쓰기 금지 |

실제 직원 ID·근무시간·검토 내역이 결과에 포함될 수 있으므로 입력·출력은 **Git 저장소 밖의 비공개 디렉터리**에 둔다. 합성 데모를 제외하고 Git이나 Slack에 업로드하지 않는다.

### 공개 Portfolio 진입점

```sh
cd /path/to/portfolio

python run.py bhandara worktime-calculator \
  --normalized /private/normalized/normalized-input.json \
  --config /private/worktime-config.json \
  --output-dir /private/worktime-result-01
```

### 복사한 원래 Worktime CLI 직접 실행

```sh
python bhandara/worktime-calculator/run.py calculate \
  --normalized /private/normalized/normalized-input.json \
  --config /private/worktime-config.json \
  --output-dir /private/worktime-result-02
```

두 명령은 **동일한 계산 함수·보고 함수**를 실행한다. `normalized-input.json`을 만드는 기존 Payroll Source Mapping CLI는 공개 Worktime 모듈의 일부가 아니다. 정규화기 신규 구현 또는 Excel 입력 지원 추가는 이번 이전 범위에서 제외한다.

## 산출물과 원래 종료 코드

- `worktime-result.json`: 직원/날짜별 근무시간 계산 사실, 원본 출처·후보 적용범위, `finalizable=false`, `coverage_verified=false`, `close_receipt=null`.
- `worktime-review.json`: 검토·오류/누락 상태, 근거·원본 행 번호.
- `worktime-review.xlsx`: 기존 `Summary`, `Daily Worktime`, `Processing`, `Review Required` 시트.

| 종료 코드 | 기존 Worktime CLI 의미 |
|---|---|
| `0` | `CALCULATED_UNCLOSED` |
| `2` | `REVIEW_REQUIRED`, `BLOCKED`, 유효하지 않은 호출/입력 |

상태가 `CALCULATED_UNCLOSED`여도 **마감·승인·급여 정산을 의미하지 않는다**. 기존 `worktime_close.py`는 코드를 그대로 이전했지만 공개 CLI로 마감 기능을 새로 노출하지 않는다.

## 이전 검증만 수행

```sh
# portfolio 저장소 루트, uv 관리 Hermes Python 또는 동일 의존성 환경
python -m unittest discover -s bhandara/tests -p 'test_worktime_migration.py' -v
python -m unittest discover -s bhandara/tests -p 'test_*.py' -v
python install.py --check
```

첫 테스트는 (1) 원본 10개 Git blob SHA의 완전 동일성, (2) 원본 Worktime 독립 실행 진입점과 Portfolio 명령의 **같은 합성 입력에 대한 JSON·XLSX 셀 값 및 종료 코드 일치**만 검사한다. 기존 계산기의 정책·오류 상황을 재평가하거나 계산식을 수정하지 않는다.

서버에서 **진짜 원본 Gearbox CLI와 새 Portfolio CLI**의 비교는 같은 `normalized-input.json`과 설정으로 실행한 결과를 나란히 보관하고, 공개 Base의 `compare-golden --profile strict-json`으로 각각의 JSON을 비교한다. 원본 Gearbox `test_worktime_cli.py`의 합성 데이터 경로를 사용하면 실데이터 접근이 필요 없다.

```sh
python run.py compare-golden --profile strict-json \
  --expected /private/legacy/worktime-result.json \
  --actual /private/public/worktime-result.json

python run.py compare-golden --profile strict-json \
  --expected /private/legacy/worktime-review.json \
  --actual /private/public/worktime-review.json
```

**2026-11-10 서버 이전·상호배타 검증 PASS.** 기존 계산기와 공개 코드의 동일 합성 입력 결과를 확인했다. 이는 새 기능/정책/법적 적합성 검증이 아니다.
