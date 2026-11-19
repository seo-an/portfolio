# Paid Time Off — v3 아키텍처 및 모듈 인계 계약

**기준: 2026-11-19, PR #56 병합 후 / 독립 Excel 및 JSON 선택적 Tool CLI 구현 완료.** 이 문서는 현재 병합된 코드를 기준으로 작성했습니다. PR #37~#43 초기 설계안 중 본문과 충돌하는 설명은 폐기합니다. 프로젝트 전체 구조는 `Module → Flow(논리적) → Tool → Workflow`입니다.

## 1. 확정된 구조

| 계층 | 책임 | 금지 |
|---|---|---|
| Module | 하나의 도메인 계산·검증 단위, 독립 호출 | 다른 업무 Module을 내부에서 필수 자동 실행 |
| Flow | 같은 Tool 안에서 필요한 Module/계산을 선택적으로 연결하는 **논리적 개념** | 물리 `flow/` 폴더, 고정된 단일 실행 순서 강제 |
| Tool | `paid-time-off` 단독 실행·설정·입출력 계약 | 다른 Tool을 임의 호출 |
| Workflow | Gearbox/Ananda가 Tool 간 순서·검증·인계 | 호출·권한·정책을 Tool 내부에 숨기기 |

Module은 `entitlement`, `deduction-quantity`, `expiry-carryover`, `closing`, 향후 `use-promotion`입니다. `eligibility`의 기존 순수 API 초안은 남아 있으나 **PTO 계산에서 재호출하지 않습니다**. `allocation.py`와 `source_join.py`는 **Tool 내부 계산/결합 유틸리티**이며 별도 Module이 아닙니다.

Bhandara 저장소는 공통 `bhandara/data/input/` 체계를 유지하고, Tool 또는 Module마다 중복 입력·출력 폴더를 만들지 않습니다. 실제 HR 개인자료는 Git 체크아웃 밖 안전한 경로에서만 읽습니다.

## 2. 구현 상태와 미구현 사항

| 위치 | 코드/출력 경계 | 구현 상태 |
|---|---|---|
| `entitlement/calculation.py` | 입사일 기준, 1년 미만 월별, 최초 회계 비례/후속 정기 연차 | 계산 완료 |
| `runner.py::run_entitlement` | 발생요약·발생상세·정책정보 Excel, `grant_id`·반영발생일수 | 독립 Excel 완료 |
| `deduction-quantity/calculation.py` | 승인 사용시간 → `Fraction` 일수 | 계산 완료 |
| `runner.py::run_deduction_quantity` | 차감요약·차감상세·정책정보 Excel, 숨김 정확 분수 | 독립 Excel 완료 |
| `source_join.py` | Entitlement·Closing/Opening·외부 대휴 결합 | 순수 결합 완료 |
| `allocation.py` | 발생 ID와 요청 ID 사용일별 배정, 예약/부족 | Tool 내부 계산 완료 |
| `expiry-carryover/calculation.py` | 만료/이월 분류, 법적 지급 자동판정 제외 | 순수 계산 완료 |
| `runner_usage.py` | `usage-ledger-result.xlsx`, 단일 사용상세·만료이월 | Tool 내부 Excel 결합 경로 완료 |
| `closing/calculation.py` | 분기별 누적 사용·발생/만료·상태 집계 | 순수 계산 완료 |
| `runner_closing.py` | `closing-result.xlsx`, 다음 기간 인계 | 독립 Excel 완료 |
| `use-promotion` | 대상·기한·통지·증빙·결과 | **미구현** |
| 신규 `paid-time-off` JSON Tool CLI | `tool_cli.py`, `config.example.json`, `run.py`의 명시적 선택 단계·경로 | **합성·서버 테스트 후 병합 완료** |
| Gearbox/Slack 운영 연결 | 원본 수신, 권한·기한, 다중 Tool Workflow | **미연결** |

**완료라는 말은 합성자료·독립 Python 경로의 완료**를 의미합니다. 실제 직원 원본 처리·승인·배포·운영 E2E를 의미하지 않습니다. 기존 `pto-calculator` v0.2.1 및 Gearbox 호환성 게이트를 건드리지 않았습니다.

## 3. 데이터 생성·보관의 정본

### 3.1 권리(Entitlement)

- 연차 발생의 법정 요건을 내부에서 다시 판단하는 대신 외부 근태 결과의 판정을 사용합니다.
- `as_of_date`의 연도 1월 1일부터 기준일까지 발생한 건만 산출합니다. 이전 연도 기록은 근태 판정의 근거이지 중복 발생 금액이 아닙니다.
- 근속 가산은 실제 입사일 기준 완료 근속연수를 사용합니다. 회계연도 첫 경계는 비례, 후속은 전년도 출근율 결과를 반영하는 정기 부여입니다.
- 원본 `계산결과`와 최종 `반영발생일수`는 **같은 발생상세 행**입니다. `grant_id`는 발생 사건의 본질적 식별정보에서 생성해 행 위치·실행 ID·수량 정정에 의존하지 않습니다.
- 수량 계산은 `Fraction`, 합계에서 마지막 한 번만 반올림합니다. 발생 건별 반올림은 금지하고 최종 합계를 발생 건에 배분합니다.
- 미판정 직원의 발생량을 임의 부분합으로 확정하지 않습니다.

### 3.2 사용(Deduction Quantity → Allocation)

- 외부 신청·승인·반려·취소 시스템이 **현재 유효한 승인 목록**을 제공합니다. Deduction은 `duration_hours / standard_daily_hours`(기본 8h)를 계산합니다.
- 오류 행은 계산 제외·사유 기록; 동일 `request_id + leave_date` 중복은 둘 다 제외합니다.
- 결과 사람용 표기는 무한소수 7자리 절사. 후속 Allocation은 정확한 숨김 분자·분모를 사용합니다.
- Allocation 정렬은 **사용일 → 가장 빠른 만료일 → 발생일 → grant_id**. `valid_from ≤ leave_date ≤ expires_on`을 만족해야 합니다.
- 하나의 신청이 여러 발생 건에 배정되면 `사용상세`에 동일 request ID가 반복됩니다. 별도 중복 차감 배정 원장은 만들지 않습니다.
- 연차와 대휴는 교차 차감할 수 없으며, 부족분은 신청별 미배정 행과 직원·휴가 유형별 **음수 잔여**에 반영합니다.
- 미래 승인 신청은 실제 사용일과 구분해 예약합니다. 현재 사용 완료 집계와 중복하지 않습니다.
- 승인 취소/변경은 현재 유효 승인 목록으로 **전체 재배정**합니다. 이미 확정된 과거 Closing 입력 자체의 변경은 외부 정정·재승인 뒤 다룹니다.

### 3.3 만료·이월(Expiry & Carryover)

- 각 권리의 `valid_from`, `expires_on`은 **외부 확정값**입니다. 만료일을 자동 연장·추정하지 않습니다.
- 마감일 현재 사용하지 않은 잔여 중 이미 만료된 부분은 만료, 이후까지 유효한 부분은 이월입니다. 이월로 별도 신규 `grant_id`를 발행하지 않습니다.
- 권리 사용기한 만료는 자동으로 수당 청구권·지급 의무를 확정하지 않습니다. 연차는 법적 미사용수당 **검토 대상**으로만 표시하고 사용촉진·대휴 정책·지급 판단은 별도 자료가 필요합니다.
- 권리의 유효 시작일·종료일 오류와 중복 ID는 해당 직원·유형 계산을 검토 대상으로 남깁니다.

### 3.4 상계 — 수동 증빙 대조

**상계 자동 API는 구현하거나 계획하지 않습니다.** 외부 담당자의 확정 상계 지시가 존재하더라도 **발생연차 근거 시트와 미상계 부족 증빙 시트가 둘 다 있어야** 실제 상계 검토를 시작합니다. 하나라도 없으면 “필수 증빙자료 부족으로 상계 처리 불가”로 종료합니다. 두 증빙의 직원/원인 신청 ID/상계 대상 발생 ID/수량을 대조해야 하며 별도 자동발생·직원 간/휴가유형 간 상계는 금지합니다.

## 4. Excel 입력·출력 관계

### 4.1 입력

| 출처 | 입력·필드 |
|---|---|
| 공통 인사명부 | `common/employee.xlsx`, 재직자/퇴사자, `employee_id, hire_date`, 퇴사일·`name`(Closing) |
| 근태 결과 | `attendance-result.xlsx` 근태결과 시트, 월간/연간 `attendance_flag` |
| 최초 회계연도 비례 | `proration.xlsx` 비례자료, 산정근거 분자·분모 |
| 승인 사용 | `approved-leave.xlsx` 승인휴가, `request_id, employee_id, leave_date, leave_type, duration_hours` |
| 유효기간·대휴 발생 | `grant-references.xlsx` 발생근거 + 대휴발생(`source_ref, 반영발생일수`) |
| 과거 잔여 | 최초 `Opening-*.4-YYYY` 또는 확정 `Closing-*.4-YYYY`; 발생 건별 0 잔여 ID·미상계 부족분까지 참조 |

Excel 결과별 계약:
- `entitlement-result.xlsx`: `발생요약`/`발생상세`/`정책정보`.
- `deduction-quantity-result.xlsx`: `차감요약`/`차감상세`/`정책정보`.
- `usage-ledger-result.xlsx`: `사용요약` 직원당 1행(`employee_id, 발생일수, 사용일수, 잔여일수`), `사용상세`에 `request_id + grant_id`와 발생/차감 출처를 한 행에 확장; 만료이월·검토사항(해당 시)·정책정보. 숨김 `_발생자료`는 정확한 정본 인계용.
- `closing-result.xlsx`: 가시 `마감보고` + 숨김 `_수량정본`, `인계자료`, `미상계부족` + 필요 시 검토사항 + 마지막 정책정보.

### 4.2 Closing A~V 확정 양식

| 열 | 헤더 | 집계 원칙 |
|---|---|---|
| A~B | employee_id, name | 직원별 1행 |
| C | 발생연차일수 | 해당 연도 신규 연차 누계 |
| D | 기초이월잔여일수 | **연초 확정 인계 잔여 고정**; 미상계 기초 부족분 포함 |
| E | 대휴발생일수 | 해당 연도 신규 대휴 누계 |
| F | 총확보휴가일수 | C + D + E |
| G | 미사용만료일수 | 해당 연도 미사용 만료 누계 |
| H~S | 1~12월 | 이미 마감한 월은 사용량(없으면 0), 미도래 월은 **공란** |
| T | 누적사용일수 | 연초~마감월 실제 사용량 |
| U | 마감잔여일수 | F − G − T; 실제 음수 허용 |
| V | 마감상태 | 정상, 초과사용, 사용촉진 검토, 자료확인 필요 |

ID는 `Closing-1.4-2026`(3/31), `Closing-2.4-2026`(6/30), `Closing-3.4-2026`(9/30), `Closing-4.4-2026`(12/31). `D`는 전 분기 `U`로 바꾸지 않습니다. 2분기 이후는 이전 분기의 **누적값**을 인계하고 **새 분기 증감**만 반영합니다.

- 상태 우선순위: `자료확인 필요 > 초과사용 > 사용촉진 검토 > 정상`.
- Q3 `사용촉진 검토`는 외부 `검토결과`에서 `review_required=Y`인 경우에만 표시합니다. 외부 검토가 없거나 직원별 누락 시 `자료확인 필요`. 이것이 Use Promotion Module 구현이나 법적 유효성의 인정은 아닙니다.
- Closing 산출물은 처음에 `정책정보.확정여부=미확정`. 사용자가 외부에서 내용을 검토·승인한 뒤에만 다음 분기 참조 자료로 취급할 수 있습니다.
- 발생 건별 `grant_id`는 **만료·사용완료로 잔여가 0이어도** 다음 인계에 남겨야 합니다. 그래야 이전에 사용된 권리를 후속 Entitlement 재실행으로 복원하지 않습니다.
- Closing 재참조 시 과거 사용량을 다시 차감하지 않고, 확정 Closing 기준일 이후 사용부터 배정합니다.

현재 `runner_closing.py`는 시점 일치·확정 상태·이전 분기 참조를 확인하고 자기 책임의 집계만 수행합니다. 상세 필드·오류 경계는 `closing/README.md`에서 확인합니다.

## 5. 운영·보안 경계

1. 실제 직원·급여·근태 원본을 Git 저장소에 커밋하지 않습니다. 샘플 및 CI 합성자료와 분리합니다.
2. AWS 환경변수의 정본은 Parameter Store이며 셸로 동기화합니다. Parameter Store 쓰기 IAM/S3 백업 읽기 IAM 권한 부착은 **사전 사용자 승인**이 필요합니다.
3. 신규 공개 PTO Tool/CLI/운영 연결은 여전히 미구현입니다. **Slack/Hermes/Gearbox가 이 새 PTO 기능을 운영 호출 중이라고 주장하면 안 됩니다.**
4. 구형 `pto-calculator`와 Gearbox 버전 호환성 계약은 임의 삭제·승격·업그레이드하지 않습니다.
5. 현재 Gearbox Adapter의 v2 Module별 입력·출력 전제와 목표 v3 Tool 단위 입출력은 다릅니다. `agent-config` 별도 브랜치·PR에서 이행해야 합니다.
6. 임시 Slack 파일은 원본 영구 보관 금지·3시간 캐시·완료/만료 삭제·S3 제외 계약을 운영 통합 때 다시 검증해야 합니다.
7. 테스트는 `unittest`, Hermes Python은 `uv` 격리 환경. `python3 gearbox/_tests/run.py`(기능), `python3 gearbox/_tests/core_run.py`(인프라) 통과 필수.
8. GitHub 개발은 브랜치 → CI → 서버에서 PR 브랜치 직접 테스트 → 일반 PR 병합 → 서버 main fast-forward/브랜치 삭제. 서버·로컬 `git push` 요구하지 않으며 Draft PR/worktree 테스트를 하지 않습니다.

## 6. 구현 이력·증빙

| PR | 현재 상태 및 의미 |
|---|---|
| #36 | Common/Normalizer, 병합 |
| #37 | PTO 기본 구조/순수 API, 병합 |
| #38 | Entitlement 독립 Excel, 병합 |
| #39 | Deduction Quantity 독립 Excel, 병합 |
| #40 | 기준 문서 최신화, 병합 |
| #41 | Allocation Tool 내부 분리와 Expiry/Carryover 순수 판정, 병합 |
| #42 | 발생 ID·Closing/대휴 결합·단일 사용내역 Excel, 병합 |
| #43 | 분기 Closing A~V Excel 보고서, 분기 간 인계 자료, 병합 |

PR #43의 GitHub Actions **전체 359 tests / OK**, Shared Excel PASS. 사용자가 신규·회귀·Gearbox 호환성 서버 테스트를 모두 통과하고 PR을 병합했음을 확인했습니다. 단, 실제 운영·실자료 계산/승인은 아직 하지 않았습니다.

## 7. 다음 단계 — 순서만 합의, 실운영 아님

1. **전체 PTO Flow 계약:** 각 Module의 선택적 호출/선행자료·병렬 가능 여부/실패·미판정 처리, 입력 정본과 산출물 연결을 설계합니다. Flow는 물리 폴더로 만들지 않습니다.
2. **Use Promotion 도메인 계약:** 법정·사내 정책 자료, 대상·통지·기한·증빙·검토 및 Closing 연결 범위를 먼저 협의합니다. 자동 법적 확정·통지 발송은 별도 승인이 없으면 하지 않습니다.
3. **과거 Closing/연말→새해 인계 정합성 검토:** 연초 D 고정, 0 잔여 ID·미상계 부족·만료·사용 예약·취소/수정 입력 기준, 외부 상계 증빙 대조 절차를 합성 사례로 검증합니다.
4. **공개 Tool 계약:** 단일 Tool 입력/출력과 Module별 `user_settings.py`, `module.json`, Runner/CLI, RUNBOOK, Golden/계약 테스트 등을 설계·개발합니다.
5. **Gearbox/Ananda 및 Slack 연동:** 마지막 단계로 미룹니다. 변경 시 별도 저장소/PR과 호환성 테스트·입력 권한·임시파일 정책·실사용 승인 필요.

**현재 사용자 결정:** 실제 PTO 계산 실행은 나중에 수행하며 **구현 구조와 실행 흐름 정리가 먼저**입니다. 이 문서는 설계 판단 및 후속 인수인계 기준입니다.

## JSON Tool CLI 갱신

선택적 단계·입출력 경로·산정 기준일은 `paid-time-off.json`에서 지정합니다. 기존 독립 Runner는 유지하고 `tool_cli.py`에서 명시 선택된 단계의 산출물만 인계합니다. Gearbox/Slack 연동이나 구형 CLI 전환은 수행하지 않았습니다. [계약](TOOL-CLI.md).
