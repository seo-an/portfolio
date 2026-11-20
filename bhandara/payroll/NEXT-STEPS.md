# Payroll 이후 운영 연결 — 남은 작업

2026-11-20 현황: Payroll 독립 Tool의 7종 Excel Reader·계산 검토·동적 PAYROLL·단독 JSON CLI와 **Portfolio Workflow**까지 구현돼 있다. **별도의 급여 계산 코어, 50인 Golden E2E, 회사 총인건비 계산기를 여기서 확장하지 않는다.**

## 진행 상태

| 내용 | 상태 |
|---|---|
| 신규 세 Tool 구현·통합 Workflow | **완료** (#80 병합) |
| Portfolio의 과거 실행 코드·샘플·문서 정리 | **PR #81 검증 대기** |
| Gearbox/Hermes·Slack 신규 Tool 연결 | **미진행 — agent-config 편집 PAUSE** |
| 업로드 ACK 이후 새 요청 무응답 재현·수정 | **미진행** |
| 운영 캐시 TTL·다중 첨부·권한·합성 E2E | **미진행** |
| 서버 브랜치·캐시 정리와 배포 | **별도 사용자 지시 후 일괄 처리** |

## 다음 우선순위: Stage 2·3을 함께 진행

1. 사용자의 `agent-config` 편집 **재개 승인**을 받은 후 별도 브랜치·PR에서 신규 Tool 3개와 Workflow 호출 경로 연결.
2. Slack 인증 업로드 후 ACK만 보내고, **새로운 명시적 `&` 검토 댓글**에서만 입력 권한·파일 역할·TTL을 검증하고 Tool 실행.
3. 실직원 자료가 아닌 **합성 파일**로 다중 첨부, 구분된 승인, 원장 검토, 사용자의 스레드 회신, 오류·만료·삭제/수정 차단 및 무응답 방지 테스트.
4. Gearbox 기능 테스트 `python3 gearbox/_tests/run.py`, 인프라 `python3 gearbox/_tests/core_run.py`를 분리해 검증.
5. 서버 적용·배포는 사용자 별도 승인 뒤 진행. 브랜치·캐시·이미지 정리는 나중에 일괄 수행.

Payroll의 잠정 급여합계는 **지급 확정이 아니고**, 사업주 산재보험료는 근로자 지급·공제 총계에 합치지 않는다. 실제 신고·송금·완전한 비용회계는 범위 밖이다.

[전체 운영 인수인계](../OPERATIONS-HANDOFF-2026-11-20.md) · [Stage 1 Workflow](../WORKFLOW.md)
