"""Bounded, read-only sub-research coordination for approved deep episodes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextvars import copy_context
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from threading import RLock
from typing import Literal, Protocol

from intelligence.runtime.episode_tool_batch import batch_call_cap
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.evidence_ledger import BranchEvidenceSink
from intelligence.services.llm_refine import current_call_ledger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    RootBudgetLedger,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


BranchStatus = Literal["completed", "partial", "failed"]
_BRANCH_STATUSES = frozenset({"completed", "partial", "failed"})
MAX_SUB_RESEARCH_BRANCHES = 3
# 缺省（deep 及以下）的每支上限。这也是 ``sub_research`` 工具申报的最小窗
# （``research_tool_registry.SUB_RESEARCH_MIN_WINDOW_SECONDS``，测试钉相等）。
MAX_CALLS_PER_BRANCH = 8
MAX_SECONDS_PER_BRANCH = 60.0
# 按档位放大的上限。2026-09-07 三道可拆题 9 支分支读数：60s 下 9/9 没有一支跑完
# （7 partial、2 failed=deadline_exhausted 零证据），而父臂每次派发时都还剩 ~590s、
# ``sub_research`` 整个调用只用 60–97s。父臂的窗不是瓶颈，分支的顶才是。
# max 档 600s 里给每支 150s / 10 次：三支并行占父臂约 2.5 分钟，父臂自己还剩 7 分钟。
# 调用同样从父账本扣（非铸币视图不变），所以 max 档的起步调用数同步 32 → 40
# （``ResearchPolicy.for_tier("max")``）——昨晚长电 vs 通富那题分支 20 + 父臂 12 恰好用满 32。
_BRANCH_LIMITS_BY_TIER: dict[str, tuple[int, float]] = {
    "max": (10, 150.0),
}


def branch_limits(tier: str | None) -> tuple[int, float]:
    """一支分支最多几次调用、多少秒。缺省 (8, 60.0)；max 档 (10, 150.0)。"""

    return _BRANCH_LIMITS_BY_TIER.get(
        str(tier or "").strip().lower(),
        (MAX_CALLS_PER_BRANCH, MAX_SECONDS_PER_BRANCH),
    )


def _clean_goals(values: Iterable[str]) -> tuple[str, ...]:
    goals: list[str] = []
    for raw in values:
        goal = str(raw or "").strip()
        if not goal:
            raise ValueError("branch goals must be non-empty")
        if goal not in goals:
            goals.append(goal)
    if len(goals) > MAX_SUB_RESEARCH_BRANCHES:
        raise ValueError("sub-research supports at most three unique goals")
    return tuple(goals)


class _BranchBudgetView:
    """A non-minting child view: calls debit the parent, seconds stay local.

    秒是墙钟。三支并行各跑 150s，对父臂只是 150s 的墙钟——父臂对 ``sub_research`` 那一批
    做批结算时按墙钟记一次；分支自己的秒只用来守自己的 150s 与出收据。此前分支把秒也
    转记到父账本，三支累加 450s、批结算再 180s，540s 的账本在墙钟 190s 归零，父臂墙钟
    还剩 396s 却 ``deadline_exhausted``、判官 unavailable（2026-09-07 候选口第二遍，
    ``docs/verification/2026-09-07-branch-level-trace.md`` §4.2）。调用仍从父账本扣：
    调用是真实的共享资源（``PRODUCT_MAX_TOOL_CALLS``），并行不会让它变便宜。
    """

    def __init__(
        self,
        *,
        parent: RootBudgetLedger,
        episode_id: str,
        calls: int,
        seconds: float,
    ) -> None:
        if calls <= 0 or seconds <= 0:
            raise ValueError("branch budget must be positive")
        self._parent = parent
        self.episode_id = str(episode_id or "").strip()
        if not self.episode_id:
            raise ValueError("branch episode_id must be non-empty")
        self.initial_calls = int(calls)
        self.hard_calls_cap = int(calls)
        self.initial_seconds = float(seconds)
        self.hard_seconds_cap = float(seconds)
        self.remaining_calls = int(calls)
        self.remaining_seconds = float(seconds)
        self._lock = RLock()

    @property
    def allocated_calls(self) -> int:
        return self.initial_calls

    @property
    def allocated_seconds(self) -> float:
        return self.initial_seconds

    def grant(self, grant: object) -> bool:
        del grant
        return False

    def promote_caps(
        self,
        *,
        episode_id: str,
        promotion_id: str,
        hard_calls_cap: int,
        hard_seconds_cap: float,
    ) -> bool:
        del episode_id, promotion_id, hard_calls_cap, hard_seconds_cap
        return False

    def _debit_parent_call_slot(self) -> None:
        slot = getattr(self._parent, "consume_call_slot", None)
        if callable(slot):
            slot()
            return
        # Parent predates the Protocol method (third-party/test stub): spend the
        # slot through the old seconds-coupled entry with a negligible debit.
        self._parent.consume_call(seconds=1e-9)

    def consume_call(self, *, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("consumed call seconds must be positive")
        with self._lock:
            if self.remaining_calls <= 0:
                raise ValueError("branch call budget exhausted")
            if seconds > self.remaining_seconds + 1e-9:
                raise ValueError("branch seconds budget exhausted")
            self._debit_parent_call_slot()
            self.remaining_calls -= 1
            self.remaining_seconds = max(0.0, self.remaining_seconds - seconds)

    def consume_call_slot(self) -> None:
        with self._lock:
            if self.remaining_calls <= 0:
                raise ValueError("branch call budget exhausted")
            self._debit_parent_call_slot()
            self.remaining_calls -= 1

    def consume_seconds(self, *, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("consumed seconds must be non-negative")
        with self._lock:
            if seconds > self.remaining_seconds + 1e-9:
                raise ValueError("branch seconds budget exhausted")
            self.remaining_seconds = max(0.0, self.remaining_seconds - seconds)

    def settle_seconds(self, *, seconds: float) -> float:
        """Clamp against this branch's own share and report what was spent.

        Settling finished work cannot be undone, so this never raises on
        overdraft. Clamping inside ``self._lock`` is what keeps concurrent
        settling from losing a debit. The parent is **not** debited here: the
        branch's wall time is inside the parent's ``sub_research`` batch, which
        the parent settles once against its own ledger when the batch returns.
        """

        try:
            requested = float(seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("settled seconds must be numeric") from exc
        if requested < 0:
            raise ValueError("settled seconds must be non-negative")
        with self._lock:
            settled = min(requested, max(0.0, self.remaining_seconds))
            self.remaining_seconds = max(0.0, self.remaining_seconds - settled)
            return settled

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "episode_id": self.episode_id,
                "initial_calls": self.initial_calls,
                "hard_calls_cap": self.hard_calls_cap,
                "initial_seconds": self.initial_seconds,
                "hard_seconds_cap": self.hard_seconds_cap,
                "remaining_calls": self.remaining_calls,
                "remaining_seconds": self.remaining_seconds,
            }


@dataclass(frozen=True)
class BranchRequest:
    branch_id: str
    goal: str
    task_frame: TaskFrame
    context: ResearchRunContext
    registry: ResearchToolRegistry
    evidence_sink: BranchEvidenceSink
    is_cancelled: Callable[[], bool]


def _non_negative_int(value: object, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be non-negative")


@dataclass(frozen=True)
class BranchBatch:
    """分支里一批工具的派发账，由分支 Episode 的 durable 事件重算。

    2026-09-07 四遍读数里「分支 150s 仍 9/9 partial」的下一个候选原因是分支上下文
    的每批帽（``batch_call_cap`` 对 quick 标签 = 4）。此前分支内部的
    ``tool_request`` / ``tool_result`` / ``tool_error`` 在 worker 返回时被整段丢掉，
    父臂事件流里只剩 ``branch_completed`` 的合计数——「每批点了几个、几个被帽拒」
    在收据里根本判不出来，只能靠人翻日志。这份账就是补那一段：

    - ``requested`` 模型这一轮点了几个工具（``tool_request`` 条数）；
    - ``succeeded`` 拿到 ``tool_result`` 的；
    - ``rejected_by_cap`` 派发前被次数闸拒的（``tool_budget_exhausted``，含每批帽
      与分支剩余次数两种来源，事件里同码，靠 ``remaining_slots_at_dispatch`` 分）；
    - ``timed_out`` / ``errored`` 真派发了但超时 / 抛错；
    - ``rejected_other`` 其它派发前拒绝（重复查询、参数不合法、未授权……）。

    时钟三元组取自本批第一条 ``tool_request``（同批共享同一份派发快照），没测到
    就留 ``None``，不写 0 把缺席伪装成读数。
    """

    index: int
    requested: int
    succeeded: int
    rejected_by_cap: int
    timed_out: int
    errored: int
    rejected_other: int
    tools: tuple[str, ...]
    remaining_slots_at_dispatch: int | None = None
    stage_timeout_granted: float | None = None
    episode_remaining_at_dispatch: float | None = None
    # 本批里等全局工具线程池等得最久的那条（工单 #39 §2.3）：``tool_result / tool_error.queued_ms`` 的最大值。
    # 分支 ×3 与父臂共用 8 个 worker，池被占满时它会涨；没测到留 None，不写 0。
    queue_wait_ms_max: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("batch index must be a positive integer")
        for field_name in (
            "requested",
            "succeeded",
            "rejected_by_cap",
            "timed_out",
            "errored",
            "rejected_other",
        ):
            _non_negative_int(getattr(self, field_name), field_name=f"batch {field_name}")
        if any(not isinstance(tool, str) or not tool.strip() for tool in self.tools):
            raise ValueError("batch tools must be non-empty strings")
        object.__setattr__(self, "tools", tuple(self.tools))

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "index": self.index,
            "requested": self.requested,
            "succeeded": self.succeeded,
            "rejected_by_cap": self.rejected_by_cap,
            "timed_out": self.timed_out,
            "errored": self.errored,
            "rejected_other": self.rejected_other,
            "tools": list(self.tools),
        }
        for field_name in (
            "remaining_slots_at_dispatch",
            "stage_timeout_granted",
            "episode_remaining_at_dispatch",
            "queue_wait_ms_max",
        ):
            value = getattr(self, field_name)
            if value is not None:
                payload[field_name] = value
        return payload


@dataclass(frozen=True)
class BranchBudgetReceipt:
    """一支分支的预算账：给了多少、用了多少、跑完还剩多少、在什么帽下跑的。

    由协调器从 ``_BranchBudgetView`` 读出，不由 worker 自报（与 ``tool_calls``
    同一条纪律：``test_branch_usage_comes_from_child_budget_not_worker_claims``）。
    ``batch_call_cap`` 是解释 ``BranchBatch.rejected_by_cap`` 的成立条件——
    分支上下文带 quick 标签时它是 4，父臂 max 是 8。
    """

    allocated_calls: int
    consumed_calls: int
    allocated_seconds: float
    remaining_seconds: float
    batch_call_cap: int

    def __post_init__(self) -> None:
        _non_negative_int(self.allocated_calls, field_name="allocated_calls")
        _non_negative_int(self.consumed_calls, field_name="consumed_calls")
        _non_negative_int(self.batch_call_cap, field_name="batch_call_cap")
        for field_name in ("allocated_seconds", "remaining_seconds"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        object.__setattr__(self, "allocated_seconds", float(self.allocated_seconds))
        object.__setattr__(self, "remaining_seconds", float(self.remaining_seconds))

    def to_dict(self) -> dict[str, object]:
        return {
            "allocated_calls": self.allocated_calls,
            "consumed_calls": self.consumed_calls,
            "allocated_seconds": self.allocated_seconds,
            "remaining_seconds": self.remaining_seconds,
            "batch_call_cap": self.batch_call_cap,
        }


@dataclass(frozen=True)
class BranchInvalidAction:
    """分支 Episode 的一次 ``invalid_action``：终局被拒 / PLAN 无效 / 终局阶段仍点工具。

    2026-09-07 10:57 候选口首个 live 读数：三支分支各剩 38–81s、零超时，却全部
    ``stop_reason=invalid_model_finish``——分支不是被预算打成 partial 的，是收尾 JSON
    被出口拒了。拒绝码（``unknown_output`` / ``unsupported_claims`` / …）只在分支自己的
    ``invalid_action`` 事件里，此前随事件流一起被丢掉。``reason`` 截 200 字。
    """

    reason: str
    code: str = ""
    kind: str = ""
    disposition: str = ""

    def __post_init__(self) -> None:
        for field_name in ("reason", "code", "kind", "disposition"):
            if not isinstance(getattr(self, field_name), str):
                raise ValueError(f"invalid action {field_name} must be a string")
        object.__setattr__(self, "reason", self.reason.strip()[:200])

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"reason": self.reason}
        for field_name in ("code", "kind", "disposition"):
            value = getattr(self, field_name)
            if value:
                payload[field_name] = value
        return payload


def branch_invalid_actions_from_events(
    events: Iterable[EpisodeEvent],
) -> tuple[BranchInvalidAction, ...]:
    """把分支事件流里的 ``invalid_action`` 逐条摘出来（顺序保留）。"""

    records: list[BranchInvalidAction] = []
    for event in events:
        if event.kind != "invalid_action":
            continue
        payload = event.payload
        records.append(
            BranchInvalidAction(
                reason=str(payload.get("reason") or ""),
                code=str(payload.get("code") or ""),
                kind=str(payload.get("kind") or ""),
                disposition=str(payload.get("disposition") or ""),
            )
        )
    return tuple(records)


_TOOL_ERROR_REJECTED_BY_CAP = "tool_budget_exhausted"
_TOOL_ERROR_TIMEOUT = "tool_timeout"
_TOOL_ERROR_EXCEPTION = "tool_exception"
_BATCH_CLOCK_FIELDS = (
    "remaining_slots_at_dispatch",
    "stage_timeout_granted",
    "episode_remaining_at_dispatch",
)


def branch_batches_from_events(
    events: Iterable[EpisodeEvent],
) -> tuple[BranchBatch, ...]:
    """把分支 Episode 的 durable 事件按 ``model_turn`` 切成一批批工具派发账。

    每条 ``model_turn`` 开一批；随后到下一条 ``model_turn`` 之前的
    ``tool_request`` / ``tool_result`` / ``tool_error`` 归这一批。没点工具的模型轮
    （比如 finish）不算批——它们已经在 ``llm_calls`` 里。只认事件不认 worker 自述，
    所以 ``requested == succeeded + rejected_by_cap + timed_out + errored + rejected_other``
    对每一批都成立，对不上就是事件流本身缺了条。
    """

    batches: list[BranchBatch] = []
    current: dict[str, object] | None = None

    def flush() -> None:
        if current is None or int(current["requested"]) == 0:
            return
        batches.append(
            BranchBatch(
                index=len(batches) + 1,
                requested=int(current["requested"]),
                succeeded=int(current["succeeded"]),
                rejected_by_cap=int(current["rejected_by_cap"]),
                timed_out=int(current["timed_out"]),
                errored=int(current["errored"]),
                rejected_other=int(current["rejected_other"]),
                tools=tuple(current["tools"]),  # type: ignore[arg-type]
                remaining_slots_at_dispatch=current["remaining_slots_at_dispatch"],  # type: ignore[arg-type]
                stage_timeout_granted=current["stage_timeout_granted"],  # type: ignore[arg-type]
                episode_remaining_at_dispatch=current["episode_remaining_at_dispatch"],  # type: ignore[arg-type]
                queue_wait_ms_max=current["queue_wait_ms_max"],  # type: ignore[arg-type]
            )
        )

    def note_queue_wait(payload: dict[str, object]) -> None:
        raw = payload.get("queued_ms")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return
        prev = current["queue_wait_ms_max"] if current is not None else None
        current["queue_wait_ms_max"] = float(raw) if prev is None else max(float(prev), float(raw))  # type: ignore[index]

    for event in events:
        if event.kind == "model_turn":
            flush()
            current = {
                "requested": 0,
                "succeeded": 0,
                "rejected_by_cap": 0,
                "timed_out": 0,
                "errored": 0,
                "rejected_other": 0,
                "tools": [],
                "remaining_slots_at_dispatch": None,
                "stage_timeout_granted": None,
                "episode_remaining_at_dispatch": None,
                "queue_wait_ms_max": None,
            }
            continue
        if current is None:
            continue
        payload = event.payload
        if event.kind == "tool_request":
            current["requested"] = int(current["requested"]) + 1
            name = str(payload.get("name") or "").strip()
            if name:
                current["tools"].append(name)  # type: ignore[union-attr]
            for field_name in _BATCH_CLOCK_FIELDS:
                if current[field_name] is None and payload.get(field_name) is not None:
                    current[field_name] = payload[field_name]
        elif event.kind == "tool_result":
            current["succeeded"] = int(current["succeeded"]) + 1
            note_queue_wait(payload)
        elif event.kind == "tool_error":
            note_queue_wait(payload)
            error = str(payload.get("error") or "").strip()
            if error == _TOOL_ERROR_REJECTED_BY_CAP:
                key = "rejected_by_cap"
            elif error == _TOOL_ERROR_TIMEOUT:
                key = "timed_out"
            elif error == _TOOL_ERROR_EXCEPTION:
                key = "errored"
            else:
                key = "rejected_other"
            current[key] = int(current[key]) + 1
    flush()
    return tuple(batches)


@dataclass(frozen=True)
class BranchResult:
    branch_id: str
    goal: str
    status: BranchStatus
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    gaps: tuple[str, ...]
    llm_calls: int
    tool_calls: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str = ""
    # 分支 Episode 自己的终局理由（``AgentOutcome.stop_reason``），不论 status。
    # ``error`` 只在 failed 时填；partial 分支「为什么停」此前只能从 gaps 文案猜。
    stop_reason: str = ""
    # 分支内逐批派发账（worker 从分支事件重算）与预算账（协调器从子账本读出）。
    batches: tuple[BranchBatch, ...] = ()
    budget: BranchBudgetReceipt | None = None
    # 分支 Episode 里的 invalid_action（终局被拒的码在这里），同样从事件重算。
    invalid_actions: tuple[BranchInvalidAction, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _BRANCH_STATUSES:
            raise ValueError("unsupported branch status")
        if not self.branch_id.strip() or not self.goal.strip():
            raise ValueError("branch identity and goal must be non-empty")
        if any(not isinstance(item, AgentEvidence) for item in self.evidence):
            raise TypeError("branch evidence must contain AgentEvidence values")
        if any(not isinstance(item, ProviderTrace) for item in self.traces):
            raise TypeError("branch traces must contain ProviderTrace values")
        for field_name in ("llm_calls", "tool_calls"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"branch {field_name} must be non-negative")
        for field_name in ("input_tokens", "output_tokens"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"branch {field_name} must be non-negative")
        if not isinstance(self.stop_reason, str):
            raise ValueError("branch stop_reason must be a string")
        if any(not isinstance(item, BranchBatch) for item in self.batches):
            raise TypeError("branch batches must contain BranchBatch values")
        if self.budget is not None and not isinstance(self.budget, BranchBudgetReceipt):
            raise TypeError("branch budget must be a BranchBudgetReceipt")
        if any(not isinstance(item, BranchInvalidAction) for item in self.invalid_actions):
            raise TypeError("branch invalid_actions must contain BranchInvalidAction values")
        object.__setattr__(self, "batches", tuple(self.batches))
        object.__setattr__(self, "invalid_actions", tuple(self.invalid_actions))


# 父臂尾段在 turn 级 LLM 调用保险丝上的预留：分支回来后父臂至少一轮消化 + 一次合成 +
# 判官（≤3）+ 修复轮（≤2），取整 8。#617 那一遍就是分支把 40 烧到判官发不出去。
PARENT_TAIL_LLM_RESERVE = 8


@dataclass(frozen=True)
class BranchAdmission:
    """起分支前的准入账：父臂先留下自己的尾段，分支只拿剩下的。

    「能力 max」的反面不是约束多，是约束放错了地方：#615 把每支抬到 150s 后，三支跑满
    会把父臂挤到一次工具都发不出、判官没时间上场（09-07 候选口第二遍）。预留的三样是
    父臂把分支成果变成答案所需的最小量——一批工具（``batch_call_cap``）、一次合成的秒
    （``policy.synthesis_reserve``）、保险丝上的尾段调用（``PARENT_TAIL_LLM_RESERVE``）。
    分支能拿多少由这三条与档位上限共同决定，账本余量不够留尾段就拒起分支、让模型直接
    点工具——分支是放大能力的手段，不能反过来吃掉出答案的能力。
    """

    branch_count: int
    calls_per_branch: int
    seconds_per_branch: float
    reserved_calls: int
    reserved_seconds: float
    root_remaining_calls: int
    root_remaining_seconds: float
    llm_headroom: int | None
    llm_expected: int
    refused_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "branch_count": self.branch_count,
            "calls_per_branch": self.calls_per_branch,
            "seconds_per_branch": round(self.seconds_per_branch, 3),
            "reserved_calls": self.reserved_calls,
            "reserved_seconds": round(self.reserved_seconds, 3),
            "root_remaining_calls": self.root_remaining_calls,
            "root_remaining_seconds": round(self.root_remaining_seconds, 3),
            "llm_headroom": self.llm_headroom,
            "llm_expected": self.llm_expected,
        }
        if self.refused_reason:
            payload["refused_reason"] = self.refused_reason
        return payload


def admit_branches(
    *,
    context: ResearchRunContext,
    root: RootBudgetLedger,
    branch_count: int,
    max_calls: int,
    max_seconds: float,
    llm_headroom: int | None,
) -> BranchAdmission:
    """给 ``branch_count`` 支分支切额度，先扣父臂尾段。

    - 次数：父臂预留一批（``batch_call_cap(policy)``，max 档 8 / 其它 4）；剩下的按支均分，
      再被档位上限压住。剩不够每支一次 → 拒。
    - 秒：墙钟。并行分支共享同一段窗，**不按支数除**；父臂预留一次合成（``synthesis_reserve``），
      分支拿 ``min(档位上限, deadline 余量, 账本余量 − 预留)``。预留后为零 → 拒。
    - 保险丝：分支预计模型调用 = 每支（批数 + 收尾 + 1 余量）× 支数，加父臂尾段 8；
      余量不够 → 拒。无台账（None）不判。
    """

    reserved_calls = batch_call_cap(context.policy)
    reserved_seconds = max(0.0, float(context.policy.synthesis_reserve))
    root_calls = int(root.remaining_calls)
    root_seconds = float(root.remaining_seconds)
    available_calls = root_calls - reserved_calls
    available_seconds = min(
        float(context.deadline.remaining()),
        root_seconds - reserved_seconds,
    )
    calls_per_branch = max(
        1,
        min(max_calls, max(0, available_calls) // max(1, branch_count)),
    )
    seconds_per_branch = max(0.001, min(max_seconds, available_seconds))
    # 分支上下文带 quick 标签，每批帽是 quick 的那个数；批数 = ceil(次数 / 帽)。
    branch_cap = batch_call_cap(ResearchPolicy("quick", calls_per_branch, seconds_per_branch, 0.0))
    per_branch_llm = -(-calls_per_branch // max(1, branch_cap)) + 2
    llm_expected = branch_count * per_branch_llm + PARENT_TAIL_LLM_RESERVE

    refused = ""
    if available_calls < branch_count:
        refused = "parent_reserve_exhausted:calls"
    elif available_seconds <= 0.0:
        refused = "parent_reserve_exhausted:seconds"
    elif llm_headroom is not None and llm_headroom < llm_expected:
        refused = "llm_call_reserve_exhausted"
    return BranchAdmission(
        branch_count=branch_count,
        calls_per_branch=calls_per_branch,
        seconds_per_branch=seconds_per_branch,
        reserved_calls=reserved_calls,
        reserved_seconds=reserved_seconds,
        root_remaining_calls=root_calls,
        root_remaining_seconds=root_seconds,
        llm_headroom=llm_headroom,
        llm_expected=llm_expected,
        refused_reason=refused,
    )


@dataclass(frozen=True)
class SubResearchResult:
    branches: tuple[BranchResult, ...]
    refused_reason: str = ""
    admission: BranchAdmission | None = None

    @property
    def tool_calls(self) -> int:
        return sum(item.tool_calls for item in self.branches)

    @property
    def llm_calls(self) -> int:
        return sum(item.llm_calls for item in self.branches)

    @property
    def input_tokens(self) -> int | None:
        values = tuple(
            item.input_tokens for item in self.branches if item.input_tokens is not None
        )
        return sum(values) if values else None

    @property
    def output_tokens(self) -> int | None:
        values = tuple(
            item.output_tokens
            for item in self.branches
            if item.output_tokens is not None
        )
        return sum(values) if values else None

    @property
    def evidence(self) -> tuple[AgentEvidence, ...]:
        return tuple(item for branch in self.branches for item in branch.evidence)

    @property
    def traces(self) -> tuple[ProviderTrace, ...]:
        return tuple(item for branch in self.branches for item in branch.traces)


class SubResearchWorker(Protocol):
    def run(self, request: BranchRequest) -> BranchResult: ...


class SubResearchCoordinator:
    """Validate and run explicit branch goals without owning research strategy."""

    def __init__(
        self,
        worker: SubResearchWorker,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self._worker = worker
        self._is_cancelled = is_cancelled or (lambda: False)

    def run(
        self,
        *,
        goals: Iterable[str],
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        evidence_sink_factory: Callable[[str], BranchEvidenceSink],
    ) -> SubResearchResult:
        """把每个分支跑到终态再返回。

        **承重不变量（写死认领，别静默改）：本方法保持同步。** 分支全部提交后在
        同一次调用里消费完 ``as_completed``，返回值又对每个 request 取
        ``results[request.branch_id]``——"已返回"这件事本身就蕴含"没有分支线程还
        活着"，``with ThreadPoolExecutor`` 的 join 只是第二道保险。"Episode 关闭时
        不存在后台分支泄漏"（spec §4.2.4 的排空档）整个靠这一条成立。

        谁把它改成 async / fire-and-forget——提前返回 future、把 executor 提到实例
        或模块级、``shutdown(wait=False)`` 后不消费、把分支挪进后台队列——谁就必须
        重开 spec §4.2.4，并在 RuntimeHandle 上补分支粒度 drain；台账
        ``docs/handoffs/2026-08-15-dsh-absorption-p0-execution-handoff.md`` §4.1 的
        四条证据届时全部作废。**仓内没有测试直接钉住它**：test 侧四处 ``is_alive()``
        断言（``test_sub_research.py`` / ``test_headless_tool_gateway.py`` ×2 /
        ``test_rag_worker.py``）钉的都不是协调器排空——本文件那处测的是
        ``_BranchBudgetView`` 并发结算的辅助线程。

        取消语义（spec §7.3）：入口整体早退 + ``_run_one`` 里每个分支启动前各查一次，
        两处用的都是 ``self._is_cancelled``——与 RuntimeHandle 折叠的是同一个上游
        callable（见 ``glm_agent_runtime.GLMAgentRuntime.__init__`` 里的
        ``_upstream_cancelled`` 注释）。已进入 worker 的分支不打断，由上面那条同步
        消费排空。**这两处守卫同样没有测试钉住**：2026-08-15 抽掉它们跑全量，
        4982 passed / 0 红。
        """

        normalized = _clean_goals(goals)
        if not normalized:
            return SubResearchResult(())
        # deep 之上的档位（max，2026-09-06）同样够起分支：判据是「不低于 deep」，
        # 不是「等于 deep」——否则 max 起步的 run 永远拿 deep_mode_required。
        if context.policy.tier not in {"deep", "max"}:
            return SubResearchResult((), "deep_mode_required")
        root = context.root_budget
        if root is None:
            return SubResearchResult((), "root_budget_required")
        if self._is_cancelled():
            return SubResearchResult((), "cancelled")
        if root.remaining_calls <= 0 or root.remaining_seconds <= 0:
            return SubResearchResult((), "root_budget_exhausted")
        if context.deadline.remaining() <= 0.0:
            return SubResearchResult((), "deadline_exhausted")

        branch_count = len(normalized)
        max_calls, max_seconds = branch_limits(context.policy.tier)
        llm_ledger = current_call_ledger()
        admission = admit_branches(
            context=context,
            root=root,
            branch_count=branch_count,
            max_calls=max_calls,
            max_seconds=max_seconds,
            llm_headroom=llm_ledger.headroom() if llm_ledger is not None else None,
        )
        if admission.refused_reason:
            return SubResearchResult((), admission.refused_reason, admission=admission)
        requests = tuple(
            self._request(
                index=index,
                goal=goal,
                task_frame=task_frame,
                context=context,
                registry=registry,
                evidence_sink_factory=evidence_sink_factory,
                root=root,
                calls=admission.calls_per_branch,
                seconds=admission.seconds_per_branch,
            )
            for index, goal in enumerate(normalized, start=1)
        )
        results: dict[str, BranchResult] = {}
        with ThreadPoolExecutor(
            max_workers=min(MAX_SUB_RESEARCH_BRANCHES, branch_count),
            thread_name_prefix="sub-research",
        ) as executor:
            futures: dict[Future[BranchResult], BranchRequest] = {
                executor.submit(
                    copy_context().run,
                    self._run_one,
                    request,
                ): request
                for request in requests
            }
            for future in as_completed(futures):
                request = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # failure isolation at the worker seam
                    result = BranchResult(
                        branch_id=request.branch_id,
                        goal=request.goal,
                        status="failed",
                        evidence=(),
                        traces=(),
                        gaps=("分支研究未完成",),
                        llm_calls=0,
                        tool_calls=self._consumed_tool_calls(request),
                        error=f"branch_worker_exception:{type(exc).__name__}",
                    )
                results[request.branch_id] = result
        return SubResearchResult(
            tuple(results[request.branch_id] for request in requests),
            admission=admission,
        )

    def _request(
        self,
        *,
        index: int,
        goal: str,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        evidence_sink_factory: Callable[[str], BranchEvidenceSink],
        root: RootBudgetLedger,
        calls: int,
        seconds: float,
    ) -> BranchRequest:
        branch_id = f"branch-{index}"
        budget = _BranchBudgetView(
            parent=root,
            episode_id=f"{context.contract.task_id}:{branch_id}",
            calls=calls,
            seconds=seconds,
        )
        branch_context = replace(
            context,
            deadline=ResearchDeadline.from_timeout(seconds),
            policy=ResearchPolicy("quick", calls, seconds, 0.0),
            trace_parent_id=f"{context.trace_parent_id}:{branch_id}",
            root_budget=budget,
        )
        return BranchRequest(
            branch_id=branch_id,
            goal=goal,
            task_frame=task_frame,
            context=branch_context,
            registry=registry,
            evidence_sink=evidence_sink_factory(branch_id),
            is_cancelled=self._is_cancelled,
        )

    def _run_one(self, request: BranchRequest) -> BranchResult:
        if request.is_cancelled():
            return BranchResult(
                branch_id=request.branch_id,
                goal=request.goal,
                status="failed",
                evidence=(),
                traces=(),
                gaps=("分支研究已取消",),
                llm_calls=0,
                tool_calls=0,
                error="cancelled",
            )
        result = self._worker.run(request)
        if result.branch_id != request.branch_id or result.goal != request.goal:
            raise ValueError("branch worker changed branch identity")
        result = replace(
            result,
            tool_calls=self._consumed_tool_calls(request),
            budget=self._budget_receipt(request),
        )
        request.evidence_sink.append(result.evidence)
        owners = dict(request.evidence_sink.snapshot().evidence_branch_owners)
        accepted_evidence = tuple(
            item
            for item in result.evidence
            if owners.get(item.content_hash) == request.branch_id
        )
        return replace(result, evidence=accepted_evidence)

    @staticmethod
    def _consumed_tool_calls(request: BranchRequest) -> int:
        budget = request.context.root_budget
        if budget is None:
            return 0
        return max(0, int(budget.initial_calls) - int(budget.remaining_calls))

    @staticmethod
    def _budget_receipt(request: BranchRequest) -> BranchBudgetReceipt | None:
        budget = request.context.root_budget
        if budget is None:
            return None
        allocated_calls = int(budget.initial_calls)
        return BranchBudgetReceipt(
            allocated_calls=allocated_calls,
            consumed_calls=max(0, allocated_calls - int(budget.remaining_calls)),
            allocated_seconds=float(budget.initial_seconds),
            remaining_seconds=max(0.0, float(budget.remaining_seconds)),
            batch_call_cap=batch_call_cap(request.context.policy),
        )


__all__ = [
    "BranchAdmission",
    "BranchBatch",
    "BranchBudgetReceipt",
    "BranchInvalidAction",
    "BranchRequest",
    "PARENT_TAIL_LLM_RESERVE",
    "admit_branches",
    "branch_batches_from_events",
    "branch_invalid_actions_from_events",
    "branch_limits",
    "BranchResult",
    "BranchStatus",
    "MAX_SUB_RESEARCH_BRANCHES",
    "SubResearchCoordinator",
    "SubResearchResult",
    "SubResearchWorker",
]
