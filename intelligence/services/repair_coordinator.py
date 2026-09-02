"""Provider-neutral repair goals and progress predicates.

The coordinator describes missing work; it never invents a query or selects a
tool. The primary model retains that decision inside the same episode.

模块内按两层分组（`2026-09-02-repair-policy-state-machine.md` §3）：

- **领域判据**（不看预算）：这个 tier 容忍第几轮、上一轮算不算进步、这轮要补
  几个格。抽 `repair_policy` 接缝时这一组进 harness。
- **预算判据与算术**（不看领域）：付不付得起、几个格折几次调用、秒数按帽截断、
  root ledger 记账。这一组留底座。

每个 `grant_for_*` 只做编排：领域闸 → 预算窗 → 记账，自己不再内联任何一条判据。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4

from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.episode_verifier import VerifiedEpisodeOutcome
from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.research_contract import RootBudgetLedger
from intelligence.services.track_contract import is_contract_rewrite_only

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


def _resolve_seconds_cap(seconds_cap: float | None) -> float:
    """None / 非正数 → 默认帽。fail-safe：坏输入不该把窗口静默压成 0。"""

    if seconds_cap is None:
        return _REPAIR_SECONDS_CAP
    value = float(seconds_cap)
    return value if value > 0.0 else _REPAIR_SECONDS_CAP


@dataclass(frozen=True)
class CoverageDelta:
    new_evidence: int
    narrowed_gaps: int
    newly_supported_outputs: int

    @property
    def progressed(self) -> bool:
        return self.new_evidence >= 1 and (
            self.narrowed_gaps >= 1 or self.newly_supported_outputs >= 1
        )


@dataclass(frozen=True)
class ProgressSnapshot:
    before_evidence_ids: tuple[str, ...]
    after_evidence_ids: tuple[str, ...]
    before_covered_outputs: tuple[str, ...]
    after_covered_outputs: tuple[str, ...]
    before_open_gaps: tuple[str, ...]
    after_open_gaps: tuple[str, ...]
    independent_source_families: tuple[str, ...]
    before_evidence_source_families: tuple[tuple[str, str], ...] = ()
    after_evidence_source_families: tuple[tuple[str, str], ...] = ()
    before_evidence_targets: tuple[tuple[str, tuple[str, ...]], ...] = ()
    after_evidence_targets: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def effective_new_evidence(self) -> int:
        before_ids = set(self.before_evidence_ids)
        before_families = {
            family for _, family in self.before_evidence_source_families
        }
        after_pairs = tuple(self.after_evidence_source_families)
        after_targets = dict(self.after_evidence_targets)
        if not after_pairs or not after_targets:
            return 0
        before_outputs = set(self.before_covered_outputs)
        families = {
            family
            for evidence_id, family in after_pairs
            if evidence_id not in before_ids
            and family not in before_families
            and (
                any(
                    target not in before_outputs
                    for target in after_targets.get(evidence_id, ())
                )
            )
        }
        return len(families)

    @property
    def coverage_delta(self) -> CoverageDelta:
        return CoverageDelta(
            new_evidence=self.effective_new_evidence,
            narrowed_gaps=len(
                set(self.before_open_gaps) - set(self.after_open_gaps)
            ),
            newly_supported_outputs=len(
                set(self.after_covered_outputs) - set(self.before_covered_outputs)
            ),
        )

    def to_dict(self) -> dict[str, object]:
        delta = self.coverage_delta
        return {
            "before_evidence_ids": list(self.before_evidence_ids),
            "after_evidence_ids": list(self.after_evidence_ids),
            "before_covered_outputs": list(self.before_covered_outputs),
            "after_covered_outputs": list(self.after_covered_outputs),
            "before_open_gaps": list(self.before_open_gaps),
            "after_open_gaps": list(self.after_open_gaps),
            "independent_source_families": list(self.independent_source_families),
            "before_evidence_source_families": [
                list(item) for item in self.before_evidence_source_families
            ],
            "after_evidence_source_families": [
                list(item) for item in self.after_evidence_source_families
            ],
            "before_evidence_targets": [
                [evidence_id, list(targets)]
                for evidence_id, targets in self.before_evidence_targets
            ],
            "after_evidence_targets": [
                [evidence_id, list(targets)]
                for evidence_id, targets in self.after_evidence_targets
            ],
            "coverage_delta": {
                "new_evidence": delta.new_evidence,
                "narrowed_gaps": delta.narrowed_gaps,
                "newly_supported_outputs": delta.newly_supported_outputs,
            },
        }


@dataclass(frozen=True)
class BudgetGrant:
    grant_id: str
    episode_id: str
    cycle: int
    calls_granted: int
    seconds_granted: float


@dataclass(frozen=True)
class RepairGoal:
    episode_id: str
    repair_goal_id: str
    cycle: int
    missing_answer_elements: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    missing_evidence_modes: tuple[str, ...]
    attempted_actions: tuple[str, ...]
    evidence_progress: CoverageDelta
    remaining_calls: int
    remaining_seconds: float
    # 冷启动修复专用：主检索窗已烧穿时，允许修复轮在授予的窗口内重开工具。
    # 只由 admit_repair 在 grant_for_cold_restart 命中时置位，模型无权申请。
    reopen_tools: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "repair_goal_id": self.repair_goal_id,
            "cycle": self.cycle,
            "missing_answer_elements": list(self.missing_answer_elements),
            "unsupported_claims": list(self.unsupported_claims),
            "missing_evidence_modes": list(self.missing_evidence_modes),
            "attempted_actions": list(self.attempted_actions),
            "evidence_progress": {
                "new_evidence": self.evidence_progress.new_evidence,
                "narrowed_gaps": self.evidence_progress.narrowed_gaps,
                "newly_supported_outputs": self.evidence_progress.newly_supported_outputs,
            },
            "remaining_calls": self.remaining_calls,
            "remaining_seconds": self.remaining_seconds,
            "reopen_tools": self.reopen_tools,
        }


@dataclass(frozen=True)
class RepairAdmission:
    """One code-owned repair decision ready for an Episode to execute."""

    goal: RepairGoal
    grant: BudgetGrant
    delivery_only: bool = False
    backfill: bool = False


def _unique(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(value).strip() for value in (values or ()) if str(value).strip())
    )


def progress_from_ledger(
    before: EvidenceLedgerSnapshot,
    after: EvidenceLedgerSnapshot,
) -> ProgressSnapshot:
    return ProgressSnapshot(
        before_evidence_ids=before.evidence_ids,
        after_evidence_ids=after.evidence_ids,
        before_covered_outputs=before.covered_outputs,
        after_covered_outputs=after.covered_outputs,
        before_open_gaps=before.open_gaps,
        after_open_gaps=after.open_gaps,
        independent_source_families=after.independent_source_families,
        before_evidence_source_families=before.evidence_source_families,
        after_evidence_source_families=after.evidence_source_families,
        before_evidence_targets=before.evidence_targets,
        after_evidence_targets=after.evidence_targets,
    )


def build_repair_goal(
    *,
    episode_id: str,
    missing_outputs: tuple[str, ...] = (),
    missing_capabilities: tuple[str, ...] = (),
    rejected_claims: tuple[str, ...] = (),
    attempted_actions: tuple[str, ...] = (),
    previous_progress: ProgressSnapshot,
    remaining_calls: int,
    remaining_seconds: float,
    cycle: int = 1,
) -> RepairGoal:
    episode = str(episode_id or "").strip()
    if not episode:
        raise ValueError("episode_id must be non-empty")
    if cycle < 1:
        raise ValueError("repair cycle must be positive")
    return RepairGoal(
        episode_id=episode,
        repair_goal_id=f"repair-{episode}-{cycle}-{uuid4().hex[:10]}",
        cycle=cycle,
        missing_answer_elements=_unique(missing_outputs),
        unsupported_claims=_unique(rejected_claims),
        missing_evidence_modes=_unique(missing_capabilities),
        attempted_actions=_unique(attempted_actions),
        evidence_progress=previous_progress.coverage_delta,
        remaining_calls=max(0, int(remaining_calls)),
        remaining_seconds=max(0.0, float(remaining_seconds)),
    )


def unreachable_repair_goal(
    goal: RepairGoal,
    *,
    evidence_output_ids: frozenset[str] | set[str],
) -> tuple[str, ...]:
    """返回本轮修复**结构性不可能补上**的那些 evidence 必填格。

    2026-08-21 生产实测（`run_20260821_114642_385979`，诊断见
    `docs/verification/2026-08-21-judge-quantity-blindspot.md`）：

    ```
    missing_answer_elements: ["direct_assessment", "counterpoint"]   ← 目标
    remaining_calls: 0                                              ← 工具额度为 0
    reopen_tools: false                                             ← 不许重开取证
    granted_seconds: 40.0  (timeout_configured: 75.0)               ← 时钟已被研究阶段花掉
    ```

    修复轮被要求补两个 **evidence 口径**的必填格，同时被禁止取证。
    这不是「模型没修好」，是**任务本身不可能**——再强的模型也变不出新证据。
    它空转 40 秒后残稿发布，读数上还表现为「repair 跑过了但没用」。

    按约束三筛（`harness-reference/PLAYBOOK.md`）：这条限制拦的是修复者的取证
    能力，失效时答案残缺（变笨），且**模型越强越挡路**——因为它本可以取证补齐。

    本函数不放宽任何限制、不加任何预算，只把「不可能」显式化：调用方据此
    跳过空转，直接落结构缺口并如实说明缺什么，而不是烧掉时钟再发残稿。
    ``model_reasoning`` 口径的格不在此列——它们本来就不需要新证据。
    """

    if goal.reopen_tools or goal.remaining_calls > 0:
        return ()
    return tuple(
        output_id
        for output_id in goal.missing_answer_elements
        if output_id in evidence_output_ids
    )


# ---------------------------------------------------------------------------
# 领域判据（不看预算）
# ---------------------------------------------------------------------------


def max_repair_cycles_for_tier(research_tier: str) -> int:
    tier = str(research_tier or "").strip().lower()
    if tier == "deep":
        return 3
    if tier in {"quick", "standard"}:
        return 1
    raise ValueError(f"unsupported repair research tier: {research_tier}")


def cycle_within_tier(cycle: int, *, research_tier: str) -> bool:
    """研究强度决定容忍几轮修复：1 ≤ cycle ≤ tier 上限。"""

    return 1 <= cycle <= max_repair_cycles_for_tier(research_tier)


def repair_is_warranted(
    progress: ProgressSnapshot,
    *,
    cycle: int,
    research_tier: str,
) -> bool:
    """领域判定：这个 tier 还容忍这一轮，且上一轮真有独立证据进展。

    不看预算——付不付得起是 :func:`can_afford_repair` 的事。
    """

    return (
        cycle_within_tier(cycle, research_tier=research_tier)
        and progress.coverage_delta.progressed
    )


def repair_work_units(goal: RepairGoal) -> int:
    """领域量：这轮要补几个格（answer 必填格 + evidence 口径）。

    只数格，不折算成调用次数——「一个格值几次调用」是预算换算
    （:func:`calls_for_work_units`）。
    """

    return len(goal.missing_answer_elements) + len(goal.missing_evidence_modes)


# 领域对失败终局的解释：这次失败属于哪一类。观察量是 stop_reason，不是 trace。
DELIVERY_REPAIR_STOP_REASONS = frozenset(
    {"sdk_invalid_finish", "sdk_invalid_repair_finish", "sdk_timeout"}
)
# 饿死型冷启动：检索窗烧穿，或主路径 LLM 超时/异常，且零证据。
# A1-R2 是后者——TimeoutError 走 model_unavailable，tools_open 已关，
# delivery 要证据，进度闸要新证据，三条路全死。不能把「模型主动收场」
# （model_finish）算进来，那是零证据降级信号，不是饿死。
COLD_RESTART_STOP_REASONS = frozenset({"deadline_exhausted", "model_unavailable"})


@dataclass(frozen=True)
class RepairFailureShape:
    """一次失败终局在领域眼里的形状。三者互斥与否由 ``admit_repair`` 分流决定。

    - ``delivery``：有证据、有结构缺口，但没写出稿或没绑定——tool-closed 交付修复。
    - ``cold_restart``：零证据饿死（窗烧穿 / 主路径模型不可用）——重开工具一发。
    - ``contract_rewrite``：缺的全是跟踪契约表达槽——从既有证据重写，不开工具。

    不看预算、不看 cycle 状态（「交付修复只许一次」是底座的账，由调用方叠）。
    """

    delivery: bool
    cold_restart: bool
    contract_rewrite: bool


def classify_repair_failure(
    outcome: AgentOutcome,
    structural: VerifiedEpisodeOutcome,
    *,
    missing_outputs: tuple[str, ...],
    rejected_claims: tuple[str, ...],
    semantic_gap_outputs: tuple[str, ...],
) -> RepairFailureShape:
    """领域失败分类。``missing_outputs`` 是结构缺口 ∪ 语义缺口（调用方已合并）。"""

    has_evidence = bool(outcome.evidence)
    return RepairFailureShape(
        delivery=bool(
            outcome.stop_reason in DELIVERY_REPAIR_STOP_REASONS
            and has_evidence
            and structural.missing_outputs
            and (not outcome.draft.strip() or not outcome.bindings)
        ),
        cold_restart=(
            outcome.stop_reason in COLD_RESTART_STOP_REASONS and not has_evidence
        ),
        contract_rewrite=is_contract_rewrite_only(
            missing_outputs,
            rejected_claims=rejected_claims,
            semantic_gap_outputs=semantic_gap_outputs,
        ),
    )


# ---------------------------------------------------------------------------
# 预算判据与算术（不看领域）
# ---------------------------------------------------------------------------

# 单轮修复的工具调用数下限 / 上限：开着工具就至少值一次调用，最多四次。
_MIN_REPAIR_CALLS = 1
_MAX_REPAIR_CALLS = 4


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
# 授予入口：领域闸 → 预算窗 → 记账
# ---------------------------------------------------------------------------


def grant_for_progress(
    goal: RepairGoal,
    progress: ProgressSnapshot,
    *,
    root_budget: RootBudgetLedger,
    research_tier: str,
    tools_open: bool = True,
    seconds_cap: float | None = None,
) -> BudgetGrant | None:
    if not repair_is_warranted(progress, cycle=goal.cycle, research_tier=research_tier):
        return None
    window = size_repair_window(
        work_units=repair_work_units(goal),
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
    终态属于窗烧穿或主路径模型不可用」，由调用方以
    ``cold_restart_candidate`` 传入；本函数只负责额度侧的三道闸——

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
        work_units=repair_work_units(goal),
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
    research_tier: str,
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
    bounded by the code-owned tier cycle cap and root seconds ledger.
    """

    if evidence_count <= 0:
        return None
    if not cycle_within_tier(goal.cycle, research_tier=research_tier):
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
    *,
    episode_id: str,
    missing_outputs: tuple[str, ...] = (),
    missing_capabilities: tuple[str, ...] = (),
    rejected_claims: tuple[str, ...] = (),
    attempted_actions: tuple[str, ...] = (),
    previous_progress: ProgressSnapshot,
    remaining_calls: int,
    remaining_seconds: float,
    cycle: int,
    root_budget: RootBudgetLedger,
    research_tier: str,
    tools_open: bool = True,
    allow_delivery_repair: bool = True,
    delivery_candidate: bool = False,
    contract_rewrite_candidate: bool = False,
    cold_restart_candidate: bool = False,
    evidence_count: int = 0,
    seconds_cap: float | None = None,
) -> RepairAdmission | None:
    """Build one goal and admit exactly one budget grant.

    The coordinator owns the policy choice between evidence-progress repair and
    tool-closed delivery repair. Callers receive one immutable decision and do
    not need to duplicate cycle, tier, or root-budget rules.

    ``contract_rewrite_candidate`` is the track-contract expression seam
    (四态 / TTL / 下期关注): rewrite the draft from already collected
    evidence, do not reopen tools even if the research window is still open.
    """

    goal = build_repair_goal(
        episode_id=episode_id,
        missing_outputs=missing_outputs,
        missing_capabilities=missing_capabilities,
        rejected_claims=rejected_claims,
        attempted_actions=attempted_actions,
        previous_progress=previous_progress,
        remaining_calls=remaining_calls,
        remaining_seconds=remaining_seconds,
        cycle=cycle,
    )
    grant: BudgetGrant | None = None
    delivery_only = False
    cold_restart = False
    if not delivery_candidate and not contract_rewrite_candidate:
        grant = grant_for_progress(
            goal,
            previous_progress,
            root_budget=root_budget,
            research_tier=research_tier,
            tools_open=tools_open,
            seconds_cap=seconds_cap,
        )
    if (
        grant is None
        and allow_delivery_repair
        and (not tools_open or delivery_candidate or contract_rewrite_candidate)
        and evidence_count > 0
        and missing_outputs
    ):
        grant = grant_for_delivery_repair(
            goal,
            root_budget=root_budget,
            research_tier=research_tier,
            evidence_count=evidence_count,
            seconds_cap=seconds_cap,
        )
        delivery_only = grant is not None
    if (
        grant is None
        and not delivery_candidate
        and not contract_rewrite_candidate
        and cold_restart_candidate
        and evidence_count == 0
        and missing_outputs
    ):
        grant = grant_for_cold_restart(
            goal,
            previous_progress,
            root_budget=root_budget,
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
    "COLD_RESTART_STOP_REASONS",
    "DELIVERY_REPAIR_STOP_REASONS",
    "BudgetGrant",
    "CoverageDelta",
    "ProgressSnapshot",
    "RepairAdmission",
    "RepairFailureShape",
    "RepairGoal",
    "admit_backfill_repair",
    "admit_repair",
    "build_repair_goal",
    "calls_for_work_units",
    "can_afford_repair",
    "classify_repair_failure",
    "cycle_within_tier",
    "grant_for_backfill",
    "grant_for_cold_restart",
    "grant_for_delivery_repair",
    "grant_for_progress",
    "grant_for_transient_model_retry",
    "max_repair_cycles_for_tier",
    "progress_from_ledger",
    "repair_is_warranted",
    "repair_work_units",
    "size_repair_window",
    "unreachable_repair_goal",
]
