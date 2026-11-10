# Bhandara 상호배타·독립 실행 검증

> **상태 (2026-11-10):** 상호배타 테스트 및 모듈 간 의존 경로 정리 PR 작성. **Hermes 서버에서 실행·검증하기 전**, PASS라고 주장하지 않는다.

## 검증 목적과 범위

이 검증의 '상호배타'는 **Base + 특정 계산기 1개만 설치했을 때 해당 계산기가 단독 실행되는지** 확인한다는 뜻이다. Gearbox와 Portfolio 중 하나만 선택하도록 강제한다는 뜻이 아니다. 기존 기능·계산식·오류 처리·정책을 재평가하지 않는다.

검증 대상은 다음 네 경로이다.

1. **Base + PTO만:** Worktime·Payroll이 없는 독립 임시 루트에 PTO 모듈과 합성 예제만 배치하고, 기존 PTO CLI를 실행해 합성 두 직원의 결과 파일·미승인 상태를 확인한다.
2. **Base + Worktime만:** PTO·Payroll이 없는 독립 임시 루트에서 기존 Source Mapping **정규화 JSON** 합성 입력을 사용하여 미마감 Worktime JSON을 생성한다.
3. **Base + Payroll만:** PTO·Worktime이 없는 독립 임시 루트에서 기존 합성 Payroll 구성 및 기존 Worktime **결과 JSON 파일만** 제공해 검토용 계산 산출물을 생성한다. Worktime 모듈 코드는 복사하지 않는다. 승인된 Worktime close 검증기를 요구하는 Payroll 모듈도 별도 import를 검사한다.
4. **Worktime → Payroll 인계:** 모듈을 서로 다른 임시 루트에 격리하고, Worktime이 만든 합성 `worktime-result.json` **파일만** Payroll 입력 계약에 전달해 기존 `schema_version: "0.1"`·검토 상태와 미확정 경계가 보존되는지 확인한다.

테스트는 Python 표준 `unittest`, 기존 Hermes uv Python, **현재 설치된** 공통 패키지(`openpyxl`, `korean-lunar-calendar`)만 사용한다. 별도 pip/uv install, 인터넷, Hermes Tool·Slack·Drive·외부 인증이 필요하지 않다. 실제 회사/직원 데이터는 사용하지 않는다.

## 발견된 의존성 및 변경

Payroll 이전 후 다음 두 경로가 여전히 Worktime 패키지의 `worktime_close.py`를 직접 참조하고 있었다.

- `payroll-calculator/functions/payroll_standalone_input.py`의 선택적 **승인된 근태 마감 Receipt** 검증
- `payroll-calculator/functions/payroll_register.py`의 import 시 로딩하는 Worktime 마감 검증기

이 경로는 **Base + Payroll만** 설치했을 때 Worktime 코드가 없어 실패할 수 있으므로, 이를 수정하지 않고 테스트만 통과시키는 것은 상호배타 요구사항을 만족하지 않는다.

- 이미 이전·검증한 `worktime-calculator/functions/worktime_close.py`를 **바이트 단위 그대로** `common/contracts/worktime_close.py`에 추가했다. 소스 Git blob SHA `734388f88992aa461bad42e44929e027a00e4adc`를 유지한다.
- Payroll의 두 참조 경로만 위의 **공통 Base 사본**을 바라보게 변경했다. Worktime 원본 파일·계산 로직·Receipt 검증 함수 본문은 수정하지 않았다.
- Payroll `migration-manifest.json`의 경로 역변환 대상이 기존 8개에서 **10개**가 되었고, 원본 동일성 자원은 4개에서 **5개**가 되었다. 기존 원본을 복원했을 때의 SHA가 같은지 `test_payroll_migration.py`에서 재확인한다.
- `run.py`는 설치되지 않은 다른 계산기 이름으로 호출되면 Python traceback 대신 기존 `UNAVAILABLE`, exit 2를 반환한다. `install.py --check`는 실제 존재하는 모듈만 안내한다. **모듈 설치/제거 작업 자체를 수행하지 않는다**.

## 서버 1차 실행에서 확인한 테스트 환경 차이 (2026-11-10)

상호배타 테스트 최초 실행 결과 **7개 중 6개 통과, 1개 테스트의 하위 사례 3건 실패**. 세 하위 사례 모두 `install.py --check`에서 `korean-lunar-calendar: NOT INSTALLED`를 반환했다. 반면 **PTO 단독 실행, Worktime 단독 실행, Payroll 단독 실행, Payroll의 Worktime 미설치 상태 import, 미설치 모듈 차단, Worktime JSON → Payroll 인계는 통과**했다.

원인은 `_run()`의 **의도적인 실행 격리**와 `install.py --check`의 **Python 패키지 설치 여부 검사**를 같은 환경으로 실행한 데 있었다. `_run()`은 `HOME`과 환경을 임시 루트로 제한하고 Python `-E`로 환경변수를 무시하도록 설계되어, Hermes의 실제 uv 환경에서 접근 가능한 패키지 배포 메타데이터도 숨길 수 있다. 따라서 의존성이 실제 없다고 결론 내릴 수 없다.

**테스트 하네스만 수정:** 계산기 3종의 **실제 CLI 독립 실행은 기존 `_run()` 격리를 그대로 유지**한다. 오직 설치된 배포판 버전을 확인하는 읽기 전용 `install.py --check`만 정상 Hermes 프로세스 환경을 상속해 호출하고, 출력에 실제 설치된 **선택된 모듈 하나**만 표시되는지도 검사한다. `install.py` 및 계산 모듈 본문은 수정하지 않는다. 정상 환경에서 `install.py --check`는 앞선 서버 검사에서 의존성 둘 다 발견한 이력이 있다.

수정 후 서버 **재검증 전**이며, 성공 여부는 아래 재실행 결과에 따라 판정한다.

## 실행

PR 브랜치를 직접 서버에 가져온 다음 Portfolio 저장소에서 다음 테스트를 실행한다.

```sh
sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_module_isolation.py' -v

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python -m unittest discover \
  -s bhandara/tests -p 'test_*.py' -v

sudo docker exec -w /opt/agent-config/.external/portfolio hermes \
  /opt/hermes/.venv/bin/python install.py --check
```

추가로 기존 Gearbox와의 경로 충돌이 없는지 검증한다. **반드시 공식 실행기**를 사용한다. 개별 Payroll `unittest discover`에는 필요한 `PYTHONPATH`가 없으므로 공식 실행기와 동일한 조건이 아니다.

```sh
sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python gearbox/_tests/core_run.py

sudo docker exec -w /opt/agent-config hermes \
  /opt/hermes/.venv/bin/python gearbox/_tests/run.py
```

## 판정 조건

- **PASS:** 7개 상호배타 테스트, Portfolio 전체 unittest, Base 의존성 점검, Gearbox 공식 기능·인프라 회귀 테스트가 통과한다.
- **FAIL:** Base + 모듈 하나만 있는 환경에서 모듈이 다른 계산기 코드나 Gearbox를 찾으려 하거나, 기존 입력·결과 계약을 보존하지 못한다. 원인을 해당 import/경로에 한정해 보완한다.
- **비범위:** 실제 직원자료, 승인/마감 실행, 세금·보험, 기능 정합성·법령 준수, 정책/예외 처리 개선, Hermes 운영 Pipeline 자동 전환.

생성된 임시 설치·합성 실행 파일은 `TemporaryDirectory`가 테스트 종료 시 삭제한다. 외부 저장소·운영 자료·기존 Gearbox 계산기 내용은 수정하지 않는다.
