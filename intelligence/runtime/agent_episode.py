"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import hashlib
import json
import os
import re
from threading import RLock
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
from intelligence.services.evidence_ledger import EvidenceLedger, EvidenceLedgerSnapshot
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
    time_gate_error_for_model,
    timeout_detail_for_model,
    tool_definitions_for_menu,
)
from intelligence.runtime.tier_promotion import apply_mode_promotion
from intelligence.services.mode_governor import ModeDecision
from intelligence.services.provider_observability import (
    ProviderTrace,
    provider_trace_tool_name,
)
from intelligence.services.provider_latency import (
    provider_name_from,
    repair_seconds_cap_for,
)
from intelligence.services.repair_coordinator import RepairGoal
from intelligence.services.research_contract import (
    PRODUCT_MAX_TOOL_CALLS,
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
from intelligence.services.episode_messages import (
    EpisodeMessage,
    append_model_input,
    assistant_message,
    check_derivation,
    record_prompt_assembled,
    record_tool_budget_state,
    rewrite_last_tool_content,
    system_message,
    to_provider,
    tool_message,
    user_message,
)
from intelligence.services.episode_restore import RestoreResult, restore_episode
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.episode_store import (
    EPISODE_LOG_VERSION,
    INTENT_KINDS,
    EpisodePhase,
    EpisodeState,
    EpisodeStore,
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
from intelligence.runtime.sub_research_tool import bind_sub_research_tool
from intelligence.runtime.sub_research import (
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
        if event.kind not in {"model_turn", "branch_completed"}:
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

    账本烧穿时降级为 ``settle_seconds``（能扣多少扣多少，绝不抛）；
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
    ) -> None:
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
        # ── P2 durable（INV-R2 / INV-R3）───────────────────────────────────
        # store 是可选的：不传的调用方（参考 loop 的替身、旧测试）事件流逐字节不变——
        # 多出来的只有 ``configure`` 首条与 ``model_intent``，它们与 store 无关。
        self._store = store
        self.episode_id = str(episode_id or "").strip() or task_frame.task_frame_hash
        # 落盘失败不拥有执行（与 event_sink_failures / derive_mismatch 同族）；但失败一次后
        # 不再写：半份日志会让恢复读出一个自信的错答案，比「没有日志」更坏。
        self.store_failures: list[str] = []
        # 已落意图、等结算的工具调用；``consume`` 对它们不再补事后 ``tool_request``。
        self.intended_call_ids: set[str] = set()
        self.contract_snapshot: Mapping[str, object] = dict(configure or {})
        self.state: EpisodeState | None = None
        # 状态写入要算「截止还剩多久」；loop 在换 context（深度裁决 / 修复轮）时更新它。
        self.active_context: ResearchRunContext | None = None
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

    def _persist(self, event: EpisodeEvent) -> None:
        store = self._store
        if store is None:
            return
        try:
            store.append(self.episode_id, (event,), sync=event.kind in INTENT_KINDS)
        except Exception as exc:  # noqa: BLE001 - 落盘失败进收据，不拥有执行
            self.store_failures.append(f"append#{event.sequence}:{type(exc).__name__}")
            self._store = None

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
            )
            self.state = state
            store = self._store
            if store is not None:
                try:
                    store.put_state(self.episode_id, state)
                except Exception as exc:  # noqa: BLE001 - 同 _persist
                    self.store_failures.append(f"state:{phase}:{type(exc).__name__}")
                    self._store = None
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

    def record_dispatch_intent(self, intent: DispatchIntent) -> None:
        """工具派发前的意图：这一批真要进线程池的每个调用各一条 ``tool_request``。

        payload 与事后写法同形（``call.to_dict()`` + dispatch clock + 空池回退标记），多一个
        ``replay``——恢复时决定「同参数重跑」还是「合成 interrupted」的依据。
        """

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
            event_payload.setdefault(
                "time_budget_injected", self.time_budget_injected
            )
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
        # sink 调用**留在锁外**：它是外部回调（UI/进度），持锁调外部代码是经典死锁
        # 源，且慢 sink 会把研究主路径一起卡住。代价是并发时 sink 的到达顺序可能与
        # sequence 不一致——消费者按 sequence 排序，别按到达顺序。
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                # Progress is observability, never an alternate execution
                # owner. A broken UI sink must not abort financial research.
                pass
        if kind == "finish":
            # 终局只有一个出口种类（finish 事件），所以 ``done`` 挂在这里而不是十个
            # return 点上：任何停机路径都不可能漏掉程序计数器的终态。
            self.put_state(phase="done")
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
            for item in observation.evidence:
                if item.content_hash in self.evidence_hashes:
                    continue
                self.evidence_hashes.add(item.content_hash)
                self.evidence.append(item)
                self.evidence_ledger.append(item)
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

    def consume_sub_research(self, result: SubResearchResult) -> None:
        self.traces.extend(result.traces)
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
        self._store = store
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
        self._sub_research_coordinator = sub_research_coordinator
        self._event_sink = event_sink

    @staticmethod
    def restore(
        episode_id: str,
        store: EpisodeStore,
        *,
        registry: ResearchToolRegistry | None = None,
        harness: ResearchHarness | None = None,
        now: datetime | None = None,
    ) -> RestoreResult:
        """崩溃后恢复（INV-R3）：读 ``EpisodeState``、按预留 id 点查结算、给下一动作或直接闭合。

        策略与合成全在 ``services.episode_restore``——它不需要模型、不需要 loop，能对着产物
        事后重跑。本单只给 ``ResumePlan``，不重新驱动 loop（P4 ``step()``）。
        """

        return restore_episode(
            episode_id, store, registry=registry, harness=harness, now=now
        )

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        _continuation_sink: list[_EpisodeContinuationState] | None = None,
    ) -> AgentOutcome:
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
        )
        ledger.active_context = context
        registry = self._with_sub_research_tool(
            task_frame=task_frame,
            context_ref=context_ref,
            registry=registry,
            evidence_ledger=evidence_ledger,
            ledger=ledger,
        )
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
        finish_failures = 0
        plan_failures = 0
        plan_turns = 0
        system, user = self._harness.assemble_prompt(task_frame, context, registry)
        # SYSTEM_PROMPT_DYNAMIC_BOUNDARY: system is byte-stable; user/tool
        # rebuild each turn. cache_control is not implemented this increment.
        _ = SYSTEM_PROMPT_DYNAMIC_BOUNDARY
        # 模型可见即已落账：system 与首轮 user 先进 durable 事件，再进 messages。
        record_prompt_assembled(ledger, system=system, user=user)
        # 程序计数器第一份：prompt 已落、还没向模型开口。
        ledger.put_state(phase="planning", context=context)
        messages: list[EpisodeMessage] = [system_message(system), user_message(user)]
        initial_evidence_snapshot = evidence_ledger.snapshot()
        accumulator = _EpisodeToolAccumulator(
            messages=messages,
            ledger=ledger,
            evidence_ledger=evidence_ledger,
            harness=self._harness,
        )
        _seed_opening_prefetch(accumulator, messages, registry)
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
                context.deadline.synthesis_timeout(self._llm_timeout)
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

            # INV-R1：请求前对账。放在 try 之外——严格模式的 DerivationMismatch 是
            # 测试要看见的红，不能被下面那个「模型异常」的 except 吞成 model_error。
            ledger.verify_model_visible(messages)
            # INV-R2：模型请求前的意图（含预留 turn_id）。菜单在意图之前算——它只读状态，
            # 不是外部效果；``tool_menu`` 事件因此仍先于 ``model_intent``。
            definitions = self._available_tool_definitions(
                tool_session=tool_session,
                registry=registry,
                context=context,
                ledger=ledger,
            )
            turn_id = ledger.record_model_intent(
                timeout_asked=timeout,
                phase="finalizing" if finalization_started else "planning",
                # 主循环没有瞬态重试；崩溃恢复允许把这一问**再发一次**（结果丢了、
                # 请求本身是只读的）。
                retries_remaining=1,
                context=context,
            )
            model_started = monotonic()
            try:
                # 线格式只在这里出现：loop 全程 EpisodeMessage，边界一次转换。
                turn = self._model.complete(
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
                },
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
                            )
                        continue
                else:
                    ledger.record_plan(plan_result.plan)
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
                batch_started = monotonic()
                batch = tool_session.execute(
                    turn.tool_calls,
                    registry=registry,
                    context=context,
                    remaining_slots=self._remaining_tool_slots(
                        context=context,
                        tool_calls=tool_calls,
                    ),
                    is_cancelled=self._is_cancelled,
                    turn_elapsed_at_dispatch=model_elapsed,
                )
                batch_elapsed = max(0.0, monotonic() - batch_started)
                tool_calls += batch.executed_count
                invalid_actions += accumulator.consume(batch, context)
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
                _settle_batch_calls(
                    context.root_budget,
                    executed_count=batch.executed_count,
                    batch_elapsed=batch_elapsed,
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
                # 这一批的结算全部落下、无在飞外部效果：程序计数器回到规划 / 收口。
                ledger.put_state(
                    phase="finalizing" if finalization_started else "planning",
                    context=context,
                )
                continue

            admission = self._harness.admit_finish(
                turn.content,
                context=context,
                evidence=tuple(accumulator.evidence),
                registry=registry,
            )
            if not admission.accepted:
                finish_failures += 1
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
                    and finish_failures == 1
                    and not finalization_started
                ):
                    append_model_input(
                        messages,
                        ledger,
                        content=self._harness.steering_message(
                            "invalid_finish", detail=reason
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
            bindings, current_gaps = admission.bindings, admission.gaps
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
            return AgentOutcome(
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
            try:
                turn = self._model.complete(
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
            ledger.add("model_turn", {"phase": phase, "turn_id": turn_id, **turn.to_dict()})
            budget_alive = _consume_root_seconds(repair_context, model_elapsed)
            if (
                turn.error
                and transient_retries_left > 0
                and not self._is_cancelled()
                and is_transient_model_error(turn.error)
            ):
                retry_timeout = (
                    repair_deadline.stage_timeout(self._llm_timeout)
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
                            self._llm_timeout
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

        context = state.context
        if state.context_ref is not None:
            state.context_ref.value = context
        ledger = state.ledger
        accumulator = state.accumulator
        messages = state.messages
        tool_session = state.tool_session
        registry = state.registry
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
        # 修复轮的时钟账，记在动手之前。
        #
        # 这三个数是 judge 那次诊断里 ``timeout_asked`` 的同位物：judge 看着像元凶，
        # 实际 asked 已经塌到 6.67/3.33/2.07 秒——是被前面耗光的，不是配置给小了。
        # 修复轮同样是 ``min(configured, remaining)``，而 ``repair_deadline`` 的
        # ``synthesis_reserve`` 是 0，拿到的就是纯残余时钟。没有这三个数，收据里只剩
        # 一个 TimeoutError，分不清「时钟被前面吃光」还是「provider 这次真慢」。
        repair_timeout_asked = repair_deadline.stage_timeout(self._llm_timeout)
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
        append_model_input(
            messages,
            ledger,
            content=self._harness.repair_goal_message(
                prompt_goal,
                tools_open=research_tools_open,
            ),
            source="repair_goal",
        )
        # 程序计数器进修复阶段；此后 deadline_at 按修复窗算。
        ledger.active_context = repair_context
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
        (
            turn,
            llm_calls,
            budget_alive,
            repair_deadline,
            repair_context,
            transient_retries_left,
        ) = self._repair_model_complete(
            messages=messages,
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
            tool_calls += batch.executed_count
            performed_tool_action = batch.executed_count > 0
            invalid_actions += accumulator.consume(batch, repair_context)
            # 修复轮的工具结算全部落下，程序计数器回到 repair。
            ledger.put_state(phase="repair", context=repair_context)
            _settle_batch_calls(
                repair_context.root_budget,
                executed_count=batch.executed_count,
                batch_elapsed=batch_elapsed,
            )
            append_model_input(
                messages,
                ledger,
                content=self._harness.steering_message("repair_finalize", detail=""),
                source="steering_repair_finalize",
            )
            final_timeout = repair_deadline.synthesis_timeout(self._llm_timeout)
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
            (
                turn,
                llm_calls,
                budget_alive,
                repair_deadline,
                repair_context,
                transient_retries_left,
            ) = self._repair_model_complete(
                messages=messages,
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
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": verdict.status,
                "stop_reason": stop_reason,
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(verdict.gaps),
                "caveat_slips": admission.caveat_slips,
                **admission.rejection,
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=verdict.status,
            draft=admission.draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=verdict.gaps,
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
        if remaining <= 0:
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

        baseline = context.deadline.stage_timeout(self._llm_timeout)
        reserve = float(getattr(context.deadline, "synthesis_reserve", 0.0) or 0.0)
        borrowable = max(0.0, reserve - MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS)
        if borrowable <= 0.0:
            return baseline
        return max(0.0, min(float(self._llm_timeout), baseline + borrowable))

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

        baseline = context.deadline.stage_timeout(self._llm_timeout)
        floor = MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS
        if baseline + 1e-9 >= floor:
            return baseline
        remaining = float(context.deadline.remaining())
        protected = max(0.0, remaining - floor)
        return max(0.0, min(float(self._llm_timeout), max(baseline, min(floor, protected))))

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
        for index, goal in enumerate(plan.branch_goals, start=1):
            ledger.add(
                "branch_started",
                {"branch_id": f"branch-{index}", "goal": goal},
            )
        result = coordinator.run(
            goals=plan.branch_goals,
            task_frame=task_frame,
            context=context,
            registry=registry,
            evidence_sink_factory=evidence_ledger.branch_sink,
        )
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
                    "branch_id": branch.branch_id,
                    "goal": branch.goal,
                    "status": branch.status,
                    # 台账 §5.3-2：不带这个字段，「单分支取消」在事件流里与
                    # 「worker 异常失败」完全同形（同为 status=failed、gap_count=1），
                    # 于是「cancelled 分支可区分」这条对账要求在 Projection 上根本
                    # 判不出来。BranchResult.error 无错时是空串，照抄即可，不另造
                    # 一个 cancelled 布尔位——那会变成第二事实源。
                    "error": branch.error,
                    "evidence_count": len(branch.evidence),
                    "gap_count": len(branch.gaps),
                    "llm_calls": branch.llm_calls,
                    "tool_calls": branch.tool_calls,
                    "input_tokens": branch.input_tokens,
                    "output_tokens": branch.output_tokens,
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
                    },
                )
        return result

    def _with_sub_research_tool(
        self,
        *,
        task_frame: TaskFrame,
        context_ref: _ContextRef,
        registry: ResearchToolRegistry,
        evidence_ledger: EvidenceLedger,
        ledger: _EpisodeLedger,
    ) -> ResearchToolRegistry:
        """有协调器的 episode 把 ``sub_research`` 绑成模型可点的工具并进注册表。

        spec 2026-09-03：不新建子代理，包现有协调器；前台同步、深度 1。没有协调器
        （分支里的嵌套 Episode、参考 loop）就原样返回——工具不存在，而不是存在但报错。
        授权仍由 contract 决定：``sub_research`` 不在 ``allowed_capabilities`` 里时，
        ``authorized_specs`` 根本不会把它摆给模型。
        """

        coordinator = self._sub_research_coordinator
        if coordinator is None:
            return registry

        def record(goals: tuple[str, ...], result: SubResearchResult) -> None:
            # 与 PLAN 路径同一组 durable 事件（branch_started / completed / failed），
            # 事件流的消费者不必区分分支是模型点的还是 PLAN 批的。
            self._record_branch_events(ledger, goals=goals, result=result)

        spec = bind_sub_research_tool(
            coordinator=coordinator,
            task_frame=task_frame,
            current_context=context_ref,
            base_registry=registry,
            evidence_ledger=evidence_ledger,
            on_result=record,
        )
        return registry.with_specs(spec)

    @staticmethod
    def _record_branch_events(
        ledger: _EpisodeLedger,
        *,
        goals: tuple[str, ...],
        result: SubResearchResult,
    ) -> None:
        for index, goal in enumerate(goals, start=1):
            ledger.add(
                "branch_started",
                {"branch_id": f"branch-{index}", "goal": goal, "origin": "tool"},
            )
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
                    "branch_id": branch.branch_id,
                    "goal": branch.goal,
                    "status": branch.status,
                    "error": branch.error,
                    "evidence_count": len(branch.evidence),
                    "gap_count": len(branch.gaps),
                    "llm_calls": branch.llm_calls,
                    "tool_calls": branch.tool_calls,
                    "input_tokens": branch.input_tokens,
                    "output_tokens": branch.output_tokens,
                    "origin": "tool",
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
    ) -> None:
        append_model_input(
            messages,
            ledger,
            content=self._harness.project_sub_research(
                branches=result.branches,
                refused_reason=result.refused_reason,
                evidence=evidence,
            ),
            source="sub_research",
        )

    @staticmethod
    def _available_tool_definitions(
        *,
        tool_session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
    ) -> list[dict[str, object]]:
        menu = tool_session.menu(registry=registry, context=context)
        # 只在真藏了工具时记账：无裁剪轮的事件流与改前逐字节相同。
        if menu.hidden:
            ledger.add("tool_menu", menu.to_payload())
        return tool_definitions_for_menu(menu, registry=registry, context=context)

    @staticmethod
    def _append_tool_budget_state(
        *,
        messages: list[EpisodeMessage],
        ledger: _EpisodeLedger,
        remaining_slots: int,
        remaining_seconds: float | None = None,
        total_seconds: float | None = None,
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
        return bool(evidence) and (
            context.deadline.synthesis_timeout(self._llm_timeout)
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
        recovery_started = monotonic()
        try:
            turn = self._finalizer.recover(
                task_frame=task_frame,
                context=context,
                evidence=tuple(accumulator.evidence),
                gaps=tuple(accumulator.gaps),
                failure_reason=failure_reason,
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
            {"phase": "finalization_recovery", **turn.to_dict()},
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
            context.deadline.synthesis_timeout(self._llm_timeout)
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
        bindings, current_gaps = admission.bindings, admission.gaps
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
        return AgentOutcome(
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
        return AgentOutcome(
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
