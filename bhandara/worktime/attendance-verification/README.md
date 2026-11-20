# Attendance Verification — 출입 인증·근태장부와 스케줄 시각 차이 대조 (0.2)

> **독립 계산 및 표준 Excel 인계 구현.** 업체별 원본 Excel 해석과 공통 Excel 변환은 `../vendor_adapters/`와 `../access_source.py`가 담당합니다. 이 Module에 직접 연결하는 Tool 공개 CLI·Gearbox/Slack 운영 배포는 아직 구현하지 않았습니다. 근로시간·지각·휴게·급여·승인을 자동 확정하지 않습니다.

## 역할과 경계

근태장부에 기록된 **출근·퇴근 시각**을 출입기에서 **명시적으로 성공 인증된 출근·퇴근 이벤트**와 비교합니다. 선택적으로 스케줄과 업체 공통 출입 후보를 함께 받으면 **기록된 시각−예정 시각**의 부호 있는 차이를 계산합니다. 근무 유형·승인 여부를 자동 분류하지는 않습니다.

- `mode=CLOCK_IN/CLOCK_OUT`: 출근·퇴근 인증 버튼의 의미를 가진 기록만 직접 대조합니다. 물리적 출입 방향(`direction=IN/OUT/UNKNOWN`)을 출근/퇴근으로 변환하지 않습니다.
- `mode=ACCESS`: 일반 출입 인증입니다. 명시적 출근 인증을 대신하지 않습니다. 첫 인증 시각은 `confirmed=false` 후보로만 보존합니다.
- `mode=OUTING/RETURN`: 외출·복귀를 나타내며 출근/퇴근 또는 법적 휴게시간으로 바꾸지 않습니다.
- `mode=DISARM`: 경비 해제입니다. 출근/퇴근 인증으로 사용하지 않습니다.
- `auth_status=FAILED/UNKNOWN`: 성공 인증으로 취급하지 않습니다. **누락된 인증 상태도 UNKNOWN**으로 처리합니다.
- `auth_method=FINGERPRINT`가 기본 허용 기준입니다. 방법이 누락되거나 불명확하면 지문 인증으로 추정하지 않습니다. 다른 수단을 검토해야 할 경우 호출자가 `accepted_auth_methods`로 명시적으로 허용하고 해당 방법을 결과에 보존해야 합니다.
- 인증 시각 일치는 **장부의 시각과 단말기 이벤트의 일치**만 의미합니다. 실제 근로 수행·휴게·지각·임금 산정·근태 승인 확정과는 별개입니다.

## 순수 계산 함수

```python
from importlib import import_module
verification = import_module("bhandara.worktime.attendance-verification")
result = verification.verify_attendance(
    attendance_rows, access_events,
    period_from="2026-11-01", period_to="2026-11-30",
)
```

### 근태장부 입력

`employee_id`, `work_date`, `clock_in`, `clock_out`이 기본입니다. `worker_id`는 다른 원본과 일치하는지 교차 확인합니다. `source_ref`, `_row_number`는 선택적 출처 추적 필드입니다.

### 정규화 출입 이벤트 입력

`employee_id`, `work_date`, `event_id`, `event_time`, `mode`, `direction`, `auth_status`, `auth_method`를 받습니다. `worker_id`, `device_id`, `source_ref`, `_row_number`는 신원 대조·출처 추적을 위해 사용합니다.

서로 다른 CAPS·세콤·KT텔레캅 원본 컬럼/코드는 **업체별 어댑터에서 명시적으로 매핑한 후** 전달해야 합니다. 알 수 없는 원본 코드의 뜻이나 인증 방법을 자동 추측하지 않습니다. 이 모듈은 제조사 파일·API에 직접 접근하지 않습니다.

시간은 로컬 기준 `HH:MM` 또는 `YYYY-MM-DDTHH:MM`을 허용하고, 초/시간대 정보가 섞인 값은 검토 대상으로 남깁니다. 익일 퇴근 시각은 **전체 날짜를 포함**해야 합니다. `work_date`는 출근 기준 근무일을 뜻하므로 익일 퇴근 인증도 해당 근무일에 연결하여 전달해야 합니다.

## 부호 있는 시각 차이 (선택 입력)

Schedule Module은 **근무 예정일과 장부 기록의 존재 여부**만 판단합니다. 출근·퇴근 시간의 차이는 이 Module의 `time_deviations`가 담당합니다.

```python
from importlib import import_module

verification = import_module("bhandara.worktime.attendance-verification")
report = verification.verify_attendance(
    attendance_rows, access_events,
    period_from="2026-11-16", period_to="2026-11-16",
    schedule_rows=schedule_rows,            # 선택: 기대 출퇴근 시각
    candidate_rows=attendance_candidates,   # 선택: 출입기 미확정 후보
)
```

`schedule_rows`는 `employee_id`, `work_date`, `scheduled_start`, `scheduled_end`, 선택 `worker_id`를 받습니다. `candidate_rows`는 업체 공통 `access-events.xlsx` v0.2의 `Attendance Candidates`와 같은 규격이며 `confirmed=false`를 반드시 유지합니다.

근태장부의 선택 사유 필드는 `clock_in_reason`과 `clock_out_reason`입니다. 값이 없으면 `null`이고, 외부에서 제공된 설명만 보존합니다. 시차출퇴근·조기출근·야근·승인된 연장근무는 **차이의 부호만으로 판정하지 않습니다**.

### 시각별 세 개의 독립 비교

| 필드 | 기준 | 의미 |
|---|---|---|
| `ledger_vs_expected` | 장부 시각 − 스케줄 시각 | 사용자가 신고한 출퇴근 시각이 예정과 얼마나 다른지 |
| `device_vs_expected` | 출입기 시각 − 스케줄 시각 | 출입기 인증/미확정 후보가 예정과 얼마나 다른지 |
| `device_vs_ledger` | 출입기 시각 − 장부 시각 | 서로 다른 두 기록이 얼마나 다른지 |

각 항목은 `delta_minutes`(부호 포함)와 `delta_seconds`(원본 초 단위 정확성 유지)를 제공합니다. 예를 들어 **09:00 대비 08:40은 `-20`**, **18:00 대비 18:16은 `+16`**입니다. 두 시각 차이를 더해 실근로시간으로 간주하지 않습니다.

- `device_origin=AUTHENTICATED_PUNCH`는 설정된 인증방법에 부합하는 명시적 출퇴근 인증입니다. `device_origin=UNCONFIRMED_ACCESS_CANDIDATE`는 보안업체 첫/마지막 출입 후보이며 **근로 시작/종료 확정값이 아닙니다.**
- `device_confirmed_as_work=false`는 항상 유지합니다. 두 기록이 일치해도 실근로·임금·근태 승인으로 승격되지 않습니다.
- 기준 시각이 없거나 출처에서 확인되지 않으면 해당 차이는 `null`입니다. 자정 경계에서 날짜를 알 수 없는 12시간 이상 차이는 부호를 추정하지 않고 `CLOCK_DATE_AMBIGUOUS`로 검토합니다.
- `time_deviations.status`는 `MATCH / DIFFERENT / NOT_COMPARABLE`이며 **스케줄 대비 시각 비교**의 요약입니다. 기존 행 `status=RECORD_MATCH/RECORD_DIFFERENT`는 **장부↔명시적 인증 대조**를 뜻하므로 별개입니다. 스케줄 대비 차이가 하나라도 있으면 전체 실행 상태는 `REVIEW_REQUIRED`로 표시하되 그 사유가 법 위반이라는 뜻은 아닙니다.
- 업체 공통 `verify_attendance_xlsx(..., schedule_rows=schedule_rows)`는 `Attendance Candidates`를 자동으로 전달합니다. `Source Review`의 미매핑·원본 오류는 기존처럼 결과 전체를 검토로 남깁니다.

## 상태 계약

| 직원·근무일별 상태 | 의미 |
|---|---|
| `RECORD_MATCH` | 장부의 출퇴근 시각과 명시적 성공 인증 기록이 모두 일치 |
| `RECORD_DIFFERENT` | 장부와 인증 시각이 다름 (지각·연장근무 확정 아님) |
| `MISSING_EVIDENCE` | 장부는 있으나 충분한 명시적 출퇴근 인증 증빙이 없음 |
| `ACCESS_ONLY` | 장부는 있으나 출입 인증만 존재하고 명시적 출퇴근 인증이 없음 |
| `DEVICE_ONLY` | 해당 근무일에 장부 없이 출입기 기록만 존재 |
| `REVIEW_REQUIRED` | 출처 신원 충돌·중복·불완전/실패한 인증·시간 형식 오류 등 |

전체 실행은 대조 대상 모두 `RECORD_MATCH`이고 원본 오류가 없을 때만 `PASS`를 반환합니다. 나머지는 `REVIEW_REQUIRED`입니다. 두 입력에 행이 전혀 없을 때도 PASS를 반환하지 않습니다.

출력 `rows[]`는 `reported`, `device_punches`, `different_fields`, `first_access_candidate`, `review_codes`, `ledger_sources`, `access_evidence`를 포함합니다. `first_access_candidate.confirmed`는 항상 `false`입니다. 두 자료의 중복/불일치가 있어도 임의로 한 행을 선택해 승인하지 않습니다.

## 연동 상태와 보류 범위

1. **구현:** CAPS·세콤·KT텔레캅의 제공 예제에서 관찰된 헤더를 사용하는 독립 어댑터와 업체 공통 Excel v0.2 Writer/Reader가 있습니다. 새 제조사 버전·미정의 코드 해석은 별도 검증 대상입니다. 자동 열 이름 추정은 하지 않습니다.
2. **구현:** `verify_attendance_xlsx()`를 통해 표준 Excel의 `Attendance Candidates`와 선택적 스케줄을 전달해 시각 차이를 계산할 수 있습니다. 이것은 공개 CLI나 Gearbox 자동 Workflow 연결을 의미하지 않습니다.
3. **보류:** 휴게·법정 근로시간 판단은 Worktime Compliance에 맡깁니다. 지각·조퇴·연장·야간·휴일근무의 확정·승인·급여 산정은 하지 않습니다.
4. **운영 단계:** Portfolio Workflow는 구현됐지만, Gearbox/Hermes·Slack 실제 호출과 권한·보관 검증은 별도입니다.

정규화 원본에서 인증 방식이나 인증 성공 여부를 확정할 수 없으면 **실근무 또는 승인된 출퇴근으로 승격하지 않아야 합니다**.

## 독립 테스트

```bash
python3 -m unittest bhandara.tests.test_worktime_attendance_verification -v
```

추가 회귀 테스트: `python3 -m unittest bhandara.tests.test_worktime_attendance_deviations -v`. 실제 직원 자료가 아닌 합성자료로 검증합니다. 서버 적용은 PR 브랜치 직접 확인 및 기존 Worktime·Gearbox 회귀 검증 후 수행합니다.
