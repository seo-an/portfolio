# Golden JSON 의미 비교기 — Phase 1 / PR #2

**목적:** 기존 Gearbox 결과와 포트폴리오 이관 결과를 숫자·상태·검토 사유 단위로 비교한다. 원본 Golden은 서버 비공개 데이터이고 공개 Git에는 포함하지 않는다.

## 사용법

동일한 가상 입력, 같은 정책·계산기간, 검증된 Python/모듈 버전으로 실행한 결과 두 개를 사용한다.

```bash
# Root is seo-an/portfolio; Python is your approved uv-managed interpreter.
python run.py compare-golden --profile payroll-workflow \
  --expected /private/bhandara/baseline/output \
  --actual /private/bhandara/candidate/output

python run.py compare-golden --profile pto-golden \
  --expected /private/bhandara/pto-golden.json \
  --actual /private/bhandara/new-pto-golden.json
```

PTO 결과는 `source_commit`, `source_hashes`, `period`, `results`가 있는 **정규화된 Golden JSON**이어야 한다. 기존 PTO 준비 단계가 발급하는 run-scoped 익명 UUID를 합성 직원 ID로 변환한 뒤 비교한다. 임의의 실명/사번 자료는 공개 Git에 보관하지 않는다.

### 비교 대상

`payroll-workflow`는 다음 9개 JSON 파일을 처리한다.

| 경로 | 방식 |
|---|---|
| `workflow-run.json` | 비결정성 실행 ID·시간·출력경로·파일바이트 SHA만 제거; 단계 상태·건수·검토 건수·산출물 종류·입력 설정 SHA 비교 |
| `01-normalized/normalized-input.json` | 전체 JSON 비교 |
| `01-normalized/review-report.json` | 전체 JSON |
| `02-worktime/worktime-result.json` | 전체 JSON, 승인/마감 여부 검증 |
| `02-worktime/worktime-review.json` | 전체 JSON |
| `04-payroll/payroll-calculation.json` | 전체 JSON, 급여 확정·장부 기록 금지 검증 |
| `04-payroll/payroll-review.json` | 생성된 XLSX의 바이너리 해시가 포함된 루트 `source_hashes`만 제외하고 전체 JSON 비교 |
| `04-payroll/policy-resolution.json` | 전체 JSON, 확정 금지 검증 |
| `04-payroll/provisional-payroll-register.json` | 전체 JSON, `null`과 0 구별 및 계산 상태·실지급액 비교 |

`pto-golden`은 전체 Golden JSON에서 이전 Git 버전인 `source_commit`만 제거한다. 원본 입력 해시, 계산기간, 직원별 부여·미해결 기록은 모두 비교한다.

`strict-json`은 임의의 두 JSON 파일을 **모든 필드·배열 순서·타입 그대로** 비교한다. 구체적인 파일 하나를 조사할 때 유용하다.

### 안전한 실패 규칙

- `GOLDEN_PASS` / 종료코드 0: 선택한 프로필에서 의미 비교 통과
- `GOLDEN_DIFF` / 종료코드 1: 의미값·결과 구조 차이 발생
- `GOLDEN_INVALID` / 종료코드 2: 파일 누락, 잘못된 JSON, 잘못된 스키마 또는 승인 경계 위반
- 비교 과정은 입력을 수정하지 않는다. 기본 메시지에는 직원 실명, 지급액 등 **원본 값이 아닌 JSON Pointer 경로와 차이 종류만** 출력한다.
- `bool`, 정수, 실수, `null`, 문자열을 구분한다. JSON 객체의 중복 키와 비유한 값(NaN/Infinity)은 실패 처리한다.
- 메타데이터 제외는 재귀적인 단어 패턴이 아니라 위 경로의 정확한 필드에 한정한다. 시각이나 ID라는 이름이 붙은 **업무 필드**를 자동으로 버리지 않는다.

## 아직 보증하지 않는 항목

- **XLSX 셀·수식·시트·서식의 논리 비교는 미구현.** 파일바이트 SHA를 결과 동등성으로 간주하지 않는다.
- `03-payroll-input/` 산출물과 `payroll-source-lineage.json`은 이 9개 JSON 비교 목록에 포함되지 않는다. 이관 시에는 별도 검증이 필요하다.
- 비교기의 PASS는 선택한 Golden 결과가 같다는 의미다. 노동법 적합성, 급여 프로그램과의 일치, 최종 결재를 뜻하지 않는다.
- 입력/정책/원본 SHA 검증은 보관된 `SHA256SUMS.txt`와 입력 설정 해시를 별도로 검사해야 한다.
- 기존 Gearbox `run.py run` 명령은 `REVIEW_REQUIRED`를 **exit 2**로 반환하는 설계이며, Golden 비교기의 exit 2와 별도의 실행이다.

## 테스트

```bash
python -m unittest discover -s bhandara/tests -p 'test_*.py' -v
python run.py compare-golden --help
```

실제 운영환경에서는 Hermes `uv` 관리 Python `3.14.9`로 PR 브랜치에서 직접 테스트한다. 실데이터는 테스트 출력과 Git에 올리지 않는다.
