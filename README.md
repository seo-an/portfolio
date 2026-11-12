# Portfolio · Bhandara(반다라)

## 이제 Excel만 복사해서 실행할 수 있습니다

**공개 샘플:** [가상 직원 80명의 실제 Excel](bhandara/examples/sample/input/) · [샘플 설명](bhandara/examples/sample/README.md)

가장 쉬운 방법은 샘플의 `input/`을 `bhandara/data/input/`에 복사한 뒤
계산할 **월만 지정**하는 것입니다. 세 계산기는 서로 독립적이며 공통 직원명부와
ID 매핑을 재사용합니다.

```bash
mkdir -p bhandara/data/input
cp -R bhandara/examples/sample/input/. bhandara/data/input/
.venv/bin/python run.py bhandara worktime-calculator --period 2026-06
.venv/bin/python run.py bhandara pto-calculator --period 2026-07
.venv/bin/python run.py bhandara payroll-calculator --period 2026-07
```

입력 폴더는 `common/`, `pto/`, `worktime/`,
`payroll/`로 구분합니다. 설정 JSON의 파일 경로 수정은
**고급 사용자에게만 선택 사항**입니다. 기본 모드에서는 파일명이나 ID가
맞지 않으면 오류로 알려주며 비슷한 이름을 임의 추측하지 않습니다.
출입 인증 기록은 자동 확정 근태가 아니며 급여도 검토용입니다.

> **처음 사용하는 인사·총무·급여 담당자라면:** 먼저 [쉬운 사용 안내서](bhandara/RUNBOOK.md)를 읽으세요. **Excel 파일 위치·확장자·활성 시트·1행 열 제목·JSON 설정 수정 위치**를 계산기별로 설명합니다.
>
> - [연차 Excel·설정 준비](bhandara/pto-calculator/RUNBOOK.md)
> - [근무시간 JSON·설정 준비](bhandara/worktime-calculator/RUNBOOK.md)
> - [급여 Excel·정책·설정 준비](bhandara/payroll-calculator/RUNBOOK.md)
>
> 이 README부터는 **개발자·설치 담당자용** 소스 구성, Python 환경, CLI·코드 계약·검증 내용입니다.


**PTO(연차), Worktime(근무시간), Payroll(급여) 계산기를 필요한 것만 내려받아 로컬에서 실행할 수 있는 공개 Python 모듈 모음**입니다. 개인 서버, Hermes 에이전트, Slack, Google Drive, API 키, 별도 데이터베이스가 없어도 실행할 수 있습니다.

> **2026-11-10 기준: 1차 이전·독립 실행·상호배타 검증 완료.** PTO·Worktime·Payroll 이전과 기존 Gearbox 회귀 테스트를 마쳤고, 서로 다른 계산기 없이 **공통 Base + 계산기 하나만** 설치한 격리 환경에서 각각 실행하는 테스트 7개와 **Worktime JSON → Payroll 인계**도 통과했습니다. 기능 개선, 새로운 계산 정책, 법적 적합성 검토는 이후 별도 프로젝트에서 진행합니다. 기존 Gearbox 운영 Pipeline은 변경하지 않았습니다.

## 1. 어떤 모듈을 받을까?

| 모듈 | 하는 일 | 입력 | 결과 | 실행 상태 |
|---|---|---|---|---|
| [PTO Calculator](bhandara/pto-calculator/README.md) | 입사일 기준 연차 **발생 내역** 계산·검토 | 직원·근무표·근태 등의 Excel, 설정 JSON | 연차 결과·검토 JSON/XLSX·실행 기록 | 독립 실행 검증 완료 |
| [Worktime Calculator](bhandara/worktime-calculator/README.md) | 정규화된 근무표·근태로 일별 근무시간 계산 | 고정 경로 Excel 자동 입력 또는 정규화 JSON(고급) | 근무시간 결과·검토 JSON/XLSX | 독립 실행 검증 완료 |
| [Payroll Calculator](bhandara/payroll-calculator/README.md) | 보상·월별 급여 입력·근무시간 사실값·정책으로 **검토용** 급여 계산 | 고정 경로 보상·급여 Excel 또는 설정 JSON(고급) | 급여 계산·검토 JSON/XLSX | 독립 실행 검증 완료 |
| [공통 Base](bhandara/BASE-CONTRACT.md) | Excel 읽기·진단·해시·결과 저장·검토 계약 | 각 계산기가 호출 | 공통 함수 | **모든 계산기에 필수** |

세 모듈은 서로를 직접 설치하지 않고 실행할 수 있습니다. 다만 **계산기 폴더 하나만 복사해서는 안 됩니다.** 공통 Base와 최상위 실행 파일도 함께 필요합니다. 구체적인 검증 기준은 [상호배타 검증 문서](bhandara/MODULE-ISOLATION.md)를 참고하세요.

## 2. 가장 쉬운 설치: 저장소 전체 받기

Python **3.12 이상**과 Git, [uv](https://docs.astral.sh/uv/)를 준비합니다. Hermes에서 실제 검증한 Python 버전은 **3.14.9**입니다. 별도 가상환경을 사용하므로 시스템 Python을 변경하지 않습니다.

```sh
git clone https://github.com/seo-an/portfolio.git
cd portfolio

uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt

.venv/bin/python install.py --check
.venv/bin/python run.py --help
```

`requirements.txt`에 고정된 외부 패키지는 `openpyxl==3.1.5`와 `korean-lunar-calendar==0.4.0`입니다. `install.py --check`는 **읽기 전용 점검**이며 패키지를 설치하지 않습니다. Windows에서는 Python 경로를 `.venv\Scripts\python.exe`로 바꿉니다.

## 3. 필요한 계산기 하나만 받기 — 권장

전체 계산기를 받지 않고 **Base + 선택한 계산기만** 구성하려면 Git의 sparse-checkout을 이용합니다. 다음 예시는 PTO 전용 설치이며 다른 모듈을 내려받지 않습니다.

```sh
git clone --depth 1 --sparse https://github.com/seo-an/portfolio.git bhandara-pto
cd bhandara-pto
git sparse-checkout set bhandara/common bhandara/pto-calculator

uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
```

**Worktime만** 필요하면 `git sparse-checkout set bhandara/common bhandara/worktime-calculator`, **Payroll만** 필요하면 `git sparse-checkout set bhandara/common bhandara/payroll-calculator`로 바꿉니다. Git은 최상위 `run.py`, `install.py`, `requirements.txt` 및 `bhandara/__init__.py`도 함께 체크아웃합니다.

Git 사용이 어렵다면 GitHub 저장소의 **Code → Download ZIP**으로 전체 소스를 받은 뒤 다음 파일만 남기는 방법도 있습니다.

```text
내-반다라/
├── run.py
├── install.py
├── requirements.txt
└── bhandara/
    ├── __init__.py
    ├── common/                    # 반드시 포함
    └── pto-calculator/           # 세 계산기 중 하나만 선택
```

`pto-calculator/` 대신 `worktime-calculator/` 또는 `payroll-calculator/`를 넣어도 됩니다. **모듈 하나만 받고 싶어도 Base는 생략할 수 없습니다.** Python 패키지 저장소(PyPI)에 각 계산기를 별도 배포한 상태는 아니므로, 위의 파일 구성이 현재 공식적인 단독 이용 방식입니다.

## 4. 실행하기

모든 명령은 **내려받은 폴더의 최상위**, 즉 `run.py`가 있는 곳에서 실행합니다. 실제 직원·근태·임금 자료와 계산 결과는 **Git 저장소 밖의 비공개 폴더**에 둡니다. 출력 대상은 다른 실행이 사용하지 않은 **새 경로**를 지정합니다.

### PTO — 제공되는 합성 Excel로 즉시 시험

```sh
.venv/bin/python bhandara/pto-calculator/examples/generate_demo.py \
  --output-dir /tmp/bhandara-pto-demo

.venv/bin/python run.py bhandara pto-calculator \
  --config /tmp/bhandara-pto-demo/config.json \
  --input-dir /tmp/bhandara-pto-demo/input \
  --output-dir /tmp/bhandara-pto-result
```

실제 적용 시에는 [PTO 입력 Excel 헤더와 설정](bhandara/pto-calculator/README.md)에 맞춰 별도의 입력 파일을 준비합니다. 합성 예제의 직원 ID와 실제 직원 기록을 혼용하지 마세요.

### Worktime — 정규화된 JSON을 준비한 다음 계산

```sh
.venv/bin/python run.py bhandara worktime-calculator \
  --normalized /private/worktime/normalized-input.json \
  --config /private/worktime/worktime-config.json \
  --output-dir /private/worktime/result-01
```

Worktime은 **원본 Excel을 직접 정규화하지 않습니다.** 별도의 Source Mapping 과정으로 `schema_version: "0.1"`의 `normalized-input.json`을 준비해야 합니다. [Worktime 실행서](bhandara/worktime-calculator/README.md)에 입력 구조와 가상 데이터 예제를 설명했습니다. 다른 계산기를 함께 설치할 필요는 없습니다.

### Payroll — 원본 입력 가공 또는 검토용 계산

```sh
# 제공된 합성 CSV로 Payroll의 기존 정규화 기능 시험
.venv/bin/python run.py bhandara payroll-calculator \
  --operation normalize \
  --input-dir bhandara/payroll-calculator/examples/source-mapping-demo \
  --output-dir /tmp/bhandara-payroll-normalized

# 이미 구성한 회사별 설정 및 입력 파일로 검토용 계산
.venv/bin/python run.py bhandara payroll-calculator \
  --config /private/payroll/payroll-config.json \
  --output-dir /private/payroll/review-01
```

Payroll의 `payroll-config.json`은 지급·공제 입력, 근태 결과, 급여항목 레지스트리, 정책 파일 등을 **명시적 경로로 지정**합니다. 설정 예제와 사용 절차는 [Payroll README](bhandara/payroll-calculator/README.md)에서 확인하세요.

**주의:** Payroll은 검토용 금액이 정상 계산되어도 `REVIEW_REQUIRED`와 **종료 코드 2**를 반환합니다. 해당 코드만으로 계산 실패라고 판단하면 안 됩니다. `payroll-review.json`과 `payroll-calculation.json`의 상태 및 산출물 유무를 함께 확인하세요.

## 5. Worktime 결과를 Payroll로 넘기는 방법

두 계산기를 **각자 별도 폴더에서 실행**할 수 있습니다. Worktime이 만든 `worktime-result.json`을 Payroll의 `payroll-config.json` 안 `worktime_result_path`에 지정하면 됩니다. 같은 Python 프로세스, Worktime 모듈 설치, 공통 DB는 필요하지 않습니다.

```json
{
  "worktime_result_path": "/private/worktime/result-01/worktime-result.json"
}
```

위 JSON은 **급여 설정 파일의 일부**입니다. 실제 계산에는 다른 필수 경로와 급여기간 설정도 필요합니다. Payroll은 `worktime_result_path`, `worktime_rows_path`, `worktime_closes_path` 중 **하나만** 선택합니다. 입력에 미마감 근무시간이 있으면 결과도 미확정·검토용이며, **JSON을 넘긴 것만으로 승인이나 근태 마감이 발생하지 않습니다.**

이 계약은 각 모듈을 다른 임시 설치 루트에 두고 JSON만 주고받는 **실제 상호배타 테스트에서 PASS**했습니다. 자세한 구조는 [검증 결과](bhandara/MODULE-ISOLATION.md) 및 [운영 실행서](bhandara/RUNBOOK.md)에 있습니다.

## 6. 검증·개인정보·운영 경계

```sh
# 저장소 전체를 받은 경우: 공개 모듈 전체 회귀 테스트
.venv/bin/python -m unittest discover -s bhandara/tests -p 'test_documentation_examples.py' -v

.venv/bin/python -m unittest discover -s bhandara/tests -p 'test_*.py' -v

# 모듈 하나만 받은 경우: 설치·의존성 확인 및 위 합성/샘플 CLI 실행
.venv/bin/python install.py --check
```

- **상호배타 테스트 완료:** `Base + PTO`, `Base + Worktime`, `Base + Payroll`의 단독 실행, 미설치 모듈 호출 차단, Worktime JSON 인계, 이전 해시·기존 Gearbox 회귀를 확인했습니다.
- **모듈이 독립 실행된다는 것과 계산 결과를 승인한다는 것은 다릅니다.** PTO 결과는 연차 사용·정산 승인, Worktime 결과는 근태 마감, Payroll 결과는 최종 급여 지급·원천세 신고·회계전표 승인을 의미하지 않습니다.
- 개인정보가 있는 원본 Excel/JSON, 계산 결과, 승인 참조, 급여액, 비공개 Golden은 **Git·Slack·공개 저장소에 올리지 않습니다.** 외부 서비스로 데이터를 자동 전송하지 않습니다.
- 실제 운영·개선 계획은 공개 계산기와 분리됩니다. Hermes 및 기존 Gearbox 운영 Pipeline은 그대로 유지합니다.

추가 자료: [Bhandara 운영 실행서](bhandara/RUNBOOK.md) · [공통 Base 계약](bhandara/BASE-CONTRACT.md) · [Golden 비교 설명](bhandara/GOLDEN-COMPARISON.md) · [Payroll 원본 이전 이력](bhandara/payroll-calculator/MIGRATION.md).
