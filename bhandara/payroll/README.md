# Payroll — 신규 계약·수당·성과급 코어 + 동적 급여대장 Output (2026-11-19)

> **현재 상태: PARTIAL_REVIEW_ONLY.** P0 코어·단일 동적 Excel Output(PR #59/#60), P0-1 독립 Reader(PR #62), P0-2/3 정확 산정기간·검토용 Adapter(PR #63), P1-1 Worktime 근무사실 검토 Bridge(PR #64)는 **모두 병합 완료**. P1-2 승인구간 수당 후보(PR #65)와 P1-3 독립 출처원장 내용 대조(PR #66)도 **병합 완료**. P1-4 중복가산 후보(PR #67)까지 병합 완료. P1-5a 계약·재직기간 일할 후보(PR #68)도 병합 완료. P1-5b-1 승인 휴가·결근 근거 대조와 기본급 차감 후보(PR #69)까지 병합 완료. P1-5b-2a 계약별 초과근무수당 후보 통합(PR #70)도 병합 완료. 후속 **Flow 경량화 PR**에서는 중간 급여대장 역변환을 제거하고 Worktime 원본 파싱·계약 검증·동적 Output 생성 횟수를 각각 1회로 정리하되 **법적 정책 인증·실제 지급 승인·휴가/입퇴사 정산·보험/세금·독립 JSON CLI 및 Gearbox/Slack 연결은 미구현**이다. 이 결과는 지급·신고·회계 확정 자료가 아니며 구형 `payroll-calculator/`도 교체하지 않는다.

## 목표: 입력별 계산, 개인별 합산

1. **개인별 계약·지급 시트**: 매년 갱신되는 계약 ID, 계약유형(`ANNUAL|MONTHLY|WEEKLY`), 계약서 금액, 산정기간, 지급일, 일할계산용 일급(`daily_base_rate`), 공제 정책 선택 ID(`deduction_code`).
2. **고정수당 매핑 시트**: `allowance_id + level`에 대해 금액 및 **급여 지급 시점** 과세·비과세 구분. 개인별 고정수당 배정은 **계약 ID만 참조하는 ALLOWANCE ASSIGNMENTS 행**으로 보유한다. 직원 ID는 CONTRACTS에서 조회하므로 중복 작성하지 않는다. CSV 문자열 배열을 요구하지 않는다.
3. **초과근무 기준 시트**: Worktime 사실 + 조기/지연/연장/야간/휴일의 승인·구간·배율·지급규칙을 결합해 변동수당을 만들 계획. **P1-2부터 검토 후보 산정 지원. 실제 법적 지급 적격성/승인 증빙의 진위는 미확정.** Worktime의 `actual_min`과 출퇴근 Δ를 더해서 지급 시간을 추정하면 안 된다. 날짜별 합계만으로 야간·휴일 구간은 확정할 수 없으므로 추가 검증된 구간 증빙이 필요하다.
4. **성과급 두 시트**: `BONUS BUDGET`의 `bonus_id`별 팀 또는 프로젝트 하나와 예산, `BONUS ALLOCATION`의 개인별 배분율을 조인한다.

## 고정 파일명: 하나의 역할 = 하나의 Excel 파일

**실행 시 선택한 `input_root/payroll/`에 7개 파일을 각각 둔다(Reader v1.1 계약).** 하나의 다중 시트 통합 Excel은 신규 입력 계약이 아니다. 각 파일은 표의 시트 **하나만** 포함하며, 파일명/시트명/헤더 정본은 [`input-files.json`](input-files.json)으로 고정한다.

| 파일명 | 시트명 | 역할 |
|---|---|---|
| `pay-contract.xlsx` | `CONTRACTS` | 직원·계약 ID, 급여계약·기간·지급일, 공제정책 ID |
| `allowance-assignments.xlsx` | `ALLOWANCE ASSIGNMENTS` | 계약 ID별 수당 ID·Level 배정 |
| `fixed-allowance-map.xlsx` | `FIXED ALLOWANCE MAP` | 수당 ID·이름·Level별 금액·급여 지급 시 과세 후보 |
| `deduction-map.xlsx` | `DEDUCTION MAP` | 공제정책 ID별 4대보험 근로자 부담 비율 |
| `overtime-rules.xlsx` | `OVERTIME RULES` | 초과근무 지급 구간·기준·배율 |
| `bonus-budget.xlsx` | `BONUS BUDGET` | 팀/프로젝트별 성과급 ID·이름·예산 |
| `bonus-allocation.xlsx` | `BONUS ALLOCATION` | 성과급 ID별 개인 배분율 |

파일 연결:
- `allowance-assignments.contract_id → pay-contract.CONTRACTS.contract_id → employee_id`
- `allowance-assignments.(allowance_id, level) → fixed-allowance-map.(allowance_id, level)`
- `pay-contract.CONTRACTS.deduction_code → deduction-map.DEDUCTION MAP.deduction_code`
- `bonus-allocation.bonus_id → bonus-budget.BONUS BUDGET.bonus_id`

**분리형 입력 샘플 ZIP**은 채팅에서 7개 XLSX로 제공했다. GitHub main의 공개 샘플 경로에서 `pay-contract.xlsx`는 확인됐지만 나머지 6개 신규 XLSX는 2026-11-19 조회 당시 확인되지 않았다. 기존 `pay-contract.xlsx`의 실제 시트가 새 `CONTRACTS` 단일 시트 규격인지도 검증 전이다. Reader는 P0-1에서 구현됐으나 Tool CLI는 미구현이다. **스키마 v1.1의 `allowance_name`·`bonus_name` 추가로 기존 ZIP은 그대로 재사용할 수 없다.** 공개 샘플 파일은 사용자 승인 없이 덮어쓰지 않는다.

## 각 Excel의 입력 헤더 계약

| 시트 | 주요 필드 | 비고 |
|---|---|---|
| CONTRACTS | employee_id, contract_id, pay_basis, contract_amount, amount_type, installments_per_year, declared_base_amount, daily_base_rate, deduction_code, calculation_period_from, calculation_period_to, payment_date | 명시한 산정기간의 **정확한 일치**만 선택하는 P0-2 함수 제공. 계약의 실제 법적 유효기간 및 일할 판단은 미구현 |
| ALLOWANCE ASSIGNMENTS | contract_id, allowance_id, level | 계약별 수당 1행. 직원 ID는 CONTRACTS에만 보유하며, ID 앞의 0은 텍스트로 보존 |
| FIXED ALLOWANCE MAP | allowance_id, allowance_name, level, amount, payroll_taxability, taxability_policy_ref | `TAXABLE|NON_TAXABLE|REVIEW`는 지급 시점의 후보 구분. 법적 한도·자격 검증 미실시 |
| DEDUCTION MAP | deduction_code, national_pension, health_insurance, longterm_care, employment_insurance, source_ref | 공제 ID별 근로자 부담율(소수 형태, 예: 4.75% → 0.0475). **직원 ID 없음**. 실제 공제액 미산정 |
| OVERTIME RULES | rule_id, category, qualifying_from, qualifying_to, minimum_minutes, daily_rate_multiplier, policy_ref | 승인된 검증구간에만 적용하는 수당 후보 규칙(법적 적정성 별도 검증) |
| BONUS BUDGET | bonus_id, bonus_name, team_id, project_id, budget_amount | 팀/프로젝트 **둘 중 정확히 하나**. 별도 증빙으로 대상 소속 확인 필요 |
| BONUS ALLOCATION | bonus_id, employee_id, allocation_ratio | 각 bonus_id별 0~1의 합계 = 1. 배분율 30%는 `0.3` |

## 공개 샘플과 실행 입력 경로는 별도

**공개 샘플 정본**은 `bhandara/examples/sample/input/payroll/` 아래에 고정 파일명 7개를 두는 것이다. 기존 `bhandara/examples/sample/input/` 합성 샘플 체계에 추가하는 경로이며, `refresh.py --apply`나 기존 공개 샘플을 임의로 덮어쓰지 않는다.

**실행 입력 위치**는 별개다: `input_root/payroll/` 아래에 같은 7개 파일명을 배치한다. `input_root`는 향후 Tool CLI 설정 JSON에서 선택한다. Reader 함수는 구현됐다. 실행용 JSON Tool CLI는 아직 없다.

2026-11-19 합성 Excel 파일은 대화에서 제공하는 **별도 ZIP 다운로드**이며, 현재 PR의 Git 추적 대상에 바이너리 XLSX를 추가한 것은 아니다. 사용자 로컬에서 샘플을 설치하려면 저장소 루트에서 ZIP을 풀기 전에 파일명 충돌 여부를 확인하고, 샘플 폴더만 추가하면 된다. 실제 직원 자료를 공개 샘플이나 Git에 넣어서는 안 된다.

## 계약 갱신과 ID 연결 원칙

- `CONTRACTS.contract_id`는 계약 버전별 고유 ID다. 한 시점의 대상 계약에서 중복되면 오류다.
- `CONTRACTS.employee_id`는 직원 식별자로 **한 번만** 보유한다.
- `ALLOWANCE ASSIGNMENTS.contract_id`를 `CONTRACTS.contract_id`에 연결해 직원과 계약조건을 확인한다.
- `CONTRACTS.deduction_code`를 `DEDUCTION MAP.deduction_code`와 연결한다. 공제율은 개인별이 아니라 정책별로 관리하며, 계약이 변경돼도 동일 정책이면 동일 `deduction_code`를 참조할 수 있다.
- 연봉협상·재계약으로 계약 ID가 달라진다면 **새 계약 ID의 수당 배정도 명시**해야 한다. 과거 계약의 수당 배정을 자동 승계하면 안 된다.
- 일별 근무 분수는 `Worktime`의 검증된 스케줄 또는 근로시간 자료를 참조한다. 계약 시트에 중복 입력하지 않는다.

## 계산 코어 사용 예

`bhandara.payroll.core`는 **검증된 dict 행**만 받는 순수 계산 함수이며 Excel을 직접 읽지 않는다.

- `resolve_contract_pay(contracts)`: 대상 계약을 직원당 한 개씩 입력받고 기본급/기준 일급을 보존한다. 연봉은 명시된 지급 횟수로만 나눈다. **BASE** 계약은 계약금액을 기본급으로 해석하고 고정수당을 더한다. **TOTAL** 계약은 명시된 `declared_base_amount`와 수당 합계가 계약총액과 일치해야 한다. 합계로 기본급 자동 역산 금지.
- `resolve_fixed_allowances(contracts, mapping, assignments)`: 수당 ID+Level 금액을 직원에 연결한다. 계약 ID를 통해 직원과 연결한다. 중복 배정, 매핑 누락, 존재하지 않는 계약 ID는 차단한다.
- `resolve_deduction_mapping(contracts, mapping)`: 계약에 기록한 `deduction_code`로 국민연금·건강보험·장기요양·고용보험의 **근로자 부담율** 네 개를 조회한다. 매핑 ID 중복, 누락, 0~1 범위 밖 비율을 차단한다. 실제 공제액 계산과 별개다.
- `allocate_performance_bonus(contracts, budgets, assignments)`: 보너스별 배분율 100% 확인, 원 단위 잔액은 **가장 큰 소수 잔여 → 직원 ID** 순서로 나눠 예산 보존.
- `build_partial_payroll(contracts, allowances, bonuses)`: 기본급+고정수당+성과급 **일부 합계**만 표시. 언제나 `PARTIAL_REVIEW_ONLY`, `OVERTIME_PAY/DEDUCTIONS/NET_PAY` 미산정.

`payment_date`, `calculation_period_*`는 전달받은 문자열을 추적하기만 한다. 날짜 형식·적용기간 중복/선택 검증은 아직 없으므로 이 코어만으로 전체 급여 실행 준비가 됐다고 판단하면 안 된다. 초과근무 시간 및 일할·퇴직 계산에 쓰일 `daily_base_rate`는 이번 단계에서 **보존만** 한다. 근로시간 관련 정보는 Worktime의 스케줄/실근로 결과에서 가져오며, CONTRACTS의 `standard_day_minutes`는 **삭제**했다. 일할계산과 배율 적용 산식은 후속 구현.

성과급 배정 직원이 팀/프로젝트에 실제 소속되는지는 지금 검증하지 않는다. 향후 부서/프로젝트 명부와 명시적으로 대조한다.

## 공제 정책: Excel은 비율, JSON은 산정기준

개인별 `DEDUCTION ASSIGNMENTS` 시트는 사용하지 않는다. `CONTRACTS.deduction_code`로 `DEDUCTION MAP` 한 행을 조회한다. 고정수당과 동일한 **ID 기반 재사용 정책**이다.

`DEDUCTION MAP`의 핵심 열:

| 열 | 의미 | 2026년 정규 근로자 부담률 예시 |
|---|---|---|
| `deduction_code` | 정책 ID(예: `INS-2026-REG`) | 정책 버전마다 발급 |
| `national_pension` | 국민연금 근로자 기여율 | 4.75% (0.0475) |
| `health_insurance` | 건강보험 근로자 부담률 | 3.595% (0.03595) |
| `longterm_care` | **건강보험료에 대한** 장기요양보험료 비율 | 13.14% (0.1314) |
| `employment_insurance` | 고용보험 근로자 부담률 중 실업급여 부분 | 0.9% (0.009) |
| `source_ref` | 공시 근거/버전 참조 URL | 사용자 검증용 |

위 예시는 **2026년도 공개 요율의 근로자 부담 측면**이며 모든 계약의 실제 공제액을 확정한다는 뜻이 아니다. 공식 근거:
- 국민연금 https://www.nps.or.kr/pnsinfo/ntpsklg/getOHAF0097M0.do
- 건강보험 https://www.nhis.or.kr/renewal_popup/poster/20260204_poster_longdesc_1.html
- 장기요양 https://m.korea.kr/briefing/pressReleaseView.do?newsId=156725039&pWise=mSub&pWiseSub=C10
- 고용보험 https://www.work24.go.kr/cm/c/f/1100/selecSystInfo.do?systId=SI00000419

**실제 계산에서 `기본급 × 보험율`로 통일하면 안 된다.** 보험마다 산정기준액이 다르다. 국민연금은 신고/결정된 기준소득월액, 건강보험은 보수월액, 장기요양은 건강보험료, 고용보험은 관련 법령상 보험료 산정대상 보수를 사용한다. 근로자·사용자 부담, 상하한, 산정 제외 항목, 적용기간, 원 단위 처리·공단 고지와의 대조를 확인해야 한다.

`deduction-policy.example.json`은 **이 산정기준과 검증 원칙을 기술**하며 비율을 중복 기록하지 않는다. 현재 Core는 비율 매핑까지만 구현했다. 보험별 산정기준 자료와 계산 규칙이 연결되기 전에는 공제액을 산정하거나 순지급액을 확정하지 않는다.

`payroll_taxability`는 **급여 지급시의 세무상 분류 후보**이며, 연말정산 시뮬레이션을 뜻하지 않는다. 예시의 식대 금액/구분은 법적 비과세 적용 여부를 확정하지 않는다.

## 동적 급여대장 Output v0.1

- 신규 순수 출력 모델: [`output.py`](output.py) (`build_payroll_register`) — [PR #60](https://github.com/seo-an/portfolio/pull/60) 병합 완료.
- 2단 헤더, 동적 항목열, 직원별 공란 및 고정 파일명 `payroll-result.xlsx` 단일 `PAYROLL` 시트 Writer: [`output_excel.py`](output_excel.py).
- 전체 직원 중 1명이라도 **0원이 아닌** 수당·성과급·초과근무수당·공제가 있으면 해당 항목 ID별 열이 생긴다. 모두 0원이면 열은 생기지 않는다.
- 지급합계·공제합계·실지급액은 **해당 계산 완료를 입력에서 명시한 경우에만** 채운다. 모든 금액이 있어도 지급 승인 상태는 아니다.
- `review_adapter.py`에서 검증된 기본급·고정수당·성과급의 ID/이름/금액을 동적 Output에 연결한다. **완료 플래그는 항상 False**로 유지하며, 실제 공제액·Worktime 추가근무수당·입퇴사 정산은 미산정.
- 정식 규칙: [Payroll Output 계약](OUTPUT-CONTRACT.md). 테스트: `bhandara.tests.test_payroll_dynamic_output_v01`.

## Excel Reader (P0-1)

`input_excel.py`의 `read_payroll_inputs(input_root, roles=...)`로 `input-files.json`에 정의된 분리 XLSX를 선택적으로 읽고, 헤더·수식·ID·금액·날짜·참조 관계를 엄격히 검증한다. Reader는 사람용 표시명 열을 엄격히 검증하고, P0-2/3 독립 함수가 산정기간 정확 일치와 검토용 이름 연결을 수행한다. 계약의 실제 효력기간/일할, 보험료·실지급액과 Tool CLI는 미연결이다. [사용법·제약 및 검증](INPUT-READER.md) 참고.

## P0-2/3 계약기간 및 검토용 Output Adapter

[산정기간·스키마 v1.1·Core→Output 연결 및 실행 예시](PERIOD-PREVIEW.md). 요청 구간과 산정기간이 정확히 일치하는 계약만 선택하고, 수당/성과급 이름을 기존 Excel 두 곳에서 읽는다. 인사·노무 관련 실제 계약 효력, 기간 분할과 임금 완결성은 자동 확정하지 않는다.

## P1-1: Worktime 근무 사실의 Payroll 검토 인계

[Worktime Bridge 계약](WORKTIME-BRIDGE.md) · `worktime_bridge.py`의 `build_payroll_worktime_review()`는 독립 Worktime의 단일 10열 Excel을 대상으로 월/주급 산정기간·직원 ID를 검증하고, 조기출근·지연퇴근·휴무일 출근 등 **검토 필요 사실**만 분류한다. 실제 승인 근로시간·야간/휴일 가산·임금액은 산정하지 않으며, 검토용 Payroll Output도 항상 `PARTIAL_REVIEW_ONLY`다. Worktime 자료는 Payroll 기존 7개 입력 시트에 추가하지 않는다.

## P1-2: 검증 근로·승인 구간의 금액 후보 계산

[가산수당 후보 계약](OVERTIME-CANDIDATES.md). `overtime_candidates.py`는 기존 초과근무 규칙과 **외부 검증 실제 근로구간/승인구간/분모·반올림 정책**을 명시적으로 결합해 추가 지급액 **후보**를 계산한다. `overtime_preview.py`는 이를 기존 `payroll-result.xlsx`의 동적 초과근무수당 열에 반영하되, **지급합계/공제합계/실지급액은 공란**, 직원 상태는 `PARTIAL_REVIEW_ONLY`로 고정한다. 승인근거 문자열의 실제 진위 검증, 법적 가산 중복·휴일 판정·휴가/입퇴사 정산과 JSON Tool CLI는 미구현이다. 7개 고정 Payroll Excel 파일·기존 Worktime 10열은 변경하지 않는다.

## P1-3: 별도 원장 출처 대조

[근무·승인 출처 대조](EVIDENCE-RECONCILIATION.md). `evidence_reconciliation.py`는 P1-2 근로/승인/분류/기본급 포함 사실을 **별도로 취득한 원장 스냅샷**과 대조한다. 근로·결재 참조의 내용 불일치·취소·중복을 차단하고, `evidence_preview.py`가 기존 동적 검토용 대장에 연결한다. 출처 레코드 자체의 **진위/승인자 권한/원장 완전성은 이 함수가 인증하지 않는다**. 지급액은 여전히 후보다.

## P1-4: 정확한 시간 중복·기본 1배분 중복방지

[중복가산 정책·검증 계약](OVERTIME-STACKING.md). 기존 `rate_policy`에 선택적으로 `overlap_policy`를 전달하여, 별도 승인된 연장·야간·휴일 **분류 조합**을 실제 겹치는 시간 구간 단위로 검사한다. 정책이 없으면 모든 중첩을 그대로 차단하고, 지정되지 않은 조합·같은 수당분류 중복·기본급 포함 여부 충돌도 차단한다. 기본급 미포함 시간의 **기준 1배분을 정책에서 지정한 수당에 단 한 번만** 배정한 후 각 수당 후보 금액을 합산한다. 실제 법적 지급 적격성은 검증하지 않는다.

## P1-5a: 입·퇴사·재계약 기간분할 검토 후보

[계약·재직기간 분할 정본](SEGMENTED-SETTLEMENT.md). `settlement_coverage.py`가 **재직 증빙·계약기간 승인 배정·직원별 연속 기간**을 명시적으로 대조하고, `segmented_settlement.py`가 계약별 전체 월/주급의 기본급과 고정수당을 **승인 적용일수에 비례하여** 계산한다. 각 계약에서 원 단위 처리를 먼저 하지 않고 직원·수당별 월간 합산 후 처리한다. 월중 입퇴사·연봉협상은 별도 자료를 요구하며, 현재 계약 Excel의 `calculation_period_from/to`는 법적 효력일이 아님을 유지한다. **P1-5b 유급/무급휴가·결근, 초과근무 결과와의 통합, P2 공제·원천세, CLI/운영 연결은 여전히 미구현**이다. 기존 7종 독립 Excel과 단일 급여대장 형식은 변경하지 않는다.

## P1-5b-1: 휴가·결근/Worktime 사실과 명시적 기본급 정산

[근태·휴가 정산 입력·검토 계약](ATTENDANCE-SETTLEMENT.md). `attendance_reconciliation.py`는 기존 Worktime 10열 일별 휴가/근태 코드와 **외부에서 이미 승인·금액 산정한 사건구간**을 참조 ID, 직원·기간·계약 ID·SHA-256으로 대조한다. 유급휴가는 명시적으로 0원, 무급휴가·결근은 **이미 확인된 양의 원 단위 차감액**만 허용한다. `attendance_preview.py`는 P1-5a 기본급 일할 후보에서 그 금액만 차감해 **기존 단일 급여대장 기본급 열**에 표시한다. 근로시간 차이를 차감액으로 계산하지 않고, 미확인 사건은 자동 0원 처리하지 않는다. 초과근무 구간은 제공된 경우 겹침만 차단하고 금액 합산은 아직 하지 않는다. 모든 합계와 실지급액은 공란, 미승인 상태를 유지한다.

## P1-5b-2a: 월중 계약변경과 초과근무 후보의 안전한 연결

[계약별 초과근무 합산 계약](CONTRACT-SCOPED-OVERTIME.md). 기존 P1-2/3/4 승인 수당 계산과 P1-5a/5b-1 일할·근태 차감 후보를 **신규 어댑터**에서 결합한다. 각 승인 근로구간의 적용 계약을 찾고 **그 계약의 기준 일급·분모**를 사용한다. 계약 변경일을 가로지르는 승인 구간은 임의 분할하지 않고 차단한다. 계약별 원 단위 처리 후 합산할 때의 차이 때문에 `rollup_policy`를 명시적으로 받는다. 기존 7개 입력 Excel, Worktime 10열, 단일 급여대장 형식과 기존 계산기 코드는 변경하지 않는다.

## Payroll Flow 경량화 — 지급항목을 모은 뒤 Output 한 번

[검증·지급항목 조립·Output 단일화 설계](INTEGRATED-FLOW.md). 확정된 7개 Excel과 Worktime 10열·급여대장 규격은 바꾸지 않고, 월중 계약분할·휴가 정산·초과근무의 **중간 동적 급여대장 재생성**을 제거한다. `segmented_settlement._build_segmented_components()`가 기존 계산 결과를 직원별 항목 목록으로 전달하고 `contract_scoped_overtime.build_contract_scoped_overtime_preview()`에서 Worktime을 한 번 파싱해 전체 검증 뒤 `build_payroll_register()`를 딱 한 번 호출한다. 독립 P1-5a/P1-5b-1 공개 함수의 실행·결과 스키마는 유지한다.

## P1-5b-2b-1: 복수 PTO 신청·확정 Closing 수량 대조

[정확한 PTO Closing/사용 상세 교차검증](PTO-CLOSING-REVIEW.md). 기존 `deduction-quantity-result.xlsx`의 정확한 분자·분모, `usage-ledger-result.xlsx`의 신청/발생 배정 상세, **외부에서 확정한** `closing-result.xlsx`의 월별 숨김 정본을 비교한다. Worktime 10열의 **하루 신청 ID 하나**는 여러 PTO 상세 신청 중 대표 참조와 대조하며, 다른 신청은 외부 승인 상세 명세에서 별도 보존한다. 신규 Payroll Flow의 선택적 `pto_sources` 입력으로 호출하지만 지급/감액 금액은 자동 생성하지 않는다. 이미 확정한 PTO/Worktime 산식과 Excel 계약, Payroll 7개 입력 및 PAYROLL 단일 Output은 수정하지 않는다.

## P1-5b-2b-2: 복수 휴가의 별도 임금결정과 고정수당 감액 후보

[복수 PTO 임금결정 계약](LEAVE-WAGE-ADJUSTMENTS.md). P1-5b-2b-1의 확정 Closing·PTO 정확분수/신청별 수량 대조(PR #72 병합)를 먼저 통과한 경우에만 **회사 외부 승인 기본급/고정수당 감액금액**을 받는다. Worktime 일별 대표 신청에서 P1-5b-1이 이미 차감한 금액은 다시 차감하지 않고, 추가 신청의 별도 결정만 반영한다. 수당 ID와 현재 지급 후보·금액 상한을 확인하고 유급휴가에 임의 감액을 만들지 않는다. 검토용 후보이며 과세·실지급액은 여전히 미완료다. 기존 7개 Excel·WORKTIME 10열·PAYROLL 단일 Output 그대로.

## 마감 전 PTO 검토 — 동일 계산 경로

[PTO 마감 전/확정 공통 계약](PTO-CLOSING-REVIEW.md). 당월 Closing이 없으면 `pto_sources["closing_file"]=None`으로 같은 `reconcile_pto_closing()`를 호출한다. Usage 실행 기준일·Deduction 파일 해시·정확 신청수량/승인 시각을 대조하고 기존 급여대장의 **검토상태 열**에 `마감 전 · 변동 가능`을 표시한다. 마감 확정 후에는 원래 Closing 월간 수량 교차 검증으로 전환한다. 외부 승인된 휴가 임금결정과 중복 차감 방지는 두 상태에서 같은 코드를 사용하며 결과는 전부 미승인 검토 후보다.

## P2-1 — 외부 확정 산정기준액으로 4대보험 공제 후보

[4대보험 후보 계산 계약](INSURANCE-CANDIDATES.md). 기존 7개 XLSX 중 `deduction-map.xlsx`의 4종 근로자 부담률과 `CONTRACTS.deduction_code`를 사용한다. 직원별 **보험마다 다른 산정기준액/가입 적용 여부/근거**는 외부에서 승인한 `insurance_assessment_plan`으로만 받는다. 기간과 요율 정책이 불일치하거나 산정기준액이 없으면 계산을 차단한다. 별도 8번째 Excel 없이 보험료를 기존 `deductions` 동적 열에 보여주지만 **원천세 미구현으로 공제합계와 실지급액은 공란**이다.

## P2-2 — 지급항목별 과세·비과세 분리 및 원천징수 후보

[과세분류·근로/지방소득세 공제 계약](TAX-WITHHOLDING.md). 기존 7개 Payroll Excel·한 시트 Output은 유지한다. 기본급, PTO 차감 후 고정수당, 계약별 초과근무, 성과급의 **실제 지급 후보 전액**에 대해 외부 확인 과세/비과세 분할 금액을 비교한다. `FIXED ALLOWANCE MAP.payroll_taxability`와 비과세 정책 참조를 검증하고, 별도 확인·승인한 **근로소득세와 지방소득세 원 단위 공제 후보**를 기존 동적 공제 열로 출력한다. 세액표/비과세 법정한도는 자동 계산하지 않으며 지급합계·공제합계·실지급액은 계속 공란이다.

## 잠정 합계·검증요청 플래그 (PR #77)

기존 **7개 입력 Excel 및 PAYROLL 한 시트의 열 배치·동적 항목**을 변경하지 않고, 통합 Flow는 기존 항목을 한 번 합산하여 **지급합계·공제합계·실지급액의 잠정값**을 표시한다. 누락되거나 아직 확정되지 않은 산식/근거는 0원으로 확정하지 않고 기존 `검토상태` 열의 **`검증요청 · 잠정합계`**, `review_flags` 및 `review_requests`에 남긴다. 숫자가 나온다고 지급·신고가 승인된 것은 아니다. 과거 P0/P1 독립 Preview는 구형 합계 공란 동작을 유지한다. [Output 최신 규약](OUTPUT-CONTRACT.md).

## 보험 가입상태와 사업주 산재보험료 (PR #77 보강)

[공통 직원보험 취득상태·산재 사업주 부담 계약](EMPLOYER-INSURANCE.md). 보험별 취득일/공란(적용 제외)/`미가입`은 기존 `common/employee.xlsx`에서 관리한다. **국민연금·건강보험·고용보험의 미확인 상태와 소득세·지방소득세만** 근로자 급여 `검토상태`의 요청 사유로 삼는다. 지급항목·기타 공제의 미해당 공란은 정상이다.

**산재보험료는 외부 확인 요율·산정기준액으로 회사 부담 후보를 계산**하고, 관리자 급여대장 `사업주 부담·회사 전용`과 `회사 비용(확인분)`으로만 출력한다. 직원 지급합계·공제합계·실지급액에 포함하지 않으며 직원별 조회에는 사업주 비용을 삭제한다. **회사 비용(확인분)은 아직 다른 3종 사업주 보험료·퇴직충당을 포함하지 않은 일부 비용**이다.

## P3-1 — JSON 설정으로 독립 실행 (진행 중)

[Payroll Tool CLI 설명](TOOL-CLI.md), [설정 예제](config.example.json). 기존 7개 단일시트 XLSX, Worktime 결과, 외부 검증된 승인/정책 JSON의 **파일 참조**만 지정하여 `python3 run.py bhandara payroll`로 한 번에 실행한다. 새 계산기·중복 급여대장·회사 원가분석 로직은 만들지 않는다. 결과는 `payroll-result.xlsx/PAYROLL`과 간략한 `payroll-review.json`이며 원본 인력 파일은 복제하지 않는다. **회사 비용(확인분)은 다른 모듈로 인계 가능한 부분합계**, 실제 전체 인건비가 아니다.

## 실행 / 테스트

```bash
python3 -m unittest bhandara.tests.test_payroll_core_v1 -v
```

**Excel Reader, P0 검토용 기간/ID/표시명 Adapter, P1-1 Worktime 사실 검토는 병합됐다.** 실제 계약 유효기간과 일할, 인정 초과근무·공제액 산정, 선택적 Payroll Tool CLI와 전체 Flow 연결은 남았다. [우선순위와 선행조건](NEXT-STEPS.md)을 따른다. `payroll-calculator` 구형 입력/결과를 새 Worktime `WORKTIME` Excel로 자동 대체하지 않는다. 새 Tool 계약이나 버전이 바뀔 때는 Gearbox 호환성 검증이 필수이며, 현재 `agent-config`는 사용자 지시에 따라 PAUSE 중이다.
