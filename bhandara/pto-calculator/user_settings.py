"""PTO 단독 실행용 사용자 설정 — 아래 문자열만 수정하세요.

별도의 JSON 설정 파일(--config)을 전달하면 이 파일을 읽지 않습니다.
기본 입력 파일은 bhandara/data/input/에 저장합니다.
"""

PERIOD = "2026-07"  # 계산 대상 월 (YYYY-MM)

EMPLOYEES_FILE = "common/employee.xlsx"
SCHEDULE_FILE = "pto/work-schedule.xlsx"
ASSIGNMENTS_FILE = "pto/work-schedule-assignment.xlsx"
EVENTS_FILE = ""  # 선택 파일: 비워두면 기본 경로의 파일이 있을 때만 사용
