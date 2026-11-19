# Bhandara 개발 현황 — 2026-11-19 (Payroll PR #60 병합 이후)

> **보관된 이력 문서:** 아래 체크리스트는 **Payroll PR #60 당시의 스냅샷**으로, 최신 완료 여부가 아닙니다. 이후 #62(Reader), #63(기간·표시명 Adapter), #64(Worktime 사실 검토), #65(가산수당 후보)가 병합됐습니다. [최신 Payroll 작업 체크리스트](payroll/NEXT-STEPS.md) · [레거시 철수 계획](LEGACY-RETIREMENT.md)을 우선 확인하세요.


> **다음 구현 과제 중심의 최신 상태.** 기존 문서의 “Payroll 설계 전”, “단일 급여대장 미구현” 표현은 더 이상 사실이 아니다. Portfolio PR #58(문서), #59(신규 Payroll 계산 코어), #60(동적 Output)이 모두 병합됐다. 사용자 보고상 #60 서버 전체 검증도 통과했다. 다만 신규 Payroll Tool은 아직 **파일 입력 → 금액 산정 → 대장 출력** 일괄 실행이 불가능하다.

## 1. 구현된 기능 — 간단 요약

| 계층 / Tool | 완료된 범위 | 중요한 경계 |
|---|---|---|
| Common | 기존 ID/외부인력 + PERSON/DEPARTMENT/AREA 업체별 매핑, 합성 샘플 도구 | 원본과 실제 ID를 자동 추론하지 않음 |
| Paid Time Off | Entitlement, Deduction Quantity, Usage Ledger, Closing, 내부 Allocation·Expiry/Carryover, Excel·JSON 선택 Flow/CLI | Use Promotion·실자료 E2E·Gearbox 연결 미완료 |
| Worktime | Schedule, Attendance Verification, Worktime Compliance, 스케줄 ID 매핑, `WORKTIME` 10컬럼 사실 Excel, JSON 선택 Flow/CLI | 지급시간/급여 계산 없음. Closing·복수 근무/신청·Gearbox 연결 미완료 |
| **새 Payroll 코어 (#59)** | 계약 ANNUAL/MONTHLY/WEEKLY, BASE/TOTAL, `contract_id`별 고정수당 ID/Level, `deduction_code`별 보험 **비율** 조회, 팀/프로젝트 성과급 예산 배분, 검토용 부분합계 | Excel을 자동 읽지 않음; 초과수당/보험 공제액/순지급은 계산하지 않음 |
| **새 Payroll Output (#60)** | `payroll-result.xlsx` / `PAYROLL` 1시트, 2단 헤더, 1명에게만 있는 수당도 열 생성, 미해당자 공란, 합계·검토 플래그 | **계산된 항목을 입력받아 보여줄 뿐, 코어와 연결하는 Adapter는 아직 없음** |
| 구형 Calculator 3종 | 호환용 `pto-calculator`, `worktime-calculator`, `payroll-calculator` 유지 | 신규 Tool에 입력/출력 계약을 자동 치환하지 않음 |
| Gearbox/Slack | 기존 운영 경로·임시 문서 캐시 정책 | 신규 Tool 운영 미연결; Slack 업로드 ACK 이후 **새 검토 요청 무응답 원인 미확인**. `agent-config` **PAUSE** |

계층 원칙: **Module → Flow(물리 폴더가 아닌 논리 조합) → Tool → Workflow(Gearbox)**. Gearbox는 Tool 간 연결·인증·권한·보관·상태·Slack 응답을 소유한다.

## 2. 다음 본선 — Payroll의 남은 문제

**세부 체크리스트/순서의 정본: [Payroll NEXT-STEPS](payroll/NEXT-STEPS.md).**

### P0 — 입력과 기존 계산 함수/Output 연결

- [ ] [`input-files.json`](payroll/input-files.json)의 **고정된 Excel 7개**를 엄격히 읽는 Reader 구현, 시트/헤더/수식/중복 ID/선행 0/정수 금액/기간 검증.
- [ ] 연봉협상·재계약 등 **기간 중 계약 변경**을 어떻게 분할 적용할지 정하고 한 기간 직원별 복수 계약의 선택/합산을 검증. 현재 `core.resolve_contract_pay`는 대상 계약이 **직원별 정확히 1개 선택됐다는 전제**이며 기간 문자열만 보존한다.
- [ ] 고정수당 `allowance_id + level`→지급금액, `contract_id`→직원 ID, 공제 `deduction_code`→보험별 비율, 성과급 `bonus_id`→팀/프로젝트 예산·직원 배분율을 통합 인계.
- [ ] **표시명 누락 해결**: 현재 수당/성과급 Mapping에 `item_id`별 사람에게 보일 `label`의 정본이 명시돼 있지 않다. Output은 `item_id/label/amount`가 반드시 필요. ID를 표시명으로 임의 대체 금지.
- [ ] 계산 코어→`build_payroll_register` 입력을 잇는 Adapter 구현. 전체 지급·공제 완료 여부는 명시적 외부 검증 근거가 있을 때만 true.

### P1 — Worktime 기반 초과근무·연차·일할

- [ ] `worktime-result.xlsx`의 `scheduled_min`, `actual_min`, 출근/퇴근 Δ, schedule ID/승인휴가 ID를 해석하고 **실제 인정 추가근로**가 따로 승인·검증됐는지 대조.
- [ ] `overtime-rules.xlsx`에 적힌 기준을 실제 근로 구간/승인 증빙에 적용. 조기·지연·연장·야간·휴일·잔업의 배율, 일급 기반 시간 환산, 중복 가산, 교차일자/휴무 경계 정의.
- [ ] `actual_min + 출퇴근Δ` 단순 합산 금지. Worktime 일별 4개 시간 필드만으로 야간/휴일 승인구간을 확정할 수 없음.
- [ ] 입사·퇴사·유급/무급 휴가의 급여 반영, 결근/누락/0분과 null의 구분, 다중 휴가 신청/분할근무의 데이터 계약.

### P2 — 급여 지급 시 비과세 및 실제 공제액

- [ ] `DEDUCTION MAP`의 4개 공제율 **조회만 구현**된 상태를 넘어 각 보험별 검증된 부과 기준액·보험 정책/상하한/절사/유효기간을 사용하여 계산. **기본급에 모든 비율을 그대로 곱하지 않는다.**
- [ ] 국민연금·건보·장기요양·고용보험 적용조건과 실제 가입·고지/산정기준, 그 외 근로소득세·지방소득세 등 공제항목의 별도 정책/데이터 계약.
- [ ] `payroll_taxability`는 **급여 지급 시점**의 과세/비과세 후보(예: 식대). 연말정산 기능과 다르며 법적 적용 한도·요건 검증 전 자동 확정 금지.
- [ ] 부분 계산/검토보류 직원의 지급·공제합계/실지급액은 미확정으로 보존. `REVIEW_REQUIRED`는 지급 승인 아님.

### P3 — 독립 JSON CLI / 합성 전체 E2E

- [ ] PTO/Worktime과 같은 JSON 기반 선택적 `steps`, 기간, 입력·출력 루트, `run_id=auto`, 명시 결과 파일 인계; 사용자에게 옵션 잔뜩 요구하지 않음.
- [ ] 50명 중 1명의 자격수당/2명 성과급, 연봉협상 날짜 중간 변경, 0원 전체항목 제거/미해당 공란, 음수 정산, 승인 미확인 근로시간, 보험 공제 미확정, 중복/누락 등을 테스트.
- [ ] Excel Reader → 코어 → 추가수당/공제 → Output Writer로 **하나의 검토용 `payroll-result.xlsx`** 생성 확인. 아직 별도 최종 급여대장/회계 장부를 자동 확정하지 않는다.

### 입력 샘플의 실제 저장 상태

- 규격 파일 [`payroll/input-files.json`](payroll/input-files.json)에 **7개 개별 파일명** 정본 확정. 사용자가 다운로드할 ZIP 샘플은 별도 제공됐다.
- GitHub `main`의 `bhandara/examples/sample/input/payroll/pay-contract.xlsx`는 조회됨. 나머지 **6개 신규 Excel은 GitHub main에서 2026-11-19 조회 시 미확인**. 기존 `pay-contract.xlsx`가 신규 `CONTRACTS` 한 시트/12열 스키마와 일치하는지도 검증 전이다.
- 기존 공개 샘플 전체를 `refresh.py --apply`로 사용자 허가 없이 교체하지 않음. 샘플 경로와 실제 실행 입력 `input_root/payroll/`은 별개.

## 3. 병행 백로그 — 현재 `agent-config` 수정은 보류

- **Slack 파일 업로드 ACK 후 후속 새 요청에도 무응답**: 현재 사용자 관찰만 있으며 재현·원인 규명이 필요. 업로드 ACK 하나만 하는 정상 설계와 **별도의 새 메시지에도 무응답**을 구분해 합성 재현. 보관 정책·IAM·인바운드 이벤트·thread routing·outbound 단계별 진단이 필요하다.
- **Gearbox 운영 연결**: 신규 PTO/Worktime/Payroll Tool과 기존 Adapter 간 JSON/Excel 인계·버전 검증, 여러 입력파일 역할 지정, 파일 인증/권한/임시 저장 TTL/S3 제외/Slack 회신/에러 처리. 현재 미연결.
- 2026-11-16 문서상 일반 업로드 임시캐시 24시간 / 명시 검토로 선택 시 최초 저장부터 3시간의 운영 계약은 **현재 재확인 없이 바꾸지 않는다**. Drive 장기 저장은 별도 사용자 명시 승인.
- `seo-an/agent-config` 문서 PR [#210](https://github.com/seo-an/agent-config/pull/210)은 2026-11-19 확인 시 **OPEN**. 사용자 재개 지시 전 편집·병합·배포 금지.
- PTO Use Promotion, Worktime Closing, 복수 근무/휴가 신청 확장도 미완료 후순위.

## 4. 개발·테스트 순서

1. Portfolio에서 **새 브랜치**를 만들고 범위 한정 구현; Python **`unittest`** 사용.
2. CI 확인 후 **일반 PR**. 서버에서 PR 브랜치를 직접 가져와 검증(Draft/별도 worktree 금지, 서버 push 요구 금지).
3. 서버: `python3 -m unittest discover -s bhandara/tests -p 'test_*.py'`; `python3 gearbox/_tests/run.py`; `python3 gearbox/_tests/core_run.py` — Hermes 컨테이너 `/opt/hermes/.venv/bin/python` 사용. Tool 계약/버전 변경 시 Gearbox 호환성 필수.
4. 사용자 병합 → 서버 main 재동기화 및 브랜치 정리. **`agent-config`는 PAUSE**, 실제 직원·계약·급여 원본/승인 없이 운영 테스트·배포·신고/송금 금지.
5. AWS 비밀값의 정본은 Parameter Store. SSM 쓰기·S3 백업 읽기 별도 IAM이 필요하면 사전 승인 요청.

## 5. 다음 대화에서 읽을 정본

- [Payroll NEXT-STEPS](payroll/NEXT-STEPS.md) — **최우선**, 아직 하지 않은 일/의존성.
- [Payroll 코어·입력 설명](payroll/README.md), [7개 파일 계약](payroll/input-files.json), [동적 Output 정본](payroll/OUTPUT-CONTRACT.md).
- [Worktime 단일 결과 계약](worktime/OUTPUT-CONTRACT.md), [Worktime JSON CLI](worktime/TOOL-CLI.md), [PTO JSON CLI](paid-time-off/TOOL-CLI.md).
- [기존 Payroll Calculator](payroll-calculator/README.md) — 재사용 코드는 참고하되 새 Tool의 계약을 자동으로 바꾸지 않는다.

**다음 구현 시작 문장:** “Payroll의 계산 코어와 동적 Output은 병합 완료다. 7개 독립 Excel Reader, 기간 중 계약 선택, ID·표시명/완료 플래그 Adapter부터 연결하자. Worktime 추가수당·실제 공제·Payroll JSON CLI는 다음 순서다. `agent-config`는 PAUSE.”
