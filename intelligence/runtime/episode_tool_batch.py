"""Validate, schedule, and execute one model-requested read-only tool batch."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from concurrent.futures import (
    FIRST_COMPLETED,
    Executor,
    Future,
    ThreadPoolExecutor,
    wait,
)
from contextvars import copy_context
from dataclasses import dataclass, replace
from functools import partial
from threading import Lock
from time import monotonic
from typing import Literal, cast

from intelligence.services import query_ledger
from intelligence.services.agent_runtime import ModelToolCall
from intelligence.services.episode_scope import TOOL_ERROR, EpisodeScope
from intelligence.services.research_contract import (
    ResearchPolicy,
    ResearchRunContext,
    apply_env_ceiling,
    derive_stage_caps,
    policy_for_env,
)
from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments,
    PreparedToolArguments,
    ResearchToolRegistry,
    ToolObservation,
    ToolSpec,
)


ToolCallStatus = Literal["success", "empty", "rejected", "timeout", "error"]
_TOOL_CALL_STATUSES = frozenset({"success", "empty", "rejected", "timeout", "error"})
MAX_BATCH_TOOL_CALLS = 4
MAX_GLOBAL_TOOL_WORKERS = 8
DEFAULT_TOOL_BATCH_TIMEOUT_SECONDS = 30.0
# 菜单「窗小就藏」的部署开关。默认开（与接线前逐字节一致）；设 off/0/false/no 关掉，
# 此后领域申报的 ``min_window_seconds`` 只进事件不影响可见性。2026-09-06「能力 max」
# 决策：先让模型看见全部工具、量出真实超时率，再决定要不要藏、藏哪个。
TOOL_MENU_HIDE_ENV = "WORKBENCH_TOOL_MENU_HIDE"


def menu_hiding_enabled() -> bool:
    raw = str(os.environ.get(TOOL_MENU_HIDE_ENV) or "").strip().lower()
    return raw not in {"off", "0", "false", "no"}


def batch_call_cap(policy: ResearchPolicy | None) -> int:
    """一批最多派几次工具。

    默认 ``MAX_BATCH_TOOL_CALLS``（4）。max 档抬到全局 worker 数：09-06 生产探针里 sol
    首轮一次点了 6 个工具，4 的帽把后 2 个打成 ``tool_budget_exhausted``，模型下一轮
    还得再要一遍——在 600s 的档里这是纯浪费。其它档位逐字节不变。
    """

    if policy is not None and str(policy.tier or "").strip().lower() == "max":
        return MAX_GLOBAL_TOOL_WORKERS
    return MAX_BATCH_TOOL_CALLS
# 时间闸两种事实各一个码（INV-R4「未派发 ≠ 超时」，工单 #28 步骤 C）：
#   tool_not_dispatched —— 授权额 ≤0，根本没进线程池；
#   tool_timeout        —— 真跑了、在实授窗内没跑完。
# 两者同属 status=timeout 族（下游按 status 的逻辑不变），detail 都只允许实授值本身
# （见 stage_timeout_granted_detail）。09-01 之前两者共用 tool_timeout，模型只能靠
# detail=stage_timeout_granted=0 猜自己是被饿死还是真慢，于是换工具再试、序列分叉。
TOOL_NOT_DISPATCHED_ERROR = "tool_not_dispatched"
TOOL_TIMEOUT_ERROR = "tool_timeout"
TIME_GATE_ERRORS: frozenset[str] = frozenset({TOOL_NOT_DISPATCHED_ERROR, TOOL_TIMEOUT_ERROR})
STAGE_TIMEOUT_GRANTED_DETAIL_RE = re.compile(
    r"^stage_timeout_granted=\d+(\.\d+)?$"
)


def stage_timeout_granted_detail(granted: float) -> str:
    """Public timeout detail: the grant, not a raw exception."""

    value = max(0.0, float(granted))
    if value == 0.0:
        text = "0"
    else:
        text = format(value, ".9f").rstrip("0").rstrip(".")
        if not text:
            text = "0"
    return f"stage_timeout_granted={text}"


def tool_batch_timeout_seconds(policy: ResearchPolicy | None = None) -> float:
    """Ceiling for one tool batch: derived from the tier, env can only lower it.

    The old 30.0 literal did not move when the episode tier did — a deep run
    still gave tools 30s of a ~192s pre-synthesis remainder.  Bookgap S3
    replaces that literal with ``derive_stage_caps``.  ``ASK_TOOL_BATCH_TIMEOUT``
    is a fuse, not the source of truth.
    """

    caps = derive_stage_caps(policy or policy_for_env())
    return apply_env_ceiling(caps.tool_batch_seconds, "ASK_TOOL_BATCH_TIMEOUT")


_CANCELLATION_POLL_SECONDS = 0.05
_SHARED_TOOL_EXECUTOR = ThreadPoolExecutor(
    max_workers=MAX_GLOBAL_TOOL_WORKERS,
    thread_name_prefix="episode-tool",
)


@dataclass(frozen=True)
class ToolDispatchClock:
    """工具批派发点的时钟账。时间闸和次数闸共用这份快照，靠 error 码分闸。"""

    batch_grant_asked: float
    stage_timeout_granted: float
    episode_remaining_at_dispatch: float
    remaining_slots_at_dispatch: int
    turn_elapsed_at_dispatch: float | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "batch_grant_asked": self.batch_grant_asked,
            "stage_timeout_granted": self.stage_timeout_granted,
            "episode_remaining_at_dispatch": self.episode_remaining_at_dispatch,
            "remaining_slots_at_dispatch": self.remaining_slots_at_dispatch,
        }
        if self.turn_elapsed_at_dispatch is not None:
            payload["turn_elapsed_at_dispatch"] = self.turn_elapsed_at_dispatch
        return payload


@dataclass(frozen=True)
class ToolCallResult:
    call: ModelToolCall
    status: ToolCallStatus
    observation: ToolObservation | None = None
    error: str = ""
    # 拒绝的**具体原因**，回灌给模型让它改写重试。
    #
    # ``error`` 是分类码（``invalid_arguments``），对模型没有可操作性——它不知道
    # 是哪个参数、错在哪。2026-08-12 实测：改前基线 15 次失败里 14 次是同一个
    # ``order_by`` 形状错误，一模一样地重复，因为模型收到的 tool 消息逐字是
    # ``{"ok": false, "error": "invalid_arguments", "detail": ""}``——**detail
    # 字段早就在那儿，只是从没被填过**。
    #
    # 两族检索源都点名这条：族 A 官方 agent-sdk/custom-tools「Claude sees the
    # message you compose. You can add context the raw exception lacks, such as
    # which request failed or what to try instead」；族 C ai-agent-book ch4
    # 「审批失败后不应简单重试，而应将拒绝理由作为工具调用结果加入 Agent 的轨迹」。
    detail: str = ""
    step_id: str = ""
    # 排队时长与执行时长**分开**记，因为它们指向完全不同的修法。
    #
    # 一个批次里的工具是并发提交的，但共享一个 deadline
    # （``stage_timeout(tool_batch_timeout_seconds())``），而线程池
    # ``MAX_GLOBAL_TOOL_WORKERS=8`` 是**全局**的：3 个并发分支各发一批
    # （每批至多 ``MAX_BATCH_TOOL_CALLS=4``）就可能有 12 个调用抢 8 个 worker，
    # 排队的那几秒照样从共享窗口里扣。
    #
    # 只记总耗时的话，「这个工具本身慢」和「它被别人挤着排队」长得一模一样，
    # 而前者要调工具、后者要调并发度或窗口。2026-08-14 就卡在这个分辨不出上：
    # 生产 evidence_search 23 次、kb_search 20 次全部 tool_timeout，而 RAG 查询
    # 本体实测只要 13-14 秒，两种解释都说得通、都无法证伪。
    #
    # None = 没测到（在派发之前就被拒/超时的调用，压根没进线程池）。
    queued_ms: float | None = None
    elapsed_ms: float | None = None
    dispatch_clock: ToolDispatchClock | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in _TOOL_CALL_STATUSES:
            raise ValueError(f"unsupported tool call status: {self.status}")


def public_timeout_detail(raw: str) -> str:
    """Allowlist：超时 detail 只放实授值，绝不放原始 TimeoutError 文本。"""

    text = str(raw or "").strip()
    return text if STAGE_TIMEOUT_GRANTED_DETAIL_RE.fullmatch(text) else ""


def time_gate_error_for_model(result: ToolCallResult) -> str:
    """一条 ``status=timeout`` 的结果，模型该看到的 error 码。

    批次执行器已经分好了 ``tool_not_dispatched`` / ``tool_timeout``；这里只是把它原样
    带给模型，不认识的（老产物、替身）回落 ``tool_timeout``。两条 loop 共用，模型在这一格
    看到的东西不随 loop 而变。
    """

    error = str(result.error or "").strip()
    return error if error in TIME_GATE_ERRORS else TOOL_TIMEOUT_ERROR


def timeout_detail_for_model(result: ToolCallResult) -> str:
    """一条 ``status=timeout`` 的结果，模型该看到的 detail。

    零授权未派发与真跑了再超时同一口径：有派发时钟就报实授值，没有就只能放行
    已经是实授值形状的 detail。两条 loop（Episode / HarnessReferenceLoop）共用，
    否则模型在这一格上看到的东西会随 loop 而变。
    """

    if result.dispatch_clock is not None:
        return public_timeout_detail(
            stage_timeout_granted_detail(result.dispatch_clock.stage_timeout_granted)
        )
    return public_timeout_detail(result.detail)


@dataclass
class _ToolTiming:
    """一次工具调用的三个时刻。``started_at`` 由工作线程自己写，所以
    ``started - submitted`` 就是真实排队延迟，不是估的。"""

    submitted_at: float
    started_at: float | None = None
    finished_at: float | None = None

    @staticmethod
    def _ms(begin: float | None, end: float | None) -> float | None:
        if begin is None or end is None:
            return None
        return round(max(0.0, end - begin) * 1000.0, 1)

    @property
    def queued_ms(self) -> float | None:
        return self._ms(self.submitted_at, self.started_at)

    @property
    def elapsed_ms(self) -> float | None:
        return self._ms(self.started_at, self.finished_at)


def _run_timed(timing: _ToolTiming, operation: Callable[[], ToolObservation]) -> ToolObservation:
    timing.started_at = monotonic()
    try:
        return operation()
    finally:
        timing.finished_at = monotonic()


@dataclass(frozen=True)
class ToolBatchResult:
    items: tuple[ToolCallResult, ...]
    executed_count: int
    normalized_queries: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ToolMenu:
    """一轮开始时模型能看见的工具，以及这轮被底座藏起来的工具和原因。

    ``would_grant`` 是按此刻剩余算出的本轮工具窗（与派发点同一套算术
    ``deadline.stage_timeout(tool_batch_timeout_seconds)``，只是早算了一个模型轮）。
    ``hidden`` 里的每个工具，其领域申报的 ``min_window_seconds`` 都大于这个窗——
    摆出来也是必超时，2026-09-03 生产读数：kb_search 66% / evidence_search 96% 的
    调用以 tool_timeout 收场，每次烧掉约 23s 研究窗。
    """

    visible: tuple[str, ...]
    hidden: tuple[tuple[str, float], ...]
    would_grant: float

    def to_payload(self) -> dict[str, object]:
        return {
            "visible": list(self.visible),
            "hidden": [name for name, _ in self.hidden],
            "min_window_seconds": {name: seconds for name, seconds in self.hidden},
            "would_grant": round(self.would_grant, 3),
            "reason": "min_window_exceeds_grant",
        }


def tool_definitions_for_menu(
    menu: ToolMenu,
    *,
    registry: ResearchToolRegistry,
    context: ResearchRunContext,
) -> list[dict[str, object]]:
    """把菜单落成模型 API 的 tool definitions；两条 loop 共用，菜单只算一次。"""

    visible = set(menu.visible)
    return [
        definition
        for definition in registry.tool_definitions(context.contract.allowed_capabilities)
        if isinstance(function := definition.get("function"), dict)
        and function.get("name") in visible
    ]


@dataclass(frozen=True)
class _Candidate:
    index: int
    call: ModelToolCall
    prepared: PreparedToolArguments
    normalized_query: str
    spec: ToolSpec

    @property
    def key(self) -> tuple[str, str]:
        return (self.call.name, self.normalized_query)


def _run_with_publish_guard(
    guard: query_ledger.QueryPublishGuard,
    operation: Callable[[], ToolObservation],
) -> ToolObservation:
    with query_ledger.query_publish_guard_scope(guard):
        return operation()


class EpisodeToolBatchSession:
    """Own episode query state and execute independent tool calls concurrently."""

    def __init__(
        self,
        *,
        executor: Executor | None = None,
        scope: EpisodeScope | None = None,
    ) -> None:
        self._seen_queries: set[tuple[str, str]] = set()
        self._successful_episode_tools: set[str] = set()
        self._lock = Lock()
        self._next_call_sequence = 1
        self._executor = executor if executor is not None else _SHARED_TOOL_EXECUTOR
        # 缺省 None：不传 scope 的调用方行为与接线前逐字节一致。
        self._scope = scope

    def menu(
        self,
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> ToolMenu:
        """本轮菜单：去掉已拿过完整快照的 episode 级工具，再去掉本轮工具窗装不下的。

        第二条是可见性裁决，不是预算：授予算术一个字不改，只是不让模型点一个
        此刻必超时的工具。领域只申报 ``min_window_seconds``，装不装得下由这里判。
        """

        would_grant = context.deadline.stage_timeout(
            tool_batch_timeout_seconds(context.policy)
        )
        hide = menu_hiding_enabled()
        visible: list[str] = []
        hidden: list[tuple[str, float]] = []
        with self._lock:
            for spec in registry.authorized_specs(context.contract.allowed_capabilities):
                if (
                    spec.query_scope == "episode"
                    and spec.name in self._successful_episode_tools
                ):
                    continue
                floor = spec.min_window_seconds
                if hide and floor is not None and floor > would_grant:
                    hidden.append((spec.name, float(floor)))
                    continue
                visible.append(spec.name)
        return ToolMenu(tuple(visible), tuple(hidden), would_grant)

    def available_tool_names(
        self,
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
    ) -> tuple[str, ...]:
        """Return the tools that remain meaningful for the next model turn."""

        return self.menu(registry=registry, context=context).visible

    def execute(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
        is_cancelled: Callable[[], bool] | None = None,
        turn_elapsed_at_dispatch: float | None = None,
    ) -> ToolBatchResult:
        with self._lock:
            return self._execute_locked(
                calls,
                registry=registry,
                context=context,
                remaining_slots=remaining_slots,
                is_cancelled=is_cancelled,
                turn_elapsed_at_dispatch=turn_elapsed_at_dispatch,
            )

    def _execute_locked(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
        is_cancelled: Callable[[], bool] | None,
        turn_elapsed_at_dispatch: float | None,
    ) -> ToolBatchResult:
        ordered_calls = tuple(calls)
        cancelled = is_cancelled or (lambda: False)
        asked = tool_batch_timeout_seconds(context.policy)
        clock = ToolDispatchClock(
            batch_grant_asked=asked,
            stage_timeout_granted=float(context.deadline.stage_timeout(asked)),
            episode_remaining_at_dispatch=float(context.deadline.remaining()),
            remaining_slots_at_dispatch=int(remaining_slots),
            turn_elapsed_at_dispatch=turn_elapsed_at_dispatch,
        )
        items: list[ToolCallResult | None] = [None] * len(ordered_calls)
        step_ids = {
            index: f"{context.trace_parent_id}:episode:tool:{self._next_call_sequence + index}"
            for index in range(len(ordered_calls))
        }
        self._next_call_sequence += len(ordered_calls)
        if cancelled():
            for index, call in enumerate(ordered_calls):
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="cancelled",
                    step_id=step_ids[index],
                )
            return self._result(
                items,
                executed_count=0,
                normalized_queries=(),
                clock=clock,
            )
        authorized_specs = {
            spec.name: spec
            for spec in registry.authorized_specs(context.contract.allowed_capabilities)
        }

        candidates: list[_Candidate] = []
        batch_queries: set[tuple[str, str]] = set()
        batch_episode_tools: set[str] = set()
        batch_call_ids: set[str] = set()
        for index, call in enumerate(ordered_calls):
            if call.call_id in batch_call_ids:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="duplicate_call_id",
                    step_id=step_ids[index],
                )
                continue
            batch_call_ids.add(call.call_id)

            spec = authorized_specs.get(call.name)
            if spec is None:
                # 压扁**真正发生在这里**，不在 registry.execute 里——这条分支直接
                # continue，execute 根本走不到。所以区分事件必须发在这个点上，
                # 否则「诊断拿到了区分」只在测试里成立，生产批次流一条都收不到。
                if self._scope is not None:
                    decision = self._scope.authorize(call.name)
                    self._scope.emit(
                        TOOL_ERROR,
                        {
                            "tool": call.name,
                            "tool_call_id": call.call_id,
                            "step_id": step_ids[index],
                            "stage": "authorize",
                            # wire 上仍是压扁的那个串；区分只在事件里
                            "reason": decision.reason,
                            "capability": decision.capability,
                        },
                    )
                from intelligence.services.tool_hunger import (
                    EVENT_UNKNOWN_TOOL,
                    classify_unauthorized,
                    record_capability_denied,
                    record_unknown_tool,
                )

                event_type, capability, reason = classify_unauthorized(
                    registry, call.name
                )
                if event_type == EVENT_UNKNOWN_TOOL:
                    record_unknown_tool(
                        call.name, call.arguments, lane="episode"
                    )
                else:
                    record_capability_denied(
                        call.name,
                        call.arguments,
                        capability=capability,
                        reason=reason,
                    )
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="unknown_or_unauthorized_tool",
                    step_id=step_ids[index],
                )
                continue
            try:
                prepared = registry.prepare(call.name, call.arguments)
            except InvalidResearchToolArguments as exc:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error=exc.code,
                    # ``prepare`` 把底层校验异常包成 InvalidResearchToolArguments 时
                    # 用的就是 ``str(exc)``，原因一直在，只是此前没往下传。
                    detail=str(exc),
                    step_id=step_ids[index],
                )
                continue

            if spec.query_scope == "episode" and (
                call.name in self._successful_episode_tools
                or call.name in batch_episode_tools
            ):
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="episode_snapshot_already_collected",
                    step_id=step_ids[index],
                )
                continue

            normalized = prepared.normalized_key
            key = (call.name, normalized)
            if key in self._seen_queries or key in batch_queries:
                items[index] = ToolCallResult(
                    call,
                    "rejected",
                    error="duplicate_query",
                    step_id=step_ids[index],
                )
                continue
            if spec.query_scope == "episode":
                batch_episode_tools.add(call.name)
            batch_queries.add(key)
            candidates.append(
                _Candidate(index, call, prepared, normalized, spec)
            )

        selected = self._select(
            candidates,
            remaining_slots=remaining_slots,
            per_batch_cap=batch_call_cap(context.policy),
        )
        selected_indexes = {candidate.index for candidate in selected}
        for candidate in candidates:
            if candidate.index not in selected_indexes:
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "rejected",
                    error="tool_budget_exhausted",
                    step_id=step_ids[candidate.index],
                )

        selected_in_model_order = tuple(sorted(selected, key=lambda item: item.index))
        timeout = clock.stage_timeout_granted
        if selected and timeout <= 0.0:
            # 授权额为零：不进线程池，也不假装跑过。码是 tool_not_dispatched，不是超时。
            for candidate in selected:
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "timeout",
                    error=TOOL_NOT_DISPATCHED_ERROR,
                    step_id=step_ids[candidate.index],
                )
            return self._result(
                items,
                executed_count=0,
                normalized_queries=(),
                clock=clock,
            )

        if cancelled():
            for candidate in selected:
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "rejected",
                    error="cancelled",
                    step_id=step_ids[candidate.index],
                )
            return self._result(
                items,
                executed_count=0,
                normalized_queries=(),
                clock=clock,
            )
        self._seen_queries.update(candidate.key for candidate in selected)
        normalized_queries = tuple(
            candidate.key for candidate in selected_in_model_order
        )
        if selected:
            self._dispatch(
                selected,
                items=items,
                registry=registry,
                context=context,
                step_ids=step_ids,
                timeout=timeout,
                is_cancelled=cancelled,
            )
            self._successful_episode_tools.update(
                candidate.call.name
                for candidate in selected
                if candidate.spec.query_scope == "episode"
                and items[candidate.index] is not None
                and items[candidate.index].status == "success"
            )
            # 空结果 / 超时 / 错误不能占 duplicate 键：W5 补证会再打同一
            # capability。有证据的 success 仍去重，防模型死循环。
            self._seen_queries.difference_update(
                candidate.key
                for candidate in selected
                if items[candidate.index] is None
                or items[candidate.index].status != "success"
            )

        return self._result(
            items,
            executed_count=len(selected),
            normalized_queries=normalized_queries,
            clock=clock,
        )

    @staticmethod
    def _result(
        items: list[ToolCallResult | None],
        *,
        executed_count: int,
        normalized_queries: tuple[tuple[str, str], ...],
        clock: ToolDispatchClock | None = None,
    ) -> ToolBatchResult:
        if any(item is None for item in items):
            raise RuntimeError("tool batch did not produce one result per call")
        stamped = []
        for item in items:
            current = cast(ToolCallResult, item)
            if clock is not None:
                current = replace(current, dispatch_clock=clock)
                if current.status == "timeout":
                    current = replace(
                        current,
                        detail=stage_timeout_granted_detail(
                            clock.stage_timeout_granted
                        ),
                    )
            stamped.append(current)
        return ToolBatchResult(
            items=tuple(stamped),
            executed_count=executed_count,
            normalized_queries=normalized_queries,
        )

    @staticmethod
    def _select(
        candidates: list[_Candidate],
        *,
        remaining_slots: int,
        per_batch_cap: int = MAX_BATCH_TOOL_CALLS,
    ) -> tuple[_Candidate, ...]:
        budget = min(int(per_batch_cap), max(0, int(remaining_slots)))
        return tuple(candidates[:budget])

    def _dispatch(
        self,
        selected: tuple[_Candidate, ...],
        *,
        items: list[ToolCallResult | None],
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        step_ids: dict[int, str],
        timeout: float,
        is_cancelled: Callable[[], bool],
    ) -> None:
        publish_cutoff = monotonic() + timeout
        publish_guard = query_ledger.QueryPublishGuard(
            publish_cutoff=publish_cutoff,
            monotonic=monotonic,
            is_cancelled=is_cancelled,
        )
        future_candidates: dict[Future[ToolObservation], _Candidate] = {}
        timings: dict[int, _ToolTiming] = {}
        try:
            for candidate in selected:
                operation = partial(
                    registry.execute,
                    candidate.call.name,
                    candidate.prepared,
                    context=context,
                    step_id=step_ids[candidate.index],
                    is_cancelled=is_cancelled,
                    scope=self._scope,
                    # 模型给的那个 call_id，不是 step_id。step_id 是本仓按
                    # trace_parent+序号生成的，跨臂/跨引擎对不上；call_id 才是
                    # §7.1 要求「逐次对账」时两边都认的那个锚。
                    tool_call_id=candidate.call.call_id,
                )
                worker_context = copy_context()
                guarded_operation = partial(
                    _run_with_publish_guard,
                    publish_guard,
                    operation,
                )
                timing = _ToolTiming(submitted_at=monotonic())
                timings[candidate.index] = timing
                timed_operation = partial(_run_timed, timing, guarded_operation)
                future = self._executor.submit(worker_context.run, timed_operation)
                future_candidates[future] = candidate

            completed: set[Future[ToolObservation]] = set()
            unfinished: set[Future[ToolObservation]] = set(future_candidates)
            cancelled_during_wait = False
            while unfinished:
                if is_cancelled():
                    cancelled_during_wait = True
                    break
                remaining = max(0.0, publish_cutoff - monotonic())
                if remaining <= 0.0:
                    break
                newly_completed, still_running = wait(
                    tuple(unfinished),
                    timeout=min(_CANCELLATION_POLL_SECONDS, remaining),
                    return_when=FIRST_COMPLETED,
                )
                completed.update(newly_completed)
                unfinished = set(still_running)
            if is_cancelled():
                cancelled_during_wait = True
            publish_guard.close(rollback=cancelled_during_wait)
            if cancelled_during_wait:
                unfinished.update(completed)
                completed.clear()
            for future in unfinished:
                future.cancel()
                candidate = future_candidates[future]
                timing = timings[candidate.index]
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "rejected" if cancelled_during_wait else "timeout",
                    error="cancelled" if cancelled_during_wait else "tool_timeout",
                    step_id=step_ids[candidate.index],
                    # 超时的这条最需要读数：``queued_ms`` 有值而 ``elapsed_ms`` 为 None，
                    # 说明它排到了但没跑完；两个都是 None 说明它连线程都没抢到——
                    # 后者是并发度问题，不是工具慢。
                    queued_ms=timing.queued_ms,
                    elapsed_ms=timing.elapsed_ms,
                )
            for future in completed:
                candidate = future_candidates[future]
                timing = timings[candidate.index]
                try:
                    observation = future.result()
                except TimeoutError:
                    items[candidate.index] = ToolCallResult(
                        candidate.call,
                        "timeout",
                        error="tool_timeout",
                        step_id=step_ids[candidate.index],
                        queued_ms=timing.queued_ms,
                        elapsed_ms=timing.elapsed_ms,
                    )
                    continue
                except Exception as exc:
                    detail = f"{type(exc).__name__}: {str(exc)[:160]}"
                    items[candidate.index] = ToolCallResult(
                        candidate.call,
                        "error",
                        error=detail,
                        step_id=step_ids[candidate.index],
                        queued_ms=timing.queued_ms,
                        elapsed_ms=timing.elapsed_ms,
                    )
                    continue
                observation = replace(
                    observation,
                    trace=replace(
                        observation.trace,
                        parent_id=context.trace_parent_id,
                        step_id=step_ids[candidate.index],
                    ),
                )
                items[candidate.index] = ToolCallResult(
                    candidate.call,
                    "success" if observation.evidence else "empty",
                    observation=observation,
                    step_id=step_ids[candidate.index],
                    queued_ms=timing.queued_ms,
                    elapsed_ms=timing.elapsed_ms,
                )
        finally:
            publish_guard.close()


class ToolBatchExecutor:
    """Stateless factory for episode-scoped tool batch sessions."""

    def __init__(
        self,
        *,
        executor: Executor | None = None,
        scope: EpisodeScope | None = None,
    ) -> None:
        self._executor = executor if executor is not None else _SHARED_TOOL_EXECUTOR
        self._scope = scope

    def new_session(
        self, *, scope: EpisodeScope | None = None
    ) -> EpisodeToolBatchSession:
        """开一个批次会话。

        ``scope`` 是**每次运行**的东西（带着这一轮的 contract、注册表、登记簿），
        而 executor 是可复用的长生命周期对象——所以 scope 要能在这里覆盖，
        不能只在 executor 构造时给一次。executor 上那个仍作缺省。
        """

        return EpisodeToolBatchSession(
            executor=self._executor,
            scope=scope if scope is not None else self._scope,
        )

    def execute(
        self,
        calls: tuple[ModelToolCall, ...],
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        remaining_slots: int,
        is_cancelled: Callable[[], bool] | None = None,
        turn_elapsed_at_dispatch: float | None = None,
    ) -> ToolBatchResult:
        """Execute one batch in a fresh ephemeral session.

        Multi-batch Episodes must create one session with :meth:`new_session`
        and reuse that session explicitly.
        """

        return self.new_session().execute(
            calls,
            registry=registry,
            context=context,
            remaining_slots=remaining_slots,
            is_cancelled=is_cancelled,
            turn_elapsed_at_dispatch=turn_elapsed_at_dispatch,
        )


__all__ = [
    "EpisodeToolBatchSession",
    "ToolBatchExecutor",
    "ToolBatchResult",
    "ToolCallResult",
    "ToolCallStatus",
    "ToolDispatchClock",
]
