# 반다라(Bhandara) 운영 실행서 — 독립 모듈 사용·검증

**최종 정리 기준: 2026-11-10.** 공개 PTO·Worktime·Payroll 계산기 이전, 원본 동일성 확인, Hermes 서버 회귀 및 **상호배타 테스트 7개**를 모두 통과했다. 기존 `agent-config`의 Gearbox 운영 계산 경로는 전환하지 않았다. 이후 계산식·정책·예외처리 개선은 별도 프로젝트로 관리한다.

이 문서는 **모듈을 설치하고 실행할 사람**을 위한 운영 지침이다. 처음 사용하는 사람은 저장소 최상위 [README](../README.md)부터 읽고, 계산기별 입력 세부 사항은 각 모듈의 README를 참고한다.

## 1. 구조와 책임

```text
portfolio/
├── README.md                   # 사용자용 시작 문서
├── requirements.txt            # 최상위 단일 의존성 목록
├── install.py                  # 설치된 Python/패키지 상태만 검사
├── run.py                      # 계산기별 명시적 CLI 라우터
└── bhandara/
    ├── __init__.py
    ├── common/                 # 모든 계산기가 공유하는 Base
    │   ├── io/
    │   ├── contracts/
    │   ├── runtime/
    │   └── utils/
    ├── pto-calculator/         # 연차 발생 계산
    ├── worktime-calculator/    # 근무시간 계산
    ├── payroll-calculator/     # 급여 검토용 계산
    ├── MODULE-ISOLATION.md     # 독립·상호배타 검증 기록
    └── tests/                  # 전체 저장소 회귀 검증
```

**소유권 구분:**

- `portfolio`: 입력 계약에 맞게 전달된 데이터를 **로컬에서 결정적으로 계산**하고 검토용 결과 파일을 만든다. 로그인·외부 API·클라우드·Slack·Hermes 없이 사용할 수 있다.
- `bhandara/common`(Base): 필수 Excel 열 검사, 원본 해시, 행·필드 진단, 공통 날짜·진단 계약, 산출물 충돌 처리, 실행 영수증, **근무시간 마감 Receipt 검증 함수** 등을 제공한다. 각 계산기의 공통 의존성이므로 생략할 수 없다.
- `agent-config`(기존 비공개 운영 경로): 실제 직원자료 접근, 인증, 스케줄링, 승인, 데이터 분리, Gearbox Workflow 및 Slack을 관리한다. **이번 공개 모듈 이전으로 대체되거나 자동 연결되지 않는다.**

## 2. 설치 단위 및 상호배타성

**상호배타성의 의미:** A 계산기를 실행하기 위해 B·C 계산기의 코드까지 설치할 필요가 없다는 뜻이다. 동시에 여러 계산기를 설치할 수 없다는 의미는 아니다.

| 설치 형태 | 포함할 것 | 제외 가능 |
|---|---|---|
| 연차만 | `run.py`, `install.py`, `requirements.txt`, `bhandara/__init__.py`, `common/`, `pto-calculator/` | Worktime, Payroll |
| 근무시간만 | 동일 공통 파일 + `common/`, `worktime-calculator/` | PTO, Payroll |
| 급여만 | 동일 공통 파일 + `common/`, `payroll-calculator/` | PTO, Worktime |
| 전부 | 저장소 전체 | 없음 |

**단독 설치란 계산기 폴더 단독이 아니라 Base + 선택한 계산기**다. 공통 검증 함수는 다른 계산기를 설치하는 대신 Base에서 참조한다. Python 패키지 배포판 형태의 별도 `pip install bhandara-payroll` 같은 명령은 제공하지 않는다.

필요한 폴더만 가져오는 예시(급여만):

```sh
git clone --depth 1 --sparse https://github.com/seo-an/portfolio.git bhandara-payroll
cd bhandara-payroll
git sparse-checkout set bhandara/common bhandara/payroll-calculator
```

Git을 쓰지 않는 경우 GitHub ZIP에서 위 표의 파일만 같은 상대 경로로 복사한다. 이때 `common/`의 내부 파일을 선택적으로 빼면 안 된다. 최상위 `run.py`에서 `bhandara`를 찾을 수 있도록 **디렉터리 구조를 유지**한다.

## 3. Python 환경 준비

Python 3.12 이상, 권장 실행 환경은 독립된 uv 가상환경이다. 검증 서버의 Hermes uv Python 3.14.9에서 실험했다.

```sh
# 반드시 run.py가 있는 설치 루트에서 실행
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 이미 설치된 모듈·패키지의 상태만 읽는다. 설치·다운로드하지 않음
.venv/bin/python install.py --check
.venv/bin/python run.py --help
```

외부 의존성 고정값은 `openpyxl==3.1.5`, `korean-lunar-calendar==0.4.0`이다. 코드를 수정하지 않는 한 추가 백엔드, 데이터베이스, OAuth, AWS Parameter Store가 필요하지 않다. Windows 가상환경의 Python은 `.venv\Scripts\python.exe`다.

**운영 참고:** 상호배타 테스트 중, 실행 프로세스의 환경을 강제로 지우고 `python -E`로 돌린 상태에서는 이미 설치된 `korean-lunar-calendar`의 *패키지 메타데이터*를 찾지 못하는 경우가 있었다. 계산기 실행 격리와 **실제 환경의 설치 정보 검사**는 분리해 다시 시험했으며 모두 통과했다. 의존성 확인은 항상 **실제 사용하는 uv Python**으로 수행한다.

## 4. 계산기별 실행 명령

입력·출력 경로는 예시다. 실제 데이터를 사용한다면 저장소 **밖에 위치한 접근 제한 디렉터리**로 변경한다. 출력 폴더는 **아직 존재하지 않는 새 경로**를 사용하고, 기존 결과를 덮어쓰지 않는다.

### 4.1 PTO: 합성 데이터로 실행 확인

```sh
.venv/bin/python bhandara/pto-calculator/examples/generate_demo.py \
  --output-dir /tmp/pto-example

.venv/bin/python run.py bhandara pto-calculator \
  --config /tmp/pto-example/config.json \
  --input-dir /tmp/pto-example/input \
  --output-dir /tmp/pto-example/result
```

입력은 `employee.xlsx`, `work-schedule.xlsx`, `work-schedule-assignment.xlsx` 및 설정에 명시된 월별 스케줄·근태·선택 이벤트이다. 설정 `period.from/to`와 상대경로는 **입력 폴더 기준**으로 해석된다. [PTO README](pto-calculator/README.md)를 참조한다.

종료 코드: `0=PASS`, `1=REVIEW_REQUIRED`, `2=ERROR`. **PASS도 연차 승인·사용량 정산 확정은 아니다.**

### 4.2 Worktime: 정규화된 JSON 입력

```sh
.venv/bin/python run.py bhandara worktime-calculator \
  --normalized /private/worktime/normalized-input.json \
  --config /private/worktime/worktime-config.json \
  --output-dir /private/worktime/result-01
```

- **입력 계약:** Source Mapping 과정에서 생산한 `schema_version: "0.1"`의 `normalized-input.json`(직원·스케줄·출퇴근·lineage)과 기간·근로제·승인 참조 설정을 사용한다.
- 같은 디렉터리의 `review-report.json`은 존재하면 함께 읽는다.
- **직접 Excel을 정규화하지 않는다.** Worktime 설치에 Payroll 소스 정규화기를 포함할 필요는 없지만, 입력 JSON은 실행 전 준비해야 한다.
- 종료 코드 `0=CALCULATED_UNCLOSED`, `2=REVIEW_REQUIRED/BLOCKED/호출 오류`. `0`이어도 **근태 마감은 아니다**.

[Worktime README](worktime-calculator/README.md)를 참조한다.

### 4.3 Payroll: 원본 자료 정규화·검토용 계산

```sh
# 포함된 가상 CSV 예제로 원본 입력 정규화 시험
.venv/bin/python run.py bhandara payroll-calculator \
  --operation normalize \
  --input-dir bhandara/payroll-calculator/examples/source-mapping-demo \
  --output-dir /tmp/payroll-normalize-demo

# 급여 정책·입력 경로를 명시한 설정으로 검토용 계산
.venv/bin/python run.py bhandara payroll-calculator \
  --config /private/payroll/payroll-config.json \
  --output-dir /private/payroll/review-01
```

- `normalize`: `manifest.json`과 CSV/XLSX/JSON의 기존 매핑 규칙대로 정규화. 준비 가능할 때 종료 코드 0, 검토·오류는 2.
- `calculate`: 보상 파일, 변동 급여 파일, 직원 고용 사실, Worktime 결과, 급여 항목 레지스트리, 회사·법정 정책 등 **설정 파일에 지정된 경로**를 이용한다. 결과가 정상 계산되어도 **검토 전용이므로 종료 코드 2**다.
- 계산 결과의 `finalizable=false`, `ledger_committed=false`를 유지한다. 승인·신고·송금·최종 급여대장 확정을 의미하지 않는다.
- `--scenario-id`와 정규화의 `--manifest`는 기존 CLI 계약 그대로 전달된다.

[Payroll README](payroll-calculator/README.md)에서 설정과 산출물 내용을 확인한다.

## 5. 모듈 간 데이터 인수인계

모듈 간 의존성은 **코드 import가 아닌 명시적인 파일 계약**으로 관리한다.

```text
Worktime 전용 설치                      Payroll 전용 설치
  Base + Worktime                        Base + Payroll
          │                                     │
          └── worktime-result.json ────────────>│
                                  파일 경로 지정│
                                                └── payroll-calculation.json
                                                    payroll-review.json
```

Payroll의 설정 `worktime_result_path`에 Worktime 결과 JSON의 파일 경로를 넣는다. 예:

```json
{
  "worktime_result_path": "/private/worktime/result-01/worktime-result.json"
}
```

이 값은 **전체 Payroll 설정 객체의 일부**다. 다른 필수 입력이 함께 있어야 계산할 수 있다. 근태 인계 항목 `worktime_result_path` / `worktime_rows_path` / `worktime_closes_path` 중 하나만 지정한다. 미승인 Worktime JSON을 전달하더라도 **자동 승인·마감·급여 확정이 발생하지 않는다.**

Payroll 내부의 마감 Receipt 검증기 import 경로는 `bhandara/common/contracts/worktime_close.py`로 이동했다. 기존 Worktime `functions/worktime_close.py`의 **바이트가 동일한 사본**이고, Payroll이 Worktime 전체 폴더를 의존하지 않도록 하기 위한 경로 분리다.

## 6. 산출물·오류 상태 확인

| 계산기 | 주요 파일 | 처리 |
|---|---|---|
| PTO | `pto-result.json`, `pto-review.json`, `pto-result.xlsx`, `pto-run.json` | 계산 결과·검토·실행 해시 기록 |
| Worktime | `worktime-result.json`, `worktime-review.json`, `worktime-review.xlsx` | 일별 근무시간·누락·검토 |
| Payroll | `payroll-calculation.json`, `payroll-calculation.xlsx`, `payroll-review.json`, `payroll-review.xlsx`, `policy-resolution.json` | **검토 전용** 급여 산출물(정상 계산 시) |

급여 입력 오류처럼 계산이 차단된 경우 Payroll은 `payroll-review.json`·`payroll-review.xlsx`만 생성할 수 있다. 정상 계산과 차단을 **종료 코드 2만으로 구별하지 말고** 보고서의 `status`·`issues`·생성 파일을 확인한다.

Base는 개별 파일의 원자적 게시와 충돌 시 번호 부여를 지원하지만, 전체 파일 묶음을 한 번에 확정하는 파일시스템 트랜잭션은 구현하지 않았다. 기존 파일 덮어쓰기/강제 확정/원본 자동 보정은 하지 않는다.

## 7. 검증 결과 및 재실행

**2026-11-10 사용자 Hermes 서버 결과**

| 항목 | 확인한 범위 | 결과 |
|---|---|---|
| PTO 이전 | 합성 Golden(2026-07), 레거시 Tooth/Gear 대 공개 CLI의 합성 2026년 전체기간 3명 비교 | PASS |
| Worktime 이전 | 원본 10개 Git blob SHA 동일성, 독립 CLI JSON/XLSX 합성 동일성 | PASS |
| Payroll 이전 | 원본 85개 파일 SHA 검증(경로 적응은 역변환), 합성 normalize/calculate 및 기존 회귀 | PASS |
| 독립 설치 | Base+PTO / Base+Worktime / Base+Payroll 격리 실행 | PASS |
| 상호배타 경계 | 미설치 모듈 차단, Payroll의 Worktime 부재 상태 import | PASS |
| 파일 인계 | Worktime JSON을 별도 설치 Payroll로 전달 | PASS |
| 운영 회귀 | 공개 Portfolio 전체 `unittest`, Gearbox 공식 코어/기능 실행기 | PASS |

위 결과는 **기존 기능을 공개 코드로 옮겼을 때 동일하게 실행된다는 검증**이지, 모든 법령·회사 정책·예외 상황에 대한 추가 기능 인증이 아니다.

```sh
# 전체 portfolio 체크아웃, .venv 설정 후
.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_module_isolation.py' -v

.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_*.py' -v

.venv/bin/python install.py --check
```

**주의:** sparse-checkout으로 계산기 하나만 받은 경우 `bhandara/tests/`가 없을 수 있다. 이때 전체 테스트를 실행할 수 없으므로, `install.py --check`와 위의 각 모듈 CLI 합성 예제로 정상 실행을 확인한다. 전체 회귀를 돌리려면 별도의 전체 체크아웃을 사용한다.

기존 Gearbox 원본 회귀는 `agent-config`에서 **공식 실행기**만 사용한다.

```sh
# agent-config 저장소 루트, 해당 Hermes uv Python 환경
python3 gearbox/_tests/core_run.py
python3 gearbox/_tests/run.py
```

Payroll 개별 `unittest discover`는 공식 실행기가 설정하는 `PYTHONPATH`가 빠져 import 실패할 수 있다. 이는 계산 실패와 다르며, 기존 테스트 코드를 임의로 바꾸지 않는다.

## 8. 정보보호·운영 경로·버전 관리

- 회사별 임금·근태·직원 자료와 결과 JSON/XLSX에는 개인 식별정보가 포함될 수 있다. **두 Git 저장소, 공개 PR, Slack에 업로드하지 않는다.** 가능하면 사용자 접근 권한이 제한된 로컬 디렉터리를 사용한다.
- 기존 Hermes 읽기 전용 Portfolio 코드: `/opt/agent-config/.external/portfolio`. Hermes 비공개 실행 데이터: `/opt/data/bhandara`(호스트 `/opt/agents/data/hermes/bhandara`). 코드 파일을 데이터 저장소처럼 사용하지 않는다.
- Hermes는 uv Python으로 실행한다. Ubuntu 호스트 Python으로 합격을 판정하지 않는다.
- 새 기능은 이전 검증과 분리해 새 프로젝트/브랜치에서 결정한다. 원본 계산식·계약 변경 시 현재 SHA·기준선과 차이를 명시하고 별도 테스트를 거친다.
- 서버에서 PR 검증할 때 작업 브랜치를 직접 체크아웃해 시험하고, 테스트 후 PR을 Merge한 다음 `main` 최신화 및 로컬 브랜치를 정리한다. Draft PR·worktree 테스트·서버 Git push는 사용하지 않는다.
- 원본 Payroll 이전 경로·Git 해시를 확인할 때는 [이전 이력](payroll-calculator/MIGRATION.md)과 `migration-manifest.json`을 따른다. 지금 보여주는 README/RUNBOOK의 운영 안내가 **최신 정본**이다.

## 9. 문서 안내

- [저장소 시작 안내](../README.md)
- [PTO 사용법](pto-calculator/README.md)
- [Worktime 사용법](worktime-calculator/README.md)
- [Payroll 사용법](payroll-calculator/README.md) · [Payroll 상세 실행서](payroll-calculator/RUNBOOK.md)
- [공통 Base 계약](BASE-CONTRACT.md) · [상호배타 검증 결과](MODULE-ISOLATION.md) · [Golden 비교 계약](GOLDEN-COMPARISON.md)
