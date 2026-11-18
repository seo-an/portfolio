# 업체별 원본 정규화 → 표준 Access Events Excel 계약 0.2

## 원칙

**CAPS, KT텔레캅 및 향후 다른 보안업체의 원본 열 순서·파일명·코드가 달라도, 어댑터의 최종 출력 Excel 구조는 반드시 같습니다.**

```text
원본 CAPS.xlsx ──> CAPS Adapter  ──┐
원본 세콤.xlsx ──> SECOM Adapter ──┼──> access-events.xlsx ──> Attendance Verification
원본 KT.xlsx   ──> KT Adapter    ──┘         └────────────> Attendance Detection 후보 근거
```

업체별 파서는 원본 해석·식별자 연결·업체 코드 매핑만 담당합니다. 결과 파일의 시트, 헤더, enum, 시간 표현은 **Tool 공통 `access_source.py`**가 통제합니다. 업체별 코드에서 지원되지 않는 값은 임의 추정하지 않고 검토 대상으로 보관합니다.

실제 CAPS/KT 내보내기 Excel은 현재 저장소에 없어 **업체별 실제 파서는 미구현**입니다. 테스트에 사용하는 가상 업체 행은 실 제조사 코드표가 아닙니다. 원본을 받은 뒤 업체별 Mapping Table을 따로 추가하되 위 표준 출력 형식은 변경하지 않습니다.

## 파일명 및 시트 고정

파일: `access-events.xlsx` (기본 권장명, 파일 경로는 호출자가 명시)

| 시트 | 목적 |
|---|---|
| **Access Events** | 근태 검증 Module에 전달할 정규화된 이벤트 1행=1이벤트 |
| **Attendance Candidates** | 직원·날짜별 명시적 출퇴근 또는 첫·마지막 유효 출입 후보. 모든 행 `confirmed=false` |
| **Source Review** | 원본에서 제외·변환 거부·미매핑된 행의 출처 및 문제 코드 |
| **Metadata** | 스키마 버전·업체명·원본 SHA-256·타임존·건수 |

### Access Events (열 순서 고정)

`event_id, employee_id, worker_id, work_date, event_time, mode, direction, auth_status, auth_method, device_id, source_vendor, source_ref, source_row_number, event_timestamp`

- `work_date`: 출근 기준 근무일(`YYYY-MM-DD`), `event_time`: 기존 계산 모듈과 호환되는 분 단위 로컬 시각(`YYYY-MM-DDTHH:MM`), `event_timestamp`: 원본 초 단위 시각(`YYYY-MM-DDTHH:MM:SS`). 초 단위 시각을 버리거나 올림하지 않습니다. 익일 퇴근 인증은 날짜를 명시하고 같은 `work_date`로 연결. 어느 근무일인지 확인할 수 없으면 임의 연결하지 않고 Source Review로 남깁니다.
- `mode`: `CLOCK_IN, CLOCK_OUT, ACCESS, OUTING, RETURN, DISARM, UNKNOWN`.
- `direction`: `IN, OUT, UNKNOWN`; 출근·퇴근 모드와 **물리 방향은 별개**입니다.
- `auth_status`: `SUCCESS, FAILED, UNKNOWN` / `auth_method`: `FINGERPRINT, FACE, CARD, PIN, UNKNOWN`. 원본에 인증방법이 없다면 `UNKNOWN`, 지문 성공으로 추정 불가.
- `employee_id, worker_id`: Common ID 연결을 외부에서 **검증 완료한 후** 적습니다. 미등록/중복/충돌을 임의로 다른 직원에게 연결하지 않습니다.
- `source_ref`: 정규화 과정에서 유지하는 원본 증빙 참조. `source_row_number`: 원본 Excel의 실제 행 번호.
- 이 시트는 출입 인증 사실을 담는 것이지, **법정 휴게·실근로·지각·연장근로 확정** 자료가 아닙니다.

### Attendance Candidates (열 순서 고정)

`employee_id, worker_id, work_date, arrival_time, departure_time, arrival_basis, departure_basis, candidate_status, confirmed, evidence_event_ids, source_vendor`

명시적 `CLOCK_IN`/`CLOCK_OUT`이 있으면 우선 사용합니다. 없고 일반 `ACCESS`만 있다면 같은 직원·같은 날짜에서 **수집 대상 이벤트 중 시간상 최초/최후 기록**을 후보로 만듭니다. 하나뿐이면 도착 후보만 제공하고 퇴근 후보는 공란으로 남깁니다. `OUTING/RETURN/DISARM` 및 경비 세트·인식 실패 기록은 후보로 사용하지 않습니다.

- `arrival_basis`: `EXPLICIT_CLOCK_IN`, `INFERRED_FIRST_ACCESS`, `MISSING`.
- `departure_basis`: `EXPLICIT_CLOCK_OUT`, `INFERRED_LAST_ACCESS`, `MISSING`.
- `candidate_status`: `EXPLICIT_PAIR`, `INFERRED_PAIR`, `PARTIAL_EXPLICIT`, `MULTIPLE_EXPLICIT_REVIEW`, `SINGLE_ACCESS`, `NO_ATTENDANCE_CANDIDATE`, `TIME_SEQUENCE_REVIEW`.
- `arrival_time`/`departure_time`은 **초 단위 원본 시각**입니다. `confirmed`는 항상 `false`; 실제 근로·지각·수당을 자동 확정하지 않습니다.
- 동일 이름이라도 `부서 + 사원번호`(CAPS) 또는 `부서 + 사번`(세콤·KT) 조합으로 식별하고, Common ID와 엄격하게 연결합니다. 이름은 충돌 여부 검토용입니다.
- 익일 근무일 연결 규칙은 별도 계약 전까지 당일 기록을 임의로 전날에 합산하지 않습니다.

### Source Review (열 순서 고정)

`source_vendor, source_row_number, status, issue_codes, source_ref, detail`

변환할 수 없는 행이나 승인되지 않은 코드 해석이 있으면 이 시트에 기록합니다. `status`는 `REJECTED, REVIEW_REQUIRED, UNMAPPED, EXCLUDED` 중 하나. `EXCLUDED`는 경비세트·인식실패처럼 의도적으로 **수집에서 제외한 정상적인 필터링 결과**이고, 검토 오류로 취급하지 않습니다. 누락된 원본 행을 조용히 버리면 안 됩니다.

### Metadata

`key, value` 형식으로 `schema_version(0.2), source_vendor, source_sha256, source_file, timezone(Asia/Seoul), event_count, candidate_count, review_count`을 기록합니다.

## 표준 Excel 쓰기/읽기 API

```python
from bhandara.worktime.access_source import (
    write_access_events_xlsx, read_access_events_xlsx,
)
output = write_access_events_xlsx(
    "/private/output/access-events.xlsx",
    normalized_events, rejected_or_review_rows,
    source_vendor="CAPS",
    source_sha256="...",  # 원본 파일의 실제 64자리 SHA-256
    source_file="caps-export.xlsx",
)
records = read_access_events_xlsx(output)
# records["events"]는 Attendance Verification의 access_events 입력 형태
# records["source_reviews"]에 정규화 중 발생한 누락/불명확 원본 보존
```

도구 내부 모든 업체 어댑터는 **같은 Writer만 호출**해야 합니다. Worktime Calculation Module은 업체별 원본을 직접 열거나 필드 위치를 추측하지 않습니다.

`read_access_events_xlsx()`의 `status=PASS`는 **표준 Excel 구조 및 변환 결과 검토 이슈 부재**만 의미합니다. `EXCLUDED`는 별도 집계되며 미매핑 오류와 혼동하지 않습니다. 지문 인증 성공, 근태 승인 또는 출퇴근 확정을 뜻하지 않습니다.

### 근무 예정 시각과 출입 후보의 부호 있는 차이

`verify_attendance_xlsx(..., schedule_rows=schedule_rows)`에 **선택적으로 스케줄을 전달**하면 `Attendance Candidates`의 첫·마지막 일반 출입 후보를 포함해, 예정 시각 대비 장부 및 출입기 시각의 **부호 있는 차이**를 `time_deviations`에 제공합니다. 정규화된 Excel의 시트·컬럼은 변경하지 않습니다.

- `ledger_vs_expected`: 장부−예정
- `device_vs_expected`: 출입기−예정 (일반 출입은 미확정)
- `device_vs_ledger`: 출입기−장부

`reason`은 근태장부의 `clock_in_reason`과 `clock_out_reason`에서만 전달받으며 임의로 조기출근·시차출퇴근·야근을 판정하지 않습니다. 출입기 인식 시각이나 시각 차이는 **승인된 근로시간이 아닙니다**.

### 정규화 실패까지 보존하는 즉시 검증 경로

`verify_attendance_xlsx(attendance_rows, workbook_path, *, period_from, period_to)`는 표준 Excel을 열어서 바로 Attendance Verification으로 전달하는 Tool 내부 편의 함수입니다.

```python
from bhandara.worktime.access_source import verify_attendance_xlsx

report = verify_attendance_xlsx(
    attendance_rows, "/private/output/access-events.xlsx",
    period_from="2026-11-16", period_to="2026-11-16",
)
```

`Access Events`가 장부와 모두 일치하더라도 `Source Review`에 미매핑·오류 행이 있다면 결과 전체를 `REVIEW_REQUIRED`로 표시합니다. 다만 정상적인 `EXCLUDED` 기록만 있으면 자동 실패 처리하지 않습니다. **좋은 행만 골라 계산해서 원본 문제가 사라진 것처럼 표현하지 않습니다.**

## Worktime Compliance와의 관계

이 Excel은 근태·외출의 독립 증빙을 제공할 뿐입니다. **CAPS/KT의 OUT→IN이 자동으로 법정 휴게가 되는 것은 아닙니다.** 실제 휴게시간·근로시간 및 증빙 완전성은 외부 검토를 거쳐 Worktime Compliance의 `daily_rows`에 들어갑니다. 따라서 업체별 어댑터를 추가해도 Compliance의 법률 기준 계산을 다시 쓰지 않습니다.

현재 CAPS·세콤·KT의 **업로드 예제에서 관찰된 헤더**를 처리하는 독립 파서가 `vendor_adapters/`에 구현되어 있습니다. 제조사 전체 버전·별도 헤더 및 실제 원본 코드 체계를 모두 지원한다는 의미는 아니며, 새 양식은 명시적 프로필/테스트가 필요합니다. `identity_rows`는 Common에서 검증된 참조를 호출자가 전달하며 동명이인 자동 결합을 하지 않습니다.
