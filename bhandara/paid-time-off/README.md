# Paid Time Off — 한국 연차유급휴가 Tool

> **현재 기준: 2026-11-18, PR #43 병합 후.** Entitlement·Deduction Quantity·Allocation·Expiry/Carryover·사용내역·Closing의 **독립 Python 계산 및 Excel 경로**가 구현되어 있습니다. 합성자료 CI와 사용자 서버 테스트를 통과했지만 실제 인사자료 운영 검증과 전체 Tool CLI/Gearbox/Slack 연결은 **아직 수행하지 않았습니다**.
>
> 기존 `pto-calculator` v0.2.1과 Gearbox 호환성 기준은 변경하지 않았습니다. 실제 운영 활성화보다 **PTO 전체 Flow 및 독립 Module 계약 정리**가 현 우선순위입니다.

## 1. 핵심 구조

| 계층 | 의미 | 책임 |
|---|---|---|
| Module | 독립적인 업무 계산·판정 단위 | entitlement, deduction-quantity, expiry-carryover, closing, 향후 use-promotion |
| Flow | 동일 Tool 내부에서 필요한 계산을 조합하는 **논리적 개념** | 물리 `flow/` 폴더를 만들지 않음 |
| Tool | 설정·입출력·호출 경계를 소유하는 단위 | `paid-time-off` |
| Workflow | 서로 다른 Tool 간 실행 순서 및 인계 | Gearbox·Ananda (운영 연결은 후속 작업) |

실제 책임 분리:

```text
확정 근태·인사자료 ──> Entitlement ─┐
외부 확정 대휴·발생근거 ────────────┼─> source_join ─┐
최초 Opening 또는 이전 Closing ───┘               │
승인 사용신청 ──> Deduction Quantity ────────────────┼─> Allocation
                                                       │
                                                       ├─> 단일 사용상세 / 사용요약
                                                       └─> Expiry & Carryover
                                                               │
                                                               └─> Closing
                                                                    ├─> 마감보고
                                                                    └─> 다음 분기 인계자료
```

- **Entitlement**는 확정된 월간·연간 근태 판정을 받아 해당 연도의 연차 발생량만 계산합니다. `eligibility`를 PTO 내부에서 다시 실행하지 않습니다.
- **Deduction Quantity**는 외부 승인된 휴가 시간 ÷ 1일 기준시간(기본 8시간)을 일수로 환산합니다. 승인·취소 결정을 직접 하지 않습니다.
- **Allocation**은 Tool 내부 `allocation.py`의 순수 함수입니다. `request_id`와 `grant_id`를 사용일에 맞춰 연결합니다. **독립 업무 Module이 아닙니다.**
- **Expiry & Carryover**는 확정 유효기간과 남은 발생분을 마감 경계에서 만료·이월로 판정합니다. **차감 배정은 하지 않습니다.**
- **Closing**은 이미 계산된 발생·사용·만료·이월을 월별 및 분기별로 **집계**합니다. 다른 Module의 계산을 복제하지 않습니다.
- **Use Promotion**은 아직 독립 Module을 구현하지 않았습니다. Closing의 3분기 외부 검토표 Y/N 수용은 사용촉진 법적 판단을 구현한 것이 아닙니다.

## 2. 기능 및 운영 상태

| 항목 | 현재 구현 | 아직 하지 않은 것 |
|---|---|---|
| Entitlement | `calculation.py`, `runner.run_entitlement()`, 발생요약/상세 Excel, 안정적 `grant_id`·반영발생일수 | 실제 운영 활성화 |
| Deduction Quantity | `calculation.py`, `runner.run_deduction_quantity()`, 차감요약/상세 Excel, 숨김 정확한 분자·분모 | 직원별 1일 기준시간 자동 정책 연결 |
| Allocation | `allocation.py`, 발생·사용 신청별 배정, 음수 부족분, 미래 예약 | 외부 자동 상계 API(만들지 않기로 결정) |
| 발생자료 결합 | `source_join.py`, 당년 Entitlement·외부 대휴·Closing 잔여를 ID로 결합 | 실자료 연속운영 검증 |
| 사용내역 | `runner_usage.py`, `usage-ledger-result.xlsx` | 공개 Tool CLI 연결 |
| Expiry & Carryover | `expiry-carryover/calculation.py`, 만료·이월·수당 검토 표시 | 권리·현금 지급 법적 판정 |
| Closing | `closing/calculation.py` + `runner_closing.py`, `closing-result.xlsx` | 자동 마감 승인 및 월별/분기별 실제 운영 |
| Use Promotion | 독립 Module 미구현 | 대상·기한·통지·증빙·결과 계약 협의 |
| Tool 운영 | 독립 라이브러리 호출 경로만 | 새 `module.json`, `user_settings.py`, `bhandara/run.py` 공개 명령, Gearbox/Slack 연동 |

## 3. 입력 자료와 원본의 소유권

기존 공유 입력 루트는 `bhandara/data/input/`이며 **실제 직원자료는 Git 체크아웃 밖 비공개 경로를 명시**합니다. Module마다 물리적인 입력/출력 폴더를 별도 생성하지 않습니다.

| 입력 파일 | 시트 | 주된 필드 |
|---|---|---|
| `common/employee.xlsx` | `재직자`, `퇴사자` | `employee_id`, `hire_date`, 퇴사자의 `termination_date`. Closing은 `name`도 확인 |
| `paid-time-off/attendance-result.xlsx` | `근태결과` | `employee_id, period_start, period_end, check_type, attendance_flag` |
| `paid-time-off/proration.xlsx` | `비례자료` | `employee_id, period_start, period_end, method, numerator, denominator`. 최초 회계연도 비례 계산 시 |
| `paid-time-off/approved-leave.xlsx` | `승인휴가` | `request_id, employee_id, leave_date, leave_type, duration_hours` |
| `grant-references.xlsx` | `발생근거` | `grant_id, employee_id, grant_date, valid_from, expires_on, source_ref` |
| 같은 발생근거 파일 | `대휴발생`(선택) | `source_ref, 반영발생일수`. 대휴 수량은 외부 확정 |
| 최초 Opening/이전 Closing | `정책정보`, `인계자료`, `미상계부족`(선택) | 확정 참조 ID, 발생 건별 기초잔여/유효기간, 미상계 신청별 부족분 |

근태 플래그는 월간 `개근/미개근/판정 안됨`, 연간 `80% 충족/80% 미충족/판정 안됨`입니다. Entitlement는 해당 연도 1월 1일부터 `as_of_date`까지의 신규 발생량만 계산하며 이전 연도 발생량을 중복 더하지 않습니다.

## 4. 계산·결과 연결의 핵심 정책

### 4.1 발생·반올림·차감 정밀도

- Entitlement의 발생 건마다 `grant_id`를 만들고 원본 `계산결과`와 최종 `반영발생일수`를 **같은 발생상세 행**에 보관합니다.
- 발생량은 `Fraction`으로 계산하고 직원별 합계에서만 최종 **1회 반올림**(정수 또는 소수 첫째 자리). 반영할 총량을 발생 건에 배분하며, 건별 독립 반올림은 하지 않습니다.
- Deduction Quantity도 `Fraction`으로 계산하되 **반올림하지 않습니다**. 무한소수는 사람에게 보여줄 때만 소수 7자리 절사합니다. 인계 Excel에서는 정확한 분자·분모 숨김 열을 사용합니다.
- 유효기간 `valid_from / expires_on`은 외부 확정값이며 없으면 임의 산정하지 않습니다.
- 동일 직원·휴가 유형의 정상 발생 건 중 **사용일 → 빠른 만료일 → 빠른 발생일 → `grant_id`** 순으로 차감합니다. 연차와 대휴는 교차 차감하지 않습니다.
- 부족분은 신청 ID에 귀속시키고 직원·휴가 유형별 **실제 음수 잔여**로 유지합니다. 미래 예약은 이미 사용한 일수와 구분합니다.
- 취소·변경된 신청은 최신 외부 유효 승인 목록으로 전체 재배정합니다. 과거 확정 Closing 자체를 수정해야 하는 정정은 별도 외부 검증이 필요합니다.

### 4.2 상계 — 외부 확정 두 증빙자료를 수동 대조

외부 담당자가 상계를 **확정하여 작업을 지시한 경우에만** 검토합니다. **발생연차 근거 시트와 기존 미상계 부족분 증빙 시트, 두 시트가 모두 있어야** 대조할 수 있습니다. 어느 하나라도 없으면 “필수 증빙자료 부족으로 상계 처리 불가”로 처리합니다. 두 시트의 직원·발생 ID·신청 ID·수량을 대조해 외부 확정 범위에서 반영하며 자동 상계하거나 별도 상계 API를 만들지 않습니다. 합산 순잔여와 실제 발생분 상계 이력은 구분해야 합니다.

### 4.3 만료·이월 및 수당

회계기간이 끝나도 유효한 발생분은 같은 `grant_id`로 이월합니다. 유효기간이 끝난 미사용분은 만료로 분류하고 **미사용수당 검토 대상 여부만** 표시합니다. 실제 수당 청구권·사용촉진 면책·지급 승인 여부는 외부 법적·정책 검토 대상입니다.

## 5. 산출물과 시트

| 결과 파일 | 가시 시트 | 기계 인계/추가 시트 |
|---|---|---|
| `entitlement-result.xlsx` | 발생요약, 발생상세, 정책정보 | 발생상세에 `grant_id`·반영발생일수 |
| `deduction-quantity-result.xlsx` | 차감요약, 차감상세, 정책정보 | 차감상세 숨김 정확한 분자/분모 열 |
| `usage-ledger-result.xlsx` | 사용요약, 사용상세, 만료이월(Closing ID 지정 시), 검토사항(오류 시), 정책정보 | 숨김 `_발생자료` 스냅샷 |
| `closing-result.xlsx` | **마감보고**, 검토사항(오류 시), 정책정보 | 숨김 `_수량정본`, `인계자료`, `미상계부족` |

**사용요약**은 직원별 `employee_id, 발생일수, 사용일수, 잔여일수` 네 열이며 휴가 유형으로 행을 나누지 않습니다. **사용상세**에는 `employee_id, leave_type, grant_id, grant_date, 반영발생일수, valid_from, expires_on, source_ref, request_id, leave_date, 차감일수, 처리구분, 사유`를 연결합니다. 사용상세는 차감 배정의 정본이며 별도 중복 원장을 만들지 않습니다.

### 5.1 Closing: 첨부 예제 확정 A~V 열

| 열 | 헤더 | 정의 |
|---|---|---|
| A~B | `employee_id`, `name` | 직원 ID·이름 |
| C | 발생연차일수 | 해당 연도 신규 발생 연차 누계 |
| D | 기초이월잔여일수 | **연초 인계 잔여로 고정**. 연초 미상계 부족분 포함 |
| E | 대휴발생일수 | 해당 연도 신규 발생 대휴 누계 |
| F | 총확보휴가일수 | C + D + E |
| G | 미사용만료일수 | 해당 연도 누적 만료 수량 |
| H~S | 1월~12월 | 월별 사용량. 마감 후 미래 월은 **공란**, 마감한 사용 0인 월은 0 |
| T | 누적사용일수 | 연초부터 해당 분기 말까지의 사용량 |
| U | 마감잔여일수 | F - G - T. 음수는 실제 숫자로 저장하고 Excel에서는 괄호 표시 가능 |
| V | 마감상태 | 정상 / 초과사용 / 사용촉진 검토 / 자료확인 필요 |

`Closing-1.4-2026`(3월 31일), `Closing-2.4-2026`(6월 30일), `Closing-3.4-2026`(9월 30일), `Closing-4.4-2026`(12월 31일). **D열에 직전 분기 잔여를 대신 넣지 않습니다.** Q2~Q4에서는 지난 분기 누적값에 이번 분기 증감만 더합니다. 이전 Closing을 인계할 때는 확정된 `Closing-*.4-YYYY` ID를 참조하고 발생 건별 **잔여 0 ID까지** 유지합니다. 최초 기초인계는 외부 확정 Opening을 사용합니다.

V열의 계산 상태는 `자료확인 필요 > 초과사용 > 사용촉진 검토 > 정상` 순서입니다. 3분기 사용촉진 검토는 외부 `검토결과` 시트의 `employee_id, review_required`(Y/N)를 받는 표기 경계일 뿐 `use-promotion`을 대신하지 않습니다. 누락된 확정 자료는 `자료확인 필요`로 남깁니다.

Closing Excel은 최초 `정책정보.확정여부=미확정`으로 산출됩니다. 외부 확인·승인을 거쳐 확정해야 다음 분기 입력으로 사용할 수 있습니다. 정확한 사용량 인계·재생성 조건은 `closing/README.md` 참조.

## 6. 호출·테스트 경계

현재 독립 호출 가능한 함수:
- `runner.run_entitlement()` 및 `runner.run_deduction_quantity()`.
- `runner_usage.run_usage_ledger()`: **기존 결과 파일**과 확정 원본을 받아 결합합니다. 다른 Module을 자동 실행하지 않습니다.
- `runner_closing.run_closing()`: 이미 산출된 Usage Excel, 직원명부, 필요 시 직전 확정 Closing 및 외부 3분기 사용촉진 검토 자료를 받습니다.

```bash
python3 -m unittest bhandara.tests.test_paid_time_off_entitlement_excel -v
python3 -m unittest bhandara.tests.test_paid_time_off_deduction_excel -v
python3 -m unittest bhandara.tests.test_paid_time_off_allocation_expiry -v
python3 -m unittest bhandara.tests.test_paid_time_off_usage_excel -v
python3 -m unittest bhandara.tests.test_paid_time_off_closing_excel -v
python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
```

기존 Gearbox 기능·인프라 호환성 테스트는 각각 `python3 gearbox/_tests/run.py`, `python3 gearbox/_tests/core_run.py`입니다. 신규 Tool 버전 변경이나 운영 연결 때 **반드시** 함께 검증합니다. 실제 HR 자료로 아직 실운영 검증하지 않았고, 사용자의 현재 우선순위는 **선택적 Flow와 책임·입출력 계약 설계**입니다.

## 7. 다음 설계 과제

1. **PTO 전체 선택적 Flow**: 어떤 입력이 있으면 어떤 단계를 연결하는지, 단독 Module 호출과 Tool 결과를 어떻게 구분할지. 논리적 Flow만 정의합니다.
2. **Use Promotion**: 법정/사내 정책 및 대상·통지·증빙·결과 인계 계약 협의. Closing의 외부 Y/N 상태와 분리합니다.
3. **연도·분기 마감 연결 점검**: 확정 Closing→다음 기간 사용내역, 1월 Opening, 변경·취소/미상계 부족분 연속성. 실자료 대신 먼저 합성 시나리오·정합성 검토.
4. **공개 Tool 경계**: `module.json`/Module별 `user_settings.py`, 단독 실행 CLI, RUNBOOK, 입력·출력 정본 정의.
5. **Gearbox 연결**: 현재 v2 Module별 입출력 Adapter와 새 v3 Tool 단위 계약 차이를 별도 `agent-config` 브랜치에서 검토. 운영 승인은 마지막 단계.

## 8. 변경 이력

- PR #36 Common, #37 PTO 구조, #38 Entitlement, #39 Deduction Quantity, #40 문서 정비.
- PR #41 Allocation과 Expiry 책임 분리, #42 발생 ID·원본 결합·사용내역 Excel, **#43 Closing 분기 마감보고서**까지 병합.
- PR #43: GitHub Actions 전체 359 tests / OK, 공유 Excel CI PASS. 사용자 서버에서도 기능·회귀·Gearbox 호환성 테스트 통과 후 병합 확인.
- 실제 운영 도입·새 Tool 활성화·실자료 실행은 **아직 하지 않았습니다**.
