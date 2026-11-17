# Paid Time Off — v3 아키텍처 및 이관 계약 (2-2 진행 중)

> **상태: 부분 구현 / 운영 연결 금지.** 2026-11-17 기준 2-2의 첫 번째 코드 분리 작업이다. 현재 `pto-calculator` v0.2.1과 그 CLI·Golden·Gearbox 버전 게이트는 그대로 유지한다. 새 디렉터리가 생겼다는 이유로 새로운 Tool 전체가 사용 가능한 것은 아니다.

## 1. 계층 정의

- **Module:** 독립적인 업무 계산 또는 판정. 다른 업무 Module의 실행·import를 전제로 하지 않는다.
- **Flow:** 같은 Tool 내부에서 필요한 Module만 선택적으로 조합하는 **논리적 관계**. `flow/` 디렉터리 없음.
- **Tool:** `paid-time-off` 업무의 설정, 공용 입출력, 공개 호출을 소유하는 단위.
- **Workflow:** Gearbox/Ananda가 필요할 때 Tool 간 경로와 실행 순서를 연결. Tool은 다른 Tool을 실행하지 않는다.

**명칭은 확정:** `entitlement`, `eligibility`, `deduction-quantity`, `expiry-carryover`, `use-promotion`, `closing`.
Tool 공개명은 **Paid Time Off (PTO)**. 현 범위는 한국 연차유급휴가이며 병가 등 글로벌 PTO 전체 지원 주장은 하지 않는다.

## 2. 현행 함수 → 신규 소유권

| 기존 구현 | 2-2 소유권 | 이행 방식 |
|---|---|---|
| `src/core.py`의 `add_months`, `monthly_grant_evaluations`, `annual_days_for_service_year`, `anniversary_grants` | `entitlement` | 입사일 기준 산식 보존·회귀 비교. 적격성 증거 **필수**. 기존 기본값(출근요건 충족 추정) 복제 금지 |
| `src/core.py`의 `fiscal_first_year_proration`, `ceil_half_day` | `entitlement` 후속 | 기존 함수는 Jan–Dec 비례 계산의 일부일 뿐. 회계연도 정책·비례 기준·반올림·입사일 기준과 비교 계약 미확정 |
| `src/eligibility.py`, `aggregation.py` | `eligibility` | 출근율/개근 판정. 신규 순수 API는 최종 검증된 기간 집계 사실만 받음; 일별 기록 집계·증빙 변환은 차기 이행 |
| `src/daily_calendar.py`, `attendance*.py`, `schedule.py`, `resolver.py`, `event_reconciliation.py` | 출근요건 증빙 입력 준비 경계 | 정책·근태 증빙의 소유권 검토 필요. 다른 Module의 계산을 묵시적으로 호출하지 않음 |
| `src/leave_ledger.py`의 `_event_days` | `deduction-quantity` | 전일·반차 차감 규칙 분리, 반반차/시간차 계산 추가. **승인·중복·휴무일 충돌 판정은 미배정** |
| `src/leave_ledger.py`의 승인·신청 ID·중복일 검토 | **미확정** | 중복 계산 없이 소유권 정할 때까지 기존 구현 보존; 신규 deduction API에 집어넣지 않음 |
| `src/leave_ledger.py`의 잠정 잔여 | **폐기** | 새 결과 계약에 `provisional_remaining_before_expiry_days` 포함 금지. 기존 레거시 회귀 테스트만 유지 |
| 현행 직접 구현 없음 | `expiry-carryover` | 소멸·이월·수당청구권 전환 조건 및 사용촉진 증빙 명시 계약 필요 |
| 현행 직접 구현 없음 | `use-promotion` | 사용촉진 일정·통보·증빙의 법령·정책 버전 검토 필요 |
| `runner.py`의 Excel 작성/기간 출력 일부 | `closing` 및 Tool 공통 리포팅 경계 | 마감 확정과 단순 계산 리포트는 구별. 신규 마감 산식 자동 생성 금지 |
| `src/input_adapter.py`, `runner.py`의 hash/헤더/행 오류 격리 | Tool 입출력·검증 경계 및 Common 재사용 | 원본 증빙·검토 결과·직원별 격리·Excel 산출 보존 |

## 3. 현재 작성된 독립 Python API

`importlib.import_module("bhandara.paid-time-off.<module-id>")`로 호출한다. 독립 라이브러리 API이며 **아직 CLI/Tool 통합 실행 계약은 아니다**.

| Module | 제공 API | 필수 입력 | 반환 및 비허용 사항 |
|---|---|---|---|
| `entitlement` | `calculate_anniversary_grants()`, `annual_days_for_service_year()`, `add_months()` | `hire_date`, `as_of_date`, 두 개의 **명시적** 월/연 적격성 판정 함수 | 날짜·사유·`raw_days`(Decimal 또는 None). 발생만 산정; 사용·잔여·승인 없음 |
| `eligibility` | `evaluate_monthly_full_attendance()`, `evaluate_annual_attendance_80()` | 기간별 검증된 근무일수·출근/결근 집계, `coverage_complete`, `source_status` | `ELIGIBLE`/`NOT_ELIGIBLE`/`UNDETERMINED`; 완전하지 않은 증빙은 `UNDETERMINED` |
| `deduction-quantity` | `calculate_deduction_quantity()` | 선언된 `unit`, 시간차는 `duration_hours` 및 **명시적** `standard_daily_hours` | `quantity_days`(문자열 Decimal 또는 null); 승인·신청 충돌·실사용·장부 반영 없음 |

- 차감 단위: `DAY` = 1, `HALF_DAY` = 0.5, `QUARTER_DAY` = 0.25, `HOUR` = 입력 시간/정책상 1일 시간. 계산 가능한 수치가 있다고 해서 사용 승인이나 회사 정책 적용 적합성을 뜻하지 않는다.
- 적격성은 최종 검증된 기간별 출근 집계만 받아 판정한다. 출근 인정일·제외일·휴가 간주 처리의 전처리 책임과 원본 증빙은 별도 계약이 필요하다.
- 신규 API에서 `approved=false`, `finalizable=false`는 계산 결과가 인사 승인/마감 확정이 아님을 뜻한다.
- 서로의 계산 함수를 필수 import하거나 다른 업무 Tool을 실행하지 않는다.

## 4. 입출력 계약: **확정 원칙 / 세부 추후 확정**

1. 기존 `bhandara/data/input/`을 공유 입력 루트로 **유지**한다. 공개 checkout의 자료는 합성 샘플만; 실제 직원/급여 입력은 checkout 밖의 비공개 루트를 명시한다.
2. 물리적 기본 폴더는 `paid-time-off/input/`, `paid-time-off/output/` **Tool 단위 1세트**. 하위 6개 Module에는 `input/`, `output/`을 만들지 않는다.
3. 입력 선택 순서: **명시된 역할별 파일 → 명시된 입력 루트의 선언된 상대경로 → 미지정 시 Tool 기본 input**. 잘못된 명시 경로·필수 헤더·권한은 기본값으로 대체하지 않는다.
4. 재사용할 공통 자료의 예: `common/employee.xlsx`, `pto/work-schedule.xlsx`, `pto/work-schedule-assignment.xlsx`, `pto/employee-events.xlsx`. 현재 기존 레이아웃과의 호환 경로이며 새 Module별 실제 요구 입력은 별도 확정.
5. Module 간 전달은 검증된 결과 값 또는 승인된 **정확한 경로**. 원본 자동 복사·기본 숨은 상태·Tool 간 종속 없음.
6. 결과물은 Module ID + run ID + 파일명으로 구별하고 정확한 절대/해석된 경로 반환. 산출물 명칭, run ID 생성, Tool Runner, `module.json`, `user_settings.py`는 다음 구현 단계에서 확정. 아직 결과 파일을 쓰지 않는다.
7. Common Normalizer는 독립 도구이며 자체 input/output을 가지는 **예외**이다.

## 5. 명시적으로 미확정·미구현인 기능

- **회계연도 발생:** 정산연도, 일할 기준, 절사/반올림, 입사일 기준 대비 불리 여부 검증.
- **신청 유효성:** 신청 ID 중복, 같은 날 겹침, 전일/반일/시간차, 취소·반려·승인 이력. 차감량 산정과 장부 반영의 소유권 미정.
- **휴무일 충돌:** 공휴일·대체공휴일·회사 휴무일·개인 스케줄 비근무일에 신청한 경우의 검토 경계.
- **소멸·이월:** 법적 사용권 소멸·수당청구권 전환 여부·회사 정책 근거 및 사용촉진 결과 연동.
- **사용촉진/Closing:** 통지·증빙·기간별 마감·관리대장의 계약과 책임 배치.
- 위 항목은 자동 판단/승인하지 않는다. `expiry-carryover`, `use-promotion`, `closing`은 이번 첫 변경에서 **계산 구현이 아닌 책임 범위 명시 상태**이다.

## 6. 버전·안전한 이관

- 지금까지 확인된 정상 운영: `pto-calculator` v0.2.1, Gearbox 호환성 PASS, 기존 서버 270개 unittest PASS (**과거 `main` 검증 이력**).
- 이 브랜치는 새 Tool의 **순수 함수 3개 Module 초안과 계약·테스트만 추가**한다. 기존 CLI, manifest, 입출력, Golden 비교는 건드리지 않는다. 신규 Tool 실행 가능한 버전을 아직 선언하지 않는다.
- 향후 신규 Tool Runner·manifest가 완성되면 선택 실행/전체 실행/입력 우선순위/증빙/Excel/고립 오류를 통합 테스트하고, 별도 `agent-config` 브랜치에서 Gearbox 허용명·버전·어댑터를 맞춘 후 전환한다.
- 사전 승인 없는 Tool 변경 버전 배포, 원본 Git 저장, Slack 파일 영구 저장, 법적 지급/마감 승인 추정 금지.

## 7. 2-2 후속 구현 순서

1. 현 순수 함수 세 Module에 일별 증빙 표준 입력/JSON 결과 계약을 추가하고 기존 Golden의 **보존 대상 계산**과 비교.
2. 회계연도 발생과 시간차의 회사별 정책 설정 계약을 정한 뒤 정책·예외 테스트.
3. 신청 상태·중복·비근무일 충돌에 대한 단일 소유권 결정, 명시적 검증 결과 전달.
4. `expiry-carryover`, `use-promotion`, `closing`의 세부 입력/증빙/결과 계약 확정 후 각각 독립 구현.
5. Tool 공통 I/O·설정·선택적 Flow·CLI 및 인적 사용 RUNBOOK 완성.
6. 변경 커밋에서 전체 `unittest`와 GitHub Actions, Gearbox 버전 게이트, 실제 서버 브랜치 검증 후 PR 병합.

> **검증 주의:** `test_paid_time_off_v3_core.py`는 이 브랜치의 세 가지 순수 함수 Module만 확인한다. 구형 270개 테스트가 통과해도 PTO v3 Tool 전체 운영 승인으로 해석하지 않는다.


## 8. 2026-11-17 협의 반영: Entitlement 첫 구현

> 이 항목은 2-2 초기 가정 중 최신 Entitlement 설계와 충돌하는 부분보다 우선합니다.
> 기존 `pto-calculator`의 입출력·Golden·Gearbox 버전은 그대로 유지합니다.

1. **근태 판정의 소유권:** 근태관리 단계가 개근/출근율 플래그를 이미 확정합니다. Entitlement는 `eligibility`를 실행하거나 검증·확인용으로 재실행하지 않습니다. `eligibility` Module의 향후 존속·배치는 미확정입니다. 기존 초안 API는 호환성 때문에 지금 당장 삭제하지 않습니다.
2. **입력:** `common/employee.xlsx`의 `재직자`와 `퇴사자` 시트를 모두 읽습니다. 근태 결과는 `check_type`=`월간`/`연간`, `attendance_flag`=`개근`/`미개근`/`80% 충족`/`80% 미충족`/`판정 안됨`을 사용합니다. 날짜 범위는 `period_start`, `period_end` 두 셀로 구분합니다. 근태 원본 집계와 출근율 판정은 수행하지 않습니다.
3. **회계연도 발생:** 최초 회계연도 경계는 비례 부여(소정근로일 기본, 달력일·월수 선택). 이후 매 회계연도 경계에서 직전 회계연도 근태 플래그 및 실제 입사일 기준 완료 근속연수에 따라 정기 연차(가산 포함)를 산정합니다. 연간 '80% 미충족' 시 월간 개근 판정으로 대체하며, 첫해 월별 발생분과 중복되지 않게 처리합니다. 누락·중첩 근태 자료는 추정하지 않고 `판정 안됨`으로 둡니다.
4. **정밀도:** 중간 계산은 `fractions.Fraction`으로 손실 없이 처리합니다. 무한소수의 원본 출력은 소수점 아래 7자리에서 **절사**하고, 최종 직원별 합계에서 한 번만 사사오입합니다. 최종 반올림 자릿수는 `0`(정수) 또는 `1`(소수점 첫째 자리) 중 선택합니다.
5. **Module 병렬 산출:** `발생요약`은 직원별 한 행(기준, `계산결과`, `발생연차`, 상태). `발생상세`는 발생일·산정기간·`계산결과`를 건별 출력합니다. 이벤트 단위에서는 반올림하지 않습니다. 정책·실행 참조·입력 SHA256은 마지막 `정책정보` 시트 하나에 모읍니다.
6. **미판정:** 필수 이전 근태 판정이 없거나 미확정이면 그 발생 건의 숫자는 비워 두고 `판정 안됨`으로 내보냅니다. 직원 요약에서 부분합을 완성된 권리처럼 표시하지 않습니다. 예외 등급과 사용자 검토 절차는 시범 구현 후 협의합니다.
7. **분리된 책임:** `expiry-carryover`가 권리별 이월·만료를 처리하고, `closing`이 발생·이월·만료 및 사용량을 집계합니다. 사용 전 유효 총량은 `기본 발생+기초 이월-만료`로 합의했으나 **통합 결과표의 열 구조는 보류**합니다.
8. **운영 상태:** `bhandara/paid-time-off/runner.py`의 `run_entitlement()`는 독립 **Excel 시범 실행 API**입니다. 공개 최상위 CLI, 전체 Tool manifest, Gearbox가 새 Tool을 호출하는 기능은 아직 미구현이며 운영 승인으로 간주하지 않습니다.

합성 테스트는 `bhandara/tests/test_paid_time_off_entitlement_excel.py`에서 다룹니다.
