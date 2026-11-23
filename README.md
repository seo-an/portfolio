> **2026-11-23 PTO Cycle 운영 갱신:** 계산 저장소 `portfolio`의 독립 PTO Module을 실행하는 **Ananda 자연어 → 인증된 Native Gateway → 실제 Slack 검토용 Excel 전송** 연결이 `seo-an/agent-config` PR #258·#260·#262·#261을 통해 운영 배포됐다. 사용자 보고 `PTO_CYCLE_DEPLOY=PASS`; Entitlement·Deduction Quantity·Usage Ledger·Closing 네 결과 Excel의 합성 Slack 검증 완료. 원본 삭제 뒤 기존 결과 스냅샷은 AVAILABLE/STALE로 유지하는 새 계약은 `agent-config` 소유다. **Worktime·Payroll의 모든 Module Slack Cycle 및 전체 Workflow E2E 완료를 뜻하지 않는다.** 이전 'PTO 운영 연결 미완료' 문구는 당시 이력이다. 현행 운영 절차: [PTO Cycle Runbook](https://github.com/seo-an/agent-config/blob/main/operations/runbooks/pto-cycle-operations.md), [최종 인수인계](https://github.com/seo-an/agent-config/blob/main/operations/handoffs/cycle-pto-operations-handoff-20261123.md).

# Bhandara — HR 계산·검토용 독립 Python Tools

> **2026-11-21 운영 갱신:** 11월 20일의 `Slack 실제 운영 미검증` 문구는 당시 기록이다. 이후 **파일-only ACK, 파일 업로드 후 스레드 자연어 집계, 파일+자연어 동시 집계, `&bhandara review attendance`**가 합성 CSV를 사용한 실제 Slack에서 PASS로 확인됐다. 단, **Worktime/Payroll 전체 Tool의 Slack Cycle E2E, 내부 모든 Module의 독립 연결, 다중 Payroll 첨부의 파일 역할 매핑은 여전히 미검증/미연결**이다. PTO 네 Module은 이후 2026-11-23 별도로 실증됐다. 최신 판단·다음 단계: [2026-11-21 인수인계](bhandara/OPERATIONS-HANDOFF-2026-11-21.md). Hermes 긴급 `&delete`는 agent-config 코드 병합까지 완료됐으나 최신 이미지 배포/실제 삭제 운영 검증은 미확인이다.


Bhandara는 **Paid Time Off(유급휴가), Worktime(근태), Payroll(급여)** 세 Tool과 이들을 명시적으로 연결하는 **Workflow**를 제공한다. 각 Tool은 독립 JSON 설정으로 실행할 수 있으며, 공통 Excel 읽기·직원 ID·출입업체 매핑·파일 SHA-256 검증 기능을 공유한다.

> **2026-11-20 현황:** 세 Tool과 Workflow 연결은 구현·병합됐다(Portfolio #80). 구형 계산 경로 철수(#81), Excel 원본 보호·실행용 폴더·Git 제외(#82)도 병합됐다. Hermes 자연어 Index·Ananda 출입원장 파일 Module 코드는 agent-config #211에서 병합되고 합성 테스트됐다. **실제 Slack 도구 발견·파일 전송·후속 무응답 재발 여부는 운영 배포 후 확인해야 한다.** 독립 Tool 내부 모든 Module을 Slack에서 개별 실행하는 기능은 아직 연결되지 않았다.

## 구성

| 실행 단위 | 기능 | 기본 출력 | 설정 예시 |
|---|---|---|---|
| Paid Time Off | 발생·차감·사용원장, 선택 마감 | `deduction-quantity-result.xlsx`, `usage-ledger-result.xlsx`, 선택 `closing-result.xlsx` | [설정](bhandara/paid-time-off/config.example.json) |
| Worktime | 스케줄·출입검토·휴게·근로 사실 | `worktime-result.xlsx` / `WORKTIME` 10열 | [설정](bhandara/worktime/config.example.json) |
| Payroll | 7종 단일시트 Excel, 별도 승인·정책 JSON을 한 번 검토 | `payroll-result.xlsx` / `PAYROLL`, `payroll-review.json` | [설정](bhandara/payroll/config.example.json) |
| Workflow | 기존 결과 검증/재사용, 호출 순서와 명시적 경로 인계 | 위 Payroll 출력 및 실행별 handoff | [설정](bhandara/workflow.example.json) |
| Common Normalizer | 명시적 열 매핑·검토 | 정규화·검토 JSON | [사용법](bhandara/common/module/normalizer/RUNBOOK.md) |

**용어:** Module은 독립 기능, Flow는 하나의 Tool 내부에서 선택된 Module 순서, Tool은 개별 실행 단위, Workflow는 여러 Tool을 조합하는 호출·인계다. `flow/` 물리 폴더나 복잡한 DB는 없다.

## 설치

Python **3.12 이상**과 [uv](https://docs.astral.sh/uv/)를 사용한다.

```bash
git clone https://github.com/seo-an/portfolio.git
cd portfolio
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python install.py --check
```

시스템 Python 대신 해당 환경의 Python으로 실행한다. 비공개 원본·승인 자료·개인 JSON을 Git에 커밋하지 않는다.

## 실행

```bash
mkdir -p bhandara/data/config
cp bhandara/paid-time-off/config.example.json bhandara/data/config/paid-time-off.json
cp bhandara/worktime/config.example.json bhandara/data/config/worktime.json
cp bhandara/payroll/config.example.json bhandara/data/config/payroll.json
cp bhandara/workflow.example.json bhandara/data/config/workflow.json

.venv/bin/python run.py bhandara paid-time-off
.venv/bin/python run.py bhandara worktime
.venv/bin/python run.py bhandara payroll
.venv/bin/python run.py bhandara workflow
```

필요한 명령만 실행한다. 서로 다른 실행을 모두 연속 실행하라는 뜻은 아니다. **각 JSON에 기간·원본 경로·필수 승인/정책 JSON을 사용자가 명시적으로 지정해야 한다.** 각 Tool의 출력은 서로 다른 형제 출력 루트를 사용한다(예: `bhandara/data/output/worktime`). 원본이 없으면 안전하게 실패하며, 결과 파일을 임의 검색·덮어쓰기 하지 않는다.

실행 자세한 설명: [처음 사용하는 사람용 RUNBOOK](bhandara/RUNBOOK.md) · [Workflow 인계](bhandara/WORKFLOW.md) · [Common 계약](bhandara/BASE-CONTRACT.md).

## 실행 폴더 자동 생성과 Git 제외

각 JSON Tool(Paid Time Off·Worktime·Payroll) 또는 Workflow를 **한 번이라도 실행 시도하면**, 설정 JSON이나 입력 자료가 없어 계산이 실패하더라도 아래 **빈 안내용 폴더**가 자동 생성됩니다. 이전 파일과 폴더를 삭제·이동·덮어쓰지 않습니다.

```text
portfolio/
└── bhandara/
    └── data/                   # .gitignore: 실행·원본·결과 전부 제외
        ├── config/             # 개인 JSON 설정 파일
        ├── input/
        │   ├── common/         # 공통 직원정보(예: employee.xlsx)
        │   ├── paid-time-off/  # 휴가·근태 원본
        │   ├── worktime/       # 스케줄·출입원장
        │   └── payroll/        # 급여 Excel 7종 및 승인 JSON
        └── output/
            ├── paid-time-off/ # PTO 결과 <run_id>/
            ├── worktime/      # Worktime 결과 <run_id>/
            ├── payroll/       # Payroll 결과 <run_id>/
            └── workflow/      # 안내용 폴더 (계산 결과는 각 Tool별 출력)
```

실제로는 실행을 시도한 Tool의 `input/<tool>` 폴더와 `input/common`만 먼저 생성됩니다. 각 Tool의 `config.example.json`을 `bhandara/data/config/<tool>.json`에 **복사한 경우에만** 예시의 `input_root: "../input"`, `output_root: "../output/<tool>"`이 위 경로를 가리킵니다. 별도 JSON에서 설정한 외부 비공개 경로는 그대로 우선하며, 안내 폴더에 임의로 원본을 복사하거나 원본의 내용을 바꾸지 않습니다.

**Hermes Docker 예외:** Hermes는 `.external/portfolio` 코드를 **읽기 전용(`:ro`)**으로 마운트합니다. 따라서 컨테이너 안에서는 코드 저장소 아래 빈 안내 폴더를 새로 만들 수 없습니다. 이때 선택적 안내 폴더 생성만 건너뛰고, **사전 검증된 개인 JSON과 읽기·쓰기 가능한 별도 비공개 데이터 경로**로 실제 Tool을 실행합니다. `PermissionError`나 잘못된 폴더/심볼릭 링크는 건너뛰지 않고 거부합니다. 안내용 기본 `bhandara/data` 경로는 **호스트/로컬의 쓰기 가능한 체크아웃에서 Tool을 실행할 때** 자동 생성됩니다. 읽기 전용 코드 위치를 결과 폴더로 우회하거나 강제 쓰기하지 않습니다.

**출력 보존:** 동일한 `run_id`가 이미 있으면 작업을 중단합니다. Worktime·Payroll XLSX 저장도 생성 전용 모드(`xb`)라 파일 존재 확인과 실제 저장 사이에 다른 파일이 생겨도 덮어쓰지 않습니다. Git은 `bhandara/data/**` 및 Tool별 실행 폴더를 무시하지만, `bhandara/tests/`의 공개 합성 샘플은 등록할 수 있습니다. 실직원 자료는 Git 작업 폴더보다 Git 밖의 승인된 비공개 디렉터리 사용을 권장합니다.

## 지급·보안 경계

Payroll이 표시하는 지급합계·공제합계·실지급 차액은 **잠정 금액**이며 `NOT_APPROVED` 상태다. 외부 승인 없이 지급, 세금·보험 신고, 자동 송금하지 않는다. Worktime의 근로 사실만으로 추가수당을 승인하지 않는다. PTO Closing은 **확정된 원본만** 지급 검토에 연결한다. 산재보험료와 회사 비용(확인분)은 관리자용이며 직원별 조회에서 제외한다.

실직원·급여 원본, 승인 JSON, 직원 ID 매핑은 Git/일반 로그·비공개가 아닌 채널에 넣지 않는다. Slack 수신·권한 확인·3시간 선택 캐시 등은 이후 [운영 연결](bhandara/OPERATIONS-HANDOFF-2026-11-20.md)에서 다룬다.

## 테스트

```bash
.venv/bin/python -B bhandara/_tests/run.py
```

표준 `unittest`를 사용한다. **별도 50명 Golden E2E는 필수 아님.** 운영 연결 변경 시 Gearbox 기능·인프라 테스트를 분리해서 수행한다.
