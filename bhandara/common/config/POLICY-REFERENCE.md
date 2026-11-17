# Bhandara Common 정책 참조 계약 (1차 구조 개편 시작)

이 문서는 **정책의 출처를 선택**하는 공통부 계약이다. 계산 공식과 회사 정책을 생성하지 않는다. 현재 세 계산기 CLI에 자동 연결된 기능은 아니며, 기존 단독 실행 동작을 변경하지 않는다.

## 소유권

- **비공개 Agent/Gearbox:** 회사 정책의 정본, 접근 승인, Google Drive 조회, 민감자료 처리
- **공개 Bhandara Common:** 제공된 JSON·허용된 파일 참조 확인, 공개 기본 참조 선택, 자료 해시
- **개별 계산 모듈:** 전달된 정책으로 각자의 계산 수행. 다른 모듈 내부 코드는 참조하지 않음

## 호출 계약

Python 진입점: `bhandara.common.config.policy_reference.resolve_policy_reference(module_id, policy_role, explicit_reference=None, *, input_roots=None)`

반환 객체: `ResolvedPolicy(value, source_kind, sha256, used_default)`

사용자는 규칙을 직접 담거나 참조를 제공할 수 있다.

- **직접 규칙:** `{"kind":"inline","value":{"schema_version":"1.0","example":"review_only"}}`
- **비공개 준비 파일:** `{"kind":"file","root":"input","path":"company-policy.json"}`

`input_roots={"input": Path("/비공개/안전한/작업영역")}`처럼 허용 루트는 **신뢰된 호출자만** 등록한다. 사용자·모델이 임의 서버 경로를 루트로 등록하면 안 된다.

Drive 참조는 Gearbox가 인증하고 사설 임시 작업영역에 준비한 다음 로컬 `file` 참조로 전달한다. Common은 네트워크나 OAuth를 직접 사용하지 않는다.

## 기본값·오류 규칙

- `explicit_reference=None`이면 `policy-defaults.json`에서 해당 모듈·역할의 공개 기본 참조를 찾는다.
- **등록된 기본값이 없다면 차단한다.** Worktime 회사별 정책과 Payroll 회사 정책의 기본값을 임의로 생성하지 않았다.
- **명시된 정책 참조가 잘못되면 차단한다.** 기존 기본값으로 몰래 대체하지 않는다.
- 이 단계에서는 완성된 하나의 JSON 정책 객체만 선택한다. 부분 정책 병합과 업무별 계산 규칙 결정은 후속 단계로 남긴다.
- `portfolio`는 공개 리소스 루트로 예약되어 있으며 호출자가 바꿀 수 없다.
- **주의:** 이 API는 Slack 원본 인증·임시파일 TTL·실행 중 잠금 기능이 아니다. 실자료 경계는 Gearbox에서 별도로 보호해야 한다.

## 현재 등록된 실제 공개 참조

| 모듈 | 역할 | 참조 대상 |
|---|---|---|
| PTO | `legal_basis` | `pto-calculator/resources/legal-basis.json` (법령 검토 출처, 계산 공식 아님) |
| Worktime | 없음 | 등록된 JSON 정책 기본값 없음. 기존 코드의 기준을 JSON 파일인 것처럼 가장하지 않음 |
| Payroll | `pay_item_registry` | `payroll-calculator/resources/pay-item-registry.json` |
| Payroll | `operating_config` | `payroll-calculator/operating-config.json` |
| Payroll | `legal_policy_2026` | `payroll-calculator/resources/policy/2026.json` (2026년 전용) |

## 후속 작업

1. Common의 정책 참조 계약을 **각 모듈 입력 경계**에 연결. 계산 공식은 유지한다.
2. Common의 표준 산출물→입력 역할 Mapping 및 버전 계약 정리.
3. Gearbox Workflow에서 각 단계의 출력 파일을 다음 모듈 입력으로 전달하도록 정렬.
4. Agent/Gearbox 정책 정본·참조 조회와 보관·인증 경계를 연결하고 합성 E2E 검증.

## 테스트

`python -m unittest bhandara.tests.test_common_policy_reference -v`

테스트는 기본 경로 선택·참조 접근 제한·오류 시 차단을 확인한다. 법령 최신성이나 개별 회사 정책의 타당성을 보증하지 않는다.
