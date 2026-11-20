"""Thin JSON-configured Workflow across the independent Bhandara Tools.

No calculation, inferred approvals, database, source-file copies or daemon.
Only explicit upstream runs or SHA-pinned reusable artifacts may feed Payroll.
"""
from __future__ import annotations

from datetime import datetime
from importlib import import_module
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from typing import Any
from zoneinfo import ZoneInfo

from bhandara.common.io.input_layout import period_bounds
from bhandara.common.utils.hashing import sha256_file


RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
PTO_ARTIFACTS = {
    "usage-ledger": ("usage-ledger-result.xlsx", "pto_usage"),
    "deduction-quantity": ("deduction-quantity-result.xlsx", "pto_deduction"),
    "closing": ("closing-result.xlsx", "pto_closing"),
}


class WorkflowError(ValueError):
    """A rejected handoff is never treated as a Payroll approval."""


def _json(path: Path, field: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise WorkflowError(f"{field}: JSON을 읽을 수 없습니다") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{field}: JSON 객체가 필요합니다")
    return value


def _path(value: Any, base: Path, field: str, *, file: bool = True) -> Path:
    if type(value) is not str or not value.strip():
        raise WorkflowError(f"{field}: 명시적 경로가 필요합니다")
    candidate = Path(value).expanduser()
    path = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if file and not path.is_file():
        raise WorkflowError(f"{field}: 파일이 없습니다")
    return path


def _tool_spec(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("action") not in ("run", "reuse"):
        raise WorkflowError(f"tools.{name}: action=run/reuse 필요")
    key = "config" if value["action"] == "run" else "artifacts"
    if set(value) != {"action", key}:
        raise WorkflowError(f"tools.{name}: action과 {key}만 허용합니다")
    if key == "artifacts" and not isinstance(value[key], dict):
        raise WorkflowError(f"tools.{name}.artifacts: 객체가 필요합니다")
    return value


def _load_workflow(config_file: str | Path) -> dict[str, Any]:
    path = Path(config_file).expanduser().resolve()
    doc = _json(path, "workflow config")
    if set(doc) != {"schema_version", "workflow", "payroll_period", "run_id", "tools"}:
        raise WorkflowError("workflow: 정확한 최상위 키가 필요합니다")
    if (doc["schema_version"], doc["workflow"]) != ("1.0", "payroll"):
        raise WorkflowError("workflow/schema_version: payroll/1.0 필요")
    try:
        first, last = period_bounds(doc["payroll_period"])
    except (ValueError, TypeError) as exc:
        raise WorkflowError("payroll_period: YYYY-MM 필요") from exc
    run_id = doc["run_id"]
    if run_id == "auto":
        run_id = datetime.now(ZoneInfo("Asia/Seoul")).strftime("wf-%Y%m%d-%H%M%S-%f")
    if type(run_id) is not str or RUN_ID.fullmatch(run_id) is None:
        raise WorkflowError("run_id: 영문·숫자·-·_ 1~64자 필요")
    tools = doc["tools"]
    if (not isinstance(tools, dict)
            or not {"worktime", "payroll"} <= set(tools)
            or set(tools) - {"paid-time-off", "worktime", "payroll"}):
        raise WorkflowError("tools: worktime, payroll 필수; paid-time-off 선택")
    worktime = _tool_spec(tools["worktime"], "worktime")
    pto = _tool_spec(tools["paid-time-off"], "paid-time-off") if "paid-time-off" in tools else None
    payroll = tools["payroll"]
    if not isinstance(payroll, dict) or set(payroll) != {"config"}:
        raise WorkflowError("tools.payroll: config만 허용합니다")
    configs = {"payroll": _path(payroll["config"], path.parent, "tools.payroll.config")}
    for name, spec in (("worktime", worktime), ("paid-time-off", pto)):
        if spec is not None and spec["action"] == "run":
            configs[name] = _path(spec["config"], path.parent, f"tools.{name}.config")
    return {
        "period": doc["payroll_period"], "from": first, "to": last,
        "run_id": run_id, "tools": tools, "configs": configs,
    }


def _absolute_tool_config(path: Path) -> dict[str, Any]:
    """Resolve the *original* JSON base before preparing a temporary override."""
    doc = _json(path, path.name)
    root = _path(doc.get("input_root"), path.parent, "input_root", file=False)
    output = _path(doc.get("output_root"), path.parent, "output_root", file=False)
    doc["input_root"], doc["output_root"] = str(root), str(output)
    for section in ("files", "source_files"):
        if section in doc:
            if not isinstance(doc[section], dict):
                raise WorkflowError(f"{section}: 객체가 필요합니다")
            doc[section] = {
                key: str(_path(value, root, f"{section}.{key}", file=False))
                for key, value in doc[section].items()
            }
    return doc


def _validate_run_configs(plan: dict[str, Any]) -> dict[str, Any]:
    """Catch period mismatches and missing approval sources before upstream work."""
    payroll = _absolute_tool_config(plan["configs"]["payroll"])
    if payroll.get("payroll_period") != plan["period"]:
        raise WorkflowError("payroll config: workflow 기간과 불일치")
    if payroll.get("tool") != "payroll" or payroll.get("schema_version") != "1.0":
        raise WorkflowError("payroll config: Tool 계약 불일치")
    from bhandara.payroll.tool_cli import REQUIRED_SOURCES
    sources = payroll.get("source_files")
    if not isinstance(sources, dict) or not REQUIRED_SOURCES <= set(sources):
        raise WorkflowError("payroll: 필수 외부 승인/정책 JSON 역할이 누락됐습니다")
    for name, file in sources.items():
        if not Path(file).is_file():
            raise WorkflowError(f"payroll.source_files.{name}: 파일이 없습니다")
    # Strict seven-workbook input set stays owned by the Payroll reader.
    contract = _json(Path(__file__).parent / "payroll" / "input-files.json",
                     "payroll input contract")
    for name, item in contract["workbooks"].items():
        if not (Path(payroll["input_root"]) / contract["input_directory"]
                / item["filename"]).is_file():
            raise WorkflowError(f"payroll workbook: {name} 누락")
    if (Path(payroll["output_root"]) / plan["run_id"]).exists():
        raise WorkflowError("payroll: run_id 결과가 이미 있습니다 (덮어쓰기 금지)")
    for name in ("worktime", "paid-time-off"):
        if name not in plan["configs"]:
            continue
        config = _json(plan["configs"][name], f"{name} config")
        if config.get("tool") != name or config.get("schema_version") != "1.0":
            raise WorkflowError(f"{name}: Tool 계약 불일치")
        if name == "worktime":
            if (config.get("period_from"), config.get("period_to")) != (plan["from"], plan["to"]):
                raise WorkflowError("worktime: Payroll 기간과 불일치")
            if "output" not in config.get("steps", []):
                raise WorkflowError("worktime: output 단계가 필요합니다")
        else:
            if (not isinstance(config.get("as_of_date"), str)
                    or not plan["from"] <= config["as_of_date"] <= plan["to"]):
                raise WorkflowError("paid-time-off: 실행 기준일은 급여월 내여야 합니다")
            if not {"usage-ledger", "deduction-quantity"} <= set(config.get("steps", [])):
                raise WorkflowError("paid-time-off: usage-ledger와 deduction-quantity 필요")
            if "closing" in config.get("steps", []):
                raise WorkflowError("paid-time-off: 미확정 Closing은 Payroll에 연결할 수 없습니다")
    if "paid-time-off" in plan["tools"] and "pto_claims" not in sources:
        raise WorkflowError("payroll.source_files.pto_claims: PTO 신청 승인 상세가 필요합니다")
    if "paid-time-off" not in plan["tools"] and any(
        name in payroll.get("files", {})
        for name in ("pto_usage", "pto_deduction", "pto_closing")
    ):
        raise WorkflowError("payroll.files: PTO를 사용하려면 Workflow에 명시하세요")
    return payroll


def _record(path: str | Path, filename: str, period: dict[str, Any],
            *, pinned: dict[str, Any] | None = None) -> dict[str, str]:
    artifact = Path(path).expanduser().resolve()
    if not artifact.is_file() or artifact.name != filename:
        raise WorkflowError(f"handoff {filename}: 정확한 결과 파일이 필요합니다")
    run_id = artifact.parent.name
    if RUN_ID.fullmatch(run_id) is None:
        raise WorkflowError(f"handoff {filename}: 실행 폴더 run_id 불일치")
    digest = sha256_file(artifact)
    if pinned is not None:
        fields = {"path", "run_id", "period_from", "period_to", "sha256"}
        if set(pinned) != fields:
            raise WorkflowError(f"handoff {filename}: 경로/run_id/기간/SHA256 필요")
        if (pinned["run_id"], pinned["period_from"], pinned["period_to"]) != (
                run_id, period["from"], period["to"]):
            raise WorkflowError(f"handoff {filename}: run_id 또는 기간 불일치")
        if (type(pinned["sha256"]) is not str
                or SHA256.fullmatch(pinned["sha256"]) is None
                or pinned["sha256"] != digest):
            raise WorkflowError(f"handoff {filename}: SHA256 불일치")
    return {"path": str(artifact), "run_id": run_id, "sha256": digest,
            "period_from": period["from"], "period_to": period["to"]}


def _reuse(spec: dict[str, Any], expected: dict[str, str],
           period: dict[str, Any]) -> dict[str, dict[str, str]]:
    values = spec["artifacts"]
    if set(values) != set(expected):
        raise WorkflowError(f"handoff: 정확한 artifact 역할 필요 {sorted(expected)}")
    if any(not isinstance(value, dict) for value in values.values()):
        raise WorkflowError("handoff: artifact별 파일 참조 객체 필요")
    return {
        key: _record(data.get("path"), filename, period, pinned=data)
        for key, (data, filename) in (
            (key, (values[key], expected[key])) for key in expected
        )
    }


def _execute_upstream(name: str, plan: dict[str, Any],
                      expected: dict[str, str]) -> dict[str, dict[str, str]]:
    spec = plan["tools"][name]
    if spec["action"] == "reuse":
        return _reuse(spec, expected, plan)
    module = import_module(f"bhandara.{name}.tool_cli")
    output = module.execute(plan["configs"][name])
    if not set(expected) <= set(output):
        raise WorkflowError(f"{name}: 필요한 결과 역할이 생성되지 않았습니다")
    return {key: _record(output[key], filename, plan)
            for key, filename in expected.items()}


def _guard_handoffs(artifacts: dict[str, dict[str, str]],
                    payroll: dict[str, Any]) -> None:
    for role, record in artifacts.items():
        path = Path(record["path"])
        if path.is_relative_to(Path(payroll["output_root"])):
            raise WorkflowError(f"{role}: Payroll output_root 내부 원본 사용 금지")
        if sha256_file(path) != record["sha256"]:
            raise WorkflowError(f"{role}: 파일 내용이 인계 후 변경됐습니다")


def execute(config_file: str | Path) -> dict[str, Any]:
    """Run only selected upstream Tools; Payroll's existing Flow runs once."""
    plan = _load_workflow(config_file)
    payroll = _validate_run_configs(plan)
    # Reuse references are verified *before* invoking any calculators.
    pto_spec = plan["tools"].get("paid-time-off")
    wt_spec = plan["tools"]["worktime"]
    if pto_spec and pto_spec["action"] == "reuse":
        _reuse(pto_spec, {key: value[0] for key, value in PTO_ARTIFACTS.items()
                         if key in pto_spec["artifacts"]}, plan)
    if wt_spec["action"] == "reuse":
        _reuse(wt_spec, {"output": "worktime-result.xlsx"}, plan)
    pto = None
    if pto_spec is not None:
        keys = ("usage-ledger", "deduction-quantity")
        expected = {key: PTO_ARTIFACTS[key][0] for key in keys}
        if pto_spec["action"] == "reuse" and "closing" in pto_spec["artifacts"]:
            expected["closing"] = PTO_ARTIFACTS["closing"][0]
        pto = _execute_upstream("paid-time-off", plan, expected)
    worktime = _execute_upstream("worktime", plan, {"output": "worktime-result.xlsx"})
    selected = {"worktime": worktime["output"]}
    # Never retain PTO references from a previous standalone Payroll config.
    # Only this Workflow's explicitly selected SHA-pinned artifacts may pass.
    for stale in ("pto_usage", "pto_deduction", "pto_closing"):
        payroll["files"].pop(stale, None)
    payroll["files"]["worktime"] = worktime["output"]["path"]
    if pto is not None:
        for key, record in pto.items():
            selected["pto_" + key] = record
            payroll["files"][PTO_ARTIFACTS[key][1]] = record["path"]
    _guard_handoffs(selected, payroll)
    payroll["run_id"] = plan["run_id"]
    # Temporary JSON contains paths only; never duplicates raw HR/approval data.
    with TemporaryDirectory(prefix="bhandara-workflow-") as directory:
        cfg = Path(directory) / "payroll.json"
        cfg.write_text(json.dumps(payroll, ensure_ascii=False), encoding="utf-8")
        from bhandara.payroll.tool_cli import execute as run_payroll
        results = run_payroll(cfg)
    _guard_handoffs(selected, payroll)
    return {"workflow": "payroll", "run_id": plan["run_id"],
            "period": plan["period"], "status": "PARTIAL_REVIEW_ONLY",
            "approval_state": "NOT_APPROVED", "handoff": selected,
            "artifacts": results}


def main(config_file: str | Path) -> int:
    try:
        report = execute(config_file)
    except (ValueError, OSError, TypeError, KeyError, ImportError) as exc:
        print(f"BHANDARA_WORKFLOW_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
