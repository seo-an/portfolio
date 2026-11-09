# PTO Calculator — 공개 독립 실행 모듈 v0.1.0

**기능:** 기존 Gearbox PTO의 **입사일 기산(anniversary-basis) 연차 발생 기록**을 로컬 Excel 입력으로 계산한다. 1년 미만의 월별 발생, 1년 이상 연차 발생, 근무 스케줄·근태·승인 이벤트에 따른 **출근율 충족 여부가 불확실한 항목**을 검토용으로 표시한다.

**계산하지 않는 것:** 회계연도 기준 연차 정산, 휴가 사용 잔액, 퇴직 정산·수당, 임금 지급 승인, 법률 적합성 확정, 근태 마감. 이 엔진의 과거 정책·계산식을 자동으로 개선했다고 주장하지 않는다.

**현재 상태 (2026-11-09):** 공개 PTO v0.1.0은 [portfolio PR #4](https://github.com/seo-an/portfolio/pull/4)로 **병합 완료**했다. Hermes Python 3.14.9에서 전체 60/60 `unittest` PASS, 2026-07 합성 직원 3명(E001·E005·E020)의 Golden 비교도 **`PTO_GOLDEN_PASS`**로 확인됐다. [agent-config PR #144](https://github.com/seo-an/agent-config/pull/144)의 **PTO Preview Adapter**도 별도 병합·합성 CLI 연동 검증을 완료했다. 단, **기존 PTO 운영 Pipeline은 그대로 유지 중이며 Hermes Tool/Slack 등록은 아직 없다**. Golden 일치는 해당 합성 데이터의 동등성만 의미한다.

## 필요한 환경

- Python 3.12 이상(코드 문법 하한; 실서버 검증 대상은 Python **3.14.9**).
- 같은 Hermes 실행환경에 포함된 **openpyxl 3.1.5**, **korean-lunar-calendar 0.4.0**.
- 공개 Portfolio 루트에 설치 환경과 모든 모듈이 함께 존재해야 한다. Hermes·Slack·Google Drive·OAuth·GitHub 인증은 실행에 필요 없다.

Portfolio 루트에서 일반 사용자 환경을 준비한다.

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
```

## 1. 입력 Excel 준비

기본 입력 위치는 `bhandara/data/pto-calculator/input/`. 이 폴더 전체는 Git에서 제외된다. 직접 입력·출력 경로를 지정하는 것이 가장 안전하다.

필수 파일은 **`employee.xlsx`**, **`work-schedule.xlsx`**, **`work-schedule-assignment.xlsx`**다. 월별 스케줄과 출퇴근 기록은 해당 기간에 필요할 때 지정하며, 승인 이벤트 파일도 선택 사항이다. 아래 표는 기존 PTO 입력 준비 단계에서 읽었던 **정확한 헤더**다. 열 순서는 자유롭고, **추가 열·빈 추가 헤더가 있어도 무시**한다.

| 파일 | 선택하는 헤더 |
|---|---|
| `employee.xlsx` | `employee_id, hire_date, termination_date, work_system` |
| `work-schedule.xlsx` | `schedule_id, work_system, sequence, day_type, shift_code, start_time, end_time, break_min, scheduled_work_hours, note` |
| `work-schedule-assignment.xlsx` | `employee_id, schedule_id, effective_from, effective_to, cycle_anchor_date, start_sequence, note` |
| `work-records/2026/2026-07-schedule.xlsx` | `employee_id, work_date, schedule_id, shift_code, scheduled_start, scheduled_end, break_min, scheduled_work_hours, day_type, note` |
| `work-records/2026/2026-07-attendance.xlsx` | `employee_id, work_date, clock_in, clock_out, break_min, source, note` |
| `employee-events.xlsx` (선택) | `request_id, employee_id, event_type, event_date, unit, status, note` |

시트는 각 파일의 **활성 시트**를 사용한다. 모든 헤더가 존재해야 하지만, 선택한 셀 가운데 비어도 되는 곳(예: `termination_date`, `note`)은 허용한다. 최소 필수값은 [module.json](module.json)의 `required_values`를 참조한다. 날짜는 `YYYY-MM-DD` 또는 Excel 날짜 셀, 시간은 Excel 시간 또는 `HH:MM` 형식을 사용한다. 수식은 계산하지 않으며 입력 수식 셀이 있으면 해당 행을 오류 처리한다.

## 2. 실행 설정

[config.json](config.json)을 로컬 데이터 영역에 복사해 원하는 기간, 입력 파일명, 직원 허용 목록을 편집한다. `employee_allowlist: []`는 **전체 직원**, `["E001","E005"]`는 지정된 직원만 처리한다. 지정한 파일은 `--input-dir` 내부의 상대경로로만 읽는다.

## 3. CLI 실행

```sh
.venv/bin/python run.py bhandara pto-calculator \
  --config /private/pto/config.json \
  --input-dir /private/pto/input \
  --output-dir /private/pto/output
```

옵션을 생략하면 저장소의 예시 `config.json`과 Git 무시 대상인 `bhandara/data/pto-calculator/{input,output}`을 사용한다. Windows는 `.venv\Scripts\python.exe`를 사용한다.

종료 코드: `0=PASS`(검토 항목 없음), `1=REVIEW_REQUIRED`, `2=ERROR`(일부 직원 오류 또는 전역 입력 차단). **0도 법률·지급·최종 결재가 아니다.**

## 4. 산출물

동일 실행에서 아래 네 파일에 같은 충돌 회피 번호 `(1)`, `(2)` 등이 적용된다.

- `pto-result.json`: 계산 기간, 입력 SHA-256, 직원별 원본 발생 결과, 검토/오류 상태, `approved=false`, `finalizable=false`
- `pto-review.json`: 영향 범위별 입력·검토 Finding(원본 값 대신 코드·행·열)
- `pto-result.xlsx`: Summary, Grants, Unresolved, Review Required. **정확한 수치의 기준은 JSON**이며 XLSX는 사람 검토용
- `pto-run.json`: 실행 ID, 모듈 버전, 원본/출력 SHA-256, 발견된 문제. 결재 영수증이 아님

원본 입력은 변경하지 않는다. 인식할 수 있는 직원별 오류는 해당 직원의 결과를 제외하고 다른 직원은 계속 계산한다. 소유자를 식별할 수 없는 전역 스케줄 오류처럼 영향 범위를 특정할 수 없으면 계산을 중단하고 오류로 표시한다. **오류를 0일로 대체하지 않는다.**

## 합성 데이터로 시험해 보기

```sh
.venv/bin/python bhandara/pto-calculator/examples/generate_demo.py \
  --output-dir /tmp/bhandara-pto-demo

.venv/bin/python run.py bhandara pto-calculator \
  --config /tmp/bhandara-pto-demo/config.json \
  --input-dir /tmp/bhandara-pto-demo/input \
  --output-dir /tmp/bhandara-pto-demo/output
```

이 예제의 `E001`과 `E005`는 **가상 직원**이다. 출근율 확인 자료가 부족한 과거 기간에는 `REVIEW_REQUIRED`가 나오는 것이 정상일 수 있다.

## 원본 Gearbox와의 관계

원본: `seo-an/agent-config` commit `296f909dd84bbdb6196be84568bd0e60775c7dbd`의 `gearbox/gear/pto-calculator/run.py` 및 `functions/*.py`. 계산식·정책 파일 내용은 그대로 옮기고 import만 공개 모듈 경계로 변경했다. 원본의 `gearbox.core`와 진단 계약도 동일 동작의 공개 공통 함수로 대체한다. 새 Excel 입력·검토·출력 경계는 원본 Tooth와 의미가 같다고 **가정해서는 안 되며**, 비공개 합성 Golden 비교로 확인해야 한다.

**주의:** 현재 `agent-config`의 원본 Gearbox는 여전히 기존 경로에서 운영된다. 양쪽의 전환·중복 제거는 별도 승인과 테스트 후 진행한다.

## 검증 기록 — 기존 비공개 PTO Golden 대조 (2026-11-09 PASS)

서버의 **원본 합성 fixture와 비공개 Golden**은 Git에 복사하지 않는다.
수치/검토 결과는 다음 게이트에서 대조하며, 출력에는 값이 아닌 차이 경로만 보인다.

```sh
/opt/hermes/.venv/bin/python \
  /opt/agent-config/.external/portfolio/bhandara/pto-calculator/examples/verify_private_golden.py \
  --fixture-root /opt/agent-config/gearbox/_tests/gear/pto-calculator/fixtures/common \
  --baseline /tmp/bhandara-pto-phase0-n_fy3m6k/pto-golden.json
```

2026-11-09 Hermes 서버에서 실제 **`PTO_GOLDEN_PASS: synthetic E001/E005/E020 July 2026 parity`**를 확인했다. 재검증할 때도 `PTO_GOLDEN_PASS`가 나와야 해당 합성 Golden과 입력 해시·기간·직원별 결과가 동등하다.
기존 실행의 `source_hashes`가 다른 파일을 가리키거나 Golden 형식이 확인되지
않으면 `PTO_GOLDEN_INVALID`로 중단한다. 비공개 Golden이 컨테이너에서 지워졌다면
호스트 보존본을 검증한 뒤 먼저 다시 복사한다.

### Gearbox Adapter 연동 결과 (2026-11-09)

- Private `agent-config` PR #144 merged the opt-in Adapter at `gearbox/adapters/bhandara/pto.py`; the old PTO pipeline was not modified.
- 실제 Hermes 컨테이너에서 합성 Excel 2명에 대해 Adapter가 공개 PTO CLI를 호출한 결과: `status=PASS`, `calculated_employee_count=2`, `processed_employee_count=2`, `finding_count=0`, `approved=false`, `finalizable=false`.
- Adapter의 출력 경로는 Hermes 컨테이너 `/opt/data/bhandara/runs/pto-preview-<id>/output/`이며, 호스트에서 대응하는 경로는 `/opt/agents/data/hermes/bhandara`이다. Excel 원본·직원별 JSON을 공개 Git/Slack으로 업로드하지 않는다.
- **미구현:** Hermes Tool/Slack 노출, 기존 PTO Gearbox Pipeline 교체, Worktime/Payroll 공개 모듈 이전.
