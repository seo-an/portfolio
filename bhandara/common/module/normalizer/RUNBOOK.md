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

## 5. 개발자 검증

```bash
python -m unittest discover -s bhandara/tests -p 'test_common_runner_v2.py' -v
python -m unittest discover -s bhandara/tests -p 'test_common_module_io_v2.py' -v
```

이 모듈은 `common/io`, `common/runtime`, `common/validation`의 함수에 의존하지 않으며, 다른 계산기 설치도 필요하지 않습니다. 에이전트가 실제 호출하기 위한 Gearbox 연결 검증은 후속 단계입니다.
