# 신규 Payroll — 다음 구현 체크리스트 (2026-11-19 · P1-5b-2a 진행)

> **진행 현황:** Portfolio PR #58~#60(문서/코어/동적 단일 Output), #62(7종 Reader), #63(P0 기간·표시명 Adapter), #64(P1-1 Worktime 사실 검토) **병합 완료**. P1-2 승인구간 수당 **후보** 산정(PR #65), P1-3 출처 기록 대조(PR #66)도 병합 완료다. P1-4 중복가산 후보 PR #67도 병합 완료. P1-5a 재직·계약분할 일할 후보(PR #68)까지 병합 완료. P1-5b-1 휴가·결근 근거 대조와 기본급 차감 후보(PR #69)도 병합 완료됐다. P1-5b-2a는 **계약분할별 초과근무 단가 적용과 단일 검토대장 결합** 단계다. 신규 Payroll이 최종 급여를 확정하거나 지급한다는 뜻은 아니다.

## 현재 코드와 미구현의 정확한 경계

| 이미 완료 | 다음 구현 필요 |
|---|---|
| `payroll/core.py`: 계약/수당/성과급 코어. `input_excel.py`: 7종 Reader. `contract_period.py`: 정확 산정기간만 선택. `review_adapter.py`: 지급항목 표시명 및 검토용 Output 결합 | 계약의 실제 법적 유효기간·중간 변경/입퇴사 일할, 승인된 추가근로/휴가 정산, 보험료·세금 공제액, 완료상태 판정 |
| `payroll/input-files.json`: 고정 7개 파일명·시트 및 v1.1 표시명 필드 | JSON 설정 기반 선택적 Tool CLI, `input_root/output_root`, `steps`, 재실행 `run_id`, 외부 결과 참조/인계 및 예외 격리 |
| `payroll/output.py`: `build_payroll_register`, 동적 열/조건부 합계; P0 Adapter는 항상 미완료 플래그 전달 | 실제 산정 검증 후 직원별 `earnings_complete`/`deductions_complete`를 책임 있게 판정할 연결 |
| `payroll/output_excel.py`: `write_payroll_result_xlsx`, **`payroll-result.xlsx`/`PAYROLL` 단일 시트**, 2단 헤더, 미수령 공란, 덮어쓰기 차단 | 전체 Flow의 끝에서 해당 Writer 호출, 검증된 산출물로 실제 출력 검증 |
| `payroll-calculator/`: 구형 계산기의 검증된 코드와 테스트 유지 | 재사용 후보 확인 후 별도 Adapter; 구형 Worktime JSON에 신규 Worktime XLSX를 곧장 전달하는 행위 금지 |

## P0: 계산 코어와 실제 Excel 연결 (가장 먼저)

**구현 현황:** P0-1 Reader는 사용자 서버 검증 후 Portfolio PR #62로 병합됐다. P0-2 `contract_period.py`(정확히 일치하는 산정기간만)·P0-3 `review_adapter.py`(ID/이름/금액 및 미완료 플래그)는 PR #63으로 병합됐다. [새 스키마와 동작 계약](PERIOD-PREVIEW.md). **법적 계약 유효기간 판정·입퇴사 일할, 변동수당/실제 공제 계산 및 CLI는 여전히 미구현**이며, 후속 PR은 CI/서버 검증과 사용자 병합 전에는 완료로 취급하지 않는다.


1. `input-files.json` 정본으로 7개 **분리 XLSX, 각 1시트**를 엄격히 읽는다. 필수 헤더, 중복 키, ID의 선행 0, 수식 금지, 잘못된 금액/배분율, 기간을 검증한다. **파일이 존재한다는 이유만으로 계산/검토 승인 금지**.
2. `CONTRACTS`에서 직원/계약의 **적용기간**을 확정한다. 재계약·연봉협상으로 하나의 급여 산정기간에 계약이 둘 이상 걸치면 **자동으로 한 건을 고르지 않는다**. 기간별 분할 계산/외부 확인 계약을 설계한다. `calculation_period_from/to`는 현재 단순 문자열 보존이며 아직 적용기간 선택이 아니다.
3. `contract_id`로 고정수당 배정을, `deduction_code`로 공제율 정책을, `bonus_id`로 팀/프로젝트 예산과 직원 배분율을 연결한다. 계약 ID가 바뀌면 옛 수당 배정을 무단 상속하지 않는다.
4. **출력 표시명**의 정본은 기존 `FIXED ALLOWANCE MAP.allowance_name`, `BONUS BUDGET.bonus_name`으로 추가했다(스키마 v1.1). 같은 수당 ID는 Level이 달라도 이름을 일치시킨다. 보너스 배정 직원의 실제 소속·프로젝트 참여 증빙은 미확인이다.
5. `review_adapter.py`가 선택한 계약의 기본급·수당·성과급을 `output.py` 입력으로 연결한다. 지급합계/공제합계/실지급액은 P1/P2 미완료이므로 공란이며, **항상 `PARTIAL_REVIEW_ONLY`**이다. 정식 Tool CLI는 P3로 남긴다.

### 고정 입력 7개 (`input_root/payroll/`)

| 파일 | 연결 |
|---|---|
| `pay-contract.xlsx` | `employee_id`, `contract_id`, 연·월·주급, 계약금액, 기본급 일급, 산정기간, 지급일, `deduction_code` |
| `allowance-assignments.xlsx` | **`contract_id + allowance_id + level`**, 직원 ID 불필요 |
| `fixed-allowance-map.xlsx` | `allowance_id + level → amount + payroll_taxability` |
| `deduction-map.xlsx` | `deduction_code → national_pension/health_insurance/longterm_care/employment_insurance` |
| `overtime-rules.xlsx` | 조기·지연·연장·야간·휴일 판단 기준·승인·구간/배율용 샘플; 실제 계산 미구현 |
| `bonus-budget.xlsx` | `bonus_id`, 팀 또는 프로젝트 하나, 예산 |
| `bonus-allocation.xlsx` | `bonus_id + employee_id + allocation_ratio`, ID별 비율 합계 1 |

**스키마 v1.1 유의:** 수당 매핑과 성과급 예산 시트의 `allowance_name`, `bonus_name`이 새 필수 열이다. 이전 ZIP/공개 파일은 최신 스키마를 충족하지 않을 수 있다. 승인 없이 공개 합성 샘플 자동 갱신 금지.

**공개 샘플 업로드 별도 잔여:** `bhandara/examples/sample/input/payroll/pay-contract.xlsx`는 main에서 확인됨. 다른 6개 신규 고정 파일은 2026-11-19 확인 시 GitHub main에서 조회되지 않았음. 이전에 제공된 다운로드 ZIP은 Git commit이나 CLI 자동 인식의 증거가 아니다. 기존 공개 `pay-contract.xlsx`의 **실제 시트/스키마가 새 CONTRACTS 계약과 맞는지도 확인해야 한다**. 정식 공개 샘플은 사용자 승인 없는 `refresh.py --apply`로 덮어쓰지 않는다.

## P1: Worktime·승인된 근로의 급여 지급 판단

**P1-1 PR #64 병합 완료:** `worktime_bridge.py`와 [WORKTIME-BRIDGE.md](WORKTIME-BRIDGE.md) 추가. Worktime 10열 XLSX의 기간·직원·분값/ID를 검증하여 잠재 검토 코드를 생성하지만, **지급 인정시간과 금액은 아직 계산하지 않는다**. P1-2에는 별도의 승인된 구간/휴가/스케줄 및 정책·일급 분모 계약이 필요하다. 서버 검증·병합 전 구현 완료로 취급하지 않는다.


- 신규 Worktime 인계: `worktime-result.xlsx` / `WORKTIME` 10열. 시간 사실은 `scheduled_min`, `actual_min`, `clock_in_delta_min`, `clock_out_delta_min` **네 개**이며, `actual_min=null`은 0이 아니다.
- 출근 Δ = 예정−기록, 퇴근 Δ = 기록−예정. **둘 다 승인이 아니라 시각 비교 사실**이다. `actual_min`에 포함된 시간을 다시 더하지 않는다.
- 조기출근/지연퇴근/연장·야간·휴일/잔업 지급 규칙, 최저 인정시간·미승인 처리, 정산단위, 구간·일자 넘김, 중첩수당 적용과 수당 기준 일급 배율을 사용자가 정의한 `overtime-rules.xlsx`에 맞춘다. **일급×배율의 분할 시간 환산 방법은 정책으로 확정**한다. 임의로 `standard_day_minutes`를 계약에 복원하지 않는다.
- Worktime 결과의 일별 총분과 Δ만으로 **야간 시간대·휴일 구간** 또는 결재 상태는 산출되지 않는다. 스케줄 및 외부 검증·승인 구간의 참조 계약이 필요하다.
- 반차 예: 소정 480분, 검증실근로 300분, 외부 승인휴가 240분 → 추가 60분 가능성은 **검토 대상일 뿐, 자동 지급 확정이 아님**. 다중 구간/복수 휴가 신청도 계약 확장이 필요하다.
- 구형 `payroll-calculator`의 계산 함수·어댑터는 재사용 가능성만 검토한다. 새 Worktime 결과를 구형 `ordinary_hours/overtime_hours/night_hours` 등에 그대로 대응시키지 않는다.

### P1-2 PR #65 병합 완료 — 승인된 근로구간의 금액 **후보**

`overtime_candidates.py` / `overtime_preview.py`와 [가산수당 후보 계약](OVERTIME-CANDIDATES.md)을 추가한다. Worktime의 Δ 또는 예정 대비 실제 분수만으로 수당을 추정하지 않으며, 외부 검증 실제근로구간·승인구간·정책 분모와 반올림·기본급 포함 여부가 **모두 명시**되어야만 후보 금액을 계산한다. **P1-4 정책을 지정하지 않으면** 중복 구간은 종전대로 거절한다. 수당은 기존 단일 동적 급여대장의 후보 열에 보일 수 있지만 **모든 완료 플래그 False, 합계 공란, 미승인**은 유지한다.

**여전히 P1 잔여:** 실제 승인·검증 레코드의 출처/권한/서명 확인 Reader, 분할근무·복수 휴가 원장·사업장별 소정/법정 휴일 검증, 중복가산·통상임금 및 분모/정산 정책 확정, 시간대/익일근로 적용, 종료/미승인 근로 예외·정식 완료 판단. **이 기능 PR은 CI·사용자 서버 검증/병합 전까지 완료로 취급하지 않는다.**

### P1-3 PR #66 병합 완료 — 별도 출처 원장 레코드 대조

`evidence_reconciliation.py` / `evidence_preview.py`에서 P1-2의 근로검증/승인/분류/기본급 포함 참조를 [독립 원장 계약](EVIDENCE-RECONCILIATION.md)과 대조한다. 이 구현은 **레코드 내용 일치 검사이지 원장 진위 인증은 아니다**. 별도 외부 원장 Reader·결재권한/서명·스냅샷 완전성/최신성 검증, 중복가산 정책과 휴일·휴가 판정은 아직 필요하다. 출처 원본의 진위/승인 권한은 여전히 외부 검증이 필요하다.

### P1-4 PR #67 병합 완료 — 승인 구간의 중복가산 시간분할·기본 1배분 중복방지

`overtime_stacking.py`는 [명시적 중복 정책](OVERTIME-STACKING.md)에 기록된 **정확한 활성 분류 집합**만 허용한다. 직원별 시작·종료 분 경계에서 분류 중복을 확인하고, 같은 분의 기본급 포함 사실은 **전부 같은 값**이어야 한다. 미포함이면 정책에서 지정한 `unpaid_base_owner` 항목에 기준 1배분 임금을 한 번만 남기고 다른 항목에서는 중복 기준임금을 뺀다. 집합·정책 부재, 기본급 포함 여부 충돌, 동일 분류 중복은 차단. 수당 후보를 계산할 수 있다는 뜻이지 **한국 법령·취업규칙상 지급액 확인을 마쳤다는 의미는 아니다**. 실제 법률/회사 규칙 검증은 여전히 별도다.

**P1 남은 실제 적용 조건:** 독립 출처원장의 인증/권한/최신성·전체 승인 누락 검증, 실제 휴일 분류와 법정/회사 중복가산 기준, 통상임금의 기준분모 및 소정근로/휴게·휴가 연계, 중도 계약/입퇴사 정산·예외 처리. P2/P3와 별도이며 최종 급여 확정은 여전히 금지.

**레거시 철수는 목표이나 아직 하지 않았다.** 모든 신규 Tool과 Gearbox 인계·E2E/Golden 회귀를 완료한 후 구형 계산기 3종을 단계별 삭제한다. [철수 게이트](../LEGACY-RETIREMENT.md).

### P1-5b-1 PR #69 병합 완료 — 근태·휴가 정산 증빙 대조 및 기본급 후보 조정

`attendance_reconciliation.py`와 `attendance_preview.py`의 [근태·휴가 정산 계약](ATTENDANCE-SETTLEMENT.md). `worktime-result.xlsx`의 단일 일별 휴가 참조와 외부 승인 사건구간·금액을 명시적으로 대조한다. 회사가 선언한 결근 코드에서 대응 정산 근거가 없으면 중단하며, 지각·조퇴·근무분수 차이만으로 임의 차감하지 않는다. **유급휴가=명시적 기본급 감액 0**, 무급휴가/결근은 승인 원장이 제공한 **차감액(원)**만 기본급 후보에서 차감한다. P1-5a의 월중 계약변경 적용일도 검증하고 SHA-256으로 Worktime 자료를 고정한다. 한 날짜에 복수 휴가 사건은 기존 Worktime 단일 leave ID 계약상 차단한다. 초과근무 승인구간과 휴가 시간대는 **목록이 제출된 경우** 겹침만 검사하고 **금액은 합산하지 않는다**. 지급합계·실지급액 공란/미승인 상태 그대로. P1-5b-1 원장 자체의 권한·진위 검증은 여전히 외부 연결이 필요하다.

### P1-5b-2a 진행 — 재계약 전후 승인 초과근무 수당 결합

신규 `contract_scoped_overtime.py`와 [계약별 초과근무 합산 계약](CONTRACT-SCOPED-OVERTIME.md)은 P1-3 승인 원장 대조·P1-5a 재직/계약 배정·P1-5b-1 휴가/근태 검토를 통과한 뒤, 기존 P1-2 수당 계산기를 **계약별로 반복 호출**하고 후보 금액을 기존 동적 단일 `PAYROLL` 시트에 한 번만 합친다. 이 PR은 확정된 PTO/Worktime/Payroll Core·Output/Reader 코드를 변경하지 않는다. 계약경계 가로지르기, 직원/근거 불일치·휴가/근로 시간 충돌은 차단한다. `rollup_policy=ROUND_PER_CONTRACT_RULE_THEN_SUM`이라는 **명시적인 반올림·합산 기준**을 외부 정책으로 요구한다. 법정·사규 적정성·원장 진위는 미검증이며 합계/실지급액은 계속 공란. GitHub CI/사용자 서버 검증/PR 병합 전에는 완료로 표시하지 않는다.

**P1-5b-2b 잔여:** 복수 휴가 신청/상세시간 원장과 PTO Closing의 정합성, 고정수당 감액 정책, 신뢰된 근로/휴가 원장의 전체 모집단 검증, 법적 규정/통상임금 적용. 그다음 P2/P3.

**P1-5b-2 추가 과제:** 계약 변경에 따라 승인 초과근무 구간의 기준 임금·배율을 선택하는 방식, 승인근로와 휴가 복수구간의 정본 인계, PTO Closing 연차 잔여·사용 대조, 고정수당의 휴가 감액 정책·급여 항목 표시, 이벤트 원장 인증·누락검증. 이후 P2/P3.

### P1-5a PR #68 병합 완료 — 계약변경/입퇴사 일할 **후보**

`settlement_coverage.py` / `segmented_settlement.py`와 [P1-5a 계약](SEGMENTED-SETTLEMENT.md)에서 별도 **재직기간 증빙·계약 ID별 승인된 날짜 배정**을 먼저 확인한 다음, 명시된 `CALENDAR_DAYS` 정책의 기본급·고정수당 후보액을 계산한다. 재직 중 누락/중첩 기간은 0원 처리하지 않고 차단한다. 계약별 금액을 합산한 뒤 직원×항목×기간 단위로 원 단위 절사/반올림을 한다. 성과급은 기존 명시적 예산·배분율을 직원당 한 번 반영하며 자동 일할하지 않는다. 원장의 실제 진위와 정책의 법적 적정성은 아직 인증되지 않는다.

**P1-5b-2 잔여:** 근태·유급/무급휴가·결근의 원장/승인 증빙, 휴가 지급·공제 분모와 가산시간 중복 제외, 계약분할 일급 변화와 승인 초과근무 시간 구간의 재조정, 중도퇴사 정산 검증, P1-2~4 수당과 P1-5a 일할의 **최종 안전한 조합**. P1-5a는 독립 검토 대장 생성만 지원하고 **완결 급여/지급 승인 아님**. GitHub CI·사용자 서버 검증/PR 병합 전에는 완료로 표시하지 않는다.

## P2: 공제·과세 및 전액 지급/순지급 계산

- `DEDUCTION MAP`은 **근로자 부담율 매핑**이다. 현재 `resolve_deduction_mapping`은 요율만 조회하며 실제 공제액을 계산하지 않는다.
- 공시요율 버전/적용기간은 Excel, 계산식·산정기준/최저·최고/절사/대상/보험별 부담 주체는 검증된 정책 JSON 등으로 관리. 국민연금 기준소득월액·건강보험 보수월액·장기요양 건강보험료 기반·고용보험 산정대상 보수는 서로 다르다. **기본급×동일비율 일괄 적용 금지**. 근로소득세·지방소득세 등 그 외 공제항목도 아직 미구현.
- `payroll_taxability`는 **지급 시 과세/비과세**(예: 식대)에 관한 구분이다. 연말정산 기능이 아니다. 실제 법정 요건·한도·지급정책 확인 없이 임의로 `NON_TAXABLE`을 확정하지 않는다.
- 입사/퇴사 비정상 기간, 사용·미사용 휴가의 급여 반영, 근로자/외부 용역 구분, 직원별 `earnings_complete`/`deductions_complete` 생성 기준을 설계한다.
- 미확정이면 합계/실지급액을 공란으로 하고 `PARTIAL_REVIEW_ONLY` 보존. 완전한 수치도 `REVIEW_REQUIRED`이고 **송금·신고 승인 상태가 아니다**.

## P3: JSON Tool CLI + 합성 통합 E2E

1. PTO·Worktime과 동일하게 개인 JSON 설정에서 `payroll_period`, `input_root`, `output_root`, `run_id=auto`, `steps`, 파일 역할 참조를 읽고 고정 명령 한 줄로 실행. `--period/--input-dir/--output-dir`를 매번 수정시키지 않는다.
2. 논리적 Flow에서 선택한 단계만 실행하고, 기존 단계 결과를 사용하면 경로·계약·기간을 명시한다. **별도 `flow/` 폴더를 만들지 않는다.**
3. 합성 50명 × 일부 수당 지급, 연봉협상 중간 계약 변경, 전원 0원/음수 정산, 초과근무 중복·미승인, 비정기 성과급 100% 배분, 공제 미검증, 실행 재시도·중복파일 등을 테스트.
4. `output.py`와 `output_excel.py`에 전달되는 열 ID·표시명·금액·완료 플래그가 일치하는지 단일 `payroll-result.xlsx`를 실제 열어 검증. 정규화 결과/검토 결과를 별도 불필요한 중복 Excel로 남기지 않는다.

### 확정 Output

`payroll-result.xlsx` / `PAYROLL` 한 시트, 2단 그룹/항목 헤더. **50명 중 1명만 받는 항목도 그 열을 생성**, 미해당자는 공란, 전원 0원은 열 제거. 그룹은 직원정보 → 기본급 → 고정수당 → 초과근무수당 → 성과급 → 지급합계 → 공제 → 공제합계 → 실지급액 → 검토. `(group,item_id)`로 열 식별, 같은 수당 ID의 Level은 열 하나. 음수 소급 조정도 열 생성. 금액 검토 미완료 시 합계와 실지급액을 가짜 0으로 만들지 않음. [정본 계약](OUTPUT-CONTRACT.md).

## 병행 / 후순위 (현재 차단)

- **`agent-config` 작업 PAUSE**: 사용자가 다시 명시적으로 재개하기 전까지 Gearbox/Slack/Hermes 설정·문서·배포를 수정하지 않는다.
- Slack 파일 업로드 ACK 뒤 새 요청에도 무응답 보고는 **원인 미확인**. 업로드만 ACK하는 정상 설계와 후속 별도 메시지 무응답을 분리해 합성 재현 필요.
- 신규 PTO/Worktime/Payroll의 Gearbox Workflow 운영 연결 및 여러 첨부의 역할 매핑, 권한/TTL/원본 삭제/결과 Slack 회신은 별도 트랙. 현재 미연결.
- PTO Use Promotion, Worktime Closing, 다중 근무·복수 휴가 구간 지원도 계속 남아 있다. Payroll 본선과 섞어 구현하지 않는다.

## 작업 프로토콜

`seo-an/portfolio`에서 **별도 브랜치 → unittest → 일반 PR → 서버에서 PR 브랜치 직접 테스트 → 사용자 병합 → 서버 main 갱신·브랜치 정리**. 서버 push·Draft PR·worktree 사용 요구 금지. Tool 계약/버전 변경 시 Gearbox 기능/인프라 호환성 검증 필수.

```bash
# 컨테이너 검증 예시
sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -B -m unittest discover -s bhandara/tests -p 'test_*.py'
sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py
sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

**다음 과제:** P1-5b-2a 사용자 서버 검증/PR 병합 → P1-5b-2b 복수 휴가·PTO Closing·고정수당 감액 검증 → P2 보험·세금·정산 → P3 독립 CLI와 합성 E2E. `agent-config`는 PAUSE. 레거시 철수는 신규 3 Tool의 운영/회귀 전환 뒤에만 시행한다.
