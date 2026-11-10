# Payroll 단독 실행기 CLI v0.1 — 운영책

## 현재 구현된 기능

Payroll은 Worktime 계산기를 실행하지 않는다. Worktime 결과 또는 검증된 마감 Receipt, 유효기간별 Compensation XLSX, 월별 Payroll Input XLSX, Registry, Operating Config, 회사·법정 Policy, Employment Facts를 읽어 **기존 Operational Payroll 계산 엔진**을 호출한다.

**반드시 구분:** 이 CLI가 산출하는 금액은 검토용이다. Worktime 마감 승인, 원천세·사회보험료 확정, 실제 급여 승인, Settlement Ledger commit, 최종 급여대장은 자동으로 수행하지 않는다. 모든 직원의 can_auto_finalize는 false이며, 금액 계산 성공이어도 REVIEW_REQUIRED(exit 2)를 반환한다.

## 1. 준비 자료

사용자는 다음 자료를 비공개 월별 폴더에 준비하고, 파일 경로를 단일 설정 파일 payroll-config.json에 넣는다.

| 설정 key | 필수 | 의미 |
|---|---|---|
| schema_version | 예 | 0.1 |
| payroll_period | 예 | 급여 계산월 YYYY-MM |
| expected_worker_ids | 예 | 급여 지급 대상 독립 직원명부의 canonical worker_id 목록. 임의 계산 결과에서 추출 금지 |
| compensation_path | 예 | 기존 Compensation XLSX 계약. worker_id/effective_from/effective_to + 급여항목 |
| payroll_input_path | 예 | 기존 Payroll Input XLSX 계약. 변동 지급, 공제, 소급 등의 거래 |
| worktime_result_path | 택 1 | Worktime 독립 CLI 산출 worktime-result.json. REVIEW_REQUIRED 입력은 계산 가능하지만 마감 미승인 |
| worktime_rows_path | 택 1 | 기존 검증된 Worktime 행 JSON 리스트. 마감 증명 아님 |
| worktime_closes_path | 택 1 | 승인된 Worktime 기간 마감 Receipt JSON 리스트. 해시·원본 기간·전체 직원 coverage 검증 |
| registry_path | 예 | gearbox/registry/pay-item-registry.json |
| operating_config_path | 예 | gear/payroll-calculator/operating-config.json. Worktime 전월/당월 귀속 자동 해석 |
| company_policy_path | 택 1 | 기존 단일 회사 급여정책 JSON. policy_catalog_path와 동시 사용 불가 |
| policy_catalog_path | 택 1 | 여러 정책 Profile/Scenario와 default_scenario_id를 가진 카탈로그 v0.2. 자세한 내용: [POLICY-SCENARIOS.md](POLICY-SCENARIOS.md) |
| scenario_id | 선택 | 카탈로그에서 선택할 시나리오. 생략하면 카탈로그 default_scenario_id 사용. --scenario-id로 덮어쓰기 가능 |
| legal_policy_path | 예 | 해당 시점 검증된 Payroll 법정기준 JSON |
| employment_facts_path | 예 | worker_id, employment_from/to를 기록한 JSON 리스트. expected_worker_ids와 일치해야 함 |
| recurring_pay_item_codes | 예 | 정기 계산 급여항목 목록. 예: ["base_salary"] |
| settlement_ledger_path | 선택 | 기존 정산원장 XLSX. **읽기 전용**으로 사용하며 신규 거래가 있어도 commit하지 않음 |

추가 선택 자료(전부 JSON 리스트): eligibility_facts_path, absence_events_path, absence_deduction_inputs_path, weekly_holiday_inputs_path, historical_rerun_results_path. 없다고 해서 임의의 수당·공제·주휴시간을 만들어 내지 않는다.

파일 경로가 상대경로이면 **payroll-config.json이 있는 디렉터리 기준**으로 해석한다. 모든 원본과 생성 결과는 Git 저장소 외부의 비공개 경로에 보관한다. 출력 디렉터리는 반드시 새 경로를 사용한다.

설정 예: examples/payroll-standalone-config.example.json. 실제로 실행할 수 있는 가상 자료 생성 스크립트는 examples/payroll-standalone-demo/generate.py.

## 2. 명령어

저장소 루트에서 다음을 실행한다.

~~~bash
cd /opt/agents/config/agent-config

python3 gearbox/gear/payroll-calculator/run.py calculate \
  --config /private/payroll/2026-10/payroll-config.json \
  --output-dir /private/payroll/output/2026-10/payroll-review-01
~~~

원본 파일들의 열 이름이 회사마다 다르다면 PR #90의 run.py normalize로 표준화한 후 기존 급여 XLSX 계약에 맞게 가공해야 한다. **현재 CLI 자체에는 임의 원본을 Compensation/Payroll Input XLSX로 자동 재구성하는 단계가 없다.** 이 연결은 후속 통합 Workflow에서 구현한다.

## 3. 결과 파일과 오류 처리

| 결과물 | 의미 |
|---|---|
| payroll-calculation.json | 계산 결과, source counts, 직원별 검토 Validation, Ledger 거래 요청 후보 및 선택된 policy_selection |
| payroll-calculation.xlsx | Summary / Calculation Detail / Validation의 검토용 급여 내역 |
| payroll-review.json | 전 직원 기대 목록과 실제 결과 비교, 정책 선택 기록, 입력 해시, 원본 Worktime 상태, 누락·검토 사유 |
| payroll-review.xlsx | Run Summary / Worker Coverage / Review Required |
| policy-resolution.json | 계산에 사용된 최종 회사 정책, 프로필·시나리오 ID, 선택 우선순위, 기본 시나리오 대비 변경 경로, SHA-256. 계산 성공 시 생성 |

정상 계산 시에는 자료가 충분해도 REVIEW_REQUIRED(exit 2), 기존 계산·검토 결과 4개와 정책 적용 기록 policy-resolution.json(총 5개)을 남긴다. 독립 직원명부 대비 계산 결과가 누락되면 BLOCKED(exit 2)이지만 정상 계산된 다른 직원의 결과는 함께 보존한다. 준비 단계 또는 계산 엔진 자체에서 예외가 발생하면 BLOCKED(exit 2)이고 **payroll-review.json / payroll-review.xlsx 두 개만** 생성한다. 이때 계산금액을 추측해서 채우지 않는다.

원천 Worktime의 BLOCKED 상태는 미완료 출퇴근을 빠뜨린 채 계산하는 위험이 있어 이 단계에서는 계산하지 않고 실패 리포트로 남긴다. Worktime REVIEW_REQUIRED나 CALCULATED_UNCLOSED 상태는 계산하되 직원별 Worktime 검토와 마감 누락 상태를 함께 기록한다. Worktime 마감 Receipt를 사용하더라도 원천세·보험료와 실제 지급 승인까지 완료되는 것은 아니다.

현재 계산 엔진이 Payroll 중 한 명의 원본 계약 오류로 배치 전체 예외를 내는 경우에는 임시 결과 금액을 제공하지 않는다. **직원별 계산 엔진 실패를 격리하고 통합 Workflow에서 임시 급여대장을 생성하는 기능은 다음 개발 단계**다.

## 4. 로컬 가상 데이터 연속 검증

먼저 Worktime 단독 실행기(PR #91)까지 테스트한다. 아래는 예시이므로 **이전에 사용한 /tmp 출력 폴더가 존재하면 숫자를 변경**한다.

~~~bash
cd /opt/agents/config/agent-config

python3 gearbox/gear/payroll-calculator/run.py normalize \
  --input-dir gearbox/gear/payroll-calculator/examples/source-mapping-demo \
  --output-dir /tmp/payroll-demo-normalized-01

python3 gearbox/gear/worktime-calculator/run.py calculate \
  --normalized /tmp/payroll-demo-normalized-01/normalized-input.json \
  --config gearbox/gear/worktime-calculator/examples/standalone-config.demo.json \
  --output-dir /tmp/payroll-demo-worktime-01

python3 gearbox/gear/payroll-calculator/examples/payroll-standalone-demo/generate.py \
  --worktime-result /tmp/payroll-demo-worktime-01/worktime-result.json \
  --output-dir /tmp/payroll-demo-input-01

python3 gearbox/gear/payroll-calculator/run.py calculate \
  --config /tmp/payroll-demo-input-01/payroll-config.json \
  --output-dir /tmp/payroll-demo-result-01
~~~

가상 직원 2명의 Compensation과 월별 변동급여 XLSX, Employment Facts 및 정책 JSON을 세 번째 명령으로 만든다. 선택 가능한 시나리오 예제는 [POLICY-SCENARIOS.md](POLICY-SCENARIOS.md)에 별도로 있다. Worktime은 승인 근거가 없는 날의 계산값만 있으므로 두 번째와 네 번째 명령은 **REVIEW_REQUIRED, exit 2**가 맞다. Payroll의 보고서 4개가 있어야 하며, 직원 2명 모두 ACTION_REQUIRED인 것이 의도한 동작이다.

## 5. 에이전트에게 그대로 지시할 요청문

> Payroll 계산만 독립 실행해줘. gearbox/gear/payroll-calculator/STANDALONE-CLI.md와 RUNBOOK.md를 읽고, <payroll-config.json 경로>에 기재된 자료를 확인한 후 run.py calculate --config ... --output-dir ...로 실행해줘. Worktime은 다시 계산하지 말고 해당 파일의 상태 및 근로시간 귀속기간을 검증해. 독립 직원명부 대비 급여 계산 대상자 누락, 미완료 Worktime, 세금·보험·정산원장 미검증, 직원별 ACTION_REQUIRED/ERROR를 payroll-review 파일로 보고해줘. 가능한 계산 결과는 payroll-calculation.xlsx/json에 보존하되, 지급 승인을 만들거나 최종 급여대장으로 확정하지 마. Settlement Ledger를 변경하지 마. 실행 권한이 없는 경우 실행했다고 보고하지 말고 필요한 실행 명령을 전달해.

## 6. 검증 방법

~~~bash
python3 -m unittest discover \
  -s gearbox/_tests/gear/payroll-calculator \
  -p 'test_payroll_standalone_cli.py'

python3 gearbox/_tests/run.py
python3 gearbox/_tests/core_run.py
~~~

## 7. 서버 검증 이력 (2026-10-30)

- 검증 대상: `feat/payroll-standalone-cli-v1` — PR #92
- 최초 단독 테스트: 10건 중 4건 실패. CLI를 독립 프로세스로 실행할 때 저장소 루트가 Python 모듈 경로에 없어 `ModuleNotFoundError: No module named 'gearbox'` 발생
- 대응: `run.py` 실행 시 저장소 루트/함수 경로를 설정하고, `normalize` 명령은 Payroll 계산 모듈을 필요할 때만 가져오도록 수정. 다른 작업 디렉터리에서 `PYTHONPATH` 없이 실행하는 회귀 테스트 2건 추가
- **수정 후 사용자 서버 검증: 단독 테스트 12건, Gearbox 전체 회귀, 인프라 테스트 모두 PASS 보고 확인**
- 이 검증은 **가상 입력과 기존 테스트 계약의 통과**를 의미하며, 실제 회사 데이터에 대해 급여·세무·사회보험·승인 절차가 완료되었다는 의미가 아니다.
- 독립 Payroll CLI의 실제 사용은 1~5절의 설정·명령·리포트를 기준으로 한다. 계산 결과의 `REVIEW_REQUIRED` 및 exit code `2`는 자료 검토가 필요한 설계상 상태다.

**다음 개발 순서:** 두 독립 Gear를 연결하는 통합 Workflow → 단계/직원별 예외 격리와 임시 산출물 → 사회보험·원천세 계산과 최종 확정 요건 완성.
