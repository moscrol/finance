"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
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
    public_agent_evidence,
)
from intelligence.runtime.episode_finalizer import (
    MIN_FINALIZATION_RECOVERY_SECONDS,
    EpisodeFinalizer,
)
from intelligence.services.evidence_ledger import EvidenceLedger, EvidenceLedgerSnapshot
from intelligence.services.episode_protocol import (
    attach_evidence_ordinals,
    build_episode_input,
    build_episode_instructions,
    evidence_ordinal_table,
    expand_episode_snapshot_bindings,
    finish_rejection_fields,
    rejection_response,
    strip_hashes_for_model,
    validate_episode_finish,
)
from intelligence.runtime.episode_tool_batch import (
    EpisodeToolBatchSession,
    ToolBatchExecutor,
    ToolBatchResult,
    ToolCallResult,
)
from intelligence.services.mode_governor import (
    ModeDecision,
    ModeGovernor,
    ModeSignals,
)
from intelligence.services.provider_observability import (
    ProviderTrace,
    provider_trace_tool_name,
)
from intelligence.services.provider_latency import (
    provider_name_from,
    repair_seconds_cap_for,
)
from intelligence.services.repair_coordinator import (
    RepairGoal,
    grant_for_transient_model_retry,
    unreachable_repair_goal,
)
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchRunContext,
)
from intelligence.services.research_plan import (
    PlanParseResult,
    ResearchPlan,
    parse_plan_candidate,
    plan_to_public_dict,
    validate_plan_revision,
)
from intelligence.services.episode_event_lanes import LiveEventSink
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
)
from intelligence.runtime.sub_research import (
    SubResearchCoordinator,
    SubResearchResult,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.tool_result_budget import budget_tool_observation


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
# ledger and deadline.
MAX_EPISODE_TOOL_CALLS = 24


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


def _default_mode_signals(
    task_frame: TaskFrame,
    plan: ResearchPlan,
) -> ModeSignals:
    user_task = task_frame.to_user_task()
    return ModeSignals(
        independent_entities=len(user_task.subjects),
        separable_branches=len(plan.branch_goals),
        evidence_domains=plan.evidence_needs,
        uncovered_answer_elements=len(plan.open_gaps),
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
def _evidence_required_output_ids(context: object) -> frozenset[str]:
    """契约里 evidence 口径的必填输出 id。model_reasoning 格不在此列。"""

    contract = getattr(context, "contract", None)
    return frozenset(
        str(getattr(item, "output_id", ""))
        for item in getattr(contract, "required_outputs", ())
        if getattr(item, "required", True)
        and str(getattr(item, "grounding_mode", "evidence")) == "evidence"
    )




class _EpisodeLedger:
    def __init__(
        self,
        task_frame: TaskFrame,
        *,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
    ) -> None:
        self._task_frame_hash = task_frame.task_frame_hash
        self._event_sink = event_sink
        # 见 add() 里的临界区注释：序号是「读长度 → 追加」两步，不锁就会重号。
        # RLock 而非 Lock：同线程重入（将来若有 sink 回调再发事件）不该自锁死。
        self._lock = RLock()
        self.events: list[EpisodeEvent] = []
        self.plan: ResearchPlan | None = None
        self.time_budget_injected = False
        self.add(
            "task",
            {
                "question": task_frame.raw_question,
                "task_frame": task_frame.to_dict(),
            },
        )

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

    时间闸（``tool_timeout`` + ``stage_timeout_granted``≤0）和次数闸
    （``tool_budget_exhausted`` + ``remaining_slots_at_dispatch``）共用这份
    快照，靠 error 码分闸。没测到的字段不写，避免把缺席伪装成 0。
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
    messages: list[dict[str, object]]
    ledger: _EpisodeLedger
    evidence_ledger: EvidenceLedger
    evidence: list[AgentEvidence] = field(default_factory=list)
    evidence_hashes: set[str] = field(default_factory=set)
    successful_tools: set[str] = field(default_factory=set)
    traces: list[ProviderTrace] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def consume(
        self,
        batch: ToolBatchResult,
        context: ResearchRunContext,
    ) -> int:
        invalid_actions = 0
        for result in batch.items:
            call = result.call
            clock = _tool_dispatch_clock_payload(result)
            timing = {**_tool_timing_payload(result), **clock}
            self.ledger.add("tool_request", {**call.to_dict(), **clock})

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
                public_error = (
                    "tool_timeout" if result.status == "timeout" else "tool_exception"
                )
                public_detail = (
                    ""
                    if result.status == "timeout"
                    else _public_tool_exception_detail(
                        result.detail or result.error
                    )
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
            ordinals = evidence_ordinal_table(tuple(self.evidence))
            public_observation = {
                "ok": True,
                "tool": observation.tool,
                "query": observation.query,
                "observation": observation.observation,
                "evidence": attach_evidence_ordinals(
                    [public_agent_evidence(item) for item in observation.evidence],
                    ordinals,
                ),
                "evidence_hashes": list(observation.evidence_hashes),
                "evidence_ids": [
                    ordinals[digest]
                    for digest in observation.evidence_hashes
                    if digest in ordinals
                ],
                "gaps": list(observation.gaps),
                "dataset": observation.dataset,
                "caliber": observation.caliber,
                "payload_field_names": list(observation.payload_field_names),
                "payload_sha256": observation.payload_sha256,
            }
            # 审计留档拿全量（含 hash），模型上下文拿预算后的副本并去掉 hash，
            # 只留 E1..En——誊抄 16-hex 是 B1/B7 零绑定的根因。
            self.ledger.add("tool_result", {**public_observation, **timing})
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": json.dumps(
                        strip_hashes_for_model(
                            budget_tool_observation(public_observation)
                        ),
                        ensure_ascii=False,
                    ),
                }
            )
        return invalid_actions

    def _append_tool_error(
        self,
        call: ModelToolCall,
        error: str,
        detail: str = "",
        timing: dict[str, object] | None = None,
    ) -> None:
        payload = {
            "ok": False,
            "tool": call.name,
            "error": error,
            # 分类码之外还要给可操作的原因——``error`` 只说「参数不合法」，
            # 模型据此改不了任何东西。详见 ToolCallResult.detail 的注释。
            "detail": str(detail or "")[:400],
        }
        # 耗时只进 ledger，**不进 payload**——下面那条 messages 是喂模型的，
        # 给它塞毫秒数既没用又占预算。审计要全量、模型要够用，同一份事实两个出口。
        self.ledger.add("tool_error", {**payload, **(timing or {})})
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": call.call_id,
                "content": json.dumps(payload, ensure_ascii=False),
            }
        )

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
    messages: list[dict[str, object]],
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
        messages.append({"role": "user", "content": message})
        accumulator.ledger.add(
            "prefetch",
            {
                "count": len(evidence),
                "tools": [item.tool for item in evidence],
            },
        )


@dataclass
class _EpisodeContinuationState:
    task_frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    tool_session: EpisodeToolBatchSession
    messages: list[dict[str, object]]
    ledger: _EpisodeLedger
    accumulator: _EpisodeToolAccumulator
    evidence_ledger: EvidenceLedger
    initial_evidence_snapshot: EvidenceLedgerSnapshot
    # run() 入口构造的那个 Scope。resume 复用本 state（含同一 tool_session，
    # 其内就是这个 scope），所以 Scope 的生命周期覆盖整个 Episode 含修复轮
    # ——这里显式暴露引用，是让会话层（RuntimeHandle）能把生命周期收据与
    # 能力收据钉在同一个对象上，而不是各拿各的。
    episode_scope: EpisodeScope


class ContinuousAgentEpisode:
    """Run a task without rebuilding the model's observable message history."""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        llm_timeout: float = DEFAULT_LLM_TIMEOUT,
        tool_executor: ToolBatchExecutor | None = None,
        finalizer: EpisodeFinalizer | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        mode_governor: ModeGovernor | None = None,
        mode_signals: Callable[[TaskFrame, ResearchPlan], ModeSignals] | None = None,
        sub_research_coordinator: SubResearchCoordinator | None = None,
        event_sink: Callable[[EpisodeEvent], None] | None = None,
        repair_seconds_cap: float | None = None,
    ) -> None:
        self._model = model
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
        self._is_cancelled = is_cancelled or (lambda: False)
        self._mode_governor = mode_governor or ModeGovernor()
        self._mode_signals = mode_signals or _default_mode_signals
        self._sub_research_coordinator = sub_research_coordinator
        self._event_sink = event_sink

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
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")

        ledger = _EpisodeLedger(task_frame, event_sink=self._event_sink)
        llm_calls = 0
        tool_calls = 0
        invalid_actions = 0
        finish_failures = 0
        plan_failures = 0
        plan_turns = 0
        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": build_episode_instructions(
                    task_frame,
                    context,
                    registry,
                ),
            },
            {
                "role": "user",
                "content": build_episode_input(task_frame, context),
            },
        ]
        evidence_ledger = EvidenceLedger(
            information_cutoff=context.information_cutoff.as_of_date,
        )
        for required in context.contract.required_outputs:
            if required.required and required.grounding_mode == "evidence":
                evidence_ledger.open_gap(required.output_id)
        initial_evidence_snapshot = evidence_ledger.snapshot()
        accumulator = _EpisodeToolAccumulator(
            messages=messages,
            ledger=ledger,
            evidence_ledger=evidence_ledger,
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
                else context.deadline.stage_timeout(self._llm_timeout)
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

            model_started = monotonic()
            try:
                definitions = self._available_tool_definitions(
                    tool_session=tool_session,
                    registry=registry,
                    context=context,
                )
                turn = self._model.complete(
                    messages=list(messages),
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
                ledger.add("model_error", {"reason": reason})
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
                    "timeout_asked": float(timeout),
                    "timeout_configured": float(self._llm_timeout),
                    "remaining_seconds_at_entry": float(
                        remaining_seconds_at_entry
                    ),
                },
            )
            if not _consume_root_seconds(context, model_elapsed):
                carried_draft, carried_bindings = self._carry_just_written_finish(
                    turn=turn,
                    context=context,
                    evidence=tuple(accumulator.evidence),
                    registry=registry,
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
                ledger.add("model_error", {"reason": turn.error})
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
            plan_result = (
                parse_plan_candidate(turn.content)
                if not finalization_started
                else PlanParseResult(None, "")
            )
            pending_mode_message: ModeDecision | None = None
            pending_branch_result: SubResearchResult | None = None
            if plan_result.plan is not None:
                try:
                    if ledger.plan is not None:
                        validate_plan_revision(
                            ledger.plan,
                            plan_result.plan,
                            original_task_id=context.contract.task_id,
                            current_task_id=context.contract.task_id,
                        )
                except ValueError as exc:
                    plan_result = PlanParseResult(None, str(exc))
                else:
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
                                )
                                mode_decided = True
                            pending_branch_result = self._run_sub_research(
                                task_frame=task_frame,
                                plan=plan_result.plan,
                                decision=pending_mode_message,
                                context=context,
                                registry=registry,
                                ledger=ledger,
                                evidence_ledger=evidence_ledger,
                            )
                            if pending_branch_result is not None:
                                accumulator.consume_sub_research(
                                    pending_branch_result
                                )
                                llm_calls += pending_branch_result.llm_calls
                                tool_calls += pending_branch_result.tool_calls
                            if pending_mode_message is not None:
                                self._append_mode_decision_message(
                                    messages=messages,
                                    decision=pending_mode_message,
                                )
                            if pending_branch_result is not None:
                                self._append_sub_research_message(
                                    messages=messages,
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
                            )
                            mode_decided = True
                        pending_branch_result = self._run_sub_research(
                            task_frame=task_frame,
                            plan=plan_result.plan,
                            decision=pending_mode_message,
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
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "上一条 PLAN 无效。请保留最初任务与当前 episode，"
                                "只修复为闭合的 PLAN JSON，或直接调用已授权工具；"
                                "PLAN 不能授权工具、预算、证据或完成状态。"
                                f"错误：{plan_result.error}"
                            ),
                        }
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
                _settle_batch_calls(
                    context.root_budget,
                    executed_count=batch.executed_count,
                    batch_elapsed=batch_elapsed,
                )
                injected = self._append_tool_budget_state(
                    messages=messages,
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
                        decision=pending_mode_message,
                    )
                if pending_branch_result is not None:
                    self._append_sub_research_message(
                        messages=messages,
                        result=pending_branch_result,
                        evidence=tuple(accumulator.evidence),
                    )
                if self._snapshot_surface_satisfied(
                    registry=registry,
                    context=context,
                    successful_tools=accumulator.successful_tools,
                ):
                    finalization_started = True
                    self._begin_finalization(
                        messages=messages,
                        ledger=ledger,
                        reason="snapshot_surface_satisfied",
                    )
                continue

            try:
                finish = validate_episode_finish(
                    turn.content,
                    context=context,
                    evidence=tuple(accumulator.evidence),
                )
                status, draft = finish.status, finish.draft
                final_gaps, bindings = finish.gaps, finish.bindings
            except ValueError as exc:
                finish_failures += 1
                invalid_actions += 1
                reason = str(exc)
                response = rejection_response(exc)
                # 病因与类别进收据：此前只留一句自由文本 reason，事后无法按类
                # 归并，`synthesis_health` 那 59% 「口径未知」就是从这里开始的。
                rejection = finish_rejection_fields(exc)
                ledger.add(
                    "invalid_action",
                    {
                        "reason": reason,
                        "code": rejection["rejection_code"],
                        "kind": getattr(
                            getattr(exc, "kind", None), "value", "unclassified"
                        ),
                        "disposition": response.stop_reason,
                    },
                )
                if (
                    response.reinject
                    and finish_failures == 1
                    and not finalization_started
                ):
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "上一条终止输出无效。请保留当前任务和全部观察，"
                                "不要重启研究；修复后只输出 FINAL_JSON。"
                                f"错误：{reason}"
                            ),
                        }
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

            bindings = expand_episode_snapshot_bindings(
                bindings=bindings,
                evidence=tuple(accumulator.evidence),
                registry=registry,
                draft=draft,
            )
            current_gaps = self._finish_gaps(final_gaps, bindings)
            ledger.record_runtime_result()
            ledger.add(
                "finish",
                {
                    "status": status,
                    "stop_reason": "model_finish",
                    "bindings": [item.to_dict() for item in bindings],
                    "gaps": list(current_gaps),
                    "caveat_slips": finish.caveat_slips,
                    **finish_rejection_fields(),
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
        messages: list[dict[str, object]],
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
            model_started = monotonic()
            try:
                turn = self._model.complete(
                    messages=list(messages),
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
            ledger.add("model_turn", {"phase": phase, **turn.to_dict()})
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
        # 把「这一轮结构性不可能补上」的格显式投递进 trace。纯观测，不改执行：
        # 生产 run_20260821_114642_385979 里修复轮被要求补两个 evidence 必填格，
        # 同时 remaining_calls=0 / reopen_tools=false——禁止取证。它空转 40 秒后
        # 残稿发布，读数上却表现成「repair 跑过了但没修好」，把不可能的任务
        # 误读成模型能力问题。有了这个字段，trace diff 一眼能分开这两件事。
        unreachable = unreachable_repair_goal(
            goal,
            evidence_output_ids=_evidence_required_output_ids(context),
        )
        if unreachable:
            goal_payload["unreachable_without_tools"] = list(unreachable)
        ledger.add("repair_goal", goal_payload)
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
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "kind": "REPAIR_GOAL",
                        **goal.to_dict(),
                        "instruction": (
                            "保留最初任务、全部原始观察和当前工具账本。"
                            + (
                                "自主选择一个新的、未重复的动作补齐缺口；"
                                if research_tools_open
                                else "研究工具已关闭，只能基于已有观察修复措辞或证据绑定；"
                            )
                            + "不得重启研究或改写用户问题。"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )
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
            _settle_batch_calls(
                repair_context.root_budget,
                executed_count=batch.executed_count,
                batch_elapsed=batch_elapsed,
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "修复动作已执行。不得再调用工具；请基于同一 episode 的"
                        "全部观察输出 FINAL_JSON，未补齐项继续明确写 gap。"
                    ),
                }
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
        try:
            finish = validate_episode_finish(
                turn.content,
                context=context,
                evidence=tuple(accumulator.evidence),
            )
        except ValueError as exc:
            invalid_actions += 1
            rejection = finish_rejection_fields(exc)
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
        bindings = expand_episode_snapshot_bindings(
            bindings=finish.bindings,
            evidence=tuple(accumulator.evidence),
            registry=registry,
            draft=finish.draft,
        )
        revised_without_tool = (
            finish.draft.strip() != previous.draft.strip()
            or bindings != previous.bindings
        )
        completed_without_tool = (
            not performed_tool_action
            and finish.status == "completed"
            and revised_without_tool
        )
        effective_status = (
            finish.status
            if performed_tool_action or completed_without_tool
            else "partial"
        )
        current_gaps = self._finish_gaps(finish.gaps, bindings)
        if not performed_tool_action and not completed_without_tool and not current_gaps:
            current_gaps = ("修复轮未执行新的取证动作，缺口仍未补齐",)
        repair_progressed = performed_tool_action or completed_without_tool
        ledger.record_runtime_result()
        ledger.add(
            "finish",
            {
                "status": effective_status,
                "stop_reason": (
                    "repair_model_finish"
                    if repair_progressed
                    else "repair_model_stop"
                ),
                "bindings": [item.to_dict() for item in bindings],
                "gaps": list(current_gaps),
                "caveat_slips": finish.caveat_slips,
                **finish_rejection_fields(),
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=effective_status,
            draft=finish.draft,
            evidence=tuple(accumulator.evidence),
            traces=tuple(accumulator.traces),
            gaps=current_gaps,
            stop_reason=(
                "repair_model_finish" if repair_progressed else "repair_model_stop"
            ),
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

    def _decide_mode(
        self,
        *,
        task_frame: TaskFrame,
        plan: ResearchPlan,
        context: ResearchRunContext,
        ledger: _EpisodeLedger,
        continuation_state: _EpisodeContinuationState | None,
    ) -> tuple[ResearchRunContext, ModeDecision]:
        signals = self._mode_signals(task_frame, plan)
        if not isinstance(signals, ModeSignals):
            raise TypeError("mode_signals must return ModeSignals")
        if context.root_budget is None and signals.dependencies_available:
            signals = replace(signals, dependencies_available=False)
        if (
            plan.branch_goals
            and self._sub_research_coordinator is None
            and signals.dependencies_available
        ):
            signals = replace(signals, dependencies_available=False)
        decision = self._mode_governor.decide(plan, signals)
        promoted = self._mode_governor.apply(context, decision)
        ledger.add("mode_decision", decision.to_dict())
        if continuation_state is not None:
            continuation_state.context = promoted
        return promoted, decision

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

    @staticmethod
    def _append_mode_decision_message(
        *,
        messages: list[dict[str, object]],
        decision: ModeDecision,
    ) -> None:
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "kind": "MODE_DECISION",
                        **decision.to_dict(),
                        "instruction": (
                            "研究深度与总预算已由运行时裁决。保留原计划，"
                            "继续自主选择查询、工具顺序和停止时点；"
                            "不得把预算或内部裁决文本写入最终答案。"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )

    @staticmethod
    def _append_sub_research_message(
        *,
        messages: list[dict[str, object]],
        result: SubResearchResult,
        evidence: tuple[AgentEvidence, ...] = (),
    ) -> None:
        ordinals = evidence_ordinal_table(evidence)
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "kind": "SUB_RESEARCH_RESULTS",
                        "branches": [
                            {
                                "branch_id": branch.branch_id,
                                "goal": branch.goal,
                                "status": branch.status,
                                "evidence": strip_hashes_for_model(
                                    {
                                        "evidence": attach_evidence_ordinals(
                                            [
                                                public_agent_evidence(item)
                                                for item in branch.evidence
                                            ],
                                            ordinals,
                                        )
                                    }
                                )["evidence"],
                                "gaps": list(branch.gaps),
                            }
                            for branch in result.branches
                        ],
                        "refused_reason": result.refused_reason,
                        "instruction": (
                            "这些是只读分支返回的公开证据观察，不是最终答案。"
                            "主 episode 仍需自行比较证据、处理冲突并决定停止；"
                            "绑定用证据序号 E1、E2…，不得把分支状态或内部标识写入公开答案。"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )

    @staticmethod
    def _available_tool_definitions(
        *,
        tool_session: EpisodeToolBatchSession,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> list[dict[str, object]]:
        available = set(
            tool_session.available_tool_names(
                registry=registry,
                context=context,
            )
        )
        return [
            definition
            for definition in registry.tool_definitions(
                context.contract.allowed_capabilities
            )
            if isinstance(function := definition.get("function"), dict)
            and function.get("name") in available
        ]

    @staticmethod
    def _append_tool_budget_state(
        *,
        messages: list[dict[str, object]],
        remaining_slots: int,
        remaining_seconds: float | None = None,
        total_seconds: float | None = None,
    ) -> bool:
        if not messages or messages[-1].get("role") != "tool":
            return False
        content = messages[-1].get("content")
        if not isinstance(content, str):
            return False
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
        messages[-1]["content"] = json.dumps(payload, ensure_ascii=False)
        return injected

    @staticmethod
    def _begin_finalization(
        *,
        messages: list[dict[str, object]],
        ledger: _EpisodeLedger,
        reason: str,
    ) -> None:
        ledger.add("finalization", {"reason": reason})
        messages.append(
            {
                "role": "user",
                "content": (
                    "研究阶段已关闭，不得再调用工具。请保留最初任务和全部"
                    "原始观察，立即基于已有证据序号 E1、E2… 输出 FINAL_JSON；"
                    "证据不足的 required output 必须标 partial 并写明 gap。"
                    "不要逐条复述全部观察，只保留最关键依据；条件写相对变化，"
                    "不得新增证据中没有的数值阈值。若用户要求预测，只保留一个"
                    "明确标注的主观基准区间及其不确定性。每个保留的精确数字"
                    "必须把直接证据序号放入对应 output binding，否则删去数字。"
                    "每条被正文使用的观察事实也必须把其直接证据序号加入对应 "
                    "output binding；不得用同一次工具返回的另一条证据代替。"
                    "原因归因若没有同一时间窗口的 news_search 证据，不得用普通 "
                    "web_search 摘要补成已核验因果，应保留盘面事实并把原因写 gap。"
                    "为保证 FINAL_JSON 完整，draft 控制在 1000 汉字以内；这是传输预算，"
                    "不要求固定标题、段数或措辞。"
                    f"关闭原因：{reason}"
                ),
            }
        )

    @staticmethod
    def _snapshot_surface_satisfied(
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        successful_tools: set[str],
    ) -> bool:
        specs = registry.authorized_specs(
            context.contract.allowed_capabilities,
        )
        return bool(specs) and all(
            spec.query_scope == "episode" and spec.name in successful_tools
            for spec in specs
        )

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

        try:
            finish = validate_episode_finish(
                turn.content,
                context=context,
                evidence=tuple(accumulator.evidence),
            )
            status, draft = finish.status, finish.draft
            final_gaps, bindings = finish.gaps, finish.bindings
        except ValueError as exc:
            invalid_actions += 1
            reason = str(exc)
            rejection = finish_rejection_fields(exc)
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

        bindings = expand_episode_snapshot_bindings(
            bindings=bindings,
            evidence=tuple(accumulator.evidence),
            registry=registry,
            draft=draft,
        )
        current_gaps = self._finish_gaps(final_gaps, bindings)
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
                "caveat_slips": finish.caveat_slips,
                **finish_rejection_fields(),
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
    def _assistant_message(turn: ModelTurn) -> dict[str, object]:
        message: dict[str, object] = {
            "role": "assistant",
            "content": turn.content,
        }
        if turn.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(
                            call.to_dict()["arguments"],
                            ensure_ascii=False,
                        ),
                    },
                }
                for call in turn.tool_calls
            ]
        return message

    @staticmethod
    def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

    @staticmethod
    def _finish_gaps(
        declared_gaps: tuple[str, ...],
        bindings: tuple[OutputEvidenceBinding, ...],
    ) -> tuple[str, ...]:
        """Project only currently unresolved gaps; history stays in events."""

        values = (*declared_gaps, *(item.gap for item in bindings))
        return tuple(
            dict.fromkeys(
                cleaned
                for value in values
                if (cleaned := str(value or "").strip())
            )
        )

    @staticmethod
    def _carry_just_written_finish(
        *,
        turn: ModelTurn,
        context: ResearchRunContext,
        evidence: tuple[AgentEvidence, ...],
        registry: ResearchToolRegistry,
    ) -> tuple[str, tuple[OutputEvidenceBinding, ...]]:
        """Salvage a just-written FINAL_JSON when the root clock is already dead.

        ``complete()`` already returned. A failed ``consume_seconds`` must not
        pretend the model never wrote. Tool-calling, errored, or invalid turns
        stay empty so this path cannot invent an answer.
        """

        if turn.error or turn.tool_calls or not str(turn.content or "").strip():
            return "", ()
        try:
            finish = validate_episode_finish(
                turn.content,
                context=context,
                evidence=evidence,
            )
        except ValueError:
            return "", ()
        bindings = expand_episode_snapshot_bindings(
            bindings=finish.bindings,
            evidence=evidence,
            registry=registry,
            draft=finish.draft,
        )
        return finish.draft, bindings

    @staticmethod
    def _carry_repair_finish(
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

        draft, bindings = ContinuousAgentEpisode._carry_just_written_finish(
            turn=turn,
            context=context,
            evidence=evidence,
            registry=registry,
        )
        if draft:
            return draft, bindings
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
