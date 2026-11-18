# Paid Time Off — 한국 연차유급휴가 도구 (재설계 중)

> **현재 상태 (2026-11-18): Entitlement·Deduction Quantity의 독립 Excel 및 Tool 내부 Allocation·Expiry 순수 API 구현. PR #42에서 ID 참조/사용내역 Excel 시험 경로 추가.**
> 전체 Tool CLI·manifest·Gearbox/Slack 연동, 차감 배정·만료·이월의 **순수 Python API는 초기 구현**, Excel/Tool 연결·Closing은 미구현입니다.
> 기존 `pto-calculator` v0.2.1과 Gearbox 버전 게이트는 변경하지 않았습니다.

## 1. Entitlement(연차 발생)에서 하는 일

- 입사일 기준 연차 발생량: 근속 가산분은 산식 안에서 처리합니다.
- 1년 미만 월별 연차 발생량: **근태관리에서 이미 판정한 '개근/미개근/판정 안됨'**만 읽습니다.
- 회계연도 기준 **최초 비례연차 + 후속 정기 부여**: 최초 비례연차는 소정근로일 기준을 기본으로 하며 달력일·월수 방식도 선택할 수 있습니다. 이후에는 직전 회계연도 근태 판정과 **실제 입사일 기준 근속 가산연차**를 반영합니다.
- 연차 발생 건별 상세와 직원별 발생요약을 **한 번에 두 시트로 출력**합니다.
- 발생요건을 재판정하지 않고 `eligibility` Module을 호출하지 않습니다.
- 사용·이월·만료·수당·잔여연차는 계산하지 않습니다.

**연도별 계산:** `as_of_date` 한 개로 범위를 정합니다. 예: `2026-12-31` 입력 시 **2026-01-01 ~ 2026-12-31**에 발생한 건만 계산·합산합니다. 전년도 근태 판정은 당년 발생의 근거로 참조하되, 전년도 발생량을 더하지 않습니다. 연중 기준일이면 해당 해 1월 1일부터 그 기준일까지 계산합니다.

**회계연도 정기 발생:** 최초 회계연도 비례 부여 이후에는 회계연도 경계마다 직전 회계연도 '80% 충족' 플래그를 확인하고, 실제 입사일의 완료 근속연수를 기준으로 15~25일을 산정합니다. 직전 회계연도 '80% 미충족'이면 해당 기간의 월간 개근 플래그를 사용합니다. 첫해 11개월분과 겹치는 월별 권리는 중복 산정하지 않으며, 월간 기간이 첫해 권리와 겹쳐 정확히 판정할 수 없는 경우 '판정 안됨'으로 남깁니다. 근태 판정이 누락·미확정인 경우에도 숫자를 추정하지 않습니다. 최초 비례 부여는 해당기간의 연간 근태 플래그와 비례 집계가 있어야 합니다.

## 2. Excel 입력

기본 공유 입력 루트: `bhandara/data/input/`

| 파일 | 시트 | 필수 열(영문 snake_case) | 비고 |
|---|---|---|---|
| `common/employee.xlsx` | `재직자`, `퇴사자` | `employee_id`, `hire_date` | `termination_date`는 퇴사자 필수; `work_system`은 기존 자료 유지 |
| `paid-time-off/attendance-result.xlsx` | `근태결과` | `employee_id`, `period_start`, `period_end`, `check_type`, `attendance_flag` | 출퇴근 원본이 아닌 근태 판정 결과 |
| `paid-time-off/proration.xlsx` | `비례자료` | `employee_id`, `period_start`, `period_end`, `method`, `numerator`, `denominator` | 회계연도 최초 비례 계산할 때 필요; `base_days` 선택, 기본 15일 |

**호환성:** 기존 `pto-calculator`는 `active` 시트를 사용합니다. 새 시트를 준비하더라도 기존 기능의 이관·검증 전에는 `active` 시트를 삭제하지 마세요. 새 Entitlement 실행기는 `재직자`·`퇴사자` 두 시트를 읽습니다.

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
3. **정책정보:** 마지막 시트. 정책 ID, 산정 기준일, **당해 연도 시작일·종료일**, 입력 파일·SHA256, 비례 산정 방식, 최종 반올림 자릿수 등. 직원별 행에 반복 기록하지 않습니다.

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


## 6. Deduction Quantity — 승인된 휴가 사용시간 계산 (2026-11-18, 시범 구현)

> 이 항목은 위의 구형 차감량 설명보다 우선합니다. **독립 Excel 시범 실행**이며,
> 발생분별 차감 배정·연차 잔여·만료·이월·월별 Closing은 구현하지 않습니다.

- **입력 파일:** 명시된 경로 또는 `<input_root>/paid-time-off/approved-leave.xlsx`
- **입력 시트:** `승인휴가`
- **필수 헤더:** `request_id`, `employee_id`, `leave_date`, `leave_type`, `duration_hours`
- **값:** 사용일 `YYYY-MM-DD`(또는 Excel 날짜), 휴가 유형 `연차`/ `대휴`, 시간은 hour 단위(예: `1.5` = 1시간 30분).
- **승인·취소·반려 관리:** 외부 시스템에서 완료한 내역만 전달합니다. 여러 날짜에 걸친 하나의 신청은 같은 `request_id`를 서로 다른 `leave_date`에 반복 사용합니다. 같은 요청·같은 날짜는 외부에서 합쳐서 보내야 합니다.
- **계산:** `duration_hours / standard_daily_hours`; 기본 1일 8시간, 직접 호출 시 변경 가능. 전일·반차·반반차/시간차의 고정 코드 분류는 입력에 필요 없습니다. 직원별 근무정책 파일은 지금 읽지 않습니다.
- **정밀도:** 중간 반올림 없음. 유한소수는 정확한 표기, 무한소수는 표시할 때만 7자리 절사. 건별 절사값을 재합산하지 않습니다.
- **예외:** 필수값 누락, 동일 `request_id + leave_date` 중복, 지원하지 않는 휴가 유형, 잘못된 시간·날짜 등은 **해당 행을 `계산 제외`**하고 사유를 남깁니다. 중복 행은 전부 제외합니다. 정상 행은 이어서 계산하고 요약 상태를 `일부 제외`로 표시합니다. 필수 헤더가 빠진 경우도 행별 제외합니다. 파일·시트 자체가 없거나 헤더 중복처럼 구조를 해석할 수 없으면 실행 오류입니다.
- **독립 결과:** `<output_root>/<run_id>/deduction-quantity-result.xlsx`에 `차감요약`(직원별 계산된 차감일수·제외 건수), `차감상세`(요청 ID·사용일·휴가 유형·사용시간·차감일수·사유), 마지막 `정책정보` 시트를 작성합니다. 같은 `run_id` 덮어쓰기는 금지합니다.
- **주의:** 이 결과는 사용량 **환산**일 뿐, 연차 발생·잔여 현황이 아닙니다. 발생분별 차감 근거와 직원별 발생/사용/잔여를 함께 보는 별도의 사용내역 결과는 추후 `expiry-carryover`와 조합할 때 설계합니다. `closing`의 월별·기간별 마감 양식과도 구분합니다.

```python
from importlib import import_module
from pathlib import Path

runner = import_module("bhandara.paid-time-off.runner")
result = runner.run_deduction_quantity(
    policy_id="회사휴가-2026",
    run_id="example-deduction-2026",
    input_root=Path("/secure/private/input"),
    output_root=Path("/secure/private/output"),
    standard_daily_hours=8,
)
print(result["path"])
```

위 `/secure/private` 경로는 예시입니다. 실제 사용 시 존재하는 비공개 경로를 지정하고 개인정보를 Git에 커밋하지 마세요. 기존 `calculate_deduction_quantity(unit=...)`는 과거 순수 API 호환을 위해 유지하되, 신규 시간 기반 API는 `deduction-quantity/calculation.py`의 `calculate_hours_deduction` 및 `calculate_approved_rows`입니다. 전체 Tool CLI·Gearbox·Slack과는 아직 연결하지 않았습니다.

```bash
python3 -m unittest bhandara.tests.test_paid_time_off_deduction_excel -v
python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
```

## 7. 다음 Module: Expiry & Carryover — 설계 시작점 (미구현)

**확정된 처리 방향:** 외부 승인 시스템이 신청·승인·반려·취소 상태를 관리합니다. Bhandara는 실행할 때마다 현재 유효한 승인 사용내역을 입력받아 정확한 사용시간을 일수로 환산합니다. 이후 `expiry-carryover`는 발생 건별 유효기간을 확인하고 승인 요청의 **사용일에 실제로 유효한 발생분**에 차감량을 배정합니다. 이전 결과에 단순히 +/−를 누적하지 않고, 취소 후 갱신된 승인 목록으로 사용일 순서대로 재배정하는 방향을 합의했습니다.

- **차감 이력 자체**에 `request_id`(사용 요청)와 `grant_id`(발생 건)를 함께 남깁니다. 하나의 요청이 여러 발생분에서 차감되면 같은 요청 ID가 여러 행에 나옵니다. 별도의 중복 배정 장부는 만들지 않습니다.
- 발생분별 기본 배정 방향은 **사용일에 유효한 권리 중 먼저 만료되는 발생분부터**입니다. 회사 정책으로 변경할 수 있도록 구체화해야 합니다. 연차·대휴는 서로 다른 권리로 구분합니다.
- 사용이 확정된 신청뿐 아니라 승인된 미래 사용분도 사용 가능 잔여 계산에서 고려하는 방향입니다. `deduction-quantity`는 승인된 미래 건을 그대로 환산하며, **발생분별 예약·최종 사용·잔여 구분은 아직 구현하지 않았습니다**.
- `entitlement`는 기준일의 해당 연도에 발생한 연차만 계산합니다. 따라서 다음 단계에서는 **과거 연도 발생분과 외부에서 확정한 대휴 발생분을 별도로 입력받을 발생 원장**을 먼저 설계해야 합니다.
- 대휴 발생량은 외부에서 결정하며, 발생일로부터 1년 유효기간이라는 사용자 운영 가정은 후속 정책 협의에 포함합니다. **모든 유형에 동일한 법정 만료 기한을 일괄 적용하지 않습니다.**
- 독립 사용내역 결과(후보)는 `사용요약`: 직원별 `employee_id, 발생일수, 사용일수, 잔여일수`, `사용상세`: 요청 ID·발생 ID·사용일·휴가유형·차감일수·차감 후 잔여 등입니다. **정확한 시트/열 및 계산 기준은 미확정**이고, `closing`의 **월별·기간별·누적 사용량 집계 양식**과 별개입니다. PTO 전체 통합결과표도 여전히 보류합니다.

### 다음 대화에서 먼저 합의할 항목

1. **발생 원장 입력:** `grant_id`, `employee_id`, `leave_type`, `grant_date`, `grant_days`, 유효기간 시작·종료, 원천/정책 참조. 이는 *제안 필드*이지 확정 헤더가 아닙니다.
2. **과거 발생분과 중복 방지:** 당년 `entitlement` 결과, 과거 발생분, 외부 대휴 발생량을 어떤 책임 계층에서 하나로 모을지 결정합니다.
3. **차감 정책:** 사용일순, 먼저 만료되는 유효 발생분 우선, 동률·부족·기간 충돌·소수 차감량 처리, 미래 승인분의 반영 기준일을 확정합니다.
4. **출력·예외:** 요청-발생 연결 이력과 발생분별 잔여를 정의한 뒤 Excel 양식을 결정합니다. 추정이나 임의 승인 없이 최소 예외부터 구현합니다.

기존의 `eligibility`는 PTO에서 재실행하지 않습니다. 모든 Module은 독립적이며 Tool 간 호출은 Gearbox Workflow 책임입니다.

## 2026-11-18 최신 설계: Allocation과 Expiry/Carryover 분리

**기존 문서에서 Expiry가 발생분 차감까지 소유한다고 한 부분은 폐기합니다.** 현재는 순수 Python API 초기 구현이며 최종 Excel·Tool 호출 경계는 아직 아닙니다.

- paid-time-off/allocation.py: Tool 내부 계산 단계. 별도 Module도 아니고 물리 flow/ 폴더도 아닙니다. 입력된 발생 건과 승인된 사용 건을 ID로 연결합니다.
- paid-time-off/expiry-carryover/calculation.py: 독립 Module. 외부에서 유효기간과 마감일 현재 잔여가 확정된 발생 건에 대해 만료 또는 이월을 판정합니다. 배정/잔여 재계산/수당 지급 승인은 하지 않습니다.
- Closing-1.4-2025 ~ Closing-4.4-2025 ID에서 분기 종료일을 유도하므로 opening_date 추가 입력은 없습니다. API의 balance_as_of는 상위 결과의 기준일이 마감일과 같은지 검증하는 값이지 사용자에게 입력을 중복 요구하는 시트가 아닙니다.
- Allocation의 발생 건 입력 필드: grant_id, employee_id, leave_type, grant_date, available_days, valid_from, expires_on, source_ref. available_days는 원천에서 확정된 반영발생일수 또는 기존 Closing의 발생분별 기초잔여를 정규화한 내부 이름입니다. 유효기간은 필수이며 누락 시 추정하지 않습니다.
- Allocation의 차감 입력 필드: request_id, employee_id, leave_type, leave_date, deduction_days. Deduction Quantity에서 이미 일수 환산된 승인 내역만 인계합니다.
- 배정 순서는 사용일 → 만료일 → 발생일 → grant_id. 취소된 요청을 제외한 현재 유효 승인 목록으로 전체 재실행합니다. 연차와 대휴를 교차 차감하지 않습니다.
- 초과 사용은 신청별 발생분 미배정 행(grant_id 없음)과 직원·유형별 **음수 잔여**로 표시합니다. 발생 건 자체를 음수로 변경하지 않습니다. 새 발생분으로 **자동 상계하지 않습니다**. 상계는 외부 확정 지시가 있어야 하지만 그 지시의 실제 입력 계약은 추후 연결합니다.
- 미래 예약은 실행 기준일의 사용량과 별도 표시합니다. 마감일 이전의 발생분별 확정 잔여만 만료/이월 계산에 사용하며 미래의 미확정 발생은 예측하지 않습니다.
- 무한소수 7자리 절사 문자열로는 정확한 분수를 복구할 수 없습니다. 향후 Excel-to-Flow 연결 시 분수의 정확한 인계 규격을 추가해야 합니다.
- Expiry의 만료된 연차는 미사용수당 **검토 대상**만 표시하며 현금청구권·면책·지급을 자동 승인하지 않습니다.
- 오류가 특정 직원/휴가유형의 수량에 영향을 주면 그 그룹의 배정을 생략합니다. 정상적인 다른 그룹의 계산은 유지합니다.
- 과거 Closing/외부 대휴/Entitlement 원본 Excel의 실제 결합, grant_id 생성, 내부 Flow의 선택적 호출, 최초 Closing 이전 기초자료 인계, 외부 상계 명령, 결과 Excel과 SHA 기록은 **아직 구현하지 않았습니다**.
- 단독 unittest: python3 -m unittest bhandara.tests.test_paid_time_off_allocation_expiry -v


## 2026-11-18 실제 Excel 연결 (PR #42)

> 이 절은 앞부분의 미구현 상태 설명보다 **우선하는 최신 계약**입니다. 기존 PTO/Payroll/Worktime 운영은 변경하지 않습니다.

### 목적과 모듈 소유권

- Entitlement 독립 Excel: 원본 \`계산결과\`를 그대로 보존하면서 **\`grant_id\`(안정적 발생 사건 ID)** 및 \`반영발생일수\`를 \`발생상세\`의 기존 열 뒤에 추가합니다. 발생량 합산 후 **마지막 1회 반올림**을 유지하고, 정해진 총량을 각 발생 행에 고정 단위로 배분합니다. 재실행·행 순서·발생 수량 정정에도 동일 사건 ID가 유지됩니다. 수량 배분은 단일 원장의 총량 배분이지 각 사건 독립 반올림이 아닙니다.
- Deduction Quantity 독립 Excel: \`차감상세\`의 기존 표시/열 순서를 유지하고 \`_exact_numerator\`/\`_exact_denominator\` 두 열을 **숨김 열**로 추가합니다. 이는 무한소수 7자리 절사 문자열에서 정확한 분수를 복원할 수 없다는 문제를 해결합니다.
- Tool 내부 \`source_join.py\`: 발생 종류별 원본 Excel을 ID 관계로 결합합니다. 독립 업무 Module이 아닙니다.
- Tool 내부 \`runner_usage.py\`: 다른 Module을 자동 실행하지 않고 **이미 생성된 Excel 결과**와 확정 근거만 읽습니다. \`allocation.py\`와 \`expiry-carryover\` 순수 API를 연결해 사용내역 Excel을 생성합니다.
- Expiry/Carryover: 만료·이월만 판정합니다. Closing과 수당 지급·권리 확정은 하지 않습니다.

### 입력 파일 계약

\`run_usage_ledger(as_of_date, policy_id, run_id, entitlement_file, deduction_file, reference_file, carry_in_file=None, closing_id=None, output_root=...)\`

각 파일은 명시적으로 지정합니다. 사용자 데이터 경로는 Git 밖의 비공개 위치여야 합니다. 자동 탐색·재계산·숨은 상태를 사용하지 않습니다.

1. \`entitlement-result.xlsx\`의 \`발생상세\`와 \`발생요약\`: grant_id/반영발생일수 필수. 실행 기준일과 발생 산정 기준일이 일치해야 합니다. 모든 확정 발생 행의 반영일수 합계가 직원 요약과 일치해야 합니다.
2. \`deduction-quantity-result.xlsx\`의 \`차감상세\`: 승인 요청 ID, 사용일, 휴가유형, **정확한 분자·분모** 필수. 기존 7자리 표기와 일치 여부 검사. 기존 형식이어서 분수 열이 없다면 **새 Deduction 버전으로 다시 산출**합니다.
3. \`grant-references.xlsx\`의 \`발생근거\`: \`grant_id, employee_id, grant_date, valid_from, expires_on, source_ref\`. Entitlement 발생 건은 \`grant_id, valid_from, expires_on\`만 채워도 됩니다. 나머지 값은 Entitlement 결과에서 참조합니다. 대휴는 이 시트에서 해당 발생 건의 직원·발생일·유효기간·원본 참조를 확정합니다.
4. 같은 파일의 \`대휴발생\`(선택): **\`source_ref, 반영발생일수\` 두 열만** 필요합니다. 다른 필드는 \`발생근거\`에서 source_ref로 연결합니다. 대휴 수량은 외부 확정값을 받아 재계산하지 않습니다.
5. \`carry-in.xlsx\`(선택): \`정책정보\` 시트에 \`참조 ID\`(예: \`Closing-4.4-2025\` 또는 최초 \`Opening-4.4-2025\`)와 \`확정여부=확정\`. \`인계자료\` 시트에 \`grant_id, employee_id, leave_type, grant_date, available_days, valid_from, expires_on, source_ref\`. **이전 Closing의 모든 발생 ID(잔여 0 포함)**가 있어야 하고, \`available_days\`는 최초 발생량이 아닌 확정 기초잔여입니다. 별도 \`opening_date\` 입력은 없습니다.
6. \`carry-in.xlsx\`의 \`미상계부족\`(선택): \`request_id, employee_id, leave_type, leave_date, shortage_days\`(양수 부족 수량). 이미 발생한 초과사용을 계속 음수 잔여로 보존하며 **자동 상계 금지**.

Closing 참조 ID로 이전 마감일을 유도하고, 그 날짜 이전 또는 당일에 사용한 승인 요청은 **기초잔여에 포함된 것으로 보아 다시 차감하지 않습니다**. 과거 확정 마감의 승인 취소·수정이 생기면 **먼저 해당 Closing 기초원장을 외부에서 정정**해야 합니다. 현재 입력에서 조용히 역사적 사용 내역을 변경하지 않습니다.

### 결과 Excel

\`usage-ledger-result.xlsx\`:
- \`사용요약\`: \`employee_id, 발생일수, 사용일수, 잔여일수\` — 직원별 1행. 직원별 연차+대휴 집계(휴가유형별 분할 없음). **음수 잔여는 Excel 실제 숫자**로 출력합니다. Closing 경계일 실행에서는 **그날 만료된 미사용 권리를 제외한** 마감 후 잔여입니다.
- \`사용상세\`: \`employee_id, leave_type, grant_id, grant_date, 반영발생일수, valid_from, expires_on, source_ref, request_id, leave_date, 차감일수, 처리구분, 사유\`. **신청-발생의 연결된 내역 자체**이며 별도의 배정 원장을 만들지 않습니다. 같은 신청에서 여러 발생 건을 쓴 경우 요청 ID 반복, 발생 ID만 다릅니다. 미래 예약/부족/인계부족도 상태로 구분합니다.
- \`만료이월\`: \`closing_id\`를 지정하고 \`as_of_date\`가 해당 Closing 마감일과 같을 때만 추가. **발생 건마다 한 행**으로 만료·이월 수량과 미사용수당 검토 여부를 표시합니다. 이 수량을 여러 사용상세 행에 반복해 이중합산하는 구조가 아닙니다.
- \`검토사항\`: 입력/배정 오류가 있을 때만 생성. 유효기간·ID 관계 오류를 임의로 보정하지 않습니다.
- \`정책정보\`: 항상 마지막. 파일 SHA256, 참조 Closing, 실행일·정책, 검토 상태, 무상계·미지급확정 원칙.

이 결과는 **사용내역 및 발생 건별 만료·이월 판정**이지 Closing 보고서를 대체하지 않습니다. Closing의 월별/분기별 마감보고는 별도 Module 책임입니다.

### 안전·운영 범위

정확한 분수는 계산에서 유지하고 화면용 소수만 기존 규칙으로 표시합니다. 유효기간 없는 건은 차감 배정에서 제외하고 검토 표시합니다. 연차·대휴 교차 차감, 발생량 예측, 원본 승인 판단, 수당 확정은 없습니다. 최초 인계는 외부 확정 자료를 사용합니다.

**아직 미구현**: 실제 Closing 및 Use-Promotion, 외부의 **명시적 상계 지시를 받아 확정 처리**하는 API, 공개 CLI/module.json/user_settings, Gearbox/Slack 운영 연동. 이 경로는 서버 배포 상태가 아니라 Python 독립 호출용입니다.

합성 \`unittest\`: \`python3 -m unittest bhandara.tests.test_paid_time_off_usage_excel -v\`

