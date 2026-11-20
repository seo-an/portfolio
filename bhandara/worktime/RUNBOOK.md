# Worktime 사용·검증 실행서 (신규 세 Module, 2026-11-19 / PR #57 병합)

**현재:** Worktime의 검증·10열 Excel·JSON Tool CLI·Portfolio Workflow는 구현되었습니다. Gearbox/Hermes·Slack 운영 호출·실자료 사용은 별도 승인 후 검증합니다.

## 1. 어떤 기능이 어디에 있나요?

| 기능 | 경로 | 현재 역할 |
|---|---|---|
| Schedule | `worktime/schedule/` | 근무 예정일/휴무일과 근태장부 **기록 존재 여부** 대조 |
| Attendance Verification | `worktime/attendance-verification/` | 장부↔출입기 증빙, 스케줄 대비 출근·퇴근 **부호 있는 시각 차이** 보존 |
| Worktime Compliance | `worktime/worktime-compliance/` | 확인된 근로·휴게 사실의 기준 적합성, **확인 휴게−필수 휴게** 차이 보존 |
| 보안업체 원본 해석 | `worktime/vendor_adapters/` | CAPS·세콤·KT텔레캅 제공 예제에 맞춘 원본 열/시각/식별자 변환 |
| 표준 출입기 Excel | `worktime/access_source.py` | 모든 업체에 동일한 `access-events.xlsx` v0.2 작성·읽기·검증 인계 |
| 스케줄 매핑 | `worktime/schedule/mapping.py` | `work-schedule.xlsx`의 `SCHEDULE MAP`·`ASSIGNMENTS` 읽기 |
| 단일 결과 | `worktime/output.py`·`output_excel.py` | 소정·실제·출근Δ·퇴근Δ와 외부 근태/휴가 참조를 한 시트에 기록 |

**Attendance Detection은 삭제한 기획**이며 별도 Module이 없습니다. 근무 종류나 지각·조퇴·야근을 시각 차이만으로 확정하지 않습니다.

## 2. 자료별 의미

- **근무 스케줄:** 해당 날짜에 근무가 예정되어 있었는지, 기준 출퇴근 시각이 무엇이었는지. 근무제도·휴일·승인된 변경사항은 별도 정본이 필요합니다.
- **근태장부:** 기록된 출퇴근 시각과 외부 입력 사유(`clock_in_reason`, `clock_out_reason`). 근로 수행·휴게 보장의 최종 증빙으로 간주하지 않습니다.
- **출입기 원본:** 업체가 기록한 출입/인증 사실. `세트(경비시작)`와 실패 기록은 제외 이력에 남기고 후보에서 제외합니다. 같은 사람·같은 날 일반 출입만 있으면 첫/마지막 유효 기록을 **미확정** 출퇴근 후보로 잡습니다.
- **실제 근로·휴게 자료:** 별도로 검증한 `worked_min`, `rest_min`, 증빙과 범위. 임의의 출입기 IN/OUT을 실제 근로 또는 자유 휴게로 단정하지 않습니다.

## 3. 주요 출력과 차이 계산

| Module | 비교 | 계산 예 |
|---|---|---|
| Schedule | 근무 예정일과 장부 유무 | 근무 예정+장부 있음 `WORK_MATCH`; 휴무+장부 있음 `UNSCHEDULED` |
| Attendance Verification | 장부 시각 − 예정 시각 | 09:00 예정·08:40 장부 출근: **-20분** |
| Attendance Verification | 출입기 시각 − 예정 시각 | 18:00 예정·18:16 출입 후보: **+16분** (미확정 출입 후보) |
| Attendance Verification | 출입기 시각 − 장부 시각 | 출처 간 차이(초 단위 정확성도 보존) |
| Worktime Compliance | 확인된 휴게 − 필수 휴게 | 필수 60분·확인 45분: **-15분**; 확인 90분: **+30분** |

`time_deviations.clock_in/clock_out`과 `daily[].rest_deviation`은 **차이의 방향과 크기**를 보존하는 것이지, 승인된 연장근무시간·수당·법적 위반 최종 판정이 아닙니다. 근태장부에 이유가 없다면 사유는 `null`입니다.

## 4. 업체 Excel 정규화

업체별 원본 형식이 달라도 출력은 모두 **같은 Excel**입니다.

```text
CAPS / SECOM / KT_TELECOP 원본
  → 업체별 헤더·코드 해석
  → 부서+사번(사원번호) 기반 Common 직원 식별자 연결
  → 경비 세트·인식 실패 제외, 미매핑/오류 분리
  → access-events.xlsx
       Access Events
       Attendance Candidates
       Source Review
       Metadata
  → Attendance Verification (필요하면 스케줄도 함께 전달)
```

- **원본 인사 식별:** 이름만으로 동명이인을 결합하지 않습니다. 사번과 부서의 조합을 확인한 다음 검증된 `employee_id`/`worker_id`에 연결합니다.
- **정상 제외와 오류:** `Source Review.status=EXCLUDED`는 정상 필터링 이력이고, `UNMAPPED/REVIEW_REQUIRED/REJECTED`는 검토가 필요한 이력입니다.
- **유효 출근·퇴근 명시 기록**이 있으면 이를 우선합니다. 일반 출입만 있으면 첫·마지막 유효 출입을 후보로 만들되 `confirmed=false`를 유지합니다.
- **원본 초 단위 시각**은 `event_timestamp` 및 후보 시각에 남깁니다.
- **추가 업체·다른 헤더 버전**은 새 프로필·합성 테스트를 구현해야 합니다. 새 원본을 자동으로 추측해 매핑하지 않습니다.
- **Common 매핑 직접 연결(신규 API):** `vendor_adapters.normalize_vendor_excel(..., id_map_path="/private/input/common/id-map.xlsx")`에서 신규 `PERSON MAP`의 `security_id` 업체 선택 및 `DEPARTMENT MAP` 조회를 지원합니다. 보조 장소 시트의 정확한 이름은 **`AREA MAP`**입니다. 기존 `identities` 직접 전달 방식도 유지합니다. 다만 Worktime 통합 CLI가 자동으로 해당 경로를 선택하는 전체 입력 Flow는 아직 구현하지 않았습니다. 다중 업체에 같은 직원이 등록되면 `PERSON MAP`에서 행을 늘리고 업체별로 필터링하며, 임의 추가 열은 읽지 않습니다.
**현재:** Worktime의 검증·10열 Excel·JSON Tool CLI·Portfolio Workflow는 구현되었습니다. Gearbox/Hermes·Slack 운영 호출·실자료 사용은 별도 승인 후 검증합니다.

세부 스키마: [ACCESS-EXCEL-CONTRACT.md](ACCESS-EXCEL-CONTRACT.md), [업체별 어댑터](vendor_adapters/README.md).

## 5. 격리 Python에서 테스트

서버 호스트의 Git 체크아웃 위치는 **반드시 전체 경로**를 사용합니다.

```bash
cd /opt/agents/config/agent-config/.external/portfolio
git status --short
git log -1 --oneline
```

Hermes 컨테이너의 마운트 경로와 Python은 호스트와 다릅니다.

```bash
sudo docker exec -w /opt/agent-config/.external/portfolio \
  hermes /opt/hermes/.venv/bin/python -B -m unittest \
  bhandara.tests.test_worktime_schedule \
  bhandara.tests.test_worktime_attendance_verification \
  bhandara.tests.test_worktime_attendance_deviations \
  bhandara.tests.test_worktime_compliance \
  bhandara.tests.test_worktime_rest_deviations \
  bhandara.tests.test_worktime_vendor_adapters \
  bhandara.tests.test_worktime_access_xlsx_contract -v
```

```bash
sudo docker exec -w /opt/agent-config/.external/portfolio \
  hermes /opt/hermes/.venv/bin/python -B -m unittest \
  discover -s bhandara/tests -p 'test_*.py'

sudo docker exec -w /opt/agent-config \
  hermes /opt/hermes/.venv/bin/python -B gearbox/_tests/run.py

sudo docker exec -w /opt/agent-config \
  hermes /opt/hermes/.venv/bin/python -B gearbox/_tests/core_run.py
```

서버 기본 `python3` 환경은 `python_calamine` 등 패키지가 없을 수 있습니다. **호스트 Python에 임의로 pip 설치하지 말고**, 위 Hermes 격리 Python을 사용합니다. 향후 새 의존성이 필요한 경우에도 `uv`로 통제합니다.

## 6. 다음 개발 단계 (미완료)

1. **매핑/Output 기본 계약 완료:** `SCHEDULE MAP`, `ASSIGNMENTS`, `WORKTIME` 단일 출력은 이미 구현되어 있습니다. 공개 샘플 Excel에는 기존 첫 시트만 있을 수 있으니 자동 교체하지 않습니다.
2. **추가 입력 사실 계약:** 근태장부·휴게 증빙과 외부 확정 근태/휴가 신청 참조의 실제 회사별 입력 방식을 정합니다. 기존 PTO를 자동 변환하지 않습니다.
3. **모듈 조합 Flow와 공개 Tool CLI:** JSON 기반 선택적 실행과 Module JSON 결과, 단일 Worktime Excel 인계는 구현했습니다. 실제 현장 데이터 계약·운영 연결은 별도 검증합니다.
4. **현실 데이터 예외 검증:** 분할근무·자정/익일 퇴근·시차출퇴근·휴일 예정 근무·복수 출입/미인증 등 **합성자료 기반** 회귀를 확장합니다.
5. **Gearbox 연결:** Bhandara 변경마다 `gearbox/_tests/run.py`와 `core_run.py` 등 기존 호환성을 검증합니다. 운영 파일 수집·보관 정책은 명시적 작업별로 다릅니다. 일반 업로드는 기존 Hermes 임시 캐시(2026-11-16 문서 기준 24시간), 인증된 검토를 선택하면 최초 캐시 시각부터 3시간입니다. 자동 영구 저장 및 S3 백업은 금지합니다. 세부 정본은 agent-config의 command-scoped-file-lifecycle.md를 확인합니다.
**현재:** Worktime의 검증·10열 Excel·JSON Tool CLI·Portfolio Workflow는 구현되었습니다. Gearbox/Hermes·Slack 운영 호출·실자료 사용은 별도 승인 후 검증합니다.

**아직 확정하지 않은 것:** 지각/조퇴·연장·야간근무의 승인 판단(Payroll/외부 정책 담당), 임금 계산, 근로시간제별 예외 정책, 실제 휴게 증빙의 입수 방식, 다중 배정/분할근무, Closing 및 외부 시스템 자동 연결.

### 신규 Worktime Output 사용 계약

- `read_schedule_mapping(path, period_from=..., period_to=...)`: 스케줄 ID별 정의와 날짜별 배정 읽기.
- `for_attendance_verification(schedule_rows)`: 익일 종료 시각을 검증 모듈용 ISO 날짜시간으로 변환.
- `build_worktime_result(schedule_rows, attendance_verification, worktime_compliance, period_from=..., period_to=..., attendance_facts=...)`: 3개 모듈의 **이미 계산한 결과**와 외부 근태/휴가 사실을 일별로 결합.
- `write_worktime_xlsx(result, path)`, `read_worktime_xlsx(path)`: `WORKTIME` 한 시트, 10컬럼 Excel 결과 작성/읽기. 기존 파일 덮어쓰기 불가.
- 결과에서 상태·승인·유급시간 산정·급여 금액은 생성하지 않음. 미확인 실제근로는 0이 아닌 공란.
- 구형 Worktime/Payroll과 자동 연결되지 않으므로 CLI나 Gearbox에서 **신규 결과를 기존 Payroll JSON인 것처럼 전달하지 말 것.**

테스트:

```bash
python -m unittest bhandara.tests.test_worktime_schedule_mapping bhandara.tests.test_worktime_output_v01 -v
```

세부 규격: [스케줄 매핑](SCHEDULE-MAP-CONTRACT.md), [단일 Output](OUTPUT-CONTRACT.md).

## 7. 관련 문서

- [전체 구조](README.md)
- [Schedule](schedule/README.md)
- [Attendance Verification](attendance-verification/README.md)
- [Worktime Compliance](worktime-compliance/README.md)
- [출입 Excel 출력 규격](ACCESS-EXCEL-CONTRACT.md)
- [업체별 원본 해석기](vendor_adapters/README.md)
**현재:** Worktime의 검증·10열 Excel·JSON Tool CLI·Portfolio Workflow는 구현되었습니다. Gearbox/Hermes·Slack 운영 호출·실자료 사용은 별도 승인 후 검증합니다.

## 신규 JSON Tool CLI

개인 설정 `bhandara/data/config/worktime.json`을 작성한 뒤 `python3 run.py bhandara worktime`로 실행합니다. `period_from`, `period_to`, 입력/출력 디렉터리, `steps`, 외부 확인된 근로시간·정책을 모두 JSON에 지정합니다. `run_id=auto`면 재실행 시 신규 결과 디렉터리를 만듭니다.

**현재:** Worktime의 검증·10열 Excel·JSON Tool CLI·Portfolio Workflow는 구현되었습니다. Gearbox/Hermes·Slack 운영 호출·실자료 사용은 별도 승인 후 검증합니다.
