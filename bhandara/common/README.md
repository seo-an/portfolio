# Common — 세 HR Tool이 공유하는 입력·검증 기반

Common은 독립적인 HR 판단·급여 계산기가 아니라, **입력 읽기와 신뢰할 수 있는 식별·검증**을 제공하는 라이브러리다. 독립 실행 가능한 Common 기능은 [Normalizer](module/normalizer/RUNBOOK.md)로 분리한다.

| 기능 | 코드 | 계약 |
|---|---|---|
| 엄격한 Excel 읽기 | `io/xlsx_stream.py`, `io/xlsx.py`, `io/input_layout.py` | 시트·헤더·수식·셀 검증, 행 번호 보존 |
| 범용 원본 | `io/tabular.py` | CSV/JSON/Excel 열 매핑 및 입력 자료형 제약 |
| 직원·업체 ID | `io/security_person_map.py` | `PERSON MAP`, `DEPARTMENT MAP`, `AREA MAP` |
| 공통 ID 파일 참조 | `io/input_layout.py` | 정확한 `common/id-map.xlsx` 역할만 지정 |
| 원본 해시 | `utils/hashing.py` | 스트리밍 SHA-256, 원본 불변 |
| 검토/진단 | `contracts/`, `validation/`, `runtime/` | 자료 부재·충돌을 무단 확정 없이 표시 |
| Common Normalizer | `module/normalizer/` | 지정한 매핑으로 별도 입력 검토 |

### 책임 경계

- 회사별 지급·휴가 산식은 개별 Tool이 소유한다. Common에서 자동 추정하지 않는다.
- 원본 Excel의 파일명, 시트명과 헤더 규격은 각각의 Tool 계약이 정한다.
- 사용자의 직원정보·ID 매핑·증빙을 Git에 저장하지 않으며, 샘플 데이터가 실제 자료를 대체하지 않는다.
- Payroll 승인 여부, Slack 사용자/스레드 인증, 임시 캐시 TTL은 Common이 결정하지 않는다.
- Worktime 보안업체별 사람 매핑은 [공통 매핑 계약](SECURITY-PERSON-MAP.md)을 따른다.
- 단일 명령 테스트: `python3 -B bhandara/_tests/run.py`.

프로젝트별 준비와 운영 연결은 [전체 사용법](../RUNBOOK.md) · [Workflow](../WORKFLOW.md)에서 확인한다.
