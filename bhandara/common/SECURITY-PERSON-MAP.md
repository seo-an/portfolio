# Common 보안업체별 사람·부서·구역 매핑

Worktime의 출입기기 원본은 직원 ID와 동일하지 않은 보안업체별 인물번호·부서·구역 코드를 포함할 수 있다. **정확한 원장 매핑이 있는 항목만** 직원과 연결하며, 이름의 유사성으로 직원을 추정하지 않는다.

## 기준 파일

`common/id-map.xlsx`의 신규 Worktime 매핑 시트는 다음과 같다.

| 시트 | 의미 | 기본 원칙 |
|---|---|---|
| `PERSON MAP` | 직원과 보안업체별 등록 ID | **직원 × 업체별 1행**. 한 직원이 여러 보안업체에 등록돼 있다면 별도 행 |
| `DEPARTMENT MAP` | 회사 부서와 보안업체 부서 코드 | 정확한 코드, 중복·충돌 차단 |
| `AREA MAP` | 회사 구역과 보안업체 구역 코드 | 명시적 구역 정본, 임의 추론 금지 |

`PERSON MAP`의 필수 열은 `employee_id`, `name`, `security_department_id`, `security_id`, `worker_id`, `payroll_id`, `security_person_id`, `main_area`다. 파일의 정확한 필수 검증은 `bhandara/common/io/security_person_map.py`가 수행한다.

**선행 검증:** 직원 ID, 업체 ID, 업체별 사람 ID, 부서/구역 코드, 중복 등록 상태가 실제 원본과 일치해야 한다. 0으로 시작하는 ID는 반드시 Excel 텍스트로 보존한다. 서로 다른 업체가 같은 숫자 ID를 사용할 수 있으므로 업체 코드 없이 사람을 연결하지 않는다. 알 수 없는 항목은 `REVIEW_REQUIRED` 또는 명시적 오류로 남긴다.

이 매핑은 Worktime 사실 검증에 쓰이며, Payroll의 계약·임금 지급 승인이나 가입 여부 결정을 대신하지 않는다. 실제 직원 파일과 보안업체 원본은 공개 저장소에 포함하지 않는다. 합성 데이터는 테스트가 임시 폴더에서 생성한다.

[Worktime 출입원장 계약](../worktime/ACCESS-EXCEL-CONTRACT.md) · [벤더 정규화 계약](../worktime/vendor_adapters/README.md)
