# 반다라 공통 입력 샘플 (가상 직원 80명)

> **새로 시작한다면 [통합 v2 샘플](../integrated/README.md)을 사용하세요.**
> 이 폴더는 구형 단일 시트 계약과 별도 용역파일을 이용하는
> **회귀 검증용 legacy 예제**로 보존합니다. 새 통합 예제는
> `Contracts + Components`와 Worktime 외부 인력 연결을 사용합니다.

이 디렉터리의 **실제 Excel 파일**은 [generate.py](generate.py)로 재현되며,
운영 데이터가 아닙니다. 80명의 직원이 공통 ID 매핑으로 세 계산기에 연결됩니다.

## 실행하기

프로젝트 루트에서:

1. `bhandara/examples/sample/input/` **폴더 안의 파일과 디렉터리**를
   `bhandara/data/input/`에 그대로 복사합니다. 기본 실행은 해당 폴더에서
   파일을 찾으므로 JSON 파일 경로를 직접 편집할 필요가 없습니다.
2. 아래 명령을 실행합니다. 결과는 기본적으로 `bhandara/data/output/` 아래에 생깁니다.

```bash
python run.py bhandara worktime-calculator --period 2026-06
python run.py bhandara pto-calculator --period 2026-07
python run.py bhandara payroll-calculator --period 2026-07
```

Worktime과 Payroll 결과는 첫 실행 시 `bhandara/data/output/<모듈명>/`에 저장되며,
같은 이름의 결과 폴더가 이미 있으면 `<모듈명>-001/`, `-002/`로 새 폴더를 만듭니다.
따라서 이전 계산 결과를 덮어쓰지 않습니다.

Worktime은 출퇴근 인증이나 근무시간을 자동 승인하지 않습니다.
Payroll의 기본 샘플 `payroll/worktime-result.json`은 **Worktime 샘플의
2026-06 실행 결과(미마감)**를 보관한 것입니다.
Worktime을 다시 실행하고 그 결과를 급여 계산에 사용하려면
`--worktime-result /실제경로/worktime-result.json`을 지정합니다.
계산 결과가 검토 필요 상태라면 0이 아닌 종료 코드가 나오는 게 정상일 수 있습니다.

## 고정 경로

| 모듈 | 실제 입력 파일명(샘플 `input/` 기준) |
|---|---|
| 공통 | `common/employee.xlsx`, `common/id-map.xlsx` (`ID_MAP` 시트) |
| PTO | `pto/work-schedule.xlsx`, `pto/work-schedule-assignment.xlsx`, `pto/work-records/2026/2026-07-schedule.xlsx`, `pto/work-records/2026/2026-07-attendance.xlsx`, `pto/employee-events.xlsx` |
| Worktime | `worktime/work-schedule.xlsx`, `worktime/attendance.xlsx` |
| Payroll | `payroll/pay-contract.xlsx`, `payroll/pay-contract-components.xlsx`, `payroll/payroll-input.xlsx`, `payroll/company-policy.json`, `payroll/worktime-result.json` 및 선택 `payroll/service-contracts.xlsx` |

## 공통 직원·식별자 입력과 테스트 시나리오의 분리

실제로 계산기에 넣는 공통 Excel은 필요한 정보만 포함합니다.

| 파일 | 열 | 역할 |
|---|---|---|
| `input/common/employee.xlsx` | `employee_id`, `hire_date`, `termination_date`, `work_system` | 직원의 고용·근로제 사실 |
| `input/common/id-map.xlsx` (`ID_MAP` 시트) | `employee_id`, `security_id`, `worker_id`, `payroll_id` | 시스템별 직원 식별자 대응 |

`work_system`은 직원명부에서만 관리합니다. 식별자 대응표에 중복 기록하지 않습니다.
`case_id`는 **두 Excel 모두에서 제거**했습니다. 계산에 쓰는 입력값이 아니라
가상 직원에게 부여한 테스트 시나리오 설명이기 때문입니다.

별도 `test-cases.json`은 이 샘플의 **`input/` 바깥**에 있으며 테스트에서만
시나리오별 직원 ID를 확인합니다. 예를 들어
`"LOW_ATTENDANCE": ["E002"]`이며, 일반·근로제 검토 사례는
`NORMAL_OR_WORKSYSTEM_REVIEW`로 묶습니다.
이 JSON은 계산기의 입력·설정에 넣거나 수정할 필요가 없습니다.
Excel의 실제 근태·스케줄을 수정해도 테스트 시나리오 분류가 자동으로 바뀌지는 않습니다.

## 계약 유형이 섞인 급여 샘플

`payroll/pay-contract.xlsx`에는 가상 직원 80명의 원 계약금액이 있습니다:
**연봉 20명, 월급 20명, 시급 20명, 일급 20명**. 연봉은 12회 균등분할이라는 가정이며 결과에 이를 검토 표시로 남깁니다.
이는 이미 계산된 월 기본급이 아니라 **연/월/시간/일 단위 계약금액**입니다.

`payroll/pay-contract-components.xlsx`에는 연봉·월급 계약에 **포함된 월 고정수당**을 따로 기록했습니다.
급여 계산기는 이 금액을 계약 총액에서 빼서 기본급을 도출하고, 수당을 별도 항목으로 전달합니다.

`payroll/service-work-records.xlsx`에는 용역제공 16행이 있어 8건에 대한 **시급×시간 / 일급×일수 추정액**을 별도 확인할 수 있습니다. 단, 실제 지급 및 원천징수 승인 없이 검토 결과로만 표시합니다.

`payroll/service-contracts.xlsx`의 가상 프리랜서 8건은 직원 80명과 **별개**이며
직원 급여대장에 합산되지 않습니다. 이 파일은 없으면 생략할 수 있습니다.
계약 구성 수당이 없는 회사도 `pay-contract-components.xlsx`의 헤더는 남겨 두어야 합니다.

급여 결과의 `contract-basis-review.xlsx`에는 계약 단가·시간/일수·기본급·계산 규칙이,
`contract-derived-compensation.xlsx`에는 기존 Payroll 엔진에 실제로 넘긴 월 기준 보상액이 남습니다.
**시급·일급의 가산수당과 유급주휴는 아직 자동 계산하지 않습니다.**
검토 결과가 나왔다고 실지급액이 확정된 것은 아닙니다.
[급여 Excel 사용 안내](../../payroll-calculator/RUNBOOK.md)를 참고하세요.

`common/id-map.xlsx`는 사내 직원번호, 출입기 식별자, 계산용
`worker_id`, 급여 시스템별 ID를 눈에 보이게 연결합니다.
**다른 회사의 식별 체계는 매핑 열 값을 바꿔야 하며 실제 사번을 Git에 올리면 안 됩니다.**

추가로 다음 가상 출입 인증자료가 있습니다.

- `worktime/security-raw-caps-synthetic.xlsx`
- `worktime/security-raw-s1-synthetic.xlsx`
- `worktime/security-raw-kt-synthetic.xlsx`

**공식 업체 내보내기 양식이라고 확인된 파일이 아닙니다.**
단말기 인증·중복 태그·메뉴 미선택 이벤트를 보존한 **재현 예제**입니다.
이들 원본은 Worktime에서 자동으로 출근·퇴근으로 확정하지 않습니다.
확인된 근태만 `worktime/attendance.xlsx`에 들어갑니다.

## 안전 기준

- 샘플에는 실제 직원·급여·승인자료가 없습니다.
- 직원 수는 80명이며, 다양한 근로제·중도퇴사·누락/중복 인증 사례가 섞여 있습니다.
- 계산기는 `approved`, `finalizable`, `ledger_committed` 상태를
  실제 결재 완료로 바꾸지 않습니다.
- `bhandara/data/input`와 `bhandara/data/output`는 Git 제외 폴더입니다.
- 필수 파일이나 ID 매핑이 없다면 다른 위치의 비슷한 파일을 임의로 찾아서 쓰지 않습니다.
