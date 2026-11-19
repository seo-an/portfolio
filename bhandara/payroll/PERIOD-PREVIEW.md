# Payroll P0-2/3: 산정기간 선택 및 검토용 급여대장 연결

## 입력 스키마 v1.1

기존 7개 개별 Excel과 고정 파일명/시트명은 변경하지 않는다. 이름을 추측하지 않도록 **기존 2개 시트에 필수 열만 추가**했다.

- `fixed-allowance-map.xlsx / FIXED ALLOWANCE MAP`: `allowance_name` — `allowance_id`의 사람이 읽을 수 있는 이름. **같은 ID는 모든 Level에서 같은 이름**이어야 한다. Level별 금액만 다름
- `bonus-budget.xlsx / BONUS BUDGET`: `bonus_name` — `bonus_id`의 이름. 팀/프로젝트 범위와 배분액은 기존 방식대로 유지

필수 이름을 빈칸, 엑셀 수식, 위험한 셀 시작 문자로 채우거나 ID를 이름으로 자동 치환하면 오류다. **구버전 7개 샘플 ZIP은 스키마 v1.1에 자동 호환되지 않는다.** 공개 합성 XLSX를 변경할 때는 사용자 승인과 기존 샘플 영향 검증이 별도 필요하다.

## P0-2: 보수적인 기간 선택

`contract_period.select_contracts_for_period(rows, period_from=..., period_to=...)`는 요청한 명시적 급여 **산정기간**과 `CONTRACTS.calculation_period_from/to`가 정확히 일치하는 계약만 직원당 1건 선택한다. 과거/미래의 비중첩 행은 제외하지만 요청기간과 **일부라도 겹치는** 계약이 있으면 오류다.

- 월급 계약: 온전한 달력 월(1일~말일)만
- 주급 계약: 연속한 7일을 포함하는 산정기간만
- 연봉 계약: 명시된 연간 지급 횟수 **12회(월 1회)** 또는 **52회(주 1회)**의 온전한 구간만 P0 미리보기 지원. 다른 횟수/불규칙 지급은 정책·구간 정본이 필요하므로 보류
- 중도 입퇴사·재계약 당월·연봉 갱신·복수 계약·기간 일부 공란: **자동 일할/보간/한 건 선택 금지**, 별도 검토 입력/정책이 준비되기 전에는 차단
- `calculation_period_*`는 **급여 산정구간**이지 계약서 효력발생일/종료일 자체가 아니다. 실제 계약 효력기간, 입퇴사일, 급여차감 근거는 **현재 입력 계약으로 확정할 수 없다.** 법적 계약 유효기간에 대한 판정이라고 주장하지 않는다

## P0-3: Core → Output 검토용 연결

`review_adapter.build_payroll_review_register(inputs, period_from=..., period_to=...)`는 다음 5개 역할이 모두 읽혔을 때만 동작한다.

1. `contracts`
2. `allowance_assignments`
3. `fixed_allowance_map`
4. `bonus_budget`
5. `bonus_allocation`

역할은 필수지만 수당·성과급이 없는 해당 시트는 **헤더만 있고 행이 0개여도 가능**하다. 없는 역할을 0원으로 가정하지 않는다. 이미 검증된 과거 계약의 수당 배정은 새 계약에 자동 상속하지 않는다. 선택 시점에 보너스 배정을 받은 직원이 근무 대상이 아니라면 계산을 차단한다.

직원별로 기본급, 고정수당(`allowance_id → allowance_name`), 성과급(`bonus_id → bonus_name`)을 계산하여 기존 `build_payroll_register`로 전달한다. **출력열 ID는 Level이 아닌 수당 ID**를 유지한다. 실제 Worktime 초과근무, 결근·연차·일할, 성과급 팀/프로젝트 소속의 외부 증빙, 4대보험·원천세 계산과 승인 상태는 이 단계에서 수행하지 않는다.

따라서 Adapter는 직원마다 **항상** `earnings_complete=False`, `deductions_complete=False`를 명시하고, `overtime_allowances=[]`, `deductions=[]`를 미산정으로 취급한다. 동적 수당·성과급 열과 개인별 기본급은 검토 미리보기로 보이지만 **지급합계·공제합계·실지급액은 공란**이다. 상태는 `PARTIAL_REVIEW_ONLY`, 문서는 `NOT_APPROVED`가 된다.

## 독립 함수 호출 예시 (Tool CLI는 P3)

```python
from pathlib import Path
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.review_adapter import build_payroll_review_register
from bhandara.payroll.output_excel import write_payroll_result_xlsx

inputs = read_payroll_inputs(
    Path("/private/synthetic-input"),
    roles=("contracts", "allowance_assignments", "fixed_allowance_map",
           "bonus_budget", "bonus_allocation"),
)
preview = build_payroll_review_register(
    inputs, period_from="2026-11-01", period_to="2026-11-30",
)
write_payroll_result_xlsx(
    preview, Path("/private/synthetic-output/payroll-result.xlsx"),
)
```

입력 경로는 실행기/설정 JSON에서 지정하며 실제 HR 데이터는 공개 Git/샘플/로그에 보존하지 않는다. Writer는 기존 파일 덮어쓰기를 금지한다. 생성된 Excel은 **계산 중간 확인용일 뿐 지급 승인용이 아니다.**

## 테스트

```bash
python3 -m unittest bhandara.tests.test_payroll_input_reader_p0 -v
python3 -m unittest bhandara.tests.test_payroll_period_preview_adapter_p0 -v
python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
```

검증 후에도 P1(인정 초과근무), P2(보험·세금과 근태 정산), P3(독립 선택 Flow/CLI), Gearbox 운영 연결은 미구현이다. `agent-config`는 PAUSE 중이며 수정하지 않는다. 변경된 Tool 계약은 Gearbox 기능·인프라 호환성 테스트를 서버에서 반드시 검증한다.
