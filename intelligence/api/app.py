"""FastAPI backend for the local Market Intelligence Workbench."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager, nullcontext
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from threading import Event, Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr, field_validator

from intelligence import userspace
from intelligence.paths import default_market_db_path, default_paths
from intelligence.api.artifacts import ArtifactRegistry
from intelligence.api.daily_reports import (
    project_daily_agent,
    project_daily_review_html,
    project_daily_review_markdown,
)
from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    daily_projection_modules,
    moneyflow_module,
    new_structured_report,
    upsert_report_module,
)
from intelligence.api.stream_events import PUBLIC_EVENT_TYPES
from intelligence.services import followups as followups_svc
from intelligence.services import kb_rag
from intelligence.services import llm_refine
from intelligence.services import market_moneyflow
from intelligence.services import perspective_lab
from intelligence.services import run_store as rs
from intelligence.runtime.agent_runtime_factory import (
    resolve_runtime_backend,
    runtime_backend_readiness,
)
from intelligence.services.forecast_learning import (
    approve_reflection,
    learning_feedback_projection,
    reject_reflection,
    set_rule_status,
)
from intelligence.runtime.conversation_orchestrator import (
    TurnOrchestrator,
    sanitize_user_visible_artifact_text,
)
from intelligence.runtime.continuous_turn_adapter import (
    ContinuousTurnAdapter,
)
from intelligence.services.conversation_store import (
    ConversationDataIntegrityError,
    ConversationStore,
)
from intelligence.runtime.episode_finalizer import EpisodeFinalizer
from intelligence.runtime.episode_progress import (
    EpisodeProgress,
    RunEpisodeProgressPublisher,
    project_episode_progress,
)
from intelligence.services.episode_tools import (
    build_episode_registry,
    latest_market_date,
)
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
)
from intelligence.runtime.glm_agent_runtime import (
    DEFAULT_GLM_LLM_TIMEOUT,
    GLMAgentRuntime,
    GLMModelClient,
)
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.research_policy import (
    ResearchExecutionPolicy,
    grounded_deep,
)
from intelligence.services.keychain_credentials import KeychainCredentialError
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.market_snapshot_contract import (
    validate_market_snapshot_root,
)
from intelligence.services.run_store import RunStore
from intelligence.services.runtime_provenance import build_runtime_provenance
from intelligence.services import task_fulfillment
from intelligence.services.task_frame import derive_required_outputs
from intelligence.services.self_use_maturity import (
    SelfUseApprovalStore,
    SelfUseLedger,
    SelfUseLedgerIntegrityError,
    evaluate_maturity,
    trading_days_from_duckdb,
)
from intelligence.services.workbench_overview import build_workbench_overview
from intelligence.workbench_skills.registry import SKILL_REGISTRY

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(
    os.environ.get("WORKBENCH_REPO_ROOT", Path(__file__).resolve().parents[2])
)

_SSE_POLL_SECONDS = 0.5
_SSE_MAX_SECONDS = 15 * 60
_DEFAULT_CONTINUOUS_TURN_TIMEOUT_SECONDS = 120.0
_CONTINUOUS_RUNTIME_MODES = frozenset({"off", "canary", "on"})


def _continuous_turn_timeout_seconds() -> float:
    """一轮 continuous research 的墙钟预算，可由部署侧覆盖。

    为什么需要这个旋钮：这个数不是「多久算慢」的偏好，而是**必须大于 provider
    延迟分布**的物理约束，而 provider 是按部署换的。链路是

        回合预算 T
          → verification_reserve = min(40, T/3)          （continuous_turn_adapter.py:66,399）
          → runtime_timeout      = T − verification_reserve
          → 再扣 synthesis_reserve
          → stage_timeout        = min(llm_timeout, remaining − reserve)
          → 这个值**就是 HTTP 请求超时**（glm_agent_runtime.py:154/277 `timeout=remaining`）

    所以 provider 一慢，超时表现为 `TimeoutError` → `model_unavailable`，而且
    `provider_attempts=1`——一次尝试就把预算耗光，重试逻辑根本没机会跑，看起来
    像「重试没生效」，实际是没预算重试。

    2026-08-08 实测：出口切到中转后 T=120 时首轮实得约 25s，而中转延迟
    P50=28s / P95=50s（N=8，同一提示词规模）。于是约一半的 run 死在第一轮，
    与模型选型无关——换了三个模型都一样，因为 P50 本身就超预算。

    默认值保持 120.0 不变：改默认会影响每个不设这个 env 的调用方与全部测试。
    需要更大预算的部署在启动器里设 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`。
    非法值（非数字、<=0）回落默认而不是抛——这是服务启动路径，
    一个拼错的环境变量不该让服务起不来。
    """

    raw = os.environ.get("WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_CONTINUOUS_TURN_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_CONTINUOUS_TURN_TIMEOUT_SECONDS
    return value if value > 0 else _DEFAULT_CONTINUOUS_TURN_TIMEOUT_SECONDS


def _positive_float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _continuous_runtime_mode() -> str:
    mode = os.environ.get("ASK_CONTINUOUS_RUNTIME", "off").strip().lower()
    return mode if mode in _CONTINUOUS_RUNTIME_MODES else "off"


def _runtime_market_reference_date() -> str | None:
    paths = default_paths()
    snapshot = validate_market_snapshot_root(paths.market_snapshot_dir)
    if snapshot.get("ready") is True:
        summary = snapshot.get("summary")
        served = (
            summary.get("served_trade_date")
            if isinstance(summary, dict)
            else None
        )
        value = str(served or snapshot.get("date") or "").strip()
        if value:
            return value[:10]
    return latest_market_date(paths.finance_root)


def _zero_inner_synthesis_reserve(
    *,
    tier: str,
    question_type: str,
) -> float:
    """SDK/headless already draft inside the episode; reserve only outside it."""

    del tier, question_type
    return 0.0


def _memory_bound_registry_factory(
    memory_user: str | None,
) -> Callable[..., object]:
    """把 memory 身份绑进装配工厂，并断言身份真的穿透到了装配产物。

    第 4 步认领项 2（spec §7.2 的收尾）：可达性审计的三分法里，
    ``memory_lookup`` 落在「条件装配」档——审计只能证明**给了身份就装配得
    出来**，证明不了**生产真的把身份递到了装配函数**。这中间一段断掉时的
    形状是完全静默的半截状态：contract 仍授权、提示词仍教用法、模型收到的
    工具清单里静静少一个（实测 run_20260808_111451，注释在
    ``_run_conversation_turn`` 的调用点）。此前靠一条
    ``partial(..., memory_user=...)`` 的 if/else 撑着，回归时没有任何东西会红。

    所以在**身份存在的这一层**装断言：给了身份、且本轮 contract 授权了
    ``memory_lookup``，装配产物就必须包含它——否则响亮地炸，不许静默半截。
    能力未授权时缺席是正确行为，不断言（注册门在 ``episode_tools`` 是
    「授权 ∧ 身份」双条件）。

    ``memory_user`` 为空时原样返回 ``build_episode_registry``：None 是真配置
    不是占位（见 ``_build_continuous_turn_adapter`` docstring），该路径行为
    与接线前逐字节一致。

    两层对「身份为空」用的判据有意不同，这也是本断言不是恒真式的地方：本层
    用 Python 真值（``not memory_user``），装配层用 ``str(...).strip() != ""``
    （``episode_tools`` 的 ``memory_identity_resolved``）。于是「传了但是空白」
    ——上游 id 只剩空格这类——本层判它非空、装配层判它为空，落在**被守卫的
    那一侧**：两层口径不一致时炸，而不是静默少一个工具。真 ``None`` 与空串
    两层判据一致，走无守卫的原样路径。

    **本守卫盖不住的形状（写死认领）**：新增一个生产装配点、压根不传
    ``memory_user``。那时 ``None`` 与「本该有身份」无法在本层区分，守卫不
    介入，静默半截会重新出现。今天挡住它的是唯一那个生产调用点上的两条
    既有测试（``test_workbench_api.py`` 的
    ``test_conversation_worker_allocates_120_seconds_to_continuous_runtime``
    与 ``test_conversation_worker_passes_selected_model_to_orchestrator``，
    都断言 ``memory_user`` 等于该轮的 user id）；再开第二个装配点的人要把它
    一起钉住。可达性审计的 ⓘ 注记说的也是这一档残留，本轮未改。
    """

    if not memory_user:
        return build_episode_registry

    def registry_factory(frame, context):
        registry = build_episode_registry(frame, context, memory_user=memory_user)
        if (
            "memory_lookup" in context.contract.allowed_capabilities
            and "memory_lookup" not in registry.names()
        ):
            raise RuntimeError(
                "memory 身份已提供且能力已授权，但装配产物缺少 memory_lookup——"
                "身份在装配链路上被丢掉了（历史形状：注册守卫因缺身份刻意不注册，"
                f"而调用方明明有身份）。实际装配出的工具：{sorted(registry.names())}"
            )
        return registry

    return registry_factory


def _build_continuous_turn_adapter(
    *,
    providers: tuple[LLMProvider, ...],
    run_id: str,
    assistant_message_id: str,
    run_store: RunStore | None = None,
    conversation_id: str = "",
    event_id_prefix: str = "",
    is_cancelled: Callable[[], bool] | None = None,
    timeout: float = 90.0,
    deadline_expires_at: float | None = None,
    memory_user: str | None = None,
) -> ContinuousTurnAdapter:
    """Compose one provider chain into a shared continuous research kernel.

    ``memory_user`` is the one identity ``memory_lookup`` needs.  It is bound
    here rather than threaded through ``ContinuousTurnAdapter`` because the
    adapter has no other reason to know who the user is, and because a new
    keyword on ``registry_factory``'s call site would break every fixed-arity
    test double (``test_continuous_turn_adapter.py:1262`` is
    ``lambda frame, context:``).  Binding it into the factory keeps both the
    adapter and those doubles unchanged.

    Passing ``None`` is a real configuration, not a placeholder: without an
    identity ``build_episode_registry`` refuses to register the tool rather
    than falling back to ``resolve_user_id(None)`` -- see the precondition in
    ``episode_tools``.
    """

    progress_publisher = None
    if run_store is not None:
        if not conversation_id.strip():
            raise ValueError("conversation_id is required with a progress RunStore")
        progress_publisher = RunEpisodeProgressPublisher(
            run_store=run_store,
            run_id=run_id,
            conversation_id=conversation_id,
            message_id=assistant_message_id,
            is_cancelled=is_cancelled,
            event_id_prefix=event_id_prefix,
        )
    elif conversation_id.strip():
        raise ValueError("progress RunStore is required with conversation_id")

    def publish_episode_event(event) -> None:
        if progress_publisher is None:
            return
        progress = project_episode_progress(event)
        if progress is not None:
            progress_publisher.publish(progress)

    def publish_public_progress(progress: EpisodeProgress) -> None:
        if progress_publisher is None:
            return
        # The controller already emits the one public "understanding" stage
        # before the adapter starts. Do not show a second identical milestone
        # merely because the adapter also has an internal phase hook.
        if progress.key == "adapter:understanding":
            return
        progress_publisher.publish(progress)

    selection = resolve_runtime_backend()
    client = GLMModelClient(
        providers=providers,
        is_cancelled=is_cancelled,
    )
    finalizer = EpisodeFinalizer(
        client,
        llm_timeout=DEFAULT_GLM_LLM_TIMEOUT,
    )
    if selection.name == "continuous_glm":
        runtime = GLMAgentRuntime(
            client=client,
            finalizer=finalizer,
            is_cancelled=is_cancelled,
            event_sink=(
                publish_episode_event if progress_publisher is not None else None
            ),
        )
    elif selection.name == "sdk_glm":
        if not providers:
            raise RuntimeError("sdk_glm provider unavailable")
        from intelligence.runtime.openai_agents_runtime import (
            OpenAIAgentsRuntime,
            build_glm_sdk_model_factory,
        )

        provider = providers[0]
        runtime = OpenAIAgentsRuntime(
            backend="sdk_glm",
            model_name=provider.model,
            model_factory=build_glm_sdk_model_factory(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=provider.model,
                timeout=timeout,
            ),
            is_cancelled=is_cancelled,
            event_sink=(
                publish_episode_event if progress_publisher is not None else None
            ),
        )
    elif selection.name == "sdk_gpt":
        if not providers:
            raise RuntimeError("sdk_gpt provider unavailable")
        from intelligence.runtime.openai_agents_runtime import (
            OpenAIAgentsRuntime,
            build_gpt_sdk_model_factory,
        )

        provider = providers[0]
        if provider.name != "openai":
            raise RuntimeError("sdk_gpt requires an OpenAI provider")
        model_name = provider.model
        runtime = OpenAIAgentsRuntime(
            backend="sdk_gpt",
            model_name=model_name,
            model_factory=build_gpt_sdk_model_factory(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=model_name,
                timeout=timeout,
            ),
            is_cancelled=is_cancelled,
            event_sink=(
                publish_episode_event if progress_publisher is not None else None
            ),
        )
    else:
        if (
            os.environ.get("AGENT_RUNTIME_BENCHMARK_ENABLE", "").strip()
            != "1"
        ):
            raise RuntimeError("Codex headless runtime is benchmark-only")
        from intelligence.runtime.codex_headless_runtime import (
            CodexHeadlessRuntime,
        )

        runtime = CodexHeadlessRuntime(
            model=os.environ.get("CODEX_HEADLESS_MODEL"),
            is_cancelled=is_cancelled,
        )
    semantic_verifier = SemanticEpisodeVerifier(
        primary_judge=client,
        finalizer=finalizer,
    )
    task_id = f"{run_id}:{assistant_message_id}"
    # 在装配层绑身份，而不是给 adapter 加一个 memory_user 参数：adapter 只负责
    # 「怎么跑一轮」，不该知道记忆台账按谁分区。同时 registry_factory 的调用点
    # （`continuous_turn_adapter.py` 里的 `self._registry_factory(frame, context)`）
    # 保持两个位置参数不变——测试替身里有固定参数的 `lambda frame, context: ...`，
    # 在调用点加 kwarg 会把它们全打断。
    registry_factory = _memory_bound_registry_factory(memory_user)
    return ContinuousTurnAdapter(
        runtime=runtime,
        semantic_verifier=semantic_verifier,
        runtime_name=selection.name,
        mode=_continuous_runtime_mode(),
        registry_factory=registry_factory,
        task_id_factory=lambda: task_id,
        timeout=timeout,
        synthesis_reserve_for_task=(
            GLMAgentRuntime.synthesis_reserve_for_task
            if selection.name == "continuous_glm"
            else _zero_inner_synthesis_reserve
        ),
        today=rs._now_iso()[:10],
        latest_data_date=_runtime_market_reference_date(),
        is_cancelled=is_cancelled,
        deadline_expires_at=deadline_expires_at,
        progress_sink=(
            publish_public_progress if progress_publisher is not None else None
        ),
    )


_WORKER_COUNT = 2
_RESTART_REASON = "workbench_restarted_before_completion"
_STABLE_MACHINE_FALLBACK_REASONS = frozenset(
    {
        "provider_timeout",
        "provider_unavailable",
        "quality_gate_rejected",
        "budget_exhausted",
        # 本轮 LLM 调用预算耗尽。原先归进 provider_unavailable，对外读起来像
        # 「供应商挂了」，实际是我们自己的限额——是固定枚举，不含用户数据。
        "call_budget_exhausted",
        # 我们自己的共享 deadline 走完了（不是对方超时）。同上，是限额不是故障。
        "deadline_exhausted_local",
        # 预算不够所以没发这次调用（准入检查拦下），一秒没浪费。
        "insufficient_budget",
    }
)
_PUBLIC_METADATA_STRING_FIELDS = frozenset(
    {
        "schema_version",
        "event_id",
        "event_type",
        "run_id",
        "conversation_id",
        "message_id",
        "step_id",
        "skill_id",
        "module_id",
        "artifact_id",
        "report_id",
        "status",
        "role",
        "task_type",
        "skill_mode",
        "perspective_mode",
        "phase",
        "answer_phase",
        "selection_source",
        "kind",
        "renderer",
        "tag",
    }
)
_PUBLIC_METADATA_STRING_LIST_FIELDS = frozenset(
    {
        "selected_skill_ids",
        "invoked_skill_ids",
        "selected_perspective_ids",
    }
)
_PUBLIC_PROGRESS_STAGES = frozenset(
    {"understanding", "planning", "research", "repair", "verification", "finalizing"}
)
_PUBLIC_TRACE_STAGE_BY_PRIVATE_NAME = {
    "turn_controller": "understanding",
    "route_skills": "planning",
    "ask_current_turn": "research",
    "ask_retrieve_compose": "research",
    "continuous_evidence_binding": "verification",
    "llm_call_ledger": "verification",
    "query_ledger": "research",
    "research_execution_budget": "research",
    "budget": "research",
    "task_fulfillment": "verification",
    "render_artifacts": "finalizing",
    "foresight_followups": "finalizing",
}
_PUBLIC_TRACE_MESSAGE_BY_PRIVATE_NAME = {
    "turn_controller": "已完成问题理解与任务对齐。",
    "route_skills": "已确认本轮所需研究能力。",
    "ask_current_turn": "正在检索本轮证据。",
    "ask_retrieve_compose": "已完成本轮证据检索与整理。",
    "continuous_evidence_binding": "已完成回答与证据的绑定核对。",
    "llm_call_ledger": "已完成模型调用状态核对。",
    "query_ledger": "已完成检索执行状态核对。",
    "research_execution_budget": "已完成本轮研究预算核对。",
    "budget": "已完成本轮研究预算核对。",
    "task_fulfillment": "已完成回答与任务契约的逐项核对。",
    "render_artifacts": "已生成本轮研究产物。",
    "foresight_followups": "已整理后续核验问题。",
}
_PUBLIC_PROGRESS_MESSAGES = {
    "understanding": "已对齐本轮任务并进入研究。",
    "planning": "已形成研究计划并确认研究深度。",
    "research": "已完成一项证据核对。",
    "repair": "正在针对关键证据缺口定向补证。",
    "verification": "正在核验证据绑定与回答完整性。",
    "finalizing": "正在基于核验结果形成公开回答。",
}
_PUBLIC_HIDDEN_CONTROL_KEYS = frozenset(
    {
        "task_frame_hash",
        "turn_intent",
        "research_plan",
        "pending_task_frame",
        "legacy_query_envelope",
    }
)


def _public_degrades(values: list[str]) -> list[str]:
    return list(
        dict.fromkeys(
            sanitize_user_visible_artifact_text(value)
            for value in values
            if isinstance(value, str) and value.strip()
        )
    )


def _public_run_payload(run: rs.Run) -> dict[str, object]:
    payload = asdict(run)
    payload["artifacts"] = [
        artifact
        for artifact in run.artifacts
        if rs.artifact_visibility(artifact) == "public"
    ]
    payload["degrades"] = _public_degrades(run.degrades)
    if run.error:
        payload["error"] = sanitize_user_visible_artifact_text(run.error)
    return payload


def _is_public_machine_enum(path: tuple[str, ...], value: str) -> bool:
    return (
        len(path) >= 3
        and path[-3:] == ("report", "llm", "fallback_reason")
        and value in _STABLE_MACHINE_FALLBACK_REASONS
    )


def _is_public_metadata_string(path: tuple[str, ...]) -> bool:
    return bool(path) and (
        path[-1] in _PUBLIC_METADATA_STRING_FIELDS
        or (len(path) >= 2 and path[-2] in _PUBLIC_METADATA_STRING_LIST_FIELDS)
    )


def _public_value(
    value: object,
    *,
    path: tuple[str, ...] = (),
    preserve_text_paths: frozenset[tuple[str, ...]] = frozenset(),
) -> object:
    if isinstance(value, str):
        if (
            _is_public_machine_enum(path, value)
            or _is_public_metadata_string(path)
            or any(
                len(path) >= len(suffix) and path[-len(suffix) :] == suffix
                for suffix in preserve_text_paths
            )
        ):
            return value
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(decoded, (dict, list)):
                    return json.dumps(
                        _public_value(
                            decoded,
                            path=path,
                            preserve_text_paths=preserve_text_paths,
                        ),
                        ensure_ascii=False,
                    )
        return sanitize_user_visible_artifact_text(value)
    if isinstance(value, list):
        return [
            _public_value(
                item,
                path=(*path, str(index)),
                preserve_text_paths=preserve_text_paths,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            str(key): _public_value(
                item,
                path=(*path, str(key)),
                preserve_text_paths=preserve_text_paths,
            )
            for key, item in value.items()
            if str(key) not in _PUBLIC_HIDDEN_CONTROL_KEYS
        }
    return value


def _public_trace_step(step: dict[str, object]) -> dict[str, object]:
    raw_name = str(step.get("name") or "").strip()
    stage = (
        raw_name
        if raw_name in _PUBLIC_PROGRESS_STAGES
        else _PUBLIC_TRACE_STAGE_BY_PRIVATE_NAME.get(raw_name, "research")
    )
    status = str(step.get("status") or "completed").strip().lower()
    if status not in {"running", "completed", "failed", "skipped"}:
        status = "completed"
    message = _PUBLIC_TRACE_MESSAGE_BY_PRIVATE_NAME.get(raw_name)
    if message is None:
        if status == "failed":
            message = "一项研究步骤未完成，相关结果未纳入结论。"
        elif status == "running":
            message = _PUBLIC_PROGRESS_MESSAGES[stage].replace("已完成", "正在完成")
        else:
            message = _PUBLIC_PROGRESS_MESSAGES[stage]
    raw_step_id = str(step.get("step_id") or raw_name or "step")
    public_step_id = hashlib.sha256(raw_step_id.encode("utf-8")).hexdigest()[:12]
    warnings = step.get("warnings")
    public_step: dict[str, object] = {
        "step_id": f"step:{public_step_id}",
        "name": stage,
        "status": status,
        "started_at": str(step.get("started_at") or ""),
        "finished_at": (
            str(step["finished_at"])
            if step.get("finished_at") is not None
            else None
        ),
        "input_summary": "",
        "output_summary": message,
        "warnings": _public_degrades(
            [str(item) for item in warnings]
            if isinstance(warnings, list)
            else []
        ),
    }
    diagnostic = _public_synthesis_diagnostic(step)
    if diagnostic is not None:
        public_step["diagnostic"] = diagnostic
    fulfillment = _public_fulfillment_diagnostic(step)
    if fulfillment is not None:
        public_step["fulfillment"] = fulfillment
    return public_step


# 判缺侧对外只放这几项。`items[].gap` 是给人读的中文长句，且可能带内部措辞，
# 故**不外放**——要定位缺哪一格靠 `output_id` + `reason_code`，那才是结构化的。
_PUBLIC_FULFILLMENT_ITEM_FIELDS = ("output_id", "status", "reason_code", "candidate_count")


def _public_fulfillment_diagnostic(
    step: dict[str, object],
) -> dict[str, object] | None:
    """把 task_fulfillment 的结构化判缺投影到公开 trace。

    为什么需要它：`FulfillmentVerdict.to_dict()` 早就带了 `reason_code`
    （`no_candidate_claim` / `text_absent` / `evidence_unbound` / `marker_absent`）
    和 `candidate_count`，orchestrator 也已经把它写进内部 trace step。但公开
    trace 此前只对 `answer_synthesis` 一步投影 `diagnostic`，于是这份判缺明细
    **一次都没出过内网**：实测 11 个 turn 的 gaps 里写着「最终回答未完成任务
    契约」，却没有一个能回答「缺的是哪一格 output」——排查只能靠读代码猜。

    这也是「路 B 用历史产出反推可满足性」走不通的直接原因（见
    `docs/superpowers/specs/2026-08-05-intent-routing-candidate-arbitration-design.md`
    §3.4）：判缺结果没有结构化落盘，历史样本里就没有可统计的判据。
    """

    if str(step.get("name") or "") not in {
        "task_fulfillment",
        "task_fulfillment_repair",
    }:
        return None
    raw_summary = step.get("output_summary")
    if not isinstance(raw_summary, str):
        return None
    try:
        summary = json.loads(raw_summary)
    except json.JSONDecodeError:
        return None
    if not isinstance(summary, dict):
        return None
    status = summary.get("status")
    items = summary.get("items")
    if not isinstance(status, str) or not isinstance(items, list):
        return None
    projected: dict[str, object] = {
        "status": status,
        "repaired": bool(summary.get("repaired")),
        "items": [
            {
                key: item[key]
                for key in _PUBLIC_FULFILLMENT_ITEM_FIELDS
                if key in item
            }
            for item in items
            if isinstance(item, dict)
        ],
    }
    counts = summary.get("reason_code_counts")
    if isinstance(counts, dict):
        projected["reason_code_counts"] = {
            str(key): value
            for key, value in counts.items()
            if isinstance(value, int)
        }
    evaluated = summary.get("evaluated_output_ids")
    if isinstance(evaluated, list):
        projected["evaluated_output_ids"] = [str(item) for item in evaluated]
    return projected


def _public_synthesis_diagnostic(
    step: dict[str, object],
) -> dict[str, object] | None:
    if str(step.get("name") or "") != "answer_synthesis":
        return None
    raw_summary = step.get("output_summary")
    if not isinstance(raw_summary, str):
        return None
    try:
        summary = json.loads(raw_summary)
    except json.JSONDecodeError:
        return None
    diagnostic = summary.get("diagnostic") if isinstance(summary, dict) else None
    if not isinstance(diagnostic, dict):
        return None
    required_fields = {
        "state",
        "reason_code",
        "detail",
        "prepared_message_count",
        "candidate_claim_count",
        "bound_claim_count",
    }
    if not required_fields.issubset(diagnostic):
        return None
    state = diagnostic.get("state")
    if not isinstance(state, str):
        return None
    if state not in {
        "not_requested",
        "not_prepared",
        "attempted",
        "accepted",
        # 确定性绑定过了、语义审缺席但带告示放行。既不是 accepted 也不是 rejected，
        # 混进任一边都会让台账读错健康度。
        "released_unverified",
        "rejected",
        "failed",
    }:
        return None
    reason_code = diagnostic.get("reason_code")
    if not isinstance(reason_code, str) or re.fullmatch(
        r"[A-Za-z0-9_.-]{1,80}", reason_code
    ) is None:
        return None
    raw_detail = diagnostic.get("detail")
    if not isinstance(raw_detail, str):
        return None
    if re.search(
        r"(?:\bprompt\b|evidence[_\s-]*(?:body|text|content|payload)|"
        r"authorization|bearer\s+|api[_\s-]*key|credential|"
        r"/(?:Users|home|tmp|private/tmp)/|[A-Za-z]:\\)",
        raw_detail,
        flags=re.IGNORECASE,
    ):
        return None
    detail = sanitize_user_visible_artifact_text(raw_detail)[:200]
    result: dict[str, object] = {
        "state": state,
        "reason_code": reason_code,
        "detail": detail,
    }
    for field_name in (
        "prepared_message_count",
        "candidate_claim_count",
        "bound_claim_count",
    ):
        value = diagnostic.get(field_name)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 1_000_000
        ):
            return None
        result[field_name] = value
    shadow_status = diagnostic.get("shadow_status")
    if isinstance(shadow_status, str) and re.fullmatch(
        r"[a-z0-9_]{0,40}", shadow_status
    ):
        result["shadow_status"] = shadow_status
    phases = _public_synthesis_phases(diagnostic.get("phases"))
    if phases:
        result["phases"] = phases
    return result


# 单段耗时是纯数值遥测，但仍然只放行固定枚举 + 有界整数：这条通道以前只走过
# 三个计数，加字段的人容易顺手把 provider 原始错误串塞进来。
_PUBLIC_SYNTHESIS_PHASE_NAMES = frozenset({"brief", "composer", "judge"})
_PUBLIC_SYNTHESIS_PHASE_STATUSES = frozenset({"ok", "failed", "skipped"})
_PUBLIC_SYNTHESIS_PHASE_MODES = frozenset({"provider", "deterministic"})


def _public_synthesis_phases(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, (list, tuple)):
        return []
    phases: list[dict[str, object]] = []
    for item in list(raw)[:8]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        if (
            name not in _PUBLIC_SYNTHESIS_PHASE_NAMES
            or status not in _PUBLIC_SYNTHESIS_PHASE_STATUSES
        ):
            continue
        public_phase: dict[str, object] = {"name": name, "status": status}
        bounded = True
        for field_name in ("remaining_ms_at_entry", "timeout_s", "elapsed_ms"):
            value = item.get(field_name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= 86_400_000
            ):
                bounded = False
                break
            public_phase[field_name] = value
        if not bounded:
            continue
        reason_code = item.get("reason_code")
        if isinstance(reason_code, str) and re.fullmatch(
            r"[A-Za-z0-9_.-]{0,80}", reason_code
        ):
            public_phase["reason_code"] = reason_code
        execution_mode = item.get("execution_mode")
        if execution_mode is not None:
            if execution_mode not in _PUBLIC_SYNTHESIS_PHASE_MODES:
                continue
            public_phase["execution_mode"] = execution_mode
        phases.append(public_phase)
    return phases


def _public_stream_event(event: dict[str, object]) -> dict[str, object]:
    event_type = event.get("event_type")
    if event_type == "trace.step":
        raw_payload = event.get("payload")
        raw_step = raw_payload.get("step") if isinstance(raw_payload, dict) else None
        event = {
            **event,
            "payload": {
                "step": _public_trace_step(raw_step if isinstance(raw_step, dict) else {})
            },
        }
    preserve_paths: set[tuple[str, ...]] = {("payload", "message", "content")}
    if event_type == "answer.snapshot":
        preserve_paths.add(("payload", "text"))
    elif event_type == "text.delta":
        preserve_paths.add(("payload", "delta"))
    projected = _public_value(
        event,
        preserve_text_paths=frozenset(preserve_paths),
    )
    return projected if isinstance(projected, dict) else {}


def _public_message_payload(message: object) -> dict[str, object]:
    projected = _public_value(
        asdict(message),
        preserve_text_paths=frozenset({("content",)}),
    )
    return projected if isinstance(projected, dict) else {}


class CancellationSignal:
    def __init__(self, *, deadline_expires_at: float | None = None) -> None:
        self._event = Event()
        self.reason: str | None = None
        self.deadline_expires_at = deadline_expires_at

    def set(self, reason: str) -> None:
        self.reason = reason
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)

    def remaining(self, default: float) -> float:
        if self.deadline_expires_at is None:
            return max(0.0, float(default))
        return max(0.0, self.deadline_expires_at - time.monotonic())


class RunSupervisor:
    def __init__(
        self,
        max_workers: int = _WORKER_COUNT,
        timeout_sec: float = _SSE_MAX_SECONDS,
    ) -> None:
        self.max_workers = max_workers
        self.timeout_sec = timeout_sec
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="workbench-run",
        )
        self._futures: dict[tuple[str, str], Future[None]] = {}
        self._timers: dict[tuple[str, str], threading.Timer] = {}
        self._stores: dict[tuple[str, str], RunStore] = {}
        self._signals: dict[tuple[str, str], CancellationSignal] = {}
        self._terminal_handlers: dict[tuple[str, str], Callable[[str], None]] = {}
        self._lock = threading.Lock()

    def submit(self, store: RunStore, run_id: str, req: CreateRunRequest) -> None:
        self._submit(
            store,
            run_id,
            lambda _: _run_ask(store, run_id, req),
        )

    def submit_conversation(
        self,
        store: RunStore,
        run_id: str,
        *,
        repo_root: Path,
        conversation_store: ConversationStore,
        conversation_id: str,
        assistant_message_id: str,
        query: str,
        skill_mode: Literal["manual", "auto", "hybrid"],
        selected_skill_ids: list[str],
        perspective_mode: Literal["neutral", "single", "compare"],
        selected_perspective_ids: list[str],
        event_id_prefix: str = "",
        llm_providers: tuple[LLMProvider, ...] = (),
    ) -> None:
        self._submit(
            store,
            run_id,
            lambda signal: _run_conversation_turn(
                repo_root=repo_root,
                conversation_store=conversation_store,
                run_store=store,
                conversation_id=conversation_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                query=query,
                skill_mode=skill_mode,
                selected_skill_ids=selected_skill_ids,
                perspective_mode=perspective_mode,
                selected_perspective_ids=selected_perspective_ids,
                cancellation_signal=signal,
                event_id_prefix=event_id_prefix,
                llm_providers=llm_providers,
            ),
            on_terminal=lambda reason: _terminalize_pending_message(
                conversation_store,
                store,
                conversation_id,
                assistant_message_id,
                run_id,
                reason,
            ),
        )

    def _submit(
        self,
        store: RunStore,
        run_id: str,
        runner: Callable[[CancellationSignal], None],
        on_terminal: Callable[[str], None] | None = None,
    ) -> None:
        key = (store.user_id, run_id)
        store.mark_running(run_id)
        signal = CancellationSignal(
            deadline_expires_at=time.monotonic() + self.timeout_sec
        )
        timer = threading.Timer(
            self.timeout_sec,
            self._expire,
            args=(store, run_id, key),
        )
        timer.daemon = True
        with self._lock:
            future = self._executor.submit(runner, signal)
            self._futures[key] = future
            self._timers[key] = timer
            self._stores[key] = store
            self._signals[key] = signal
            if on_terminal is not None:
                self._terminal_handlers[key] = on_terminal
        future.add_done_callback(lambda completed: self._forget(key, completed))
        timer.start()

    def cancel(self, store: RunStore, run_id: str) -> bool:
        key = (store.user_id, run_id)
        with self._lock:
            future = self._futures.get(key)
            timer = self._timers.get(key)
            active_store = self._stores.get(key, store)
            signal = self._signals.get(key)
            terminal_handler = self._terminal_handlers.get(key)
        if timer is not None:
            timer.cancel()
        if signal is not None:
            signal.set("cancelled_by_user")
        queued_cancelled = future.cancel() if future is not None else False
        run = active_store.finish_run(
            run_id,
            rs.STATUS_CANCELLED,
            error="cancelled_by_user",
        )
        if run.status == rs.STATUS_CANCELLED and terminal_handler is not None:
            terminal_handler("cancelled_by_user")
        return queued_cancelled

    @property
    def cancellation_signals(self) -> dict[tuple[str, str], CancellationSignal]:
        return self._signals

    def active_count(self) -> int:
        with self._lock:
            return sum(not future.done() for future in self._futures.values())

    def shutdown(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
        for timer in timers:
            timer.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _forget(self, key: tuple[str, str], future: Future[None]) -> None:
        with self._lock:
            self._futures.pop(key, None)
            timer = self._timers.pop(key, None)
            store = self._stores.pop(key, None)
            self._signals.pop(key, None)
            terminal_handler = self._terminal_handlers.pop(key, None)
        if timer is not None:
            timer.cancel()
        if future.cancelled() or store is None:
            return
        if future.exception() is None:
            return
        run_id = key[1]
        _, claimed = store.claim_failed_run(
            run_id,
            error="executor_failure",
            degrade="executor_failure",
        )
        if claimed and terminal_handler is not None:
            terminal_handler("executor_failure")

    def _expire(
        self,
        store: RunStore,
        run_id: str,
        key: tuple[str, str],
    ) -> None:
        with self._lock:
            future = self._futures.get(key)
            signal = self._signals.get(key)
            terminal_handler = self._terminal_handlers.get(key)
        if future is None or future.done():
            return
        _, claimed = store.claim_failed_run(
            run_id,
            error="executor_timeout",
            degrade="executor_timeout",
        )
        if not claimed:
            return
        if signal is not None:
            signal.set("executor_timeout")
        future.cancel()
        if terminal_handler is not None:
            terminal_handler("executor_timeout")


class CreateRunRequest(BaseModel):
    question: str = Field(min_length=1)
    user: str | None = None
    task_type: str = "ask"
    session_id: str | None = None
    parent_run_id: str | None = None
    compose: bool = True
    repo_root: Path | None = Field(default=None, exclude=True)


def _run_terminal(store: RunStore, run_id: str) -> bool:
    return store.load_run(run_id).status in (
        rs.STATUS_COMPLETED,
        rs.STATUS_FAILED,
        rs.STATUS_CANCELLED,
    )


class CreateConversationRequest(BaseModel):
    title: str = "新对话"
    user: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class UpdateConversationRequest(BaseModel):
    title: str = Field(min_length=1)
    user: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class UserRequest(BaseModel):
    user: str | None = None


class CreateMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    skill_mode: Literal["manual", "auto", "hybrid"]
    selected_skill_ids: list[str] = Field(default_factory=list)
    perspective_mode: Literal["neutral", "single", "compare"] = "neutral"
    selected_perspective_ids: list[str] = Field(default_factory=list)
    user: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class ConfigureLLMRequest(BaseModel):
    provider: Literal["zhipu", "openai", "deepseek", "moonshot", "dashscope"]
    api_key: SecretStr
    base_url: str | None = Field(default=None, min_length=8, max_length=2048)
    model: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:/-]+$",
    )
    remember: bool = False
    user: str | None = None


class ApproveReflectionRequest(BaseModel):
    hypothesis_ids: list[str] = Field(default_factory=list, max_length=50)


class RuleStatusRequest(BaseModel):
    status: Literal["approved", "rejected"]


def _run_conversation_turn(
    *,
    repo_root: Path,
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    run_id: str,
    assistant_message_id: str,
    query: str,
    skill_mode: Literal["manual", "auto", "hybrid"],
    selected_skill_ids: list[str],
    cancellation_signal: CancellationSignal,
    perspective_mode: Literal["neutral", "single", "compare"] = "neutral",
    selected_perspective_ids: list[str] | None = None,
    event_id_prefix: str = "",
    llm_providers: tuple[LLMProvider, ...] = (),
) -> None:
    try:
        test_delay_ms = int(os.environ.get("WORKBENCH_TEST_RUN_DELAY_MS", "0"))
    except ValueError:
        test_delay_ms = 0
    test_delay_ms = min(5000, max(0, test_delay_ms))
    if test_delay_ms and cancellation_signal.wait(test_delay_ms / 1000):
        return
    primary_provider = llm_providers[0] if llm_providers else None
    provider_context = (
        llm_refine.provider_override(primary_provider)
        if primary_provider is not None
        else nullcontext()
    )
    with provider_context:
        TurnOrchestrator(
            repo_root=repo_root,
            conversation_store=conversation_store,
            run_store=run_store,
            llm_model=primary_provider.model if primary_provider is not None else None,
            is_cancelled=cancellation_signal.is_set,
            cancellation_reason=lambda: cancellation_signal.reason,
            event_id_prefix=event_id_prefix,
            # The legacy grounded presenter owns a two-provider synthesis tail;
            # reserve its measured frozen-replay envelope explicitly.  The
            # continuous adapter below keeps its separate 120s contract.
            research_policy=ResearchExecutionPolicy(
                max_elapsed_seconds=grounded_deep.root_seconds,
                synthesis_reserve_seconds=(
                    grounded_deep.synthesis_reserve_seconds
                ),
                grounded_budget_profile=grounded_deep,
            ),
            continuous_turn_adapter=_build_continuous_turn_adapter(
                providers=llm_providers,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                run_store=run_store,
                conversation_id=conversation_id,
                event_id_prefix=event_id_prefix,
                is_cancelled=cancellation_signal.is_set,
                timeout=min(
                    _continuous_turn_timeout_seconds(),
                    cancellation_signal.remaining(
                        _continuous_turn_timeout_seconds()
                    ),
                ),
                deadline_expires_at=cancellation_signal.deadline_expires_at,
                # 不传这个，`memory_lookup` 在生产里一次都不会注册。
                #
                # `_build_continuous_turn_adapter` 里那条
                # `_memory_bound_registry_factory(memory_user)`（当时还是
                # `partial(build_episode_registry, memory_user=memory_user)`）
                # 早就写好了，但它的 `if memory_user` 永远为假：本函数此前没有把
                # 身份传进去，而 `build_episode_registry` 的守卫
                # （`episode_tools.py:937`）在缺身份时**刻意不注册**该工具，
                # 以免把 A 用户的私有台账读给 B 用户。
                #
                # 后果是一个完全静默的半截状态：contract.allowed_capabilities
                # 里有 memory_lookup、提示词里讲了怎么用它、prior_recall 槽位也
                # 开着，唯独模型收到的工具清单里没有它。实测（run_20260808_111451）
                # 模型看到的是 7 个工具、其中不含 memory_lookup——它不是"没选"，
                # 是压根没得选。授权与身份穿透必须成对出现，只做一半不报错。
                #
                # `run_store.user_id` 是 `RunStore` 已解析好的 id（同一行下方的
                # `runtime_providers_for(run_store.user_id)` 用的就是它），
                # 所以这里不需要新增参数或改上游签名。
                memory_user=run_store.user_id,
            ),
        ).run_turn(
            conversation_id=conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query=query,
            skill_mode=skill_mode,
            selected_skill_ids=selected_skill_ids,
            perspective_mode=perspective_mode,
            selected_perspective_ids=selected_perspective_ids or [],
        )


def _terminalize_pending_message(
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    message_id: str,
    run_id: str,
    reason: str,
) -> None:
    current = next(
        (
            message
            for message in conversation_store.load_messages(conversation_id)
            if message.message_id == message_id
        ),
        None,
    )
    if current is None or current.status in {
        rs.STATUS_COMPLETED,
        rs.STATUS_FAILED,
        rs.STATUS_CANCELLED,
    }:
        return
    status = rs.STATUS_CANCELLED if reason == "cancelled_by_user" else rs.STATUS_FAILED
    warning = (
        "用户已取消本轮执行"
        if status == rs.STATUS_CANCELLED
        else (
            "本轮执行超时"
            if reason == "executor_timeout"
            else "本轮执行未完成"
        )
    )
    message = conversation_store.revise_message(
        conversation_id,
        message_id,
        content=current.content,
        status=status,
        selected_skill_ids=current.selected_skill_ids,
        invoked_skill_ids=current.invoked_skill_ids,
        citations=current.citations,
        degrades=list(dict.fromkeys([*current.degrades, warning])),
    )
    run_store.append_stream_event(
        run_id,
        event_id=f"supervisor:{status}",
        event_type="message.error",
        payload={"status": status, "message": asdict(message)},
        conversation_id=conversation_id,
        message_id=message_id,
    )


def _ask_answer_coverage(
    question: str,
    result: object,
    answer_md: str,
) -> dict[str, object]:
    """Record whether each required output's wording reached this path's answer.

    ``POST /api/runs`` → ``_run_ask`` is a second entry point, independent of
    ``TurnOrchestrator``.  It never calls ``task_fulfillment`` at all, and it
    calls ``complete_report`` without ``answer_status`` — which silently falls
    back to the ``business_status`` default ``"complete"``.  So this path has
    always reported a complete answer without anything having checked it.

    Observation only, same discipline as the continuous path: measure the gap
    before sizing a policy against it.

    ``required_outputs`` is re-derived from (question, question_type) via the
    shared ``task_frame.derive_required_outputs`` rather than duplicating the
    default table, so both entry points grade against the same contract.
    ``AskResult`` does not carry the frame, and this path never builds one.
    """

    question_plan = getattr(result, "question_plan", None)
    question_type = str(getattr(question_plan, "question_type", "") or "")
    required_outputs = derive_required_outputs(question_type, question)
    answer_text = str(getattr(result, "synthesis", None) or answer_md or "")
    coverage = task_fulfillment.evaluate_marker_coverage(
        required_outputs,
        answer_text,
    )
    return {
        "entry_point": "api_runs_ask",
        "question_type": question_type or None,
        **coverage,
    }


def _run_ask(
    store: RunStore,
    run_id: str,
    req: CreateRunRequest,
) -> None:
    from intelligence.services.ask import AskOptions, answer_query, render_answer
    from intelligence.services.llm_refine import detect_provider

    repo_root = req.repo_root or REPO_ROOT
    report = new_structured_report(
        run_id=run_id,
        question=req.question,
        task_type=req.task_type,
    )
    store.append_stream_event(
        run_id,
        event_id="report:start",
        event_type="report.start",
        payload={"report": report},
    )
    if _run_terminal(store, run_id):
        return

    report_warnings: list[str] = []
    report_date: str | None = None

    def emit_module(module: dict[str, object]) -> None:
        upsert_report_module(report, module)
        store.append_stream_event(
            run_id,
            event_id=f"module:{module['module_id']}",
            event_type="report.module",
            payload={"module": module},
        )

    if req.task_type == "daily":
        try:
            report_date, daily_modules, daily_warnings = daily_projection_modules(
                repo_root
            )
            report["as_of"] = report_date
            report_warnings.extend(daily_warnings)
            for module in daily_modules:
                emit_module(module)
            if _run_terminal(store, run_id):
                return
        except Exception as exc:  # noqa: BLE001
            warning = f"日报 canonical 投影失败（{type(exc).__name__}）"
            report_warnings.append(warning)
            store.add_degrade(run_id, warning)

    wants_moneyflow = (
        req.task_type == "daily"
        or market_moneyflow.parse_moneyflow_intent(req.question)
    )
    if wants_moneyflow:
        snapshot = market_moneyflow.load_moneyflow_snapshot(
            default_market_db_path(),
            as_of_date=report_date,
        )
        emit_module(moneyflow_module(snapshot))
        if snapshot.status != "ok":
            for warning in snapshot.warnings:
                store.add_degrade(run_id, warning)
        if _run_terminal(store, run_id):
            return

    started_at = rs._now_iso()
    store.append_step(
        run_id,
        step_id="s01",
        name="ask_retrieve_compose",
        status="running",
        input_summary=req.question,
        started_at=started_at,
    )
    try:
        result = answer_query(
            AskOptions(
                query=req.question,
                date=report_date,
                user=req.user,
                compose=req.compose,
                compose_revise_on_warn=req.task_type != "daily",
                market_db_path=default_market_db_path(),
                force_moneyflow_block=req.task_type == "daily",
            )
        )
        rag_telemetry = (
            asdict(result.wiki_rag_telemetry)
            if result.wiki_rag_telemetry is not None
            else {}
        )
        store.update_provenance(
            run_id,
            source_date=result.trade_date,
            kb_commit=str(rag_telemetry.get("index_source_revision") or "") or None,
            kb_index_built_at=str(rag_telemetry.get("index_built_at") or "") or None,
            kb_index_freshness=str(rag_telemetry.get("index_freshness") or "") or None,
        )
        if _run_terminal(store, run_id):
            return
    except Exception as exc:  # noqa: BLE001
        if _run_terminal(store, run_id):
            return
        store.append_step(
            run_id,
            step_id="s01",
            name="ask_retrieve_compose",
            status="failed",
            input_summary=req.question,
            started_at=started_at,
            finished_at=rs._now_iso(),
            warnings=[f"{type(exc).__name__}: {exc}"],
        )
        report["status"] = "failed"
        report_warnings.append(f"{type(exc).__name__}: {exc}")
        report["warnings"] = report_warnings
        store.append_stream_event(
            run_id,
            event_id="report:error",
            event_type="report.error",
            payload={"report": report},
        )
        store.finish_run(run_id, rs.STATUS_FAILED, error=f"{type(exc).__name__}: {exc}")
        return

    hits = [
        source
        for source, found in (
            ("market", result.found_market),
            ("graph", result.found_graph),
            ("wiki", result.found_wiki),
        )
        if found
    ]
    citation_counts = dict(
        Counter(citation.tag[:1] for citation in result.citations if citation.tag)
    )
    store.append_step(
        run_id,
        step_id="s01",
        name="ask_retrieve_compose",
        status="completed",
        input_summary=req.question,
        started_at=started_at,
        finished_at=rs._now_iso(),
        output_summary=(
            f"命中源：{'+'.join(hits) or '无'}；引用 {len(result.citations)} 条"
            f"；模块 {','.join(result.routed_modules) or '—'}"
        ),
        warnings=list(result.warnings),
        retrieval={
            "sources": hits,
            "citation_counts": citation_counts,
            "citations": [asdict(citation) for citation in result.citations],
            "trade_date": result.trade_date,
            "matched_theme": result.matched_theme,
        },
    )
    for warning in result.warnings:
        store.add_degrade(run_id, warning)
    if req.compose and not (result.llm_refined or result.synthesis):
        store.add_degrade(run_id, "llm_unavailable_template_answer")

    for module in ask_result_modules(result):
        emit_module(module)

    render_started_at = rs._now_iso()
    answer_md = render_answer(result)
    store.add_artifact(
        run_id,
        "answer.md",
        answer_md,
        renderer="markdown",
        title=f"研究回答：{req.question[:24]}",
    )
    summary = {
        "trade_date": result.trade_date,
        "matched_theme": result.matched_theme,
        "question_type": result.question_plan.question_type
        if result.question_plan
        else None,
        "citations": len(result.citations),
        "citation_counts": citation_counts,
        "citation_records": [asdict(citation) for citation in result.citations],
        "llm_refined": result.llm_refined,
        "llm_composed": bool(result.synthesis),
        "warnings": list(result.warnings),
    }
    store.add_artifact(
        run_id,
        "summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        renderer="json",
        title="结构化摘要",
    )
    coverage = _ask_answer_coverage(req.question, result, answer_md)
    report["answer_marker_coverage"] = coverage
    store.append_step(
        run_id,
        step_id="s01b",
        name="answer_marker_coverage",
        status="completed",
        input_summary=req.question,
        started_at=render_started_at,
        finished_at=rs._now_iso(),
        output_summary=json.dumps(coverage, ensure_ascii=False),
    )
    provider = detect_provider()
    complete_report(
        report,
        as_of=result.trade_date or report_date,
        warnings=[*report_warnings, *result.warnings],
        llm_provider=result.llm_provider,
        llm_model=provider.model if provider and result.llm_provider else None,
        # 刻意不传 answer_status：本轮只加观测，不动交付判定。
        # ⚠️ 这条路的 answer_status 一直是无条件 "complete"（complete_report
        # 在 answer_status 不在白名单时回落成 business_status 默认值），
        # 即「没有任何东西检查过答案，报告照报 complete」。coverage 现在能
        # 量出这个洞有多大，但要不要让它影响状态，等有分布数据再定。
    )
    store.add_artifact(
        run_id,
        "report.json",
        json.dumps(report, ensure_ascii=False, indent=2),
        renderer="structured_report",
        title="结构化流式报告",
    )
    store.append_stream_event(
        run_id,
        event_id="report:complete",
        event_type="report.complete",
        payload={"report": report},
    )
    store.append_step(
        run_id,
        step_id="s02",
        name="render_artifacts",
        status="completed",
        started_at=render_started_at,
        finished_at=rs._now_iso(),
        output_summary="answer.md + summary.json",
    )
    if _run_terminal(store, run_id):
        return

    followup_started_at = rs._now_iso()
    store.append_step(
        run_id,
        step_id="s03",
        name="foresight_followups",
        status="running",
        input_summary=req.question,
        started_at=followup_started_at,
    )
    try:
        followups = followups_svc.generate_followups(
            req.question,
            matched_theme=result.matched_theme,
            answer_excerpt=result.synthesis or answer_md,
            use_llm=req.task_type != "daily",
        )
        store.add_artifact(
            run_id,
            "followups.json",
            followups.to_json(),
            renderer="json",
            title="猜你想问",
        )
        if not followups.llm_used:
            store.add_degrade(run_id, "llm_unavailable_template_followups")
        store.append_step(
            run_id,
            step_id="s03",
            name="foresight_followups",
            status="completed",
            input_summary=req.question,
            started_at=followup_started_at,
            finished_at=rs._now_iso(),
            output_summary=f"追问 {len(followups.followups)} 条（{'LLM' if followups.llm_used else '模板'}）",
            warnings=list(followups.warnings),
        )
    except Exception as exc:  # noqa: BLE001
        store.append_step(
            run_id,
            step_id="s03",
            name="foresight_followups",
            status="failed",
            input_summary=req.question,
            started_at=followup_started_at,
            finished_at=rs._now_iso(),
            warnings=[f"{type(exc).__name__}: {exc}"],
        )

    if _run_terminal(store, run_id):
        return
    store.finish_run(run_id, rs.STATUS_COMPLETED)


def _pending_review_count(repo_root: Path) -> int:
    ledger = repo_root / "docs" / "learning" / "forecast-review-ledger"
    return sum(
        1
        for manifest in ledger.glob("20??-??-??.manifest.json")
        if not manifest.with_name(
            manifest.name.replace(".manifest.json", ".verdict.json")
        ).is_file()
    )


def _run_context(store: RunStore, run_id: str) -> dict[str, object]:
    run = store.load_run(run_id)
    trace = store.load_trace(run_id)
    source_labels = {
        "market": "盘面快照",
        "graph": "知识图谱",
        "wiki": "知识库检索",
    }
    citation_labels = {
        "S": "盘面证据",
        "G": "图谱证据",
        "R": "事实证据",
        "W": "语义检索",
        "L": "公告与互动证据",
        "M": "用户记忆",
        "V": "历史回检",
    }
    evidence: list[dict[str, object]] = []
    citation_counts: Counter[str] = Counter()
    seen_sources: set[str] = set()
    warnings: list[str] = []
    for step in trace:
        warnings.extend(str(warning) for warning in step.get("warnings", []))
        retrieval = step.get("retrieval")
        if not isinstance(retrieval, dict):
            continue
        for source in retrieval.get("sources", []):
            source_name = str(source)
            if source_name in seen_sources:
                continue
            seen_sources.add(source_name)
            evidence.append(
                {
                    "id": f"source:{source_name}",
                    "label": source_labels.get(source_name, source_name),
                    "kind": "source",
                    "classification": "fact_source",
                    "detail": "本次检索已命中",
                    "status": "hit",
                }
            )
        citation_records = retrieval.get("citations", [])
        if isinstance(citation_records, list):
            for citation in citation_records:
                if not isinstance(citation, dict):
                    continue
                tag = str(citation.get("tag") or "")
                source = str(citation.get("source") or "")
                if not tag or not source:
                    continue
                binding = [
                    f"chunk={citation.get('chunk_id')}"
                    if citation.get("chunk_id")
                    else "",
                    f"hash={str(citation.get('content_hash'))[:12]}"
                    if citation.get("content_hash")
                    else "",
                    f"index={str(citation.get('index_source_revision'))[:12]}"
                    if citation.get("index_source_revision")
                    else "",
                    f"freshness={citation.get('index_freshness')}"
                    if citation.get("index_freshness")
                    else "",
                ]
                evidence.append(
                    {
                        "id": f"citation-record:{tag}",
                        "label": f"[{tag}] {source}",
                        "kind": "citation_record",
                        "classification": "bound_evidence",
                        "detail": " · ".join(item for item in binding if item)
                        or str(citation.get("detail") or "已记录引用"),
                        "status": "hit",
                    }
                )
        counts = retrieval.get("citation_counts", {})
        if isinstance(counts, dict):
            citation_counts.update(
                {
                    str(tag): int(count)
                    for tag, count in counts.items()
                    if str(count).isdigit() or isinstance(count, int)
                }
            )
    for tag, count in sorted(citation_counts.items()):
        if tag in {"M", "V"}:
            continue
        evidence.append(
            {
                "id": f"citation:{tag}",
                "label": citation_labels.get(tag, f"{tag} 类证据"),
                "kind": "citation",
                "classification": "fact_or_context",
                "detail": f"{count} 条引用",
                "status": "hit",
            }
        )

    memory = []
    if citation_counts.get("M"):
        memory.append(
            {
                "label": "用户记忆命中",
                "detail": f"{citation_counts['M']} 条 M 类引用参与本次回答",
                "source": "run trace",
            }
        )
    review = []
    if citation_counts.get("V"):
        review.append(
            {
                "label": "历史回检命中",
                "detail": f"{citation_counts['V']} 条 V 类引用参与本次回答",
                "source": run.manifest_ref or "run trace",
            }
        )
    gaps = list(dict.fromkeys([*run.degrades, *warnings]))
    return {
        "evidence": evidence,
        "memory": memory,
        "review": review,
        "gaps": gaps,
        "warnings": list(dict.fromkeys(warnings)),
        "metadata": {
            "source_date": run.source_date,
            "duckdb_cutoff": run.duckdb_cutoff,
            "kb_commit": run.kb_commit,
            "kb_index_built_at": run.kb_index_built_at,
            "kb_index_freshness": run.kb_index_freshness,
            "manifest_ref": run.manifest_ref,
        },
    }


def _resume_conversation_run(
    supervisor: RunSupervisor,
    store: RunStore,
    run: rs.Run,
    repo_root: Path,
    *,
    llm_providers: tuple[LLMProvider, ...] = (),
) -> bool:
    if run.session_id is None:
        return False
    conversation_store = ConversationStore(user_id=store.user_id)
    messages = conversation_store.load_messages(run.session_id)
    user_message = next(
        (
            message
            for message in messages
            if message.run_id == run.run_id and message.role == "user"
        ),
        None,
    )
    assistant_message = next(
        (
            message
            for message in messages
            if message.run_id == run.run_id and message.role == "assistant"
        ),
        None,
    )
    if user_message is None or assistant_message is None:
        return False
    event_id_prefix = f"recovery:{len(store.load_stream_events(run.run_id)) + 1}:"
    supervisor.submit_conversation(
        store,
        run.run_id,
        repo_root=repo_root,
        conversation_store=conversation_store,
        conversation_id=run.session_id,
        assistant_message_id=assistant_message.message_id,
        query=user_message.content,
        skill_mode=user_message.skill_mode,
        selected_skill_ids=list(user_message.selected_skill_ids),
        perspective_mode=user_message.perspective_mode,
        selected_perspective_ids=list(user_message.selected_perspective_ids),
        event_id_prefix=event_id_prefix,
        llm_providers=llm_providers,
    )
    return True


def create_app(
    *,
    repo_root: Path | None = None,
    run_timeout_sec: float = _SSE_MAX_SECONDS,
    self_use_require_consecutive_trading_days: bool = False,
    llm_settings: SessionLLMSettings | None = None,
) -> FastAPI:
    root = (repo_root or REPO_ROOT).resolve()
    effective_default_user_id = userspace.resolve_user_id(None)
    runtime_provenance = build_runtime_provenance(root)
    runtime_paths = default_paths()
    runtime_provenance["finance_root"] = str(runtime_paths.finance_root.resolve())
    continuous_mode = _continuous_runtime_mode()
    runtime_provenance["continuous_agent"] = {
        "mode": continuous_mode,
        "canary_id": (
            os.environ.get("CONTINUOUS_RUNTIME_CANARY_ID", "").strip()
            if continuous_mode == "canary"
            else ""
        ),
        "source_revision": runtime_provenance.get("source_revision"),
    }
    llm_settings = llm_settings or SessionLLMSettings()
    runtime_selection = resolve_runtime_backend()
    runtime_provenance["agent_runtime"] = runtime_backend_readiness(
        runtime_selection
    ).to_dict()
    supervisor = RunSupervisor(timeout_sec=run_timeout_sec)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if kb_rag.rag_worker.enabled():
            try:
                kb_rag.prewarm(
                    runtime_paths.knowledge_wiki,
                    timeout=_positive_float_env(
                        "RAG_WORKER_PREWARM_TIMEOUT",
                        90.0,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - fail closed at readiness
                kb_rag.rag_worker.record_startup_failure(exc)
        try:
            yield
        finally:
            kb_rag.rag_worker.close_all()
            llm_settings.clear_all()
            supervisor.shutdown()

    app = FastAPI(title="Market Intelligence Workbench API", lifespan=lifespan)
    app.state.repo_root = root
    app.state.finance_root = runtime_paths.finance_root.resolve()
    registries: dict[str, ArtifactRegistry] = {}
    recovered_runs: list[str] = []
    conversation_locks: dict[tuple[str, str], Lock] = {}
    conversation_locks_guard = Lock()

    user_ids = {effective_default_user_id}
    users_root = userspace.users_dir()
    runtime_provenance["users_dir"] = str(users_root.resolve())
    if users_root.is_dir():
        user_ids.update(
            path.name
            for path in users_root.iterdir()
            if path.is_dir() and (path / "runs").is_dir()
        )
    for user_id in sorted(user_ids):
        try:
            store = RunStore(user_id=user_id)
            for run in store.requeue_incomplete_runs(reason=_RESTART_REASON):
                recovered_runs.append(run.run_id)
                try:
                    if _resume_conversation_run(
                        supervisor,
                        store,
                        run,
                        root,
                        llm_providers=llm_settings.runtime_providers_for(user_id),
                    ):
                        continue
                except (
                    FileNotFoundError,
                    ValueError,
                    json.JSONDecodeError,
                    ConversationDataIntegrityError,
                ):
                    pass
                supervisor.submit(
                    store,
                    run.run_id,
                    CreateRunRequest(
                        question=run.question,
                        user=run.user,
                        task_type=run.task_type,
                        session_id=run.session_id,
                        parent_run_id=run.parent_run_id,
                        repo_root=root,
                    ),
                )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    app.state.supervisor = supervisor
    app.state.recovered_runs = recovered_runs
    app.state.cancellation_registry = supervisor.cancellation_signals
    app.state.conversation_locks = conversation_locks
    app.state.conversation_locks_guard = conversation_locks_guard
    app.state.llm_settings = llm_settings

    def store_for(user: str | None) -> RunStore:
        return RunStore(user_id=user)

    def conversation_store_for(user: str | None) -> ConversationStore:
        return ConversationStore(user_id=store_for(user).user_id)

    def refresh_session_runtime_readiness(user_id: str) -> None:
        """Refresh global health metadata after the default user's config request.

        Keychain loading remains lazy: this helper is called only after a route
        has already resolved the user's provider. The projection contains only
        provider id/model and never the provider secret or endpoint.
        """

        if user_id != effective_default_user_id:
            return
        provider = llm_settings.byok_provider(user_id)
        runtime_provenance["agent_runtime"] = runtime_backend_readiness(
            runtime_selection,
            session_provider=provider.name if provider is not None else None,
            session_model=provider.model if provider is not None else None,
        ).to_dict()

    def self_use_projection(user: str | None) -> dict[str, object]:
        conversation_store = conversation_store_for(user)
        self_use_dir = conversation_store.root.parent / "self-use"
        ledger = SelfUseLedger(self_use_dir / "events.jsonl")
        trading_days = trading_days_from_duckdb(
            root / "db" / "market_feature_store.duckdb"
        )
        try:
            result = evaluate_maturity(
                ledger.load(),
                trading_days=trading_days,
                require_consecutive_trading_days=(
                    self_use_require_consecutive_trading_days
                ),
            )
        except (OSError, SelfUseLedgerIntegrityError) as exc:
            raise HTTPException(500, "自用成熟度台账不可读") from exc
        # passed 由持久化审批驱动：审批指纹须与当前裁决快照一致，否则失效。
        approvals = SelfUseApprovalStore(self_use_dir / "approval.json")
        passed = bool(
            result.eligible_for_user_decision and approvals.is_approved_for(result)
        )
        return {
            "distinct_trade_dates": result.metrics["distinct_trade_dates"],
            "success_rate": result.metrics["core_success_rate"],
            "useful_rate": result.metrics["useful_rate"],
            "manual_rescue_rate": result.metrics["manual_rescue_rate"],
            "covered_workflows": result.metrics["covered_workflows"],
            "blockers": list(result.blockers),
            "eligible_for_user_decision": result.eligible_for_user_decision,
            "passed": passed,
        }

    def conversation_lock_for(user: str | None, conversation_id: str) -> Lock:
        resolved_user_id = store_for(user).user_id
        key = (resolved_user_id, conversation_id)
        with conversation_locks_guard:
            lock = conversation_locks.get(key)
            if lock is None:
                lock = Lock()
                conversation_locks[key] = lock
            return lock

    def conversation_or_404(user: str | None, conversation_id: str):
        try:
            return conversation_store_for(user).load_conversation(conversation_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "conversation 不存在") from None

    def registry_for(user: str | None) -> ArtifactRegistry:
        store = store_for(user)
        registry = registries.get(store.user_id)
        if registry is None:
            registry = ArtifactRegistry(repo_root=root, run_store=store)
            registries[store.user_id] = registry
        return registry

    def dependency_checks() -> dict[str, bool]:
        return {
            "repo_root": root.is_dir(),
            "knowledge_wiki": runtime_paths.knowledge_wiki.is_dir(),
            "relations": (runtime_paths.knowledge_wiki / "relations").is_dir(),
            "vector_index": runtime_paths.vector_index_dir.is_dir(),
            # 索引目录在 ≠ 检索跑得起来。``vector_index`` 只判目录存在，而
            # kb_search 是 subprocess 拉起 ``KB_RAG_PYTHON`` 去跑 rag_index.py：
            # **解释器不可执行时索引目录照样在，health 照样全绿**。
            #
            # 2026-08-12 实测到这个缺口的代价：
            # ``knowledge-base-private/.rag_venv`` 是指向 ``~/知识库/.rag_venv``
            # 的符号链接，而那个目录已不存在（链接建于 07-14）。于是 kb_search
            # 每次都 7ms 抛 FileNotFoundError，被脱敏成「研究过程中出现内部错误」，
            # 历史 22 次调用 22 次空手（20 次 error/timeout）——**静默停摆约一个月，
            # 而 health 一直报 vector_index: true**。
            #
            # 这就是「契约体检」那条审查项本身长在仪表上的样子：
            # 广告的是「向量检索就绪」，交付的是「目录存在」。
            "rag_runtime": kb_rag.rag_runtime_ready(),
            "market_snapshot": runtime_paths.market_snapshot_dir.is_dir(),
            "frontend_built": (STATIC_DIR / "index.html").is_file(),
        }

    @app.get("/api/health")
    @app.get("/api/health/live")
    def health_live() -> dict[str, object]:
        checks = dependency_checks()
        return {
            "status": "healthy",
            "timestamp": rs._now_iso(),
            "dependencies": checks,
            "runtime": runtime_provenance,
        }

    @app.get("/api/readiness")
    @app.get("/api/health/ready")
    def health_ready(user: str | None = None) -> JSONResponse:
        store = store_for(user)
        rag_probe = kb_rag.probe_rag_cli(runtime_paths.knowledge_wiki)
        # 探针的写侧半步：发现死进程 worker 就按预热配方调度自愈（单飞+冷却）。
        # 查询失败式自愈覆盖不了「进程死了但后续查询全带 filters 走 CLI」的
        # 形状（2026-08-13 R23 注入实测），那时 readiness 会永久红。
        kb_rag.rag_worker.ensure_recovery()
        worker_status = kb_rag.rag_worker.status()
        snapshot_contract = validate_market_snapshot_root(
            runtime_paths.market_snapshot_dir
        )
        snapshot_date = str(
            snapshot_contract["summary"].get("served_trade_date")
            or snapshot_contract.get("date")
            or ""
        )[:10]
        market_database_date = latest_market_date(runtime_paths.finance_root)
        continuous_requires_market_consistency = continuous_mode in {
            "on",
            "canary",
        }
        market_data_consistent = (
            not continuous_requires_market_consistency
            or (
                bool(snapshot_contract["ready"])
                and bool(snapshot_date)
                and market_database_date is not None
                and market_database_date >= snapshot_date
            )
        )
        run_root_ready = False
        try:
            store.root.mkdir(parents=True, exist_ok=True)
            run_root_ready = store.root.is_dir() and os.access(store.root, os.W_OK)
        except OSError:
            pass
        checks = {
            **dependency_checks(),
            "rag_query_protocol": rag_probe.query_protocol_compatible,
            "rag_worker": (
                not worker_status["enabled"]
                or (
                    worker_status["state"] == "ready"
                    and int(worker_status["active"]) >= 1
                )
            ),
            "run_store_writable": run_root_ready,
            "market_snapshot_contract": bool(snapshot_contract["ready"]),
            "market_data_consistency": market_data_consistent,
            # 加载树与仓库树是否一致。`is not False` 而不是 `is True`：三态里的
            # None 表示「无仓库树可比」（纯快照部署），那是未知而非不一致。
            #
            # 刻意**不进** `critical`：本项为真正的漂移报警，但它也会在「仓库里
            # 有人正改着 intelligence/ 而生产快照是先前冻结的正确副本」时为假。
            # 让那种情形把生产判成 not_ready，等于用一次无关的编辑换一次自伤。
            # 真正的闸门放在 `scripts/deploy_workbench_runtime.sh`：那里 rsync 之后
            # 两棵树按构造必然一致，不一致就是部署真的失败了，此时报错才可行动。
            "code_snapshot_matches_repo": (
                runtime_provenance.get("code_matches_repo") is not False
            ),
        }
        critical = {
            "repo_root": checks["repo_root"],
            "run_store_writable": checks["run_store_writable"],
            "knowledge_wiki": checks["knowledge_wiki"],
            "relations": checks["relations"],
            "vector_index": checks["vector_index"],
            "rag_query_protocol": checks["rag_query_protocol"],
            "rag_worker": checks["rag_worker"],
            "market_snapshot": checks["market_snapshot_contract"],
            "market_data_consistency": checks["market_data_consistency"],
        }
        ready = all(critical.values())
        payload = {
            "status": "ready" if ready else "not_ready",
            "timestamp": rs._now_iso(),
            "checks": checks,
            "critical": critical,
            "missing_critical": [
                name for name, available in critical.items() if not available
            ],
            "rag": rag_probe.to_dict(),
            "market_snapshot": {
                "status": snapshot_contract["status"],
                "ready": snapshot_contract["ready"],
                "date": snapshot_contract["summary"].get("served_trade_date")
                or snapshot_contract["date"],
                "requested_date": snapshot_contract["summary"].get(
                    "requested_trade_date"
                ),
                "provider": snapshot_contract["summary"].get("provider"),
                "source": snapshot_contract["summary"].get("source"),
                "summary": snapshot_contract["summary"],
                "errors": snapshot_contract["errors"],
                "warnings": snapshot_contract["warnings"],
            },
            "market_database": {
                "date": market_database_date,
                "snapshot_date": snapshot_date or None,
                "consistent_with_snapshot": market_data_consistent,
                "required_by_continuous_runtime": (
                    continuous_requires_market_consistency
                ),
            },
            "workers": {
                "active": supervisor.active_count(),
                "capacity": supervisor.max_workers,
                "timeout_sec": supervisor.timeout_sec,
                "rag": worker_status,
            },
            "recovered_runs": len(recovered_runs),
        }
        return JSONResponse(payload, status_code=200 if ready else 503)

    @app.post("/api/runs")
    def create_run(req: CreateRunRequest) -> dict[str, object]:
        req.repo_root = root
        store = store_for(req.user)
        run = store.create_run(
            req.question,
            req.task_type,
            session_id=req.session_id,
            parent_run_id=req.parent_run_id,
        )
        supervisor.submit(store, run.run_id, req)
        return {"run_id": run.run_id, "status": run.status}

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str, user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        try:
            run = store.load_run(run_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        if run.status not in (
            rs.STATUS_COMPLETED,
            rs.STATUS_FAILED,
            rs.STATUS_CANCELLED,
        ):
            supervisor.cancel(store, run_id)
            run = store.load_run(run_id)
        return {
            "run_id": run.run_id,
            "status": run.status,
            "cancel_requested": True,
        }

    @app.post("/api/conversations")
    def create_conversation(req: CreateConversationRequest) -> dict[str, object]:
        try:
            return asdict(
                conversation_store_for(req.user).create_conversation(req.title)
            )
        except ValueError as exc:
            raise HTTPException(422, "invalid user") from exc

    @app.get("/api/conversations")
    def list_conversations(user: str | None = None) -> list[dict[str, object]]:
        try:
            return [
                asdict(item)
                for item in conversation_store_for(user).list_conversations()
            ]
        except ValueError as exc:
            raise HTTPException(422, "invalid user") from exc

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(
        conversation_id: str, user: str | None = None
    ) -> dict[str, object]:
        return asdict(conversation_or_404(user, conversation_id))

    @app.patch("/api/conversations/{conversation_id}")
    def update_conversation(
        conversation_id: str, req: UpdateConversationRequest
    ) -> dict[str, object]:
        with conversation_lock_for(req.user, conversation_id):
            conversation_or_404(req.user, conversation_id)
            return asdict(
                conversation_store_for(req.user).rename_conversation(
                    conversation_id, req.title
                )
            )

    @app.post("/api/conversations/{conversation_id}/archive")
    def archive_conversation(
        conversation_id: str, req: UserRequest
    ) -> dict[str, object]:
        with conversation_lock_for(req.user, conversation_id):
            conversation_or_404(req.user, conversation_id)
            return asdict(
                conversation_store_for(req.user).archive_conversation(conversation_id)
            )

    @app.get("/api/conversations/{conversation_id}/messages")
    def list_messages(
        conversation_id: str, user: str | None = None
    ) -> list[dict[str, object]]:
        conversation_or_404(user, conversation_id)
        return [
            _public_message_payload(item)
            for item in conversation_store_for(user).load_messages(conversation_id)
        ]

    @app.get("/api/llm/config")
    def get_llm_config(user: str | None = None) -> dict[str, object]:
        user_id = store_for(user).user_id
        description = llm_settings.describe(user_id)
        refresh_session_runtime_readiness(user_id)
        return description

    @app.put("/api/llm/config")
    def configure_llm(req: ConfigureLLMRequest) -> dict[str, object]:
        user_id = store_for(req.user).user_id
        api_key = req.api_key.get_secret_value().strip()
        if not 8 <= len(api_key) <= 4096:
            raise HTTPException(422, "invalid api key")
        try:
            llm_settings.configure_byok(
                user_id,
                provider_id=req.provider,
                api_key=api_key,
                base_url=req.base_url,
                model=req.model,
                persist=req.remember,
            )
        except ValueError as exc:
            raise HTTPException(422, "invalid provider base URL") from exc
        except KeychainCredentialError as exc:
            raise HTTPException(503, "无法安全保存模型密钥，请关闭记住选项后重试") from exc
        description = llm_settings.describe(user_id)
        refresh_session_runtime_readiness(user_id)
        return description

    @app.delete("/api/llm/config")
    def use_built_in_llm(user: str | None = None) -> dict[str, object]:
        user_id = store_for(user).user_id
        llm_settings.clear_byok(user_id)
        description = llm_settings.describe(user_id)
        refresh_session_runtime_readiness(user_id)
        return description

    @app.delete("/api/llm/config/saved")
    def forget_saved_llm(user: str | None = None) -> dict[str, object]:
        user_id = store_for(user).user_id
        try:
            llm_settings.forget_saved_byok(user_id)
        except KeychainCredentialError as exc:
            raise HTTPException(503, "无法删除已保存的模型密钥") from exc
        description = llm_settings.describe(user_id)
        refresh_session_runtime_readiness(user_id)
        return description

    @app.post("/api/conversations/{conversation_id}/messages", status_code=202)
    def create_message(
        conversation_id: str, req: CreateMessageRequest
    ) -> dict[str, str]:
        with conversation_lock_for(req.user, conversation_id):
            conversation = conversation_or_404(req.user, conversation_id)
            unknown_skills = [
                skill_id
                for skill_id in dict.fromkeys(req.selected_skill_ids)
                if skill_id not in SKILL_REGISTRY
            ]
            if unknown_skills:
                raise HTTPException(422, "unknown product skill")
            if len(dict.fromkeys(req.selected_skill_ids)) > 3:
                raise HTTPException(422, "at most 3 product skills may be selected")
            try:
                selected_perspective_ids = perspective_lab.validate_runtime_selection(
                    userspace.user_space(conversation.user_id),
                    req.perspective_mode,
                    req.selected_perspective_ids,
                )
            except (ValueError, FileNotFoundError) as exc:
                raise HTTPException(422, str(exc)) from exc
            parent_run_id = conversation.last_run_id
            run_store = store_for(req.user)
            run = run_store.create_run(
                req.content,
                "ask",
                session_id=conversation_id,
                parent_run_id=parent_run_id,
            )
            try:
                store = conversation_store_for(req.user)
                user_message = store.append_message(
                    conversation_id,
                    "user",
                    req.content,
                    run_id=run.run_id,
                    skill_mode=req.skill_mode,
                    selected_skill_ids=req.selected_skill_ids,
                    perspective_mode=req.perspective_mode,
                    selected_perspective_ids=list(selected_perspective_ids),
                )
                assistant_message = store.append_message(
                    conversation_id,
                    "assistant",
                    "",
                    status="pending",
                    run_id=run.run_id,
                    perspective_mode=req.perspective_mode,
                    selected_perspective_ids=list(selected_perspective_ids),
                )
                current = store.load_conversation(conversation_id)
                store.update_summary(
                    conversation_id, current.summary, last_run_id=run.run_id
                )
                supervisor.submit_conversation(
                    run_store,
                    run.run_id,
                    repo_root=root,
                    conversation_store=store,
                    conversation_id=conversation_id,
                    assistant_message_id=assistant_message.message_id,
                    query=req.content,
                    skill_mode=req.skill_mode,
                    selected_skill_ids=list(req.selected_skill_ids),
                    perspective_mode=req.perspective_mode,
                    selected_perspective_ids=list(selected_perspective_ids),
                    llm_providers=llm_settings.runtime_providers_for(run_store.user_id),
                )
            except Exception:
                try:
                    run_store.finish_run(
                        run.run_id,
                        rs.STATUS_FAILED,
                        error="message persistence or submission failed",
                    )
                except Exception as compensation_exc:
                    raise RuntimeError(
                        "failed to persist run failure state"
                    ) from compensation_exc
                raise
            return {
                "conversation_id": conversation_id,
                "user_message_id": user_message.message_id,
                "assistant_message_id": assistant_message.message_id,
                "run_id": run.run_id,
            }

    @app.get("/api/skills")
    def list_skills() -> list[dict[str, object]]:
        try:
            registry = import_module("intelligence.workbench_skills.registry")
        except ModuleNotFoundError as exc:
            if exc.name in {
                "intelligence.workbench_skills",
                "intelligence.workbench_skills.registry",
            }:
                return []
            raise
        return [asdict(skill) for skill in registry.SKILL_REGISTRY.values()]

    @app.get("/api/perspectives")
    def list_perspectives(user: str | None = None) -> list[dict[str, object]]:
        user_id = store_for(user).user_id
        return perspective_lab.list_profiles(userspace.user_space(user_id))

    @app.get("/api/runs")
    def list_runs(user: str | None = None) -> list[dict[str, object]]:
        return [
            _public_run_payload(run) for run in reversed(store_for(user).list_runs())
        ]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, user: str | None = None) -> dict[str, object]:
        try:
            return _public_run_payload(store_for(user).load_run(run_id))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/trace")
    def get_trace(run_id: str, user: str | None = None) -> list[dict[str, object]]:
        store = store_for(user)
        try:
            if not store.run_path(run_id).exists():
                raise HTTPException(404, f"run 不存在：{run_id}")
            return [_public_trace_step(step) for step in store.load_trace(run_id)]
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/context")
    def get_run_context(run_id: str, user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        try:
            return _run_context(store, run_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/followups")
    def get_followups(run_id: str, user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        try:
            path = store.run_dir(run_id) / "followups.json"
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        if not path.is_file():
            return {"followups": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"followups": []}

    @app.get("/api/runs/{run_id}/events")
    def run_events(
        run_id: str,
        request: Request,
        user: str | None = None,
        after: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        store = store_for(user)
        try:
            if not store.run_path(run_id).exists():
                raise HTTPException(404, f"run 不存在：{run_id}")
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

        last_event_id = request.headers.get("last-event-id", "")
        cursor = after
        if cursor == 0 and last_event_id:
            if last_event_id.isdigit():
                cursor = int(last_event_id)
            else:
                cursor = next(
                    (
                        event["seq"]
                        for event in store.load_stream_events(run_id)
                        if event["event_id"] == last_event_id
                    ),
                    0,
                )

        def stream():
            current_cursor = cursor
            deadline = time.monotonic() + _SSE_MAX_SECONDS
            terminal_event_deadline: float | None = None
            while True:
                report_events = store.load_stream_events(run_id, after=current_cursor)
                for event in report_events:
                    current_cursor = event["seq"]
                    if event["event_type"] not in PUBLIC_EVENT_TYPES:
                        continue
                    public_event = _public_stream_event(event)
                    data = json.dumps(public_event, ensure_ascii=False)
                    yield (
                        f"id: {public_event['event_id']}\n"
                        f"event: {public_event['event_type']}\n"
                        f"data: {data}\n\n"
                    )
                run = store.load_run(run_id)
                if run.status in (
                    rs.STATUS_COMPLETED,
                    rs.STATUS_FAILED,
                    rs.STATUS_CANCELLED,
                ):
                    terminal_message_missing = run.session_id and not any(
                        event["event_type"] in {"message.complete", "message.error"}
                        for event in store.load_stream_events(run_id)
                    )
                    if terminal_message_missing:
                        terminal_event_deadline = (
                            terminal_event_deadline
                            or time.monotonic() + 2 * _SSE_POLL_SECONDS
                        )
                    if (
                        terminal_message_missing
                        and time.monotonic() < terminal_event_deadline
                    ):
                        time.sleep(_SSE_POLL_SECONDS)
                        continue
                    yield (
                        "event: run\n"
                        f"data: {json.dumps(_public_run_payload(run), ensure_ascii=False)}\n\n"
                    )
                    return
                if time.monotonic() > deadline:
                    yield "event: timeout\ndata: {}\n\n"
                    return
                time.sleep(_SSE_POLL_SECONDS)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/runs/{run_id}/report")
    def get_run_report(
        run_id: str, user: str | None = None
    ) -> dict[str, object] | None:
        store = store_for(user)
        try:
            run_dir = store.run_dir(run_id)
            if not store.run_path(run_id).exists():
                raise HTTPException(404, f"run 不存在：{run_id}")
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        report_path = run_dir / "report.json"
        if report_path.is_file():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        report: dict[str, object] | None = None
        for event in store.load_stream_events(run_id):
            payload = event.get("payload", {})
            if event.get("event_type") in {
                "report.start",
                "report.complete",
                "report.error",
            }:
                candidate = payload.get("report") if isinstance(payload, dict) else None
                if isinstance(candidate, dict):
                    report = candidate
            elif event.get("event_type") == "report.module" and report is not None:
                module = payload.get("module") if isinstance(payload, dict) else None
                if isinstance(module, dict):
                    upsert_report_module(report, module)
        return report

    @app.get("/api/runs/{run_id}/artifacts/{name:path}")
    def get_run_artifact(
        run_id: str, name: str, user: str | None = None
    ) -> FileResponse:
        store = store_for(user)
        try:
            run = store.load_run(run_id)
            run_dir = store.run_dir(run_id).resolve()
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        artifact = next(
            (
                item
                for item in run.artifacts
                if item.get("path") == name
                and rs.artifact_visibility(item) == "public"
                and item.get("downloadable", True) is True
            ),
            None,
        )
        if artifact is None:
            raise HTTPException(404, f"产物不存在：{name}")
        path = (run_dir / str(artifact["path"])).resolve()
        try:
            path.relative_to(run_dir)
        except ValueError as exc:
            raise HTTPException(404, f"产物不存在：{name}") from exc
        if not path.is_file():
            raise HTTPException(404, f"产物不存在：{name}")
        return FileResponse(path)

    @app.get("/api/artifacts")
    def list_artifacts(
        category: str | None = None,
        date: str | None = None,
        status: str | None = None,
        query: str | None = Query(default=None, alias="q"),
        user: str | None = None,
    ) -> list[dict[str, object]]:
        return [
            descriptor.public_dict()
            for descriptor in registry_for(user).list(
                category=category,
                date=date,
                status=status,
                query=query,
            )
        ]

    @app.get("/api/artifacts/{artifact_id}/content")
    def get_artifact_content(artifact_id: str, user: str | None = None) -> FileResponse:
        try:
            descriptor, path = registry_for(user).content_path(artifact_id)
        except KeyError as exc:
            raise HTTPException(404, f"产物未注册：{artifact_id}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, f"产物文件不存在：{artifact_id}") from exc
        except PermissionError as exc:
            raise HTTPException(403, "产物路径不在允许目录") from exc
        headers = {}
        if descriptor.viewer == "legacy_html":
            headers["Content-Security-Policy"] = (
                "sandbox allow-scripts; default-src 'self' data: blob: https:; "
                "style-src 'self' 'unsafe-inline' https:; "
                "script-src 'self' 'unsafe-inline' https:; img-src 'self' data: blob: https:"
            )
        return FileResponse(path, headers=headers)

    @app.get("/api/artifacts/{artifact_id}/projection")
    def get_artifact_projection(
        artifact_id: str, user: str | None = None
    ) -> dict[str, object]:
        registry = registry_for(user)
        descriptor = registry.get(artifact_id)
        if descriptor is None:
            raise HTTPException(404, f"产物未注册：{artifact_id}")
        if descriptor.category not in {"daily_agent", "daily_review"}:
            raise HTTPException(404, "该产物不支持原生投影")
        if descriptor.category == "daily_review" and not Path(
            descriptor.source_path
        ).name.endswith(("-daily-review.html", "-daily-review.md")):
            raise HTTPException(404, "该产物不支持原生投影")

        original = next(
            (
                item
                for item in registry.list(
                    category=descriptor.category,
                    date=descriptor.date,
                )
                if item.viewer == "legacy_html" and item.status != "missing"
            ),
            None,
        )
        try:
            if descriptor.category == "daily_agent":
                _, source = registry.canonical_path(artifact_id)
                payload = json.loads(source.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Daily Agent canonical JSON 必须是对象")
                projection = project_daily_agent(
                    payload,
                    source_path=source.relative_to(root).as_posix(),
                )
            else:
                try:
                    _, source = registry.canonical_path(artifact_id)
                except FileNotFoundError:
                    _, source = registry.content_path(artifact_id)
                source_path = source.relative_to(root).as_posix()
                if source.suffix.lower() == ".md":
                    projection = project_daily_review_markdown(
                        source.read_text(encoding="utf-8"),
                        source_path=source_path,
                        date=descriptor.date,
                    )
                elif source.suffix.lower() == ".html":
                    projection = project_daily_review_html(
                        source.read_text(encoding="utf-8"),
                        source_path=source_path,
                        date=descriptor.date,
                    )
                else:
                    raise ValueError("Daily Review 需要 canonical Markdown 或历史 HTML")
        except KeyError as exc:
            raise HTTPException(404, f"产物未注册：{artifact_id}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, "原生投影来源不存在") from exc
        except PermissionError as exc:
            raise HTTPException(403, "投影来源路径不在允许目录") from exc
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(422, f"无法生成原生投影：{exc}") from exc

        provenance = projection.get("provenance")
        if isinstance(provenance, dict) and original is not None:
            provenance["rendered_path"] = original.source_path
            provenance["original_report_available"] = True
            provenance["original_artifact_id"] = original.artifact_id
        return projection

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact_descriptor(
        artifact_id: str, user: str | None = None
    ) -> dict[str, object]:
        descriptor = registry_for(user).get(artifact_id)
        if descriptor is None:
            raise HTTPException(404, f"产物未注册：{artifact_id}")
        return descriptor.public_dict()

    @app.get("/api/artifacts/{artifact_id}/{asset_path:path}")
    def get_artifact_asset(
        artifact_id: str, asset_path: str, user: str | None = None
    ) -> FileResponse:
        try:
            _, path = registry_for(user).asset_path(artifact_id, asset_path)
        except KeyError as exc:
            raise HTTPException(404, f"产物未注册：{artifact_id}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, f"配套资源不存在：{asset_path}") from exc
        except PermissionError as exc:
            raise HTTPException(403, "配套资源路径不在产物目录内") from exc
        return FileResponse(path)

    @app.get("/api/workbench/bootstrap")
    def workbench_bootstrap(user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        runs = list(reversed(store.list_runs()))[:20]
        artifacts = registry_for(user).list()
        latest_daily = next(
            (
                artifact
                for artifact in artifacts
                if artifact.category
                in {"daily_review", "daily_agent", "theme_candidates"}
                and artifact.status != "missing"
            ),
            None,
        )
        data_cutoff = (
            latest_daily.date
            if latest_daily
            else next(
                (run.source_date for run in runs if run.source_date),
                None,
            )
        )
        workflows = [
            {
                "id": "daily",
                "title": "今日复盘",
                "description": "调用 GLM 综合证据，并流式生成日报与 L2 资金流模块",
                "task_type": "daily",
                "artifact_id": latest_daily.artifact_id if latest_daily else None,
                "prompt": "基于最新收盘数据，总结今日盘面、主线、反证和下一交易日验证点。",
            },
            {
                "id": "theme",
                "title": "题材深挖",
                "description": "从产业链、证据与盘面阶段拆解题材",
                "task_type": "theme",
                "artifact_id": None,
                "prompt": "请深挖这个题材的产业链、核心矛盾、证据分层、反证和后续验证信号：",
            },
            {
                "id": "stock_research",
                "title": "个股研究",
                "description": "核对公司角色、兑现路径与风险",
                "task_type": "stock_research",
                "artifact_id": None,
                "prompt": "请研究这只股票的业务角色、受益链条、当前证据、反证和可验证节点：",
            },
        ]
        return {
            "user": store.user_id,
            "workflows": workflows,
            "recent_runs": [_public_run_payload(run) for run in runs],
            "latest_artifacts": [artifact.public_dict() for artifact in artifacts[:10]],
            "latest_daily_artifact": latest_daily.public_dict()
            if latest_daily
            else None,
            "pending_review_count": _pending_review_count(root),
            "needs_human_action": sum(
                1 for artifact in artifacts if artifact.status in {"warn", "missing"}
            ),
            "data_cutoff": data_cutoff,
            "self_use_maturity": self_use_projection(user),
        }

    @app.get("/api/workbench/overview")
    def workbench_overview() -> dict[str, object]:
        return build_workbench_overview(
            runtime_paths.finance_root,
            runtime_paths.knowledge_wiki,
        )

    learning_root = root / "docs" / "learning" / "forecast-lessons"

    @app.get("/api/workbench/learning-feedback")
    def workbench_learning_feedback() -> dict[str, object]:
        return learning_feedback_projection(learning_root)

    @app.post("/api/workbench/learning-feedback/reflections/{filename}/approve")
    def approve_learning_reflection(
        filename: str,
        req: ApproveReflectionRequest,
    ) -> dict[str, object]:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise HTTPException(400, "invalid reflection filename")
        reflection = learning_root / "reflections" / filename
        if not reflection.is_file():
            raise HTTPException(404, "reflection not found")
        try:
            approve_reflection(
                reflection,
                learning_root / "lessons.jsonl",
                hypothesis_ids=req.hypothesis_ids,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return learning_feedback_projection(learning_root)

    @app.post("/api/workbench/learning-feedback/reflections/{filename}/reject")
    def reject_learning_reflection(
        filename: str,
        req: ApproveReflectionRequest,
    ) -> dict[str, object]:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise HTTPException(400, "invalid reflection filename")
        reflection = learning_root / "reflections" / filename
        if not reflection.is_file():
            raise HTTPException(404, "reflection not found")
        try:
            reject_reflection(reflection, hypothesis_ids=req.hypothesis_ids)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return learning_feedback_projection(learning_root)

    @app.post("/api/workbench/learning-feedback/rules/{candidate_id}/status")
    def update_learning_rule(
        candidate_id: str,
        req: RuleStatusRequest,
    ) -> dict[str, object]:
        try:
            set_rule_status(
                learning_root / "rule_candidates.jsonl",
                candidate_id,
                req.status,
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return learning_feedback_projection(learning_root)

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        if not (STATIC_DIR / "index.html").is_file():
            raise HTTPException(503, "Workbench 前端尚未构建")
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
