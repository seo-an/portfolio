# Normalizer — 독립 실행 데이터 정리 모듈

이 기능은 **입력 파일을 명시한 열 이름으로 정리하여 결과 파일을 만드는 독립 도구**입니다. Common의 재사용 라이브러리를 호출하는 다른 계산기와 달리, Normalizer 자체를 단독 호출할 수 있습니다. PTO·Worktime·Payroll은 자동 실행하지 않습니다.

## 1. 기본 입력·출력 폴더

프로그램 폴더 안에 다음 디렉터리가 **실제로 존재**합니다.

```text
bhandara/common/
├── io/                          # 다른 계산기를 위한 라이브러리
├── validation/                  # 다른 계산기를 위한 라이브러리
└── module/
    └── normalizer/
        ├── module.json
        ├── runner.py
        ├── paths.py
        ├── user_settings.py
        ├── input/                  # 기본 입력
        │   ├── source.csv          # 사용자가 준비 (Git 추적 제외)
        │   └── mapping.json        # 사용자가 준비 (Git 추적 제외)
        └── output/                 # 기본 결과
            └── <run-id>/
                ├── normalizer-result.json
                ├── normalizer-review.json
                └── normalizer-run.json
```

`input/`, `output/`은 빈 폴더 상태로 제공됩니다. 기본 파일이 없으면 오류가 납니다. 파일의 기본 이름은 `user_settings.py`에서 변경할 수 있습니다.

**운영 중요:** 공개 Git 저장소 안의 기본 경로는 합성·개발 자료용입니다. 실제 직원·급여 등 민감자료는 아래의 `--data-root` 방식으로 **Git 체크아웃 밖의 비공개 작업 공간**에 보관하세요. 강제 최신화 스크립트는 Git 무시 파일도 삭제하므로 프로그램 폴더에 실제 자료를 두면 안 됩니다.

## 2. 준비할 파일

`source.csv`는 첫 행에 헤더를 작성합니다.

```csv
staff_number,worked_minutes
E001,450
E002,480
```

`mapping.json`은 원본 헤더를 결과 필드에 대응시킵니다.

```json
{
  "schema_version": "1.0",
  "source_format": "csv",
  "fields": {
    "employee_id": "staff_number",
    "minutes": "worked_minutes"
  },
  "required": ["employee_id"]
}
```

`fields`의 **왼쪽**은 결과 필드명, **오른쪽**은 원본 열 이름입니다. 선택 가능한 `source_format`은 `csv`, `json`, `xlsx`입니다. JSON 하위 배열은 `records_path`, Excel 시트는 `sheet`로 선택합니다. 회사별 수당 규정·법적 판단을 추론하지 않습니다.

## 3. 실행

합성자료로 프로그램 폴더의 기본 `input/`을 쓰는 경우:

```bash
python run.py bhandara common-normalizer --run-id synthetic-001
```

운영 자료를 비공개 공간에서 쓰는 경우, 예를 들어 `/private/bhandara`를 지정하면 다음 폴더를 사용합니다.

```text
/private/bhandara/
└── common-normalizer/
    ├── input/
    │   ├── source.csv
    │   └── mapping.json
    └── output/
        └── run-001/
```

```bash
python run.py bhandara common-normalizer \
  --data-root /private/bhandara \
  --run-id run-001
```

외부 파일을 복사하지 않고 경로로 넘기는 것도 가능합니다.

```bash
python run.py bhandara common-normalizer \
  --data-root /private/bhandara \
  --run-id run-002 \
  --source /private/received/source.csv \
  --config /private/received/mapping.json
```

명시적으로 전달된 경로가 없거나 잘못되면 **기본 파일로 대체하지 않고 오류**가 발생합니다. 결과는 `output/<run-id>/` 아래에 저장되며 기존 실행 건은 덮어쓰지 않습니다.

## 4. 산출물과 경계

- `normalizer-result.json`: 정리된 자료 및 원본 행번호
- `normalizer-review.json`: 빈 필수값 등 검토 정보. 원본 셀 값은 오류 메시지에 포함하지 않음
- `normalizer-run.json`: 실행 식별자, 상태, 원본·결과 SHA-256

`PASS`는 구조 검증만 통과했다는 뜻이며 승인이나 최종 확정이 아닙니다. `BLOCKED` 산출물은 다른 계산기로 자동 전달하지 않습니다. **다른 계산기가 이 결과를 사용하려면, 해당 계산기의 입력 스키마에 적합한지 검증하고 결과 파일 경로를 명시적으로 전달**해야 합니다.

## 5. 다른 계산기에서 Common을 라이브러리로 사용할 때

Normalizer도 `io`, `validation`처럼 **필요한 함수만 import**할 수 있습니다.
`common/module/normalizer/` 폴더를 import해도 독립 실행이 자동으로 시작되거나
`input/`, `output/`의 파일을 읽고 쓰지 않습니다.

공통 기능을 가져와서 함께 사용하는 예시입니다.

```python
from bhandara.common.io import tabular
from bhandara.common.validation import scalars
```

```python
from bhandara.common.module.normalizer import (
    load_mapping,
    read_source,
    transform,
    run_normalizer,
)
```

`load_mapping(path)`은 매핑 JSON을 검증해 반환합니다.
`read_source(path, mapping)`은 원본 행을 읽고,
`transform(rows, mapping)`은 **결과 행과 오류 목록을 반환**할 뿐 출력 파일을 만들지 않습니다.
반면 `run_normalizer(private_data_root, ...)`는 자체 입출력 계약에 따라
`normalizer-result.json` 등의 결과 파일을 씁니다.

| 사용 방식 | 데이터 파일 생성 | 다른 Common 라이브러리 필요 |
|---|---|---|
| `io`, `validation` 함수 import | 함수에 따라 다름 | 해당 기능만 |
| Normalizer `transform()` 호출 | 없음 | 없음 |
| Normalizer `run_normalizer()` 호출 | 있음, 모듈의 `output/<run-id>/` | 없음 |
| `common-normalizer` CLI 실행 | 있음, 모듈의 `output/<run-id>/` | 없음 |

Normalizer 내부는 계산기나 Common 라이브러리를 import하지 않습니다.
반대로 계산기는 Normalizer가 필요하지 않으면 import하지 않아도 됩니다.
이는 **코드 사용 방식**과 **독립 실행 모듈의 파일 전달 계약**을 동시에 지원하기 위한 구조입니다.

## 6. 한 번에 테스트하기

저장소 루트에서 전체 기능과 계산기 회귀 검증을 한 번에 실행합니다.

```bash
python -m unittest discover -s bhandara/tests -p 'test_*.py' -v
```

새로 추가된 검증에는 Common 함수와 Normalizer 동시 import,
Normalizer 공개 API와 CLI 결과 비교, Common 라이브러리 없이 Normalizer만
설치한 격리 실행이 포함됩니다. GitHub Actions에서도 같은 종합 검증을 실행합니다.

별도 `Gearbox`를 통한 Ananda 호출은 **연결 전**이며 위 테스트는
이를 검증하거나 실제 HR 자료를 처리하지 않습니다.
