# Payroll Policy Catalog / Scenario 운영책 (v0.2)

## 목표

**한 JSON에서 여러 회사 정책 Profile과 실행 시나리오를 관리**한다. 명령에서 시나리오를 지정하지 않으면 카탈로그에 명시된 default_scenario_id를 선택한다. 실무 급여 산정 및 기존 급여 프로그램 대조용 운영 시나리오와, 정책을 바꾸어 계산하는 가상 시나리오를 명확히 구분한다.

기존 급여 계산 수식과 Worktime·Payroll 독립 실행기 구조는 유지하고, 회사 정책 선택/검증 계층을 추가했다.

## 1. 카탈로그 형식

~~~json
{
  "schema_version": "0.2",
  "catalog_id": "company-payroll",
  "default_scenario_id": "production",
  "profiles": {
    "baseline": {
      "policy": {
        "ordinary_wage": {"monthly_basis_hours": 209, "pay_items": {}},
        "proration": {"base_salary": {"method": "역일수"}},
        "worktime_pay": {"base_component_policy": {}},
        "amount_processing": {
          "unit": 10,
          "method": "절사",
          "apply_at": "최종지급액",
          "remainder": {
            "handling": "settlement_ledger",
            "transaction_type": "rounding_carry",
            "settlement_month": 12
          }
        }
      }
    },
    "basis_200": {
      "inherits": "baseline",
      "overrides": {"ordinary_wage": {"monthly_basis_hours": 200}}
    }
  },
  "scenarios": {
    "production": {"profile_id": "baseline", "kind": "operational"},
    "basis_200_simulation": {"profile_id": "basis_200", "kind": "simulation"}
  }
}
~~~

209·200시간은 선택 기능 설명용이며 특정 사업장의 적법한 정책이나 권장값이 아니다.

- default_scenario_id는 필수이며 반드시 scenarios의 기존 ID를 가리켜야 한다. 잘못된 default를 대신 다른 항목으로 선택하지 않는다.
- Profile은 완성된 policy 객체를 직접 정의하거나 inherits + overrides를 이용해 상속한다. 상속은 중첩 객체를 병합하고 상위 값은 변경하지 않는다.
- 존재하지 않는 정책 경로의 overrides는 오타 위험이 있으므로 차단한다. 새로운 Pay Item에 대한 명시적 필드 추가는 proration / ordinary_wage.pay_items / worktime_pay.base_component_policy 아래에만 허용한다.
- 순환 상속, 존재하지 않는 시나리오·프로필, 불완전한 기본 정책 및 잘못된 스키마는 계산 전에 차단한다.
- 시나리오 kind는 operational 또는 simulation을 명시한다. 생략 시 임의 운영 정책을 추정하지 않는다.

## 2. 기본 선택 우선순위

| 우선순위 | 통합 Workflow | Payroll 독립 CLI |
|---|---|---|
| 1 | --scenario-id | --scenario-id |
| 2 | workflow-config.json의 scenario_id | payroll-config.json의 scenario_id |
| 3 | payroll-config.json의 scenario_id | 카탈로그 default_scenario_id |
| 4 | 카탈로그 default_scenario_id | - |

선택하지 않은 경우에도 default_scenario_id를 반드시 확정해서 실행한다. 카탈로그의 처음 등장한 시나리오나 가장 최근 시나리오를 임의 선택하지 않는다.

Payroll 설정의 기존 company_policy_path를 **policy_catalog_path로 교체**한다. 둘을 동시에 설정하면 BLOCKED다. 기존 단일 company_policy_path만 사용하는 레거시 설정은 계속 지원하지만 해당 설정에서 시나리오를 선택하려 하면 차단한다. 통합 Workflow가 임시 Payroll 설정을 생성할 때에도 카탈로그의 원본 경로를 유지한다.

~~~json
{
  "schema_version": "0.1",
  "payroll_period": "2026-10",
  "policy_catalog_path": "policy-catalog.json",
  "scenario_id": "production"
}
~~~

위 예시는 Payroll config의 **정책 관련 필드 발췌**이며 다른 필수 자료 경로, 직원명부, 급여항목 목록은 기존 계약에 따라 추가한다. scenario_id를 생략하면 카탈로그 default를 사용한다.

## 3. 실행

Payroll 독립:

~~~bash
python3 gearbox/gear/payroll-calculator/run.py calculate \
  --config /private/payroll/2026-10/payroll-config.json \
  --output-dir /private/payroll/output/default-01

python3 gearbox/gear/payroll-calculator/run.py calculate \
  --config /private/payroll/2026-10/payroll-config.json \
  --scenario-id basis_200_simulation \
  --output-dir /private/payroll/output/basis-200-01
~~~

통합 Workflow:

~~~bash
python3 gearbox/workflow/payroll/run.py run \
  --config /private/payroll/2026-10/workflow-config.json \
  --output-dir /private/payroll/output/workflow-default-01

python3 gearbox/workflow/payroll/run.py run \
  --config /private/payroll/2026-10/workflow-config.json \
  --scenario-id basis_200_simulation \
  --output-dir /private/payroll/output/workflow-basis-200-01
~~~

각 시나리오는 덮어쓰지 않는 **별도 출력 디렉터리**에 저장한다.

## 4. 산출물과 감사 추적

- payroll 결과 폴더의 policy-resolution.json: 선택 ID, profile ID, scenario kind, 선택 경로, default ID, 상속 목록, **합성된 실제 회사 정책**, 정책 SHA-256, 기본 시나리오 대비 모든 변경 필드.
- payroll-calculation.json / payroll-review.json: policy_selection 메타데이터를 포함한다.
- workflow-run.json: Payroll 계산 성공 시 선택된 policy_selection을 기록하며 산출물 SHA-256을 관리한다.
- 부분 직원 복구 시 동일한 정책을 모든 직원에게 적용하며, 정책 선택이나 회사 법정 기준을 재해석하지 않는다.

단일 정책 레거시 실행의 경우에도 정책 출처와 해시를 확인할 수 있다. 선택·변경 메타데이터를 통해 두 실행 결과의 기준 차이를 추적할 수 있다.

**현재 범위:** company policy 객체. 별도 legal policy JSON, Worktime assignment, operating-config의 지급/귀속월, Compensation 기본급, Payroll Input 등 원천 사실 자료는 이번 Catalog 선택으로 변경되지 않는다. 기본급 인상 시뮬레이션은 향후 입력 데이터 시나리오에서 다룬다. 기존 계산 모듈이 지원하지 않는 계산방법을 JSON에 추가한다고 새로운 산식이 생기지도 않는다.

운영과 simulation 구분은 출력 구분을 위한 명시적 메타데이터다. 어느 쪽도 현재 Workflow에서 자동 지급 승인 또는 Settlement Ledger commit을 수행하지 않는다.

## 5. 비식별 CLI 연속 데모

~~~bash
cd /opt/agents/config/agent-config

python3 gearbox/workflow/payroll/examples/generate_demo.py \
  --output-dir /tmp/payroll-scenario-company-01

python3 gearbox/workflow/payroll/examples/add_policy_scenarios.py \
  --input-dir /tmp/payroll-scenario-company-01

# --scenario-id 없음: default_scenario_id = baseline
python3 gearbox/workflow/payroll/run.py run \
  --config /tmp/payroll-scenario-company-01/workflow-config.json \
  --output-dir /tmp/payroll-scenario-base-01

# 선택된 가상 시나리오: 절사 단위를 100만 원으로 변경
python3 gearbox/workflow/payroll/run.py run \
  --config /tmp/payroll-scenario-company-01/workflow-config.json \
  --scenario-id rounding_1000000 \
  --output-dir /tmp/payroll-scenario-alt-01
~~~

데모 rounding_1000000은 **정책 선택과 실제 금액 차이 검증용의 극단적 시뮬레이션**이며 실무 운영 권장 절사단위가 아니다. EP0001은 기본 지급가능 금액 3,300,000원에서 시뮬레이션 3,000,000원으로 바뀌어 정책 차이가 계산에 반영됨을 검증한다. 정상 데모도 승인·세무 검토가 남아 REVIEW_REQUIRED/exit 2를 반환한다.

## 6. 검증 명령

~~~bash
python3 -m unittest discover -s gearbox/_tests/workflow -p 'test_payroll_policy_scenarios.py'
python3 -m unittest discover -s gearbox/_tests/workflow -p 'test_payroll_workflow.py'
python3 -m unittest discover -s gearbox/_tests/gear/payroll-calculator -p 'test_payroll_standalone_cli.py'
python3 gearbox/_tests/run.py
python3 gearbox/_tests/core_run.py
~~~

향후 단계: 서로 다른 원본 입력을 쓰는 사실 시나리오, 복수 시나리오 일괄 실행/비교 리포트, 기존 급여 프로그램 자료와 자동 대조, 원천세·사회보험 검증.

## 서버 검증 이력 — 2026-10-30

PR #95 작업 브랜치 feat/payroll-policy-scenarios-v1에서 사용자 서버 검증 완료.

- 신규 시나리오 전용 unittest, 기존 Workflow unittest, Payroll 단독 CLI unittest, Gearbox 전체 기능 및 인프라 테스트: **모두 PASS** (사용자 보고).
- 비식별 회사 원본 생성 및 정책 카탈로그 생성 성공: /tmp/payroll-scenario-company-01/policy-catalog.json.
- 옵션 생략 실행: `Policy scenario: baseline (profile=base, kind=operational, source=catalog_default)`.
- 명시적 선택 실행: `Policy scenario: rounding_1000000 (profile=rounding_million, kind=simulation, source=cli)`.
- 두 실행 모두 `Payroll Workflow: REVIEW_REQUIRED (calculation and comparison use only)`.
- 두 실행 모두 `normalize: PASS records=9 findings=0`, `worktime: REVIEW records=2 findings=2`, `prepare_payroll: PASS records=None findings=None`, `payroll: REVIEW records=2 findings=7`.
- 감사기록: /tmp/payroll-scenario-base-01/workflow-run.json 및 /tmp/payroll-scenario-alt-01/workflow-run.json.

**검증 의미:** 사용자가 제공한 실제 CLI 출력은 기본 시나리오 선택 및 명령어 우선 선택과 두 경로의 정상 계산 흐름을 직접 확인해 준다. 금액 차이(EP0001 3,300,000원 → 3,000,000원)는 신규 전용 unittest의 기대값이며, 제공된 CLI 출력에는 직원별 금액이 없으므로 CLI 로그에서 직접 금액을 확인했다고 주장하지 않는다. 실제 회사 급여 데이터 및 외부 급여 프로그램과의 일치 검증은 아직 별개다.

이번 검증 결과 기록을 위한 변경은 운영 문서에만 적용했으며 계산 코드 및 테스트는 서버 검증 이후 변경하지 않았다.


## 다중 시나리오 한 번에 계산·비교 (새 기능 — 서버 검증 대기)

`gearbox/workflow/payroll/run.py compare --config <workflow.json> --output-dir <new-output-dir>`를 사용하면 카탈로그의 Default를 기준으로 다른 모든 시나리오를 동시에 계산한다. `--scenario-ids <id1> <id2>`를 추가하면 선택한 시나리오만 비교한다. 비교 명령의 baseline은 **항상 카탈로그 Default**이며, 단일 run 명령의 scenario_id 설정 기본선택과 구별한다. 공통 근태 계산은 한 번만 실행한다. 직원·항목·회사합계 차액, 정책 변경 내역, 오류 보존 계약은 [Workflow 일괄 비교 운영책](../../workflow/payroll/SCENARIO-COMPARISON.md)을 참고한다.


## 시나리오별 회계식 급여대장 재사용 (신규, 검증 대기)

시나리오별 계산 결과로부터 별도 회계식 급여대장을 생성할 수 있다. 기존 run.py book 명령의 --calculation-json을 scenarios/<scenario_id>/04-payroll/payroll-calculation.json으로 지정하면 되며, 가상 계정 매핑 및 전월 계산자료(선택)를 함께 입력한다. 정책별 차액 비교와 회계식 장부의 전월 비교는 **서로 다른 분석**이므로 각각 독립 산출물로 관리한다. [ACCOUNTING-BOOK.md](../../workflow/payroll/ACCOUNTING-BOOK.md) 참고.
