"""Scripted dsh Adapter：先验证窄协议，不连接真实 dsh。

来源：``docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md``
§8.1–§8.3、§11 第 7 步；台账把网关传 EpisodeScope 认领给这一步。

--------------------------------------------------------------------------
这一步是什么 / 不是什么
--------------------------------------------------------------------------

dsh 的 TypeScript Agent 要通过窄协议打 Python Domain Gateway。第 7 步的
**先**半段是用一个脚本化 stub 把协议跑通：task frame / episode scope /
tool definitions / tool call / tool result / durable event / final outcome。

Stub **走现有** ``HeadlessToolGateway`` 的 JSON/HTTP 面（spec §8.2：对照
实验先用本地 HTTP，不引入新外部服务）。它不是第二套工具执行器。

本模块**不**做的事：

- 不 import dsh SDK，不复制 dsh 源码，不拉起 Node；sparse checkout 只经
  ``DSH_SOURCE_INDEX`` 做 pin + cone 探测，路径不写进源码、不写进收据；
- 不把 ``dsh_stub`` 加进 ``RUNTIME_BACKEND_NAMES``——factory 一旦认这个名字
  却没有独立 readiness，会掉进 headless 的回落分支；
- 不跑 live A/B，不把 ``DSH_AB_RELAY_KEY`` 注入当前进程。
  ``form_step8_decision`` 只是默认立场的函数，不是第 8 步对照收据。

--------------------------------------------------------------------------
禁止的双写（spec §8.3）
--------------------------------------------------------------------------

- 工具调用的 ``tool_call_id`` 就是网关的 ``request_id``，stub 不另造一号；
- 模型可见结果用 ``public_agent_evidence``，不把 ``internal_locator`` /
  DuckDB 路径 / 凭证送过桥；
- Durable 事件来自网关 snapshot + 一条 ``task`` 锚点，不另开 Session 账本。
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
import subprocess
from typing import Literal

from intelligence.runtime.headless_tool_gateway import (
    HeadlessGatewaySnapshot,
    HeadlessToolGateway,
)
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
    public_agent_evidence,
)
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.episode_session import CallbackEpisodeSession, EpisodeSession
from intelligence.services.repair_coordinator import RepairGoal
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.runtime_handle import RuntimeHandle
from intelligence.services.task_frame import TaskFrame


ADAPTER_PROTOCOL_KEYS: tuple[str, ...] = (
    "task_frame",
    "episode_scope",
    "tool_definitions",
    "tool_calls",
    "tool_results",
    "durable_events",
    "final_outcome",
)

DSH_SOURCE_INDEX_ENV = "DSH_SOURCE_INDEX"
DSH_AB_RELAY_KEY_ENV = "DSH_AB_RELAY_KEY"
PINNED_DSH_COMMIT = "47f943859bef60e4160492346772ded9b24f765a"
# Step 1 收据要求 cone 含 packages/llm；缺它就会退回 git show 读 README。
# 只记相对路径，收据里不得出现家目录。
DSH_CONE_MARKERS: tuple[str, ...] = (
    "packages/llm/llm-pi-ai/README.md",
    "packages/bundle/base/cordis.patch.yml",
)

_PRIVATE_MARKERS: tuple[str, ...] = (
    "internal_locator",
    "duckdb",
    "/Users/",
    "OPENAI_API_KEY",
    "DSH_AB_RELAY_KEY",
)


class DshAdapterProtocolError(ValueError):
    """窄协议收据不完整，或把私有路径/凭证送过了桥。"""


@dataclass(frozen=True)
class ScriptedDshAction:
    """dsh 侧的一条脚本动作。这是测试输入，不是第二份事件账本。"""

    kind: Literal["tool_call", "finish"]
    tool: str = ""
    query: str = ""
    draft: str = ""

    def __post_init__(self) -> None:
        if self.kind == "tool_call":
            if not self.tool.strip() or not self.query.strip():
                raise ValueError("scripted tool_call 必须带 tool 和 query")
        elif self.kind == "finish":
            if not self.draft.strip():
                raise ValueError("scripted finish 必须带非空 draft")
        else:
            raise ValueError(f"unsupported scripted dsh action: {self.kind}")


def _scan_private_leak(payload: object, *, path: str) -> None:
    if payload is None or isinstance(payload, (bool, int, float)):
        return
    if isinstance(payload, str):
        lowered = payload.lower()
        for marker in _PRIVATE_MARKERS:
            if marker.lower() in lowered:
                raise DshAdapterProtocolError(
                    f"adapter protocol leaked {marker!r} at {path}"
                )
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not isinstance(key, str):
                raise DshAdapterProtocolError(f"{path} must use string keys")
            key_path = f"{path}.{key}"
            if key in _PRIVATE_MARKERS:
                raise DshAdapterProtocolError(
                    f"adapter protocol leaked {key!r} at {key_path}"
                )
            _scan_private_leak(value, path=key_path)
        return
    if isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            _scan_private_leak(item, path=f"{path}[{index}]")
        return
    raise DshAdapterProtocolError(f"{path} must be JSON-safe")


def dump_adapter_protocol(
    *,
    task_frame: TaskFrame,
    scope: EpisodeScope,
    snapshot: HeadlessGatewaySnapshot,
    outcome: AgentOutcome,
) -> dict[str, object]:
    """spec §8.2 那份窄协议收据。只投影已有对象，不另造事实。"""

    calls: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    for event in snapshot.events:
        payload = dict(event.payload)
        request_id = str(payload.get("request_id") or "")
        if event.kind == "tool_request":
            calls.append(
                {
                    "tool_call_id": request_id,
                    "tool": payload.get("tool"),
                    "query": payload.get("query"),
                }
            )
        elif event.kind in {"tool_result", "tool_error"}:
            results.append(
                {
                    "tool_call_id": request_id,
                    "kind": event.kind,
                    "tool": payload.get("tool"),
                    "status": payload.get("status") or payload.get("error"),
                }
            )
    receipt: dict[str, object] = {
        "task_frame": {
            "task_frame_hash": task_frame.task_frame_hash,
            "question": task_frame.raw_question,
        },
        "episode_scope": scope.dump(),
        "tool_definitions": scope.model_visible_definitions(),
        "tool_calls": calls,
        "tool_results": results,
        "durable_events": [event.to_dict() for event in outcome.events],
        "final_outcome": {
            "status": outcome.status,
            "draft": outcome.draft,
            "stop_reason": outcome.stop_reason,
            "evidence": [public_agent_evidence(item) for item in outcome.evidence],
        },
    }
    missing = [key for key in ADAPTER_PROTOCOL_KEYS if key not in receipt]
    if missing:
        raise DshAdapterProtocolError(f"adapter protocol missing keys: {missing}")
    _scan_private_leak(receipt, path="adapter_protocol")
    return receipt


class DshStubRuntime:
    """ResumableAgentRuntime 的脚本化 Arm B。只验证协议，不调模型。"""

    def __init__(
        self,
        script: Sequence[ScriptedDshAction],
        *,
        is_cancelled: Callable[[], bool] | None = None,
        user_id: str = "",
    ) -> None:
        actions = tuple(script)
        if not actions:
            raise ValueError("dsh stub script must contain at least one action")
        if actions[-1].kind != "finish":
            raise ValueError("dsh stub script must end with finish")
        if any(action.kind == "finish" for action in actions[:-1]):
            raise ValueError("dsh stub script may finish only once, at the end")
        self._script = actions
        self._upstream_cancelled = is_cancelled
        self._user_id = str(user_id or "")
        self._last_protocol: dict[str, object] | None = None

    @property
    def last_protocol(self) -> dict[str, object]:
        if self._last_protocol is None:
            raise RuntimeError("dsh stub has not produced a protocol receipt")
        return self._last_protocol

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome:
        session = self.start(
            task_frame,
            context=context,
            registry=registry,
        )
        try:
            return session.outcome
        finally:
            session.close()

    def start(
        self,
        task_frame: TaskFrame,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> EpisodeSession:
        handle = RuntimeHandle(
            episode_id=context.contract.task_id,
            task_frame_hash=(
                context.contract.task_frame_hash or task_frame.task_frame_hash
            ),
            upstream_cancelled=self._upstream_cancelled,
        )
        handle.mark_started()
        handle.begin_work("initial_run", allow_during_cancel=True)
        try:
            scope = EpisodeScope(
                episode_id=context.contract.task_id,
                user_id=self._user_id,
                context=context,
                registry=registry,
            )
            handle.attach_scope(scope)
            outcome = self._play(task_frame, context, registry, scope)
        finally:
            handle.end_work("initial_run")
        handle.mark_running()
        return CallbackEpisodeSession(
            episode_id=context.contract.task_id,
            outcome=outcome,
            resume_callback=self._resume,
            runtime_handle=handle,
        )

    def _play(
        self,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        scope: EpisodeScope,
    ) -> AgentOutcome:
        if self._upstream_cancelled is not None and self._upstream_cancelled():
            task_hash = context.contract.task_frame_hash or task_frame.task_frame_hash
            outcome = AgentOutcome(
                task_frame_hash=task_hash,
                status="failed",
                draft="",
                evidence=(),
                traces=(),
                gaps=("scripted dsh stub cancelled before dispatch",),
                stop_reason="cancelled",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {
                            "task_frame_hash": task_hash,
                            "question": task_frame.raw_question,
                        },
                    ),
                    EpisodeEvent(2, "finish", {"status": "failed", "reason": "cancelled"}),
                ),
                bindings=(),
                usage=AgentUsage(),
            )
            empty = HeadlessGatewaySnapshot(
                evidence=(),
                traces=(),
                events=(),
                gaps=outcome.gaps,
                executed_count=0,
                duplicate_queries=0,
            )
            self._last_protocol = dump_adapter_protocol(
                task_frame=task_frame,
                scope=scope,
                snapshot=empty,
                outcome=outcome,
            )
            return outcome
        draft = ""
        with HeadlessToolGateway(
            registry=registry,
            context=context,
            is_cancelled=self._upstream_cancelled,
            scope=scope,
        ) as gateway:
            for action in self._script:
                if action.kind == "tool_call":
                    gateway.call(action.tool, action.query)
                else:
                    draft = action.draft
            snapshot = gateway.snapshot()
        outcome = _outcome_from_snapshot(
            task_frame=task_frame,
            context=context,
            snapshot=snapshot,
            draft=draft,
        )
        self._last_protocol = dump_adapter_protocol(
            task_frame=task_frame,
            scope=scope,
            snapshot=snapshot,
            outcome=outcome,
        )
        return outcome

    def _resume(
        self,
        previous: AgentOutcome,
        goal: RepairGoal,
    ) -> AgentOutcome:
        next_sequence = previous.events[-1].sequence + 1
        extra = EpisodeEvent(
            next_sequence,
            "model_turn",
            {
                "content": f"scripted dsh repair {goal.repair_goal_id}",
                "provider": "dsh_stub",
            },
        )
        return replace(
            previous,
            events=(*previous.events, extra),
            stop_reason="repair_reentry",
        )


def relay_key_fingerprint(raw_key: str) -> str:
    """artifact 只记指纹，不记 ``DSH_AB_RELAY_KEY`` 原文。"""

    secret = str(raw_key or "")
    if not secret:
        raise ValueError("relay key is empty")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def _empty_probe(*, status: str, pinned: str) -> dict[str, object]:
    return {
        "status": status,
        "head": "",
        "pinned": pinned,
        "matches_pin": False,
        "cone_ok": False,
        "missing_markers": list(DSH_CONE_MARKERS),
    }


def probe_dsh_checkout(*, source_index: str | None = None) -> dict[str, object]:
    """探测本地 sparse checkout 的 pin 与 cone。路径只来自参数或环境。

    收据故意不含 path：artifact 不能把工作机家目录带出去。
    """

    raw = source_index if source_index is not None else os.environ.get(
        DSH_SOURCE_INDEX_ENV, ""
    )
    path = str(raw or "").strip()
    pinned = PINNED_DSH_COMMIT
    if not path:
        return _empty_probe(status="missing", pinned=pinned)
    root = Path(path)
    if not (root / ".git").exists():
        return _empty_probe(status="not_git", pinned=pinned)
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return _empty_probe(status="not_git", pinned=pinned)
    head = completed.stdout.strip()
    missing = [marker for marker in DSH_CONE_MARKERS if not (root / marker).is_file()]
    matches_pin = head == pinned
    cone_ok = not missing
    if not matches_pin:
        status = "pin_mismatch"
    elif not cone_ok:
        status = "cone_incomplete"
    else:
        status = "ok"
    return {
        "status": status,
        "head": head,
        "pinned": pinned,
        "matches_pin": matches_pin,
        "cone_ok": cone_ok,
        "missing_markers": missing,
    }


def form_step8_decision(
    *,
    protocol_ok: bool,
    live_ab_ran: bool,
    net_benefit: bool = False,
) -> dict[str, object]:
    """默认立场，不是第 8 步对照收据。没跑 live A/B 就不能保留运行时。"""

    if not protocol_ok:
        reason = "protocol_failed"
    elif not live_ab_ran:
        reason = "live_ab_not_run"
    elif not net_benefit:
        reason = "no_measured_net_benefit"
    else:
        reason = "live_ab_showed_net_benefit"
    retain = bool(protocol_ok and live_ab_ran and net_benefit)
    return {
        "retain_dsh_runtime": retain,
        "reason": reason,
        "protocol_ok": protocol_ok,
        "live_ab_ran": live_ab_ran,
        "net_benefit": net_benefit,
        "forbidden_copy": (
            "--keychain-user",
            "localhost:57244",
            "gpt-5.6-sol",
        ),
        "credential_env": DSH_AB_RELAY_KEY_ENV,
        "pinned_commit": PINNED_DSH_COMMIT,
    }


def _outcome_from_snapshot(
    *,
    task_frame: TaskFrame,
    context: ResearchRunContext,
    snapshot: HeadlessGatewaySnapshot,
    draft: str,
) -> AgentOutcome:
    task_hash = context.contract.task_frame_hash or task_frame.task_frame_hash
    tool_exception = any(
        event.kind == "tool_error"
        and str(event.payload.get("error") or "") == "tool_exception"
        for event in snapshot.events
    )
    status = "failed" if tool_exception else "completed"
    stop_reason = "tool_exception" if tool_exception else "model_finish"
    events: list[EpisodeEvent] = [
        EpisodeEvent(
            1,
            "task",
            {
                "task_frame_hash": task_hash,
                "question": task_frame.raw_question,
            },
        ),
        *snapshot.events,
    ]
    next_sequence = events[-1].sequence + 1
    events.append(
        EpisodeEvent(
            next_sequence,
            "finish",
            {"status": status, "provider": "dsh_stub", "reason": stop_reason},
        )
    )
    evidence = () if tool_exception else snapshot.evidence
    hashes = tuple(item.content_hash for item in evidence if item.content_hash)
    bindings = tuple(
        OutputEvidenceBinding(
            output_id=item.output_id,
            evidence_hashes=hashes if hashes else (),
            gap="" if hashes else "scripted dsh stub collected no evidence",
        )
        for item in context.contract.required_outputs
        if item.required
    )
    return AgentOutcome(
        task_frame_hash=task_hash,
        status=status,
        draft="" if tool_exception else draft,
        evidence=evidence,
        traces=snapshot.traces,
        gaps=snapshot.gaps,
        stop_reason=stop_reason,
        events=tuple(events),
        bindings=bindings,
        usage=AgentUsage(
            llm_calls=0,
            tool_calls=snapshot.executed_count,
            invalid_actions=0,
        ),
    )


__all__ = [
    "ADAPTER_PROTOCOL_KEYS",
    "DSH_AB_RELAY_KEY_ENV",
    "DSH_CONE_MARKERS",
    "DSH_SOURCE_INDEX_ENV",
    "DshAdapterProtocolError",
    "DshStubRuntime",
    "PINNED_DSH_COMMIT",
    "ScriptedDshAction",
    "dump_adapter_protocol",
    "form_step8_decision",
    "probe_dsh_checkout",
    "relay_key_fingerprint",
]
