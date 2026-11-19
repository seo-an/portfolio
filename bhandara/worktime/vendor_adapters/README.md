# CAPS · 세콤 · KT텔레캅 원본 변환 해석기

> 업로드된 3개 시트의 **실제 관찰된 헤더와 데이터 형식**을 기준으로 한 초기 업체 프로필입니다. 제조사 공식 규격 전체를 검증했다는 의미는 아닙니다.

## 업체별 필드

| 업체 `vendor` | 이름 | 사번 | 부서 | 일시 | 출입기 | 판정 필드 |
|---|---|---|---|---|---|---|
| `CAPS` | `성명` | `사원번호` | `부서` | `일자` + `시간` | `단말기명` | `상태` |
| `SECOM` | `성명` | `사번` | `부서` | `일시` | `출입구명` | `인증방식` |
| `KT_TELECOP` | `이름` | `사번` | `부서` | `일시` (오전·오후 가능) | `장치명` | `인증구분` |

- `인증방식`/`인증구분`의 `지문`, `안면인식`, `카드`는 출근/퇴근 모드가 **아니라 인증 방법**입니다. 별도의 `상태`, `구분`, `출입구분`, `근태구분` 열이 있으면 명시된 모드만 구분하고, 없으면 `ACCESS`로 둡니다.
- `출근(인증)`/`퇴근(인증)`은 `CLOCK_IN`/`CLOCK_OUT`. `외출`/`복귀`는 `OUTING`/`RETURN`이고 출퇴근/휴게시간으로 환산하지 않습니다.
- 원본의 `세트`, `경비시작`, `경비설정`, `인식실패`, `인증실패` 등은 **이벤트 수집 대상에서 제외**합니다. 원본 행번호와 사유는 표준 Excel의 `Source Review`에 `EXCLUDED`로 남깁니다. 정상적인 제외는 전체 검증 실패로 취급하지 않습니다.
- 출퇴근 모드가 아예 없을 때는 해당 직원·날짜의 성공 기록 중 일반 `ACCESS`만 골라 **가장 이른 시각을 출근 후보, 가장 늦은 시각을 퇴근 후보**로 삼습니다. 한 건만 있으면 퇴근 후보는 비웁니다. `confirmed=false`.
- 명시적 출근·퇴근 모드가 일부라도 있으면 `ACCESS`로 나머지를 **몰래 채우지 않습니다**. 중복 출퇴근은 다중 후보 검토로 남깁니다.
- 동명이인은 이름으로 합치지 않습니다. **`department + employee_number`**을 Common에서 검증된 `employee_id + worker_id`와 연결해야 합니다. 이름이 참조 자료와 다르면 `EMPLOYEE_NAME_CONFLICT` 검토. 사번만 같고 부서가 다른 직원은 별개.
- 익일로 넘어가는 근무는 이번 기본 프로필의 **당일 기록 그룹 규칙에 따라 분리**됩니다. 주간·야간 연결 정책이 확정되기 전 자동으로 전날 퇴근으로 합치지 않습니다.

## 출력 Excel

모든 업체는 *동일한* `bhandara/worktime/access_source.py` Writer를 호출합니다. **v0.2 표준 Excel**은 네 시트로 고정됩니다.

1. `Access Events`: 정규화된 모든 수집 대상 원본 이벤트. `event_time`은 기존 계산 모듈용 분 단위 시각, `event_timestamp`는 원본 초 단위 시각.
2. `Attendance Candidates`: 직원·날짜별 출퇴근 후보, 추출 근거, `confirmed=false`. 모든 업체 동일 규격.
3. `Source Review`: 수집 제외(`EXCLUDED`)와 불명확·미매핑(`UNMAPPED` 등) 기록. 원본 행 번호 유지.
4. `Metadata`: 스키마·업체·원본 SHA-256·원본 파일명·타임존·건수.

완전한 [입출력 계약](../ACCESS-EXCEL-CONTRACT.md)을 따릅니다. 업체 원본의 초 단위 시각을 버리지 않습니다.

## Common Excel 직접 연결 (신규)

새 계약에서는 **업체별 전용 열 없이** `common/id-map.xlsx`의 `PERSON MAP`을 사용합니다. `security_id`는 직원별 유일 번호가 아니라 `CAPS`/`SECOM`/`TELECOP` 업체 구분입니다. 같은 직원이 여러 업체에 등록됐다면 업체마다 한 행을 두고, 선택한 `vendor`의 행만 해석기로 전달합니다.

```python
from bhandara.worktime.vendor_adapters import normalize_vendor_excel

result = normalize_vendor_excel(
    "/private/input/caps-original.xlsx",
    "/private/output/access-events.xlsx",
    vendor="CAPS",
    id_map_path="/private/input/common/id-map.xlsx",
)
# 결과는 Attendance Verification용 출입기 record
# result["identity_mapping_reviews"]는 업체 ID 누락/참조 오류 진단
```

기존 호출자가 `identities`를 직접 전달하는 API는 유지합니다. **두 입력을 동시에 주면 오류**가 나며 어느 쪽이 정본인지 추측하지 않습니다. 새 매핑의 시트/열과 외부 ID 충돌 규칙은 [Common 계약](../../common/SECURITY-PERSON-MAP.md)에서 확인할 수 있습니다.

## 순수 함수 및 파일 변환

```python
from bhandara.worktime.vendor_adapters import normalize_vendor_excel

identities = [
    {
        "department": "DEPT-A", "employee_number": "1001",
        "employee_id": "E001", "worker_id": "W001",
        "name": "Example Person",
    }
]
result = normalize_vendor_excel(
    "/private/input/vendor-export.xlsx",
    "/private/output/access-events.xlsx",
    vendor="SECOM", sheet_name="기록",
    identities=identities,
)
```

- 위 `identities`는 **호출자가 제공하는 Common의 검증된 매핑 자료**입니다. 이름·사번을 바탕으로 코드에서 자동 생성하지 않습니다.
- 직원정보/출입기 원본을 공개 저장소에 커밋하지 않습니다.
- 처리 전 입력이 유효하지 않으면 오류가 나고, 변환 불가능한 개별 행은 검토 시트에 남깁니다. 기존 결과 Excel을 덮어쓰지 않습니다.
- 도구 내부 독립 변환 경로만 구현한 상태이며 공개 CLI·Gearbox·Slack 연결은 여전히 미구현입니다.

## 합성 테스트

```bash
python3 -m unittest bhandara.tests.test_worktime_vendor_adapters -v
python3 -m unittest bhandara.tests.test_worktime_access_xlsx_contract -v
```
