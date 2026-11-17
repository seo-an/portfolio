# Common — 재사용 라이브러리와 독립 실행 도구

Common의 `io/`, `config/`, `validation/`, `runtime/`, `utils/`, `contracts/`는 다른 계산기가 필요할 때 import하는 **공통 라이브러리**입니다.

반면 `module/normalizer/`는 **에이전트가 개별 호출하도록 등록할 수 있는 독립 실행 모듈**입니다. 자신만의 `module.json`, `user_settings.py`, `input/`, `output/`을 가지며 다른 계산기 또는 Common 라이브러리에 의존하지 않습니다.

- [Normalizer 파일 준비·실행 안내](module/normalizer/RUNBOOK.md)
- [공통 Python 라이브러리 설명](README.md)

Normalizer를 호출했다고 PTO·Worktime·Payroll이 자동 실행되지는 않습니다. 다른 계산기의 출력 파일 경로가 입력으로 쓰일 수는 있지만 각 모듈은 자체 입력 계약을 검증해야 합니다.
