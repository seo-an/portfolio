# 반다라 공통 입력 샘플 (가상 직원 80명)

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
| Payroll | `payroll/compensation.xlsx`, `payroll/payroll-input.xlsx`, `payroll/company-policy.json`, `payroll/worktime-result.json` |

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
