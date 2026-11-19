# Payroll P1-5b-1 — 휴가·결근과 근태자료 대조 및 기본급 차감 후보

> **범위:** 별도 확인된 휴가/결근 정산기록과 신규 Worktime 일별 사실을 대조한다. **기본급에서 실제 얼마를 차감해야 하는지 자동 계산하지 않는다.** 승인된 외부 원장이 이미 계산한 **차감액(원)**만 검토용 기본급 후보에 반영한다. 실제 법적 정산 적합성·승인자 권한·지급/공제 확정은 미구현.

## 1. 기존 계약 유지

- 신규 Payroll 입력은 기존 **7개 개별 단일 시트 Excel** 그대로. 추가 8번째 Excel은 없다.
- Worktime도 기존 `worktime-result.xlsx` / `WORKTIME` **10열** 그대로. 별도 휴가 상세 시간열을 만들어 넣지 않는다.
- 최종 Output은 기존 `payroll-result.xlsx` / `PAYROLL` **한 시트**. 별도 정산용 Excel은 생성하지 않는다.
- `attendance_plan` 객체는 정식 JSON Tool CLI 연결 전에 **외부에서 검증된 자료를 직접 함수에 전달**한다. 추후 CLI/운영 입력 계약에서 신뢰·권한·보관 근거를 확정해야 한다.

## 2. 입력 정보

`settlement_plan`은 [P1-5a 기간분할 계약](SEGMENTED-SETTLEMENT.md)의 재직증빙·계약 기간 배정 자료다. 이 스냅샷의 `snapshot_ref`와 휴가·결근 정산 원장의 `settlement_snapshot_ref`가 같아야 한다.

`attendance_plan`의 합성 예시:

```json
{
  "schema_version": "0.1",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "snapshot_ref": "SYNTHETIC-ATTENDANCE-2026-11",
  "settlement_snapshot_ref": "SYNTHETIC-EMPLOYMENT-SNAPSHOT",
  "worktime_sha256": "<실제 Worktime XLSX의 소문자 SHA-256 64자리>",
  "absence_codes": ["ABSENCE"],
  "events": [
    {
      "event_id": "EV001",
      "employee_id": "0001",
      "work_date": "2026-11-02",
      "contract_id": "C-OLD",
      "event_kind": "LEAVE",
      "worktime_code": "ANNUAL_HALF",
      "leave_request_id": "LV001",
      "start_at": "2026-11-02T13:00",
      "end_at": "2026-11-02T17:00",
      "approved_minutes": 240,
      "treatment": "PAID_LEAVE",
      "base_reduction_won": 0,
      "base_amount_not_pre_adjusted": true,
      "approval_status": "APPROVED",
      "approval_ref": "SYNTHETIC-APPROVAL-001",
      "policy_ref": "SYNTHETIC-LEAVE-POLICY",
      "evidence_ref": "SYNTHETIC-LEAVE-REGISTER-001"
    },
    {
      "event_id": "EV002",
      "employee_id": "0001",
      "work_date": "2026-11-03",
      "contract_id": "C-OLD",
      "event_kind": "ATTENDANCE",
      "worktime_code": "ABSENCE",
      "leave_request_id": null,
      "start_at": "2026-11-03T13:00",
      "end_at": "2026-11-03T17:00",
      "approved_minutes": 240,
      "treatment": "UNPAID_ABSENCE",
      "base_reduction_won": 60000,
      "base_amount_not_pre_adjusted": true,
      "approval_status": "APPROVED",
      "approval_ref": "SYNTHETIC-APPROVAL-002",
      "policy_ref": "SYNTHETIC-ABSENCE-POLICY",
      "evidence_ref": "SYNTHETIC-ATTENDANCE-REGISTER-002"
    }
  ]
}
```

`worktime_sha256`는 제출한 Worktime Excel 내용의 해시다. 아래 함수 예시처럼 파일에서 **매번 직접 산출**해야 한다. 위의 `<...>`는 설명용 자리표시자이며 실제 실행값이 아니다.

### 분류 및 원 단위 처리

| 구분 | 필요 근거 | 기본급 반영 |
|---|---|---|
| `PAID_LEAVE` | Worktime `leave_type`와 `leave_request_id` 모두 일치, 승인시간·시각·정책 | **0원 차감**. 해당 휴가의 1배분 임금이 기존 기본급에 포함됐다는 외부 전제 필요 |
| `UNPAID_LEAVE` | 동일 휴가 참조, 승인된 기간·독립 정산금액 | **외부에서 확정한 양의 차감금액만** 후보에 반영 |
| `UNPAID_ABSENCE` | `attendance_type`가 `absence_codes` 중 하나이며 일별 실제 근로분 확인, 승인된 기간·차감금액 | **외부에서 확정한 양의 차감금액만** 후보에 반영 |

모든 금전 차감의 `base_amount_not_pre_adjusted=true`는 해당 금액이 P1-5a의 월·주 **전체 급여 기준에서 아직 차감되지 않았음을 외부가 확인**했다는 선언이다. `approval_ref`·`policy_ref`·`evidence_ref`는 **입력 문자열만 확인**하며 실제 서명이나 승인권한을 입증하지 않는다.

`approved_minutes`는 시작/종료 시각의 차이와 같고 Worktime `scheduled_min`보다 길 수 없다. `actual_min`·출퇴근 시각차를 사용하여 무급 분수나 차감액을 역산하지 않는다. 결근 사건은 Worktime `actual_min`을 확인할 수 있어야 하고, 하루 소정시간이 미확정이면 정산을 중단한다.

## 3. 의도적으로 차단하는 경우

- 임의로 추가한 휴가 사건이 Worktime 신청 ID/유형 또는 직원/일자/계약 배정과 불일치하는 경우
- Worktime에 휴가 신청 정보가 있는데 이번 외부 정산 원장의 사건 목록에 **대응 기록이 없는 경우**
- 회사에서 `absence_codes`로 선언한 결근 사실에 승인·정산 사건이 **없는 경우**
- 같은 직원·날짜에 **복수 사건**을 넣거나 휴가/결근 구간이 서로 겹치는 경우. Worktime 10열에는 휴가 신청 ID가 하루 하나뿐이므로 복수 신청/구간은 향후 별도 증빙 계약으로 확장한다
- 월중 계약 교체일을 가로지르는 사건(두 계약 중 어디에 귀속할지 명확하지 않음), 재직·계약 배정기간 밖의 사건
- 승인시간과 실제 사건구간 길이가 불일치하거나, 결근 사건인데 실제 근로분이 `null`인 경우
- `PAID_LEAVE`인데 차감액이 양수, `UNPAID_LEAVE` 또는 `UNPAID_ABSENCE`인데 양의 차감액이 없는 경우
- 직원별 누적 기본급 차감액이 원래 일할 기본급 후보보다 많아 음수가 되는 경우
- 제출한 Worktime 파일의 SHA-256이 계획서와 다르거나 읽는 도중 내용이 변경된 경우

Worktime의 `attendance_type`이 명시된 `absence_codes`에 속하지 않는 경우는 **차감하지 않고 미분류 검토 항목**으로 남긴다. 예를 들어 `LATE`를 보고 임의로 지각공제하지 않는다. 부재 코드 목록 자체의 누락 가능성까지 코드가 탐지하는 것은 아니므로 최종 완결 판정은 허용하지 않는다.

## 4. 계산과 Output

```python
from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.attendance_preview import build_attendance_adjusted_preview
from bhandara.payroll.output_excel import write_payroll_result_xlsx

attendance_plan["worktime_sha256"] = sha256_file(
    "/secure/worktime/worktime-result.xlsx"
)
preview = build_attendance_adjusted_preview(
    inputs, "/secure/worktime/worktime-result.xlsx",
    settlement_plan=settlement_plan,
    attendance_plan=attendance_plan,
    period_from="2026-11-01", period_to="2026-11-30",
    # Optional: only cross-check the listed approved overtime intervals.
    approved_overtime_segments=None,
)

write_payroll_result_xlsx(
    preview["payroll_register"], "/secure/output/payroll-result.xlsx"
)
```

**합성 예시:** 승인된 일할 기본급 후보가 3,000,000원, 무급휴가 차감 후보가 60,000원이면 급여대장의 **기본급 후보는 2,940,000원**으로 표시된다. 단, `settlement_review.employees`에 `base_before_attendance_adjustment=3000000`, `base_reduction_candidate=60000`과 별도의 `attendance_review.events` 근거가 남는다. 차감액을 **공제/4대보험/세금** 열에 넣지 않는다. 고정수당의 출근일 조건·무급휴가 감액 여부는 **아직 평가하지 않는다**.

결과의 `earnings_complete=False`, `deductions_complete=False`, `PARTIAL_REVIEW_ONLY`, `NOT_APPROVED`는 유지한다. **지급합계·공제합계·실지급액은 계속 공란**이다.

## 5. 초과근무와의 관계 / P1-5b-2 잔여

- `approved_overtime_segments`를 제공한 경우 해당 승인 구간과 휴가/결근 **시각의 중첩만 검사하여 오류 차단**한다. 제공하지 않으면 `overtime_overlap_review=NOT_ASSESSED`로 표시한다. 빈 목록이라도 전체 승인 근무의 부존재를 증명하지 않는다.
- **초과근무 수당 금액은 P1-5b-1의 기본급 후보에 합산하지 않는다.** 기존 P1-2/3/4 계산은 급여기간에 한 개의 계약을 선택하는 경로이고, P1-5a/5b는 월중 계약분할을 처리한다. 각 승인 근로구간을 해당 시점의 계약 기준시급·분모에 연결하는 독립 검증이 없으면 **잘못된 급여**가 된다.
- 향후 P1-5b-2는 계약분할된 근로구간의 임금 기준, 같은 날 복수 휴가, PTO Closing의 실제 사용/잔여 원장, 고정수당 감액, 근로/휴가/연장 구간 전체 누락 및 중복검증, 외부 승인·정본 인증 등을 연결한다.
- P2 보험·세액·급여 공제, P3 JSON Tool CLI/Workflow, Gearbox 운영 전환 및 구형 계산기 철수는 이후 작업이다. `agent-config` PAUSE, 서버 브랜치 정리 보류.

**테스트:** `python3 -m unittest bhandara.tests.test_payroll_attendance_settlement_p1 -v`와 전체 Bhandara/Gearbox 기능·인프라 회귀.
