# Payroll P3 — JSON 설정 기반 독립 Tool CLI

> **Payroll 계산 코어·회계 원가 모듈을 새로 만들지 않는다.** PR #77까지 병합된 계약/근태/초과근무/PTO/보험·세금 검토 Flow를 명시적 JSON 파일 참조로 딱 **한 번** 호출한다. 기존 **7개 개별 단일시트 Payroll XLSX**, Worktime \`WORKTIME\` 10열, PTO 독립 Tool, 단일 \`PAYROLL\` 시트 규격은 변경하지 않는다.

> **구현·검증·병합 완료(PR #78).** 이 문서는 **독립 CLI 사용 계약**이고, 서로 다른 Tool 간 Workflow 호출·Slack/Hermes 운영 연결은 **별도 미구현 작업**이다. 다음 진행 순서·안전 경계는 [운영 연결 1~4단계 인수인계](../OPERATIONS-HANDOFF-2026-11-20.md)에서 확인한다. **회사 비용 산정은 관리자용 산재보험료·확인분 출력까지만** 제공하고 이후 기업 인건비·회계 처리는 다른 모듈에 인계한다. 사용자 결정상 별도 50인 Golden E2E 필수 아님.

## 실행 (한 줄)

\`\`\`bash
mkdir -p bhandara/data/config
cp bhandara/payroll/config.example.json bhandara/data/config/payroll.json
# 개인 JSON에서 payroll_period, input_root/output_root, 파일 참조, steps를 지정
python3 run.py bhandara payroll
\`\`\`

설정 경로가 다르면 \`python3 run.py bhandara payroll --config /private/config/payroll.json\`을 사용한다. \`--period\`, \`--input-dir\`, \`--output-dir\` 같은 옵션은 신규 Tool에서 거절한다. 명령어를 매월 수정하지 않는다.

- \`schema_version="1.0", tool="payroll"\`
- \`payroll_period="YYYY-MM"\`: 정확히 한 달. 월 초·말은 날짜계산으로 구한다.
- \`run_id="auto"\`: 한국시간 기준 고유 실행 폴더. 직접 고정 ID도 가능하지만 **같은 ID 재실행은 중단하고 기존 산출물을 보존**한다.
- \`input_root\`: 신규 Payroll 7종 XLSX가 들어 있는 **상위 폴더**. 예를 들어 \`/private/hr/input\` 아래 \`payroll/pay-contract.xlsx\` 등.
- \`output_root\`: 원본과 다른 폴더. \`<output_root>/<run_id>/\`에 결과를 생성한다.
- \`steps\`: \`["review","output"]\` 또는 \`["review"]\`, \`["output"]\`. \`review\`는 경고·근거해시 요약 \`payroll-review.json\`, \`output\`은 기존 \`payroll-result.xlsx\`를 출력한다. 어느 경우나 **기존 통합 Flow를 한 번만** 계산한다.

## 파일 참조

[예시 설정](config.example.json)의 \`files\` 필드는 다음과 같다.

| 키 | 필수 | 의미 |
|---|---|---|
| \`worktime\` | 필수 | 이미 생성된 \`worktime-result.xlsx\` (Worktime 10열) |
| \`employee\` | 선택 | 공통 \`employee.xlsx\` 가입·미가입·적용 제외 정보 |
| \`pto_usage\`, \`pto_deduction\` | 함께 선택 | PTO 사용 내역 + 정확 차감수량 결과 |
| \`pto_closing\` | 선택 | **마감 확정** 자료가 있을 때만. 없으면 \`마감 전·변동 가능\` |
  
\`source_files\`는 **실행 설정 안에 원장 데이터를 복사해 쓰지 않고**, 외부 시스템에서 별도로 검증·작성한 JSON을 파일명으로 연결한다.

| 키 | 필수 | 내용 |
|---|---|---|
| \`settlement_plan\` | 필수 | 재직·계약별 기간 배정 승인 계획 JSON 객체 |
| \`attendance_plan\` | 필수 | Worktime SHA-256과 승인된 휴가/결근 지급처리 JSON 객체 |
| \`verified_work\` | 필수 | 외부 검증된 근로 구간 JSON 목록 (0건이면 \`[]\`) |
| \`approved_segments\` | 필수 | 승인 초과근무 구간 JSON 목록 (0건이면 \`[]\`) |
| \`evidence_registry\` | 필수 | 서로 독립인 출처 증빙 원장 대조 JSON 객체 |
| \`rate_policy\` | 필수 | 계약별 일급·분모 및 중복 가산 정책 JSON 객체 |
| \`rollup_policy\` | 필수 | 계약 단위 수당 원 단위 처리·합산 정책 객체 |
| \`pto_claims\` | PTO 사용 시 필수 | PTO 승인 상세 신청 JSON 목록 |
| \`pto_wage_plan\` | 선택 | 별도 승인된 신청별 기본급·고정수당 감액 |
| \`insurance_assessment_plan\` | 선택 | 외부 확인 보험별 기준소득·보수 및 적용 정책 |
| \`withholding_plan\` | 선택 | 항목별 과세·비과세와 근로/지방소득세 확정 금액 |
| \`industrial_assessment_plan\` | 선택 | 외부 확인 산재보험 사업주 부담 기준액·요율 |

대상 경로는 절대경로 또는 \`input_root\`에서 시작하는 상대경로다. 실제 JSON **내부 필드와 정책의 정본**은 각 모듈의 계약 [계약/근태](CONTRACT-SCOPED-OVERTIME.md) · [보험](INSURANCE-CANDIDATES.md) · [원천징수](TAX-WITHHOLDING.md) · [사업주 비용](EMPLOYER-INSURANCE.md)에서 확인한다. **P3는 새 정책 스키마를 만들지 않는다.**

외부 원장 **승인 근거 문자열 자체의 진위/권한 인증**은 아직 이 CLI가 보증하지 않는다. 입력 자료의 파일 SHA-256, 작업 중 수정 여부, 기간·직원·산정 정책의 일치 여부만 기존 검증 계약에 따라 검사한다.

## 결과와 후속 모듈 인계

- \`payroll-result.xlsx\` / **\`PAYROLL\` 시트 하나**: 지급항목별 미해당 공란/동적 열/잠정 지급합계·공제합계·차액, 필요한 소득세·보험료 검토 플래그.
- 관리자 열: 산재보험료(사업주) 및 **회사 비용(확인분)**. **세전 지급후보 + 산재보험만** 포함하는 *부분 합계*다. 향후 총인건비·회계 모듈이 급여대장의 이 항목을 가져갈 수 있다. Payroll에서 회사 원가계산을 더 확장하지 않는다.
- \`payroll-review.json\`: 근로자 수, \`NOT_APPROVED\`, 주제별 검토 요청, 회사 비용 범위와 합계, 각 입력 역할의 SHA-256. HR 원본 또는 승인 상세의 사본을 이 파일에 저장하지 않는다.

**직원 안내에는 이 관리자용 Excel 자체를 사용하면 안 된다.** 기존 \`build_employee_payroll_view()\`를 통해 해당 직원 행 및 급여 항목만 취한다. 산재보험료 등 회사 비용은 직원용 결과에서 제외된다.

**잠정 합계 != 지급승인.** 남아 있는 근거 검증, 법적 적정성 확인, 실제 보험/세금 신고, 실지급 확정, 자동 지급 등은 이 단계에서 다루지 않는다. 파일을 Slack/Hermes에 올려도 이 CLI가 자동 호출되지는 않는다. Gearbox 연결은 사용자 승인 전 \`agent-config\` PAUSE를 유지한다.

## 테스트

\`\`\`bash
python3 -B -m unittest bhandara.tests.test_payroll_json_tool_cli -v
python3 -B bhandara/_tests/run.py

# Hermes 서버 기능/인프라 호환성은 분리해서 실행
# python3 gearbox/_tests/run.py
# python3 gearbox/_tests/core_run.py
\`\`\`

합성자료에 대해서만 CLI를 검증한다. 같은 \`run_id\`로 이미 결과가 있으면 **덮어쓰거나 자동 삭제하지 않는다**. 기존 모든 금액 검증 코어/Reader/Writer는 유지한다.
