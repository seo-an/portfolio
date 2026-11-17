# Paid Time Off — Tool v3 재설계 (부분 구현)

`paid-time-off`는 한국 연차유급휴가를 대상으로 한 Bhandara의 새로운 업무 Tool입니다. 현재 2-2 이행 중이며, **아직 CLI로 실행하거나 실제 직원 파일을 계산하는 Tool이 아닙니다.** 기존 `pto-calculator`는 변경 없이 그대로 유지됩니다.

## 현재 가능한 것

독립 Python API 세 가지를 **합성 자료로** 테스트할 수 있습니다.

- `entitlement`: 입사일 기준 월별·연간 발생일 계산. 기간별 출근요건 판정 결과를 **반드시** 입력해야 하며, 근거 없으면 발생일수를 확정하지 않습니다.
- `eligibility`: 검증된 기간 집계에서 월 개근 및 연간 80% 출근율 판정. 증빙이 불완전하면 `UNDETERMINED`.
- `deduction-quantity`: 전일·반차·반반차·시간차 차감량 산정. 시간차는 회사 정책상 1일 시간을 명시해야 하며 누락 시 검토 상태가 됩니다.

`expiry-carryover`, `use-promotion`, `closing`은 폴더와 담당 범위만 정의한 **미구현 Module**입니다. 재설계 진행 사항과 상세한 미확정 요건은 [ARCHITECTURE.md](ARCHITECTURE.md)에서 확인하세요.

## 간단한 독립 API 예시

```python
from importlib import import_module

deduction = import_module("bhandara.paid-time-off.deduction-quantity")
result = deduction.calculate_deduction_quantity(unit="QUARTER_DAY")
assert result["quantity_days"] == "0.25"
assert result["approved"] is False
```

현재 입력 자료를 주고받는 파일·Tool Runner·명령어는 **아직 제공하지 않습니다**. `bhandara/data/input/`은 그대로 유지하며, 향후 Tool의 `input/`·`output/`은 공통 1세트만 사용합니다. 실제 직원 자료는 Git 체크아웃 밖에 보관해야 합니다.

## 개발자 검증

```bash
python3 -m unittest bhandara.tests.test_paid_time_off_v3_core -v
```

위 테스트는 독립 순수 API의 최소 계약만 검증합니다. 구형 PTO 통합 실행, 사용촉진·이월·마감·법적 지급·실제 Slack/Gearbox 호출 검증이 아닙니다. 사용자용 Excel 실행 RUNBOOK은 Tool 실행 기능 구현 후 제공할 예정입니다.
