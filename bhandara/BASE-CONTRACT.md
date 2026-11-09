# Bhandara Base — 공개 공통 계약 v0.1

**구현 상태:** Excel 필수 컬럼 추출, 진단 결과, 원본 SHA-256, 안전한 산출물 생성과 실행 기록은 구현됨. **PTO/Worktime/Payroll 계산기, 사용자용 계산 CLI, 모듈 스키마 자동 검색은 미구현.**

## 1. 소유권과 환경

- 모든 실행·출력 파일은 사용자 관리의 **비공개 로컬 디렉터리**에 둔다. Git(이 저장소 또는 `agent-config`)에 실제 직원/급여/근태자료를 넣지 않는다.
- 기본 런타임 기준: Hermes `multi-agents-hermes:1.2.0`, uv 관리 Python **3.14.9**; 외부 종속성은 승인된 `openpyxl==3.1.5` 한 가지. 본 저장소 최상위 `requirements.txt`가 유일한 설치 목록이다.
- `install.py --check`는 Python 및 설치 버전을 **읽기 전용으로 확인**한다. 패키지 설치/운영환경 변경은 하지 않는다.
- 공개 Base는 Python 함수 API다. Hermes, Drive, Slack, 인증, 급여 지급·승인은 연결하지 않는다.

## 2. Excel 입력 및 행별 진단

`bhandara.common.io.xlsx.read_required_rows(path, required_headers, sheet_name=None, header_row=1)`:

- `.xlsx`/`.xlsm`만 읽으며 원본을 **수정하지 않는다**. 읽기 전후 SHA-256을 검증하고 변경 시 실패한다.
- **필수 헤더는 정확히 하나씩** 존재해야 한다. 헤더 앞뒤 공백은 제거한다. 필수 헤더가 없거나 중복되면 `SpreadsheetInputError` (전체 시트 매핑 불가).
- **추가 컬럼은 전부 무시한다.** 불필요한 빈/중복 헤더도 오류가 아니다.
- 데이터 행의 필수 셀 `None`, 빈 문자열, 공백만 있는 문자열은 **행 오류**로 기록한다. 해당 행만 제외하고 나머지 행은 그대로 반환한다.
- **0과 False는 유효한 입력값이다.** 빈 셀로 간주하지 않는다.
- 필수 셀의 Excel 수식은 계산하지 않고 `FORMULA_UNSUPPORTED`로 행 오류 처리한다. cached formula 값이나 출근·승인을 추정하지 않는다.
- 완전히 비어 있는 행은 건너뛴다. **필수 셀이 비었더라도 다른 열에 값이 있는 행은 오류로 남긴다.** 데이터가 전혀 없으면 `NO_DATA_ROWS`로 `ERROR` 처리한다.
- `SheetReadResult`는 `rows`(값과 원본 Excel 행 번호), `findings`, `source_sha256`, `accepted_rows`, `rejected_rows`, `nonempty_rows`, `status`를 제공한다. 입력값과 오류 코드/위치를 분리한다.

오류 계약: `Finding`에는 `code`, `severity`, `scope`, `message`, `source`(파일명), `sheet`, `row_number`, `field`가 포함되며 **실제 셀 값은 기본 오류 객체에 넣지 않는다**. 작업 상태는 `summarize_status(findings)`로 결정한다. 오류가 한 건이라도 있으면 `ERROR`, 오류 없이 검토 사항만 있으면 `REVIEW_REQUIRED`, 모두 없으면 `PASS`다. 이 상태는 **실제 계산 결과 승인/최종 확정과 무관하다.**

## 3. 산출물 일괄 예약·충돌 버전

`bhandara.common.runtime.artifacts.ArtifactBatch`:

```python
from bhandara.common.runtime.artifacts import ArtifactBatch

with ArtifactBatch("/private/output", ["result.json", "review.json"]) as batch:
    batch.write_json("result.json", {"status": "REVIEW_REQUIRED"})
    batch.write_json("review.json", {"findings": []})
    saved = batch.commit()
```

- 기존 파일을 **덮어쓰지 않는다.** 하나라도 이미 존재하면 같은 실행에 포함된 **모든 파일**에 동일 번호 `(1)`, `(2)` 등을 붙인다.
- 여러 프로세스/스레드의 동시 실행은 파일별 `O_EXCL` 예약으로 충돌을 방지한다. 파일별 내용은 스테이징 후 `os.replace`로 원자적으로 게시된다.
- 준비 도중 예외, 미완성 배치, 게시 중 예외가 발생하면 **이번 실행이 생성한 파일만** 롤백한다. 다른 실행 및 이전 산출물은 건드리지 않는다.
- `write_bytes()`는 생성한 XLSX 등의 바이너리를 저장하며, `copy_file()`은 원본을 변경하지 않고 복사한다. `staged_hashes()`는 게시 전 파일 해시를 반환한다.
- 출력 파일은 생성 시 `0600`, 새 출력 디렉터리는 기본 `0700`(POSIX 기준). 파일명에 하위 경로, 절대경로, 숨김 파일을 허용하지 않는다.

**한계:** 여러 파일이 *동시에* 보이는 원자적 트랜잭션은 아니다. 각 파일은 원자적으로 교체되지만, 배치 내 게시 순서 사이에 다른 프로세스가 일부 파일을 볼 수 있다. 시스템 강제 종료·정전으로 남는 예약 빈 파일의 자동 복구, 네트워크 파일시스템의 `O_EXCL` 보장은 별도 작업 대상이다. **실제 운영 소비자는 전체 배치가 완성되었음을 검증한 후 사용**해야 한다.

## 4. 실행 이력

`bhandara.common.runtime.receipt.build_receipt()`는 `module_id`, `module_version`, `run_id`, 기록 시각, `input_sha256`, `output_sha256`, 오류 목록, `status`, `approved=False`, `finalizable=False`를 가진 JSON 객체를 생성한다.

```python
from bhandara.common.runtime.receipt import build_receipt

with ArtifactBatch("/private/output", ["result.json", "run-receipt.json"]) as batch:
    batch.write_json("result.json", {"rows": []})
    receipt = build_receipt(
        module_id="pto-calculator", module_version="0.1.0",
        input_files={"employee": "/private/employee.xlsx"},
        output_sha256=batch.staged_hashes(), findings=[],
    )
    batch.write_json("run-receipt.json", receipt)
    saved = batch.commit()
```

기록 파일의 SHA를 자기 자신에게 포함하지 않아 순환 참조를 피한다. 상태가 `PASS`여도 `approved`와 `finalizable`은 **항상 False**다. 이 버전에서는 별도 서명/승인 체계를 구현하지 않는다.

## 5. 개발·검증

```bash
# portfolio 저장소 루트에서, 승인된 uv 관리 Python으로 실행
python -m unittest discover -s bhandara/tests -p 'test_*.py' -v
python install.py --check
```

`unittest` 전용 합성 Fixture만 이용한다. 실제 기업 데이터나 비공개 Golden JSON을 공개 Git에 올리지 않는다. 기존 Gearbox 계산 엔진과의 Golden 비교는 `run.py compare-golden`의 별도 기능으로 수행한다.
