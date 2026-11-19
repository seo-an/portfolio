# Bhandara Common · 보안업체 직원 매핑 v0.2

## 목적과 경계

**정본은 하나의 `common/id-map.xlsx` 파일**입니다. 신규 Worktime의 보안업체 원본 정규화용으로 다음 세 시트를 읽습니다.

| 시트 | 필수 헤더 | 의미 |
|---|---|---|
| `PERSON MAP` | `employee_id, name, security_department_id, security_id, worker_id, payroll_id, security_person_id, main_area` | 직원·업체 등록 정보 |
| `DEPARTMENT MAP` | `department, security_department_id` | 업체 원본 부서와 보안 부서 ID 연결 |
| `AREA MAP` | `area, security_area_id` | 장소 코드 참조 |

일반적으로 한 업체와만 계약하므로 단일 업체 사용을 기본으로 합니다. **다중 계약을 위해 별도 열을 늘리지 않습니다.** 동일 직원이 복수 업체에 등록됐다면 `PERSON MAP`에 **같은 `employee_id`로 업체별 행을 하나씩 추가**할 수 있습니다.

**한 행 = 직원 1명 × 보안업체 1곳**입니다. 한 직원이 여러 업체에 등록되면 행 수는 직원 수와 같지 않습니다.

## PERSON MAP 필드

| 열 | 의미 | 읽기 규칙 |
|---|---|---|
| `employee_id` | 공통 직원 ID | 필수. 복수 업체에 걸쳐 중복 가능 |
| `name` | 보안업체 성명 확인용 | 선택. 이름만으로 직원 식별 금지 |
| `security_department_id` | 보안시스템 부서 식별자 | `security_person_id`와 함께 직원 식별 |
| `security_id` | **보안업체 구분값** | 필수. `CAPS`, `SECOM`, `TELECOP` 또는 `KT_TELECOP` |
| `worker_id` | 계산 도구 간 공통 근로자 ID | 필수, 동일 직원의 여러 행에서 일치 |
| `payroll_id` | 급여시스템 직원 ID | 선택, 값이 있으면 동일 직원의 여러 행에서 일치 |
| `security_person_id` | 보안시스템 사람 식별자/사번 | 부서 ID와 조합하여 식별 |
| `main_area` | 주 출입 장소 `security_area_id` | 선택, `AREA MAP`과 검증 |

- `security_id`는 **개별 직원의 고유 보안번호가 아니라 업체 코드**입니다. 동일한 업체명이 여러 행에 반복되는 것은 정상입니다.
- 업체별 직원 식별 키: **`(security_id, security_department_id, security_person_id)`**.
- 동일 `employee_id`에서 업체별 `worker_id`, 입력된 `payroll_id`, 입력된 `name`이 모순되면 차단합니다.
- 동일 `(employee_id, security_id)`가 두 번 나오거나 업체·부서·사람 ID 조합이 중복되면 차단합니다.
- `security_department_id`와 `security_person_id` 중 하나만 있거나, 부서 ID가 `DEPARTMENT MAP`에서 해석되지 않으면 **선택한 업체의 해당 행을 매핑하지 않고 검토 사유를 반환**합니다. 다른 업체·다른 직원으로 추정하지 않습니다.
- `security_person_id`의 `001`, `0007` 등은 Excel에서 **텍스트 값**으로 저장해야 합니다.
- 보안업체별 새로운 열을 추가하더라도 **추가 열은 공식 지원하지 않으며 프로그램이 읽지 않습니다**. 사용자 보관용 임의 열은 허용하되, 필수 열 이름 변경/삭제는 허용하지 않습니다.
- 데이터 중복이나 서로 다른 직원 간 ID 충돌은 선택 업체에 관계없이 검사하여 공통 정본의 일관성을 보장합니다.

## DEPARTMENT MAP 및 AREA MAP

- `DEPARTMENT MAP`은 보안업체 원본의 **부서 문자열**을 `security_department_id`에 대응시킵니다. 코드만 있고 부서명이 없는 미완성 행은 사용하지 않습니다.
- `AREA MAP`은 `main_area` 등 장소 코드의 조회용입니다. **장소가 다르다는 이유만으로 출근 여부·연장근로를 확정하지 않습니다.**
- 현재 두 시트에는 업체 열이 없습니다. 복수 업체에서 **같은 부서 ID를 서로 다른 부서에 재사용**하는 등 코드가 충돌하면 이 시트만으로 정확한 대응이 불가능하므로 검토/정리가 필요합니다.
- `main_area`가 등록되지 않았다면 해당 업체 행에 `MAIN_AREA_UNMAPPED` 진단을 남기되, 직원 ID 매핑 자체는 유지합니다.

## 코드 사용

```python
from bhandara.common.io.security_person_map import read_security_person_map

mapping = read_security_person_map(
    "/private/input/common/id-map.xlsx", vendor="CAPS",
)
identities = mapping["identities"]  # CAPS 행만
issues = mapping["issues"]          # 선택 업체 매핑 누락 진단
```

```python
from bhandara.worktime.vendor_adapters import normalize_vendor_excel

result = normalize_vendor_excel(
    "/private/input/caps-original.xlsx",
    "/private/output/access-events.xlsx",
    vendor="CAPS",
    id_map_path="/private/input/common/id-map.xlsx",
)
# result["identity_mapping_reviews"]에서 Common Mapping 검토 사유 확인
```

업체 원본에서 `부서 + 사번`을 먼저 읽고 위 매핑과 대조한 뒤 정규화된 `access-events.xlsx`를 만듭니다. 이 파일은 **Attendance Verification 입력 자료 중 출입기 record**이며, Worktime 최종 보고서가 아닙니다.

### 구형 계산기와 호환성

기존 `bhandara.common.io.input_layout.read_id_map()`의 **`ID_MAP` 시트와 개인별 고유 `security_id` 계약은 그대로 둡니다**. 구형 `worktime-calculator`/Payroll/Gearbox 운영을 이번 PR로 전환하지 않습니다. 신규 `PERSON MAP`은 신규 Worktime의 보안업체 정규화 경로에서 읽습니다.

동일 파일에 기존 `ID_MAP`과 신규 `PERSON MAP`을 무조건 중복 유지해야 한다는 뜻이 아니라, **두 리더의 계약과 전환 시점을 분리**했다는 의미입니다. 운영 시스템을 전환하기 전 기존 의존성을 별도 검토해야 합니다.

## 통합 합성 샘플 생성

`bhandara/examples/sample/generate.py --output-dir /tmp/bhandara-sample-80`을 사용자가 **명시적으로 실행할 때에만** 한 세트의 합성 샘플을 생성합니다. 생성되는 `common/id-map.xlsx`에는 구형 `ID_MAP` 및 `EXTERNAL`과 함께 신규 `PERSON MAP`, `DEPARTMENT MAP`, `AREA MAP`을 넣습니다. 기존 코드의 개인별 `security_id`와 신규 매핑의 업체 `security_id`는 서로 다른 시트에서만 사용합니다. 구형 계산기의 매핑을 신규 매핑으로 은밀하게 대체하지 않습니다.

생성된 신규 `PERSON MAP`은 가상 직원 80명의 CAPS 등록 및 같은 직원의 SECOM/TELECOP 추가 등록 2개 행을 포함합니다. 업체별 추가 열은 생성하지 않습니다. 정식 공개 샘플 교체는 `refresh.py --apply`의 별도 명시적 실행만 허용합니다. 일반 코드 변경·CI는 샘플을 자동 갱신하지 않습니다.

## 상태 및 테스트

- 합성 예제로만 검증하며 실제 직원·회사 식별 자료를 공개 Git에 보관하지 않습니다.
- `python3 -m unittest bhandara.tests.test_common_security_person_map -v`
- `python3 -m unittest bhandara.tests.test_worktime_vendor_adapters -v`
- Bhandara 전체 unittest 및 Gearbox 기능/인프라 호환성은 PR 병합 전 별도 서버 실행이 필요합니다.
- 보안업체 1곳 기반 사용이 우선이며, 다중 업체 지원은 **직원×업체 중복 행 + 업체 선택 필터** 범위로 제한합니다.
