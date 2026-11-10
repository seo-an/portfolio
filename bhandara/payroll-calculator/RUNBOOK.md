# 급여 계산기 운영 실행서 — 독립 설치·입력·검토·인계

**운영 문서 기준일: 2026-11-10.** Payroll Calculator의 공개 이전, 원본 SHA·합성 출력 동등성, **Base + Payroll 단독 실행**, Worktime JSON 인계, Gearbox 전체 회귀 테스트를 통과했다. 기존 비공개 Gearbox 운영 계산기는 그대로 유지한다.

이 문서는 **실제로 급여 계산기 하나만 내려받아 사용하는 사람**을 위한 실행 순서와 점검 기준을 설명한다. 계산 원리·기존 세부 정책 분석이 필요한 경우 [원본 문서 보존본](legacy-source-docs/RUNBOOK.md)을 읽을 수 있으나, 해당 문서는 이전 전 Gearbox 경로와 과거 상태가 포함된 **참고 기록**이다. 현재 사용법은 [README](README.md)와 **이 문서**가 기준이다.

## 1. 적용 범위 및 책임 경계

Payroll이 수행하는 일:

1. 설정 파일이 명시한 급여월과 직원 목록, 보상 정보 및 월별 급여 항목 입력을 읽는다.
2. Worktime 결과 또는 별도 근무시간 사실값을 **계약에 맞게 인계**받는다. 원본 출퇴근 기록을 Payroll에서 다시 해석하지 않는다.
3. 원본에서 이전한 급여 항목 레지스트리, 회사 정책, 법정 정책, 운영 기간 설정을 적용해 계산한다.
4. 지급·공제·일할 계산·초과·야간·휴일근로 연동·결근 공제·주휴·소급정산 등 기존 계산 함수의 **검토용 결과**와 문제 목록을 생성한다.

Payroll이 **하지 않는 일**:

- 임금 지급 승인, 은행 이체, 원천세 신고, 사회보험료 확정, 법령 준수 보증
- 근무시간 원본의 재해석, 부족한 승인 자동 보완, Worktime 마감 처리
- 확정 회계원장(정산원장)에 거래 기록, 기존 급여대장 최종 발행
- 기존 Hermes·Gearbox 운영 Pipeline 교체

**정상 계산이어도 종료 코드 2**, `finalizable=false`, `ledger_committed=false`가 유지되는 **검토 전용 프로그램**이다.

## 2. 설치 — Payroll 하나만 구성

```sh
git clone --depth 1 --sparse https://github.com/seo-an/portfolio.git bhandara-payroll
cd bhandara-payroll

# 다른 계산기는 다운로드하지 않고 Base + Payroll만 사용
git sparse-checkout set bhandara/common bhandara/payroll-calculator

uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
```

필수 구성은 최상위 `run.py`, `install.py`, `requirements.txt`, `bhandara/__init__.py`, `bhandara/common/`, `bhandara/payroll-calculator/`이다. **공통 Base 없이는 단독 모듈 실행이 불가능**하다.

의존성 버전은 `openpyxl==3.1.5`와 `korean-lunar-calendar==0.4.0`으로 고정되어 있다. 검증 서버는 uv 관리 Python 3.14.9였고 Python 3.12 이상을 지원한다.

`install.py --check`는 계산을 하지 않으며 설치된 Python·패키지와 실제 체크아웃된 모듈만 읽는다. sparse-checkout에서 `Available modules: payroll-calculator.`가 표시되는지 확인한다.

## 3. 첫 실행 — 제공된 합성 자료로 정상 산출물 확인

```sh
# Worktime 프로그램을 설치하지 않고, 제공된 합성 근무시간 JSON으로 입력 생성
.venv/bin/python \
  bhandara/payroll-calculator/examples/payroll-standalone-demo/generate.py \
  --worktime-result \
  bhandara/payroll-calculator/examples/payroll-standalone-demo/worktime-result.synthetic.json \
  --output-dir /tmp/payroll-input-demo

# 검토용 급여 계산
.venv/bin/python run.py bhandara payroll-calculator \
  --config /tmp/payroll-input-demo/payroll-config.json \
  --output-dir /tmp/payroll-calc-demo
```

예제 파일의 직원 `EP0001`, `EP0002`는 가상 직원이다. 실행이 정상일 때 예상되는 것은 **검토용 급여 산출물 생성**이지 종료 코드 0이 아니다. 계산 모드에서는 정상 실행이어도 `REVIEW_REQUIRED` / **종료 코드 2**가 발생한다.

확인할 파일:

```text
/tmp/payroll-calc-demo/
├── payroll-calculation.json     # 임시 금액·계산 근거
├── payroll-calculation.xlsx     # 임시 계산 검토 양식
├── payroll-review.json          # 상태·직원별 검토 사항
├── payroll-review.xlsx          # 검토 사항 표
└── policy-resolution.json       # 선택된 정책·시나리오
```

위 폴더는 **존재하지 않는 경로**여야 한다. 이미 있는 폴더를 강제로 덮어쓰지 않는다. 실제 급여 입력을 그대로 예제 폴더에 저장하거나 Git에 넣지 않는다.

## 4. 실무 입력 계약

### 4.1 급여 설정 파일

계산 모드는 `--config /private/payroll/payroll-config.json`을 사용한다. 설정 파일의 `schema_version`은 `"0.1"`이다.

```json
{
  "schema_version": "0.1",
  "payroll_period": "2026-10",
  "expected_worker_ids": ["EP0001", "EP0002"],
  "compensation_path": "compensation.xlsx",
  "payroll_input_path": "payroll-input.xlsx",
  "worktime_result_path": "/private/worktime/worktime-result.json",
  "registry_path": "/path/to/bhandara/payroll-calculator/resources/pay-item-registry.json",
  "operating_config_path": "/path/to/bhandara/payroll-calculator/operating-config.json",
  "company_policy_path": "company-policy.json",
  "legal_policy_path": "/path/to/bhandara/payroll-calculator/resources/policy/2026.json",
  "employment_facts_path": "employment-facts.json",
  "recurring_pay_item_codes": ["base_salary"]
}
```

이 JSON은 **입력 필드 구조를 보여주는 예시**다. 가상 직원과 실제 회사 데이터, 임의 정책 값을 혼합하지 않는다. 보상·급여 입력·재직 정보·회사 정책·근무시간·법정 정책을 모두 실제 대상 회사의 **검증된 경로와 내용**으로 지정해야 한다. 설정 파일 기준의 상대 경로와 절대 경로를 사용할 수 있다.

### 4.2 파일별 준비 조건

| 데이터 | 필수 확인 사항 |
|---|---|
| Compensation Excel | `worker_id`, `effective_from`, `effective_to` 선행 헤더와 지급 항목 코드; 적용기간 중복 확인 |
| Payroll Input Excel | `worker_id`, `pay_item_code`, `amount`, `quantity`, `origin_pay_item_code`, `origin_from`, `origin_to`, `note` |
| Employment facts JSON | 직원별 고용·종료 사실 및 급여항목 자격에 필요한 원본 정보 |
| Worktime 결과 | 대상 급여월이 참조하는 근무시간 기간과 직원 명부, 검토 상태를 확인 |
| 급여항목 Registry | 항목 유형(지급·공제·정산), 허용 원본, 일할·통상임금·근무시간 연결 정의 |
| Operating Config | 급여월 기준 각 원본의 사용 기간 및 지급 기준 |
| 회사 정책 | 일할 계산, 통상임금 시간수, 근로시간 가산 기본분, 금액 단위·절사 잔액 처리 |
| 법정 정책 | 계산 시점에 맞는 기준인지 **별도 확인**. 포함된 2026 JSON은 이전 당시 원본 보존용 |

기존 함수는 원본 데이터 누락이나 계약 오류가 있으면 **추정값이나 0원으로 자동 보정해서 승인하지 않는다.** 오류가 발생해도 검토 자료를 남기는 기존 경로를 유지한다.

## 5. 원본 정규화 모드

`normalize`는 원본에서 이전한 `source_pipeline.py`·`source_mapping.py` 계약을 따른다. 근무시간 계산이 아니라 **원본 형식의 표준화**다.

```sh
.venv/bin/python run.py bhandara payroll-calculator \
  --operation normalize \
  --input-dir bhandara/payroll-calculator/examples/source-mapping-demo \
  --output-dir /tmp/payroll-normalized-demo
```

- 입력 폴더의 `manifest.json`에서 파일·열·값 대응과 직원 명부를 읽는다.
- 다른 매핑 파일을 쓰려면 `--manifest /private/mapping/manifest.json`을 지정한다.
- 결과 `normalized-input.json`은 원본에서 유지한 `schema_version: "0.1"` 계약과 출처·행별 검토 정보를 가진다.
- 정상 `READY_FOR_CALCULATION`이면 종료 코드 0, 검토·차단 상태면 2다.
- Worktime 계산기 자체는 원본 Excel을 직접 정규화하지 않으며, **별도로 받은 정규화 JSON**을 사용한다.

## 6. Worktime 모듈 없이 급여 계산하기

```text
별도 Worktime 폴더
  Base + Worktime
      │
      └── worktime-result.json ─────────┐
                                        │ 파일 경로만 전달
별도 Payroll 폴더                       ▼
  Base + Payroll                  payroll-config.json
                                        │
                                        ▼
                               검토용 급여 결과 JSON/XLSX
```

Payroll은 입력 경로를 다음 셋 중 **정확히 하나**로 받는다.

- `worktime_result_path`: Worktime 미마감·검토용 결과 JSON
- `worktime_rows_path`: 별도 검증한 근무시간 행 데이터
- `worktime_closes_path`: 승인·마감 근거를 가진 근무시간 Receipt

`worktime_closes_path`를 사용할 때의 마감 Receipt 검증 함수는 공통 Base `bhandara/common/contracts/worktime_close.py`에 있다. 이는 이전한 Worktime 계산기의 해당 함수와 **바이트가 동일**하며, Payroll이 Worktime 전체 소스 없이 독립적으로 import할 수 있도록 참조 경로만 옮겼다.

반면 **미마감 Worktime 결과 JSON**을 넘긴다고 해서 Payroll이 근무시간을 승인하거나 Receipt를 만들어 주지 않는다. 양쪽 결과는 계속 미확정 검토용이다.

## 7. 정책·금액 처리의 운영 원칙

원본 계산기 정책을 새로 해석하거나 개선하는 목적의 문서가 아니다. 기존 계약을 사용하는 운영자는 다음을 확인해야 한다.

- **급여항목 정의**(`resources/pay-item-registry.json`)와 **회사별 계산 정책**(`company_policy_path`)은 서로 다른 책임이다. Registry는 항목의 의미, 회사 정책은 계산 방법·기준을 정의한다.
- **법정 정책**(`resources/policy/2026.json`)은 2026년 원본 코드 이전 당시의 자료이며, 현재 법령을 자동 갱신하지 않는다.
- **운영 기간**(`operating-config.json`)은 원본 급여월과 근무시간 원본의 기간 선택에 관여한다. 월을 바꿀 때 설정만 바꾼다고 모든 원본이 자동으로 준비되는 것은 아니다.
- **소급·이월·절사 잔액**은 계산 중 생성되는 검토·거래 요청일 수 있다. 실제 Settlement Ledger에 자동 확정 반영되는 것으로 해석하지 않는다.
- **세액·보험료**는 이 모듈에서 확정하지 않는다. 실제 지급하려면 회사의 별도 검토·결재·신고 절차를 거쳐야 한다.

구체적인 과거 설계·업무 정의를 확인할 경우 [기존 운영 문서의 보존본](legacy-source-docs/RUNBOOK.md)을 참고하되, 거기에 적힌 `gearbox/` 경로와 PR 검증 대기 상태를 **현재 사용법으로 적용하지 않는다.**

## 8. 결과·실패 대응

```sh
.venv/bin/python run.py bhandara payroll-calculator \
  --config /private/payroll/payroll-config.json \
  --output-dir /private/payroll/review-02
```

계산이 정상이라면 `payroll-calculation.json`과 `payroll-review.json`이 생성된다. 출력의 `status`, `issue_count`, `worker_statuses`, `finalizable`, `ledger_committed`를 확인한다.

| 상황 | 우선 확인할 것 | 처리 |
|---|---|---|
| 종료 코드 2 + `REVIEW_REQUIRED` | 계산 결과 JSON·검토 JSON 존재 | **정상적인 검토 전용 실행**으로 분류 |
| 종료 코드 2 + `BLOCKED` | 검토 보고서 `issues` | 누락·헤더·기간·정책 경로를 고쳐 새로운 출력 폴더에 재실행 |
| `ModuleNotFoundError` | `bhandara/common/`, `bhandara/__init__.py`, 최상위 경로 | 필수 Base 누락이나 잘못된 실행 위치 확인 |
| Worktime 파일 불일치 | 원본 기간·직원 명부·`worktime_..._path` 하나만 설정했는지 | 원본 계약 기준으로 다시 입력 준비 |
| 출력 폴더 존재 | 새 `--output-dir` 사용 | 기존 산출물 무단 덮어쓰기 금지 |
| 정책·법령 해석 불확실 | 원본 정책 파일·승인 근거 | 자동 승인하지 않고 별도 전문가·실무 검토 |

실제로 검토가 필요한 자료를 **설정을 느슨하게 만들어서 무조건 PASS로 바꾸지 않는다.** 기존 계산 엔진이 오류를 구분하는 구조는 이번 이전에서 수정하지 않았다.

## 9. 이전·상호배타 검증 및 유지보수

**2026-11-10 확인 완료**

1. 원본 파일 **85개**의 출처 Git blob SHA 확인. 필요한 import·경로 변경 **10곳**은 역변환하면 원본 해시와 동일하다.
2. 공통 Base로 옮긴 도구·정책·Worktime close 검증 함수 등 **원본 자원 5개**의 SHA 일치 확인.
3. 기존 Payroll CLI와 공개 최상위 CLI의 **같은 합성 normalize/calculate 결과 JSON·XLSX 내용 일치**.
4. **Base + Payroll만** 있는 격리된 임시 폴더에서 합성 급여 계산 및 보조 모듈 import 통과.
5. **Base + Worktime**의 JSON 결과를 Worktime 코드 없이 Payroll로 넘기는 인계 통과.
6. Portfolio 전체 `unittest`와 기존 Gearbox 공식 코어/기능 회귀 테스트 통과.

```sh
# 전체 portfolio가 준비된 환경에서
.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_payroll_migration.py' -v

.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_module_isolation.py' -v

.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_*.py' -v
```

모듈 하나만 sparse-checkout한 폴더에는 테스트 모듈이 없을 수 있다. 그 경우 위의 가상 입력 생성·실행 명령과 `install.py --check`로 최소 동작을 확인한다.

원본 Gearbox를 검증할 때는 `gearbox/_tests/run.py` 공식 실행기를 사용해야 한다. 직접 개별 테스트를 돌리면 기존 Payroll `functions/`의 `PYTHONPATH` 설정이 빠져 import 실패를 만들 수 있다.

## 10. 원본 보존·보안·프로젝트 종료 기준

- 사용자를 위한 **최신 한국어 문서**: [README](README.md) 및 **이 RUNBOOK**.
- 기존 Gearbox에서 복사한 **원본 문서의 바이트 동일 사본**: `legacy-source-docs/README.md`, `legacy-source-docs/RUNBOOK.md`. [migration-manifest.json](migration-manifest.json)으로 원본 SHA 검증을 유지한다.
- 코드 이전·상호배타 확인 근거: [이전 기록](MIGRATION.md), [상호배타 검증](../MODULE-ISOLATION.md), [공통 Base 운영서](../RUNBOOK.md).
- 실직원 급여·근태 자료, 비공개 Golden, 결과 파일을 공개 Git·PR·Slack으로 전송하지 않는다.
- 기능 재점검, 새로운 예외처리·급여 정책·정산·장부 개선은 **별도 프로젝트**에서 기획·승인·시험한다. 이 문서 작업에서 기존 계산기 본문을 변경하지 않는다.
