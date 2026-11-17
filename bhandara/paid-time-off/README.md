# Paid Time Off — 한국 연차유급휴가 도구 (재설계 중)

> **현재 상태: Entitlement(연차 발생) 독립 계산 및 Excel 출력 시범 구현.**
> 전체 Tool CLI, Gearbox 연결, 이월·만료·사용·마감과의 통합은 아직 제공하지 않습니다.
> 기존 `pto-calculator` v0.2.1은 변경하지 않았습니다.

## 1. Entitlement(연차 발생)에서 하는 일

- 입사일 기준 연차 발생량: 근속 가산분은 산식 안에서 처리합니다.
- 1년 미만 월별 연차 발생량: **근태관리에서 이미 판정한 '개근/미개근/판정 안됨'**만 읽습니다.
- 회계연도 기준 **최초 비례연차**: 소정근로일 기준을 기본으로 하며 달력일·월수 방식도 선택할 수 있습니다.
- 연차 발생 건별 상세와 직원별 발생요약을 **한 번에 두 시트로 출력**합니다.
- 발생요건을 재판정하지 않고 `eligibility` Module을 호출하지 않습니다.
- 사용·이월·만료·수당·잔여연차는 계산하지 않습니다.

**제한:** 최초 비례연차 이후의 회계연도 부여 정책은 아직 협의하지 않았으므로 해당 시점에 도달한 경우 **'판정 안됨'**으로 표시합니다. 회계연도 비례분 역시 해당기간의 연간 근태 플래그가 확정되어야 계산합니다.

## 2. Excel 입력

기본 공유 입력 루트: `bhandara/data/input/`

| 파일 | 시트 | 필수 열(영문 snake_case) | 비고 |
|---|---|---|---|
| `common/employee.xlsx` | `재직자`, `퇴사자` | `employee_id`, `hire_date` | `termination_date`는 퇴사자 필수; `work_system`은 기존 자료 유지 |
| `paid-time-off/attendance-result.xlsx` | `근태결과` | `employee_id`, `period_start`, `period_end`, `check_type`, `attendance_flag` | 출퇴근 원본이 아닌 근태 판정 결과 |
| `paid-time-off/proration.xlsx` | `비례자료` | `employee_id`, `period_start`, `period_end`, `method`, `numerator`, `denominator` | 회계연도 최초 비례 계산할 때 필요; `base_days` 선택, 기본 15일 |

Excel은 사람이 읽는 **셀 값에 한국어**를 사용합니다.

- `check_type`: `월간` 또는 `연간`
- 월간 `attendance_flag`: `개근`, `미개근`, `판정 안됨`
- 연간 `attendance_flag`: `80% 충족`, `80% 미충족`, `판정 안됨`
- `method`: `소정근로일 기준`(기본), `달력일 기준`, `월수 기준`

근태 판정 기간은 반드시 `period_start`, `period_end`의 **두 열**로 나누어 기재합니다. 날짜 값은 `YYYY-MM-DD` 형식입니다. 근태 플래그가 없으면 `개근`이라고 추정하지 않고 `판정 안됨`으로 표시합니다.

소정근로일 수는 일반 연차 발생 계산에는 불필요합니다. **회계연도 비례연차**의 산식에만 명시적인 분자·분모 집계를 요구합니다. 이 두 수치는 근태·스케줄 처리에서 가져오는 값이며 Entitlement가 출근율을 다시 계산하지 않습니다.

## 3. 결과 Excel

한 번 실행하면 `<output_root>/<run_id>/entitlement-result.xlsx` 파일이 생깁니다.

1. **발생요약:** 직원별 한 행. `employee_id`, `basis`, `계산결과`(반올림 전 합계), `발생연차`(최종 반올림), `상태`
2. **발생상세:** 발생 건별 한 행. 발생일, 산정기간의 시작일·종료일, 구분, `계산결과`, 상태와 사유. **발생 건마다 반올림하지 않습니다.**
3. **정책정보:** 마지막 시트. 정책 ID, 산정 기준일, 입력 파일·SHA256, 비례 산정 방식, 최종 반올림 자릿수 등. 직원별 행에 반복 기록하지 않습니다.

어느 한 건의 필수 근태 판정이 누락·미확정이면 그 직원의 요약 `발생연차`는 빈 값이고 상태는 `판정 안됨`입니다. 다른 직원의 자료와 혼동하지 않습니다.

**소수점 규칙:** 중간 계산은 유리수로 정확히 유지하고 반올림하지 않습니다. 무한소수는 상세·요약의 원본 표기 시 소수점 아래 **7자리에서 절사**합니다. 모든 발생 건을 합산한 뒤 **마지막에만 한 번 반올림**하며, 결과 자릿수는 정수(`0`) 또는 소수점 첫째 자리(`1`, 기본) 중 선택합니다.

## 4. 라이브러리 방식으로 시범 실행

Python 실행 환경에 루트 `requirements.txt`의 의존성이 설치되어 있어야 합니다.

```python
from datetime import date
from importlib import import_module
from pathlib import Path

runner = import_module("bhandara.paid-time-off.runner")
result = runner.run_entitlement(
    as_of_date=date(2026, 12, 31),
    basis="입사일 기준",  # 또는 "1년 미만 기준", "회계연도 기준"
    policy_id="회사연차-2026",
    run_id="sample-2026",
    input_root=Path("bhandara/data/input"),
    rounding_digits=1,  # 0=정수, 1=소수점 첫째 자리
)
print(result["path"])
```

이 예제는 **대상 파일을 준비한 뒤 실행하는 라이브러리 호출**입니다. 아직 최상위 `bhandara/run.py`의 공개 Tool CLI 명령으로 연결되지 않았습니다. 같은 `run_id`의 출력은 덮어쓰지 않습니다. 실제 직원자료는 Git 체크아웃 외부의 비공개 입력 루트를 명시하여 사용하십시오.

## 5. 검증

```bash
python3 -m unittest bhandara.tests.test_paid_time_off_v3_core -v
python3 -m unittest bhandara.tests.test_paid_time_off_entitlement_excel -v
python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
```

다른 Module의 정책 및 전체 Workflow는 계속 설계 중입니다. `ARCHITECTURE.md`에 이관 경계가 설명되어 있습니다.
