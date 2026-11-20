# Payroll — 최신 상태 및 운영 연결 우선순위 (2026-11-20)

> **독립 Payroll Tool CLI 구현·검증 완료(PR #78까지 사용자 서버 테스트·병합).** 더 이상 P0~P3를 미구현으로 표시하거나, 새로운 50명 Golden E2E를 운영 연결의 필수 전제로 요구하지 않는다. 다음 작업의 정본은 [Bhandara 운영 연결 1~4단계 인수인계](../OPERATIONS-HANDOFF-2026-11-20.md)다.

## 구현·병합 완료

| 영역 | 현재 제공하는 기능 | 정본 |
|---|---|---|
| Payroll 입력 | 독립 7개 XLSX, 직원 계약/수당·성과급·공제율 매핑, 기간·ID/중복 검증 | [`input-files.json`](input-files.json) |
| Worktime 연계 | `worktime-result.xlsx` 10열 사실 검토, 외부 검증 구간/승인과 계약별 초과근무 후보 | [`CONTRACT-SCOPED-OVERTIME.md`](CONTRACT-SCOPED-OVERTIME.md) |
| PTO 연계 | 확정 Closing 또는 현재 기준일 자료로 복수 휴가 대조, 별도 승인 원 단위 감액·중복차감 방지 | [`PTO-CLOSING-REVIEW.md`](PTO-CLOSING-REVIEW.md) |
| 보험/원천징수 | Common 취득일·공란(적용 제외)·미가입, 근로자 부담 보험, 항목별 과세·비과세/외부 원천세 후보 | [`INSURANCE-CANDIDATES.md`](INSURANCE-CANDIDATES.md) · [`TAX-WITHHOLDING.md`](TAX-WITHHOLDING.md) |
| 사업주 산재보험 | 관리자용 산재보험료·회사 비용(확인분) 표시만 수행. 전체 인건비/회계 계산은 다른 Tool의 미래 책임 | [`EMPLOYER-INSURANCE.md`](EMPLOYER-INSURANCE.md) |
| Payroll Output | `PAYROLL` 한 시트/2단 헤더, 동적 항목/미해당 공란, **계산된 항목의 잠정 합계**, 미확인 보험·소득세 검토요청 | [`OUTPUT-CONTRACT.md`](OUTPUT-CONTRACT.md) |
| 독립 Tool 실행 | JSON 설정 → 기존 Payroll 검토 Flow 1회 → `payroll-result.xlsx` + 선택 `payroll-review.json`, 원본 SHA·덮어쓰기 방지 | [`TOOL-CLI.md`](TOOL-CLI.md) |

정식 지급·송금·세무 신고·원본 승인권한 인증은 구현됐다고 주장하지 않는다. `NOT_APPROVED` 상태는 유지하며 외부에서 확정한 정책·원천징수액을 코드가 임의로 재산정하지 않는다.

## 남은 작업 — 계산기 확장이 아니라 운영 연결

1. **Stage 1 / Portfolio Workflow:** `paid-time-off`와 `worktime` 실행결과를 `payroll` 설정의 정확 경로·기간·해시로 인계하고, 부족한 승인 JSON은 명시적으로 요구한다. 내부 모듈의 별도 재구현·중복 계산기·`flow/` 물리 폴더를 만들지 않는다.
2. **Stage 2 / Gearbox·Hermes·Slack:** **사용자의 명시적 `agent-config` 작업 재개 승인 후** 인증된 새 명령을 신규 Tool CLI에 연결한다. 업로드만 하면 정형 ACK를 반환하는 기존 보안 동작은 유지하고, 다중 첨부를 임의 선택하지 않는다.
3. **Stage 3 / 운영 안정화:** 새 검토 요청에 후속 답변이 없는 현상은 업로드 ACK 정상 동작과 별개로 합성파일 재현. 권한 영수증·TTL·삭제/수정 이벤트·실패 응답·회신 경로를 확인한다. 기존 파일 보관 24시간/인증 근태 검토 최초 캐시부터 3시간의 **선택적 정책**을 무단 변경하지 않는다.
4. **Stage 4 / 레거시 철수:** 새 Tool의 운영 호출·Gearbox 호환·문서/샘플 경로가 확인되면 `pto-calculator`, `worktime-calculator`, `payroll-calculator`를 **각각 별도 PR**로 이전/제거한다. [철수 게이트](../LEGACY-RETIREMENT.md)를 확인한다.

**사용자가 확정한 제외 범위:** 별도 50명 Golden E2E 전용 체계, Payroll 내부 추가 회사 총인건비 분석, 새로운 DB/상시 서버, 임의의 법적 급여 승인, 현재 서버 정리.

## 운영 차단 조건

- **`agent-config` 수정·배포 PAUSE**: 사용자 재개 지시 없이는 코드를 변경하지 않는다.
- **NOT_CONNECTED**: Payroll 독립 CLI 병합은 Slack 실자료 계산 연결 완료를 의미하지 않는다.
- **개인정보**: 실제 인사/급여 원본·계산결과를 공개 Git에 넣거나 일반 로그에 기록하지 않는다.
- **불명확한 승인**: Worktime 사실을 승인 초과근무로 추정하거나 PTO 마감 전을 확정으로 승격하지 않는다.
- **자료 누락**: 인증된 원본·필수 JSON·실행 기간/경로가 누락되면 성공으로 보고하지 않는다.
- **서버 cleanup 및 운영 배포**: 사용자 요청대로 **나중에 한 번에** 처리. 현재 문서 PR에서는 수행하지 않는다.

## 변경 검증 기준

```bash
# Bhandara 전체 unittest: 주제별 PASS/FAIL/ERROR/SKIP 요약
sudo docker exec -w /opt/agent-config/.external/portfolio \
  hermes /opt/hermes/.venv/bin/python -B bhandara/_tests/run.py

# Gearbox 기능/인프라 회귀 — 버전 변경 시 반드시 함께 확인
sudo docker exec -w /opt/agent-config \
  hermes /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py
sudo docker exec -w /opt/agent-config \
  hermes /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

위 명령은 **향후 코드/운영 연결 PR의 검증 안내**이며 현재 자동 실행한 기록이 아니다. Git 작업은 `branch → unittest → 일반 PR → 사용자 서버에서 해당 브랜치 직접 테스트 → 사용자 merge`. Draft/worktree/서버 push 지시 금지.

**바로 다음 대화에서 Stage 1부터.** 상세 입력·인수인계·중단 조건은 [운영 연결 인수인계](../OPERATIONS-HANDOFF-2026-11-20.md)를 우선한다.
