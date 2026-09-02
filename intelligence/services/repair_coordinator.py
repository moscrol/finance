"""Provider-neutral repair goals and progress predicates.

The coordinator describes missing work; it never invents a query or selects a
tool. The primary model retains that decision inside the same episode.

本模块只剩**领域侧**（`2026-09-02-repair-policy-state-machine.md` §3）：修复目标与
进度快照的值对象、「修什么」（`build_repair_goal` / `unreachable_repair_goal`）、
「这个 tier 容忍第几轮 / 上一轮算不算进步 / 这轮缺几个格」（`repair_is_warranted` /
`repair_work_units`）、「这次失败属于哪一类」（`classify_repair_failure`）。
全部不看预算、不碰账本。抽 `repair_policy` 接缝时这一组进 harness。

预算侧（付不付得起、几个格折几次调用、按帽截秒、`root_budget.grant()` 记账、
五种 `grant_for_*` 与两个 `admit_*`）在 `intelligence/runtime/repair_budget.py`：
领域申请、底座授予。
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.episode_verifier import VerifiedEpisodeOutcome
from intelligence.services.evidence_ledger import EvidenceLedgerSnapshot
from intelligence.services.track_contract import is_contract_rewrite_only


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


__all__ = [
    "COLD_RESTART_STOP_REASONS",
    "DELIVERY_REPAIR_STOP_REASONS",
    "BudgetGrant",
    "CoverageDelta",
    "ProgressSnapshot",
    "RepairAdmission",
    "RepairFailureShape",
    "RepairGoal",
    "build_repair_goal",
    "classify_repair_failure",
    "cycle_within_tier",
    "max_repair_cycles_for_tier",
    "progress_from_ledger",
    "repair_is_warranted",
    "repair_work_units",
    "unreachable_repair_goal",
]
