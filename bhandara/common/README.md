# Bhandara Common — 계산기 공통 처리

`common/`은 PTO·Worktime·Payroll 중 어떤 계산기 하나만 설치해도 사용할 수 있는 **범용 기능**을 담습니다. 특정 회사의 급여 규칙, 직원 개인정보 처리 정책, 운영 승인 권한은 이 폴더에서 결정하지 않습니다.

## 입력 파일을 읽고 검증하는 기능

| 기능 | 모듈 | 하는 일 |
|---|---|---|
| CSV·XLSX·JSON 읽기 | `io/tabular.py` | 명시한 파일/시트/인코딩 읽기, 열 이름 중복·누락 확인, 원본 행번호 보존, 입력 폴더 밖 경로 접근 차단 |
| 자료형 변환 | `validation/scalars.py` | 날짜·시간·정수·소수·논리값을 정해진 자료형으로 변환, 모호하거나 잘못된 값 거절 |
| 기존 계산기별 Excel 계약 | `io/xlsx.py`, `io/input_layout.py` | 계산기별 기존 Excel 열과 입력 파일 역할 검증 (순차 통합 예정) |
| 설정 처리 | `config/resolver.py` | 외부 전체 JSON과 각 계산기의 `user_settings.py` 중 한 출처 선택 |

### 회사별 매핑과의 경계

예를 들어 원본 CSV에서 `사번`과 `근로자번호` 중 무엇이 `worker_id`인지 결정하는 **회사별 매핑 규칙**은 Gearbox가 관리합니다. 공개 Bhandara를 단독 사용하는 사람은 계산기별 `manifest.json` 등에 같은 규칙을 직접 적을 수 있습니다. Common은 그 **명시된 규칙을 실행하는 일반 처리 기능**을 제공하되 어떤 별칭·코드가 옳은지 추측하지 않습니다.

급여 계산기 `functions/source_mapping.py`는 회사별로 선택된 컬럼 별칭/`value_map`을 적용하고, Common의 일반 파서와 변환기를 호출합니다. 원본 행번호, 누락·거절 행, SHA 출처 검증을 보존합니다.

**사용자 주의:** Common 파일은 사용자가 직접 편집할 필요가 없습니다. 본인이 설치한 계산기 폴더의 `RUNBOOK.md`와 `user_settings.py`를 먼저 확인하세요. `user_settings.py`는 현재 기간·파일 역할 설정만 지원하며, 수당 정책이나 법정 요건을 추정하지 않습니다.

## 개발·검증

별도 계산기 간 import를 사용하지 않으며, Gearbox나 클라우드 설치도 필요하지 않습니다. `unittest` 검증은 다음처럼 실행합니다.

```bash
python -m unittest discover -s bhandara/tests -p 'test_common_tabular_normalization.py' -v
python -m unittest discover -s bhandara/tests -p 'test_module_isolation.py' -v
```

**이전 기록:** `payroll-calculator/migration-manifest.json`은 원본 Gearbox 코드의 초기 이관 기록을 유지합니다. 추가 리팩터링은 `post-migration-refactors.json`에서 추적합니다.
