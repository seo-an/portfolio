# Bhandara 레거시 철수 게이트 (운영 연결 완료 후)

> **현재 상태(2026-11-20): 구형 계산기 미삭제.** 신규 `paid-time-off`·`worktime`·`payroll`은 PR #78까지 독립 JSON Tool CLI를 구현·검증·병합했다. 그러나 실제 Gearbox/Hermes·Slack 신규 Tool 호출은 아직 `NOT_CONNECTED`이고 `agent-config`는 사용자 요청으로 `PAUSE`다. **서버 정리는 나중에 한 번에** 진행한다.

**최신 4단계 운영 인수인계:** [`OPERATIONS-HANDOFF-2026-11-20.md`](OPERATIONS-HANDOFF-2026-11-20.md)

## 철수 대상과 남아 있는 의존

- 기존 `pto-calculator`, `worktime-calculator`, `payroll-calculator`, 구형 `run.py` 라우팅·설정·샘플·전용 테스트/문서 중 신규 Tool에서 사용하지 않는 부분.
- Gearbox와 Hermes의 **현재 운영 호출 경로**. `portfolio`의 신규 CLI 병합이 이 호출 경로를 자동으로 바꾸지는 않는다.
- 구형 Worktime JSON과 신규 Worktime 10열 Excel은 동일 계약이 아니므로 **경로만 바꿔 끼우지 않는다**.
- 신규 Tool과 Common이 계속 사용하는 라이브러리·Reader·ID/보안업체 매핑은 구형 폴더에서 사용한 적이 있어도 **실제 의존을 확인하기 전 삭제 금지**.
- 현재 공개 합성 샘플 중 구형 규격에 속한 파일은 신규 7개 Payroll 입력으로 오인하지 않는다. 파일 형식 이관 여부를 별도로 확인한다.

## 철수 순서 (필수 게이트)

| 단계 | 요구되는 사실 | 현재 상태 |
|---|---|---|
| 1. 신규 Tool 독립 CLI 준비 | 세 Tool의 JSON 설정과 계산·출력·단독 테스트 | **완료** (#78까지 사용자 서버 테스트/병합) |
| 2. Workflow 인계 | 정확한 호출 순서, 결과 파일·승인 JSON·기간/해시 인계 및 오류 차단 | **미구현** |
| 3. Gearbox/Hermes 운영 전환 | 사용자 재개 승인, 신규 Tool 선택·권한·Slack 응답·호환성 검증 | **PAUSE / NOT_CONNECTED** |
| 4. 운영 안정성 | 업로드 ACK와 후속 새 메시지 응답 분리, 삭제·만료/재시도/오류 회신을 합성자료로 확인 | **미검증** |
| 5. 구형 참조 인벤토리 | 실행 코드·설치·문서·샘플·Gearbox·프로필의 마지막 구형 참조 검색 | **시행 전** |
| 6. 단계별 제거 PR | 구형 Tool별 호출 이전 → 사용자 서버 회귀 확인 → 일반 PR 병합 후 제거 | **차단** |
| 7. 서버 정리/배포 | 사용자 요청 시 일괄 적용·롤백 확인 | **후순위** |

**50명 Golden E2E를 신규 필수 게이트로 두지 않는다.** 기존 단독/통합 `unittest`와 실제 변경된 계약의 표적 합성 회귀, Bhandara 전체 테스트와 Gearbox 기능·인프라 호환성 검증으로 판단한다. Golden 비교는 특정 차이가 있을 때 **선택적인 진단 방법**일 뿐, 자동 착수할 별도 개발 트랙이 아니다.

## PR 방식과 보호 범위

1. 구형 Tool별 **독립 브랜치 → 일반 PR**. Draft PR·worktree·서버 Git push 요구 금지.
2. 코드 변경은 그 Tool에 실제 호출/의존이 남지 않았다는 근거를 확인한 뒤 수행. **삭제를 먼저 하고 테스트를 고치는 방식 금지**.
3. Bhandara `bhandara/_tests/run.py`, Gearbox `gearbox/_tests/run.py`, 인프라 `gearbox/_tests/core_run.py` 및 모듈 버전 호환성 테스트 필수.
4. 사용자 서버의 PR 브랜치를 직접 당겨 검증하고 사용자가 병합. 이 문서 PR에서는 서버·런타임·레거시 파일을 변경하지 않는다.
5. 실직원/급여 원본, 운영 백업/캐시, 승인 JSON은 코드 철수 PR에서 직접 조작하거나 공개하지 않는다.

## 다음 액션

- **먼저 [운영 연결 Stage 1](OPERATIONS-HANDOFF-2026-11-20.md#1-단계--portfolio-tool-간-workflow-연결)**을 완료한다.
- Stage 2 `agent-config` 변경은 사용자에게 명시적 재개 지시를 받은 뒤에만 진행한다.
- Stage 3 후속 검토 요청·Slack 회신 문제의 합성자료 E2E 통과 뒤 Stage 4 구형 제거를 시작한다.
- **서버 branch cleanup/이미지 배포/파일 정리는 사용자가 지정한 후속 일괄 작업**으로 남긴다.
