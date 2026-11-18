# Attendance Verification — 출입 인증 근거와 근태장부 대조 (0.1)

> **독립 순수 계산 구현.** 벤더 원본 연결·Excel 입출력·공개 CLI·Gearbox/Slack 배포는 아직 구현하지 않았습니다. 검토 결과는 근로시간·지각·휴게·급여·승인 여부를 자동 확정하지 않습니다.

## 역할과 경계

근태장부에 기록된 **출근·퇴근 시각**을 출입기에서 **명시적으로 성공 인증된 출근·퇴근 이벤트**와 비교합니다.

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

서로 다른 CAPS·KT텔레캅 원본 컬럼/코드는 **업체별 어댑터에서 명시적으로 매핑한 후** 전달해야 합니다. 알 수 없는 원본 코드의 뜻이나 인증 방법을 자동 추측하지 않습니다. 이 모듈은 제조사 파일·API에 직접 접근하지 않습니다.

시간은 로컬 기준 `HH:MM` 또는 `YYYY-MM-DDTHH:MM`을 허용하고, 초/시간대 정보가 섞인 값은 검토 대상으로 남깁니다. 익일 퇴근 시각은 **전체 날짜를 포함**해야 합니다. `work_date`는 출근 기준 근무일을 뜻하므로 익일 퇴근 인증도 해당 근무일에 연결하여 전달해야 합니다.

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

## 이번 PR에서 하지 않는 일

1. 원본 인증 파일의 수집·열 이름 추정·제조사별 원본 코드 매핑. 실제 제공된 CAPS/KT텔레캅 샘플의 열과 코드 의미를 확인한 뒤 **별도의 독립 어댑터**를 설계합니다.
2. Schedule Module 또는 구형 `worktime-calculator`와 자동 연결하지 않습니다.
3. 휴게·법정 근로시간·지각·조퇴·연장·야간·휴일근무 판정은 다른 Module에서 처리합니다.
4. Closing, Gearbox, Slack, Tool 공개 CLI 및 Payroll 연동은 보류합니다.

## 독립 테스트

```bash
python3 -m unittest bhandara.tests.test_worktime_attendance_verification -v
```

실제 직원 자료가 아닌 합성자료로 검증합니다. 서버 적용은 PR 브랜치 직접 확인 및 기존 Worktime·Gearbox 회귀 검증 후 수행합니다.
