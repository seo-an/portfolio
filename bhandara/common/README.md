# Bhandara Common — 계산기 공통 처리

`common/`은 PTO·Worktime·Payroll 중 어떤 계산기 하나만 설치해도 사용할 수 있는 **범용 기능**을 담습니다. 특정 회사의 급여 규칙, 직원 개인정보 처리 정책, 운영 승인 권한은 이 폴더에서 결정하지 않습니다.

## 입력 파일을 읽고 검증하는 기능

| 기능 | 모듈 | 하는 일 |
|---|---|---|
| XLSX 워크북·시트 스트림 | `io/xlsx_stream.py` | 파일 열기·시트 선택·헤더 행 위치·행 순회·닫기만 담당. 셀 값/수식 처리 정책은 호출자가 결정 | 
| CSV·XLSX·JSON 읽기 | `io/tabular.py` | 명시한 파일/시트/인코딩 읽기, 열 이름 중복·누락 확인, 원본 행번호 보존, 입력 폴더 밖 경로 접근 차단 |
| 자료형 변환 | `validation/scalars.py` | 날짜·시간·정수·소수·논리값을 정해진 자료형으로 변환, 모호하거나 잘못된 값 거절 |
| 기존 계산기별 Excel 계약 | `io/xlsx.py`, `io/input_layout.py` | Common 스트림으로 파일을 읽되, 필수 열·셀 및 계산기별 오류 처리 계약은 각각 유지 |
| 설정 처리 | `config/resolver.py` | 외부 전체 JSON과 각 계산기의 `user_settings.py` 중 한 출처 선택 |

### XLSX 읽기 계약을 합치지 않는 이유

2026-11-12부터 `io/tabular.py`와 `io/input_layout.py`는 `io/xlsx_stream.py`의 워크북 열기·시트 선택·행 순회 기능을 재사용합니다. 이 단계에서는 업무별 검증 정책을 공통화하지 않습니다.

| 사용처 | 헤더·수식 처리 | 실패 범위 |
|---|---|---|
| Payroll 원본 매핑 `io/tabular.py` | 모든 헤더는 비어 있거나 중복되면 안 됨. 기존 `data_only=True` 유지(수식의 캐시값을 읽을 수 있음) | 원본 구조 오류는 소스 단위 오류, 값 변환 거절은 매핑 계층 |
| 공유 입력 `io/input_layout.py` → Worktime `shared_excel.py` | 모든 헤더는 고유·비공백. 어떤 수식 셀도 허용하지 않음 | 헤더·수식 오류는 입력 전체 실패; 직원·식별자 확인은 Worktime |
| 공통 검증 `io/xlsx.py` | 필수 헤더만 고유하면 됨. 필수 셀의 수식·누락은 해당 행 거절 | 정상 행을 유지하고 `Finding`을 보고 |
| PTO `src/input_adapter.py` | 필수 헤더만 검사, 선택 이벤트 필드·엑셀 날짜/시간을 자체 변환 | 오류 행의 직원 식별 가능 여부에 따라 개별 직원 차단 또는 전체 차단 |

따라서 `data_only`, 헤더 검사, `Finding` 및 차단 범위를 일괄 변경하면 기존 계산 결과가 달라질 수 있습니다. 다음 단계에서 `io/xlsx.py` 등의 워크북 순회를 순차적으로 재사용하더라도 **기존 오류 코드·행번호·원본 SHA·승인 상태는 그대로** 유지해야 합니다. Worktime `shared_excel.py`는 `input_layout.py`를 사용하므로 이번 변경의 간접 적용 대상입니다.

### PTO XLSX 스트림 적용 (2026-11-13)

PTO의 `src/input_adapter.py`도 Common의 `open_xlsx_rows()`를 사용하여 워크북 열기·시트 선택·행 순회·파일 닫기를 수행합니다. 단, `data_only=False`와 `keep_links=False`를 유지하며, 엑셀의 원본 날짜 기준(`workbook.epoch`)도 그대로 전달합니다.

**PTO 고유 규칙은 이동하지 않았습니다.** 필수 헤더 중복 검사(무관한 추가 열은 허용), 필수 셀 수식 거절, 이벤트 `reduced_hours` 선택 검증, `Finding` 코드·원본 행번호, 직원별 거절 또는 전역 차단, 입력 전후 SHA 확인은 모두 PTO가 담당합니다. Common 스트림은 회사 정책이나 업무 오류의 영향 범위를 결정하지 않습니다.

합성 Excel 회귀 검증: `python -m unittest discover -s bhandara/tests -p 'test_pto_xlsx_stream_contract.py' -v`.

### Common 필수 행 검증 리더 적용 (2026-11-13)

`io/xlsx.py`의 `read_required_rows()`도 공통 `open_xlsx_rows()`를 사용합니다. Excel 열기·시트 선택·헤더 행 위치·행 순회·파일 닫기를 중복 구현하지 않습니다.

**기존 검증 계약은 그대로 유지합니다.** 필수 헤더만 고유하면 추가 열(빈 열·중복된 열 포함)은 무시하고, 필수 셀의 수식이나 누락은 해당 행만 거절합니다. 정상 행은 계속 반환하며 원본 물리 행번호, `FORMULA_UNSUPPORTED`·`REQUIRED_CELL_MISSING`·`NO_DATA_ROWS` Finding, 파일명·시트명·입력 SHA 검증 및 `SpreadsheetInputError`는 그대로 사용합니다. `data_only=False`, `keep_links=False`도 바꾸지 않았습니다.

합성 검증: `python -m unittest discover -s bhandara/tests -p 'test_common_xlsx_validation_stream.py' -v`.

### 회사별 매핑과의 경계

예를 들어 원본 CSV에서 `사번`과 `근로자번호` 중 무엇이 `worker_id`인지 결정하는 **회사별 매핑 규칙**은 Gearbox가 관리합니다. 공개 Bhandara를 단독 사용하는 사람은 계산기별 `manifest.json` 등에 같은 규칙을 직접 적을 수 있습니다. Common은 그 **명시된 규칙을 실행하는 일반 처리 기능**을 제공하되 어떤 별칭·코드가 옳은지 추측하지 않습니다.

급여 계산기 `functions/source_mapping.py`는 회사별로 선택된 컬럼 별칭/`value_map`을 적용하고, Common의 일반 파서와 변환기를 호출합니다. 원본 행번호, 누락·거절 행, SHA 출처 검증을 보존합니다.

**사용자 주의:** Common 파일은 사용자가 직접 편집할 필요가 없습니다. 본인이 설치한 계산기 폴더의 `RUNBOOK.md`와 `user_settings.py`를 먼저 확인하세요. `user_settings.py`는 현재 기간·파일 역할 설정만 지원하며, 수당 정책이나 법정 요건을 추정하지 않습니다.

## 개발·검증

별도 계산기 간 import를 사용하지 않으며, Gearbox나 클라우드 설치도 필요하지 않습니다. `unittest` 검증은 다음처럼 실행합니다.

```bash
python -m unittest discover -s bhandara/tests -p 'test_common_tabular_normalization.py' -v
python -m unittest discover -s bhandara/tests -p 'test_common_xlsx_stream_contract.py' -v
python -m unittest discover -s bhandara/tests -p 'test_common_xlsx_validation_stream.py' -v
python -m unittest discover -s bhandara/tests -p 'test_module_isolation.py' -v
```

**이전 기록:** `payroll-calculator/migration-manifest.json`은 원본 Gearbox 코드의 초기 이관 기록을 유지합니다. 추가 리팩터링은 `post-migration-refactors.json`에서 추적합니다.
