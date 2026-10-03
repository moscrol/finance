"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import hashlib
import json
import os
import re
from threading import Lock, RLock
from time import monotonic

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    EpisodeStatus,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
    is_transient_model_error,
)
from intelligence.runtime.episode_finalizer import (
    MIN_FINALIZATION_RECOVERY_SECONDS,
    EpisodeFinalizer,
)
from intelligence.services.adaptive_research import (
    needs_perspective_checkpoint,
    perspective_checkpoint_message,
)
from intelligence.services.derived_calculation import bind_derived_calculation_tool
from intelligence.services.evidence_ledger import EvidenceLedger, EvidenceLedgerSnapshot
from intelligence.services.evidence_read import (
    EvidenceReadCoverage, bind_evidence_read_tool, evidence_read_enabled,
)
from intelligence.services.episode_protocol import (
    SYSTEM_PROMPT_DYNAMIC_BOUNDARY,
    finish_rejection_fields,
)
from intelligence.runtime.episode_tool_batch import (
    DispatchIntent,
    EpisodeToolBatchSession,
    ToolBatchExecutor,
    ToolBatchResult,
    ToolCallResult,
    batch_call_cap,
    time_gate_error_for_model,
    timeout_detail_for_model,
    tool_definitions_for_menu,
)
from intelligence.services.research_reasoning import observation_guidance
from intelligence.services.prior_evidence import remap_evidence_bindings
from intelligence.runtime.research_progress import (
    ResearchProgressTracker,
    ToolCallDigest,
    progress_enabled,
)
from intelligence.runtime.tier_promotion import apply_mode_promotion
from intelligence.services.episode_history_compaction import (
    compact_history,
    history_compaction_enabled,
    history_keep_batches,
)
from intelligence.services.material_grounding import claim_finish_format
from intelligence.services.mode_governor import ModeDecision
from intelligence.services.provider_observability import (
    ProviderTrace,
    provider_trace_tool_name,
)
from intelligence.services import llm_refine
from intelligence.services.llm_http_transport import host_suspended_since, host_suspended_total
from intelligence.services.material_delivery import (
    material_pack_turn_seconds,
    material_pack_writer_model,
)
from intelligence.services.provider_latency import (
    provider_name_from,
    repair_seconds_cap_for,
)
from intelligence.services.repair_coordinator import BudgetGrant, RepairGoal
from intelligence.services.research_contract import (
    PRODUCT_MAX_TOOL_CALLS,
    InMemoryRootBudgetLedger,
    ResearchDeadline,
    ResearchRunContext,
)
from intelligence.services.research_plan import (
    PlanParseResult,
    ResearchPlan,
    plan_to_public_dict,
)
from intelligence.services.cancel_signal import CancelSignal
from intelligence.services.episode_event_lanes import LiveEventSink
from intelligence.services.episode_inbox import (
    Inbox,
    InboxReceipt,
    InboxTarget,
    spool_dir_for,
)
from intelligence.services.episode_messages import (
    PROMPT_SOURCE_FINALIZER,
    EpisodeMessage,
    append_model_input,
    assistant_message,
    check_derivation,
    record_application_tool_call,
    record_prompt_assembled,
    record_tool_budget_state,
    rewrite_last_tool_content,
    system_message,
    to_provider,
    tool_message,
    unreported_invalid_finish,
    user_message,
)
from intelligence.services.episode_restore import RestoreResult, RestoreUnavailable, restore_episode
from intelligence.services.episode_authorization import capture_authorization_snapshot
from intelligence.services.episode_entry_identity import capture_entry_identity
from intelligence.services.episode_evidence import capture_evidence_snapshot
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.episode_store import (
    EPISODE_LOG_VERSION,
    INTENT_KINDS,
    EpisodePhase,
    EpisodeState,
    EpisodeStore,
    EpisodeWriterBusy,
    FencedEpisodeStore,
    episode_writer,
    now_iso,
)
from intelligence.services.research_harness import (
    FinanceResearchHarness,
    FinishAdmission,
    ModeGovernance,
    ResearchHarness,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
)
from intelligence.runtime.repair_budget import grant_for_transient_model_retry
from intelligence.runtime.sub_research_tool import (
    bind_sub_research_tool,
    branch_telemetry,
)
from intelligence.runtime.sub_research import (
    BranchRun,
    SubResearchCoordinator,
    SubResearchResult,
)
from intelligence.services.task_frame import TaskFrame


DEFAULT_LLM_TIMEOUT = 20.0
MIN_PLANNING_TURN_SECONDS = 8.0
# 一次最终合成至少需要的秒数。首轮可以向 ``synthesis_reserve`` **借**超出这个
# 地板的部分（见 ``_opening_planning_timeout``）：reserve 的正当用途是保证
# "已查到的证据"还能被合成，但首轮一条证据都没有，保护对象不存在。地板取
# ``EpisodeFinalizer`` 的默认超时（20s），即"够跑一次合成"的口径——借走的只是
# reserve 里超出一次合成所需的余量，不是整段。
MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS = 20.0
# 修复轮瞬态错误的补救次数上限（repair / repair_finalize 两跳共用）。
# 2026-08-13 收据（86 个带修复 episode）：首发超时后换新调用救回率 61%
# （17/28），连环 stall 11/28——第二发 retry 预计再救回约六成连环 stall。
# 每发仍是 ≤30s 满窗、从 root hard-cap 未分配余量铸造，余量不足自然 fail
# closed，所以上限 2 只在「前两发都 stall 且余量还在」时才多花一笔。
# 同批取证证伪了「升窗到 45/60s」：成功修复调用 n=66 的 max=27.8s，
# 慢的是挂死型 stall（主路径 75s 窗也 12% 超时），等更久不如换新调用。
_TRANSIENT_RETRY_LIMIT = 2


def budget_status_enabled() -> bool:
    """Whether each planning turn is told how much wall-clock budget is left.

    Bookgap S1 turns this **on by default** so the model sees time remaining
    in the same ``runtime_budget`` payload as tool-call remaining.  Set
    ``ASK_EPISODE_BUDGET_STATUS=off`` to fuse it off.  The finish event
    records ``time_budget_injected`` so eval can tell the arms apart.
    """

    raw = str(os.environ.get("ASK_EPISODE_BUDGET_STATUS") or "").strip().lower()
    return raw not in {"off", "0", "false", "no"}
# Planning is model-owned state, but it must still have a finite allowance so
# a model cannot keep revising a plan forever without reaching research or
# finalization.  The allowance is separate from max_steps, which is the
# finance-tool budget.
MAX_PLAN_TURNS = 2
# The loop must be able to represent the largest governed mode without giving
# quick runs that budget. Actual execution remains bounded by the current root
# ledger and deadline. Pinned to the product cap so a ``max`` tier ledger is
# not silently clipped here to the old deep number.
MAX_EPISODE_TOOL_CALLS = PRODUCT_MAX_TOOL_CALLS


def _token_usage_from_events(
    events: list[EpisodeEvent] | tuple[EpisodeEvent, ...],
) -> tuple[int | None, int | None]:
    input_total = 0
    output_total = 0
    input_observed = False
    output_observed = False
    for event in events:
        if event.kind not in {"model_turn", "branch_completed", "branch_failed"}:
            continue
        input_value = event.payload.get("input_tokens")
        output_value = event.payload.get("output_tokens")
        if isinstance(input_value, int) and not isinstance(input_value, bool):
            input_total += max(0, input_value)
            input_observed = True
        if isinstance(output_value, int) and not isinstance(output_value, bool):
            output_total += max(0, output_value)
            output_observed = True
    return (
        input_total if input_observed else None,
        output_total if output_observed else None,
    )


def _agent_usage(
    ledger: "_EpisodeLedger",
    *,
    llm_calls: int,
    tool_calls: int,
    invalid_actions: int,
) -> AgentUsage:
    input_tokens, output_tokens = _token_usage_from_events(ledger.events)
    return AgentUsage(
        llm_calls=llm_calls,
        tool_calls=tool_calls,
        invalid_actions=invalid_actions,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _tool_branch_usage(events: Sequence[EpisodeEvent]) -> tuple[int, int]:
    """Count newly settled branches, never telemetry re-served from query cache.

    PLAN branches settle separately. A result beyond the parent delivery window
    has no terminal branch event here and remains uncertain, not a known zero.
    """
    settlements = [e for e in events if e.kind in {"branch_completed", "branch_failed"}
                   and e.payload.get("origin") == "tool"]
    return (
        sum(int(e.payload.get("llm_calls") or 0) for e in settlements),
        sum(int(e.payload.get("tool_calls") or 0) for e in settlements),
    )


def _consume_root_seconds(context: ResearchRunContext, seconds: float) -> bool:
    ledger = context.root_budget
    if ledger is None:
        return True
    try:
        ledger.consume_seconds(seconds=max(0.0, float(seconds)))
    except ValueError:
        return False
    return True


def _settle_batch_calls(
    root_budget: object,
    *,
    executed_count: int,
    batch_elapsed: float,
) -> None:
    """Settle a finished tool batch against the root ledger without raising.

    结算已经发生的工作不能 fail closed——工具批次执行完才记账，此刻抛
    ``ValueError`` 撤不回任何东西，只会把整个 run 炸成硬失败。生产实测
    （2026-08-13 R13-A3）：首个模型轮耗时 ~30s 把 root 秒账本烧到只剩零头，
    工具批次执行完 ``consume_call`` 抛 "root seconds budget exhausted"，
    异常逃出 episode 主循环，run 直接 failed——没有 stopped_outcome、没有
    修复轮、冷启动也够不着（adapter 拿到的是异常不是 AgentOutcome）。

    秒账本烧穿时降级为 ``consume_call_slot`` + ``settle_seconds``：已执行的调用
    仍扣槽，时间能扣多少扣多少，不因超时退款；次数已空则不再扣成负数。
    call 槽位随 ``remaining_calls`` 归零自然反映到 ``_remaining_tool_slots``，
    下一轮进入 ``tool_budget_exhausted`` finalization，模型还能带着
    已取得的证据交卷。这与 #297 在重试闸门确立的原则同源：
    **纠正/结算层自己不能成为新的失败源**。
    """

    if root_budget is None or executed_count <= 0:
        return
    seconds_per_call = max(batch_elapsed / executed_count, 1e-6)
    for _ in range(executed_count):
        try:
            root_budget.consume_call(seconds=seconds_per_call)
        except ValueError:
            # consume_call rejected both debits. Time overrun does not refund
            # an already executed call (including a child's parent call slot).
            consume_slot = getattr(root_budget, "consume_call_slot", None)
            if callable(consume_slot):
                try:
                    consume_slot()
                except ValueError:
                    pass  # no slots remain; never invent a negative balance
            root_budget.settle_seconds(seconds=seconds_per_call)


def _wall_clock_after(seconds: float) -> str:
    """把 ``ResearchDeadline`` 的单调钟余量换成恢复时能读的挂钟时刻。"""

    return (
        datetime.now().astimezone() + timedelta(seconds=max(0.0, float(seconds)))
    ).isoformat(timespec="milliseconds")


class _EpisodeLedger:
    def __init__(
        self,
        task_frame: TaskFrame,
        *,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
        store: EpisodeStore | None = None,
        episode_id: str = "",
        configure: Mapping[str, object] | None = None,
        on_store_failure: Callable[[], None] | None = None,
    ) -> None:
        self._on_store_failure = on_store_failure
        self._task_frame_hash = task_frame.task_frame_hash
        self._event_sink = event_sink
        # 见 add() 里的临界区注释：序号是「读长度 → 追加」两步，不锁就会重号。
        # RLock 而非 Lock：同线程重入（将来若有 sink 回调再发事件）不该自锁死。
        self._lock = RLock()
        self.events: list[EpisodeEvent] = []
        self.plan: ResearchPlan | None = None
        self.time_budget_injected = False
        # INV-R1 对账失败的落账点。run() 在 Scope 建好后把它接到
        # ``EpisodeScope.record_derive_mismatch``；接线前（或没有 Scope 的调用方）
        # 落在本地列表，收据不因接线时机而丢。
        self.derive_mismatches: list[str] = []
        self.derive_mismatch_sink: Callable[[str], None] | None = None
        # 历史折叠（spec 2026-09-07 §3.2）的累计账，随 finish 事件落盘让 eval 分得开臂。
        self.history_compaction_folded = 0
        self.history_compaction_saved = 0
        # ── P2 durable（INV-R2 / INV-R3）───────────────────────────────────
        # store 是可选的：不传的调用方（参考 loop 的替身、旧测试）事件流逐字节不变——
        # 多出来的只有 ``configure`` 首条与 ``model_intent``，它们与 store 无关。
        self._store = store
        self.episode_id = str(episode_id or "").strip() or task_frame.task_frame_hash
        # OPT-08：可靠存储与进度通知是两份合同。关键写失败后停止新效果，
        # 仅内存继续收集已发生的结果；不能静默退化为正常完成的临时模式。
        self.persistence_mode = "durable" if store is not None else "ephemeral"
        self._local_store_failures: list[str] = []
        self._store_fence = store if isinstance(store, FencedEpisodeStore) else None
        # 已落意图、等结算的工具调用；``consume`` 对它们不再补事后 ``tool_request``。
        self.intended_call_ids: set[str] = set()
        self.contract_snapshot: Mapping[str, object] = dict(configure or {})
        self.state: EpisodeState | None = None
        # 状态写入要算「截止还剩多久」；loop 在换 context（深度裁决 / 修复轮）时更新它。
        self.active_context: ResearchRunContext | None = None
        self.active_registry: ResearchToolRegistry | None = None
        self.active_evidence_ledger: EvidenceLedger | None = None
        self.presented_evidence: list[AgentEvidence] | None = None
        # ── P3 收件箱（INV-R5）────────────────────────────────────────────
        # run() 建好账本后挂上；``finish`` 落账前由 add() 统一清箱（收口 / 取消各一个 reason），
        # 与 ``done`` 挂在同一个出口——十个 return 点没有一个能漏掉箱里的话。
        self.inbox: Inbox | None = None
        self._turn_counter = 0
        if configure is not None:
            # 配置快照是唯一允许先于 ``task`` 的事件（AgentOutcome 不变量）。
            self.add("configure", dict(configure))
        self.add(
            "task",
            {
                "question": task_frame.raw_question,
                "task_frame": task_frame.to_dict(),
            },
        )

    def note_derive_mismatch(self, detail: str) -> None:
        self.derive_mismatches.append(str(detail))
        if self.derive_mismatch_sink is not None:
            self.derive_mismatch_sink(str(detail))

    # ── durable：意图 / 状态 ─────────────────────────────────────────────

    @property
    def store_failures(self) -> list[str]:
        # Read shared health without callbacks into other ledger locks (no ABBA).
        failures = list(self._local_store_failures)
        if not failures and self._store_fence is not None and self._store_fence.failure:
            failures.append(f"episode_tree:{self._store_fence.failure}")
        return failures

    def _persist(self, event: EpisodeEvent) -> None:
        if self.store_failures:
            self._store = None
        store = self._store
        if store is None:
            return
        try:
            store.append(
                self.episode_id, (event,),
                sync=event.kind in INTENT_KINDS or event.kind in {
                    "finish", "inbox_inserted", "inbox_claimed", "inbox_discarded",
                },
            )
        except Exception as exc:  # noqa: BLE001 - 熔断新派发，保留内存结果
            self._fail_store(f"append#{event.sequence}:{type(exc).__name__}")

    def _fail_store(self, detail: str) -> None:
        self._local_store_failures.append(detail)
        self._store = None
        if self._on_store_failure is not None:
            self._on_store_failure()

    def model_complete(self, model: AgentModelClient, **kwargs: object) -> ModelTurn:
        """Every model entry (including repair) must pass the durable fence."""
        if self.store_failures:
            return ModelTurn("", (), error="storage_failed", provider_attempts=0)
        return model.complete(**kwargs)

    def outcome(self, **kwargs: object) -> AgentOutcome:
        """Only advertise completion AFTER finish append and done checkpoint succeed.

        A finish already appended cannot be rewritten when the done checkpoint fails.
        The extra in-memory failure receipt supersedes it without corrupting the prefix.
        """
        persistence = self.persistence_mode
        if self.store_failures:
            persistence = "failed"
            gap = "关键恢复记录保存失败；已停止新派发，保留的草稿不可视为可靠完成或自动续跑依据。"
            if not any(e.kind == "persistence_failed" for e in self.events):
                self.add("persistence_failed", {
                    "status": "failed", "stop_reason": "storage_failed",
                    "store_failures": list(self.store_failures),
                    "recovery": "uncertain", "learning_eligible": False,
                })
            kwargs.update(
                status="failed", stop_reason="storage_failed",
                gaps=tuple(dict.fromkeys((*kwargs.get("gaps", ()), gap))),
            )
        kwargs.update(events=tuple(self.events), persistence=persistence)
        return AgentOutcome(**kwargs)

    def put_state(
        self,
        *,
        phase: EpisodePhase,
        reserved_ids: tuple[str, ...] = (),
        context: ResearchRunContext | None = None,
        retry: Mapping[str, object] | None = None,
        cancel: Mapping[str, object] | None = None,
    ) -> EpisodeState:
        """覆写一份完整的程序计数器（INV-R3）。每次 phase 转移调一次。

        ``deadline_at`` / ``consumed_seconds`` 从 ``context``（缺省 ``active_context``）的
        截止算成挂钟；没有 context 就沿用上一份——终局 ``done`` 不需要它们。
        """

        previous = self.state
        source = context if context is not None else self.active_context
        deadline_at = previous.deadline_at if previous is not None else ""
        consumed = previous.consumed_seconds if previous is not None else 0.0
        if source is not None:
            remaining = float(source.deadline.remaining())
            deadline_at = _wall_clock_after(remaining)
            consumed = max(0.0, float(source.policy.total_seconds) - remaining)
        carried_cancel = (
            dict(cancel)
            if cancel is not None
            else (dict(previous.cancel) if previous is not None and previous.cancel else None)
        )
        with self._lock:
            state = EpisodeState(
                episode_id=self.episode_id,
                phase=phase,
                turn_index=self._turn_counter,
                reserved_ids=tuple(reserved_ids),
                consumed_seconds=consumed,
                deadline_at=deadline_at,
                retry=dict(retry) if retry is not None else {},
                contract_snapshot=self.contract_snapshot,
                cancel=carried_cancel,
                last_sequence=len(self.events),
                updated_at=now_iso(),
                # 热路径不产生未知效果（本进程内的意图都能看到自己的结算），但也没资格
                # **抹掉**上一次恢复留下的未对账凭证：只有对账能清空它。不带它往下传，
                # 等于用下一个检查点把「有笔账没对」静默改写成「无账可对」。
                unreconciled_effects=(
                    tuple(previous.unreconciled_effects) if previous is not None else ()
                ),
            )
            if not self.store_failures:
                try:
                    budget_snapshot = previous.budget_snapshot if previous is not None else None
                    budget_sequence = previous.budget_snapshot_sequence if previous is not None else None
                    if source is not None:
                        # A child view is NOT an independent root allocation.
                        root = source.root_budget
                        budget_snapshot = root.to_snapshot() if isinstance(root, InMemoryRootBudgetLedger) else None
                        if isinstance(root, InMemoryRootBudgetLedger) and budget_snapshot is None:
                            raise ValueError("root budget omitted its required snapshot")
                        budget_sequence = len(self.events) if budget_snapshot is not None else None
                    state = replace(
                        state, budget_snapshot=budget_snapshot, budget_snapshot_sequence=budget_sequence,
                    )
                except Exception as exc:
                    # Encoding is part of required persistence. Do not write a
                    # valid-looking state with its required budget omitted.
                    if self.persistence_mode != "durable":
                        raise
                    if self._store_fence is not None:
                        self._store_fence.fail(self.episode_id, f"state:{phase}:budget", exc)
                    self._fail_store(f"state:{phase}:budget:{type(exc).__name__}")
            if not self.store_failures:
                try:
                    authorization = previous.authorization_snapshot if previous is not None else None
                    if source is not None:
                        if self.active_registry is None:
                            raise ValueError("episode omitted its required authorization registry")
                        authorization = capture_authorization_snapshot(source, self.active_registry)
                        if authorization is None:
                            raise ValueError("episode omitted its required authorization snapshot")
                    state = replace(state, authorization_snapshot=authorization)
                except Exception as exc:
                    if self.persistence_mode != "durable":
                        raise
                    if self._store_fence is not None:
                        self._store_fence.fail(self.episode_id, f"state:{phase}:authorization", exc)
                    self._fail_store(f"state:{phase}:authorization:{type(exc).__name__}")
            if not self.store_failures:
                try:
                    identity = previous.entry_identity if previous is not None else None
                    if source is not None:
                        captured = capture_entry_identity(source)
                        # One episode, one owner. A door that changes mid-run (or
                        # disappears) is not a fallback to "unbound" -- it means the
                        # context we are checkpointing is no longer the one that started.
                        if identity is not None and captured != identity:
                            raise ValueError("episode entry identity must not change mid-run")
                        identity = captured
                    state = replace(state, entry_identity=identity)
                except Exception as exc:
                    if self.persistence_mode != "durable":
                        raise
                    if self._store_fence is not None:
                        self._store_fence.fail(self.episode_id, f"state:{phase}:identity", exc)
                    self._fail_store(f"state:{phase}:identity:{type(exc).__name__}")
            if not self.store_failures:
                try:
                    evidence = previous.evidence_snapshot if previous is not None else None
                    evidence_sequence = previous.evidence_snapshot_sequence if previous is not None else None
                    if source is not None:
                        if self.active_evidence_ledger is None or self.presented_evidence is None:
                            raise ValueError("episode omitted its required evidence source")
                        if self.active_evidence_ledger.information_cutoff != source.information_cutoff.as_of_date:
                            raise ValueError("episode evidence cutoff differs from current context")
                        evidence = capture_evidence_snapshot(
                            episode_id=self.episode_id, ledger=self.active_evidence_ledger,
                            presented_evidence=tuple(self.presented_evidence),
                        )
                        if evidence is None:
                            raise ValueError("episode omitted its required evidence snapshot")
                        evidence_sequence = len(self.events)
                    state = replace(state, evidence_snapshot=evidence, evidence_snapshot_sequence=evidence_sequence)
                except Exception as exc:
                    if self.persistence_mode != "durable":
                        raise
                    if self._store_fence is not None:
                        self._store_fence.fail(self.episode_id, f"state:{phase}:evidence", exc)
                    self._fail_store(f"state:{phase}:evidence:{type(exc).__name__}")
            self.state = state
            store = self._store if not self.store_failures else None
            if store is not None:
                try:
                    store.put_state(self.episode_id, state)
                except Exception as exc:  # noqa: BLE001 - 同 _persist
                    self._fail_store(f"state:{phase}:{type(exc).__name__}")
        return state

    def record_model_intent(
        self,
        *,
        timeout_asked: float,
        phase: str,
        retries_remaining: int,
        context: ResearchRunContext | None = None,
    ) -> str:
        """模型请求前的意图（效果三明治左片）。返回预留给结算复用的 ``turn_id``。

        ``retries_remaining`` 是**捕获的**重试策略：恢复时发现意图无结算，允许再问几次。
        写在意图与状态里而不是恢复时现算——策略是当时的决定，以后的代码不该改写它。
        """

        with self._lock:
            self._turn_counter += 1
            turn_id = f"turn-{self._turn_counter}"
        self.add(
            "model_intent",
            {
                "turn_id": turn_id,
                "timeout_asked": float(timeout_asked),
                "phase": str(phase),
                "retries_remaining": int(retries_remaining),
            },
        )
        self.put_state(
            phase="model_pending",
            reserved_ids=(turn_id,),
            context=context,
            retry={"remaining": int(retries_remaining)},
        )
        return turn_id

    def record_dispatch_intent(self, intent: DispatchIntent) -> bool:
        """工具派发前的意图：这一批真要进线程池的每个调用各一条 ``tool_request``。

        payload 与事后写法同形（``call.to_dict()`` + dispatch clock + 空池回退标记），多一个
        ``replay``——恢复时决定「同参数重跑」还是「合成 interrupted」的依据。
        """

        if self.store_failures:
            return False
        clock = intent.clock.to_payload()
        for call in intent.calls:
            payload: dict[str, object] = {
                **call.to_dict(),
                **clock,
                "replay": str(intent.replay.get(call.call_id, "safe")),
            }
            extra = intent.request_extras.get(call.call_id)
            if extra:
                payload.update(extra)
            self.add("tool_request", payload)
            with self._lock:
                self.intended_call_ids.add(call.call_id)
        self.put_state(
            phase="tools_pending",
            reserved_ids=tuple(call.call_id for call in intent.calls),
        )
        return not self.store_failures

    def settle_tool_request(self, call_id: str) -> bool:
        """结算到达：该调用若有在飞意图则销掉并返回 True（调用方不再补事后 tool_request）。"""

        with self._lock:
            if call_id in self.intended_call_ids:
                self.intended_call_ids.discard(call_id)
                return True
            return False

    def verify_model_visible(self, messages: list[EpisodeMessage]) -> bool:
        """请求前对账（INV-R1）：即将发出的 messages 必须能从本账本的事件派生。

        严格模式（测试）不一致即抛；生产只记账不炸——见 ``episode_messages`` 文首。
        """

        with self._lock:
            snapshot = tuple(self.events)
        return check_derivation(snapshot, messages, on_mismatch=self.note_derive_mismatch)

    def add(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event_payload = dict(payload)
        event_payload["task_frame_hash"] = self._task_frame_hash
        if kind == "finish":
            # INV-R5：收口前清箱。箱里没送到模型的话逐条落 inbox_discarded，reason 按终局分
            # （取消 → cancelled，其余 → episode_finished），事件序都在 finish 之前——
            # 读事件流的人不会看到「finish 之后还有未决的 inserted」。
            inbox = self.inbox
            if inbox is not None and not inbox.closed:
                inbox.discard_all(
                    reason=(
                        "cancelled"
                        if str(event_payload.get("stop_reason") or "") == "cancelled"
                        else "episode_finished"
                    )
                )
            event_payload.setdefault(
                "time_budget_injected", self.time_budget_injected
            )
            event_payload.setdefault(
                "history_compaction",
                {
                    "enabled": history_compaction_enabled(),
                    "folded_messages": self.history_compaction_folded,
                    "chars_saved": self.history_compaction_saved,
                },
            )
            event_payload.setdefault("store_failures", list(self.store_failures))
            if self.store_failures:
                event_payload.update(status="failed", stop_reason="storage_failed")
        # 事件发生的挂钟时刻。相邻两条事件的时间差就是上一步的耗时——所以不需要
        # 给每一步单独开 span，就能算出「哪一步吃掉了时钟」。
        #
        # 放进 payload 而不是给 EpisodeEvent 加字段：``task_frame_hash`` 已经是
        # 同样的做法，而 EpisodeEvent 是 services 层的冻结 dataclass，被所有
        # runtime 共用，加字段的爆炸半径大得多。
        event_payload["at"] = datetime.now().astimezone().isoformat(timespec="milliseconds")
        # 临界区：序号取自 ``len(self.events)``，与 append 之间必须原子。两个线程
        # 各读到同一个长度就会发出重号，而重号会撞 episode_session 的 resume 前缀
        # 不变量（事件只增、前缀逐条相等）和「sequence 恰好是 1..N」的断言。
        #
        # 今天所有 add 都在主线程（阶段事件的 sink 还是 None，emit 直接返回），
        # 所以这把锁现在是**先决条件**不是修复：spec §11 第 5 步要把发射点接到
        # 8 worker 的共享工具线程池上，先接线后加锁等于造一个随机变红的门禁。
        # 顺序见台账 §10.2 的 D2。
        with self._lock:
            event = EpisodeEvent(len(self.events) + 1, kind, event_payload)
            self.events.append(event)
            # 落盘留在锁内：store 里的行序必须等于 sequence 序，两个线程各拿到号再
            # 抢着写会让 JSONL 乱序（读回时按「1..N 连续」判损坏）。意图类 fsync，
            # 结算类不 fsync——见 episode_store 文首。
            self._persist(event)
        if kind == "finish":
            # done 写成功之前不向 UI 广告完成；finish fsync 同时冲刷前序结算。
            self.put_state(phase="done")
        # sink 调用**留在锁外**：它是外部回调（UI/进度），持锁调外部代码是经典死锁
        # 源，且慢 sink 会把研究主路径一起卡住。代价是并发时 sink 的到达顺序可能与
        # sequence 不一致——消费者按 sequence 排序，别按到达顺序。
        if self._event_sink is not None and not (kind == "finish" and self.store_failures):
            try:
                self._event_sink(event)
            except Exception:
                # Progress is observability, never an alternate execution
                # owner. A broken UI sink must not abort financial research.
                pass
        return event

    def record_plan(self, plan: ResearchPlan) -> EpisodeEvent:
        self.plan = plan
        return self.add("plan", plan_to_public_dict(plan))

    def record_runtime_result(self) -> None:
        with self._lock:
            snapshot = tuple(self.events)
        input_tokens, output_tokens = _token_usage_from_events(snapshot)
        if input_tokens is None and output_tokens is None:
            return
        self.add(
            "runtime_result",
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )



def _tool_timing_payload(result: ToolCallResult) -> dict[str, object]:
    """把一次工具调用的排队/执行时长摊平成事件字段。

    只有测到的才写：派发前就被拒的调用压根没进线程池，此时写 0 会把
    「没测到」伪装成「零耗时」——那正是这套埋点要消灭的那类假读数。
    """

    payload: dict[str, object] = {}
    if result.queued_ms is not None:
        payload["queued_ms"] = result.queued_ms
    if result.elapsed_ms is not None:
        payload["elapsed_ms"] = result.elapsed_ms
    return payload


def _tool_dispatch_clock_payload(result: ToolCallResult) -> dict[str, object]:
    """派发点五元组：名义窗 / 实授 / 剩余 / 次数 / 思考耗时。

    时间闸（``tool_not_dispatched`` 零授权未派发 / ``tool_timeout`` 真超时）和次数闸
    （``tool_budget_exhausted`` + ``remaining_slots_at_dispatch``）共用这份
    快照，靠 error 码分闸；``detail=stage_timeout_granted=…`` 给实授值。
    没测到的字段不写，避免把缺席伪装成 0。
    """

    clock = result.dispatch_clock
    if clock is None:
        return {}
    return clock.to_payload()


_ABS_PATH_RE = re.compile(
    r"(?:~|/Users|/home|/private/var|/var/folders)[^\s\"'，。]+"
)
_TOOL_EXCEPTION_DETAIL_LIMIT = 160


def _public_tool_exception_detail(raw: str) -> str:
    """Keep exception class + first line; strip home paths; truncate.

    ``error`` stays the public classification ``tool_exception``. The batch
    layer already formats ``TypeName: message``, but ``consume`` used to drop
    that string and persist ``detail=""``.
    """

    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.splitlines()[0].strip()
    if not text:
        return ""
    return _ABS_PATH_RE.sub("<path>", text)[:_TOOL_EXCEPTION_DETAIL_LIMIT]


@dataclass
class _EpisodeToolAccumulator:
    messages: list[EpisodeMessage]
    ledger: _EpisodeLedger
    evidence_ledger: EvidenceLedger
    # 「审计留什么、模型看什么」归 harness；本类只管账：事件、证据去重、traces、gaps。
    harness: ResearchHarness | None = None
    evidence: list[AgentEvidence] = field(default_factory=list)
    evidence_hashes: set[str] = field(default_factory=set)
    successful_tools: set[str] = field(default_factory=set)
    traces: list[ProviderTrace] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    seen_observation_prose: set[str] = field(default_factory=set)
    read_coverage: EvidenceReadCoverage = field(default_factory=EvidenceReadCoverage)
    # 研究进展账（06 号单）：按批记「这轮有没有新证据 / 同一查询重复了几次 / 哪个工具连续空手」，
    # 底座事实，run() 叠进 runtime_budget 递给模型；停滞到底时收口。
    progress: ResearchProgressTracker = field(default_factory=ResearchProgressTracker)

    def __post_init__(self) -> None:
        if self.harness is None:
            self.harness = FinanceResearchHarness()

    def consume(
        self,
        batch: ToolBatchResult,
        context: ResearchRunContext,
        request_extras: Mapping[str, Mapping[str, object]] | None = None,
    ) -> int:
        invalid_actions = 0
        extras_by_id = request_extras or {}
        for result in batch.items:
            call = result.call
            clock = _tool_dispatch_clock_payload(result)
            timing = {**_tool_timing_payload(result), **clock}
            request_payload = {**call.to_dict(), **clock}
            extra = extras_by_id.get(call.call_id)
            if extra:
                request_payload.update(extra)
            # 派发过的调用在 ``_dispatch`` 之前已由 ``record_dispatch_intent`` 落过意图
            # （INV-R2）；这里只给**没派发**的（拒绝 / 零授权 / 取消）补事后记录——它们没有
            # 外部效果，不需要意图，但读者仍指望每个调用恰好一条 tool_request。
            if not self.ledger.settle_tool_request(call.call_id):
                self.ledger.add("tool_request", request_payload)

            if result.status == "rejected":
                invalid_actions += 1
                # 去重闸拒掉的调用就是「同一查询又来了一遍」：进展账记成 duplicate，
                # 而不是笼统的 rejected——模型下一轮要看到的是「换查询」这个事实。
                self.progress.record_call(
                    ToolCallDigest(
                        call.name,
                        call.arguments,
                        "duplicate" if result.error == "duplicate_query" else "rejected",
                    )
                )
                if result.error == "unknown_or_unauthorized_tool":
                    self.traces.append(
                        ProviderTrace(
                            provider="episode:tool_gate",
                            capability=call.name,
                            status="disabled",
                            detail=result.error,
                            parent_id=context.trace_parent_id,
                            step_id=result.step_id,
                        )
                    )
                self._append_tool_error(call, result.error, result.detail, timing)
                continue

            if result.status in {"error", "timeout"}:
                # 时间闸两码（未派发 / 真超时）由批次执行器分好，这里原样带给模型。
                public_error = (
                    time_gate_error_for_model(result)
                    if result.status == "timeout"
                    else "tool_exception"
                )
                if result.status == "timeout":
                    public_detail = timeout_detail_for_model(result)
                else:
                    public_detail = _public_tool_exception_detail(
                        result.detail or result.error
                    )
                self.traces.append(
                    ProviderTrace(
                        provider=f"agent:{call.name}",
                        capability=call.name,
                        status="request_error",
                        detail=public_error,
                        parent_id=context.trace_parent_id,
                        step_id=result.step_id,
                    )
                )
                self._append_tool_error(
                    call, public_error, public_detail, timing=timing
                )
                self.progress.record_call(
                    ToolCallDigest(call.name, call.arguments, str(result.status))
                )
                continue

            observation = result.observation
            if observation is None:
                raise RuntimeError(
                    "successful tool batch result requires an observation"
                )
            self.traces.append(observation.trace)
            self._extend_unique_gaps(observation.gaps)
            if observation.evidence:
                self.successful_tools.add(call.name)
            new_evidence = 0
            for item in observation.evidence:
                if item.content_hash in self.evidence_hashes:
                    continue
                self.evidence_hashes.add(item.content_hash)
                self.evidence.append(item)
                self.evidence_ledger.append(item)
                new_evidence += 1
            assert self.harness is not None
            projection = self.harness.project_tool_result(
                observation,
                evidence_so_far=tuple(self.evidence),
                seen_prose=self.seen_observation_prose,
            )
            self.seen_observation_prose = set(projection.seen_prose)
            # call_id 与 timing 只进 ledger 展开，不进审计底稿——那个 dict 是
            # 模型视图的来源（R-20260827-15）。``model_content`` 是模型真看到的那段
            # （INV-R1）：审计底稿与模型正文同一份事实两个出口，两个都进事件。
            self.ledger.add(
                "tool_result",
                {
                    **projection.audit_payload,
                    "call_id": call.call_id,
                    "model_content": projection.model_content,
                    **timing,
                },
            )
            self.messages.append(
                tool_message(call.call_id, projection.model_content, source="tool_result")
            )
            # Navigation progress is measured only after delivery into model input.
            # A reread keeps the old evidence identity; do not invent a new source
            # to prevent the existing stall heuristic from closing the episode.
            new_read_chars = (
                self.read_coverage.observe(projection.model_content, evidence=tuple(self.evidence))
                if evidence_read_enabled() else 0
            )
            self.progress.record_call(
                ToolCallDigest(
                    call.name, observation.query or call.arguments,
                    "new" if new_evidence else "duplicate" if observation.evidence else "empty",
                    new_evidence=new_evidence, total_evidence=len(observation.evidence),
                    new_read_chars=new_read_chars,
                )
            )
            acknowledge = getattr(self.harness, "acknowledge_tool_result", None)
            if acknowledge is not None:
                acknowledge(observation, projection, context=context)
        return invalid_actions

    def _append_tool_error(
        self,
        call: ModelToolCall,
        error: str,
        detail: str = "",
        timing: dict[str, object] | None = None,
    ) -> None:
        assert self.harness is not None
        payload = self.harness.project_tool_error(
            tool=call.name, error=error, detail=detail
        )
        # 耗时与 call_id 只进 ledger，**不进 payload**——下面那条 messages 是喂模型的，
        # 给它塞毫秒数既没用又占预算。审计要全量、模型要够用，同一份事实两个出口。
        # ``model_content`` 是那段序列化后的正文本身（INV-R1 派生用）。
        model_content = json.dumps(payload, ensure_ascii=False)
        self.ledger.add(
            "tool_error",
            {
                **payload,
                "call_id": call.call_id,
                "model_content": model_content,
                **(timing or {}),
            },
        )
        self.messages.append(tool_message(call.call_id, model_content, source="tool_error"))

    def _extend_unique_gaps(self, values: tuple[str, ...]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in self.gaps:
                self.gaps.append(cleaned)

    def note_delivered_sub_research(self, messages: Sequence[EpisodeMessage]) -> None:
        """Seed only literal evidence in branch messages already in model input.

        Branch completion and inbox insertion are not delivery. This records
        coverage, not new read progress or a new independent evidence source.
        """
        if not evidence_read_enabled():
            return
        for message in messages:
            if message.source == "sub_research":
                self.read_coverage.observe(
                    message.content, evidence=tuple(self.evidence)
                )

    def retain_entity_diagnostics(self, declared: tuple[str, ...]) -> tuple[str, ...]:
        """A model finish cannot erase the tool's exact-identity diagnostic."""
        return tuple(dict.fromkeys((
            *declared,
            *(gap for gap in self.gaps if gap.startswith(("fabricated_entity:", "entity_catalog_unavailable:"))),
        )))

    def consume_sub_research(self, result: SubResearchResult) -> None:
        self.traces.extend(result.traces)
        self.progress.record_branches(
            result.branches, refused_reason=result.refused_reason
        )
        for branch in result.branches:
            # 分支里跑的工具此前**一条事件都不发**：只有 branch_started /
            # branch_completed 这对括号，中间发生了什么在事件流里是黑的。
            # 2026-08-14 实测两个 run 声称 tool_calls=8、工具事件 0 条，全部
            # 发生在 3 个并发分支里。后果不只是"看不见"——任何按事件计数的
            # 成功率/错误率都会漏掉整条路径，而漏掉的恰恰是并发压力最大的那条。
            for trace in branch.traces:
                self.ledger.add(
                    "branch_tool",
                    {
                        "branch_id": branch.branch_id,
                        "goal": branch.goal,
                        "tool": provider_trace_tool_name(trace),
                        "provider": trace.provider,
                        "capability": trace.capability,
                        "status": trace.status,
                        "result_count": trace.result_count,
                        "detail": str(trace.detail or "")[:200],
                    },
                )
            self._extend_unique_gaps(
                tuple(f"{branch.goal}: {gap}" for gap in branch.gaps)
            )
            for item in branch.evidence:
                if item.content_hash in self.evidence_hashes:
                    continue
                self.evidence_hashes.add(item.content_hash)
                self.evidence.append(item)


def _seed_prior_evidence(
    accumulator: _EpisodeToolAccumulator,
    messages: list[EpisodeMessage],
    context: ResearchRunContext,
) -> None:
    snapshot = context.prior_evidence
    if snapshot is None:
        return
    from intelligence.services.derived_calculation import evidence_payload

    material = context.contract.material_contract
    if material is None or material.data_scope != "material_only" or context.contract.allowed_capabilities:
        raise ValueError("frozen prior inputs cannot authorize a new-read episode")
    evidence = snapshot.admitted(
        task_frame_hash=context.contract.task_frame_hash,
        cutoff=context.information_cutoff.as_of_date,
    )
    if not evidence:
        raise ValueError("no prior evidence within the current cutoff")
    accumulator.evidence_ledger.append(evidence)
    accumulator.evidence.extend(evidence)
    accumulator.evidence_hashes.update(item.content_hash for item in evidence)
    receipt = snapshot.receipt()
    receipt["bindings"] = remap_evidence_bindings(
        snapshot, tuple(accumulator.evidence)
    )
    append_model_input(
        messages, accumulator.ledger,
        content=json.dumps({
            "kind": "prior_tool_evidence", "receipt": receipt,
            "evidence": evidence_payload(evidence),
            "rule": (
                "以下是经同用户同会话原件校验的旧工具输入，不是重新查询。日期与口径仍属于原轮，"
                "不能当作当前行情或其他日期的观测；仅用于复核原问题，不扩大研究范围。"
                "只使用此处新编号，旧答编号不得直接复用。旧结论、覆盖状态和完成判定均未继承。"
                "历史助手陈述仍只是待审判断；原件没有的资金行为等信息继续未知，"
                "不得用待撤回的旧说法反过来证明自己。"
            ),
        }, ensure_ascii=False),
        source="prior_tool_evidence",
    )


def _seed_opening_prefetch(
    accumulator: _EpisodeToolAccumulator,
    messages: list[EpisodeMessage],
    registry: ResearchToolRegistry,
) -> None:
    """把 harness 预取放进证据账本和开场 user 消息，不伪造 tool_call_id。"""

    evidence = tuple(getattr(registry, "opening_prefetch", ()) or ())
    if not evidence:
        return
    from intelligence.services.asof_prefetch import format_opening_prefetch_message

    for item in evidence:
        digest = str(item.content_hash or "").strip()
        if not digest or digest in accumulator.evidence_hashes:
            continue
        accumulator.evidence_hashes.add(digest)
        accumulator.evidence.append(item)
        accumulator.evidence_ledger.append(item)
    message = format_opening_prefetch_message(evidence)
    if message:
        append_model_input(
            messages, accumulator.ledger, content=message, source="opening_prefetch"
        )
        if evidence_read_enabled():
            accumulator.read_coverage.note_complete(evidence)
        accumulator.ledger.add(
            "prefetch",
            {
                "count": len(evidence),
                "tools": [item.tool for item in evidence],
            },
        )


class _ContextRef:
    """loop 手里「当前 context」的可变引用。

    PLAN 升档会 ``replace`` 出新 context；episode 期绑好的 ``sub_research`` runner 在批执行器
    线程里跑，得按换过之后的档位与账本起分支，所以给它一个会跟着变的引用而不是起步时的值。
    """

    __slots__ = ("value",)

    def __init__(self, value: ResearchRunContext) -> None:
        self.value = value

    def __call__(self) -> ResearchRunContext:
        return self.value


@dataclass
class _EpisodeContinuationState:
    task_frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    tool_session: EpisodeToolBatchSession
    messages: list[EpisodeMessage]
    ledger: _EpisodeLedger
    accumulator: _EpisodeToolAccumulator
    evidence_ledger: EvidenceLedger
    initial_evidence_snapshot: EvidenceLedgerSnapshot
    # run() 入口构造的那个 Scope。resume 复用本 state（含同一 tool_session，
    # 其内就是这个 scope），所以 Scope 的生命周期覆盖整个 Episode 含修复轮
    # ——这里显式暴露引用，是让会话层（RuntimeHandle）能把生命周期收据与
    # 能力收据钉在同一个对象上，而不是各拿各的。
    episode_scope: EpisodeScope
    # run() 绑 sub_research 工具时用的当前 context 引用；resume 换 context 也要更新它。
    # None = 本 episode 没有协调器、没绑该工具（分支里的嵌套 Episode、参考 loop）。
    context_ref: _ContextRef | None = None


STEP_PHASES: tuple[str, ...] = (
    "model_pending",
    "model_settled",
    "before_tool_dispatch",
    "tools_settled",
    "before_finish",
)


@dataclass(frozen=True)
class StepPoint:
    """``manual_drive().step()`` 停下的那个点（运行底座 P4）。只给驱动方 / 竞态测试看。"""

    phase: str
    llm_calls: int
    tool_calls: int
    turn_id: str = ""


class EpisodeDrive:
    """一次性的单步驱动器：包着 ``ContinuousAgentEpisode._drive`` 生成器。

    ``step()`` 跑到下一个 ``StepPoint``（终态时回 ``None`` 并填好 ``outcome``）；
    ``run_until(phase)`` 连跑到某类步点；``run_to_end()`` 排空。生成器抛过异常后不可再驱动。
    """

    def __init__(self, generator: Generator[StepPoint, None, AgentOutcome]) -> None:
        self._generator = generator
        self.outcome: AgentOutcome | None = None
        self.finished = False
        self.steps: list[StepPoint] = []
        self._operation_lock = Lock()

    def step(self) -> StepPoint | None:
        if not self._operation_lock.acquire(blocking=False):
            raise EpisodeWriterBusy("episode drive operation is active")
        try:
            if self.finished:
                return None
            try:
                point = next(self._generator)
            except StopIteration as stop:
                self.outcome = stop.value
                self.finished = True
                return None
            except BaseException:
                self.finished = True
                raise
            self.steps.append(point)
            return point
        finally:
            self._operation_lock.release()

    def close(self) -> None:
        """Abandon a paused drive; an executing step must finish before closing."""
        if not self._operation_lock.acquire(blocking=False):
            raise EpisodeWriterBusy("episode drive operation is active")
        try:
            try:
                self._generator.close()
            finally:
                self.finished = True
        finally:
            self._operation_lock.release()

    def run_until(self, phase: str) -> StepPoint | None:
        """跑到下一个 ``phase`` 步点；先到终态就回 ``None``。"""

        if phase not in STEP_PHASES:
            raise ValueError(f"unknown step phase: {phase!r}")
        while True:
            point = self.step()
            if point is None or point.phase == phase:
                return point

    def run_to_end(self) -> AgentOutcome:
        while not self.finished:
            self.step()
        assert self.outcome is not None
        return self.outcome


class ContinuousAgentEpisode:
    """Run a task without rebuilding the model's observable message history."""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        llm_timeout: float = DEFAULT_LLM_TIMEOUT,
        tool_executor: ToolBatchExecutor | None = None,
        finalizer: EpisodeFinalizer | None = None,
        is_cancelled: Callable[[], bool] | CancelSignal | None = None,
        sub_research_coordinator: SubResearchCoordinator | None = None,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
        repair_seconds_cap: float | None = None,
        harness: ResearchHarness | None = None,
        store: EpisodeStore | None = None,
        runtime_config: Mapping[str, object] | None = None,
    ) -> None:
        self._model = model
        # P2：durable store（INV-R2 / R3）。None = 只在内存记账，事件流形状仍与落盘时相同。
        # ``runtime_config`` 是装配根（GLMAgentRuntime）知道、Episode 不知道的配置
        # （模型名 / provider 链），只进 ``configure`` 快照，不参与任何判断。
        self._store = (
            FencedEpisodeStore(store)
            if store is not None and not isinstance(store, FencedEpisodeStore)
            else store
        )
        self._runtime_config: dict[str, object] = dict(runtime_config or {})
        # 领域门（prompt / 批后停机 / 取证面 / 终局准入 / 深度裁决）由 harness 回答，
        # loop 只调。默认金融 harness 是对既有函数的纯委托；传别的实现进来就是换领域。
        # 深度裁决的两个注入件（mode_governor / mode_signals）归 harness 构造器：
        # #529 把它们搬过去时这里留了一层转交壳兼容既有调用方，调用方全部改直传
        # harness 后即删（本刀）。Episode 从此不认识 ModeGovernor / ModeSignals。
        self._harness: ResearchHarness = (
            harness if harness is not None else FinanceResearchHarness()
        )
        self._llm_timeout = max(0.1, float(llm_timeout))
        self._repair_seconds_cap = (
            float(repair_seconds_cap)
            if repair_seconds_cap is not None
            else repair_seconds_cap_for(provider_name_from(model))
        )
        self._tool_executor = (
            tool_executor if tool_executor is not None else ToolBatchExecutor()
        )
        self._finalizer = (
            finalizer
            if finalizer is not None
            else EpisodeFinalizer(model, llm_timeout=self._llm_timeout)
        )
        # 取消信号类型化（INV-R4）：裸谓词包成 CancelSignal，原因默认 user。
        # ``_is_cancelled`` 仍是可调用的——所有既有检查点零改动，多出来的是 ``.cause``。
        self._cancel = CancelSignal.coerce(is_cancelled)
        self._is_cancelled: Callable[[], bool] = self._cancel
        if isinstance(self._store, FencedEpisodeStore):
            self._store.on_failure(lambda: self._cancel.request("hook", "storage_failed"))
        self._sub_research_coordinator = sub_research_coordinator
        self._event_sink = event_sink
        # P3：当前在跑的 episode 的收件箱（INV-R5）。``steer()`` 从这里递话；run() 进门时换新。
        # 没在跑时是 None——递话方拿到 ``no_active_episode`` 回执，不是异常。
        self._active_inbox: Inbox | None = None
        # The inbox and cancellation signal belong to this runner, not a task ID.
        self._control_lock = Lock()

    @contextmanager
    def _control_writer(self, episode_id: str) -> Iterator[None]:
        if not self._control_lock.acquire(blocking=False):
            raise EpisodeWriterBusy("episode runner already controls a task")
        try:
            with episode_writer(self._store, episode_id):
                yield
        finally:
            self._control_lock.release()

    # ── 收件箱：外部输入的唯一入口（INV-R5）───────────────────────────────

    @property
    def inbox(self) -> Inbox | None:
        """当前 episode 的收件箱；run() 之外为 None。测试与装配审计用。"""

        return self._active_inbox

    def steer(
        self,
        content: str,
        *,
        target: InboxTarget = "next_step",
        source: str = "steer",
        wakeup: bool = False,
    ) -> InboxReceipt:
        """外部给正在跑的 episode 递一句话（user 角色）。

        ``next_step``：下一次模型请求前送达；``next_turn``：模型停下时送达并让它再跑一轮。
        收不收由 ``ResearchHarness.admit_inbox_message`` 判；三个事实都进 durable 流。
        没有在跑的 episode 时回 ``accepted=False, reason="no_active_episode"``——不抛：
        递话方不该能把研究主路径打断。
        """

        inbox = self._active_inbox
        if inbox is None:
            return InboxReceipt(message_id="", accepted=False, reason="no_active_episode")
        return inbox.send(
            user_message(str(content), source=str(source or "steer")),
            target=target,
            wakeup=wakeup,
        )

    @staticmethod
    def _claim_inbox(
        *,
        messages: list[EpisodeMessage],
        ledger: _EpisodeLedger,
        target: InboxTarget,
        accumulator: _EpisodeToolAccumulator | None = None,
    ) -> int:
        """把该队列的话取出来 append 进 messages。认领事件先落、消息后进——与
        ``append_model_input`` 同一个「事件在前、派生物在后」的写序。"""

        inbox = ledger.inbox
        if inbox is None:
            return 0
        claimed = inbox.claim(target)
        messages.extend(claimed)
        if accumulator is not None:
            accumulator.note_delivered_sub_research(claimed)
        return len(claimed)

    @staticmethod
    def restore(
        episode_id: str,
        store: EpisodeStore,
        *,
        registry: ResearchToolRegistry | None = None,
        harness: ResearchHarness | None = None,
        now: datetime | None = None,
        context: ResearchRunContext | None = None,
    ) -> RestoreResult:
        """崩溃后恢复（INV-R3）：读 ``EpisodeState``、按预留 id 点查结算、给下一动作或直接闭合。

        策略与合成全在 ``services.episode_restore``——它不需要模型、不需要 loop，能对着产物
        事后重跑。本单只给 ``ResumePlan``，不重新驱动 loop（P4 ``step()``）。
        """

        return restore_episode(
            episode_id, store, registry=registry, harness=harness, now=now, context=context,
        )

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[_EpisodeContinuationState] | None = None,
    ) -> AgentOutcome:
        """跑到终态。控制流全在 ``_drive`` 里；这里只是把生成器排空（P4 ``step()``）。"""

        with llm_refine.writer_model_scope(material_pack_writer_model(context.contract)):
            return self.manual_drive(
                task_frame=task_frame,
                context=context,
                registry=registry,
                _continuation_sink=_continuation_sink,
            ).run_to_end()

    def manual_drive(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[_EpisodeContinuationState] | None = None,
    ) -> EpisodeDrive:
        """单步驱动（运行底座 P4 / 工单 #31）：每次 ``step()`` 跑到下一个效果边界停下。

        与 ``run()`` 是**同一段代码**——``run()`` 就是把这个生成器排空。停下的点只有五种
        （``STEP_PHASES``）：模型意图已 durable、结算未发（``model_pending``）；模型结算刚落
        （``model_settled``）；工具意图将落、批次未派发（``before_tool_dispatch``）；批次结算
        刚落（``tools_settled``）；终局 ``finish`` 将落（``before_finish``）。竞态目录
        （``conformance/races/``）就是在这些点上把取消 / steer / restore 插进去，两种顺序各跑一遍。

        为什么是生成器而不是状态机重写：run() 有几十个局部变量与十来个 return 点，改成
        显式状态对象等于重写一遍控制流、再靠测试证明它没变；生成器让**同一份代码**在
        ``yield`` 处暂停，局部变量原地保留，事件序、写序、消息序逐字节不变（全量套件在
        严格派生下就是证明）。代价是驱动对象一次性：生成器抛过异常就不能再 ``step()``。
        """

        return EpisodeDrive(
            self._drive_owned(
                task_frame=task_frame,
                context=context,
                registry=registry,
                _continuation_sink=_continuation_sink,
            )
        )

    def _drive_owned(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[_EpisodeContinuationState] | None = None,
    ) -> Generator[StepPoint, None, AgentOutcome]:
        episode_id = context.contract.task_id.strip()
        with self._control_writer(episode_id):
            if self._store is not None:
                events, state = self._store.load(episode_id)
                if events or state is not None:
                    raise RestoreUnavailable(f"{episode_id}: existing episode requires recovery, not a fresh run")
            try:
                return (yield from self._drive(
                    task_frame=task_frame, context=context, registry=registry,
                    _continuation_sink=_continuation_sink,
                ))
            except BaseException:
                if self._active_inbox is not None:
                    self._active_inbox.suspend()
                self._active_inbox = None
                raise
            finally:
                if self._active_inbox is not None:
                    self._active_inbox.suspend()

    def _drive(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[_EpisodeContinuationState] | None = None,
    ) -> Generator[StepPoint, None, AgentOutcome]:
        # EpisodeScope 在这里构造——这是 Episode 的入口，contract、注册表、
        # 身份都齐了。第 3 步把接缝接到了执行路径上，但生产链路一直没人构造 Scope，
        # 于是事件、调用登记和 dump 收据在生产里都不发生（机制休眠）。
        #
        # episode_id 用 context.contract.task_id：这是仓内既有约定
        # （glm_agent_runtime.py:481、openai_agents_runtime.py:1006 都这么取），
        # 不另发明第二种 Episode 身份。
        #
        # event_sink 接 Live 车道（第 5 步第 2 条，检阅裁定 D3）：工具阶段事件
        # ``tool/*`` 走实时出口，**不进 ledger.events、不占 durable sequence**，
        # 分类由 ``episode_event_lanes`` 那张单表说了算。durable 侧的
        # ``tool_request``/``tool_result``/``tool_error`` 一字未动，仍是对账权威。
        #
        # 只在真有下游 sink 时才挂：否则 ``dump()`` 的 ``event_sink_attached``
        # 会在没人接收时报 True——收据不说谎优先于形式上"接线了"。
        #
        # Scope 内的副本不能约束还持有原 registry 的消费者；先绑定本地引用，
        # 再生成配置快照、绑 episode 工具、拼提示词与播种账本。
        registry = registry.for_context(context)
        # 证据账本要在绑 sub_research 之前建：分支证据经它的 branch_sink 进父账本。
        # 建得早不改任何事件——它只依赖 context。
        evidence_ledger = EvidenceLedger(
            information_cutoff=context.information_cutoff.as_of_date,
        )
        for required in context.contract.required_outputs:
            if required.required and required.grounding_mode == "evidence":
                evidence_ledger.open_gap(required.output_id)
        context_ref = _ContextRef(context)
        # 配置快照先于 task（G6）：恢复只读它，不读活对象。快照在绑 sub_research 之前
        # 算——那一步需要 ledger 已存在；sub_research 的在场只记一个布尔位。
        ledger = _EpisodeLedger(
            task_frame,
            event_sink=self._event_sink,
            store=self._store,
            episode_id=context.contract.task_id,
            configure=self._configure_snapshot(context=context, registry=registry),
            on_store_failure=lambda: self._cancel.request("hook", "storage_failed"),
        )
        ledger.active_context = context
        # INV-R5：收件箱在账本之后、任何模型请求之前建好——从此外部输入只有这一扇门。
        # 收不收由 harness 判（§5 第 2 条接触点）；子研究回灌也走它（§6.4 第 3 条）。
        # 落盘的 store 顺带给箱子一个跨进程投递槽（CLI steer，工单 #30 第 5 条）；内存 store 没有。
        inbox = Inbox(
            ledger,
            admit=self._harness.admit_inbox_message,
            spool=spool_dir_for(self._store, ledger.episode_id),
            persistence_failed=lambda: bool(ledger.store_failures),
        )
        ledger.inbox = inbox
        self._active_inbox = inbox
        # 研究进展账要在绑 episode 工具之前建：分支结果在批执行器线程里回来时直接记进它。
        progress = ResearchProgressTracker()
        registry = self._with_episode_bound_tools(
            task_frame=task_frame,
            context_ref=context_ref,
            registry=registry,
            evidence_ledger=evidence_ledger,
            ledger=ledger,
            progress=progress,
        )
        # Dynamic tools are now bound; configure intentionally predates them.
        # Recovery authority must describe this actual registry, not its summary.
        ledger.active_registry = registry
        episode_scope = EpisodeScope(
            episode_id=context.contract.task_id,
            # 用户身份不在本层：memory 身份是装配期输入（build_episode_registry
            # 的 memory_user），运行器拿不到也不该拿。留空是如实陈述，不是占位。
            user_id="",
            context=context,
            registry=registry,
            event_sink=(
                LiveEventSink(self._event_sink)
                if self._event_sink is not None
                else None
            ),
        )
        tool_session = self._tool_executor.new_session(scope=episode_scope)
        # INV-R2：工具意图出口。批次执行器在 ``_dispatch`` 之前把真要跑的调用整批交给它，
        # ledger 落 ``tool_request{replay}`` 并把程序计数器推到 ``tools_pending``。
        tool_session.on_dispatch = ledger.record_dispatch_intent
        tool_session.execution_failed = lambda: bool(ledger.store_failures)
        # INV-R1 对账失败落进 Scope 收据（dump()["derive_mismatches"]）。
        ledger.derive_mismatch_sink = episode_scope.record_derive_mismatch
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")

        llm_calls = 0
        tool_calls = 0
        invalid_actions = 0
        finish_repairs: set[str] = set()
        plan_failures = 0
        plan_turns = 0
        perspective_checkpoint_sent = False
        system, user = self._harness.assemble_prompt(task_frame, context, registry)
        # SYSTEM_PROMPT_DYNAMIC_BOUNDARY: system is byte-stable; user/tool
        # rebuild each turn. cache_control is not implemented this increment.
        _ = SYSTEM_PROMPT_DYNAMIC_BOUNDARY
        # 模型可见即已落账：system 与首轮 user 先进 durable 事件，再进 messages。
        record_prompt_assembled(ledger, system=system, user=user)
        messages: list[EpisodeMessage] = [system_message(system), user_message(user)]
        initial_evidence_snapshot = evidence_ledger.snapshot()
        accumulator = _EpisodeToolAccumulator(
            messages=messages,
            ledger=ledger,
            evidence_ledger=evidence_ledger,
            harness=self._harness,
            progress=progress,
        )
        ledger.active_evidence_ledger = evidence_ledger
        ledger.presented_evidence = accumulator.evidence
        _seed_prior_evidence(accumulator, messages, context)
        _seed_opening_prefetch(accumulator, messages, registry)
        # First checkpoint includes opening evidence before any model effect.
        ledger.put_state(phase="planning", context=context)
        continuation_state: _EpisodeContinuationState | None = None
        if _continuation_sink is not None:
            continuation_state = _EpisodeContinuationState(
                task_frame=task_frame,
                context=context,
                registry=registry,
                tool_session=tool_session,
                messages=messages,
                ledger=ledger,
                accumulator=accumulator,
                evidence_ledger=evidence_ledger,
                initial_evidence_snapshot=initial_evidence_snapshot,
                episode_scope=episode_scope,
                context_ref=context_ref,
            )
            _continuation_sink.append(continuation_state)
        finalization_started = False
        mode_decided = False
        # max_steps counts finance-tool calls. Valid PLAN-only turns are
        # added on top of that bounded research budget.
        for _round in range(
            1,
            MAX_EPISODE_TOOL_CALLS + MAX_PLAN_TURNS + 2,
        ):
            if ledger.store_failures:
                return self._stopped_outcome(
                    task_frame=task_frame, status="failed", stop_reason="storage_failed",
                    gap="恢复记录保存失败", ledger=ledger,
                    evidence=accumulator.evidence, traces=accumulator.traces,
                    gaps=accumulator.gaps, llm_calls=llm_calls, tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            if self._is_cancelled():
                return self._cancelled_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            # 首轮向 reserve 借超出「一次合成」的余量：那时一条证据都没有，
            # reserve 保护的对象还不存在，而预扣会让唯一能启动检索的调用饿死。
            # 开场超时只看「模型还没跑、工具还没成功」。harness 预取会先把
            # 观察值放进 accumulator.evidence，但不能因此取消首轮向 reserve 借窗。
            is_opening_call = llm_calls == 0 and not accumulator.successful_tools
            planning_timeout = (
                self._opening_planning_timeout(context)
                if is_opening_call
                else self._followup_planning_timeout(context)
            )
            remaining_tool_slots = self._remaining_tool_slots(
                context=context,
                tool_calls=tool_calls,
            )
            should_finalize = (
                finalization_started
                or remaining_tool_slots <= 0
                or planning_timeout < MIN_PLANNING_TURN_SECONDS
                or (_round - plan_turns) > self._model_round_budget(context)
            )
            if should_finalize and not finalization_started:
                finalization_started = True
                if remaining_tool_slots <= 0:
                    finalization_reason = "tool_budget_exhausted"
                elif planning_timeout < MIN_PLANNING_TURN_SECONDS:
                    finalization_reason = "retrieval_deadline_closed"
                else:
                    finalization_reason = "model_round_budget_exhausted"
                self._begin_finalization(
                    messages=messages,
                    ledger=ledger,
                    reason=finalization_reason,
                )

            remaining_seconds_at_entry = context.deadline.remaining()
            timeout = (
                context.deadline.synthesis_timeout(self._turn_ceiling(context))
                if finalization_started
                else planning_timeout
            )
            if timeout <= 0.001:
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="deadline_exhausted",
                    gap="研究截止时间已到，仍有必需输出未覆盖",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            # INV-R5：每次模型请求前认领 next_step（pi steering）。先于历史折叠——
            # 认领的是 user 消息，折叠只碰 tool 消息，两者互不改写；先于对账是必然。
            if self._claim_inbox(
                messages=messages, ledger=ledger, target="next_step",
                accumulator=accumulator,
            ):
                # 外部递了话（用户改方向 / 分支回灌）：新方向的第一批不算原地踏步。
                accumulator.progress.note_external_input()
            perspective_checkpoint = (
                not finalization_started
                and not perspective_checkpoint_sent
                and plan_turns < MAX_PLAN_TURNS
                and tool_calls > 0
                and needs_perspective_checkpoint(
                    ledger.plan, research_tier=context.policy.tier,
                )
            )
            if perspective_checkpoint:
                perspective_checkpoint_sent = True
                append_model_input(
                    messages, ledger,
                    content=perspective_checkpoint_message(ledger.plan),
                    source="adaptive_research_checkpoint",
                )
            # 历史折叠先于对账：它改的是模型即将看到的 tool 消息正文，并以
            # ``history_compacted`` 事件承载替换后的正文，所以对账必须在它之后。
            self._compact_history_for_model(
                messages=messages,
                accumulator=accumulator,
                ledger=ledger,
                llm_calls=llm_calls,
            )
            # INV-R1：请求前对账。放在 try 之外——严格模式的 DerivationMismatch 是
            # 测试要看见的红，不能被下面那个「模型异常」的 except 吞成 model_error。
            ledger.verify_model_visible(messages)
            # INV-R2：模型请求前的意图（含预留 turn_id）。菜单在意图之前算——它只读状态，
            # 不是外部效果；``tool_menu`` 事件因此仍先于 ``model_intent``。
            definitions = (
                [] if finalization_started or perspective_checkpoint else self._available_tool_definitions(
                    tool_session=tool_session,
                    registry=registry,
                    context=context,
                    ledger=ledger,
                )
            )
            turn_id = ledger.record_model_intent(
                timeout_asked=timeout,
                phase="finalizing" if finalization_started else "planning",
                # 主循环没有瞬态重试；崩溃恢复允许把这一问**再发一次**（结果丢了、
                # 请求本身是只读的）。
                retries_remaining=1,
                context=context,
            )
            # P4 步点①：意图已 durable、结算未发——INV-R2 的「不确定窗口」入口。
            yield StepPoint("model_pending", llm_calls, tool_calls, turn_id=turn_id)
            model_started = monotonic()
            suspend_anchor = host_suspended_total()
            try:
                # 线格式只在这里出现：loop 全程 EpisodeMessage，边界一次转换。
                turn = ledger.model_complete(
                    self._model,
                    messages=to_provider(messages),
                    tools=[] if finalization_started else definitions,
                    timeout=timeout,
                )
            except Exception as exc:
                budget_remaining = _consume_root_seconds(
                    context,
                    max(0.0, monotonic() - model_started),
                )
                llm_calls += 1
                if not budget_remaining:
                    ledger.add(
                        "model_error",
                        {"reason": f"model_exception:{type(exc).__name__}", "turn_id": turn_id},
                    )
                    return self._stopped_outcome(
                        task_frame=task_frame,
                        status="partial" if accumulator.evidence else "failed",
                        stop_reason="deadline_exhausted",
                        gap="研究截止时间已到，仍有必需输出未覆盖",
                        ledger=ledger,
                        evidence=accumulator.evidence,
                        traces=accumulator.traces,
                        gaps=accumulator.gaps,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                reason = f"model_exception:{type(exc).__name__}"
                ledger.add("model_error", {"reason": reason, "turn_id": turn_id})
                if (
                    not finalization_started
                    and self._can_recover_finalization(
                        context=context,
                        evidence=accumulator.evidence,
                    )
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="planning_model_unavailable",
                    )
                    continue
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
                        registry=registry,
                        failure_reason=reason,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="model_unavailable",
                    gap=reason,
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            model_elapsed = max(0.0, monotonic() - model_started)
            opening_tool_context = None
            if is_opening_call and _round == 1 and not finalization_started and turn.tool_calls and not turn.error:
                opening_tool_context = self._handoff_opening_budget(
                    context=context, ledger=ledger, model_started=model_started,
                    model_timeout=timeout, model_elapsed=model_elapsed,
                )
            llm_calls += turn.provider_attempts
            # 与 repair_reentry 对齐：asked / configured / 入场残余必须落在
            # 同一条 model_turn 上。2026-08-16 L01 首轮合成 TimeoutError 墙钟
            # 68.3s，payload 没有 asked，H2（75s 硬墙 vs 研究窗残余）判不了。
            # 不在这里编造 input_tokens：provider 没回就保持缺席。
            ledger.add(
                "model_turn",
                {
                    **turn.to_dict(),
                    # 结算复用意图预留的关联 id（INV-R2）。
                    "turn_id": turn_id,
                    "timeout_asked": float(timeout),
                    "timeout_configured": float(self._llm_timeout),
                    "remaining_seconds_at_entry": float(
                        remaining_seconds_at_entry
                    ),
                    # 预算按 monotonic 计，主机睡眠（合盖）时停走、醒来接着算。
                    # 2026-09-27 deploy-probe：两条事件墙钟隔 2320s、预算只走 75s，
                    # 被当成连接卡死 38 分钟去查——其实主机睡了 2253s。
                    "host_suspended_seconds": host_suspended_since(suspend_anchor),
                },
            )
            if not turn.tool_calls and not turn.error:
                # 写作轮（没点工具的模型轮）超出研究额度的部分从合成保留的余量里出。
                # 账本 initial_seconds = total − reserve 是研究额度，reserve 本就是留给
                # 写结论的钱，但此前写作轮照样从研究额度扣：2026-09-08 GLM 思考臂
                # max 档 reserve 抬到 240 后研究额度缩到 360，写作 181s 一到账本就溢出、
                # 墙钟还剩 167s 却报 deadline_exhausted（收据 glm-ceiling-20260907 §7）。
                # 只铸差额、不铸整段：sol 写作 15–40s 研究额度盖得住 → 一笔不铸、账本
                # 逐字节同前；余量尽量留给修复（修复也从同一段余量铸）。
                self._grant_writing_shortfall(
                    context=context,
                    ledger=ledger,
                    elapsed=model_elapsed,
                    llm_calls=llm_calls,
                )
            # P4 步点②：模型结算刚落，下一件外部效果（派发 / 收口）还没开始。
            yield StepPoint("model_settled", llm_calls, tool_calls, turn_id=turn_id)
            if ledger.store_failures:
                if not _consume_root_seconds(context, model_elapsed) and context.root_budget is not None:
                    context.root_budget.settle_seconds(seconds=model_elapsed)
                carried = self._carry_just_written_finish(
                    turn=turn, context=context, evidence=tuple(accumulator.evidence), registry=registry,
                )
                return self._stopped_outcome(
                    task_frame=task_frame, status="failed", stop_reason="storage_failed",
                    gap="恢复记录保存失败", ledger=ledger,
                    evidence=accumulator.evidence, traces=accumulator.traces,
                    gaps=accumulator.gaps, llm_calls=llm_calls, tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    carried_draft=carried.draft if carried is not None else "",
                    carried_bindings=carried.bindings if carried is not None else (),
                )
            if not _consume_root_seconds(context, model_elapsed):
                if context.root_budget is not None:
                    context.root_budget.settle_seconds(seconds=model_elapsed)
                carried = self._carry_just_written_finish(
                    turn=turn,
                    context=context,
                    evidence=tuple(accumulator.evidence),
                    registry=registry,
                )
                carried_draft = carried.draft if carried is not None else ""
                carried_bindings = carried.bindings if carried is not None else ()
                if carried is not None and carried_draft:
                    # 此前这里会再校验一次并用**不带 draft** 的展开覆盖 bindings，
                    # 把比较集展开丢掉；现在与其它四处终局门同一份 admission。
                    assert carried.status is not None
                    return self._stopped_outcome(
                        task_frame=task_frame,
                        status=carried.status,
                        stop_reason="model_finish",
                        gap="",
                        ledger=ledger,
                        evidence=accumulator.evidence,
                        traces=accumulator.traces,
                        gaps=list(carried.gaps),
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                        carried_draft=carried_draft,
                        carried_bindings=carried_bindings,
                    )
                # R-20260828-06：LLM 这轮已经发生，tool_calls 是产出。
                # 丢掉等于编译完把查询扔掉。flush 后停机，不发明稿、不开下一轮。
                if (
                    turn.tool_calls
                    and not finalization_started
                    and not self._is_cancelled()
                ):
                    tool_calls, invalid_actions = self._flush_pending_tools(
                        turn=turn,
                        tool_session=tool_session,
                        registry=registry,
                        context=context,
                        accumulator=accumulator,
                        model_elapsed=model_elapsed,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="deadline_exhausted",
                    gap="研究截止时间已到，仍有必需输出未覆盖",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    carried_draft=carried_draft,
                    carried_bindings=carried_bindings,
                )
            if self._is_cancelled():
                return self._cancelled_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            if turn.error:
                ledger.add("model_error", {"reason": turn.error, "turn_id": turn_id})
                if (
                    not finalization_started
                    and self._can_recover_finalization(
                        context=context,
                        evidence=accumulator.evidence,
                    )
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="planning_model_unavailable",
                    )
                    continue
                if self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
                        registry=registry,
                        failure_reason=turn.error,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="model_unavailable",
                    gap=turn.error,
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            messages.append(self._assistant_message(turn))
            # Once finalization starts, PLAN is no longer a valid model
            # response.  Let the existing terminal validator/recovery path
            # handle it as an invalid finish instead of accepting it and
            # silently skipping the recovery state machine.
            # PLAN 识别与修订合法性归 harness；PLAN-only 轮的次数闸归 loop。
            plan_result = (
                self._harness.interpret_plan(
                    turn.content,
                    previous_plan=ledger.plan,
                    task_id=context.contract.task_id,
                )
                if not finalization_started
                else PlanParseResult(None, "")
            )
            pending_mode_message: ModeGovernance | None = None
            pending_branch_result: SubResearchResult | None = None
            if plan_result.plan is not None:
                if not turn.tool_calls:
                    if plan_turns >= MAX_PLAN_TURNS:
                        plan_result = PlanParseResult(
                            None,
                            "PLAN revision allowance exhausted",
                        )
                    else:
                        plan_turns += 1
                        ledger.record_plan(plan_result.plan)
                        progress.record_plan(
                            plan_result.plan,
                            evidence=tuple(accumulator.evidence),
                        )
                        if not mode_decided:
                            context, pending_mode_message = self._decide_mode(
                                task_frame=task_frame,
                                plan=plan_result.plan,
                                context=context,
                                ledger=ledger,
                                continuation_state=continuation_state,
                                context_ref=context_ref,
                            )
                            mode_decided = True
                        pending_branch_result = self._run_sub_research(
                            task_frame=task_frame,
                            plan=plan_result.plan,
                            decision=(
                                pending_mode_message.decision
                                if pending_mode_message is not None
                                else None
                            ),
                            context=context,
                            registry=registry,
                            ledger=ledger,
                            evidence_ledger=evidence_ledger,
                        )
                        if pending_branch_result is not None:
                            accumulator.consume_sub_research(pending_branch_result)
                            llm_calls += pending_branch_result.llm_calls
                            tool_calls += pending_branch_result.tool_calls
                        if pending_mode_message is not None:
                            self._append_mode_decision_message(
                                messages=messages,
                                ledger=ledger,
                                governance=pending_mode_message,
                            )
                        if pending_branch_result is not None:
                            self._append_sub_research_message(
                                messages=messages,
                                ledger=ledger,
                                result=pending_branch_result,
                                evidence=tuple(accumulator.evidence),
                                accumulator=accumulator,
                            )
                        continue
                else:
                    ledger.record_plan(plan_result.plan)
                    progress.record_plan(
                        plan_result.plan,
                        evidence=tuple(accumulator.evidence),
                    )
                    if not mode_decided:
                        context, pending_mode_message = self._decide_mode(
                            task_frame=task_frame,
                            plan=plan_result.plan,
                            context=context,
                            ledger=ledger,
                            continuation_state=continuation_state,
                            context_ref=context_ref,
                        )
                        mode_decided = True
                    pending_branch_result = self._run_sub_research(
                        task_frame=task_frame,
                        plan=plan_result.plan,
                        decision=(
                            pending_mode_message.decision
                            if pending_mode_message is not None
                            else None
                        ),
                        context=context,
                        registry=registry,
                        ledger=ledger,
                        evidence_ledger=evidence_ledger,
                    )
                    if pending_branch_result is not None:
                        accumulator.consume_sub_research(pending_branch_result)
                        llm_calls += pending_branch_result.llm_calls
                        tool_calls += pending_branch_result.tool_calls
            if plan_result.error:
                plan_failures += 1
                invalid_actions += 1
                ledger.add("invalid_action", {"reason": plan_result.error})
                if plan_failures == 1:
                    append_model_input(
                        messages,
                        ledger,
                        content=self._harness.steering_message(
                            "invalid_plan", detail=plan_result.error
                        ),
                        source="steering_invalid_plan",
                    )
                    continue
            if turn.tool_calls:
                if finalization_started:
                    invalid_actions += len(turn.tool_calls)
                    reason = "tool_call_during_finalization"
                    ledger.add(
                        "invalid_action",
                        {"reason": reason},
                    )
                    if self._can_recover_finalization(
                        context=context,
                        evidence=accumulator.evidence,
                    ):
                        return self._recover_finalization(
                            task_frame=task_frame,
                            context=context,
                            ledger=ledger,
                            accumulator=accumulator,
                            registry=registry,
                            failure_reason=reason,
                            llm_calls=llm_calls,
                            tool_calls=tool_calls,
                            invalid_actions=invalid_actions,
                        )
                    return self._stopped_outcome(
                        task_frame=task_frame,
                        status="partial",
                        stop_reason="invalid_model_finish",
                        gap="最终合成阶段仍尝试调用工具",
                        ledger=ledger,
                        evidence=accumulator.evidence,
                        traces=accumulator.traces,
                        gaps=accumulator.gaps,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                    )
                # P4 步点③：工具批次将派发（意图 tool_request 在 _dispatch 前由 ledger 落）。
                yield StepPoint("before_tool_dispatch", llm_calls, tool_calls, turn_id=turn_id)
                batch_started = monotonic()
                branch_event_offset = len(ledger.events)
                if opening_tool_context is not None:
                    # Keep the latest contract/permissions after mode governance.
                    # Intervening work may spend funds or tighten the parent clock.
                    root = context.root_budget
                    funded = max(0.0, float(root.remaining_seconds)) if root is not None else 0.0
                    allocated = float(getattr(root, "allocated_seconds", 0.0))
                    headroom = max(0.0, float(getattr(root, "hard_seconds_cap", allocated)) - allocated)
                    available = max(0.0, min(funded, funded + headroom - MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS))
                    opening_tool_context = replace(context, deadline=ResearchDeadline(
                        expires_at=min(
                            opening_tool_context.deadline.expires_at,
                            context.deadline.expires_at - MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS,
                            monotonic() + available,
                        ),
                    ))
                batch = tool_session.execute(
                    turn.tool_calls,
                    registry=registry,
                    context=opening_tool_context or context,
                    remaining_slots=self._remaining_tool_slots(
                        context=context,
                        tool_calls=tool_calls,
                    ),
                    is_cancelled=self._is_cancelled,
                    turn_elapsed_at_dispatch=model_elapsed,
                )
                batch_elapsed = max(0.0, monotonic() - batch_started)
                branch_llm_calls, branch_tool_calls = _tool_branch_usage(ledger.events[branch_event_offset:])
                llm_calls += branch_llm_calls
                tool_calls += batch.executed_count + branch_tool_calls
                invalid_actions += accumulator.consume(batch, context)
                # Debit received work before exposing a settled step or writing
                # any finalizing checkpoint. Unknown in-flight work is still
                # not refundable/replayable merely because a snapshot exists.
                _settle_batch_calls(
                    context.root_budget,
                    executed_count=batch.executed_count,
                    batch_elapsed=batch_elapsed,
                )
                # P4 步点④：这一批的结算（tool_result / tool_error）全部落账。
                yield StepPoint("tools_settled", llm_calls, tool_calls, turn_id=turn_id)
                halt = self._harness.halt_after_tool_batch(
                    context=context,
                    batch_errors=tuple(item.error for item in batch.items),
                )
                if halt and not finalization_started:
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason=halt,
                    )
                fallback = self._maybe_execute_empty_pool_fallback(
                    batch=batch,
                    tool_session=tool_session,
                    registry=registry,
                    context=context,
                    accumulator=accumulator,
                    tool_calls=tool_calls,
                    model_elapsed=model_elapsed,
                )
                if fallback is not None:
                    fb_batch, extras, fb_elapsed = fallback
                    tool_calls += fb_batch.executed_count
                    invalid_actions += accumulator.consume(
                        fb_batch,
                        context,
                        request_extras=extras,
                    )
                    _settle_batch_calls(
                        context.root_budget,
                        executed_count=fb_batch.executed_count,
                        batch_elapsed=fb_elapsed,
                    )
                progress_view = self._research_progress_view(
                    accumulator=accumulator,
                    tool_session=tool_session,
                    registry=registry,
                    context=context,
                )
                injected = self._append_tool_budget_state(
                    messages=messages,
                    ledger=ledger,
                    remaining_seconds=(
                        context.deadline.remaining()
                        if budget_status_enabled()
                        else None
                    ),
                    total_seconds=(
                        float(context.policy.total_seconds)
                        if budget_status_enabled()
                        else None
                    ),
                    remaining_slots=max(
                        0,
                        self._remaining_tool_slots(
                            context=context,
                            tool_calls=tool_calls,
                        ),
                    ),
                    per_batch_cap=batch_call_cap(context.policy),
                    progress=progress_view,
                    question_type=context.contract.question_type,
                )
                if injected:
                    ledger.time_budget_injected = True
                if pending_mode_message is not None:
                    self._append_mode_decision_message(
                        messages=messages,
                        ledger=ledger,
                        governance=pending_mode_message,
                    )
                if pending_branch_result is not None:
                    self._append_sub_research_message(
                        messages=messages,
                        ledger=ledger,
                        result=pending_branch_result,
                        evidence=tuple(accumulator.evidence),
                        accumulator=accumulator,
                    )
                if self._harness.retrieval_complete(
                    context=context,
                    registry=registry,
                    successful_tools=accumulator.successful_tools,
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="snapshot_surface_satisfied",
                    )
                # 停滞收口（06 号单）：连续 N 批零新证据且已有证据在手，研究阶段关门。
                # 关门前模型已连续两轮看到 stalled 建议与「再一批就收口」的预告；
                # 已有证据一条不丢，收口只是不再让它原地重复调用。
                if (
                    not finalization_started
                    and progress_view is not None
                    and accumulator.progress.should_finalize()
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="research_stalled",
                    )
                # 这一批的结算全部落下、无在飞外部效果：程序计数器回到规划 / 收口。
                ledger.put_state(
                    phase="finalizing" if finalization_started else "planning",
                    context=context,
                )
                continue

            # INV-R5：模型停下（无工具调用）且还没收口——箱里有话就不结束，把 next_turn
            # （pi follow-up）连同此刻已到的 next_step 一起认领，再给模型一轮。模型刚写的
            # 终局留在历史里当普通 assistant 消息；下一轮它对着新话重新给终局。
            # 收口阶段不认领：episode 正按预算关门，留到 finish 统一 discarded。
            # 竞态「steer 到达 vs 模型停下」两序在这里汇合：先到的在请求前就被认领，
            # 后到的在这里被认领——两种历史都合法，都不丢话。
            if not finalization_started and ledger.inbox is not None and ledger.inbox.pending():
                self._claim_inbox(
                    messages=messages, ledger=ledger, target="next_turn",
                    accumulator=accumulator,
                )
                self._claim_inbox(
                    messages=messages, ledger=ledger, target="next_step",
                    accumulator=accumulator,
                )
                continue

            admission = self._harness.admit_finish(
                turn.content,
                context=context,
                evidence=tuple(accumulator.evidence),
                registry=registry,
            )
            if not admission.accepted:
                invalid_actions += 1
                reason = admission.reason
                response = admission.response
                assert response is not None
                # 病因与类别进收据：此前只留一句自由文本 reason，事后无法按类
                # 归并，`synthesis_health` 那 59% 「口径未知」就是从这里开始的。
                rejection = admission.rejection
                ledger.add(
                    "invalid_action",
                    {
                        "reason": reason,
                        "code": rejection["rejection_code"],
                        "kind": admission.kind,
                        "disposition": response.stop_reason,
                    },
                )
                if (
                    response.reinject
                    and admission.repair_steering_kind not in finish_repairs
                    and not finalization_started
                ):
                    finish_repairs.add(admission.repair_steering_kind)
                    append_model_input(
                        messages,
                        ledger,
                        content=self._harness.steering_message(
                            admission.repair_steering_kind, detail=reason
                        ),
                        source="steering_invalid_finish",
                    )
                    continue
                if response.allow_recovery and self._can_recover_finalization(
                    context=context,
                    evidence=accumulator.evidence,
                ):
                    return self._recover_finalization(
                        task_frame=task_frame,
                        context=context,
                        ledger=ledger,
                        accumulator=accumulator,
                        registry=registry,
                        failure_reason=reason,
                        llm_calls=llm_calls,
                        tool_calls=tool_calls,
                        invalid_actions=invalid_actions,
                        candidate_content=turn.content,
                    )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial",
                    stop_reason="invalid_model_finish",
                    gap="模型未能返回可验证的结构化终止结果",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    **rejection,
                )

            assert admission.status is not None
            status, draft = admission.status, admission.draft
            bindings = admission.bindings
            current_gaps = accumulator.retain_entity_diagnostics(admission.gaps)
            # P4 步点⑤：终局已获准入、finish 事件将落（其它停机路径经 _stopped_outcome /
            # _cancelled_outcome / _recover_finalization 直接返回，不设步点）。
            yield StepPoint("before_finish", llm_calls, tool_calls, turn_id=turn_id)
            ledger.record_runtime_result()
            ledger.add(
                "finish",
                {
                    "status": status,
                    "stop_reason": "model_finish",
                    "bindings": [item.to_dict() for item in bindings],
                    "gaps": list(current_gaps),
                    "caveat_slips": admission.caveat_slips,
                    **admission.rejection,
                },
            )
            return ledger.outcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=status,
                draft=draft,
                evidence=tuple(accumulator.evidence),
                traces=tuple(accumulator.traces),
                gaps=current_gaps,
                stop_reason="model_finish",
                events=tuple(ledger.events),
                bindings=bindings,
                usage=_agent_usage(
                    ledger,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                ),
                plan=ledger.plan,
            )

        return self._stopped_outcome(
            task_frame=task_frame,
            status="partial",
            stop_reason="step_exhausted",
            gap="研究预算已耗尽，仍有必需输出未覆盖",
            ledger=ledger,
            evidence=accumulator.evidence,
            traces=accumulator.traces,
            gaps=accumulator.gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
        )

    def _repair_model_complete(
        self,
        *,
        messages: list[EpisodeMessage],
        accumulator: _EpisodeToolAccumulator,
        tools: list[dict[str, object]],
        timeout: float,
        repair_deadline: ResearchDeadline,
        repair_context: ResearchRunContext,
        goal: RepairGoal,
        ledger: _EpisodeLedger,
        phase: str,
        llm_calls: int,
        transient_retries_left: int,
    ) -> tuple[
        ModelTurn,
        int,
        bool,
        ResearchDeadline,
        ResearchRunContext,
        int,
    ]:
        """修复轮的一次模型调用：瞬态错误最多补救 ``_TRANSIENT_RETRY_LIMIT`` 次。

        两条补救路径，熔断共用：

        1. repair deadline 还有余量（502/断连这种快速失败）——用余量重问价；
        2. 余量被 TimeoutError 烧穿，但 root hard-cap 还有未分配秒数——再铸
           一笔 ``grant_for_transient_model_retry``，用新窗口重问价。
           「烧穿」包括耗时略超账本残余、``consume_seconds`` fail closed
           一分未扣的情形：先 ``settle_seconds`` 结平残余再铸。

        失败 turn 的空 assistant 消息不在这里进历史。
        """

        while True:
            # INV-R5：修复轮的每次模型请求前同样认领 next_step——收件箱是唯一输入面，
            # 不因阶段而关。瞬态重试之间到的话在下一次重问价前送达。
            self._claim_inbox(
                messages=messages, ledger=ledger, target="next_step",
                accumulator=accumulator,
            )
            # INV-R1：每次重问价前都对账（瞬态重试不改 messages，但重试之间可能多了
            # repair_model_retry 事件——那不是模型可见内容，派生必须对它无感）。
            ledger.verify_model_visible(messages)
            # INV-R2：每一次重问价都是一次外部效果，各自一条意图；捕获的重试余量就是
            # 修复轮此刻还剩的瞬态补救次数。
            turn_id = ledger.record_model_intent(
                timeout_asked=timeout,
                phase=phase,
                retries_remaining=transient_retries_left,
                context=repair_context,
            )
            model_started = monotonic()
            suspend_anchor = host_suspended_total()
            try:
                turn = ledger.model_complete(
                    self._model,
                    messages=to_provider(messages),
                    tools=tools,
                    timeout=timeout,
                )
            except Exception as exc:
                turn = ModelTurn(
                    "",
                    (),
                    "",
                    f"model_exception:{type(exc).__name__}",
                    provider_attempts=1,
                )
            model_elapsed = max(0.0, monotonic() - model_started)
            llm_calls += turn.provider_attempts
            ledger.add("model_turn", {
                "phase": phase, "turn_id": turn_id, **turn.to_dict(),
                "host_suspended_seconds": host_suspended_since(suspend_anchor),
            })
            budget_alive = _consume_root_seconds(repair_context, model_elapsed)
            if ledger.store_failures:
                if not budget_alive and repair_context.root_budget is not None:
                    repair_context.root_budget.settle_seconds(seconds=model_elapsed)
                return (turn, llm_calls, False, repair_deadline, repair_context, transient_retries_left)
            if (
                turn.error
                and transient_retries_left > 0
                and not self._is_cancelled()
                and is_transient_model_error(turn.error)
            ):
                retry_timeout = (
                    repair_deadline.stage_timeout(self._turn_ceiling(repair_context))
                    if budget_alive
                    else 0.0
                )
                retry_grant = None
                if retry_timeout <= 0.001 and repair_context.root_budget is not None:
                    if not budget_alive:
                        # 记账失败 = 耗时超过残余，consume fail closed 一分未扣。
                        # 先把残余结平再铸新窗；否则「恰好烧爆账本」的 turn 连
                        # 重试闸门都进不去——2026-08-13 R4 的 A6/A7 就是这个
                        # 形状，而那正是这条补救路径要救的时刻。
                        repair_context.root_budget.settle_seconds(
                            seconds=model_elapsed
                        )
                    retry_grant = grant_for_transient_model_retry(
                        goal,
                        root_budget=repair_context.root_budget,
                        # 第几次补救：账本按 (goal, attempt) 幂等去重，
                        # 不同 attempt 各铸各的满窗（帽随生效 provider p90）。
                        attempt=(
                            _TRANSIENT_RETRY_LIMIT - transient_retries_left + 1
                        ),
                        seconds_cap=self._repair_seconds_cap,
                    )
                    if retry_grant is not None:
                        budget_alive = True
                        repair_deadline = ResearchDeadline.from_timeout(
                            retry_grant.seconds_granted
                        )
                        repair_context = replace(
                            repair_context,
                            deadline=repair_deadline,
                        )
                        retry_timeout = repair_deadline.stage_timeout(
                            self._turn_ceiling(repair_context)
                        )
                if retry_timeout > 0.001:
                    transient_retries_left -= 1
                    payload: dict[str, object] = {
                        "reason": turn.error,
                        "timeout_asked": retry_timeout,
                        "retries_left": transient_retries_left,
                    }
                    if retry_grant is not None:
                        payload["grant_id"] = retry_grant.grant_id
                        payload["seconds_granted"] = retry_grant.seconds_granted
                    ledger.add("repair_model_retry", payload)
                    timeout = retry_timeout
                    continue
            return (
                turn,
                llm_calls,
                budget_alive,
                repair_deadline,
                repair_context,
                transient_retries_left,
            )

    def resume(
        self,
        state: _EpisodeContinuationState,
        previous: AgentOutcome,
        goal: RepairGoal,
    ) -> AgentOutcome:
        """Continue one captured provider history for a verifier repair goal."""

        if state.ledger.store_failures:
            return previous
        episode_id = state.ledger.episode_id
        if (state.ledger._store is not self._store
                or state.context.contract.task_id.strip() != episode_id
                or goal.episode_id != episode_id
                or previous.task_frame_hash != state.task_frame.task_frame_hash):
            raise RestoreUnavailable("repair continuation owner or task identity mismatch")
        with self._control_writer(episode_id):
            if self._store is not None:
                events, checkpoint = self._store.load(state.ledger.episode_id)
                if events != tuple(state.ledger.events) or checkpoint != state.ledger.state:
                    raise RestoreUnavailable("repair continuation no longer matches the stored episode")
            try:
                with llm_refine.writer_model_scope(
                    material_pack_writer_model(state.context.contract)
                ):
                    return self._resume_owned(state, previous, goal)
            except BaseException:
                if self._active_inbox is not None:
                    self._active_inbox.suspend()
                self._active_inbox = None
                raise
            finally:
                if self._active_inbox is not None:
                    self._active_inbox.suspend()

    def _resume_owned(
        self,
        state: _EpisodeContinuationState,
        previous: AgentOutcome,
        goal: RepairGoal,
    ) -> AgentOutcome:
        if state.ledger.store_failures:
            return previous
        context = state.context
        if state.context_ref is not None:
            state.context_ref.value = context
        ledger = state.ledger
        # INV-R5：上一轮 finish 已清箱并关箱；修复轮 episode 又活了，外部输入面随之重开。
        if ledger.inbox is not None:
            ledger.inbox.reopen()
            self._active_inbox = ledger.inbox
        accumulator = state.accumulator
        messages = state.messages
        tool_session = state.tool_session
        registry = state.registry.for_context(context)
        state.registry = registry
        task_frame = state.task_frame
        repair_seconds = max(0.0, float(goal.remaining_seconds))
        if context.root_budget is not None:
            repair_seconds = min(
                repair_seconds,
                max(0.0, float(context.root_budget.remaining_seconds)),
            )
        repair_deadline = ResearchDeadline.from_timeout(repair_seconds)
        repair_context = replace(context, deadline=repair_deadline)
        repair_tool_deadline = context.deadline.bounded_stage(repair_seconds)
        if goal.reopen_tools and repair_tool_deadline.expired:
            # 冷启动修复：主检索窗已烧穿，工具窗改用坐标器授予的窗口。
            # 「关闭的检索窗禁止工具」仍是常规修复的不变量；这里的例外由
            # admit_repair 的 grant_for_cold_restart 三道准入把关（仅 cycle 1、
            # 仅零证据、仅确实尝试过检索），模型无权自行申请。
            repair_tool_deadline = repair_deadline
        repair_tool_context = replace(context, deadline=repair_tool_deadline)
        research_tools_open = not repair_tool_deadline.expired
        goal_payload = goal.to_dict()
        # 把「这一轮结构性不可能补上」的格显式投递进 trace（#289 第 6 刀观测）。
        # W2 在观测之后接裁决：降级 contract / 模型侧 goal，但不跳过本轮——
        # salvage 刚写出的 FINAL_JSON 仍然要跑。哪些格不可达、降成什么样是领域的事。
        downgrade = self._harness.downgrade_unreachable(goal, contract=context.contract)
        if downgrade.unreachable:
            goal_payload["unreachable_without_tools"] = list(downgrade.unreachable)
        ledger.add("repair_goal", goal_payload)
        downgraded_contract, prompt_goal = downgrade.contract, downgrade.goal
        if downgraded_contract is not context.contract:
            context = replace(context, contract=downgraded_contract)
            state.context = context
            if state.context_ref is not None:
                state.context_ref.value = context
            repair_context = replace(repair_context, contract=downgraded_contract)
            repair_tool_context = replace(
                repair_tool_context,
                contract=downgraded_contract,
            )
        # 同名 runner/contract 可能在修复入口被替换：Scope 诊断与执行必须
        # 使用同一份当前注册表，不能只有 state.registry 更新、Scope 仍授权旧实现。
        rebound_scope = tool_session.bind_scope(
            registry=registry, context=repair_tool_context,
        )
        if rebound_scope is not None:
            state.episode_scope = rebound_scope
            registry = rebound_scope.registry
            state.registry = registry
            ledger.derive_mismatch_sink = rebound_scope.record_derive_mismatch
        # 修复轮的时钟账，记在动手之前。
        #
        # 这三个数是 judge 那次诊断里 ``timeout_asked`` 的同位物：judge 看着像元凶，
        # 实际 asked 已经塌到 6.67/3.33/2.07 秒——是被前面耗光的，不是配置给小了。
        # 修复轮同样是 ``min(configured, remaining)``，而 ``repair_deadline`` 的
        # ``synthesis_reserve`` 是 0，拿到的就是纯残余时钟。没有这三个数，收据里只剩
        # 一个 TimeoutError，分不清「时钟被前面吃光」还是「provider 这次真慢」。
        repair_timeout_asked = repair_deadline.stage_timeout(self._turn_ceiling(context))
        ledger.add(
            "repair_reentry",
            {
                "episode_id": goal.episode_id,
                "repair_goal_id": goal.repair_goal_id,
                "cycle": goal.cycle,
                "granted_seconds": repair_seconds,
                "timeout_asked": repair_timeout_asked,
                "timeout_configured": float(self._llm_timeout),
                "research_tools_open": research_tools_open,
                # 这一轮拿什么去冒险：失败时它是**兜底**，不再归零。
                # 修复轮自己写出合法 FINAL_JSON 时优先用新的那份
                # （_carry_repair_finish）；这里为 0 不代表失败就一定交白卷。
                "previous_draft_chars": len(previous.draft),
            },
        )
        # 上一集最后一次拒收如果从没回灌过（loop 只回灌第一次），作者进修复轮时
        # 只知道「缺哪个输出」、不知道「上次为什么被拒」，往往原样重发。
        # 此处不多花模型调用，只把账上尚未送达的那句用 harness 同一段文案补上。
        unreported = unreported_invalid_finish(previous.events)
        if unreported:
            append_model_input(
                messages,
                ledger,
                content=self._harness.steering_message(
                    "invalid_finish", detail=unreported
                ),
                source="repair_last_rejection",
            )
        append_model_input(
            messages,
            ledger,
            content=self._harness.repair_goal_message(
                prompt_goal,
                tools_open=research_tools_open,
                finish_format=claim_finish_format(downgraded_contract, prior_evidence=context.prior_evidence),
            ),
            source="repair_goal",
        )
        # 程序计数器进修复阶段；此后 deadline_at 按修复窗算。
        ledger.active_context = repair_context
        ledger.active_registry = registry
        ledger.put_state(phase="repair", context=repair_context)
        llm_calls = previous.usage.llm_calls
        tool_calls = previous.usage.tool_calls
        invalid_actions = previous.usage.invalid_actions
        timeout = repair_timeout_asked
        if timeout <= 0.001:
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="repair_deadline_exhausted",
                gap="修复阶段截止时间已到",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        definitions = (
            self._available_tool_definitions(
                tool_session=tool_session,
                registry=registry,
                context=repair_tool_context,
                ledger=ledger,
            )
            if research_tools_open
            else []
        )
        # 瞬态模型错误（超时/断连/网关 5xx）在修复轮不再一击终局。
        # 余量够就用余量重试；余量被真实 TimeoutError 烧穿则从 root hard-cap
        # 未分配余量再铸一笔（grant_for_transient_model_retry）。熔断上限见
        # _TRANSIENT_RETRY_LIMIT，两跳（repair / repair_finalize）共用。
        # 失败 turn 不进消息历史。
        transient_retries_left = _TRANSIENT_RETRY_LIMIT
        repair_expires_before = repair_deadline.expires_at
        self._compact_history_for_model(
            messages=messages,
            accumulator=accumulator,
            ledger=ledger,
            llm_calls=llm_calls,
        )
        (
            turn,
            llm_calls,
            budget_alive,
            repair_deadline,
            repair_context,
            transient_retries_left,
        ) = self._repair_model_complete(
            messages=messages,
            accumulator=accumulator,
            tools=definitions,
            timeout=timeout,
            repair_deadline=repair_deadline,
            repair_context=repair_context,
            goal=goal,
            ledger=ledger,
            phase="repair",
            llm_calls=llm_calls,
            transient_retries_left=transient_retries_left,
        )
        messages.append(self._assistant_message(turn))
        # 额外 grant 换了 repair 窗口后，工具窗口也要跟着换；否则重试若要
        # 调工具，会撞上已经烧穿的旧 bounded_stage。冷启动修复的工具窗直接
        # 跟随新授予窗口——它的旧 bounded_stage 本来就是烧穿的。
        if repair_deadline.expires_at > repair_expires_before + 0.001:
            repair_tool_context = replace(
                context,
                deadline=(
                    repair_deadline
                    if goal.reopen_tools
                    else context.deadline.bounded_stage(repair_deadline.remaining())
                ),
            )
        performed_tool_action = False
        if not budget_alive:
            carried_draft, carried_bindings = self._carry_repair_finish(
                turn=turn,
                previous=previous,
                context=context,
                evidence=tuple(accumulator.evidence),
                registry=registry,
            )
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="repair_deadline_exhausted",
                gap="修复阶段截止时间已到",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=carried_draft,
                carried_bindings=carried_bindings,
            )
        if turn.error:
            ledger.add("model_error", {"reason": turn.error})
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="repair_model_unavailable",
                gap=turn.error,
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
            )
        if turn.tool_calls:
            batch_started = monotonic()
            branch_event_offset = len(ledger.events)
            batch = tool_session.execute(
                turn.tool_calls,
                registry=registry,
                # Tool calls remain bound to the original absolute research
                # deadline. The repair deadline only governs model wording
                # and binding work after retrieval closes.
                context=repair_tool_context,
                remaining_slots=min(
                    goal.remaining_calls,
                    (
                        int(context.root_budget.remaining_calls)
                        if context.root_budget is not None
                        else goal.remaining_calls
                    ),
                ),
                is_cancelled=self._is_cancelled,
            )
            batch_elapsed = max(0.0, monotonic() - batch_started)
            branch_llm_calls, branch_tool_calls = _tool_branch_usage(ledger.events[branch_event_offset:])
            llm_calls += branch_llm_calls
            tool_calls += batch.executed_count + branch_tool_calls
            performed_tool_action = batch.executed_count > 0
            invalid_actions += accumulator.consume(batch, repair_context)
            _settle_batch_calls(
                repair_context.root_budget,
                executed_count=batch.executed_count,
                batch_elapsed=batch_elapsed,
            )
            # 修复轮的结果与预算均结算后，才把程序计数器移回 repair。
            ledger.put_state(phase="repair", context=repair_context)
            append_model_input(
                messages,
                ledger,
                content=self._harness.steering_message("repair_finalize", detail=""),
                source="steering_repair_finalize",
            )
            final_timeout = repair_deadline.synthesis_timeout(self._turn_ceiling(context))
            if final_timeout <= 0.001:
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="repair_deadline_exhausted",
                    gap="修复阶段截止时间已到",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    carried_draft=previous.draft,
                    carried_bindings=previous.bindings,
                )
            self._compact_history_for_model(
                messages=messages,
                accumulator=accumulator,
                ledger=ledger,
                llm_calls=llm_calls,
            )
            (
                turn,
                llm_calls,
                budget_alive,
                repair_deadline,
                repair_context,
                transient_retries_left,
            ) = self._repair_model_complete(
                messages=messages,
                accumulator=accumulator,
                tools=[],
                timeout=final_timeout,
                repair_deadline=repair_deadline,
                repair_context=repair_context,
                goal=goal,
                ledger=ledger,
                phase="repair_finalize",
                llm_calls=llm_calls,
                transient_retries_left=transient_retries_left,
            )
            messages.append(self._assistant_message(turn))
            if not budget_alive:
                carried_draft, carried_bindings = self._carry_repair_finish(
                    turn=turn,
                    previous=previous,
                    context=context,
                    evidence=tuple(accumulator.evidence),
                    registry=registry,
                )
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if accumulator.evidence else "failed",
                    stop_reason="repair_deadline_exhausted",
                    gap="修复阶段截止时间已到",
                    ledger=ledger,
                    evidence=accumulator.evidence,
                    traces=accumulator.traces,
                    gaps=accumulator.gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                    carried_draft=carried_draft,
                    carried_bindings=carried_bindings,
                )
        if turn.error or turn.tool_calls:
            invalid_actions += len(turn.tool_calls)
            rejection = finish_rejection_fields(
                code=(
                    "repair_model_error" if turn.error else "repair_tool_during_finish"
                ),
                reason=turn.error or "修复终止阶段仍尝试调用工具",
            )
            ledger.add(
                "invalid_action",
                {
                    "reason": rejection["rejection_reason"],
                    "code": rejection["rejection_code"],
                    "disposition": "invalid_repair_finish",
                },
            )
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="invalid_repair_finish",
                gap=turn.error or "修复终止阶段仍尝试调用工具",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
                **rejection,
            )
        admission = self._harness.admit_finish(
            turn.content,
            context=context,
            evidence=tuple(accumulator.evidence),
            registry=registry,
        )
        if not admission.accepted:
            invalid_actions += 1
            rejection = admission.rejection
            ledger.add(
                "invalid_action",
                {
                    "reason": rejection["rejection_reason"],
                    "code": rejection["rejection_code"],
                    "disposition": "invalid_repair_finish",
                },
            )
            return self._stopped_outcome(
                task_frame=task_frame,
                status="partial" if accumulator.evidence else "failed",
                stop_reason="invalid_repair_finish",
                gap="修复轮未返回可验证的 FINAL_JSON",
                ledger=ledger,
                evidence=accumulator.evidence,
                traces=accumulator.traces,
                gaps=accumulator.gaps,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                carried_draft=previous.draft,
                carried_bindings=previous.bindings,
                **rejection,
            )
        assert admission.status is not None
        bindings = admission.bindings
        verdict = self._harness.admit_repair_result(
            admission=admission,
            previous=previous,
            performed_tool_action=performed_tool_action,
        )
        stop_reason = "repair_model_finish" if verdict.progressed else "repair_model_stop"
        current_gaps = accumulator.retain_entity_diagnostics(verdict.gaps)
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": verdict.status,
                "stop_reason": stop_reason,
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(current_gaps),
                "caveat_slips": admission.caveat_slips,
                **admission.rejection,
            },
        )
        return ledger.outcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=verdict.status,
            draft=admission.draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=current_gaps,
            stop_reason=stop_reason,
            events=tuple(ledger.events),
            bindings=bindings,
            usage=_agent_usage(
                ledger,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=ledger.plan,
        )

    def _maybe_execute_empty_pool_fallback(
        self,
        *,
        batch: ToolBatchResult,
        tool_session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        accumulator: _EpisodeToolAccumulator,
        tool_calls: int,
        model_elapsed: float,
    ) -> tuple[ToolBatchResult, dict[str, Mapping[str, object]], float] | None:
        remaining = self._remaining_tool_slots(
            context=context,
            tool_calls=tool_calls,
        )
        if remaining <= 0 or accumulator.ledger.store_failures:
            return None
        # 底座只递自己拥有的事实：本批结果、此刻真能派的工具、事件流、阶段。
        # 该不该补、补什么是领域的事（harness），付不付得起（上面的剩余槛）是这里的事。
        available = frozenset(
            tool_session.available_tool_names(
                registry=registry,
                context=context,
            )
        ) | frozenset(context.contract.allowed_capabilities)
        fallback = self._harness.fallback_after_empty_batch(
            batch.items,
            context=context,
            registry=registry,
            authorized_tools=available,
            events=accumulator.ledger.events,
            in_repair=False,
        )
        if fallback is None:
            return None
        # 这一枪是应用替模型点的，模型没有说过——但下一次请求里它的 tool 消息必须有
        # assistant.tool_calls 声明，否则 OpenAI 兼容接口回 400（2026-09-09 M3 / M6 真实
        # run 第 3/4 轮就是这样失败的）。声明是模型可见内容：先落 durable 事件再进
        # messages（INV-R1），且在派发意图（tool_request）之前（声明 → 意图 → 效果）。
        record_application_tool_call(
            accumulator.messages,
            accumulator.ledger,
            call=fallback.call,
            source="empty_pool_fallback",
        )
        started = monotonic()
        extras = {fallback.call.call_id: fallback.request_extras}
        fallback_batch = tool_session.execute(
            (fallback.call,),
            registry=registry,
            context=context,
            remaining_slots=remaining,
            is_cancelled=self._is_cancelled,
            turn_elapsed_at_dispatch=model_elapsed,
            # 意图在派发前落账，领域要盖在 tool_request 上的标记得跟着意图走。
            request_extras=extras,
        )
        return (
            fallback_batch,
            extras,
            max(0.0, monotonic() - started),
        )

    def _flush_pending_tools(
        self,
        *,
        turn: ModelTurn,
        tool_session: object,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        accumulator: _EpisodeToolAccumulator,
        model_elapsed: float,
        tool_calls: int,
        invalid_actions: int,
    ) -> tuple[int, int]:
        """Dispatch tool_calls already returned by this model turn.

        remaining_slots gates *new* turns. This mailbox is already full, so
        flush even when the call ledger is at zero.
        """

        execute = getattr(tool_session, "execute", None)
        if not callable(execute) or not turn.tool_calls:
            return tool_calls, invalid_actions
        remaining = max(
            len(turn.tool_calls),
            self._remaining_tool_slots(context=context, tool_calls=tool_calls),
        )
        batch_started = monotonic()
        batch = execute(
            turn.tool_calls,
            registry=registry,
            context=context,
            remaining_slots=remaining,
            is_cancelled=self._is_cancelled,
            turn_elapsed_at_dispatch=model_elapsed,
        )
        batch_elapsed = max(0.0, monotonic() - batch_started)
        tool_calls += batch.executed_count
        invalid_actions += accumulator.consume(batch, context)
        _settle_batch_calls(
            context.root_budget,
            executed_count=batch.executed_count,
            batch_elapsed=batch_elapsed,
        )
        return tool_calls, invalid_actions

    @staticmethod
    def _remaining_tool_slots(
        *,
        context: ResearchRunContext,
        tool_calls: int,
    ) -> int:
        policy_remaining = max(0, context.policy.max_steps - tool_calls)
        root_budget = context.root_budget
        if root_budget is None:
            return policy_remaining
        return max(0, int(root_budget.remaining_calls))

    @staticmethod
    def _model_round_budget(context: ResearchRunContext) -> int:
        root_budget = context.root_budget
        if root_budget is None:
            return max(1, int(context.policy.max_steps))
        return max(1, min(MAX_EPISODE_TOOL_CALLS, root_budget.hard_calls_cap))

    def _turn_ceiling(self, context: ResearchRunContext) -> float:
        """单次模型调用上限：provider 标定的 ``llm_timeout``（生产 75s）；编号材料题包抬到
        ``MATERIAL_PACK_TURN_SECONDS``（2026-09-27 Knevo r3：强制思考首字前 62s）。其他题不变。"""

        return max(float(self._llm_timeout), material_pack_turn_seconds(context.contract))

    def _opening_planning_timeout(self, context: ResearchRunContext) -> float:
        """首轮窗口 = 常规切法 + 向 ``synthesis_reserve`` 借来的**余量**。

        借的只是 reserve 里超出「跑一次合成」所需的部分
        （``MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS``），不是整段——所以
        「到点还能交出有依据的答案」这条不变量依然成立。

        为什么首轮该借：reserve 的正当用途是保护**已查到的证据**不被写到一半
        砍掉，但首次调用时一条证据都没有，保护对象还不存在。而首轮失败是全损的
        ——那些秒数照样花掉，省下的 reserve 一秒都没用上，最终只能吐模板。

        ［实测 2026-08-08 生产 8792］turn=120s / standard / theme_analysis：
            effective = min(90, 120 − 40)   = 80
            reserve   = min(60, 80 × 2/3)   = 53.33   (episode_factory:360)
            首轮      = min(75, 80 − 53.33) = 26.67s  ← 低于 provider P50 28s
        三个 run 均 ``TimeoutError`` → 零 binding → 235B 模板答案（sha256 相同）。
        借入后：26.67 + (53.33 − 20) = 60s ≥ P95 50s。

        注意档位表**不参与**这条路径：``effective = min(tier_total, 80)``，
        80 恒为较小者，所以把 standard 从 90 调到 300 首轮一秒不变（已用探针
        验证）。��也是为什么"重标定档位表"救不了首轮。

        上界仍是 ``self._llm_timeout``（生产 75s，由 provider 特性定），与
        ``expires_at``（总共能跑多久）解耦。

        ``synthesis_reserve`` 用 ``getattr`` 读：``context.deadline`` 是鸭子类型
        注入点，测试替身只实现所需子集。上一版把新方法加在 ``ResearchDeadline``
        上，替身立刻 ``AttributeError``——这里只用替身已有的接口。
        """

        baseline = context.deadline.stage_timeout(self._turn_ceiling(context))
        reserve = float(getattr(context.deadline, "synthesis_reserve", 0.0) or 0.0)
        borrowable = max(0.0, reserve - MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS)
        if borrowable <= 0.0:
            return baseline
        return max(0.0, min(float(self._turn_ceiling(context)), baseline + borrowable))

    @staticmethod
    def _handoff_opening_budget(
        *, context: ResearchRunContext, ledger: "_EpisodeLedger",
        model_started: float, model_timeout: float, model_elapsed: float,
    ) -> ResearchRunContext | None:
        """Carry an already-authorized opening loan into its first tool batch.

        Lazy: the ordinary positive-stage path is unchanged. The loan ends at
        the ORIGINAL model window, never a fresh timeout after the model wait.
        Transfer only existing root headroom, before debit/dispatch; preserve
        the synthesis floor in both wall-clock and root accounting. No call
        grants, promotions, permission changes or follow-up/recovery re-loans.
        """
        deadline = context.deadline
        floor = MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS
        root = context.root_budget
        if (
            type(deadline) is not ResearchDeadline
            or deadline.synthesis_reserve <= floor
            or deadline.stage_timeout(model_timeout) > 0.0
            or root is None
            or ledger.store_failures
        ):
            return None
        now = monotonic()
        expires_at = min(model_started + model_timeout, deadline.expires_at - floor)
        window = max(0.0, expires_at - now)
        funded = max(0.0, float(root.remaining_seconds))
        allocated = float(getattr(root, "allocated_seconds", 0.0))
        hard_cap = float(getattr(root, "hard_seconds_cap", allocated))
        headroom = max(0.0, hard_cap - allocated)
        window = min(window, max(0.0, funded + headroom - model_elapsed - floor))
        if window <= 0.001:
            return None
        needed = max(0.0, model_elapsed + window - funded)
        if needed > 1e-9:
            grant = BudgetGrant(
                grant_id=f"opening-handoff-{context.contract.task_id}",
                episode_id=context.contract.task_id, cycle=0,
                calls_granted=0, seconds_granted=needed,
            )
            grant_fn = getattr(root, "grant", None)
            if not callable(grant_fn) or not grant_fn(grant):
                return None
        child_deadline = ResearchDeadline(expires_at=min(expires_at, now + window))
        ledger.add("opening_budget_handoff", {
            "model_elapsed": model_elapsed, "seconds_granted": needed,
            "tool_window_seconds": window, "expires_at": child_deadline.expires_at,
            "synthesis_floor_seconds": floor,
            "parent_expires_at": deadline.expires_at,
            "parent_remaining_at_handoff": deadline.remaining(),
        })
        return replace(context, deadline=child_deadline)

    def _followup_planning_timeout(self, context: ResearchRunContext) -> float:
        """证据到手后的规划窗：预扣后不够一次写作时，向 reserve 借到地板。

        常规切法是 ``remaining − synthesis_reserve``。8796 第三次调用
        remaining=72.27、reserve=60 → 只剩 12.27s，低于一次合成地板
        （``MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS`` = 20s），写作超时；
        同题 8792 实测写作 15.9s。借到地板，不把整段 reserve 交给还可能
        再调工具的规划轮——第二次工具轮仍走 stage 切法。

        不变量：借完之后至少还留一截合成地板（``remaining − grant ≥ floor``），
        与首轮「只借余量」对称。
        """

        baseline = context.deadline.stage_timeout(self._turn_ceiling(context))
        floor = MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS
        if baseline + 1e-9 >= floor:
            return baseline
        remaining = float(context.deadline.remaining())
        protected = max(0.0, remaining - floor)
        return max(0.0, min(float(self._turn_ceiling(context)), max(baseline, min(floor, protected))))

    def _decide_mode(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
        continuation_state: _EpisodeContinuationState | None,
        context_ref: _ContextRef | None = None,
    ) -> tuple[ResearchRunContext, ModeGovernance]:
        # 深度裁决归 harness；loop 只说自己能不能开分支，然后把裁决落账（底座）、
        # 记事件、换 context。
        governance = self._harness.govern_mode(
            task_frame=task_frame,
            plan=plan,
            context=context,
            can_branch=self._sub_research_coordinator is not None,
        )
        promoted = apply_mode_promotion(context, governance.decision)
        ledger.add("mode_decision", governance.decision.to_dict())
        if continuation_state is not None:
            continuation_state.context = promoted
        if context_ref is not None:
            context_ref.value = promoted
        # 程序计数器之后按新 context 的截止算 deadline_at。
        ledger.active_context = promoted
        if promoted is not context:
            # PLAN branches can start before the next parent model/tool intent.
            # Confirm the new authority/budget BEFORE those child effects too,
            # without erasing the settled turn or its still-undispatched tools.
            position = ledger.state
            if position is None:
                raise RuntimeError("mode promotion requires an episode checkpoint")
            ledger.put_state(
                phase=position.phase, reserved_ids=position.reserved_ids,
                retry=position.retry, cancel=position.cancel, context=promoted,
            )
        return promoted, governance

    def _run_sub_research(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        decision: ModeDecision | None,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        ledger: _EpisodeLedger,
        evidence_ledger: EvidenceLedger,
    ) -> SubResearchResult | None:
        coordinator = self._sub_research_coordinator
        if (
            coordinator is None
            or decision is None
            or decision.effective_mode != "deep"
            or not plan.branch_goals
        ):
            return None
        branch_run = BranchRun(ledger.episode_id, "plan")
        self._record_branch_starts(ledger, plan.branch_goals, branch_run)
        if ledger.store_failures:
            for index, goal in enumerate(plan.branch_goals, start=1):
                ledger.add("branch_failed", {
                    "branch_id": f"branch-{index}", "goal": goal,
                    "status": "failed", "error": "storage_failed",
                    "stop_reason": "storage_failed", "llm_calls": 0, "llm_calls_known": True,
                    "episode_ref": branch_run.reference(f"branch-{index}").to_dict(),
                })
            return None
        result = coordinator.run(
            goals=plan.branch_goals,
            task_frame=task_frame,
            context=context,
            registry=registry,
            evidence_sink_factory=evidence_ledger.branch_sink,
            branch_run=branch_run,
            episode_store=self._store,
        )
        completed_ids: set[str] = set()
        for branch in result.branches:
            completed_ids.add(branch.branch_id)
            # 台账 §5.3-2：payload 里的 ``error`` 不能省——不带它，「单分支取消」在
            # 事件流里与「worker 异常失败」完全同形（同为 status=failed、gap_count=1），
            # 「cancelled 分支可区分」这条对账要求在 Projection 上根本判不出来。
            # BranchResult.error 无错时是空串，照抄即可，不另造 cancelled 布尔位。
            # 字段清单归 ``branch_telemetry``，与 sub_research 工具的 telemetry 同源。
            ledger.add(
                (
                    "branch_completed"
                    if branch.status in {"completed", "partial"}
                    else "branch_failed"
                ),
                {
                    **branch_telemetry(branch),
                    "episode_ref": branch_run.reference(branch.branch_id).to_dict(),
                },
            )
        for index, goal in enumerate(plan.branch_goals, start=1):
            branch_id = f"branch-{index}"
            if branch_id not in completed_ids:
                ledger.add(
                    "branch_failed",
                    {
                        "branch_id": branch_id,
                        "goal": goal,
                        "status": "failed",
                        "reason": result.refused_reason or "branch_not_executed",
                        "episode_ref": branch_run.reference(branch_id).to_dict(),
                    },
                )
        return result

    def _with_episode_bound_tools(
        self,
        *,
        task_frame: TaskFrame,
        context_ref: _ContextRef,
        registry: ResearchToolRegistry,
        evidence_ledger: EvidenceLedger,
        ledger: _EpisodeLedger,
        progress: ResearchProgressTracker | None = None,
    ) -> ResearchToolRegistry:
        """把只有 episode 期才绑得出 runner 的工具并进注册表：``derived_calculation`` 与 ``sub_research``。

        两个都要这一个 episode 的证据账本，装配层（``build_episode_registry``）拿不到，
        所以在这里绑（没账本不挂）。授权仍由 contract 决定：不在 ``allowed_capabilities``
        里的工具 ``authorized_specs`` 根本不会摆给模型。

        ``derived_calculation``（spec capability-amplification §3.4）：读的是账本对象，
        模型第 N 轮算的是前 N-1 轮取到的证据。

        ``sub_research``（spec 2026-09-03）：不新建子代理，包现有协调器；前台同步、深度 1。
        没有协调器（分支里的嵌套 Episode、参考 loop）就不挂——工具不存在，而不是存在但报错。
        """

        registry = registry.with_specs(
            bind_derived_calculation_tool(
                evidence_ledger=evidence_ledger,
                # 身份由装配层折进注册表（``ResearchToolRegistry.calc_loader``）。
                # 本层只转交、不解析——EpisodeScope.user_id 恒为 "" 这条边界不动。
                # None = 装配方没给身份，走 load_calculation_record 的默认解析。
                calc_loader=getattr(registry, "calc_loader", None),
            )
        )
        # Explicit capability plus opt-in: a deployment switch is not authority.
        # Bind the presented pool, never the branch ledger or another user's run.
        if evidence_read_enabled() and "evidence_read" in context_ref.value.contract.allowed_capabilities:
            registry = registry.with_specs(bind_evidence_read_tool(
                presented_evidence=lambda: tuple(ledger.presented_evidence or ()),
            ))
        coordinator = self._sub_research_coordinator
        if coordinator is None:
            return registry

        def start(goals: tuple[str, ...], branch_run: BranchRun) -> bool:
            self._record_branch_starts(ledger, goals, branch_run)
            return not ledger.store_failures

        def record(goals: tuple[str, ...], result: SubResearchResult, branch_run: BranchRun) -> None:
            # 与 PLAN 路径同一组 durable 事件（branch_started / completed / failed），
            # 事件流的消费者不必区分分支是模型点的还是 PLAN 批的。
            self._record_branch_events(ledger, goals=goals, result=result, branch_run=branch_run)
            if progress is not None:
                # 分支状态进研究进展账（工具路径的证据本身经 tool_result 进 consume）。
                progress.record_branches(
                    result.branches, refused_reason=result.refused_reason
                )

        spec = bind_sub_research_tool(
            coordinator=coordinator,
            task_frame=task_frame,
            current_context=context_ref,
            base_registry=registry,
            evidence_ledger=evidence_ledger,
            on_start=start,
            on_result=record,
            episode_store=self._store,
        )
        return registry.with_specs(spec)

    @staticmethod
    def _record_branch_starts(
        ledger: _EpisodeLedger, goals: tuple[str, ...], branch_run: BranchRun,
    ) -> None:
        for index, goal in enumerate(goals, start=1):
            branch_id = f"branch-{index}"
            ledger.add("branch_started", {
                "branch_id": branch_id, "goal": goal, "origin": branch_run.origin,
                "episode_ref": branch_run.reference(branch_id).to_dict(),
            })

    @staticmethod
    def _record_branch_events(
        ledger: _EpisodeLedger,
        *,
        goals: tuple[str, ...],
        result: SubResearchResult,
        branch_run: BranchRun,
    ) -> None:
        completed_ids: set[str] = set()
        for branch in result.branches:
            completed_ids.add(branch.branch_id)
            ledger.add(
                (
                    "branch_completed"
                    if branch.status in {"completed", "partial"}
                    else "branch_failed"
                ),
                {
                    **branch_telemetry(branch), "origin": "tool",
                    "episode_ref": branch_run.reference(branch.branch_id).to_dict(),
                },
            )
        for index, goal in enumerate(goals, start=1):
            branch_id = f"branch-{index}"
            if branch_id not in completed_ids:
                ledger.add(
                    "branch_failed",
                    {
                        "branch_id": branch_id,
                        "goal": goal,
                        "status": "failed",
                        "reason": result.refused_reason or "branch_not_executed",
                        "origin": "tool",
                        "episode_ref": branch_run.reference(branch_id).to_dict(),
                    },
                )

    @staticmethod
    def _append_mode_decision_message(
        *,
        messages: list[EpisodeMessage],
        ledger: _EpisodeLedger,
        governance: ModeGovernance,
    ) -> None:
        append_model_input(
            messages, ledger, content=governance.message, source="mode_decision"
        )

    def _append_sub_research_message(
        self,
        *,
        messages: list[EpisodeMessage],
        ledger: _EpisodeLedger,
        result: SubResearchResult,
        evidence: tuple[AgentEvidence, ...] = (),
        accumulator: _EpisodeToolAccumulator | None = None,
    ) -> None:
        """子研究回灌走收件箱（终态稿 §6.4 第 3 条）：``inbox.send(target=next_step,
        source="sub_research")``，下一次模型请求前被认领进 messages。

        与直接 append 的差别只有一个：它成了三事实 durable 的收件箱消息（inserted /
        claimed），不再是 ``model_input``；位置从「批后立刻」挪到「下一次请求前」——
        中间若插了收口指令，回灌排在指令之后。没有收件箱的账本（旧调用方 / 替身）
        退回直接 append，事件流与 P2 相同。
        """

        content = self._harness.project_sub_research(
            branches=result.branches,
            refused_reason=result.refused_reason,
            evidence=evidence,
        )
        inbox = ledger.inbox
        if inbox is None:
            append_model_input(messages, ledger, content=content, source="sub_research")
            if accumulator is not None:
                accumulator.note_delivered_sub_research((messages[-1],))
            return
        inbox.send(user_message(content, source="sub_research"), target="next_step")

    @staticmethod
    def _available_tool_definitions(
        *,
        tool_session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
    ) -> list[dict[str, object]]:
        menu = tool_session.menu(registry=registry, context=context)
        # 每个开放工具的模型步都留实际菜单：configure 早于动态工具装配，且合同
        # 授权不等于预算/去重裁剪后的可见集合。与参照 loop 同源，UI 只投影标签。
        ledger.add("tool_menu", menu.to_payload())
        return tool_definitions_for_menu(menu, registry=registry, context=context)

    @staticmethod
    def _compact_history_for_model(
        *,
        messages: list[EpisodeMessage],
        accumulator: _EpisodeToolAccumulator,
        ledger: _EpisodeLedger,
        llm_calls: int,
    ) -> None:
        """进模型前把比最近 K 批更早的工具观察折成 E 号索引（spec 2026-09-07 §3.2）。

        就地改 ``messages``（修复轮复用同一份，所以不能只做视图），只改 tool 消息的
        ``content``；durable ``tool_result`` 事件早已落全量，这里另记一条
        ``history_compacted`` 让收据能重算模型当时看到的字数。开关缺省关，关时不碰。
        """

        if not history_compaction_enabled():
            return
        report = compact_history(
            messages,
            evidence=tuple(accumulator.evidence),
            keep_batches=history_keep_batches(),
        )
        if not report.folded:
            return
        ledger.history_compaction_folded += len(report.folded)
        ledger.history_compaction_saved += report.chars_saved
        ledger.add(
            "history_compacted",
            {**report.to_payload(), "llm_calls_before": int(llm_calls)},
        )

    @staticmethod
    def _research_progress_view(
        *,
        accumulator: _EpisodeToolAccumulator,
        tool_session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> dict[str, object] | None:
        """批后收账并算给模型看的研究进展块；开关关时返回 None（逐字节同前）。

        ``tools_short_of_window``：菜单裁剪关着（生产 ``WORKBENCH_TOOL_MENU_HIDE=off``）时，
        申报窗大于下一轮工具窗的工具仍然可见——点了必超时白烧一轮。这里把「可用但装不下」
        这个事实递给模型，而不是替它藏菜单。
        """

        if not progress_enabled():
            return None
        accumulator.progress.close_batch()
        menu = tool_session.menu(registry=registry, context=context)
        visible = set(menu.visible)
        short_of_window = [
            spec.name
            for spec in registry.authorized_specs(context.contract.allowed_capabilities)
            if spec.name in visible
            and spec.min_window_seconds is not None
            and float(spec.min_window_seconds) > float(menu.would_grant)
        ]
        return accumulator.progress.model_view(
            available_tools=menu.visible,
            tools_short_of_window=short_of_window,
        )

    @staticmethod
    def _append_tool_budget_state(
        *,
        messages: list[EpisodeMessage],
        ledger: _EpisodeLedger,
        remaining_slots: int,
        remaining_seconds: float | None = None,
        total_seconds: float | None = None,
        per_batch_cap: int | None = None,
        progress: Mapping[str, object] | None = None,
        question_type: str = "",
    ) -> bool:
        if not messages or messages[-1].role != "tool":
            return False
        content = messages[-1].content
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return False
        if not isinstance(payload, dict):
            return False
        budget: dict[str, object] = {
            "remaining_tool_calls": remaining_slots,
            "instruction": (
                "下一轮工具调用总数不得超过 remaining_tool_calls；"
                "只能调用当前菜单中仍可见的工具；证据足够时直接输出 FINAL_JSON。"
            ),
        }
        # 派发节奏（2026-09-07 收据 §10）：同题七遍里工具消息合计稳定 8–12 万字，变量是模型轮数——
        # 19 轮那遍连续 17 轮每轮只点 1 个工具，把历史重发了 96 万字、多等了 ~150s 模型往返。
        # 上面那句只是**上限**（「不得超过」），没有一句话说并行是被期待的。这里把每批帽和
        # 「一起点」写进同一条注入：改的是 harness 自己的 steering 通道，不动宪法；
        # 只剩 1 次可点时不说这话（没什么可并行的）。
        batch_now = (
            min(int(per_batch_cap), int(remaining_slots))
            if per_batch_cap is not None and per_batch_cap > 0
            else None
        )
        if batch_now is not None and batch_now > 1:
            budget["per_batch_cap"] = batch_now
            budget["instruction"] = (
                str(budget["instruction"])
                + f"互不依赖的工具应在同一轮一起点出（本轮最多 {batch_now} 个）："
                "一轮只点一个会多花一轮模型往返并重发整段上下文；"
                "只有下一步取决于上一步结果时才逐轮点。"
            )
        # Steps were already exposed here; *time* was gated off.  Bookgap S1
        # turns the clock on in the same payload so the model does not hunt
        # for a second budget channel.  The CJK status_line is the v1
        # status-bar row; numbers stay in fields for eval.
        injected = False
        if remaining_seconds is not None and total_seconds and total_seconds > 0:
            remaining = max(0.0, remaining_seconds)
            fraction = max(0.0, min(1.0, remaining / total_seconds))
            percent = int(round(fraction * 100))
            budget["remaining_seconds"] = round(remaining, 1)
            budget["remaining_fraction"] = round(fraction, 2)
            budget["status_line"] = (
                f"[预算] 时间 剩 {remaining:.0f} 秒 / 总 {total_seconds:.0f} 秒"
                f"（{percent}%）；工具 剩 {remaining_slots} 次"
            )
            budget["instruction"] = (
                str(budget["instruction"])
                + "剩余时间充裕时可广泛探索；remaining_fraction 低于 0.3 时"
                "收敛到最有把握的方向，宁可少查也要留出写结论的时间。"
            )
            injected = True
        if progress:
            # 研究进展账（06 号单）叠在同一个预算块里：不新增事件种类、不改派生规则，
            # 模型在同一处读「还剩多少」和「刚才那批有没有新东西」。
            budget["research_progress"] = dict(progress)
        reasoning = observation_guidance(question_type)
        if reasoning:
            budget["research_reasoning"] = reasoning
        payload["runtime_budget"] = budget
        model_content = json.dumps(payload, ensure_ascii=False)
        # 这是对最后一条 tool 消息的**覆写**，不是追加：durable 侧记整段新 content，
        # 派生规则同样是覆写（INV-R1）。消息不可变，覆写 = 换一条新的。
        rewrite_last_tool_content(messages, model_content)
        record_tool_budget_state(ledger, runtime_budget=budget, model_content=model_content)
        return injected

    def _begin_finalization(
        self,
        *,
        messages: list[EpisodeMessage],
        ledger: _EpisodeLedger,
        reason: str,
    ) -> None:
        ledger.add("finalization", {"reason": reason})
        append_model_input(
            messages,
            ledger,
            content=self._harness.steering_message("begin_finalization", detail=reason),
            source="begin_finalization",
        )
        # phase 转移：从这里起模型只被要求收口（tools=[]）。恢复读到它就不再派工具。
        ledger.put_state(phase="finalizing")

    def _configure_snapshot(
        self,
        *,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> dict[str, object]:
        """``configure`` 事件 / ``EpisodeState.contract_snapshot`` 的内容（G6）。

        只放标量与哈希，不抄文本：恢复只需要「当时授权了什么、工具各自 replay 声明、
        截止与超时怎么配」。``instructions_hash`` 不在这里——system 提示词在绑完
        sub_research 之后才拼得出来，而本事件必须先于 ``task``；它的哈希由紧随其后的
        ``prompt_assembled.system_sha256`` 承载，同一事实不落两处。
        """

        contract = context.contract
        authorized = tuple(
            sorted(
                (spec.name, spec.replay)
                for spec in registry.authorized_specs(contract.allowed_capabilities)
            )
        )
        tool_contracts_hash = hashlib.sha256(
            json.dumps(authorized, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return {
            **self._runtime_config,
            "log_version": EPISODE_LOG_VERSION,
            "persistence_mode": "durable" if self._store is not None else "ephemeral",
            "task_id": contract.task_id,
            "research_tier": contract.research_tier,
            "allowed_capabilities": list(contract.allowed_capabilities),
            "authorized_tools": [name for name, _replay in authorized],
            "tool_replay": {name: replay for name, replay in authorized},
            "tool_contracts_hash": tool_contracts_hash,
            "sub_research_available": self._sub_research_coordinator is not None,
            "policy_total_seconds": float(context.policy.total_seconds),
            "policy_max_steps": int(context.policy.max_steps),
            "llm_timeout": float(self._llm_timeout),
            "repair_seconds_cap": float(self._repair_seconds_cap),
            "provider_name": provider_name_from(self._model),
            "harness": type(self._harness).__name__,
        }

    def _can_recover_finalization(
        self,
        *,
        context: ResearchRunContext,
        evidence: list[AgentEvidence],
    ) -> bool:
        materials_hook = getattr(self._harness, "finalization_materials", None)
        has_materials = bool(materials_hook(context=context)) if callable(materials_hook) else False
        return (bool(evidence) or has_materials) and (
            context.deadline.synthesis_timeout(self._turn_ceiling(context))
            >= MIN_FINALIZATION_RECOVERY_SECONDS
        )

    @staticmethod
    def _provider_attempts_from_exception(exc: Exception) -> int:
        value = getattr(exc, "provider_attempts", 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return 0
        return value

    def _recover_finalization(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        registry: ResearchToolRegistry,
        failure_reason: str,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
        candidate_content: str = "",
    ) -> AgentOutcome:
        """Attempt exactly one compact recovery and always return a terminal outcome."""

        if self._is_cancelled():
            return self._cancelled_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )
        ledger.add(
            "finalization_recovery_started",
            {"failure_reason": failure_reason},
        )
        # 兜底合成也是一次外部效果：``finalization_recovery_started`` 即其意图（INTENT_KINDS
        # 里 fsync），结算是 ``finalization_recovery_outcome``；程序计数器把它记成在飞。
        ledger.put_state(
            phase="finalizing",
            reserved_ids=("finalization_recovery",),
            context=context,
        )
        if ledger.store_failures:
            return self._failed_recovery_outcome(
                task_frame=task_frame, ledger=ledger, accumulator=accumulator,
                reason="storage_failed", public_gap="恢复记录保存失败",
                llm_calls=llm_calls, tool_calls=tool_calls, invalid_actions=invalid_actions,
            )

        def record_recovery_prompt(system: str, user: str) -> None:
            record_prompt_assembled(ledger, system=system, user=user, source=PROMPT_SOURCE_FINALIZER)
            if ledger.store_failures:
                raise RuntimeError("storage_failed")

        recovery_started = monotonic()
        suspend_anchor = host_suspended_total()
        try:
            recovery_options = {}
            materials_hook = getattr(self._harness, "finalization_materials", None)
            if callable(materials_hook):
                materials = materials_hook(context=context)
                if materials:
                    recovery_options["domain_materials"] = materials
            priority_hook = getattr(self._harness, "recovery_evidence_priority", None)
            if callable(priority_hook):
                priority = priority_hook(
                    context=context, evidence=tuple(accumulator.evidence),
                    candidate_content=candidate_content,
                )
                if isinstance(priority, tuple) and priority:
                    recovery_options["evidence_priority"] = priority
            turn = self._finalizer.recover(
                task_frame=task_frame,
                context=context,
                evidence=tuple(accumulator.evidence),
                gaps=tuple(accumulator.gaps),
                failure_reason=failure_reason,
                # 兜底合成那段独立 prompt 也是模型可见内容：落账（source=finalizer），
                # 但不进 episode 的消息历史，派生器对它跳过。
                on_prompt=record_recovery_prompt,
                **recovery_options,
            )
        except Exception as exc:
            budget_remaining = _consume_root_seconds(
                context,
                max(0.0, monotonic() - recovery_started),
            )
            llm_calls += self._provider_attempts_from_exception(exc)
            if not budget_remaining:
                return self._failed_recovery_outcome(
                    task_frame=task_frame,
                    ledger=ledger,
                    accumulator=accumulator,
                    reason="finalization_recovery_deadline_exhausted",
                    public_gap="终局恢复超出截止时间，无法生成可验证回答",
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )
            reason = f"finalization_recovery_exception:{type(exc).__name__}"
            ledger.add("model_error", {"reason": reason})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复失败，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        recovery_elapsed = max(0.0, monotonic() - recovery_started)
        llm_calls += turn.provider_attempts
        ledger.add(
            "model_turn",
            {
                "phase": "finalization_recovery", **turn.to_dict(),
                "host_suspended_seconds": host_suspended_since(suspend_anchor),
            },
        )
        if not _consume_root_seconds(context, recovery_elapsed):
            reason = "finalization_recovery_deadline_exhausted"
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复超出截止时间，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )
        if (
            context.deadline.synthesis_timeout(self._turn_ceiling(context))
            < MIN_FINALIZATION_RECOVERY_SECONDS
        ):
            reason = "finalization_recovery_deadline_exhausted"
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复超出截止时间，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )
        if turn.error:
            ledger.add("model_error", {"reason": turn.error})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=turn.error,
                public_gap="终局恢复失败，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        if turn.tool_calls:
            invalid_actions += len(turn.tool_calls)
            reason = "tool_call_during_finalization_recovery"
            ledger.add("invalid_action", {"reason": reason})
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复仍尝试调用工具，无法生成可验证回答",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            )

        admission = self._harness.admit_finish(
            turn.content,
            context=context,
            evidence=tuple(accumulator.evidence),
            registry=registry,
        )
        if not admission.accepted:
            invalid_actions += 1
            reason = admission.reason
            rejection = admission.rejection
            ledger.add(
                "invalid_action",
                {
                    "reason": reason,
                    "code": rejection["rejection_code"],
                    "disposition": "finalization_recovery_failed",
                },
            )
            return self._failed_recovery_outcome(
                task_frame=task_frame,
                ledger=ledger,
                accumulator=accumulator,
                reason=reason,
                public_gap="终局恢复未能返回可验证的结构化结果",
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
                **rejection,
            )

        assert admission.status is not None
        status, draft = admission.status, admission.draft
        bindings = admission.bindings
        current_gaps = accumulator.retain_entity_diagnostics(admission.gaps)
        ledger.add(
            "finalization_recovery_outcome",
            {"status": "recovered", "answer_status": status},
        )
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": "finalization_recovered",
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(current_gaps),
                "caveat_slips": admission.caveat_slips,
                **admission.rejection,
            },
        )
        return ledger.outcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=current_gaps,
            stop_reason="finalization_recovered",
            events=tuple(ledger.events),
            bindings=bindings,
            usage=_agent_usage(
                ledger,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=ledger.plan,
        )

    def _cancelled_outcome(
        self,
        *,
        task_frame: TaskFrame,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        # INV-R4：cancelled 终局必带类型化原因。first cause wins 由 CancelSignal 保证。
        cancel = self._cancel.snapshot()
        # 取消先 durable、再写 finish（INV-R4 的存储侧）：两者之间崩溃，恢复读到
        # state.cancel 非空就合成 cancelled 终局，而不是把用户的停当成没发生。
        ledger.put_state(
            phase=ledger.state.phase if ledger.state is not None else "planning",
            cancel=cancel,
        )
        return self._stopped_outcome(
            task_frame=task_frame,
            status="failed",
            stop_reason="cancelled",
            gap="本轮执行已取消",
            ledger=ledger,
            evidence=accumulator.evidence,
            traces=accumulator.traces,
            gaps=accumulator.gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
            finish_extra={
                "cancel_cause": cancel["cause"],
                "cancel_detail": cancel["detail"],
            },
        )

    @staticmethod
    def _failed_recovery_outcome(
        *,
        task_frame: TaskFrame,
        ledger: _EpisodeLedger,
        accumulator: _EpisodeToolAccumulator,
        reason: str,
        public_gap: str,
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
        rejection_code: str = "none",
        rejection_reason: str = "",
    ) -> AgentOutcome:
        ledger.add(
            "finalization_recovery_outcome",
            {"status": "failed", "reason": reason},
        )
        return ContinuousAgentEpisode._stopped_outcome(
            task_frame=task_frame,
            status="partial",
            stop_reason="finalization_recovery_failed",
            gap=public_gap,
            ledger=ledger,
            evidence=accumulator.evidence,
            traces=accumulator.traces,
            gaps=accumulator.gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
            rejection_code=rejection_code,
            rejection_reason=rejection_reason,
        )

    @staticmethod
    def _assistant_message(turn: ModelTurn) -> EpisodeMessage:
        # 形状唯一定义在 ``episode_messages.assistant_message``：派生侧
        # ``assistant_message_from_payload`` 与它同源，INV-R1 才能逐字节成立。
        return assistant_message(turn)

    @staticmethod
    def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

    @staticmethod
    def _grant_writing_shortfall(
        *,
        context: ResearchRunContext,
        ledger: "_EpisodeLedger",
        elapsed: float,
        llm_calls: int,
    ) -> float:
        """写作轮超出研究额度的秒数，从根账本的余量（= 合成保留）里铸一笔补上。

        余量 = ``hard_seconds_cap − allocated_seconds``，正是档位表留给写结论的
        ``synthesis_reserve``。只铸 ``min(差额, 余量)``：研究额度盖得住的写作轮
        一笔不铸（sol 路径逐字节同前），铸不满时照旧走 ``consume_seconds`` 失败 →
        ``_carry_just_written_finish`` 补救。修复轮从同一段余量铸窗，所以这里
        绝不预铸整段 reserve。账本鸭子类型：替身没有 ``grant`` 就什么也不做。
        """

        root = context.root_budget
        if root is None or elapsed <= 0.0:
            return 0.0
        grant_fn = getattr(root, "grant", None)
        if not callable(grant_fn):
            return 0.0
        remaining = max(0.0, float(getattr(root, "remaining_seconds", 0.0) or 0.0))
        shortfall = max(0.0, float(elapsed) - remaining)
        if shortfall <= 1e-9:
            return 0.0
        hard_cap = float(getattr(root, "hard_seconds_cap", 0.0) or 0.0)
        allocated = float(getattr(root, "allocated_seconds", hard_cap) or 0.0)
        headroom = max(0.0, hard_cap - allocated)
        seconds = min(shortfall, headroom)
        if seconds <= 1e-9:
            return 0.0
        episode_id = str(getattr(root, "episode_id", "") or "").strip()
        grant = BudgetGrant(
            grant_id=f"writing-{episode_id}-{int(llm_calls)}",
            episode_id=episode_id,
            cycle=0,
            calls_granted=0,
            seconds_granted=seconds,
        )
        if not grant_fn(grant):
            return 0.0
        ledger.add(
            "writing_grant",
            {
                "seconds_granted": round(seconds, 3),
                "model_elapsed": round(float(elapsed), 3),
                "shortfall": round(shortfall, 3),
                "headroom_before": round(headroom, 3),
                "llm_calls": int(llm_calls),
            },
        )
        return seconds

    def _carry_just_written_finish(
        self,
        *,
        turn: ModelTurn,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        registry: ResearchToolRegistry,
    ) -> FinishAdmission | None:
        """Salvage a just-written FINAL_JSON when the root clock is already dead.

        ``complete()`` already returned. A failed ``consume_seconds`` must not
        pretend the model never wrote. Tool-calling, errored, or invalid turns
        return ``None`` so this path cannot invent an answer.
        """

        if turn.error or turn.tool_calls or not str(turn.content or "").strip():
            return None
        admission = self._harness.admit_finish(
            turn.content,
            context=context,
            evidence=evidence,
            registry=registry,
        )
        if not admission.accepted:
            return None
        return admission

    def _carry_repair_finish(
        self,
        *,
        turn: ModelTurn,
        previous: AgentOutcome,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        registry: ResearchToolRegistry,
    ) -> tuple[str, tuple[OutputEvidenceBinding, ...]]:
        """Prefer the repair turn's own FINAL_JSON, else keep the previous answer.

        修复轮的截止路径原本一律结转 ``previous.draft``。那假设「上一轮已经有
        稿」——首轮合成超时（空稿）时假设破了，修复轮**刚写出来**的合法
        FINAL_JSON 会被当成从没发生过。液冷 ``run_20260820_032014_595378``
        就是这个形状：seq23 写出 814 字 draft、四格 bindings 全绑上证据，
        seq25 ``carried_draft_chars=0``，公开答卷降级成「现有证据不足」。

        取舍顺序固定：刚写出的合法稿 > 上一轮的稿。校验不过、报错、还在调
        工具的 turn 一律落回 ``previous``——这条路径不负责发明答案，也不负责
        把已有答案丢掉。
        """

        carried = self._carry_just_written_finish(
            turn=turn,
            context=context,
            evidence=evidence,
            registry=registry,
        )
        if carried is not None and carried.draft:
            return carried.draft, carried.bindings
        return previous.draft, previous.bindings

    @staticmethod
    def _stopped_outcome(
        *,
        task_frame: TaskFrame,
        status: EpisodeStatus,
        stop_reason: str,
        gap: str,
        ledger: _EpisodeLedger,
        evidence: list[AgentEvidence],
        traces: list[ProviderTrace],
        gaps: list[str],
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
        carried_draft: str = "",
        carried_bindings: tuple[OutputEvidenceBinding, ...] = (),
        rejection_code: str = "none",
        rejection_reason: str = "",
        finish_extra: Mapping[str, object] | None = None,
    ) -> AgentOutcome:
        """Stop this episode, optionally carrying an earlier answer forward.

        ``run()`` 的多数停机路径没有更早的答案可留，两个 carried 参数保持空。
        例外：``complete()`` 已返回可验证 FINAL_JSON 之后 ``consume_seconds``
        失败——稿已经写出来了，截止不能把它当成「从没生成过」
        （R-20260817-01 / 同题两发 ``carried_draft_chars=0``）。

        ``resume()`` 不一样：修复轮进来时上一轮**已经**有草稿和绑定了。修复是
        fix-forward，不是重跑；provider 在修复轮超时并不能让上一轮的答案失效。
        默认空会把「partial 但有答案」降级成「什么都没有」，比不修更差——
        2026-08-10 生产线四个 case 的 ``draft_chars=0`` 就是这么来的
        （trajectory 里 ``finalization -> finish`` 明明走过）。
        """

        final_gaps = list(gaps)
        ContinuousAgentEpisode._extend_unique(final_gaps, (gap,))
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": stop_reason,
                "gaps": final_gaps,
                # 留档结转了多长的草稿：收据里的 draft_chars 取的是最终 outcome，
                # 没有这一行就分不清「从没生成过」和「生成了但修复轮丢了」。
                "carried_draft_chars": len(carried_draft),
                # 未走过 validate 的停机路径：没有搬运，计数为 0 且字段在场。
                "caveat_slips": 0,
                "rejection_code": rejection_code,
                "rejection_reason": rejection_reason,
                # 只有取消终局带 cancel_cause / cancel_detail（INV-R4）；其余路径不带该键。
                **dict(finish_extra or {}),
            },
        )
        return ledger.outcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft=carried_draft,
            evidence=tuple(evidence),
            traces=tuple(traces),
            gaps=tuple(final_gaps),
            stop_reason=stop_reason,
            events=tuple(ledger.events),
            bindings=carried_bindings,
            usage=_agent_usage(
                ledger,
                llm_calls=llm_calls,
                tool_calls=tool_calls,
                invalid_actions=invalid_actions,
            ),
            plan=ledger.plan,
        )

__all__ = [
    "ContinuousAgentEpisode",
    "DEFAULT_LLM_TIMEOUT",
    "MIN_PLANNING_TURN_SECONDS",
]
