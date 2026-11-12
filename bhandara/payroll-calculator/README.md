# 급여 계산기(Payroll Calculator) — 독립 실행 모듈 v0.3.1

## 공통 Excel 고정 경로 자동 입력

`bhandara/data/input/{common,payroll}`의 직원·ID 매핑·연봉/월급/시급/일급 **계약금액 Excel**을 검증하고
포함된 월 고정수당을 분리해 기본급을 산정합니다. 기존 Payroll 계산식은 유지합니다.

```bash
python run.py bhandara payroll-calculator --period 2026-07
```

별도 Worktime 설치 없이 미마감 Worktime 결과 JSON을 받아
독립 실행할 수 있습니다. 기본 인계는 현재 Worktime Excel의 해시를 확인하고,
원본이 바뀌면 재계산을 요구합니다.
[80명 실물 샘플](../examples/sample/input/).

> **실제 사용하려는 분:** [급여 계산기 RUNBOOK](RUNBOOK.md)에 `pay-contract.xlsx`·`pay-contract-components.xlsx`·`payroll-input.xlsx` 작성법, 활성 시트, 정확한 헤더, 폴더 구성 및 JSON에서 바꿀 항목을 모아 뒀습니다. [바로 수정할 수 있는 급여 설정 JSON 틀](examples/payroll-config.user-template.json)도 제공하며, **이 README는 개발자·설치 담당자용 기술·코드 계약·검증 문서**입니다.


**기존 Gearbox 급여 계산기를 공개 저장소에서 독립 실행하도록 이전한 모듈**이다. 보상 정보, 월별 급여 입력, 근무시간 결과, 급여항목·회사 정책을 이용해 **검토용 급여 계산 결과**를 만든다.

> **2026-11-10 이전·검증 완료.** 원본 Payroll 파일 85개를 보존했고, 경로 변경은 원본 해시로 역검증했다. 합성 데이터를 이용한 계산·정규화 진입점 검증, Gearbox 원본 회귀, **Base + Payroll만 설치한 상호배타 테스트**, 다른 위치의 Worktime JSON 인계를 모두 통과했다. 기존 급여 계산식, 지급·공제 정책, 예외처리 기능은 수정하지 않았다.

이 모듈은 **사회보험료·원천세 확정, 급여 지급 승인, 회계 장부 확정, 실제 송금**을 수행하지 않는다. 결과에 금액이 계산되더라도 `finalizable=false`, `ledger_committed=false`이다. 기존 운영 Gearbox Payroll Workflow를 교체하지 않는다.

## 계약금액 기본급 어댑터의 정확한 범위

신규 `contract_adapter.py`는 기존 Payroll 계산 엔진 **앞단**에서 다음 데이터를 만듭니다.

- `ANNUAL`: 연 총액 / 12 − 계약에 포함된 월 고정수당. **12회 균등분할 전제**를 검토 코드로 남기며 다른 지급구조는 미지원.
- `MONTHLY`: 월 총액 − 계약에 포함된 월 고정수당.
- `HOURLY`: 계약 시급 × 검토 대상 Worktime 일반 근로시간.
- `DAILY`: 계약 일급 × 계약상 기준 근무시간을 충족한 일수.
- `SERVICE`: 별도 `service-work-records.xlsx`의 시급×시간 또는 일급×일수로 **용역대가 추정액을 검토용으로 계산**하며 **직원 Payroll 계산에는 포함하지 않음**.

시급·일급의 **연장·야간·휴일 가산수당과 유급주휴는 아직 이 어댑터에서 미계산**입니다.
이들을 월 고정급 통상시급 환산에 임의로 넣지 않도록 별도 Worktime 입력 경로로 제외하고,
`contract-basis-review.json`에 `NONMONTHLY_PREMIUM_NOT_CALCULATED`,
`WEEKLY_PAID_HOLIDAY_NOT_RESOLVED`를 기록합니다. 실제 지급액을 의미하지 않습니다.

새 계약 입력이 있으면 `contract-derived-compensation.xlsx`를 생성해 기존 엔진에 전달합니다.
새 계약 파일이 없으면 기존 `compensation.xlsx`와 수동 JSON 방식으로 실행합니다.
[실물 80명 샘플](../examples/sample/input/) 및 [쉬운 사용 안내](RUNBOOK.md)를 참고하세요.

## 1. Payroll 모듈 하나만 설치하기

필요한 파일 구성은 다음과 같다.

```text
bhandara-payroll/
├── run.py
├── install.py
├── requirements.txt
└── bhandara/
    ├── __init__.py
    ├── common/                 # 필수: 공통 Base와 Worktime close 검증 계약
    └── payroll-calculator/    # 급여 계산기
        ├── run.py
        ├── functions/
        ├── resources/         # 급여항목 레지스트리·2026년 기준 정책
        ├── examples/          # 합성 테스트 자료
        └── module.json
```

PTO·Worktime 폴더를 포함할 필요가 없다. Payroll이 승인된 근무시간 마감 영수증을 확인하는 경우에도 **Base에 포함된 원본 동일 검증 함수**를 사용한다. 이 구조를 실제 격리 테스트에서 확인했다.

Git이 있으면 필요한 폴더만 내려받는다.

```sh
git clone --depth 1 --sparse https://github.com/seo-an/portfolio.git bhandara-payroll
cd bhandara-payroll
git sparse-checkout set bhandara/common bhandara/payroll-calculator

uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt

.venv/bin/python install.py --check
```

Python 3.12 이상을 지원하며 Hermes 검증 버전은 **3.14.9**다. 외부 의존성은 최상위 `requirements.txt`에서 관리한다. Windows는 `.venv\Scripts\python.exe`를 사용한다. Python 패키지를 설치할 때 시스템 환경을 직접 수정하지 말고 가상환경을 사용한다.

GitHub ZIP을 내려받아 필요한 파일만 옮겨도 되지만 위 트리의 **상대 경로를 그대로 유지**해야 한다. **Payroll 계산기 폴더 하나만 복사해서는 실행할 수 없다.**

## 2. 첫 실행 — Payroll만으로 합성 급여 계산하기

모듈에 **가상 직원 2명의 근무시간 결과 JSON**과 합성 급여파일 생성기가 포함돼 있다. 별도 Worktime 설치 없이 Payroll 단독 실행을 확인할 수 있다.

```sh
# 1. 제공된 합성 Worktime JSON을 참조해 급여 입력·정책 파일 생성
.venv/bin/python \
  bhandara/payroll-calculator/examples/payroll-standalone-demo/generate.py \
  --worktime-result \
  bhandara/payroll-calculator/examples/payroll-standalone-demo/worktime-result.synthetic.json \
  --output-dir /tmp/bhandara-payroll-demo-input

# 2. 계산 실행: 정상적으로 계산돼도 검토 전용이므로 종료 코드 2
.venv/bin/python run.py bhandara payroll-calculator \
  --config /tmp/bhandara-payroll-demo-input/payroll-config.json \
  --output-dir /tmp/bhandara-payroll-demo-result
```

예제 출력 폴더는 새 경로여야 한다. 동일한 예제를 다시 실행한다면 새로운 이름을 지정한다. 예제 입력의 직원 ID `EP0001`, `EP0002`와 금액은 **가상 데이터**다.

계산이 성공해도 `Payroll: REVIEW_REQUIRED (review only, not finalized)`가 표시되고 프로세스 종료 코드는 **2**다. 이때 계산 성공 여부는 `payroll-calculation.json` 생성과 `payroll-review.json`의 내용으로 확인해야 한다. 종료 코드 2만으로 실패라고 판단하지 않는다.

## 3. 원본 자료 정규화 기능

기존 원본 CSV/XLSX/JSON의 열 이름과 값 매핑을 `manifest.json`으로 정의하면, Payroll에 포함된 `normalize` CLI로 정규화할 수 있다. **Worktime 모듈을 설치할 필요는 없다.**

```sh
.venv/bin/python run.py bhandara payroll-calculator \
  --operation normalize \
  --input-dir bhandara/payroll-calculator/examples/source-mapping-demo \
  --output-dir /tmp/bhandara-payroll-normalized
```

기본 설정은 입력 폴더의 `manifest.json`을 사용한다. 별도 설정을 사용하려면 `--manifest /private/mapping/manifest.json`을 지정한다. 정규화 결과가 `READY_FOR_CALCULATION`이면 종료 코드 `0`, 검토·차단이면 `2`다.

**구분할 점:** Payroll의 원본 정규화 기능이 포함되어 있다고 해서 Worktime의 원본 Excel 직접 입력 기능이 생긴 것은 아니다. Worktime은 여전히 별도로 정규화한 `normalized-input.json`을 받는다.

### 범용 입력 변환 기능의 Common 분리

2026-11-12 이후 공개 계산기의 정규화 처리는 다음처럼 역할을 구분합니다.

| 위치 | 담당 기능 |
|---|---|
| `bhandara/common/io/tabular.py` | CSV·XLSX·JSON 읽기, 일반 헤더 구조 검사, 상대 입력 경로 범위 제한, 물리적 행번호 보존 |
| `bhandara/common/validation/scalars.py` | 날짜·시간·정수·소수·불리언 등 범용 값 변환 |
| `bhandara/payroll-calculator/functions/source_mapping.py` | 명시적 필드 별칭과 `value_map` 적용, 데이터 누락·중복 검토, 원본 행번호·SHA·거절 사유 연결 |
| Gearbox의 회사별 Adapter/설정 | 어떤 원본 컬럼·코드에 어떤 의미를 부여할지 결정, 외부 인증·가명화·운영 승인 |

**공통 입력 변환기는 특정 회사나 급여항목 이름을 알지 못합니다.** Payroll을 독립 설치한 경우에는 기존처럼 `manifest.json`에 원하는 매핑 규칙을 직접 지정합니다. Gearbox가 입력을 전달할 때는 Gearbox 측 규칙으로 선택한 매핑 계약을 사용합니다.

이 변경은 **CSV/XLSX/JSON의 원래 읽기 방식과 Payroll 정규화 CLI의 결과 계약을 유지하기 위한 코드 분리**입니다. 다른 계산기로의 자동 전환, 지급액 확정, 오류 무시 기능은 추가하지 않습니다. 최초 Gearbox 소스 이관의 SHA 기록은 `migration-manifest.json`에 남기고, 이후 변경한 정규화 파일은 `post-migration-refactors.json`으로 별도 추적합니다.

---
## 4. 실제 입력 파일과 설정

계산 모드에서는 `payroll-config.json`(`schema_version: "0.1"`)에 **모든 자료 경로를 명시**한다. [기존 설정 양식](examples/payroll-standalone-config.example.json)은 필드 계약 참고용으로, 배포 서버의 오래된 `gearbox/` 경로 대신 현재 실제 파일 경로를 입력해야 한다.

| 설정 키 | 내용 |
|---|---|
| `payroll_period` | 계산 대상 급여월(`YYYY-MM`) |
| `expected_worker_ids` | 계산 대상 직원의 `worker_id` 목록 |
| `compensation_path` | 직원별 적용기간이 있는 보상 Excel |
| `payroll_input_path` | 해당 월 지급·공제·조정 입력 Excel |
| `employment_facts_path` | 재직·퇴직 등 적용 사실 JSON |
| `registry_path` | 급여항목 정의 JSON. 공개본 `resources/pay-item-registry.json` 사용 가능 |
| `operating_config_path` | 급여월과 원본 기간에 대한 운영 설정. 공개본 `operating-config.json` 참조 |
| `company_policy_path` | 회사별 일할 계산·통상임금·반올림 등 정책 JSON |
| `legal_policy_path` | 해당 시점의 법정 계산 기준 JSON. 공개 예제 `resources/policy/2026.json`은 **원본 스냅샷**이며 현행 법령 검증을 대체하지 않음 |
| `worktime_result_path` | Worktime이 내보낸 근무시간 결과 JSON(인계 방식 중 하나) |
| `recurring_pay_item_codes` | 반복 적용할 급여항목 코드 목록 |

상대 경로는 기존 계산기 입력 계약에 따라 급여 설정 파일 위치를 기준으로 처리한다. `--scenario-id`를 지정해 기존 정책 카탈로그의 계산 시나리오를 선택하는 기능도 그대로다.

원본 Worktime 인계 방식은 `worktime_result_path`, `worktime_rows_path`, `worktime_closes_path` 중 **하나만** 선택한다. 복수 지정하거나 승인되지 않은 근무시간을 임의로 '확정'으로 변경하면 안 된다.

## 5. Worktime과 분리된 채로 JSON 파일만 인계하기

Worktime과 Payroll을 **서로 다른 설치 폴더**에 둬도 된다. 두 프로그램은 별도 프로세스로 실행하고 아래 파일만 전달한다.

```text
Base + Worktime                              Base + Payroll
   │                                              │
   └─ worktime-result.json ── 파일 경로 지정 ──>  └─ payroll-config.json
                                                       │
                                                       └─ 급여 검토용 산출물
```

급여 설정 안에 다음 항목을 포함한다.

```json
{
  "worktime_result_path": "/private/worktime/result-01/worktime-result.json"
}
```

이는 설정 파일의 **한 부분만 보여주는 예**다. 나머지 필수 경로 및 정책과 대상 급여월도 지정해야 한다. Worktime 결과의 `status`가 `REVIEW_REQUIRED`, `close_receipt=null`이면 Payroll도 **미마감 사실값으로 계산하는 검토용 실행**이며 자동 승인·Ledger 반영은 발생하지 않는다.

이 JSON 인계는 **Worktime 폴더 없는 Payroll 설치**에서 합성 테스트를 통과했다. 세 계산기의 독립성 기록은 [상호배타 검증](../MODULE-ISOLATION.md) 참고.

## 6. 실행 결과와 종료 코드

| 실행 종류 | 상태·종료 코드 | 판정 방법 |
|---|---|---|
| `normalize` 성공 | `READY_FOR_CALCULATION`, 종료 `0` | 입력 가공 보고서 확인 |
| `normalize` 검토·오류 | 종료 `2` | `review-report.json`의 원인 확인 |
| `calculate` 정상 계산 | **`REVIEW_REQUIRED`, 종료 `2`** | `payroll-calculation.json` 및 `payroll-review.json` 생성 확인 |
| `calculate` 계약·계산 오류 | `BLOCKED`, 종료 `2` | 검토 JSON/XLSX를 통해 원인 확인 |

정상 계산 시 기존 출력 파일은 다음과 같다.

- `payroll-calculation.json` / `payroll-calculation.xlsx`: 계산 금액·항목·계산 근거를 담은 **임시 계산 결과**.
- `payroll-review.json` / `payroll-review.xlsx`: 대상 직원 누락·오류·검토 필요 항목.
- `policy-resolution.json`: 계산에 적용된 정책 선택 내역.

계약·계산 오류로 중단된 경우 검토용 JSON/XLSX 두 개만 생성될 수 있다. 모두 **최종 급여대장·원천세 신고 파일·회계 승인 전표가 아니다.**

## 7. 이전 이력과 원본 보존

- [원본 이전 기록](MIGRATION.md) 및 [원본 해시 표](migration-manifest.json)에 최초 원본 파일 85개와 참조 경로만 변경한 코드 내역을 보관한다.
- 실제 사용을 위한 README·RUNBOOK은 **현재의 한국어 문서가 정본**이다.
- Gearbox 원본 문서의 **바이트 동일 사본**은 `legacy-source-docs/README.md`, `legacy-source-docs/RUNBOOK.md`로 보존했다. 이전 검증 테스트의 원본 해시와 파일 개수 85개는 유지된다. 이 사본의 이전 서버 경로·운영 상태는 **현재 사용 설명이 아니다**.
- 계산 함수·정책·예외 로직 변경은 이번 프로젝트에서 하지 않았다. 개선은 이후 별도 프로젝트에서 설계한다.

## 8. 테스트와 개인정보 보호

```sh
# 전체 portfolio를 내려받은 경우, 해당 가상 자료만 사용
.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_payroll_migration.py' -v

.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_module_isolation.py' -v

.venv/bin/python install.py --check
```

계산기 하나만 sparse-checkout한 환경에서는 `bhandara/tests/`가 없을 수 있다. 이 경우 위의 **합성 급여 계산 예제**와 `install.py --check`를 실행하고, 전체 회귀는 전체 저장소에서 확인한다.

실제 근로자 식별정보, 급여액, 원본 파일, 결과 JSON/XLSX는 공개 Git이나 Slack에 올리지 않는다. 로컬에서 접근 권한을 제한하고 별도의 승인·법령 확인 절차를 거쳐야 한다.

관련 문서: [급여 운영 실행서](RUNBOOK.md) · [저장소 README](../../README.md) · [반다라 공통 RUNBOOK](../RUNBOOK.md).
