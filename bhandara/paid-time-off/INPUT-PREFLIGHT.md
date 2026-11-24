# PTO 입력자료 사전검사 계약

계산 전 Excel의 소비 Module별 입력 적합성을 검사한다. 기존 Reader를 재사용하며 별도 양식 규칙 사본을 만들지 않는다. 기존 계산 CLI의 동작은 바뀌지 않는다.

## 요청 / 응답

```bash
python -B -m bhandara.paid-time-off.input_preflight /path/to/input.xlsx
```

호출자는 신뢰된 로컬 실행 환경에서 파일을 지정한다. Gearbox는 실제 Slack 파일을 검증한 후 보호된 임시 경로로 전달해야 한다. 원본 파일 경로나 사용자 제공 경로를 모델에 노출하지 않는다.

응답 JSON: schema_version=1.0, tool=paid-time-off, operation=inspect_input, status=OK, review_only=true, approved=false. checks 배열의 각 항목은 module, role, status, missing_headers를 포함한다. MATCH는 해당 Module의 기존 Reader가 입력을 받아들였다는 뜻이며 계산 결과의 승인이나 전체 실행 가능성을 뜻하지 않는다. MISSING_HEADERS는 승인휴가의 필수 헤더 누락을 나타낸다. REJECTED는 해당 역할에 부적합하거나 읽을 수 없는 파일이다. 동일 role에 대해 Module별 결과가 다를 수 있다. 오류에 개인 정보, 경로, 행 값, 예외 원문을 포함하지 않는다.

프로세스 성공 및 status=OK는 검사 요청 처리가 완료되었다는 뜻으로, HTTP 200과 유사하다. MATCH가 없거나 복수여도 응답 자체는 성공이다. Gearbox는 실행 오류, 응답 계약 불일치, 양식 불일치를 별도 처리해야 한다. 복수 역할이 일치하면 사용자에게 확인한다.

검사는 원본을 변경하거나 계산, 결과 파일 생성, 작업공간 생성을 수행하지 않는다. 계산 기준일, 정책, 파일 간 연결, 행별 계산 진단은 기존 Module 실행에서 최종 검증한다. 현재 검사는 PTO의 사용자 업로드 역할만 대상으로 하며, 이미 생성된 결과 Artifact의 무결성 및 버전 검증을 대체하지 않는다.

## 검증

```bash
python -B -m unittest discover -s bhandara/tests -p 'test_pto_input_preflight.py' -v
```

Gearbox 실행 연결은 별도 PR에서 진행한다.
