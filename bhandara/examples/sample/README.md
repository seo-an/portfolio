# 반다라 통합 샘플 — 직원 80명 + 외부 인력 2명

**정식 공개 샘플은 이 폴더의 `input/` 한 세트뿐입니다.**

**샘플 생성은 명시적 요청이 있을 때만 합니다.** 일반 `push`/`pull_request`는 정식 샘플을 자동 갱신하거나 커밋하지 않습니다. `generate.py --output-dir <새 경로>`는 Git 밖의 새 디렉터리에만 생성하고, `refresh.py`는 **`--apply`가 없는 한 아무 것도 생성/수정하지 않습니다**. GitHub Actions의 canonical sample refresh도 수동 `workflow_dispatch`로만 실행합니다. 기본 `apply=false`에서는 합성 생성·검증 테스트만 실행하며, **정식 Excel을 교체하려면 기능 브랜치에서 `apply=true`를 명시해야** 합니다. 개발용 일반 unittest에서 통합 샘플 생성 호출은 기본 건너뛰고, `BHANDARA_RUN_SAMPLE_GENERATOR_TESTS=1`을 명시한 경우에만 실행합니다.

생성 스키마: `common/id-map.xlsx`의 구형 `ID_MAP` / `EXTERNAL` 두 시트를 유지하면서 신규 `PERSON MAP`, `DEPARTMENT MAP`, `AREA MAP` 세 시트를 추가합니다. 신규 `PERSON MAP`은 **직원×보안업체 1행**이고 `security_id`는 업체 코드입니다. 합성 직원 80명을 CAPS에 등록하고 두 직원의 SECOM/TELECOP 등록을 추가 행으로 포함합니다.

**기존 Excel은 자동으로 교체하지 않습니다.** 이 저장소가 공개하는 80명
샘플은 `input/` 한 세트이며, 새 형식을 별도 공개 샘플로 중복 보관하지
않습니다. 단, 이 파일들은 **마지막으로 명시적 갱신을 수행한 시점의 스냅샷**이므로
생성기 코드의 새 시트가 아직 반영되지 않았을 수 있습니다.

- **현재 보관된 Excel을 사용:** `input/`을 열거나 복사합니다. 기존 계산기 호환성 유지.
- **최신 구조 새로 생성:** [`generate.py`](generate.py)에 `--output-dir`을 명시하여 Git 밖의 비어 있는 경로에 생성합니다.
- **공개 스냅샷 교체:** 별도 브랜치에서 검토 후 `refresh.py --apply`를 명시적으로 실행합니다. `input/` 전체를 교체하므로 기존 사용자 수정 내용을 사전에 확인해야 합니다.
- **자동화:** 일반 push/PR에는 생성·덮어쓰기 없음. 수동 Actions는 기본 `apply=false`로 테스트만 수행하고, `apply=true`가 명시된 비-main 브랜치에서만 갱신·커밋을 시도합니다.

샘플 생성기는 실제 `.xlsx` 파일과 `worktime-result.json`을 생성합니다.
**데이터는 전부 합성 자료이며 실제 직원·계약·승인·세금 자료가 아닙니다.**

## 1. 한 번만 실행해서 샘플 만들기

프로젝트 루트에서 실행합니다. 생성 경로는 **Git 저장소 바깥**의
새 폴더여야 하고, 기존 폴더가 있으면 덮어쓰지 않습니다.

```bash
python bhandara/examples/sample/generate.py \
  --output-dir /tmp/bhandara-sample-80
```

생성한 폴더의 구성:

```text
/tmp/bhandara-sample-80/
├── manifest.json
└── input/
    ├── common/
    │   ├── employee.xlsx          # 사내 직원 80명만
    │   └── id-map.xlsx            # ID_MAP(기존 80명)·EXTERNAL(외부 2명) + PERSON MAP·DEPARTMENT MAP·AREA MAP
    ├── worktime/
    │   ├── work-schedule.xlsx     # 예정근무: 직원 + 외부 서비스
    │   ├── attendance.xlsx        # 실제 근태: 직원 + 외부 서비스
    │   └── security-raw-*.xlsx    # 합성 출입기 원본, 자동 승인 금지
    ├── payroll/
    │   ├── pay-contract.xlsx      # Contracts + Components (통합)
    │   ├── payroll-input.xlsx     # 가상 성과급
    │   ├── company-policy.json    # 예시 정책; 실제 법령 판단 아님
    │   └── worktime-result.json   # 위 Excel로 실제 계산한 6월 결과
    └── pto/
        ├── employee-events.xlsx   # 승인 합성 연차 2·오전 반차 3·오후 반차 2·조퇴 1·단축 1 + 기존 검토 2건
        ├── work-schedule.xlsx
        └── work-records/2026/     # 해당 일자의 근태 증빙도 함께 조정
```

**최신 통합 형식에는 다음 별도 파일이 없습니다:**
`pay-contract-components.xlsx`, `service-contracts.xlsx`,
`service-work-records.xlsx`.

## 2. Mapping 시트 확인

명시적으로 `generate.py`를 실행하면 생성된 `common/id-map.xlsx`에는 다음 5개 시트가 함께 있습니다.

| 시트 | 역할 |
|---|---|
| `ID_MAP` | 구형 Worktime/Payroll의 개인별 고유 ID 계약(80명) |
| `EXTERNAL` | 외부 인력 Worktime 식별자(2명) |
| `PERSON MAP` | 신규 Worktime 직원×업체 등록 정보(CAPS 80행 + SECOM 1행 + TELECOP 1행) |
| `DEPARTMENT MAP` | 보안시스템 부서 코드와 원본 부서명 연결 |
| `AREA MAP` | 출입 장소명과 장소 코드 연결 |

`PERSON MAP.security_id`는 **업체 코드**이고 `ID_MAP.security_id`는 구형 코드에서 쓰는 **개인별 고유 ID**이므로 상호 혼용하지 않습니다. 업체가 추가되면 `PERSON MAP`의 **행**을 추가하며, 업체별 추가 열은 프로그램이 읽지 않습니다. 규칙은 [Common ID Mapping](../../common/SECURITY-PERSON-MAP.md)에 있습니다.

## 3. 파일 열어보기

- `pay-contract.xlsx`의 **Contracts**: 직원 계약 80개와 외부 용역
  계약 3개. `relationship_type`으로 법적 계약 분기를 분명하게 입력
- **Components**: 고정 지급항목과 `base_salary`를 명시적으로 분리
- `E006` 직원: 월 기본급 350만 원(**BASE**) + 직책수당 15만 원
  + 식대 10만 원 = 월 지급 계약 구성 합계 **375만 원**
- 나머지 연봉/월급 계약: 계약금액은 **TOTAL**, 구성 수당을 포함하며
  `base_salary + allowances == monthly contract amount` 검증
- 외부 시급 `EXT-W001`과 일급 `EXT-W002`: 같은 근무표·근태를
  Worktime에서 계산. `PROJECT` 계약은 납품 증빙 없으므로 금액 미산정
- 회사 직원 외 인력은 `common/employee.xlsx`에 넣지 않습니다.

## 연차 사용·잠정 잔여 샘플

현재 `input/`의 80명 직원 중 기존 E031·E044 검토 이벤트 2건에 더해
아래 승인된 **합성 이벤트 9건**을 생성합니다.

| 직원 | 승인된 합성 이벤트 | 발생일 | 연차 차감 |
|---|---|---|---|
| E001, E002 | 연차 | 2026-07-06 | 각각 1일 |
| E003, E004, E005 | 오전 반차 | 2026-07-07 | 각각 0.5일 |
| E006, E007 | 오후 반차 | 2026-07-08 | 각각 0.5일 |
| E008 | 조기퇴근 | 2026-07-09 | 연차 미차감 |
| E009 | 육아기근로시간단축 | 2026-07-10 | 연차 미차감 |

같은 날짜의 `pto/work-records/2026/2026-07-attendance.xlsx`에도
전일 연차는 출근기록 미기재, 오전/오후 반차는 실제 근무한 반일,
조퇴·단축은 실제 일찍 퇴근한 기록으로 반영했습니다.
예제 데이터의 상태 `APPROVED`는 **가상 인사 이벤트 가정**이며
실제 인사 승인이나 근로시간·휴게의 최종 검증을 뜻하지 않습니다.

PTO 실행 결과 `pto-result.xlsx`에서 `Summary`, `Usage`,
`Balances`, `Unresolved`, `Review Required` 시트를 확인하세요.
`known_used_days`는 계산하지만 `confirmed_balance_days`,
`expired_days`는 **미검증 `null`**로 유지합니다. `provisional_remaining_before_expiry_days`
역시 확정 잔여가 아닙니다.

**이미 생성한 /tmp/bhandara-sample-80 폴더는 자동 갱신되지 않습니다.**
새 경로에 재생성해야 바뀐 Excel이 보입니다. 생성기는 덮어쓰지 않습니다.

## 3. Worktime 계산 재현

`worktime-result.json`은 실제 Worktime 계산기로 생성한
**2026년 6월의 미마감 결과**입니다. 입력 Excel을 변경했다면 반드시
새 Worktime 결과를 생성하고 그것을 Payroll에 다시 전달하세요.

```bash
python run.py bhandara worktime-calculator \
  --period 2026-06 \
  --input-dir /tmp/bhandara-sample-80/input \
  --output-dir /tmp/bhandara-sample-80/recalculated-worktime
```

`recalculated-worktime`은 아직 존재하지 않아야 합니다.
Workbench는 변경된 데이터의 Worktime 결과를 임의로 찾아 대신 사용하지 않습니다.

## 4. Payroll·PTO 사용

```bash
python run.py bhandara payroll-calculator \
  --period 2026-07 \
  --input-dir /tmp/bhandara-sample-80/input \
  --worktime-result /tmp/bhandara-sample-80/input/payroll/worktime-result.json \
  --output-dir /tmp/bhandara-sample-80/payroll-review

python run.py bhandara pto-calculator \
  --period 2026-07 \
  --input-dir /tmp/bhandara-sample-80/input \
  --output-dir /tmp/bhandara-sample-80/pto-review
```

출력 폴더는 각각 새 이름이어야 합니다. 실제 근무 승인·용역 검수·
급여 지급·원천세/사회보험 판정은 **어느 계산기도 자동 확정하지 않습니다**.

## 5. 과세·비과세 구분은 별도 검토

이 통합 샘플의 `company-policy.json`에는 **세무 검토 후보 분류**가
포함되어 있습니다. `base_salary`는 과세 후보, `meal_allowance`는
비과세 후보(예시 100,000원 한도), `position_allowance`는
판정 보류로 설정합니다. **100,000원은 법정 한도가 아닌 임의의 합성 테스트 숫자입니다.**
실제 세법상 비과세 자격·한도를 확정하거나 원천세를 계산하는 기능이 아닙니다.

Payroll 0.3.2 이상에서는 `taxability-review.json/xlsx`로 후보 분류와
보류 금액을 별도 출력합니다. 이전 버전에서는 이 설정을 지급액에
반영하지 않으며, 외부 인력의 용역대가는 세무 분류에 포함되지 않습니다.
[분류 규칙 사용 안내](../../payroll-calculator/RUNBOOK.md)를 확인하세요.
