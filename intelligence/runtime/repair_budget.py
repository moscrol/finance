"""修复轮的预算侧：付不付得起、几个格折几次调用、按帽截秒、root ledger 记账。

从 ``services/repair_coordinator`` 搬来（`2026-09-02-repair-policy-state-machine.md`
§3.3 M5）：这些函数持有 ``RootBudgetLedger`` 并铸额度，主体是预算算术，按原 spec
§3 的定义属底座——它们本来就不该住在领域层。领域判据（tier 容忍几轮 / 上一轮算不算
进步 / 这轮缺几个格 / 这次失败属哪类）仍在 ``services`` 侧，本模块只消费它们的结论。

授予协议：**领域申请、底座授予、领域不碰账本。** ``RepairNeed``（修什么 / 属哪类 /
几个格 / 要不要重开工具）与 ``RepairWarrant``（tier 容忍度 × 上一轮进展）是领域递
过来的申请——本模块**被告知**，不自己去调领域判据；``BudgetGrant`` 是授予，
``root_budget.grant()`` 只在本模块的 ``_mint_grant`` 一处被调用。

每个 ``grant_for_*`` 只做编排：读申请 → 预算窗 → 记账，自己不再内联任何一条判据。
"""

from __future__ import annotations

from dataclasses import replace

from intelligence.services.repair_coordinator import (
    BudgetGrant,
    ProgressSnapshot,
    RepairAdmission,
    RepairGoal,
    RepairNeed,
    RepairWarrant,
    build_repair_goal,
)
from intelligence.services.research_contract import RootBudgetLedger

# 修复轮单笔授予帽（秒）的**默认值**。曾按 `min(剩余, 30, 缺口×8)` 计工时——
# 缺口少窗口就小（1 缺口=8s、3 缺口=24s）。但一次 LLM 调用的成本由**固定延迟
# 地板**主导（网络 + prompt 处理），与缺口数无关：低于地板的窗口注定超时，还要
# 白烧掉授予本身。2026-08-13 生产收据（R7/R21）：16/24s 窗 0/5 全超时，30s 窗
# 5/5 全成功。故删去按缺口缩放项，一律给满窗（仍受 remaining 与 root ledger
# 约束，fail closed 不变）。
#
# 2026-08-16：该地板是 **provider 的属性**，不是全局常数——30.0 来自对中转
# terra 的实测，换到 GLM 后两个修复轮各在整 30.0 秒超时（p90=34.4s）。故各
# grant 函数改收 `seconds_cap`，由调用方按生效 provider 注入；取值口径与实测
# 出处见 `provider_latency.py`。本模块保持 provider-neutral：它只消费一个数，
# 不认识 provider，也不读 env。
#
# 本常数仍是 `seconds_cap=None` 时的回退值，故未传参的调用方行为逐字节不变。
# **禁止把这个 30 调成新常数**（R-20260816-07 / R-21）。
_REPAIR_SECONDS_CAP = 30.0
# W5 窄补证：不超过原回合（root hard cap）的这一比例。比「再给满 30s」更
# 紧，避免补证把下游语义窗挤掉；低于 1s 仍 fail closed。
BACKFILL_BUDGET_FRACTION = 0.25
# 单轮修复的工具调用数下限 / 上限：开着工具就至少值一次调用，最多四次。
_MIN_REPAIR_CALLS = 1
_MAX_REPAIR_CALLS = 4


def _resolve_seconds_cap(seconds_cap: float | None) -> float:
    """None / 非正数 → 默认帽。fail-safe：坏输入不该把窗口静默压成 0。"""

    if seconds_cap is None:
        return _REPAIR_SECONDS_CAP
    value = float(seconds_cap)
    return value if value > 0.0 else _REPAIR_SECONDS_CAP


# ---------------------------------------------------------------------------
# 预算判据与算术（不看领域）
# ---------------------------------------------------------------------------


def can_afford_repair(
    *,
    remaining_calls: int,
    remaining_seconds: float,
    tools_open: bool,
) -> bool:
    """预算判定：工具开着就得剩至少一次调用；无论开关都得剩至少 1 秒。"""

    if tools_open and remaining_calls <= 0:
        return False
    return remaining_seconds >= 1.0


def calls_for_work_units(
    work_units: int,
    *,
    remaining_calls: int,
    tools_open: bool,
) -> int:
    """一个格值一次调用，夹在 [1, 4] 内，再受余量约束；工具关着为 0。"""

    if not tools_open:
        return 0
    return min(
        max(_MIN_REPAIR_CALLS, work_units),
        _MAX_REPAIR_CALLS,
        remaining_calls,
    )


def size_repair_window(
    *,
    work_units: int,
    remaining_calls: int,
    remaining_seconds: float,
    tools_open: bool,
    seconds_cap: float | None,
) -> tuple[int, float] | None:
    """预算算术：付得起就返回 ``(calls, seconds)``，否则 ``None``。

    秒数 = ``min(余量, 单笔帽)``；帽可能被调用方注入得很小，截断后不足 1 秒
    同样 fail closed。
    """

    if not can_afford_repair(
        remaining_calls=remaining_calls,
        remaining_seconds=remaining_seconds,
        tools_open=tools_open,
    ):
        return None
    calls = calls_for_work_units(
        work_units,
        remaining_calls=remaining_calls,
        tools_open=tools_open,
    )
    seconds = min(remaining_seconds, _resolve_seconds_cap(seconds_cap))
    if seconds < 1.0:
        return None
    return calls, seconds


def _mint_grant(
    root_budget: RootBudgetLedger,
    *,
    grant_id: str,
    goal: RepairGoal,
    calls: int,
    seconds: float,
) -> BudgetGrant | None:
    """账本写入：铸一笔并记到 root ledger；ledger 拒了（幂等 / 越帽 / 异 episode）就 ``None``。"""

    grant = BudgetGrant(
        grant_id=grant_id,
        episode_id=goal.episode_id,
        cycle=goal.cycle,
        calls_granted=calls,
        seconds_granted=seconds,
    )
    return grant if root_budget.grant(grant) else None


# ---------------------------------------------------------------------------
# 授予入口：读申请 → 预算窗 → 记账
# ---------------------------------------------------------------------------


def grant_for_progress(
    goal: RepairGoal,
    *,
    root_budget: RootBudgetLedger,
    warranted: bool,
    work_units: int,
    tools_open: bool = True,
    seconds_cap: float | None = None,
) -> BudgetGrant | None:
    """进度修复窗。``warranted`` / ``work_units`` 是领域递来的判定，这里只认不算。"""

    if not warranted:
        return None
    window = size_repair_window(
        work_units=work_units,
        remaining_calls=goal.remaining_calls,
        remaining_seconds=goal.remaining_seconds,
        tools_open=tools_open,
        seconds_cap=seconds_cap,
    )
    if window is None:
        return None
    calls, seconds = window
    return _mint_grant(
        root_budget,
        grant_id=f"grant-{goal.repair_goal_id}",
        goal=goal,
        calls=calls,
        seconds=seconds,
    )


def grant_for_cold_restart(
    goal: RepairGoal,
    progress: ProgressSnapshot,
    *,
    root_budget: RootBudgetLedger,
    work_units: int,
    seconds_cap: float | None = None,
) -> BudgetGrant | None:
    """Grant one tool-open restart turn for an episode starved of evidence.

    进度闸（``repair_is_warranted`` 的 ``coverage_delta.progressed``）要求主路径
    至少捞到 1 条证据才配修复——它挡的是「无进展还无限续命」的循环。但它把饿死型
    episode 一并挡死。生产实测两种饿死形状（2026-08-13）：

    - R7-A3：首个打偏的查询烧穿检索窗，末尾批量补发的检索在截止线上被集体判
      ``tool_timeout``，43s 零证据终局，root 余量 ~257s；
    - R9-A3：首个模型轮（规划）就把窗口吃光，**一次工具都没轮到**，零 trace。

    第二种形状说明「试过工具」不能当饿死判据——模型没偷懒，是 provider 慢。
    第三种（A1-R2）是主路径 LLM TimeoutError，stop_reason 变成
    ``model_unavailable``，检索窗也已关（``tools_open=False``）：进度闸、
    delivery 闸、旧冷启动判据三条路全死。饿死的判据因此是「零证据 +
    终态属于窗烧穿或主路径模型不可用」，由 ``classify_repair_failure`` 判定后
    经 ``cold_restart_candidate`` 传入；本函数只负责额度侧的三道闸——

    - ``cycle == 1``：只给一发，失败不再续（防循环，与进度闸的目的一致）；
    - ``after_evidence_ids`` 为空：一旦有任何证据，走常规进度/交付通道；
    - root 余量足额：fail closed，不铸空头授予。

    授予额度沿用进度修复的公式（≤30s 满窗），从 root 未分配余量铸造。
    """

    if goal.cycle != 1:
        return None
    if progress.after_evidence_ids:
        return None
    if not goal.missing_answer_elements:
        return None
    window = size_repair_window(
        work_units=work_units,
        remaining_calls=goal.remaining_calls,
        remaining_seconds=goal.remaining_seconds,
        tools_open=True,
        seconds_cap=seconds_cap,
    )
    if window is None:
        return None
    calls, seconds = window
    return _mint_grant(
        root_budget,
        grant_id=f"cold-restart-{goal.repair_goal_id}",
        goal=goal,
        calls=calls,
        seconds=seconds,
    )


def grant_for_delivery_repair(
    goal: RepairGoal,
    *,
    root_budget: RootBudgetLedger,
    cycle_allowed: bool,
    evidence_count: int,
    seconds_cap: float | None = None,
) -> BudgetGrant | None:
    """Grant one tool-closed delivery turn from already collected evidence.

    Research continuation still requires provenance-backed coverage progress via
    :func:`grant_for_progress`.  This narrower grant exists for the opposite
    seam: the research turn timed out *after* collecting evidence but *before*
    it produced a draft or bindings.  Requiring an already-closed output gap in
    that state would make repair conditional on the work repair must perform.

    The grant cannot reopen tools, cannot run without evidence, and remains
    bounded by the tier cycle cap (``cycle_allowed``, judged by the domain) and
    the root seconds ledger.
    """

    if evidence_count <= 0:
        return None
    if not cycle_allowed:
        return None
    if not goal.missing_answer_elements:
        return None
    window = size_repair_window(
        work_units=0,
        remaining_calls=0,
        remaining_seconds=goal.remaining_seconds,
        tools_open=False,
        seconds_cap=seconds_cap,
    )
    if window is None:
        return None
    _, seconds = window
    return _mint_grant(
        root_budget,
        grant_id=f"delivery-grant-{goal.repair_goal_id}",
        goal=goal,
        calls=0,
        seconds=seconds,
    )


def grant_for_transient_model_retry(
    goal: RepairGoal,
    *,
    root_budget: RootBudgetLedger,
    attempt: int = 1,
    seconds_cap: float | None = None,
) -> BudgetGrant | None:
    """超时把修复窗口烧穿后，从 hard-cap 未分配余量再铸一笔秒数。

    历史背景：修复授予曾是 ``min(剩余, 30, 缺口×8)``，常只有 8 秒（该缩放项
    已删，见 ``_REPAIR_SECONDS_CAP``）；生产 ``llm_timeout`` 是 75 秒。
    第一次 ``complete`` 的 timeout 因此等于整笔授予，真实 TimeoutError
    会把 repair deadline 吃到 0——「失败后再看余量」这条重试闸门对超时是
    死代码。即使首笔已是满窗 30s，root 剩余不足时仍会出现小窗，本函数仍有意义。

    尺寸必须按 **root 未分配余量** 算，不能按 ``goal.remaining_seconds``：
    admission 已把后者替换成刚烧穿的那笔授予（生产实测 16s / 8s），按它
    重铸等于用同样大小的窗口对着 P50≈28s 的 provider 再撞一次——
    2026-08-13 R4 验收 A4/A5/A8/A9/A10 五题全是这个死法。

    这笔 grant 动的是 research 从未分配的 hard-cap 余量（synthesis
    reserve 那截），    不重开工具槽，不突破调用方注入的单笔帽（默认 30 秒）。铸不出就 fail
    closed。grant_id 按 (repair_goal, attempt) 固定：同一 attempt 重复
    调用被 root ledger 拒掉（幂等防呆），不同 attempt 各铸各的——
    熔断次数由调用方的 ``transient_retries_left`` 独占，账本只管余量。
    """

    headroom = max(
        0.0,
        float(root_budget.hard_seconds_cap) - float(root_budget.allocated_seconds),
    )
    seconds = min(headroom, _resolve_seconds_cap(seconds_cap))
    if seconds < 1.0:
        return None
    suffix = "" if attempt <= 1 else f"-{attempt}"
    return _mint_grant(
        root_budget,
        grant_id=f"transient-retry-{goal.repair_goal_id}{suffix}",
        goal=goal,
        calls=0,
        seconds=seconds,
    )


def admit_repair(
    need: RepairNeed,
    warrant: RepairWarrant,
    *,
    episode_id: str,
    attempted_actions: tuple[str, ...] = (),
    previous_progress: ProgressSnapshot,
    remaining_calls: int,
    remaining_seconds: float,
    cycle: int,
    root_budget: RootBudgetLedger,
    tools_open: bool = True,
    allow_delivery_repair: bool = True,
    evidence_count: int = 0,
    seconds_cap: float | None = None,
) -> RepairAdmission | None:
    """Build one goal and admit exactly one budget grant.

    ``need``（修什么 / 属哪类 / 几个格）与 ``warrant``（tier 容忍度 × 进展）是领域
    递来的申请；本函数只做底座这边的编排——按固定优先级试三种窗（进度 → 交付 →
    冷启动），前一种铸不出（领域不批或账本拒）就试下一种。``allow_delivery_repair``
    （交付修复只许一次）是 cycle 状态，属这里，不属领域。

    ``need.shape.contract_rewrite`` is the track-contract expression seam
    (四态 / TTL / 下期关注): rewrite the draft from already collected
    evidence, do not reopen tools even if the research window is still open.
    """

    goal = build_repair_goal(
        episode_id=episode_id,
        missing_outputs=need.missing_outputs,
        missing_capabilities=need.missing_capabilities,
        rejected_claims=need.rejected_claims,
        attempted_actions=attempted_actions,
        previous_progress=previous_progress,
        remaining_calls=remaining_calls,
        remaining_seconds=remaining_seconds,
        cycle=cycle,
    )
    delivery_candidate = allow_delivery_repair and need.shape.delivery
    contract_rewrite_candidate = need.shape.contract_rewrite
    grant: BudgetGrant | None = None
    delivery_only = False
    cold_restart = False
    if not delivery_candidate and not contract_rewrite_candidate:
        grant = grant_for_progress(
            goal,
            root_budget=root_budget,
            warranted=warrant.warranted,
            work_units=need.work_units,
            tools_open=tools_open,
            seconds_cap=seconds_cap,
        )
    if (
        grant is None
        and allow_delivery_repair
        and (not tools_open or delivery_candidate or contract_rewrite_candidate)
        and evidence_count > 0
        and need.missing_outputs
    ):
        grant = grant_for_delivery_repair(
            goal,
            root_budget=root_budget,
            cycle_allowed=warrant.cycle_allowed,
            evidence_count=evidence_count,
            seconds_cap=seconds_cap,
        )
        delivery_only = grant is not None
    if (
        grant is None
        and not delivery_candidate
        and not contract_rewrite_candidate
        and need.needs_tools
        and evidence_count == 0
        and need.missing_outputs
    ):
        grant = grant_for_cold_restart(
            goal,
            previous_progress,
            root_budget=root_budget,
            work_units=need.work_units,
            seconds_cap=seconds_cap,
        )
        cold_restart = grant is not None
    if grant is None:
        return None
    return RepairAdmission(
        goal=replace(
            goal,
            remaining_calls=grant.calls_granted,
            remaining_seconds=grant.seconds_granted,
            reopen_tools=cold_restart,
        ),
        grant=grant,
        delivery_only=delivery_only,
    )


def grant_for_backfill(
    goal: RepairGoal,
    *,
    root_budget: RootBudgetLedger,
    original_seconds: float,
    tools_open: bool = True,
    seconds_cap: float | None = None,
) -> BudgetGrant | None:
    """Grant one narrow evidence-fetch turn. No progress-gate, no extra cycles.

    进度闸 ``repair_is_warranted`` 要求主路径已经有独立新证据——数字型阻断常常
    是「证据在、数字不在」，会被误判成不配再修。补证自己的闸是：工具开着、
    指定了 capability、预算 ≤ 原回合 25%、且至少留得下一整次调用。
    """

    if not tools_open:
        return None
    if not goal.missing_evidence_modes:
        return None
    if goal.remaining_calls < 1:
        return None
    fraction_cap = max(0.0, float(original_seconds)) * BACKFILL_BUDGET_FRACTION
    seconds = min(
        goal.remaining_seconds,
        fraction_cap,
        _resolve_seconds_cap(seconds_cap),
    )
    if seconds < 1.0:
        return None
    return _mint_grant(
        root_budget,
        grant_id=f"backfill-{goal.repair_goal_id}",
        goal=goal,
        calls=1,
        seconds=seconds,
    )


def admit_backfill_repair(
    *,
    episode_id: str,
    missing_outputs: tuple[str, ...] = (),
    missing_capabilities: tuple[str, ...] = (),
    attempted_actions: tuple[str, ...] = (),
    previous_progress: ProgressSnapshot,
    remaining_calls: int,
    remaining_seconds: float,
    cycle: int,
    root_budget: RootBudgetLedger,
    tools_open: bool = True,
    seconds_cap: float | None = None,
) -> RepairAdmission | None:
    """Admit exactly one IssueCode-triggered backfill turn."""

    if not missing_capabilities:
        return None
    goal = build_repair_goal(
        episode_id=episode_id,
        missing_outputs=missing_outputs,
        missing_capabilities=missing_capabilities,
        previous_progress=previous_progress,
        remaining_calls=remaining_calls,
        remaining_seconds=remaining_seconds,
        cycle=cycle,
        attempted_actions=attempted_actions,
    )
    grant = grant_for_backfill(
        goal,
        root_budget=root_budget,
        original_seconds=float(root_budget.hard_seconds_cap),
        tools_open=tools_open,
        seconds_cap=seconds_cap,
    )
    if grant is None:
        return None
    return RepairAdmission(
        goal=replace(
            goal,
            remaining_calls=grant.calls_granted,
            remaining_seconds=grant.seconds_granted,
        ),
        grant=grant,
        backfill=True,
    )


__all__ = [
    "BACKFILL_BUDGET_FRACTION",
    "admit_backfill_repair",
    "admit_repair",
    "calls_for_work_units",
    "can_afford_repair",
    "grant_for_backfill",
    "grant_for_cold_restart",
    "grant_for_delivery_repair",
    "grant_for_progress",
    "grant_for_transient_model_retry",
    "size_repair_window",
]
