# Payroll Calculator — Bhandara 독립 모듈 이전 기록

> **상태 (2026-11-10):** 기존 Gearbox 소스를 공개 `portfolio` 작업 브랜치에 이전하고, **합성 입력 동등성·원본 Git 해시 검증 코드를 작성함**. 실제 Hermes 서버 테스트 및 PR Merge 전이며 계산 결과 PASS를 아직 주장하지 않는다.
>
> **프로젝트 경계:** 이번 작업은 **소스 이전과 이전이 잘됐는지만 확인**한다. 계산 로직 수정, 기능 평가, 예외처리 개선, 급여 정책 변경, 직원별 실패 격리 보완, 세금·보험 계산 추가, 승인·마감 기능은 별도 프로젝트에서만 다룬다.

## 원본 및 이전 범위

- 원본: `seo-an/agent-config/gearbox/gear/payroll-calculator/`
- 공개: `seo-an/portfolio/bhandara/payroll-calculator/`
- 원본 커밋: [`migration-manifest.json`](migration-manifest.json)의 `source_commit`에 고정.
- **원본 추적 파일 85개 전체** 이전(기존 `run.py`, `functions/`의 67개 계산·입력·검토 모듈, 정책·계약·예제·기존 RUNBOOK 및 문서 포함).
- **77개는 원본 Git blob SHA와 동일.** 나머지 8개는 `migration-manifest.json`에 선언한 경로/임포트 문자열 변경만 허용한다. 테스트는 해당 문자열만 역변환해 원본 Git blob SHA가 일치하는지 확인한다.
- 다른 경로에서 **4개 원본 자원도 바이트 단위로 그대로 복사**: `gearbox/core/xlsx.py`, `gearbox/diagnostics/catalog.py`, 급여항목 레지스트리 JSON, 2026년 급여 정책 JSON.
- Gearbox 진단 규약 및 날짜 구간 함수는 이전 PTO에서 이미 옮긴 **동일한 내용의 공개 Base** `bhandara/common/contracts/pto_diagnostics.py`와 `bhandara/common/utils/date_interval.py`를 재사용한다. Excel row reader 및 진단 catalog는 이름만 분리한 원본 사본을 공개 Base에 보유한다.
- Worktime close Receipt는 이미 이전 완료된 `bhandara/worktime-calculator/functions/worktime_close.py`를 기존 상대 경로 규칙으로 읽는다. **기존 Worktime 구현을 변경하거나 복제하지 않는다.**

> 원본에서 복사한 `README.md`, `RUNBOOK.md`, `STANDALONE-CLI.md` 등의 기존 문서에는 이전 전 `gearbox/` 경로가 남아 있다. **원본 보존용 기록**이므로 이전 후 CLI·폴더 경로는 이 문서를 우선 사용한다. 문서의 정책/법령 기술은 새로 검증하지 않았다.

## 기존 기능 계약 그대로 보존

### 입력

`normalize`는 예전처럼 원본 폴더의 `manifest.json` 및 CSV/XLSX/JSON 매핑을 읽는다. `calculate`는 예전처럼 `payroll-config.json`에 선언된 보상·월별 급여 입력 XLSX, 근태 인계 자료, 직원·정책·급여항목 레지스트리 등을 읽는다.

- `payroll-config.json`의 `schema_version`은 `"0.1"`을 유지한다.
- Worktime 원본은 기존 계약의 `worktime_result_path`, `worktime_rows_path`, `worktime_closes_path` 중 **정확히 하나**를 사용한다.
- 레지스트리 및 2026년 정책 예제는 공개 모듈의 `resources/`로 이동했다. 실제 운영 파일 경로는 **호출자가 지정하는 기존 계약을 유지**한다.
- 운영 원본 파일, 직원정보, 급여 금액과 산출물은 **Git 저장소 밖의 비공개 폴더**에 둔다. 공개 테스트는 가상 직원만 사용한다.

### 공개 CLI

Portfolio 루트에서 실행한다. 다음 명령은 **이전한 기존 Payroll CLI에 인자만 전달**한다.

```sh
# 이미 준비한 payroll-config.json으로 검토용 급여 계산
python run.py bhandara payroll-calculator \
  --config /private/payroll-config.json \
  --output-dir /private/payroll-review-01

# 기존 Source Mapping normalize
python run.py bhandara payroll-calculator \
  --operation normalize \
  --input-dir /private/source-input \
  --output-dir /private/normalized-01
```

기존 CLI를 직접 호출하는 방식도 유지한다.

```sh
python bhandara/payroll-calculator/run.py calculate \
  --config /private/payroll-config.json \
  --output-dir /private/payroll-review-02

python bhandara/payroll-calculator/run.py normalize \
  --input-dir /private/source-input \
  --output-dir /private/normalized-02
```

기존 `--scenario-id` 및 `--manifest`는 최상위 Portfolio CLI에서도 동일하게 전달할 수 있다.

### 산출물 및 승인 경계

원본 CLI의 상태·종료 코드·파일 구조를 변경하지 않았다.

- `calculate` 정상 계산은 **검토 전용 `REVIEW_REQUIRED` / exit 2**이다. 직원 결과가 있어도 `finalizable=false`, `ledger_committed=false`이며 최종 급여·지급 승인을 생성하지 않는다.
- 정상 계산 시 `payroll-calculation.json`, `payroll-calculation.xlsx`, `payroll-review.json`, `payroll-review.xlsx`, `policy-resolution.json`의 기존 5개 파일을 사용한다.
- 계산 전 계약 오류 또는 엔진 오류에서는 원본 구현처럼 `payroll-review.json`와 `payroll-review.xlsx`만 생성할 수 있다. 원본 계산기 오류 정책은 이번 이전에서 바꾸지 않는다.
- `normalize`는 원본 정상 `READY_FOR_CALCULATION`의 종료 코드 0, 그 외 2를 유지한다.
- 기존 Payroll Workflow, Settlement Ledger 작성/마감, 원천세·보험료 확정·실제 송금은 이번 변경에 포함되지 않는다.

## 이전 검증

**범위:** 85개 원본 파일 SHA, 8개 경로 변경의 정확한 역변환, 자원 4개 SHA, 기존 Payroll CLI 직접 호출 vs Portfolio CLI로 같은 합성 자료를 계산했을 때 JSON/XLSX 내용과 종료 코드가 같은지 검사한다. 이는 **이전 동등성 검증**이며 새 정책 테스트가 아니다.

```sh
# portfolio 저장소 루트, Hermes uv Python을 사용
python -m unittest discover -s bhandara/tests \
  -p 'test_payroll_migration.py' -v

python -m unittest discover -s bhandara/tests \
  -p 'test_*.py' -v

python install.py --check
```

기존 Gearbox의 기능·인프라 회귀 테스트는 원본 저장소에서 실행한다. 새로운 계산·예외 처리 기능을 위한 추가 테스트는 설계하지 않는다.

### Hermes 서버 PR 브랜치 테스트

```sh
cd /opt/agents/config/agent-config/.external/portfolio
sudo git status --short
sudo git fetch origin feat/bhandara-payroll-migration
sudo git switch -c feat/bhandara-payroll-migration \
  --track origin/feat/bhandara-payroll-migration

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_payroll_migration.py' -v

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_*.py' -v

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python install.py --check

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -m unittest discover \
  -s gearbox/_tests/gear/payroll-calculator -p 'test_*.py' -v

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python gearbox/_tests/core_run.py

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python gearbox/_tests/run.py
```

**서버 검증을 통과한 후에만 Merge.** 기존 `agent-config` 실행 경로, Hermes Plugin, n8n/Slack, 실제 직원자료는 변경하지 않는다.
