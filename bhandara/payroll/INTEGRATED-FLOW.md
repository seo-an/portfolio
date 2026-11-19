# Payroll Flow 경량화 — 검증·항목 조립·Output 단일 실행

> 적용 대상: P1-5b-2a 통합 급여 **검토 후보** 경로인 `build_contract_scoped_overtime_preview()`. 기존의 확정된 Excel 입력·출력 계약과 P1 계산 결과는 유지한다. **새로운 필수 파일·DB·Flow 물리 폴더를 만들지 않는다.**

## 개선 배경

이전 통합 경로는 아래처럼 작업했다.

1. 외부 재직·계약 배정을 검증
2. P1-5b-1 근태 정산 어댑터에서 Worktime을 읽고, 내부에서 P1-5a의 계약 검증을 **한 번 더 실행**
3. P1-5a **중간 동적 급여대장을 생성**
4. 통합 초과근무 어댑터에서 Worktime을 **또 읽고**, 계약별 초과근무 후보를 계산
5. 앞에서 생성한 동적 급여대장의 열을 탐색하여 수당 목록으로 **역변환**한 뒤, 새 급여대장을 재생성

이 패턴은 새 수당·공제 기능이 추가될수록 임시 Preview와 항목 역변환을 계속 쌓게 된다.

## 변경한 내부 실행 흐름

```text
7개 Payroll XLSX (기존 Reader)
  ├─ 계약기간·재직 검증 1회
  └─ 수당·성과급·계약금액 Core (기존 계산식)

worktime-result.xlsx (기존 10열)
  ├─ 단일시트·직원 ID 타입 구조 검사 1회
  ├─ 일별 사실 XLSX 데이터 파싱 1회
  └─ 같은 데이터로 근태·휴가 승인 및 초과근무 사실 검토

승인 계약배정 + Worktime + 승인/분류 출처원장
  ├─ 계약별 기본급/고정수당/성과급 원시 항목
  ├─ 확인된 휴가/결근 기본급 차감 후보
  └─ 계약별 승인 초과근무 후보 + 중복가산 검토
            ↓
직원별 지급항목 목록 (메모리)
            ↓
build_payroll_register(...) 단 1회
            ↓
기존 PAYROLL 동적 헤더/단일 Excel Writer
```

`segmented_settlement.py`에서 내부 함수 `_build_segmented_components()`를 분리했다. 이 함수는 기존 P1-5a 계산식으로 **직원별 지급항목 목록과 검토 기록만** 반환한다. 공개 `build_segmented_settlement_preview()`는 기존 입력 인자와 출력 스키마를 그대로 유지하는 얇은 Wrapper로 동작한다.

`contract_scoped_overtime.py`는 P1-5b-1 Preview 자체를 재호출하지 않고, 검증된 데이터 객체를 공유한 채 `reconcile_attendance_adjustments()`와 기존 `calculate_overtime_candidates()`를 사용한다. 끝에서 초과근무 항목 목록을 한 번 붙여 `build_payroll_register()`를 호출한다. **동적 급여대장의 열을 역변환하는 처리 `_merge_candidates()`를 제거**한다.

### 무엇을 변경하지 않았나

- 7개 Payroll XLSX 파일/시트/헤더, Worktime `WORKTIME` 10열
- 급여대장의 `PAYROLL` 1시트와 동적 열·2단 헤더·0원 생략 규칙
- P1-2 초과근무 금액·중복가산 및 계약별 명시적 반올림 정책
- P1-3 승인·분류 증빙의 원장 대조, P1-5b-1 무급휴가/결근 근거 검증
- 기존 P1-5a 공개 함수 인자 및 결과 키, P1-5b-1 공개 Preview API
- 실제 인증 없이 계산한 금액은 후보로만 표시하고 `earnings_complete=False`, `deductions_complete=False`, `NOT_APPROVED`, `PARTIAL_REVIEW_ONLY`를 유지하는 원칙
- PTO / Worktime 계산기, Gearbox/Hermes `agent-config`

### 검증 계획

`unittest` 회귀 테스트에서 통합 경로에 대한 `read_worktime_xlsx()`, `validate_settlement_coverage()`, `build_payroll_register()`의 호출 횟수를 각각 **1회**로 고정한다. 기존 P1-5b-1의 단독 Preview와 통합 경로에 초과근무가 없을 때의 급여대장·근태 검토 기록을 비교한다. 연장/야간 중복, 계약 전후 단가, 월중 무급휴가, 50명 중 1명 지급, 기존 공개 단독 Preview 테스트를 전체 회귀로 재검증한다.

**주의:** 파일을 안전하게 읽기 위한 `_verify_worktime_workbook()`의 구조 검사와 `read_worktime_xlsx()`의 실제 데이터 읽기는 서로 다른 동작이므로 각각 한 번은 필요하다. 데이터의 SHA-256 확인도 삭제하지 않는다. 기존 출처 원장/승인자 신뢰성을 **이번 리팩터링에서 새로 인증하는 것은 아니다**.

## 앞으로의 원칙

P1-5b-2b의 PTO Closing·복수 휴가·고정수당 감액은 **이미 검증한 데이터에서 직원별 지급항목 목록에 반영**하고, 정식 급여대장 Output은 Flow 최종 단계에서 한 번만 생성한다. P2 보험·원천세도 같은 방식으로 검증된 금액 성분을 추가한다. 최종 승인/완결 플래그는 별도 증빙이 다 충족될 때만 처리한다.

**운영/레거시 상태:** 이번 PR은 **내부 코드 리팩터링**이며 독립 Payroll JSON Tool CLI, Gearbox 운영 연결, 구형 `*-calculator` 제거는 포함하지 않는다. 서버 브랜치 정리도 보류한다.