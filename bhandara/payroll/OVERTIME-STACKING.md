# Payroll P1-4 — 연장·야간·휴일 **중복구간** 수당 후보 검토

> 기존 P1-2의 `base_pay_includes_time` 필드 의미를 바꾸지 않는다. `True`는 **해당 근로분의 1배 기준임금이 이미 계약 기본급에 포함**됐다는 뜻이고, `False`는 **포함되지 않았다는 뜻**이다. 동일 시각의 승인구간이 이 값에서 충돌하면 차단한다.

## 이번 단계의 목적

한 직원의 근로시간이 `OVERTIME`·`NIGHT`·`HOLIDAY` 중 여러 분류에 동시에 속할 수 있다. 기존 P1-2는 모든 중첩을 차단했다. P1-4는 **정확히 명시한 분류 조합만 허용**하고, 원 단위 최종 반올림 이전에 **미지급 기준 1배분 임금을 단 한 번만 배분**한다.

- 새 순수 모듈: `overtime_stacking.review_approved_stacking()`. 직원별 시작/종료 시각을 분 단위 구간으로 나누어 그 구간에서 동시에 활성화된 분류 집합을 검사한다.
- 기존 호출 경로: `overtime_candidates.calculate_overtime_candidates()`가 `rate_policy.overlap_policy`(선택적)를 받는다. 미전달 시 P1-2와 동일하게 **모든 중첩 차단**.
- 분류가 다른 승인 두 개라도 **같은 카테고리의 중복 수당**, 승인되지 않은 분류 조합, 상충하는 기본급 포함 사실, 두 번 계산될 기본 1배분은 차단.
- `stacking_review.overlap_slices`에 직원/시작·종료/분류/승인 구간 ID/겹친 분수/미지급 기준 1배분 배정 대상을 남긴다. **법적 적합성이나 지급 승인으로 승격하지 않는다.**

## 추가 JSON 정책의 정확한 구조

이 설정은 계산기가 **임의로 생성하지 않으며**, 회사의 별도 지급 기준과 분류·중복가산에 대한 확인을 전제로 외부에서 명시해야 한다.

```json
{
  "multiplier_semantics": "TOTAL_RATE",
  "rounding_scope": "EMPLOYEE_RULE_PERIOD",
  "rounding_mode": "DOWN",
  "reference_day_minutes_by_contract": {
    "C01": 480
  },
  "rule_labels": {
    "OT01": "연장근로수당",
    "N01": "야간근로 가산수당"
  },
  "overlap_policy": {
    "mode": "EXPLICIT_CATEGORY_SETS",
    "policy_ref": "SYNTHETIC-STACKING-EXAMPLE",
    "same_category": "BLOCK",
    "base_component_policy": "CONSISTENT_INCLUSION_SINGLE_OWNER",
    "allowed_category_sets": [
      {
        "categories": ["OVERTIME", "NIGHT"],
        "unpaid_base_owner": "OVERTIME"
      }
    ]
  }
}
```

`allowed_category_sets`는 가능한 모든 조합을 묵시적으로 허용하는 목록이 아니라 **해당 시각에 동시에 활성화되어도 되는 분류의 정확한 집합 목록**이다. 예를 들어 `OVERTIME+NIGHT`만 적으면 `HOLIDAY+NIGHT`나 `OVERTIME+NIGHT+HOLIDAY`는 **거부**된다. 세 분류가 겹칠 수 있게 하려면 3개 집합을 별도로 등록해야 하고, 일부 시간에 2개만 활성화된다면 해당 2개 집합도 등록해야 한다.

`unpaid_base_owner`는 **동일 근로분이 기본급에 포함되지 않았을 때** 중복된 기준임금(1배분)을 어느 항목에 한 번만 남길지 지정한다. 예시에서는 `OVERTIME`이 기준 1배분의 소유 항목이고 `NIGHT`는 가산분만 남긴다. 기본급에 이미 포함된 근로분이라면 이 소유 설정을 사용하지 않고 모든 항목에서 1배분을 제외한 **추가 가산분만** 계산한다.

이 모듈은 정책의 문자열·구조와 금액 산식의 일관성만 검증한다. **회사 취업규칙/근로계약/관련 법령상 이 조합을 가산해도 되는지**, 휴일근로 단계별 가산을 어떻게 구분하는지, 통상임금과 단위시간 분모가 맞는지는 증명하지 않는다. `policy_ref`는 **출처 인증이 아닌 참조 ID**다.

## 합성 계산 예시 — 2026년의 실제 법정 요율이라고 주장하지 않음

기준 일급 96,000원, 환산분모 480분, **같은 60분**에 OVERTIME 총 배율 1.5와 NIGHT 총 배율 1.5가 **외부에서 분류·승인**됐다고 가정한다.

| 기준 1배분 임금의 상태 | 연장 항목 후보 | 야간 항목 후보 | 추가 지급 후보 합계 |
|---|---:|---:|---:|
| 둘 다 기본급에 **미포함**(False), OVERTIME을 1배분 소유자로 명시 | 18,000원 | 6,000원 | 24,000원 |
| 둘 다 기본급에 **기포함**(True) | 6,000원 | 6,000원 | 12,000원 |
| 두 승인구간의 기본급 포함 여부가 서로 다름 | 계산 중단 | 계산 중단 | 미확정 |

첫 행은 60분의 **기준임금 1배분을 OT에 한 번 배정하고**, 야간에서 중복 기준임금(1배분)을 빼 1.5+0.5=2배분으로 만든다. 이 선택은 **인증된 지급기준**을 대신하지 않는다.

직원×규칙×기간에 대한 원 단위 반올림 **직전**의 Decimal 금액에 중복 기준임금 조정을 수행한다. 0.5분 등 분 이하 구간, 본인 아닌 직원의 시간구간 혼합, 동일 분류 중첩, 허용되지 않은 조합, 분류별 기준급 포함 상태 불일치, 1배 이하의 미지급 분류에서 음수 가산 발생은 차단한다.

## 연결과 미완료 경계

기존 `build_overtime_candidate_preview` 또는 P1-3 `build_reconciled_overtime_preview`의 `rate_policy`에 위 `overlap_policy`를 추가하면 된다. **기존 7개 Payroll 분리 Excel, Worktime 10열, `payroll-result.xlsx` 단일 `PAYROLL` 시트 계약은 변경하지 않는다.**

- 실제 근로/승인/수당 분류 증빙은 **P1-2/P1-3의 별도 검증 입력**이 필수다. 출퇴근 시각 차이로 승인구간을 생성하지 않는다.
- `stacking_review.status=EXPLICIT_POLICY_MATCHED`는 **작성된 정책 구조와 입력의 일치**만 의미한다. 결재의 진위·승인자 권한·법적 가산 적격성·원장 포괄성은 여전히 확인하지 않는다.
- 서로 다른 수당 행의 `minutes`를 단순 합산하면 안 된다. 같은 60분이 두 카테고리에 각각 60분으로 표시될 수 있다. 인건비 집계는 **금액 성분**으로만 수행한다.
- 최종 급여대장의 수당 **후보 금액**은 보이지만 지급합계·공제합계·실지급액은 여전히 공란. `earnings_complete=False`, `deductions_complete=False`, `PARTIAL_REVIEW_ONLY` 및 `NOT_APPROVED` 유지.
- 새 JSON Tool CLI, 진짜 원장 진위/권한 검증, 법정 휴일분류·휴가 정산, 중도 계약 분할, P2 공제·원천세 및 실자료 지급승인은 별도 후속.
- 레거시 Calculator 3종은 새로운 Tool의 모든 계약/운영/회귀검증 후 철수: [철수 게이트](../LEGACY-RETIREMENT.md).

테스트: `python3 -m unittest bhandara.tests.test_payroll_overtime_stacking_p1 -v` 및 전체 Bhandara/Gearbox 기능·인프라 회귀.