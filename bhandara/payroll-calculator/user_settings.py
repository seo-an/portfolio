"""급여 계산기 단독 실행 설정 — 아래 문자열만 수정하세요.

별도의 JSON 설정 파일(--config)을 전달하면 이 파일을 읽지 않습니다.
기본 입력 파일은 bhandara/data/input/에 저장합니다.
회사 정책·Worktime 계산 결과는 명시적 입력 파일이며 자동 승인되지 않습니다.
"""

PERIOD = "2026-07"  # 계산 대상 월 (YYYY-MM)

EMPLOYEES_FILE = "common/employee.xlsx"
IDENTITY_FILE = "common/id-map.xlsx"
CONTRACTS_FILE = "payroll/pay-contract.xlsx"  # 있을 때 계약금액 방식 사용
COMPENSATION_FILE = "payroll/compensation.xlsx"  # 계약금액 파일 없을 때만 사용
PAYROLL_INPUT_FILE = "payroll/payroll-input.xlsx"
COMPANY_POLICY_FILE = "payroll/company-policy.json"
WORKTIME_RESULT_FILE = "payroll/worktime-result.json"
