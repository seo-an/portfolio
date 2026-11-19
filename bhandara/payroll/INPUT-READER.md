# Payroll Excel 입력 Reader — P0-1

`input_excel.py`는 `input-files.json`을 기준으로 `input_root/payroll/` 아래 독립 Excel 7종을 읽습니다. **각 파일은 지정한 시트 1개**여야 하며, 사용자 실자료의 입력 경로를 소스 코드에 넣지 않습니다.

## 호출 예

```python
from bhandara.payroll.input_excel import read_payroll_inputs

# 선택한 단계에서 필요한 파일만 열어 검증한다.
data = read_payroll_inputs("/secure/input", roles=("contracts", "allowance_assignments", "fixed_allowance_map"))
contracts = data.for_role("contracts")
```

`roles`를 생략하면 7종 전체가 필요합니다. 선택하지 않은 파일은 읽지 않으며 없는 파일에 가상 기본값을 만들지 않습니다. 반환된 행은 정본 헤더 키, `Decimal` 숫자, ISO 날짜, 물리적 Excel 행번호 `_row_number`를 포함합니다. 원본은 읽기 전용이며 저장·변경하지 않습니다.

## 차단 사항

- 이름이 다른 파일, 지정 시트 누락·추가 시트, 필수 헤더 누락·중복, 입력 필드의 수식
- 지정 열의 빈 필수 값, 금액의 음수·소수 원, 유효하지 않은 숫자·비율, 날짜 형식·범위 오류
- 숫자로 저장한 ID(앞자리 0 소실 위험), 역할별 중복 키, 수당·공제 정책·성과급 ID 참조 오류
- 같은 직원의 중복된 계산기간, 성과급 배분율 합계가 100%가 아닌 경우

비어 있어도 되는 셀은 역할별로 명시되어 있습니다. 예를 들어 월급·주급의 `installments_per_year`, BASE 계약의 `declared_base_amount`, 팀/프로젝트 중 해당하지 않는 식별자 등입니다. 데이터 오류의 메시지에는 직원·급여 값이나 실제 파일 경로를 포함하지 않습니다.

## 의도적으로 하지 않는 일

- `calculation_period_from/to`의 중복·형식은 검사하지만 **법적 계약 유효기간으로 간주하지 않습니다.** 직원당 정확히 1개 계약을 선택하거나 재계약 당월의 일할금액을 자동 계산하지 않습니다.
- 공제율의 적용 시점, 직원의 실제 소속·보너스 자격, Worktime 승인·추가근로, 보험료·세액은 검증/계산하지 않습니다.
- 사람용 표시명은 스키마 v1.1의 `allowance_name`·`bonus_name`에 입력한다. `review_adapter.py`가 검증된 이름과 금액을 동적 출력에 연결하지만 **완결된 지급합계나 실지급액을 만들지 않는다.** Tool CLI, Slack 보관 및 지급 승인 기능은 여전히 없습니다.
- `read_payroll_inputs`를 호출하는 단계에서 역할 목록을 명시해야 하며, 독립 Tool의 선택적 `steps` CLI 연결은 P3입니다. [P0-2/3 산정기간·검토용 연결](PERIOD-PREVIEW.md)을 참고합니다.

## 검증

```bash
python3 -m unittest bhandara.tests.test_payroll_input_reader_p0 -v
python3 -m unittest discover -s bhandara/tests -p 'test_*.py'
```

`agent-config`는 PAUSE 중이며, Tool 계약을 변경할 때에는 운영 Gearbox 기능/인프라 테스트도 별도로 실행합니다. 이 Reader의 실행은 실제 급여 지급이나 HR 데이터 운영을 승인하지 않습니다.
