# Worktime Calculator — 독립 모듈 이전 v0.1.0

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
