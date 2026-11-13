# Bhandara 통합 샘플 v2 — 직원 80명 + 외부 인력 2명

이것은 **새로 사용하기 시작할 때 권장하는 입력 예제**입니다.
구형 파일을 쓰는 [기존 80명 샘플](../sample/README.md)은
이전 버전의 계산 결과와 비교하는 회귀 기준으로 보존합니다.

샘플 생성기는 실제 `.xlsx` 파일과 `worktime-result.json`을 생성합니다.
**데이터는 전부 합성 자료이며 실제 직원·계약·승인·세금 자료가 아닙니다.**

## 1. 한 번만 실행해서 샘플 만들기

프로젝트 루트에서 실행합니다. 생성 경로는 **Git 저장소 바깥**의
새 폴더여야 하고, 기존 폴더가 있으면 덮어쓰지 않습니다.

```bash
python bhandara/examples/integrated/generate.py \
  --output-dir /tmp/bhandara-integrated-v2
```

생성한 폴더의 구성:

```text
/tmp/bhandara-integrated-v2/
├── manifest.json
└── input/
    ├── common/
    │   ├── employee.xlsx          # 사내 직원 80명만
    │   └── id-map.xlsx            # ID_MAP 직원 80명, EXTERNAL 외부 2명
    ├── worktime/
    │   ├── work-schedule.xlsx     # 예정근무: 직원 + 외부 서비스
    │   ├── attendance.xlsx        # 실제 근태: 직원 + 외부 서비스
    │   └── security-raw-*.xlsx    # 합성 출입기 원본, 자동 승인 금지
    ├── payroll/
    │   ├── pay-contract.xlsx      # Contracts + Components (v2)
    │   ├── payroll-input.xlsx     # 가상 성과급
    │   ├── company-policy.json    # 예시 정책; 실제 법령 판단 아님
    │   └── worktime-result.json   # 위 Excel로 실제 계산한 6월 결과
    └── pto/
        └── ...                    # 기존 직원 80명용 연차 테스트 자료
```

**v2에는 다음 구형 파일이 생성되지 않습니다:**
`pay-contract-components.xlsx`, `service-contracts.xlsx`,
`service-work-records.xlsx`.

## 2. 파일 열어보기

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

## 3. Worktime 계산 재현

`worktime-result.json`은 실제 Worktime 계산기로 생성한
**2026년 6월의 미마감 결과**입니다. 입력 Excel을 변경했다면 반드시
새 Worktime 결과를 생성하고 그것을 Payroll에 다시 전달하세요.

```bash
python run.py bhandara worktime-calculator \
  --period 2026-06 \
  --input-dir /tmp/bhandara-integrated-v2/input \
  --output-dir /tmp/bhandara-integrated-v2/recalculated-worktime
```

`recalculated-worktime`은 아직 존재하지 않아야 합니다.
Workbench는 변경된 데이터의 Worktime 결과를 임의로 찾아 대신 사용하지 않습니다.

## 4. Payroll·PTO 사용

```bash
python run.py bhandara payroll-calculator \
  --period 2026-07 \
  --input-dir /tmp/bhandara-integrated-v2/input \
  --worktime-result /tmp/bhandara-integrated-v2/input/payroll/worktime-result.json \
  --output-dir /tmp/bhandara-integrated-v2/payroll-review

python run.py bhandara pto-calculator \
  --period 2026-07 \
  --input-dir /tmp/bhandara-integrated-v2/input \
  --output-dir /tmp/bhandara-integrated-v2/pto-review
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
