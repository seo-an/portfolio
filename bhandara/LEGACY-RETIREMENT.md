# Bhandara 레거시 철수 계획 (마이그레이션 완료 후)

> **목표:** 구형 `pto-calculator`, `worktime-calculator`, `payroll-calculator` 및 이들의 더 이상 쓰지 않는 설정/예제/호환 코드를 제거하고, 신규 `paid-time-off` / `worktime` / `payroll` + Common + 논리 Flow/Tool/Workflow 구조로 단일화한다. **2026-11-19 현재 철수 완료가 아님.**

## 현재 확인한 의존 관계

- `run.py`의 `_LOCAL_ROLE_FIELDS`에 구형 계산기 3종이 등록되어 있고, 구형 `module_id` 라우팅·파일 역할·설정 및 `payroll-calculator.taxability_adapter` 호출 경로가 남아 있다.
- 루트 `README.md`, `bhandara/RUNBOOK.md`, `bhandara/DEVELOPMENT-STATUS-2026-11-19.md`와 Golden 비교/단독 설치 안내가 구형 계산기의 입출력을 설명한다.
- 공개 샘플 `bhandara/examples/sample/input/payroll/pay-contract.xlsx`는 기존 활성 시트 방식일 수 있으며, 새 `payroll/input-files.json`의 **7개 별도 XLSX**와 자동 호환한다고 인정하지 않는다.
- `agent-config` / Gearbox의 실제 기존 Calculator 호출, 버전·권한·Slack 입력/출력 연결은 아직 운영 전환/회귀 검증이 필요하다. `agent-config`는 사용자 재개 지시까지 PAUSE.

## 순서대로 철수

| 단계 | 통과 기준 | 삭제 가능 여부 |
|---|---|---|
| 1. 새 Tool 기능 완성 | PTO의 Use Promotion, Worktime의 Closing/복수 구간, Payroll의 법정 지급검토·공제·중도변경 등 정의된 범위를 구현 | 구형 삭제 금지 |
| 2. JSON CLI·Flow·계약 E2E | 신규 3종 각각 한 줄 실행, 월/주기·입출력·상태·원본 불변 및 50명 합성자료 검증 | 삭제 금지 |
| 3. 구형 비교 | 동일 합성 입력의 **정규화된 계약·결과** 비교. 설계 변경에 따른 차이는 명시적 승인받은 테스트로 기록 | 삭제 금지 |
| 4. Gearbox/Hermes 전환 | 신규 Tool 호출·권한·파일 TTL·Slack 회신과 핵심 Gearbox 기능/인프라 테스트 통과 | 운영 의존 관계 제거 후 검토 |
| 5. 신규 단독 설치 | Common+신규 Tool만 설치해 실행; `run.py`, 설치 검사, 샘플·문서가 더 이상 구형 파일을 참조하지 않음 | 단계별 철수 가능 |
| 6. 레거시 삭제 PR | 기존 `*-calculator` 폴더, 구형 라우팅/설정/테스트, 구형 문서·예제·의존 모듈 제거. 신규 합성 테스트와 운영 회귀 전체 통과 | 사용자 검증·병합 후 완료 |

**삭제를 먼저 하고 테스트를 고치는 방식은 금지**한다. 신규 기능이 아직 지원하지 않는 외부 계약이 남아 있으면 삭제 조건을 충족하지 못한다. 구형 계산기별 **독립 PR**로 이관·제거하고 각 PR에서 GitHub CI와 실제 서버 브랜치 테스트를 통과한다.

## 삭제하지 않을 것

- Common의 현재 신규 Tool에서 사용 중인 Base·ID Mapping·보안업체 Mapping 등 **공통 기능**
- 신규 계산과 비교에 계속 필요한 검증용 **Golden의 형식/기준**. 다만 구형 구현에만 의존하는 테스트는 신규 정본으로 전환
- 실제 사용자 직원/급여 원본·개인정보 및 운영 백업은 코드 철수 작업의 삭제 대상이 아니다. 개인정보 보관·삭제 정책은 운영 계약에서 별도로 처리한다.

## 실무상 현재 다음 단계

1. Payroll P1-3 출처 원장 내용 대조(PR #66)와 P1-4 중복가산 후보(PR #67)는 병합됐다. P1-5a 재직·계약분할 검토 PR #68도 병합됐다. P1-5b-1 휴가·결근 근태 대조 및 승인 차감 후보(PR #69)도 병합됐다. 현재 P1-5b-2a **계약별 초과근무 수당 후보 결합**을 신규 어댑터로 추가 중이며 이후 P1-5b-2b 복수 휴가·PTO Closing·고정수당 감액 검증과 P2/P3를 진행한다.
2. Payroll P2 공제·과세, P3 JSON CLI와 전체 합성 E2E.
3. 아직 남은 PTO/Worktime 기능을 완료하고 Gearbox/Slack 신 Tool로 운영 경로를 전환한다.
4. **마지막에** 레거시 제거 PR을 단계적으로 진행한다.

이 문서는 *철수 목표와 선행조건*이지, 실제 삭제가 수행됐다는 기록이 아니다.
