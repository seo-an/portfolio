# Paid Time Off — v3 아키텍처 및 이관 계약 (2026-11-18)

> **상태: 일부 Module의 독립 Excel API만 구현·병합, 전체 PTO 운영 연결 전.**
> `portfolio` PR #36(Common), #37(PTO 구조/순수 API), #38(Entitlement Excel), #39(Deduction Quantity Excel) 병합.
> 현재 `portfolio/main`의 PR #39 병합 커밋: `8dffedc789415ea2acf4d8e9e360612ba1ca6baf`.
> 기존 `pto-calculator` v0.2.1, 독립 Tool/CLI, Gearbox 버전 게이트는 임의 변경하지 않습니다.

## 1. 확정 아키텍처 및 경계

| 계층 | 역할 |
|---|---|
| **Module** | 독립 계산/검증 기능. 다른 업무 Module의 자동 실행이나 필수 import를 전제로 하지 않음 |
| **Flow** | **같은 Tool 내부**에서 필요할 때 Module을 조합하는 논리적 개념. 물리 `flow/` 디렉터리 없음 |
| **Tool** | 업무별 설정, 입력/출력, 단독 호출과 Flow 조합을 소유하는 단위. 공개명 `paid-time-off` |
| **Workflow** | 서로 다른 Tool 사이의 실행 순서·파일 인계. Gearbox/Ananda 책임 |

- PTO 현재 주요 Module: `entitlement`, `deduction-quantity`, `expiry-carryover`, `use-promotion`, `closing`. `eligibility`는 예전 순수 API 초안으로 **존재하지만 PTO에서는 재실행하지 않습니다**. 향후 위치·삭제는 별도 결정합니다.
- 입력은 공통 `bhandara/data/input/` 루트와 Tool당 하나의 `input/`·`output/`을 사용합니다. 하위 Module마다 별도의 입력/출력 폴더를 만들지 않습니다.
- 실제 직원정보는 Git checkout 바깥 비공개 경로를 직접 지정합니다. Tool 간 자동 원본 복사·숨은 상태를 두지 않습니다.
- **발생·차감량 계산과 승인·권리 확정·지급을 구별**합니다. 회사 정책·근태 승인·신청 승인 등 외부에서 확정한 사실을 재판정하지 않습니다.
- `provisional_remaining_before_expiry_days` 등 잠정 잔여 필드는 새 설계에 도입하지 않습니다.
- 한국의 법정 연차유급휴가를 우선 대상으로 삼고, 대휴 등 추가 휴가 유형의 발생 권리·사용기간은 각 정책의 근거와 별도 계약을 전제로 합니다.

## 2. 실제 구현과 미구현

| 대상 | 코드 상태 | 운영상 의미 |
|---|---|---|
| Common 재사용 / Normalizer | PR #36 병합 | 독립 도구, 자체 입출력을 가진 예외 |
| PTO 초기 순수 API 구조 | PR #37 병합 | 운영 Tool 전체 아님 |
| `entitlement` | PR #38 병합, `calculation.py` + `runner.run_entitlement()` | 발생량 시범 Excel: `발생요약/발생상세/정책정보` |
| `deduction-quantity` | PR #39 병합, `calculation.py` + `runner.run_deduction_quantity()` | 승인된 사용시간 시범 Excel: `차감요약/차감상세/정책정보` |
| `eligibility` | 구형 순수 API 초안 존재 | PTO 발생 계산 단계에서 실행하지 않음 |
| Tool 내부 allocation.py | 순수 Python API 초기 구현 | Excel/Tool 연결 미구현 |
| expiry-carryover | 만료·이월 순수 Python API 초기 구현 | Excel/Tool 연결 미구현 |
| use-promotion / closing | 설계 문서만 | 계산·장부·Excel 미구현 |
| `paid-time-off/module.json`, `user_settings.py`, 최상위 CLI, Tool 조합 | 아직 미구현 | Gearbox/Slack 운영 호출 금지 |
| 구형 `pto-calculator` | v0.2.1 유지 | Golden·버전 게이트 임의 변경 금지 |

구형 `gearbox/adapters/bhandara/module_workspace.py`, `module_invocation.py`의 일부 계약은 v2의 Module별 입출력 전제입니다. v3 Tool 단위 이관을 하려면 `agent-config`에서 **별도 브랜치/PR**로 수정하고 Gearbox 호환성 게이트를 반드시 검증해야 합니다.

## 3. Module별 업무 책임

- **`entitlement`**: 입사일 기준·1년 미만 월별·회계연도 첫 비례/후속 정기 연차의 **기준일 연도 발생량만 계산**합니다. 근태관리 확정 플래그를 입력받아 사용·잔여·만료는 계산하지 않습니다.
- **`deduction-quantity`**: 외부에서 승인돼 현재 유효한 요청의 사용시간을 일수로 환산합니다. 연차/대휴 모두 지원하지만 어느 발생분에서 차감할지는 계산하지 않습니다. 미래 승인된 사용일도 입력에서 제외하지 않습니다.
- **Tool 내부 allocation.py**: 순수 계산으로 요청 ID와 발생 ID를 연결해 부족분·예약까지 배정합니다. 업무 Module이 아닙니다.
- **expiry-carryover**: 만료/이월 판정만 하는 독립 순수 Module입니다. **차감 배정은 하지 않습니다.** 수당 지급·법적 면책 판정도 하지 않습니다.
- **`use-promotion` (미구현)**: 사용촉진 대상·기한·통지/증빙 및 적용 법령·정책을 별도 협의합니다.
- **`closing` (미구현)**: 월별·기간별 사용량, 총 사용량 등의 **마감 집계·보고 양식**을 담당합니다. 요청별 차감 근거를 보여 주는 사용내역 표와는 서로 다른 산출물입니다.
- 신청·승인·반려·취소 이력, 출퇴근 원본 검토, 휴일/근무일 충돌 검증은 **외부 시스템**이 소유합니다. 계산 Module은 외부 확정 사실을 신뢰하고 해당 계약을 검증합니다.

## 4. 독립 실행 경로와 입력 정책

- Entitlement 입력: `common/employee.xlsx`(`재직자`/`퇴사자`), `paid-time-off/attendance-result.xlsx`(`근태결과`), 최초 회계연도 비례 계산 시 `paid-time-off/proration.xlsx`(`비례자료`).
- Entitlement 산정기간: `as_of_date`가 속한 해의 1월 1일부터 기준일까지 발생한 건만. 이전 해 근태는 판정 근거로 참조 가능하나 이전 해 **발생량**은 다시 합산하지 않습니다.
- Deduction 입력: `paid-time-off/approved-leave.xlsx`(`승인휴가`), 필수 헤더 `request_id, employee_id, leave_date, leave_type, duration_hours`.
- Deduction 정책: `duration_hours / standard_daily_hours`; 기본값 **8시간**이며 호출에서 덮어쓰기 가능. **직원별 자동 정책/스케줄 조회는 아직 구현하지 않았습니다.** 동일 요청 ID의 다른 날짜 허용, 동일 요청+동일 날짜는 모두 계산 제외합니다.
- 시간 환산은 중간 반올림하지 않습니다. 유한소수는 그대로, 무한소수는 **표시에서만 소수 7자리 절사**합니다. Entitlement의 최종 연차 발생량 정수/소수 첫째 자리 반올림 정책을 Deduction에 복제하지 않습니다.
- Deduction에서 값 누락·날짜/시간 오류·미지원 유형·중복 요청 날짜·Excel 수식 등은 해당 행 `계산 제외`와 사유로 기록하고 정상 행은 계속 계산합니다. 파일/시트 부재나 중복 헤더 등 구조적 오류는 중단합니다.
- Entitlement의 근태 판정 미확정은 `판정 안됨`으로 처리하며 일부 발생 건이 미확정이면 해당 직원 요약 발생연차를 확정 숫자로 채우지 않습니다.
- 동일 `run_id` 결과 덮어쓰기 금지. 입력 SHA256/정책 참조를 마지막 `정책정보` 시트에 기록합니다.

독립 Python 호출 예시는 `README.md`를 봅니다. **기존 `calculate_deduction_quantity(unit=...)` 순수 API는 호환용으로 유지**, 신규 시간 기반 계산은 `deduction-quantity/calculation.py`에 있으며 두 API를 혼동하지 않습니다.

## 5. 현재 미확정 사항

- PTO 전체 Tool `module.json`, `user_settings.py`, 선택적 Flow, 최상위 CLI, Gearbox/Slack 신규 운영 연결.
- 발생 건 고유 ID(`grant_id`) 부여, 당년 Entitlement 결과와 과거 발생·이월 원장 및 외부 대휴 발생분의 중복 없는 결합.
- 발생분별 만료일 결정·정책 버전·우선순위, 미래 승인분의 예약과 실제 사용 완료 시점, 부족 수량·오류 행 처리.
- 휴가 사용권 만료와 미사용수당/사용촉진 면책 여부의 관계. **만료일만으로 법정 수당 지급을 자동 확정하지 않습니다.**
- 요청-발생 연결을 담는 독립 사용내역 결과표의 정확한 열/시트 및 PTO 통합결과표는 **보류**.
- `closing`의 월별·기간별·총 사용량 보고 구조, `use-promotion`의 통지·증빙 규칙.
- 과거 직원/퇴사자·근무정책 변경, 승인 취소/정정 이력의 기준 시점 및 재실행 스냅샷 보존 방식.

## 6. 검증·이관 이력 및 안전 규칙

| PR | 범위 | 확인된 검증 |
|---|---|---|
| `portfolio` #36 | Common/Normalizer | 서버 270 tests / OK (당시) |
| `portfolio` #37 | PTO 독립 API | GitHub Actions 전체 285 tests / OK (당시) |
| `portfolio` #38 | Entitlement Excel | GitHub Actions 전체 311 / OK; 사용자 서버 331 / OK (서로 다른 실행) |
| `portfolio` #39 | Deduction Excel | GitHub Actions 전체 **321 tests / OK**; 사용자 서버에서 테스트·호환성 모두 통과 확인 후 병합 |

- `portfolio/main`의 #39 병합 커밋은 `8dffedc789415ea2acf4d8e9e360612ba1ca6baf` (2026-11-18 확인). 문서 PR이 후속 병합되면 이 커밋은 **#39 기준 기록**이지 최신 HEAD가 아닐 수 있습니다.
- 기존 Gearbox 기능 테스트는 `python3 gearbox/_tests/run.py`, 인프라 테스트는 `python3 gearbox/_tests/core_run.py`. 신규 Bhandara에는 `unittest`를 사용하며 `pytest`는 사용하지 않습니다.
- 서버 테스트는 Hermes의 uv 격리 Python을 사용합니다. 사용자 서버에서 PR 브랜치를 직접 checkout하여 테스트하고, 정상 완료 후 PR을 병합합니다. Draft PR·worktree 테스트·서버 push 요구 금지.
- 병합 뒤 서버에서 `main`으로 복귀/fast-forward, 기능 브랜치를 `git branch -d`로 정리합니다. 작업 파일을 지우는 `reset --hard`나 `clean -fdx`를 습관적으로 사용하지 않습니다.
- 실제 직원/급여 입력 Git 저장 금지. 임시 Slack 파일은 3시간 캐시·완료/만료 삭제·S3 백업 제외 계약을 운영 E2E에서 재검증해야 합니다.
- Parameter Store 설정 사용; 쓰기 IAM과 S3 백업 읽기 IAM을 붙이는 작업은 사전에 사용자 승인을 받습니다.

## 7. 다음 Module 협의 순서

1. **`expiry-carryover` 기능 범위**: 발생분별 사용 가능 여부, 이월/만료, 차감 배정 책임과 수당/승인 제외.
2. **Input**: 발생 원장·과거 발생분·대휴 발생분, `entitlement` 산출 경로, `deduction-quantity` 상세 결과를 어떻게 연결할지.
3. **계산**: 사용일에 유효한 발생분만 차감, 사용일 순 처리, 먼저 만료되는 권리 우선. 취소 신청이 빠진 **최신 승인 목록으로 전체 재배정**, 별도 역방향 환입 장부를 만들지 않음.
4. **Output**: `request_id` + `grant_id`가 **동일한 차감내역 자체**에 들어가며 동일 요청이 두 발생분에 걸치면 여러 행. 발생분별 잔여·기간별 상태·정책 근거의 정확한 시트는 다음에 확정.
5. **예외**: 만료 전/후 사용, 부족 수량, 중복 원장, 날짜 충돌, 미래 승인분 예약 등의 최소 처리 규칙을 합의.
6. 이후 `use-promotion`과 `closing` 순서로 설계하고, 모든 Module 계약이 갖춰진 후 선택적 Flow·Tool·Gearbox 이관을 진행합니다.

> **중요:** 위 Expiry/Carryover의 구체적인 Excel 헤더·차감 우선순위 설정 방법·결과 시트는 아직 구현/확정되지 않았습니다. 다음 대화에서도 사용자와 먼저 협의한 뒤 브랜치·PR 작업을 시작합니다.

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


## 9. 2026-11-18 결정 및 이행: Deduction Quantity

> 2-2 초기 문서의 “차감량은 순수 API뿐/아직 Excel 결과 없음”이라는 표현은
> 최신 구현 상태를 설명하지 않습니다. 새로 추가된 것은 **독립 Excel 시범 API**이지
> PTO 전체 Tool 또는 Gearbox 운영 경로가 아닙니다.

1. **외부 신청 시스템:** 신청·승인·반려·취소를 관리합니다. 승인돼 현재 유효한 신청만 `approved-leave.xlsx`의 `승인휴가` 시트에 제공합니다. 미래 승인분도 포함하며, 취소된 신청은 다음 실행 입력에서 제거합니다.
2. **입력 및 정책:** `request_id`, `employee_id`, `leave_date`, `leave_type`, `duration_hours`. 연차·대휴를 구분하지만 차감 수량 계산법은 동일합니다. 외부에서 대휴 발생량을 확정합니다. 기준시간 기본값은 8시간이며 직접 지정한 정책값이 있으면 우선합니다. 현재 직원별 근무시간 자동 조회는 구현하지 않습니다.
3. **계산:** 모든 차감량은 시간/일 기준시간의 정확한 `Fraction`으로 합산합니다. 유한소수는 정확하게, 무한소수는 출력에서만 7자리 절사하며 반올림하지 않습니다. 기존 `unit=DAY/HALF_DAY/QUARTER_DAY/HOUR` 순수 API는 과거 테스트 및 호환을 위해 유지하고 신규 Excel 경로에는 사용하지 않습니다.
4. **예외:** 행 누락·동일 요청 ID 및 사용일 중복·유형 오류·시간/날짜 오류·Excel 수식은 각 행에 표시한 뒤 계산 제외합니다. 중복 조합에 해당하는 행을 모두 제외합니다. 정상 행은 계속 계산하고 직원별 요약에 부분 제외를 명시합니다. 파일·시트 부재, 헤더 중복 등 구조적 오류는 실행 자체를 중단합니다. 고급 검토 등급은 후속 실사용 이후 정의합니다.
5. **독립 Output:** `차감요약`(직원별 유효 차감일수), `차감상세`(신청 ID·사용일·유형·원시간·차감일수·검토 사유), 마지막 `정책정보`. `run_deduction_quantity()` 독립 Python API로 실행. 발생일수·잔여일수·발생분별 차감 배정은 계산하지 않습니다.
6. **이후 조합:** `expiry-carryover`는 현재 유효한 발생 건/만료/이월을 고려해 승인 사용량을 발생분에 배정하고, 그 **차감내역 자체**에 `request_id`와 `grant_id`를 함께 보유합니다. 취소 시 과거 배정을 부분 롤백하지 않고 변경된 유효 승인 목록으로 사용일 순서대로 다시 배정합니다. 먼저 만료되는 유효 권리부터 차감하는 방식은 정책화합니다. 생성 가능한 통합 사용내역 결과와 `closing`의 월별/누계 마감 양식은 서로 구별하고 아직 구현하지 않습니다.
7. **기존 정책 유지:** `entitlement`는 연도별 발생량만 계산하고 PTO에서 `eligibility`를 재실행하지 않습니다. Tool 하위별 입출력 폴더, 물리 `flow/` 폴더, 잠정 잔여 필드는 추가하지 않습니다. 구형 `pto-calculator`와 Gearbox 버전 게이트는 그대로 유지합니다.


## 10. 2026-11-18 설계 결정: 발생분별 차감 배정 (미구현)

- 차감내역을 별도 배정 원장으로 이중 보관하지 않고 그 자체에 `request_id`/`grant_id`를 기록합니다.
- 취소 후 `+1` 환입 행으로 기존 기록을 임의 수정하는 것이 아니라, 외부에서 취소 신청을 제외한 유효 승인 목록을 다시 받아 사용일 순으로 배정합니다.
- 발생일이 과거여도 **해당 사용일에 권리가 유효해야** 배정할 수 있습니다. 발생일·만료일·우선순위 정책이 없다면 임의로 추정하지 않습니다.
- 사용내역 요약 후보는 직원별 `employee_id`, 발생일수·사용일수·잔여일수. 상세 후보는 요청 ID/발생 ID/사용일/휴가유형/차감량 및 잔여 추적입니다. **이는 다음 Module 조합 이후의 결과 후보이고 현재 Deduction Excel의 확정 열이 아닙니다.**
- `closing`은 이 결과와 별도로 월별·기간별·누적 사용량을 마감 집계합니다. PTO 전체 통합 결과표는 여전히 보류합니다.

## 2026-11-18 최신 설계: Allocation과 Expiry/Carryover 분리

**기존 문서에서 Expiry가 발생분 차감까지 소유한다고 한 부분은 폐기합니다.** 현재는 순수 Python API 초기 구현이며 최종 Excel·Tool 호출 경계는 아직 아닙니다.

- paid-time-off/allocation.py: Tool 내부 계산 단계. 별도 Module도 아니고 물리 flow/ 폴더도 아닙니다. 입력된 발생 건과 승인된 사용 건을 ID로 연결합니다.
- paid-time-off/expiry-carryover/calculation.py: 독립 Module. 외부에서 유효기간과 마감일 현재 잔여가 확정된 발생 건에 대해 만료 또는 이월을 판정합니다. 배정/잔여 재계산/수당 지급 승인은 하지 않습니다.
- Closing-1.4-2025 ~ Closing-4.4-2025 ID에서 분기 종료일을 유도하므로 opening_date 추가 입력은 없습니다. API의 balance_as_of는 상위 결과의 기준일이 마감일과 같은지 검증하는 값이지 사용자에게 입력을 중복 요구하는 시트가 아닙니다.
- Allocation의 발생 건 입력 필드: grant_id, employee_id, leave_type, grant_date, available_days, valid_from, expires_on, source_ref. available_days는 원천에서 확정된 반영발생일수 또는 기존 Closing의 발생분별 기초잔여를 정규화한 내부 이름입니다. 유효기간은 필수이며 누락 시 추정하지 않습니다.
- Allocation의 차감 입력 필드: request_id, employee_id, leave_type, leave_date, deduction_days. Deduction Quantity에서 이미 일수 환산된 승인 내역만 인계합니다.
- 배정 순서는 사용일 → 만료일 → 발생일 → grant_id. 취소된 요청을 제외한 현재 유효 승인 목록으로 전체 재실행합니다. 연차와 대휴를 교차 차감하지 않습니다.
- 초과 사용은 신청별 발생분 미배정 행(grant_id 없음)과 직원·유형별 **음수 잔여**로 표시합니다. 발생 건 자체를 음수로 변경하지 않습니다. 새 발생분으로 **자동 상계하지 않습니다**. 상계는 외부 확정 지시가 있어야 하지만 그 지시의 실제 입력 계약은 추후 연결합니다.
- 미래 예약은 실행 기준일의 사용량과 별도 표시합니다. 마감일 이전의 발생분별 확정 잔여만 만료/이월 계산에 사용하며 미래의 미확정 발생은 예측하지 않습니다.
- 무한소수 7자리 절사 문자열로는 정확한 분수를 복구할 수 없습니다. 향후 Excel-to-Flow 연결 시 분수의 정확한 인계 규격을 추가해야 합니다.
- Expiry의 만료된 연차는 미사용수당 **검토 대상**만 표시하며 현금청구권·면책·지급을 자동 승인하지 않습니다.
- 오류가 특정 직원/휴가유형의 수량에 영향을 주면 그 그룹의 배정을 생략합니다. 정상적인 다른 그룹의 계산은 유지합니다.
- 과거 Closing/외부 대휴/Entitlement 원본 Excel의 실제 결합, grant_id 생성, 내부 Flow의 선택적 호출, 최초 Closing 이전 기초자료 인계, 외부 상계 명령, 결과 Excel과 SHA 기록은 **아직 구현하지 않았습니다**.
- 단독 unittest: python3 -m unittest bhandara.tests.test_paid_time_off_allocation_expiry -v

