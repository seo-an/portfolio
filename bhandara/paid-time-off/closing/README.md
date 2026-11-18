# Closing — PTO 분기 마감보고

상태: 순수 계산 API와 독립 Excel runner 1차 구현. Gearbox/Slack 운영 연결은 아직 없음.
Closing은 기존 Entitlement, Deduction Quantity, Allocation, Expiry/Carryover 결과만 집계합니다. 정책·권리·만료일·수당 지급 여부를 다시 결정하지 않습니다.

## 마감 ID와 범위

- Closing-1.4-2026: 1~3월, 3월 31일
- Closing-2.4-2026: 1~6월, 6월 30일
- Closing-3.4-2026: 1~9월, 9월 30일
- Closing-4.4-2026: 1~12월, 12월 31일
- 기초이월잔여일수는 연초에 인계한 잔여(연초 미상계 부족 포함)로 고정하며 직전 분기 말 잔여로 대체하지 않습니다.
- 마감된 월에 사용량이 없으면 0, 미도래 월은 공란입니다.

## 출력: closing-result.xlsx

사용자가 제출한 예제의 A~V열 순서를 유지합니다.
employee_id | name | 발생연차일수 | 기초이월잔여일수 | 대휴발생일수 | 총확보휴가일수 | 미사용만료일수 | 1월~12월 | 누적사용일수 | 마감잔여일수 | 마감상태

- 총확보휴가일수 = 발생연차일수 + 기초이월잔여일수 + 대휴발생일수
- 마감잔여일수 = 총확보휴가일수 - 미사용만료일수 - 누적사용일수. 실제 음수값을 보존하고 Excel에서는 (3)처럼 보이게 합니다.
- 이전 분기 마감보고서를 재활용할 때 이전 집계량과 이번 분기 증감분만 결합하고 이미 마감한 사용량을 다시 합산하지 않습니다.
- 마감상태 우선순위: 자료확인 필요 > 초과사용 > 사용촉진 검토 > 정상. 3분기 사용촉진은 외부 검토 결과 Y/N에만 의존합니다.
- 3분기 사용촉진 외부 판정자료가 없거나 일부 직원이 빠졌으면 자료확인 필요. Closing이 사용촉진 법정 요건을 판단하지 않습니다.

출력에는 읽기 쉬운 마감보고 외에 인계자료·미상계부족·_수량정본 3개 숨김 시트를 둡니다. 이는 재계산용 중복 원장이 아니라 정확한 분수와 발생 ID를 다음 분기에 전달하는 스냅샷입니다.
인계자료는 발생 건별 잔여 0까지 기록하며 이미 만료된 건은 0으로 넘깁니다. 미상계부족은 신청 ID별 미상계 잔여입니다.
정책정보는 항상 마지막에 위치하고 최초 출력 확정여부=미확정입니다. 외부 검토·승인을 거쳐 명시적으로 확정해야 다음 분기 입력으로 활용할 수 있습니다.

## 독립 호출

python3에서는 bhandara.paid-time-off.runner_closing.run_closing을 importlib로 불러 호출할 수 있습니다.
필수 입력: closing_id, policy_id, run_id, usage_file, employee_file.
조건부 입력: previous_closing_file(같은 해 직전 분기의 확정 Closing이 기초일 때), promotion_file(3분기 외부 사용촉진 검토 Y/N), output_root.
usage_file은 현행 run_usage_ledger에서 출력한 파일이어야 하며 사용요약, 사용상세, 만료이월, 숨김 _발생자료 및 정책정보가 있어야 합니다.
employee_file은 common/employee.xlsx의 재직자·퇴사자 시트 및 employee_id, name 열을 사용하며 이름 누락은 자료확인 필요로 남깁니다.
promotion_file은 검토결과 시트 employee_id, review_required (Y/N) 열을 사용합니다.
기존 확정 Closing은 정책정보의 참조 ID와 확정여부=확정을 확인합니다.
사용권 만료가 자동으로 미사용수당 지급 확정을 의미하지 않습니다. 외부 확정 상계 지시를 처리하는 별도 API는 만들지 않습니다.

검증: python3 -m unittest bhandara.tests.test_paid_time_off_closing_excel -v
전체: python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
