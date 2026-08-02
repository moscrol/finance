"""验收台账：28 道题的进度只从这里生成，不从记忆里写。

三个子命令：
  board   读最近一次 run 记录，打印看板（题 / 期望 / 实测 / 通过 / 失败分类 / 证据路径）
  run     走用户真实点击的那条路径（POST /api/conversations/{id}/messages），落 trace
  freeze  冻结 codex / knevo 的参照答案快照（人工粘贴，禁止被测方自己生成）

设计取舍：
- **不内联评分逻辑。** 判定沿用 intelligence/eval/agent_eval.py 的确定性闸；这里只负责
  「跑真实路径 + 落证据 + 出看板」。分数是可复算的数，不是叙述。
- **trace 落成 JSONL 而不是接 OpenTelemetry。** 当前瓶颈是"用户看不到中间过程"，
  不是"查询不方便"；等题量上规模再换 Langfuse / OTel 这类带 UI 的方案。
- **参照快照必须外部冻结。** 被测方不得重新生成自己的基准，否则考生兼出题人。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from intelligence.eval.acceptance_observations import (
    ObservationArtifactError,
    REFERENCE_ELIGIBILITY_PATH,
    load_observation_artifact,
)
from intelligence.eval.acceptance_axes import (
    AxisState,
    InformationComparison,
    project_axes,
)
from intelligence.eval.acceptance_comparison import (
    ComparisonArtifactError,
    build_comparison_queue,
    load_comparison_queue,
    load_comparison_result,
    write_comparison_queue,
)
from intelligence.eval.acceptance_runs import (
    RunArtifactError,
    load_validated_run,
    select_latest_case_runs,
)
from intelligence.eval.acceptance_verdict import (
    ExperienceState,
    OperationalState,
    VerdictState,
    VERDICT_OVERLAY_PATH,
    compile_case_contract,
    evaluate_case,
    load_verdict_overlay,
)

REPO = Path(__file__).resolve().parents[2]
CASES_PATH = REPO / "intelligence/eval/cases/acceptance_cases.json"
EXECUTION_CONTRACTS_PATH = (
    REPO / "intelligence/eval/cases/acceptance_execution_contracts.json"
)
RUNS_DIR = REPO / "intelligence/eval/runs"
SNAPSHOT_DIR = REPO / "intelligence/eval/cases/reference_snapshots"
DEFAULT_BASE = "http://127.0.0.1:8799"
DEFAULT_USER = "linxiaoqi5111"
EXECUTION_PATHS = frozenset(
    {
        "continuous_episode",
        "continuous_fast_path",
        "continuous_clarification",
        "legacy_direct",
    }
)


def load_cases() -> dict[str, Any]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def load_execution_contracts() -> dict[str, str]:
    """Load an explicit path for every frozen case and fail closed on drift."""

    payload = json.loads(EXECUTION_CONTRACTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("invalid execution contract schema")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, dict):
        raise ValueError("execution contract cases must be an object")
    case_ids = {str(case.get("id")) for case in load_cases().get("cases", [])}
    if set(raw_cases) != case_ids:
        missing = sorted(case_ids - set(raw_cases))
        extra = sorted(set(raw_cases) - case_ids)
        raise ValueError(
            f"execution contract case ids drifted (missing={missing}, extra={extra})"
        )
    result: dict[str, str] = {}
    for case_id, raw_path in raw_cases.items():
        path = str(raw_path or "").strip()
        if path not in EXECUTION_PATHS:
            raise ValueError(f"invalid execution path for {case_id}: {path}")
        result[str(case_id)] = path
    return result


def _rel(path: Path) -> str:
    """相对仓库根显示；路径在仓库外时退回绝对路径而不是抛异常。"""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


@dataclass
class TurnTrace:
    """一次真实回答的完整轨迹 —— 用户不用问我，打开这个文件就能看到发生了什么。

    字段名对齐 runtime 真实返回的形状，别自创：
    - 消息体给 ``invoked_skill_ids`` / ``citations`` / ``degrades``，**没有**
      ``tools_called``。早先版本读 ``tools_called``，于是每条轨迹的工具信息
      恒为空 —— 看板显示 tools=0 却不是真没调工具，是探针探错了地方。
    - 真正能区分「取到证据后回答」和「取不到证据而降级」的是
      ``/api/runs/{run_id}/context`` 的 ``evidence[]``：C1 绑定 6 条证据正常
      作答，A4 绑定 0 条直接降级拒答。这是判空答/假拒答的唯一可靠信号。
    """

    question: str
    answer: str | None = None
    conversation_id: str | None = None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    run_id: str | None = None
    parent_run_id: str | None = None
    expected_execution_path: str | None = None
    execution_path: str | None = None
    terminal_owner: str | None = None
    attempt_id: str | None = None
    attempt_index: int | None = None
    runtime_instance_id: str | None = None
    task_frame_hash: str | None = None
    cutoff: str | None = None
    artifact_receipt_valid: bool | None = None
    preflight_receipt_hash: str | None = None
    invoked_skill_ids: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    degrades: list[str] = field(default_factory=list)
    evidence_bound: int = 0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    trace_steps: list[str] = field(default_factory=list)
    synthesis_diagnostic: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    status: str = "unknown"
    error: str | None = None


@dataclass
class CaseRun:
    case_id: str
    tier: str
    turns: list[TurnTrace] = field(default_factory=list)
    blocked_reason: str | None = None
    conversation_id: str | None = None
    execution_diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExpectedRuntime:
    mode: str
    backend: str
    model: str
    revision: str
    code_root: str
    provider_label: str
    provider_protocol: str = "openai_responses"


@dataclass(frozen=True)
class PreflightReport:
    acceptance_eligible: bool
    failures: tuple[str, ...]
    expected: dict[str, object]
    observed: dict[str, object]
    receipt_hash: str

    @property
    def detail(self) -> str:
        if self.failures:
            return "; ".join(self.failures)
        runtime = self.observed.get("runtime")
        if isinstance(runtime, dict):
            return (
                f"revision={str(runtime.get('source_revision') or '')[:8]} "
                f"backend={runtime.get('agent_runtime', {}).get('backend')}"
            )
        return "preflight=ok"

    def __iter__(self):
        """Keep old diagnostic callers able to unpack ``(ok, detail)``."""

        yield not self.failures
        yield self.detail


# --------------------------------------------------------------------------- #
# run —— 走用户真实点击的那条路径
# --------------------------------------------------------------------------- #
def _post(url: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _get(url: str, timeout: float = 30.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def preflight(
    base: str,
    expected: ExpectedRuntime | None = None,
) -> PreflightReport:
    """部署接缝前置检查。跑不过就不许报进度 —— 这四道缝各自坑过一次。

    注意 /api/llm/config 当前恒定阻塞约 6s（疑似 Keychain 查询），所以 timeout
    必须给到 10s 以上，否则前置检查会因自身超时而误报『不可达』。
    """
    try:
        health = _get(f"{base}/api/health", timeout=10)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        failure = f"服务不可达: {type(exc).__name__}"
        return PreflightReport(
            acceptance_eligible=False,
            failures=(failure,),
            expected=(expected.__dict__ if expected is not None else {}),
            observed={},
            receipt_hash=_canonical_receipt_hash(
                {"expected": expected.__dict__ if expected else {}, "failure": failure}
            ),
        )

    runtime = health.get("runtime") or {}
    agent_runtime = runtime.get("agent_runtime") or {}
    deps = health.get("dependencies") or {}
    revision = runtime.get("source_revision") or ""

    failed: list[str] = []
    if health.get("status") != "healthy":
        failed.append(f"status={health.get('status')}")
    if not runtime.get("finance_root"):
        failed.append("finance_root 缺失")
    if not revision:
        failed.append("source_revision 缺失")
    for dep in ("repo_root", "knowledge_wiki", "relations", "market_snapshot"):
        if deps.get(dep) is False:
            failed.append(f"依赖 {dep} 不可用")
    if agent_runtime.get("ready") is False:
        failed.append(
            f"agent_runtime 未就绪（backend={agent_runtime.get('backend')}, "
            f"reason={agent_runtime.get('reason')}）"
        )
    if expected is not None and agent_runtime.get("ready") is not True:
        failed.append("agent_runtime.ready 必须为 true")

    if expected is not None:
        continuous = runtime.get("continuous_agent") or {}
        if continuous.get("mode") != expected.mode:
            failed.append(
                f"continuous_agent.mode={continuous.get('mode')!r}, expected={expected.mode!r}"
            )
        if runtime.get("source_dirty") is not False:
            failed.append("source_dirty 必须为 false")
        if revision != expected.revision:
            failed.append("source_revision 与 expected revision 不一致")
        observed_code_root = str(runtime.get("code_root") or "")
        if observed_code_root != str(Path(expected.code_root).expanduser().resolve()):
            failed.append("code_root 与 expected code root 不一致")
        import_root = str(runtime.get("import_root") or "")
        if import_root != observed_code_root:
            failed.append("import_root 与 code_root 不一致")
        if not str(runtime.get("runtime_instance_id") or "").strip():
            failed.append("runtime_instance_id 缺失")
        for key, value, label in (
            ("backend", agent_runtime.get("backend"), "backend"),
            ("model", agent_runtime.get("model"), "model"),
            ("provider_label", agent_runtime.get("provider_label"), "provider_label"),
            ("provider_protocol", agent_runtime.get("provider_protocol"), "provider_protocol"),
        ):
            expected_value = getattr(expected, key)
            if value != expected_value:
                failed.append(f"{label}={value!r}, expected={expected_value!r}")
        chain_size = agent_runtime.get("provider_chain_size")
        if chain_size != 1:
            failed.append(f"provider_chain_size={chain_size!r}, expected=1")

    try:
        cfg = _get(f"{base}/api/llm/config", timeout=15)
        if cfg.get("ready") is False or (
            expected is not None and cfg.get("ready") is not True
        ):
            failed.append("llm_config.ready=false（BYOK 凭据未就绪）")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        failed.append(f"llm/config 不可达: {type(exc).__name__}")

    if failed:
        pass
    observed = {
        "status": health.get("status"),
        "dependencies": {
            str(key): bool(value) for key, value in deps.items()
            if str(key) in {"repo_root", "knowledge_wiki", "relations", "market_snapshot"}
        },
        "runtime": {
            key: runtime.get(key)
            for key in (
                "runtime_instance_id",
                "source_revision",
                "source_dirty",
                "code_root",
                "import_root",
                "python_executable",
                "continuous_agent",
            )
            if key in runtime
        },
    }
    observed["runtime"]["agent_runtime"] = {
        key: agent_runtime.get(key)
        for key in (
            "backend",
            "ready",
            "reason",
            "model",
            "provider_label",
            "provider_protocol",
            "endpoint_fingerprint",
            "provider_chain_size",
        )
        if key in agent_runtime
    }
    expected_payload = expected.__dict__ if expected is not None else {}
    receipt_hash = _canonical_receipt_hash(
        {"expected": expected_payload, "observed": observed, "failures": failed}
    )
    return PreflightReport(
        acceptance_eligible=bool(expected is not None and not failed),
        failures=tuple(failed),
        expected=expected_payload,
        observed=observed,
        receipt_hash=receipt_hash,
    )


def _canonical_receipt_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fill_run_detail(base: str, trace: TurnTrace, *, user: str | None = None) -> None:
    """补 run 级证据绑定与步骤。取不到不算失败 —— 答案本身已经拿到了。"""
    if not trace.run_id:
        return
    user_query = f"?{urllib.parse.urlencode({'user': user})}" if user else ""
    try:
        ctx = _get(
            f"{base}/api/runs/{trace.run_id}/context{user_query}",
            timeout=15,
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        ctx = {}
    evidence = ctx.get("evidence") or []
    trace.evidence = list(evidence)
    trace.evidence_bound = sum(
        1 for e in evidence if isinstance(e, dict) and e.get("status") == "hit"
    )
    trace.gaps = list(ctx.get("gaps") or [])
    try:
        steps = _get(
            f"{base}/api/runs/{trace.run_id}/trace{user_query}",
            timeout=15,
        )
    except (urllib.error.URLError, TimeoutError, OSError):
        steps = []
    if isinstance(steps, list):
        trace.trace_steps = [
            str(s.get("name")) for s in steps if isinstance(s, dict) and s.get("name")
        ]
        trace.synthesis_diagnostic = _capture_synthesis_diagnostic(steps)


def create_conversation(base: str, user: str, title: str = "acceptance") -> str:
    payload = _post(
        f"{base}/api/conversations",
        {"title": title, "user": user},
    )
    conversation_id = str(
        payload.get("conversation_id") or payload.get("id") or ""
    ).strip()
    if not conversation_id:
        raise ValueError("create conversation response missing conversation_id")
    return conversation_id


def ask_turn(
    base: str,
    user: str,
    conversation_id: str,
    question: str,
    timeout: float,
    *,
    expected_path: str | None = None,
    preflight_receipt_hash: str | None = None,
) -> TurnTrace:
    """Submit one turn and wait for the exact assistant message returned by POST."""

    trace = TurnTrace(
        question=question,
        conversation_id=conversation_id,
        expected_execution_path=expected_path,
        preflight_receipt_hash=preflight_receipt_hash,
    )
    started = time.monotonic()
    try:
        submission = _post(
            f"{base}/api/conversations/{conversation_id}/messages",
            {"content": question, "skill_mode": "auto", "user": user},
        )
        trace.user_message_id = str(submission.get("user_message_id") or "")
        trace.assistant_message_id = str(
            submission.get("assistant_message_id") or ""
        )
        trace.run_id = str(submission.get("run_id") or "")
        if not all(
            (
                trace.user_message_id,
                trace.assistant_message_id,
                trace.run_id,
            )
        ):
            raise ValueError("turn submission response missing stable identifiers")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(2.0)
            messages_payload = _get(
                f"{base}/api/conversations/{conversation_id}/messages?user={user}"
            )
            items = (
                messages_payload
                if isinstance(messages_payload, list)
                else messages_payload.get("messages", [])
            )
            assistant = next(
                (
                    item
                    for item in items
                    if isinstance(item, dict)
                    and item.get("message_id") == trace.assistant_message_id
                ),
                None,
            )
            if assistant is None or assistant.get("status") in {
                None,
                "pending",
                "running",
            }:
                continue
            if assistant.get("run_id") != trace.run_id:
                raise ValueError("assistant message run_id differs from submission")
            _fill_terminal_trace(base, user, trace, assistant)
            break
        else:
            trace.status = "timeout"
            trace.error = f"超过 {timeout}s 未返回终态"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        trace.status = "error"
        trace.error = str(exc)
    trace.elapsed_s = round(time.monotonic() - started, 1)
    return trace


def _fill_terminal_trace(
    base: str,
    user: str,
    trace: TurnTrace,
    assistant: dict[str, Any],
) -> None:
    trace.answer = assistant.get("content")
    trace.status = str(assistant.get("status") or "unknown")
    trace.invoked_skill_ids = list(assistant.get("invoked_skill_ids") or [])
    trace.citations = list(assistant.get("citations") or [])
    trace.degrades = list(assistant.get("degrades") or [])
    if not trace.run_id:
        trace.error = "run_id_missing"
        return
    run = _get(f"{base}/api/runs/{trace.run_id}?user={user}")
    if not isinstance(run, dict):
        trace.error = "run_payload_invalid"
        return
    trace.parent_run_id = run.get("parent_run_id")
    provenance = _get(
        f"{base}/api/runs/{trace.run_id}/provenance?user={user}"
    )
    events = provenance.get("attempts") if isinstance(provenance, dict) else None
    if not isinstance(events, list):
        trace.error = "execution_provenance_missing"
        return
    finished = next(
        (
            item
            for item in reversed(events)
            if isinstance(item, dict)
            and item.get("event_type") == "attempt.finished"
            and item.get("run_id") == trace.run_id
        ),
        None,
    )
    if not isinstance(finished, dict):
        trace.error = "attempt_finished_missing"
        return
    attempt_id = str(finished.get("attempt_id") or "")
    bound = next(
        (
            item
            for item in reversed(events)
            if isinstance(item, dict)
            and item.get("event_type") == "execution.bound"
            and item.get("attempt_id") == attempt_id
        ),
        None,
    )
    started = next(
        (
            item
            for item in reversed(events)
            if isinstance(item, dict)
            and item.get("event_type") == "attempt.started"
            and item.get("attempt_id") == attempt_id
        ),
        None,
    )
    if not isinstance(bound, dict) or not isinstance(started, dict):
        trace.error = "attempt_binding_missing"
        return
    trace.attempt_id = attempt_id
    try:
        trace.attempt_index = int(started["attempt_index"])
    except (TypeError, ValueError):
        trace.error = "attempt_index_invalid"
        return
    trace.runtime_instance_id = str(started.get("runtime_instance_id") or "")
    trace.execution_path = str(bound.get("execution_path") or "")
    trace.terminal_owner = str(bound.get("terminal_owner") or "")
    trace.task_frame_hash = str(bound.get("task_frame_hash") or "")
    trace.cutoff = str(bound.get("cutoff") or "") or None
    if (
        trace.expected_execution_path is not None
        and trace.execution_path != trace.expected_execution_path
    ):
        trace.error = "execution_path_mismatch"
        return
    receipts = finished.get("artifact_receipts")
    if not isinstance(receipts, list):
        trace.error = "artifact_receipts_missing"
        return
    episode = next(
        (
            item
            for item in receipts
            if isinstance(item, dict)
            and item.get("path") == "continuous-episode.json"
        ),
        None,
    )
    if trace.execution_path == "continuous_episode":
        trace.artifact_receipt_valid = bool(
            isinstance(episode, dict)
            and episode.get("run_id") == trace.run_id
            and episode.get("attempt_id") == trace.attempt_id
            and episode.get("task_frame_hash") == trace.task_frame_hash
            and episode.get("cutoff") == trace.cutoff
            and re.fullmatch(
                r"[0-9a-f]{64}", str(episode.get("sha256") or "")
            )
        )
        if not trace.artifact_receipt_valid:
            trace.error = "continuous_episode_receipt_mismatch"
            return
    else:
        trace.artifact_receipt_valid = episode is None
        if not trace.artifact_receipt_valid:
            trace.error = "unexpected_continuous_episode_receipt"
            return
    _fill_run_detail(base, trace, user=user)


def run_case(
    base: str,
    user: str,
    case: Mapping[str, Any],
    *,
    timeout: float,
    preflight_receipt_hash: str,
    execution_contract: str,
) -> CaseRun:
    case_id = str(case["id"])
    case_run = CaseRun(case_id=case_id, tier=str(case["tier"]))
    try:
        conversation_id = create_conversation(base, user, "acceptance")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        case_run.blocked_reason = str(exc)
        return case_run
    case_run.conversation_id = conversation_id
    questions = [str(case["query"]), *[str(item) for item in case.get("followups", [])]]
    for question in questions:
        trace = ask_turn(
            base,
            user,
            conversation_id,
            question,
            timeout,
            expected_path=execution_contract,
            preflight_receipt_hash=preflight_receipt_hash,
        )
        case_run.turns.append(trace)
        if trace.status in {"error", "timeout"}:
            break
    case_run.execution_diagnostics.extend(_case_execution_diagnostics(case, case_run))
    return case_run


def _case_execution_diagnostics(
    case: Mapping[str, Any],
    case_run: CaseRun,
) -> list[str]:
    """Check structural guarantees that cannot be inferred by the answer judge.

    C10 is deliberately checked here instead of in the truth evaluator.  A
    truth rule may say whether an answer is consistent, but it cannot prove
    that the runner used one conversation, three distinct messages, and a
    stable PIT cutoff.
    """

    diagnostics: list[str] = []
    turns = case_run.turns
    if case_run.blocked_reason:
        diagnostics.append("conversation_creation_failed")
        return diagnostics
    if not turns:
        diagnostics.append("no_turns_recorded")
        return diagnostics

    # Every turn in a formal run must carry the path and receipt that the
    # execution contract asked for.  The detailed error remains on TurnTrace;
    # this list is the bounded Layer 1 explanation.
    for index, turn in enumerate(turns, 1):
        if turn.error:
            diagnostics.append(f"turn_{index}:{turn.error}")
        if not turn.conversation_id:
            diagnostics.append(f"turn_{index}:conversation_id_missing")
        if not turn.run_id or not turn.assistant_message_id:
            diagnostics.append(f"turn_{index}:stable_id_missing")
        if turn.execution_path != turn.expected_execution_path:
            diagnostics.append(f"turn_{index}:execution_path_mismatch")
        if turn.artifact_receipt_valid is not True:
            diagnostics.append(f"turn_{index}:artifact_receipt_invalid")
        if not turn.attempt_id or not turn.task_frame_hash:
            diagnostics.append(f"turn_{index}:attempt_binding_missing")

    if len(turns) <= 1 and not case.get("check_cross_turn_consistency"):
        return list(dict.fromkeys(diagnostics))

    conversation_ids = {turn.conversation_id for turn in turns}
    if len(conversation_ids) != 1 or None in conversation_ids:
        diagnostics.append("multi_turn_conversation_not_reused")

    run_ids = [turn.run_id for turn in turns]
    if len(run_ids) != len(set(run_ids)) or any(not value for value in run_ids):
        diagnostics.append("multi_turn_run_ids_not_distinct")
    message_ids = [turn.assistant_message_id for turn in turns]
    if len(message_ids) != len(set(message_ids)) or any(
        not value for value in message_ids
    ):
        diagnostics.append("multi_turn_message_ids_not_distinct")

    # The API creates each follow-up with conversation.last_run_id as its
    # parent.  Checking the exact chain catches a runner that accidentally
    # starts independent conversations even when the text happens to agree.
    if turns[0].parent_run_id is not None:
        diagnostics.append("multi_turn_first_parent_must_be_null")
    for previous, current in zip(turns, turns[1:]):
        if current.parent_run_id != previous.run_id:
            diagnostics.append("multi_turn_parent_chain_mismatch")
            break

    cutoffs = [turn.cutoff for turn in turns]
    if any(not cutoff for cutoff in cutoffs) or len(set(cutoffs)) != 1:
        diagnostics.append("multi_turn_cutoff_not_stable")
    expected_date = str(case.get("date") or "").strip()
    if expected_date and any(
        cutoff and not str(cutoff).startswith(expected_date) for cutoff in cutoffs
    ):
        diagnostics.append("multi_turn_cutoff_mismatch")
    return list(dict.fromkeys(diagnostics))


def _execution_summary(
    runs: list[CaseRun],
    execution_contracts: Mapping[str, str],
    *,
    expected: ExpectedRuntime | None,
    preflight_report: PreflightReport,
) -> dict[str, Any]:
    """Produce the non-negotiable Layer 1 receipt independently of Layer 2."""

    turns = [turn for case_run in runs for turn in case_run.turns]
    path_matches = sum(
        1
        for turn in turns
        if turn.execution_path
        and turn.execution_path == turn.expected_execution_path
    )
    episode_turns = [
        turn for turn in turns if turn.execution_path == "continuous_episode"
    ]
    runtime_ids = sorted(
        {str(turn.runtime_instance_id) for turn in turns if turn.runtime_instance_id}
    )
    expected_runtime_id = ""
    observed_runtime = preflight_report.observed.get("runtime")
    if isinstance(observed_runtime, Mapping):
        expected_runtime_id = str(observed_runtime.get("runtime_instance_id") or "")
    runtime_instance_matches = sum(
        1
        for turn in turns
        if expected_runtime_id
        and turn.runtime_instance_id == expected_runtime_id
    )
    c10 = next(
        (case_run for case_run in runs if case_run.case_id == "C10-multi-turn-consistency"),
        None,
    )
    c10_turns = c10.turns if c10 is not None else []
    c10_conversations = sorted(
        {turn.conversation_id for turn in c10_turns if turn.conversation_id}
    )
    c10_run_ids = [turn.run_id for turn in c10_turns]
    c10_message_ids = [turn.assistant_message_id for turn in c10_turns]
    c10_cutoffs = [turn.cutoff for turn in c10_turns]
    c10_summary = {
        "turns": len(c10_turns),
        "conversation_ids": c10_conversations,
        "single_conversation": len(c10_conversations) == 1 and len(c10_turns) == 3,
        "distinct_run_ids": len(c10_run_ids) == len(set(c10_run_ids))
        and all(c10_run_ids),
        "distinct_assistant_message_ids": len(c10_message_ids)
        == len(set(c10_message_ids))
        and all(c10_message_ids),
        "parent_chain_valid": bool(c10_turns)
        and c10_turns[0].parent_run_id is None
        and all(
            current.parent_run_id == previous.run_id
            for previous, current in zip(c10_turns, c10_turns[1:])
        ),
        "cutoff_consistent": bool(c10_turns)
        and all(c10_cutoffs)
        and len(set(c10_cutoffs)) == 1,
    }
    c10_summary["cutoff_matches_case"] = not (
        c10 is not None
        and any(
            "cutoff_mismatch" in diagnostic
            for diagnostic in c10.execution_diagnostics
        )
    )
    c10_summary["structural_valid"] = all(
        bool(c10_summary[key])
        for key in (
            "single_conversation",
            "distinct_run_ids",
            "distinct_assistant_message_ids",
            "parent_chain_valid",
            "cutoff_consistent",
            "cutoff_matches_case",
        )
    ) if c10 is not None else True

    expected_path_by_case = {
        case_run.case_id: execution_contracts.get(case_run.case_id)
        for case_run in runs
    }
    turn_contract_valid = all(
        turn.status == "completed"
        and not turn.error
        and turn.expected_execution_path == expected_path_by_case.get(case_run.case_id)
        and turn.execution_path == turn.expected_execution_path
        and turn.artifact_receipt_valid is True
        and bool(turn.attempt_id)
        and bool(turn.task_frame_hash)
        and bool(turn.runtime_instance_id)
        and (
            not expected_runtime_id
            or turn.runtime_instance_id == expected_runtime_id
        )
        for case_run in runs
        for turn in case_run.turns
    )
    diagnostics = list(
        dict.fromkeys(
            diagnostic
            for case_run in runs
            for diagnostic in case_run.execution_diagnostics
        )
    )
    layer1_eligible = bool(
        expected is not None
        and preflight_report.acceptance_eligible
        and bool(turns)
        and path_matches == len(turns)
        and len(episode_turns)
        == sum(
            1
            for case_run in runs
            for _ in case_run.turns
            if execution_contracts.get(case_run.case_id) == "continuous_episode"
        )
        and sum(
            1 for turn in episode_turns if turn.artifact_receipt_valid is True
        )
        == len(episode_turns)
        and runtime_instance_matches == len(turns)
        and len(runtime_ids) <= 1
        and turn_contract_valid
        and bool(c10_summary["structural_valid"])
        and not diagnostics
    )
    if expected is not None and not preflight_report.acceptance_eligible:
        diagnostics.insert(0, "preflight_ineligible")
    return {
        "total_turns": len(turns),
        "path_matches": path_matches,
        "continuous_episode_turns": len(episode_turns),
        "valid_episode_receipts": sum(
            1 for turn in episode_turns if turn.artifact_receipt_valid is True
        ),
        "runtime_instance_ids": runtime_ids,
        "runtime_instance_drift": len(runtime_ids) > 1,
        "runtime_instance_matches": runtime_instance_matches,
        "c10": c10_summary,
        "layer1_eligible": layer1_eligible,
        "diagnostics": diagnostics,
    }


_SYNTHESIS_DIAGNOSTIC_FIELDS = (
    "state",
    "reason_code",
    "detail",
    "prepared_message_count",
    "candidate_claim_count",
    "bound_claim_count",
)
_SYNTHESIS_DIAGNOSTIC_STATES = {
    "not_requested",
    "not_prepared",
    "attempted",
    "accepted",
    "rejected",
    "failed",
}


def _capture_synthesis_diagnostic(steps: list[Any]) -> dict[str, Any]:
    """Retain only the bounded diagnostic already exposed by the public trace."""

    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        raw = step.get("diagnostic")
        if not isinstance(raw, dict):
            continue
        state = raw.get("state")
        reason_code = raw.get("reason_code")
        if state not in _SYNTHESIS_DIAGNOSTIC_STATES or not isinstance(
            reason_code, str
        ):
            continue
        diagnostic = {
            key: raw[key]
            for key in _SYNTHESIS_DIAGNOSTIC_FIELDS
            if key in raw
        }
        diagnostic["detail"] = str(diagnostic.get("detail") or "")[:200]
        return diagnostic
    return {}


def ask_once(base: str, user: str, question: str, timeout: float) -> TurnTrace:
    """Compatibility wrapper: one new conversation and one exact turn."""
    try:
        conversation_id = create_conversation(base, user, "acceptance")
        return ask_turn(
            base,
            user,
            conversation_id,
            question,
            timeout,
        )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        trace = TurnTrace(question=question)
        trace.status = "error"
        trace.error = str(exc)
        return trace


def cmd_run(args: argparse.Namespace) -> int:
    requested_output = getattr(args, "output", None)
    output_path = Path(requested_output) if requested_output else None
    if output_path is not None and output_path.exists():
        print(f"❌ 输出已存在，拒绝覆盖：{_rel(output_path)}")
        return 2

    doc = load_cases()
    try:
        expected = _expected_runtime_from_args(args)
    except ValueError as exc:
        print(f"❌ expected runtime 参数无效：{exc}")
        return 2
    raw_report = preflight(args.base, expected) if expected is not None else preflight(args.base)
    if isinstance(raw_report, PreflightReport):
        preflight_report = raw_report
        ok, detail = tuple(raw_report)
    else:
        # Compatibility for older tests/tools that monkeypatch the old tuple API.
        ok, detail = raw_report
        preflight_report = PreflightReport(
            acceptance_eligible=False,
            failures=(() if ok else (str(detail),)),
            expected={},
            observed={},
            receipt_hash=_canonical_receipt_hash({"detail": detail}),
        )
    if not ok and not args.force:
        print(f"❌ 前置检查未通过：{detail}")
        print("   这是部署接缝问题，不是题目失败。修好再跑，或 --force 强跑留证据。")
        return 2
    print(f"✅ 前置检查：{detail}" if ok else f"⚠️  强跑（前置未过）：{detail}")

    try:
        execution_contracts = load_execution_contracts()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if expected is not None:
            print(f"❌ execution contract 无效：{exc}")
            return 2
        execution_contracts = {
            str(case["id"]): "legacy_direct" for case in doc["cases"]
        }
    selected = [
        c
        for c in doc["cases"]
        if (not args.tier or c["tier"] == args.tier)
        and (not args.case or c["id"] in args.case)
    ]
    print(f"选中 {len(selected)} / {len(doc['cases'])} 道题\n")
    runs: list[CaseRun] = []
    for i, case in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {case['id']} … ", end="", flush=True)
        execution_contract = execution_contracts[case["id"]]
        if expected is not None:
            # Formal acceptance always goes through the exact-ID, one-
            # conversation-per-case runner.  This is the path whose
            # provenance is eligible for the Continuous Harness board.
            cr = run_case(
                args.base,
                args.user,
                case,
                timeout=args.timeout,
                preflight_receipt_hash=preflight_report.receipt_hash,
                execution_contract=execution_contract,
            )
        else:
            # Keep the historical diagnostic CLI compatible.  It is
            # intentionally non-formal because no strict runtime identity was
            # supplied, and therefore can never unlock the Continuous board.
            cr = CaseRun(case_id=case["id"], tier=case["tier"])
            questions = [case["query"], *case.get("followups", [])]
            for q in questions:
                t = ask_once(args.base, args.user, q, args.timeout)
                cr.turns.append(t)
                if t.status in {"error", "timeout"}:
                    break
            cr.execution_diagnostics.extend(_case_execution_diagnostics(case, cr))
        head = cr.turns[0] if cr.turns else None
        degraded = " ⚠降级" if head and head.degrades else ""
        print(
            f"{head.status if head else 'n/a'}  {head.elapsed_s if head else 0}s  "
            f"证据={head.evidence_bound if head else 0}{degraded}"
        )
        runs.append(cr)

    execution_summary = _execution_summary(
        runs,
        execution_contracts,
        expected=expected,
        preflight_report=preflight_report,
    )
    formal_acceptance_eligible = bool(
        preflight_report.acceptance_eligible
        and execution_summary["layer1_eligible"]
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = output_path or RUNS_DIR / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": stamp,
        "base": args.base,
        "preflight_ok": ok,
        "preflight_detail": detail,
        "acceptance_eligible": formal_acceptance_eligible,
        "preflight_acceptance_eligible": preflight_report.acceptance_eligible,
        "preflight": asdict(preflight_report),
        "execution_summary": execution_summary,
        "execution_contracts": {
            case_id: execution_contracts[case_id]
            for case_id in (case["id"] for case in selected)
        },
        "cases": [asdict(r) for r in runs],
    }
    try:
        with out.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except FileExistsError:
        print(f"❌ 输出已存在，拒绝覆盖：{_rel(out)}")
        return 2
    print(f"\ntrace 已落盘：{_rel(out)}")
    print("看板：python3 -m intelligence.eval.acceptance board")
    return 0


def _expected_runtime_from_args(
    args: argparse.Namespace,
) -> ExpectedRuntime | None:
    values = {
        "revision": getattr(args, "expected_revision", None),
        "code_root": getattr(args, "expected_code_root", None),
        "mode": getattr(args, "expected_mode", None),
        "backend": getattr(args, "expected_backend", None),
        "model": getattr(args, "expected_model", None),
        "provider_label": getattr(args, "expected_provider_label", None),
        "provider_protocol": getattr(args, "expected_provider_protocol", None),
    }
    if not any(values.values()):
        return None
    if not all(values.values()):
        raise ValueError("formal preflight requires all expected runtime fields")
    revision = str(values["revision"]).strip()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("expected_revision must be a 40-character git sha")
    code_root = str(Path(str(values["code_root"])).expanduser().resolve())
    return ExpectedRuntime(
        mode=str(values["mode"]),
        backend=str(values["backend"]),
        model=str(values["model"]),
        revision=revision,
        code_root=code_root,
        provider_label=str(values["provider_label"]),
        provider_protocol=str(values["provider_protocol"]),
    )


# --------------------------------------------------------------------------- #
# board —— 进度只从这里生成
# --------------------------------------------------------------------------- #
def latest_run() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    runs = sorted(RUNS_DIR.glob("*.json"))
    return runs[-1] if runs else None


def cmd_board(args: argparse.Namespace) -> int:
    doc = load_cases()
    cases = doc["cases"]
    case_tiers = {case["id"]: case["tier"] for case in cases}
    explicit_run = getattr(args, "run", None)
    if not explicit_run and (
        getattr(args, "truth_observations", None)
        or getattr(args, "experience_labels", None)
        or getattr(args, "information_comparisons", None)
    ):
        print(
            "❌ observation sidecar 只绑定单个 run；"
            "请同时提供 board --run PATH"
        )
        return 2
    run_path = Path(explicit_run) if explicit_run else None
    try:
        if run_path is not None:
            record = load_validated_run(run_path, case_tiers)
            if (
                "acceptance_eligible" in record
                and record.get("acceptance_eligible") is not True
            ):
                print(
                    f"❌ 指定运行 {run_path.stem} acceptance_eligible=false，"
                    "不能进入正式看板计数"
                )
                return 2
            execution_summary = record.get("execution_summary")
            if (
                isinstance(execution_summary, Mapping)
                and "layer1_eligible" in execution_summary
                and execution_summary.get("layer1_eligible") is not True
            ):
                print(
                    f"❌ 指定运行 {run_path.stem} Layer 1 execution_summary 不合格，"
                    "不能进入正式 Continuous 看板计数"
                )
                return 2
            by_id = {case["case_id"]: case for case in record["cases"]}
            source_by_id = {case_id: run_path for case_id in by_id}
            header_note = (
                f"指定真实运行 {run_path.stem}"
                f"（前置检查{'通过' if record.get('preflight_ok') else '未过'}）"
            )
        else:
            selected = select_latest_case_runs(RUNS_DIR, case_tiers)
            by_id = {
                case_id: item.case_run for case_id, item in selected.items()
            }
            source_by_id = {
                case_id: item.source_path for case_id, item in selected.items()
            }
            contributing = sorted({path.stem for path in source_by_id.values()})
            header_note = "尚无真实运行记录"
            if contributing:
                header_note = (
                    f"汇总 {len(contributing)} 份真实运行"
                    f"（来源：{'、'.join(contributing)}）"
                )
    except RunArtifactError as exc:
        print(f"❌ run artifact 无效：{exc}")
        return 2

    try:
        observations_by_case = _load_board_observations(args, run_path)
    except ObservationArtifactError as exc:
        print(f"❌ observation sidecar 无效：{exc}")
        return 2

    information_by_case: dict[str, Mapping[str, Any]] = {}
    information_path = getattr(args, "information_comparisons", None)
    if information_path:
        assert run_path is not None
        try:
            comparison_queue = build_comparison_queue(run_path, agent="knevo")
            comparison_artifact = load_comparison_result(
                Path(information_path),
                queue=comparison_queue,
            )
            information_by_case = {
                case_id: dict(observation)
                for case_id, observation in comparison_artifact.case_observations.items()
            }
        except ComparisonArtifactError as exc:
            print(f"❌ information comparison 无效：{exc}")
            return 2

    overlay = load_verdict_overlay()
    print(f"# 验收看板 · {header_note}\n")
    print(
        "| 题 | 组 | 来源 | 运行 | 真值 | 体验 | 送达 | 信息量 | 可信度 | "
        "耗时 | 绑定证据 | 说明 |"
    )
    print("|---|---|---|---|---|---|---|---|---|---:|---:|---|")
    operational_tally = {state: 0 for state in OperationalState}
    truth_tally = {state: 0 for state in VerdictState}
    experience_tally = {state: 0 for state in ExperienceState}
    delivery_tally = {state: 0 for state in AxisState}
    information_tally = {state: 0 for state in AxisState}
    credibility_tally = {state: 0 for state in AxisState}
    # 红的稳定性按 rule.kind 差一个数量级：A 组同输入复跑实测，事实层 0% 翻转、
    # 措辞层 33%。合成一个「失败 N」会把两者压成一个数，看板就读不出
    # 「这一刀有没有用」。分层计数，不改表格结构。
    failing_kinds: dict[str, int] = {}
    operational_labels = {
        OperationalState.NOT_RUN: "⬜ 未跑",
        OperationalState.BLOCKED: "⚫ 阻塞",
        OperationalState.FAILED: "🔴 未产出",
        OperationalState.DEGRADED: "🟠 降级完成",
        OperationalState.COMPLETED: "🟢 完成",
    }
    truth_labels = {
        VerdictState.NOT_RUN: "—",
        VerdictState.PASS: "✅ 通过",
        VerdictState.FAIL: "❌ 失败",
        VerdictState.UNJUDGEABLE: "❔ 不可判",
    }
    experience_labels = {
        ExperienceState.UNLABELED: "未标注",
        ExperienceState.LABELED: "已盲标",
        ExperienceState.INELIGIBLE: "不适用",
    }
    axis_labels = {
        AxisState.PASS: "✅ 通过",
        AxisState.PARTIAL: "🟠 部分",
        AxisState.FAIL: "❌ 失败",
        AxisState.UNJUDGEABLE: "❔ 不可判",
        AxisState.NOT_EVALUATED: "— 未评",
        AxisState.NOT_RUN: "—",
    }
    information_comparison_labels = {
        InformationComparison.WORKBENCH_WINS: "✅ 工作台优",
        InformationComparison.TIE: "➖ 持平",
        InformationComparison.KNEVO_WINS: "❌ Knevo优",
    }
    for c in cases:
        r = by_id.get(c["id"])
        contract = compile_case_contract(c, overlay[c["id"]])
        case_observations = observations_by_case.get(c["id"]) or {}
        verdict = evaluate_case(
            contract,
            r,
            observations=case_observations,
        )
        axes = project_axes(
            verdict,
            information=information_by_case.get(c["id"]),
        )
        operational_tally[verdict.operational.state] += 1
        truth_tally[verdict.truth.state] += 1
        experience_tally[verdict.experience.state] += 1
        delivery_tally[axes.delivery.state] += 1
        information_tally[axes.information.state] += 1
        credibility_tally[axes.credibility.state] += 1
        t0 = (r.get("turns") or [None])[0] if r else None
        detail = ""
        if verdict.truth.state is VerdictState.FAIL:
            failures = [
                rule.reason
                for rule in verdict.truth.rules
                if rule.state is VerdictState.FAIL
            ]
            detail = failures[0] if failures else "deterministic truth rule failed"
            for rule in verdict.truth.rules:
                if rule.state is VerdictState.FAIL:
                    failing_kinds[rule.kind] = failing_kinds.get(rule.kind, 0) + 1
        elif verdict.truth.state is VerdictState.UNJUDGEABLE:
            pending = [
                rule.reason
                for rule in verdict.truth.rules
                if rule.state is VerdictState.UNJUDGEABLE
            ]
            detail = pending[0] if pending else verdict.operational.reason
        elif verdict.operational.state in {
            OperationalState.BLOCKED,
            OperationalState.FAILED,
        }:
            detail = verdict.operational.reason
        if verdict.operational.state is OperationalState.DEGRADED:
            diagnostic = (
                t0.get("synthesis_diagnostic")
                if isinstance(t0, Mapping)
                else None
            )
            reason_code = (
                str(diagnostic.get("reason_code") or "")
                if isinstance(diagnostic, Mapping)
                else ""
            )
            diagnostic_note = (
                f"synthesis reason_code={reason_code}"
                if reason_code
                else "synthesis diagnostic unavailable"
            )
            detail = (
                f"{detail}；{diagnostic_note}"
                if detail
                else f"{verdict.operational.reason}；{diagnostic_note}"
            )
        print(
            f"| {c['id']} | {c['tier']} | "
            f"{source_by_id[c['id']].stem[-7:] if c['id'] in source_by_id else '—'} | "
            f"{operational_labels[verdict.operational.state]} | "
            f"{truth_labels[verdict.truth.state]} | "
            f"{experience_labels[verdict.experience.state]}"
            f"{f'({verdict.experience.label})' if verdict.experience.label else ''} | "
            f"{axis_labels[axes.delivery.state]} | "
            f"{information_comparison_labels.get(axes.information.comparison, axis_labels[axes.information.state])} | "
            f"{axis_labels[axes.credibility.state]} | "
            f"{(t0 or {}).get('elapsed_s', '—')}"
            f"{'s' if t0 else ''} | {(t0 or {}).get('evidence_bound') or 0 if t0 else '—'} | "
            f"{detail} |"
        )

    total = len(cases)
    completed_count = (
        operational_tally[OperationalState.COMPLETED]
        + operational_tally[OperationalState.DEGRADED]
    )
    print(
        f"\n**运行口径**：{total} 道题里，未跑 "
        f"{operational_tally[OperationalState.NOT_RUN]}、阻塞 "
        f"{operational_tally[OperationalState.BLOCKED]}、未产出 "
        f"{operational_tally[OperationalState.FAILED]}、降级完成 "
        f"{operational_tally[OperationalState.DEGRADED]}、正常完成 "
        f"{operational_tally[OperationalState.COMPLETED]}（完成合计 {completed_count}）。"
    )
    judged = truth_tally[VerdictState.PASS] + truth_tally[VerdictState.FAIL]
    rate_note = (
        f"可判子集通过率 {truth_tally[VerdictState.PASS]}/{judged}"
        if judged
        else "尚无可判子集通过率"
    )
    print(
        f"**真值口径**：通过 {truth_tally[VerdictState.PASS]}、失败 "
        f"{truth_tally[VerdictState.FAIL]}、不可判 "
        f"{truth_tally[VerdictState.UNJUDGEABLE]}、未跑 "
        f"{truth_tally[VerdictState.NOT_RUN]}；{rate_note}（不是 28 题产品通过率）。"
    )
    print(
        "**三轴口径**：送达通过/部分/失败 "
        f"{delivery_tally[AxisState.PASS]}/{delivery_tally[AxisState.PARTIAL]}/"
        f"{delivery_tally[AxisState.FAIL]}；信息量已评/未评 "
        f"{total - information_tally[AxisState.NOT_EVALUATED] - information_tally[AxisState.NOT_RUN]}/"
        f"{information_tally[AxisState.NOT_EVALUATED]}；可信通过/失败/不可判 "
        f"{credibility_tally[AxisState.PASS]}/{credibility_tally[AxisState.FAIL]}/"
        f"{credibility_tally[AxisState.UNJUDGEABLE]}。"
    )
    if failing_kinds:
        breakdown = "、".join(
            f"{kind} {count}"
            for kind, count in sorted(failing_kinds.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        print(
            f"**失败按判据层**：{breakdown}。"
            "（同输入复跑实测：fact 层 0% 翻转，product_language 层 33%——"
            "措辞层的红不要单次比较）"
        )
    print(
        f"**体验口径**：已盲标 {experience_tally[ExperienceState.LABELED]}、"
        f"未标注 {experience_tally[ExperienceState.UNLABELED]}、"
        f"不适用 {experience_tally[ExperienceState.INELIGIBLE]}。"
    )
    snaps = list(SNAPSHOT_DIR.glob("*.json")) if SNAPSHOT_DIR.exists() else []
    print(f"**参照快照**：已冻结 {len(snaps)} / {total} 道（codex/knevo）")
    return 0


def _load_board_observations(
    args: argparse.Namespace, run_path: Path | None
) -> dict[str, dict[str, Any]]:
    requested = (
        (
            getattr(args, "truth_observations", None),
            "acceptance_truth_observations",
        ),
        (
            getattr(args, "experience_labels", None),
            "acceptance_experience_labels",
        ),
    )
    if not any(path for path, _kind in requested):
        if getattr(args, "blind_manifest", None):
            raise ObservationArtifactError(
                "blind manifest requires --experience-labels"
            )
        return {}
    if run_path is None:
        raise ObservationArtifactError("没有 run，不能加载 observation sidecar")

    merged: dict[str, dict[str, Any]] = {}
    for raw_path, expected_kind in requested:
        if not raw_path:
            continue
        artifact = load_observation_artifact(
            Path(raw_path),
            run_path=run_path,
            cases_path=CASES_PATH,
            overlay_path=VERDICT_OVERLAY_PATH,
            reference_eligibility_path=REFERENCE_ELIGIBILITY_PATH,
            blind_manifest_path=(
                Path(getattr(args, "blind_manifest"))
                if expected_kind == "acceptance_experience_labels"
                and getattr(args, "blind_manifest", None)
                else None
            ),
        )
        if artifact.kind != expected_kind:
            raise ObservationArtifactError(
                f"{raw_path} kind={artifact.kind}, expected={expected_kind}"
            )
        for case_id in artifact.case_observations:
            projection = artifact.for_case(case_id)
            target = merged.setdefault(case_id, {})
            duplicate = set(target) & set(projection)
            if duplicate:
                raise ObservationArtifactError(
                    f"duplicate observation axes for {case_id}: {sorted(duplicate)}"
                )
            target.update(projection)
    return merged


def classify_failure(turn: dict[str, Any]) -> str:
    """把失败分成『部署接缝』和『业务质量』—— 前者不该算题目分数。"""
    err = (turn.get("error") or "").lower()
    status = turn.get("status")
    if status == "timeout":
        return "接缝:超时"
    if "urlopen" in err or "refused" in err or "conversation_id" in err:
        return "接缝:服务/路由"
    if "api_key" in err or "missing" in err or "credential" in err:
        return "接缝:凭据"
    if "schema" in err or "400" in err or "invalid" in err:
        return "接缝:协议/Schema"
    if status == "error":
        return "接缝:未分类"
    if turn.get("degrades") and not (turn.get("evidence_bound") or 0):
        # 服务健康、模型答了，但一条证据都没绑上就降级 —— 这是检索/绑定的业务
        # 缺陷（可能是假拒答），不是部署接缝，别混进接缝账里当"环境没配好"。
        return "业务质量:零证据降级"
    return "业务质量"


def cmd_comparison_pack(args: argparse.Namespace) -> int:
    try:
        queue = build_comparison_queue(Path(args.run), agent=args.agent)
        write_comparison_queue(queue, Path(args.output))
    except ComparisonArtifactError as exc:
        print(f"❌ comparison pack 失败：{exc}")
        return 2
    eligible = sum(entry.status == "eligible" for entry in queue.entries.values())
    missing = sum(entry.status == "missing" for entry in queue.entries.values())
    ineligible = len(queue.entries) - eligible - missing
    print(
        f"✅ comparison pack 已写入 {_rel(Path(args.output))}："
        f"eligible={eligible}, missing={missing}, ineligible={ineligible}"
    )
    return 0


def cmd_validate_comparison(args: argparse.Namespace) -> int:
    try:
        queue = load_comparison_queue(Path(args.queue))
        artifact = load_comparison_result(Path(args.result), queue=queue)
    except ComparisonArtifactError as exc:
        print(f"❌ information comparison 无效：{exc}")
        return 2
    print(
        f"✅ information comparison 有效：{len(artifact.case_observations)} cases，"
        f"evaluator={artifact.evaluator_id}/{artifact.evaluator_model}"
    )
    return 0


# --------------------------------------------------------------------------- #
# freeze —— 参照快照必须外部冻结
# --------------------------------------------------------------------------- #
def cmd_freeze(args: argparse.Namespace) -> int:
    """冻结外部参照答案。

    ``via`` 必填：参照答案的价值全在来源可追溯。codex 走
    ``codex exec -m gpt-5.5``（与 dual_blind_flows.sh 同一条路）；knevo 有两条路 ——
    ``manual_paste``（人工转贴，有转写损耗、可能丢工具轨迹）与 ``cdp_readback``
    （CDP 驱动用户自己已登录的 Chrome，读 /api/conversations/{id} 的 transcript）。
    后者保真度更高且带工具调用轨迹，但**必须记住答案仍是用户账号里人工提问产生的**，
    不是我们自动跑的。半年后回看快照，必须能分清"这是机器跑的"还是"这是人问的"、
    以及问的是哪一天 —— 否则基准不可复核。

    ``answer_sha256`` 是防篡改锚：冻结后任何改动都会让哈希对不上。
    ``--meta-file`` 收 JSON，落到 ``source_meta``：cdp_readback 用它存会话 id、
    原始提问、工具调用轨迹 —— 工具轨迹能和题目的 expect_tools 直接对照，
    是"它怎么答出来的"而不只是"它答了什么"。
    """
    doc = load_cases()
    ids = {c["id"] for c in doc["cases"]}
    if args.case_id not in ids:
        print(f"❌ 未知题号 {args.case_id}。可用：{sorted(ids)}")
        return 2
    if args.agent not in doc["reference_agents"]:
        print(f"❌ agent 必须是 {doc['reference_agents']} 之一")
        return 2
    if args.answer_file == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.answer_file).read_text(encoding="utf-8")
    if not text.strip():
        print("❌ 答案为空，拒绝冻结")
        return 2
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOT_DIR / f"{args.case_id}.{args.agent}.json"
    if out.exists() and not args.overwrite:
        print(
            f"❌ {out.name} 已存在。参照快照一旦冻结不应重生成；确需覆盖加 --overwrite"
        )
        return 2
    meta = None
    if getattr(args, "meta_file", None):
        meta = json.loads(Path(args.meta_file).read_text(encoding="utf-8"))
    out.write_text(
        json.dumps(
            {
                "case_id": args.case_id,
                "agent": args.agent,
                "frozen_at": datetime.now(timezone.utc).isoformat(),
                "via": args.via,
                "asked_at": args.asked_at,
                "answer_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "source_meta": meta,
                "answer": text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✅ 已冻结 {_rel(out)}（{len(text)} 字，via={args.via}）")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="acceptance", description="28 道验收题台账")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("board", help="打印看板（进度唯一来源）")
    b.add_argument("--run", help="只读取指定 run artifact（sidecar 必须显式绑定）")
    b.add_argument("--truth-observations", help="显式绑定的 truth observation sidecar")
    b.add_argument("--experience-labels", help="显式绑定的 blind experience sidecar")
    b.add_argument(
        "--information-comparisons",
        help="显式绑定的 information comparison sidecar",
    )
    b.add_argument("--blind-manifest", help="experience sidecar 对应的密封盲评身份清单")
    b.set_defaults(func=cmd_board)

    r = sub.add_parser("run", help="走真实路径跑题并落 trace")
    r.add_argument("--base", default=DEFAULT_BASE)
    r.add_argument("--user", default=DEFAULT_USER)
    r.add_argument("--tier", choices=["high_freq", "mid_freq", "long_tail"])
    r.add_argument("--case", action="append", help="只跑指定题号，可重复")
    r.add_argument("--timeout", type=float, default=300.0)
    r.add_argument("--force", action="store_true", help="前置检查未过也强跑")
    r.add_argument("--output", help="trace 精确输出路径（拒绝覆盖已有文件）")
    r.add_argument("--expected-revision")
    r.add_argument("--expected-code-root")
    r.add_argument("--expected-mode")
    r.add_argument("--expected-backend")
    r.add_argument("--expected-model")
    r.add_argument("--expected-provider-label")
    r.add_argument(
        "--expected-provider-protocol",
    )
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("freeze", help="冻结 codex/knevo 参照答案")
    f.add_argument("case_id")
    f.add_argument("agent")
    f.add_argument("answer_file", help="答案文件路径；写 - 表示从 stdin 读")
    f.add_argument(
        "--via",
        required=True,
        choices=["manual_paste", "cdp_readback", "codex_exec", "cli"],
        help=(
            "来源：manual_paste=人工转贴；cdp_readback=CDP 读用户已登录 Chrome 的"
            "会话 transcript（保真、带工具轨迹，仍是人工提问）；codex_exec=codex exec 自动跑"
        ),
    )
    f.add_argument("--asked-at", help="实际提问日期 YYYY-MM-DD（与题目锚定日可能不同）")
    f.add_argument("--meta-file", help="JSON 文件，落到 source_meta（会话 id / 原始提问 / 工具轨迹）")
    f.add_argument("--overwrite", action="store_true")
    f.set_defaults(func=cmd_freeze)

    cp = sub.add_parser("comparison-pack", help="生成冻结 Workbench/Knevo 对比包")
    cp.add_argument("--run", required=True)
    cp.add_argument("--agent", default="knevo", choices=["knevo"])
    cp.add_argument("--output", required=True)
    cp.set_defaults(func=cmd_comparison_pack)

    vc = sub.add_parser("validate-comparison", help="校验 information comparison")
    vc.add_argument("result")
    vc.add_argument("--queue", required=True)
    vc.set_defaults(func=cmd_validate_comparison)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
