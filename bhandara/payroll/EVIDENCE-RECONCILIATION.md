# Payroll P1-3 — 근무·승인 출처 기록 별도 대조

P1-2에서는 `verification_ref`, `approval_ref`, `classification_ref`, `base_inclusion_ref`가 비어 있지 않은지만 확인했다. 이번에는 **별도 취득한 원장 스냅샷**과 승인 근로구간의 **직원·날짜·시작/종료시각·상태·수당분류·기본급 포함 여부**를 대조한다.

검증 함수: `evidence_reconciliation.reconcile_overtime_evidence()`. 검토 대장 통합: `evidence_preview.build_reconciled_overtime_preview()`.

## 외부 원장 계약

다음 JSON은 모두 **합성자료**다. `work_verifications` 항목에는 P1-2의 `verified_work` 6개 열과 `status=VERIFIED`가 모두 들어간다. `approvals`에는 `approved_segments` 11개 열 전부와 `status=CURRENT`가 들어간다. 별도의 `classifications` 및 `base_inclusions` 기록은 같은 `segment_id`를 가리켜야 한다.

```json
{
  "schema_version": "0.1",
  "period_from": "2026-11-01",
  "period_to": "2026-11-30",
  "source_system": "SYNTHETIC-HRIS",
  "snapshot_ref": "SNAPSHOT-DEMO-001",
  "work_verifications": [
    {
      "evidence_id": "W001",
      "employee_id": "0001",
      "work_date": "2026-11-02",
      "start_at": "2026-11-02T17:00",
      "end_at": "2026-11-02T18:00",
      "verification_ref": "V001",
      "status": "VERIFIED"
    }
  ],
  "approvals": [
    {
      "segment_id": "A001",
      "work_evidence_id": "W001",
      "employee_id": "0001",
      "work_date": "2026-11-02",
      "start_at": "2026-11-02T17:00",
      "end_at": "2026-11-02T18:00",
      "rule_id": "OT01",
      "approval_status": "APPROVED",
      "approval_ref": "AP001",
      "classification_ref": "CL001",
      "base_pay_includes_time": false,
      "base_inclusion_ref": "BASE001",
      "status": "CURRENT"
    }
  ],
  "classifications": [
    {
      "classification_ref": "CL001",
      "segment_id": "A001",
      "rule_id": "OT01",
      "category": "OVERTIME",
      "policy_ref": "SYNTHETIC-OVERTIME-POLICY",
      "status": "VERIFIED"
    }
  ],
  "base_inclusions": [
    {
      "base_inclusion_ref": "BASE001",
      "segment_id": "A001",
      "base_pay_includes_time": false,
      "status": "VERIFIED"
    }
  ]
}
```

`classifications.policy_ref`는 기존 `overtime-rules.xlsx`에서 같은 `rule_id`가 가진 `policy_ref`와 일치해야 한다. 근로/승인 참조에 다른 직원·시간이 들어오거나 중복 참조·거절/취소/미검증 상태가 있으면 **전체 작업을 차단**한다. 선택 기간 밖의 근로구간도 차단한다.

**한계:** 이 코드는 **원장 레코드 간 내용 일치**를 검증한다. 원장 원본의 진위, 승인자 권한, 전자서명, 스냅샷 최신성과 누락 없는 전체 모집단을 인증하지는 않는다. `source_system`·`snapshot_ref`는 추적용 문자열이지 인증 정보가 아니다. 입력을 작성한 사람이 원장도 임의로 만든다면 아무런 신뢰 추가가 없다.

## 호출 예시

```python
from bhandara.payroll.evidence_preview import build_reconciled_overtime_preview

result = build_reconciled_overtime_preview(
    inputs,
    "/secure/worktime/worktime-result.xlsx",
    period_from="2026-11-01", period_to="2026-11-30",
    verified_work=verified_work,
    approved_segments=approved_segments,
    evidence_registry=evidence_registry,
    rate_policy=rate_policy,
)
register = result["payroll_register"]
audit = result["evidence_review"]
```

결과에는 `claim_consistency=MATCHED_SOURCE_RECORDS`와 `source_authenticity=NOT_AUTHENTICATED_BY_THIS_MODULE`가 동시에 남는다. 기존 Payroll 7개 XLSX 및 Worktime 10열은 변경하지 않는다. 가산수당 금액은 **검토 후보**일 뿐 지급합계·공제합계·실지급액은 공란이며 `PARTIAL_REVIEW_ONLY` / `NOT_APPROVED`가 유지된다.

**후속:** 외부 원장 Reader 및 실제 권한·서명·스냅샷 최신성 검증, 법정/사규 중복가산·휴일 분류, 휴가·중도입퇴사 정산, P2 공제, P3 JSON Tool CLI와 Gearbox 운영 연결. `agent-config` 수정 PAUSE 유지.

테스트: `python3 -m unittest bhandara.tests.test_payroll_evidence_reconciliation_p1 -v`.
