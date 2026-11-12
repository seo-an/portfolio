# PTO 실무 혼합 사례 — 실제 제공 Excel (14명)

이 폴더는 **실제 내려받아 열어보고 계산기에 입력할 수 있는 샘플 파일**을 보관합니다.
`generate_review_cases.py`를 실행해야만 나타나는 임시 파일이 아닙니다.

## 어디부터 열어보나요?

1. [case-index.xlsx](case-index.xlsx) — 직원 14명의 `employee_id`, `case_id`, 사례 설명, 예상 **검토 동작**을 확인합니다.
2. [input/employee.xlsx](input/employee.xlsx) — 위 직원 ID들이 무작위 순서로 섞여 있습니다. 추가 열 `case_id`는 설명용이며 계산기가 무시합니다.
3. [input/work-records/2025-2026-schedule.xlsx](input/work-records/2025-2026-schedule.xlsx)와 [input/work-records/2025-2026-attendance.xlsx](input/work-records/2025-2026-attendance.xlsx) — 정상 근태와 경계 사례가 같은 파일에 혼합되어 있습니다.
4. [input/employee-events.xlsx](input/employee-events.xlsx) — 확정 결근·병가·육아휴직·단축근로 이벤트를 확인합니다.
5. [config.json](config.json) — 위 파일 경로, 계산기간(`2025-01-01`~`2026-01-31`)이 이미 설정되어 있습니다.

전체 파일이 필요하면 GitHub에서 `examples/sample/` 디렉터리가 들어 있는 저장소 ZIP을 다운로드하세요.

## 실행

```bash
python run.py bhandara pto-calculator \
  --config bhandara/pto-calculator/examples/sample/config.json \
  --input-dir bhandara/pto-calculator/examples/sample/input \
  --output-dir /tmp/pto-sample-output
```

일부 사례는 불확실한 자료를 의도적으로 포함합니다. 이 경우 `REVIEW_REQUIRED`와 종료 코드 `1`이 발생할 수 있으며, 그것이 사례의 목적입니다.

## 주의

- 모든 직원은 합성 ID이며, 실제 사원정보·급여·승인 이력은 포함하지 않습니다.
- 샘플은 **법령의 절대적 정답표가 아닙니다.** `case-index.xlsx`의 예상 동작도 검토 가설입니다.
- 반복 생성 코드는 [../generate_review_cases.py](../generate_review_cases.py)에 보관합니다. 생성 결과를 일회성으로 지우지 않고 이 폴더에 별도 배포합니다.
- 현행 및 과거 법령의 적용 시점은 [법령 근거 기록](../../resources/legal-basis.json)을 확인해야 합니다.
