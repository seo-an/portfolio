# Common 데이터 정리 모듈 — 사용 안내

Common도 PTO·Worktime·Payroll과 마찬가지로 **혼자 실행하는 도구**입니다. 원본 파일을 받아서 사용자가 지정한 열 이름으로 정리하고, 본인 전용 `output/`에 결과를 저장합니다.

다른 계산기를 쓰기 전에 반드시 Common을 실행할 필요는 없습니다. 이미 해당 계산기 입력 규격에 맞는 파일이 있다면 그 파일을 직접 사용하세요.

## 1. 어디에 파일을 두나요?

**실제 직원·급여·근태 자료는 Git 저장소에 넣지 마세요.** 먼저 Git 작업 폴더 밖에 개인용 데이터 폴더를 마련합니다. 예를 들어 `/private/bhandara/`를 사용한다면 다음과 같습니다.

```text
/private/bhandara/
└── common/
    ├── input/
    │   ├── source.csv       ← 정리할 원본
    │   └── mapping.json     ← 열 이름을 어떻게 바꿀지 정의
    └── output/
        └── common-001/      ← 한 번의 실행 결과
            ├── common-result.json
            ├── common-review.json
            └── common-run.json
```

`common-001`처럼 실행 건마다 다른 이름을 사용합니다. 이전 결과는 덮어쓰지 않습니다.

다른 계산기도 동일한 원칙으로 각자의 `input/`·`output/`을 사용합니다. Common이 다른 계산기의 폴더를 직접 수정하지 않습니다.

## 2. 원본 파일을 어떻게 만드나요?

가장 단순한 예시는 `source.csv`입니다. 첫 행에 열 이름을 넣고, 그 아래에 자료를 입력합니다. 예시의 사번은 가상값입니다.

```csv
staff_number,worked_minutes
E001,450
E002,480
```

CSV 외에 JSON, XLSX도 지원합니다. Excel은 첫 행을 헤더로 사용하며, 수식 계산값을 추측하지 않습니다. JSON은 배열 또는 `records_path`로 지정한 배열을 사용합니다.

## 3. 열 이름을 어떻게 지정하나요?

`common/input/mapping.json`을 다음과 같이 작성합니다.

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

- `source_format`: 원본 형식. `csv`, `xlsx`, `json` 중 하나
- `fields`: **왼쪽이 결과에 쓸 이름**, 오른쪽이 원본 파일의 **정확한 열 이름**
- `required`: 빈 값이 있어서는 안 되는 결과 필드
- XLSX의 특정 시트를 읽으려면 `sheet`에 시트 이름을 지정합니다.
- JSON 객체의 하위 배열을 읽으려면 `records_path`에 위치를 적습니다.

이 설정은 **데이터 구조**를 정하는 것이며 회사 정책·급여 산식·법적 판단을 정하지 않습니다.

## 4. 실행하기

Portfolio 저장소의 루트에서 현재 사용하는 uv Python 환경으로 실행합니다.

```bash
python run.py bhandara common \
  --data-root /private/bhandara \
  --run-id common-001
```

여기서 `--data-root`는 `common/`의 **상위 폴더**입니다. Common은 자동으로 `common/input/source.csv`와 `common/input/mapping.json`을 찾습니다.

다른 곳에 있는 원본을 사용하고 싶다면 파일을 Common 입력 폴더에 복사할 필요가 없습니다.

```bash
python run.py bhandara common \
  --data-root /private/bhandara \
  --run-id common-002 \
  --source /private/received/new-source.csv \
  --config /private/policies/mapping.json
```

`--source`와 `--config`에는 절대 파일 경로를 전달할 수 있습니다. **명시한 파일이 없거나 잘못되면 실행을 중지**하며 기본 파일로 자동 대체하지 않습니다. 접근 가능한 외부 경로를 누가 전달해도 되는지는 단독 실행자 또는 Gearbox의 권한 관리 책임입니다.

## 5. 어떤 결과가 나오나요?

| 파일 | 내용 |
|---|---|
| `common-result.json` | 정리된 행과 원본 행번호, 상태, 원본 SHA-256 |
| `common-review.json` | 누락된 필수값의 행번호·필드 등 검토 사항(원본 셀 값 제외) |
| `common-run.json` | 실행 ID, 모듈 버전, 입출력 SHA-256 등 실행 추적 정보 |

상태가 `PASS`이면 기본 구조 검사를 통과했다는 뜻일 뿐, 인사·급여 정책이나 계산 결과가 승인되었다는 뜻은 아닙니다. 필수값 누락이 발견되면 상태가 `BLOCKED`이며 **불완전한 결과를 다른 계산기로 자동 전달하지 않습니다.**

## 6. 다른 계산기로 전달할 때

예를 들어 Common 결과를 Worktime 입력으로 쓰려면 **Worktime이 요구하는 실제 JSON 형식인지 별도로 확인한 후** 그 파일의 전체 경로를 Worktime 호출에 전달합니다. Common이 만들었다고 해서 Worktime·PTO·Payroll의 계약과 자동 호환되는 것은 아닙니다.

```text
Common/input → Common 정리 → Common/output/<run-id>/common-result.json
                                          │
                                          └─ (명시 경로 + 대상 모듈 입력 검증)
                                                       ▼
                                              대상 모듈/input 선택
                                                       ▼
                                              대상 모듈/output/<run-id>/
```

경로만 전달하며 파일 복사는 의무가 아닙니다. 단일 계산 요청이라면 Common을 호출하지 않습니다. Workflow 연결은 4단계에서만 진행합니다.

## 7. 보안·검증

모듈은 인터넷 접근, 파일 원본 변경, 자동 승인, 파일 자동 삭제를 수행하지 않습니다. **민감자료의 접근권한·보존기간·삭제·백업 제외는 운영자와 Gearbox에서 관리**합니다. 공개 저장소의 예시에는 합성자료만 사용하세요.

합성 단위 테스트는 다음과 같습니다.

```bash
python -m unittest discover -s bhandara/tests -p 'test_common_module_io_v2.py' -v
python -m unittest discover -s bhandara/tests -p 'test_common_runner_v2.py' -v
```

계산기별 기존 Excel 처리 규칙은 변경하지 않았습니다. 실제 계산 결과, 다른 모듈과의 입력 형식 일치, 민감자료의 실행 중 삭제 검증은 후속 단계에서 별도로 확인합니다.
