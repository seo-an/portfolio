# Payroll — 신규 도구 개발 (계약·고정수당·성과급 계산 코어 v0.1)

> **현재 상태: PARTIAL_REVIEW_ONLY.** 이 폴더는 `payroll-calculator/`를 교체하지 않는다. 아직 독립 Tool CLI, Excel Reader/Writer, 초과근무 지급, 보험료·공제, 순지급액, Gearbox 연동이 없다. 이 PR의 계산 결과는 지급·신고·회계 확정 자료가 아니다.

## 목표: 입력별 계산, 개인별 합산

1. **개인별 계약·지급 시트**: 매년 갱신되는 계약 ID, 계약유형(`ANNUAL|MONTHLY|WEEKLY`), 계약서 금액, 산정기간, 지급일, 일할계산용 일급(`daily_base_rate`), 일일 기준 분(`standard_day_minutes`), 공제항목 배정.
2. **고정수당 매핑 시트**: `allowance_id + level`에 대해 금액 및 **급여 지급 시점** 과세·비과세 구분. 사람별 배정은 중복·구분자 오류를 피하려고 **별도 ALLOWANCE ASSIGNMENTS 행**으로 보유한다. CSV 문자열 배열을 요구하지 않는다.
3. **초과근무 기준 시트**: Worktime 사실 + 조기/지연/연장/야간/휴일의 승인·구간·배율·지급규칙을 결합해 변동수당을 만들 계획. **현재 미구현.** Worktime의 `actual_min`과 출퇴근 Δ를 더해서 지급 시간을 추정하면 안 된다. 날짜별 합계만으로 야간·휴일 구간은 확정할 수 없으므로 추가 검증된 구간 증빙이 필요하다.
4. **성과급 두 시트**: `BONUS BUDGET`의 `bonus_id`별 팀 또는 프로젝트 하나와 예산, `BONUS ALLOCATION`의 개인별 배분율을 조인한다.

## 제안 Excel 시트 스키마 (샘플은 별도 XLSX 다운로드로 제공)

| 시트 | 주요 필드 | 비고 |
|---|---|---|
| CONTRACTS | employee_id, contract_id, pay_basis, contract_amount, amount_type, installments_per_year, declared_base_amount, daily_base_rate, standard_day_minutes, calculation_period_from, calculation_period_to, payment_date | 적용기간 선택은 **추후 Reader/CLI 책임**; 현재는 *외부에서 대상 기간에 해당하는 계약을 정확히 1행 선택해 전달* |
| ALLOWANCE ASSIGNMENTS | employee_id, contract_id, allowance_id, level | 한 사람에게 수당별 1행, ID 앞의 0은 텍스트로 보존 |
| FIXED ALLOWANCE MAP | allowance_id, level, amount, payroll_taxability, taxability_policy_ref | `TAXABLE|NON_TAXABLE|REVIEW`는 지급 시점의 후보 구분. 법적 한도·자격 검증 미실시 |
| DEDUCTION ASSIGNMENTS | employee_id, deduction_code | 대상 선정만 정의, 공제액 미산정 |
| OVERTIME RULES | rule_id, category, qualifying_from, qualifying_to, minimum_minutes, daily_rate_multiplier, policy_ref | 정책 설계 샘플. 초과근무 계산 미구현 |
| BONUS BUDGET | bonus_id, team_id, project_id, budget_amount | 팀/프로젝트 **둘 중 정확히 하나**. 별도 증빙으로 대상 소속 확인 필요 |
| BONUS ALLOCATION | bonus_id, employee_id, allocation_ratio | 각 bonus_id별 0~1의 합계 = 1. 배분율 30%는 `0.3` |

## 계산 코어 사용 예

`bhandara.payroll.core`는 **검증된 dict 행**만 받는 순수 계산 함수이며 Excel을 직접 읽지 않는다.

- `resolve_contract_pay(contracts)`: 대상 계약을 직원당 한 개씩 입력받고 기본급/기준 일급을 보존한다. 연봉은 명시된 지급 횟수로만 나눈다. **BASE** 계약은 계약금액을 기본급으로 해석하고 고정수당을 더한다. **TOTAL** 계약은 명시된 `declared_base_amount`와 수당 합계가 계약총액과 일치해야 한다. 합계로 기본급 자동 역산 금지.
- `resolve_fixed_allowances(contracts, mapping, assignments)`: 수당 ID+Level 금액을 직원에 연결한다. 수당 ID 중복 배정, 매핑 누락, 계약 불일치면 차단한다.
- `allocate_performance_bonus(contracts, budgets, assignments)`: 보너스별 배분율 100% 확인, 원 단위 잔액은 **가장 큰 소수 잔여 → 직원 ID** 순서로 나눠 예산 보존.
- `build_partial_payroll(contracts, allowances, bonuses)`: 기본급+고정수당+성과급 **일부 합계**만 표시. 언제나 `PARTIAL_REVIEW_ONLY`, `OVERTIME_PAY/DEDUCTIONS/NET_PAY` 미산정.

`payment_date`, `calculation_period_*`는 전달받은 문자열을 추적하기만 한다. 날짜 형식·적용기간 중복/선택 검증은 아직 없으므로 이 코어만으로 전체 급여 실행 준비가 됐다고 판단하면 안 된다. 초과근무 시간 및 일할·퇴직 계산에 쓰일 `daily_base_rate`는 이번 단계에서 **보존만** 한다. 일할계산과 배율 적용 산식은 후속 구현.

성과급 배정 직원이 팀/프로젝트에 실제 소속되는지는 지금 검증하지 않는다. 향후 부서/프로젝트 명부와 명시적으로 대조한다.

## 공제율 JSON 원칙

`deduction-policy.example.json`은 정책 항목의 **형식 예시일 뿐 실제 적용 가능한 비율표가 아니다**. 공시된 보험료율, 대상 보험별 부과 기준액, 근로자/사업주 부담 구분, 기간별 상하한, 절사 규칙을 독립 정책으로 검증 후 적용한다. 산재보험의 일반 근로자 공제액을 만들어서는 안 된다. 보험료율이 없거나 기준액이 확정되지 않으면 **미산정**이다.

`payroll_taxability`는 **급여 지급시의 세무상 분류 후보**이며, 연말정산 시뮬레이션을 뜻하지 않는다. 예시의 식대 금액/구분은 법적 비과세 적용 여부를 확정하지 않는다.

## 실행 / 테스트

```bash
python3 -m unittest bhandara.tests.test_payroll_core_v1 -v
```

독립 Payroll Tool CLI 및 최종 급여대장 Excel은 다음 단계에서 만든다. `payroll-calculator` 구형 입력/결과를 새 Worktime `WORKTIME` Excel로 자동 대체하지 않는다. 새 Tool 계약이나 버전이 바뀔 때는 Gearbox 호환성 검증이 필수이며, 현재 `agent-config`는 사용자 지시에 따라 PAUSE 중이다.
