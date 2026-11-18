# Expiry & Carryover — 독립 만료·이월 판정 Module

현재 **순수 Python 계산 API 초기 구현**. Excel 입력/출력과 Tool/Gearbox 운영 연결은 아직 구현하지 않았습니다.

- API: `calculation.evaluate_expiry_carryover(balances, closing_id=..., balance_as_of=...)`
- Input: 외부에서 확정한 발생 건별 잔여, 유효기간 시작/종료일, `grant_id`·`employee_id`·`leave_type`.
- 기준일: `Closing-1.4-2025`처럼 회계분기 ID에서 자동 유도. `balance_as_of`는 계산 결과 기준일 일치 여부 검사입니다.
- 판정: 경계일 종료까지 남은 발생분이 유효기간 종료에 도달하면 만료, 이후까지 유효하면 이월, 잔여 0이면 잔여 없음, 유효 시작 전이면 미도래.
- 누락/오류 건은 계산 제외하고 이유 표기. 유효기간·발생량·권리 유불리 등을 자체 산정하지 않습니다.
- 이월은 새로운 발생이 아니며 기존 `grant_id`가 유지됩니다.
- 법정 연차 미사용수당은 **검토 필요 여부만** 표시합니다. 청구권 성립·지급 승인·사용촉진 면책은 자동 판단하지 않습니다.
- 발생분 사용 배정(`request_id` + `grant_id`)과 초과 사용분 음수 잔여는 Tool 내부 `../allocation.py`에서 계산하며, 이 Module은 배정하지 않습니다.

검증: `python3 -m unittest bhandara.tests.test_paid_time_off_allocation_expiry -v`
