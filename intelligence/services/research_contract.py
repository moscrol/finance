from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from threading import RLock
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast
from weakref import WeakValueDictionary

from intelligence.services.query_resolution import (
    QueryResolution,
    classify_reference,
)
from intelligence.services.episode_effects import unknown_effects_from_payload
from intelligence.services.query_understanding import QueryEnvelope
from intelligence.services.route_table import owner_skills_from_route_table
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.task_frame import TaskFrame
from intelligence.services.material_contract import MaterialContract
from intelligence.services.material_grounding import MaterialGrounding
from intelligence.services.premise_financial_calculation import PremiseCalculation
from intelligence.services.material_permissions import LOCAL_EVIDENCE_PRODUCERS, restrict_read_capabilities
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.user_task import (
    requests_previous_answer_review,
    top_level_message_text,
)

if TYPE_CHECKING:
    from intelligence.services.episode_entry_identity import EpisodeEntryIdentity
    from intelligence.services.prior_evidence import PriorTurnEvidence

AnswerOwner: TypeAlias = Literal[
    "stock-deep-dive",
    "financial-analysis",
    "news-impact",
    "theme-research",
]
OwnerExecutionMode: TypeAlias = Literal["inline", "subtask"]
ClaimType: TypeAlias = Literal["fact", "inference", "expectation"]
GroundingMode: TypeAlias = Literal["evidence", "user_premise", "model_reasoning"]
InformationCutoffSource: TypeAlias = Literal[
    "requested",
    "latest_available",
    "runtime_default",
]
StageStatus: TypeAlias = Literal[
    "pending",
    "completed",
    "partial",
    "timeout",
    "failed",
    "skipped",
]

RESEARCH_OWNER_IDS = frozenset(
    {
        "stock-deep-dive",
        "financial-analysis",
        "news-impact",
        "theme-research",
    }
)
QUESTION_OWNER_SKILLS: dict[str, AnswerOwner] = {
    question_type: cast(AnswerOwner, owner)
    for question_type, owner in owner_skills_from_route_table().items()
    if owner in RESEARCH_OWNER_IDS
}
OWNER_RETRIEVAL_STAGES: dict[AnswerOwner, tuple[str, ...]] = {
    "stock-deep-dive": (
        "company_master",
        "company_evidence",
        "financial_transmission",
        "market_choice",
        "counterevidence",
    ),
    "financial-analysis": (
        "report_period",
        "financial_metrics",
        "segment_disclosure",
        "prior_period_comparison",
    ),
    "news-impact": (
        "original_disclosure",
        "event_facts",
        "external_news",
        "impact_transmission",
        "substitutes_and_harmed_directions",
    ),
    "theme-research": (
        "definition",
        "chain_stages",
        "company_mapping",
        "market_lifecycle",
        "historical_analogs",
        "scenario_tree",
        "counterevidence",
    ),
}


@dataclass(frozen=True)
class OwnerWorkflowSpec:
    owner: AnswerOwner
    label: str
    execution_mode: OwnerExecutionMode
    preset: str
    required_skill_ids: tuple[str, ...]
    retrieval_stages: tuple[str, ...]
    output_schema: str
    presentation_kind: str
    max_wall_time_seconds: int

    def __post_init__(self) -> None:
        if self.execution_mode not in {"inline", "subtask"}:
            raise ValueError("unsupported owner execution mode")
        if self.max_wall_time_seconds <= 0:
            raise ValueError("owner workflow wall time must be positive")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


OWNER_WORKFLOW_SPECS: dict[AnswerOwner, OwnerWorkflowSpec] = {
    "stock-deep-dive": OwnerWorkflowSpec(
        owner="stock-deep-dive",
        label="个股深挖",
        execution_mode="inline",
        preset="finance-researcher",
        required_skill_ids=("finance-mode", "stock-deep-dive"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["stock-deep-dive"],
        output_schema="AnswerSpec",
        presentation_kind="theme_research",
        max_wall_time_seconds=240,
    ),
    "financial-analysis": OwnerWorkflowSpec(
        owner="financial-analysis",
        label="财务分析",
        execution_mode="inline",
        preset="finance-financial-analyst",
        required_skill_ids=("finance-mode", "financial-analysis"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["financial-analysis"],
        output_schema="AnswerSpec",
        presentation_kind="base_finance",
        max_wall_time_seconds=240,
    ),
    "news-impact": OwnerWorkflowSpec(
        owner="news-impact",
        label="消息与公告冲击",
        execution_mode="inline",
        preset="finance-event-analyst",
        required_skill_ids=("finance-mode", "news-impact"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["news-impact"],
        output_schema="AnswerSpec",
        presentation_kind="theme_research",
        max_wall_time_seconds=240,
    ),
    "theme-research": OwnerWorkflowSpec(
        owner="theme-research",
        label="题材研究",
        execution_mode="inline",
        preset="finance-theme-researcher",
        required_skill_ids=("finance-mode", "theme-research"),
        retrieval_stages=OWNER_RETRIEVAL_STAGES["theme-research"],
        output_schema="AnswerSpec",
        presentation_kind="theme_research",
        max_wall_time_seconds=240,
    ),
}

_COMPARISON_PATTERN = re.compile(r"(?:比较|对比|相比|和.+比|与.+比)")
_CONTEXT_DEPENDENT_RESEARCH_PATTERN = re.compile(
    r"(?:原因|为什么|证伪|反证|弹性|赔率|空间|受益|一阶|二阶|"
    r"历史类似|历史类比|真实订单|订单|验证清单|验证路径|下周|"
    r"催化|风险|毛利率|净利率|收入|利润|现金流|兑现|替代标的|"
    r"哪个更|分别是谁|怎么看|如何验证|"
    r"(?:这个|那个|这次|那次)(?:反弹|修复))"
)
_CONTEXT_DEPENDENT_RESEARCH_PREFIX_PATTERN = re.compile(
    r"^(?:毛利率|净利率|收入|营收|利润|现金流|原因|为什么|"
    r"历史类似|历史类比|真实订单|订单|验证清单|验证路径|"
    r"下周|一阶|二阶|哪些反证|哪些风险)"
)
_EXPLICIT_SWITCH_PATTERN = re.compile(
    r"(?:改看|换成|切换到|另外看|再分析|重新分析|转向|换个话题|换个问题|另一个问题)"
)
_TASK_SWITCH_PATTERNS: dict[str, re.Pattern[str]] = {
    "financial_analysis": re.compile(
        r"(财报|年报|季报|中报|收入|营收|利润|毛利率|净利率|现金流)"
    ),
    "news_impact": re.compile(r"(公告|新闻|消息|事件).{0,12}(影响|冲击|利好|利空)"),
    "stock_deep_dive": re.compile(
        r"(个股深挖|公司深挖|上涨空间|后续空间|还能涨|估值|贵不贵)"
    ),
    "theme_analysis": re.compile(r"(题材|产业链|板块).{0,12}(研究|分析|梳理|深挖)"),
}


@dataclass(frozen=True)
class TurnIntent:
    primary_subject: str | None
    secondary_topics: tuple[str, ...]
    question_type: str
    answer_owner: AnswerOwner | None
    comparison_entities: tuple[str, ...]
    inherited_from_turn: str | None
    evidence_atom_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    stage_artifact_ids: tuple[str, ...] = ()
    time_horizon: str = "unspecified"
    operators: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    timeframe: str | None = None
    task_frame_hash: str = ""
    pending_task_frame: dict[str, object] | None = None
    clarification_rounds: int = 0
    history_intent: HistoryIntent | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> TurnIntent | None:
        if not isinstance(value, dict):
            return None
        try:
            primary_subject = value.get("primary_subject")
            question_type = value["question_type"]
            answer_owner = value.get("answer_owner")
            inherited_from_turn = value.get("inherited_from_turn")
            secondary_topics = value.get("secondary_topics", ())
            comparison_entities = value.get("comparison_entities", ())
            evidence_atom_ids = value.get("evidence_atom_ids", ())
            skill_ids = value.get("skill_ids", ())
            stage_artifact_ids = value.get("stage_artifact_ids", ())
            time_horizon = value.get("time_horizon", "unspecified")
            operators = value.get("operators", ())
            required_outputs = value.get("required_outputs", ())
            timeframe = value.get("timeframe")
            task_frame_hash = value.get("task_frame_hash", "")
            pending_task_frame = value.get("pending_task_frame")
            clarification_rounds = value.get("clarification_rounds", 0)
        except KeyError:
            return None
        if primary_subject is not None and not isinstance(primary_subject, str):
            return None
        if not isinstance(question_type, str):
            return None
        if answer_owner is not None and answer_owner not in RESEARCH_OWNER_IDS:
            return None
        if inherited_from_turn is not None and not isinstance(inherited_from_turn, str):
            return None
        if not isinstance(time_horizon, str):
            return None
        if timeframe is not None and not isinstance(timeframe, str):
            return None
        if not isinstance(task_frame_hash, str):
            return None
        if pending_task_frame is not None and not isinstance(
            pending_task_frame,
            dict,
        ):
            return None
        if (
            isinstance(clarification_rounds, bool)
            or not isinstance(clarification_rounds, int)
            or clarification_rounds < 0
        ):
            return None
        for items in (
            secondary_topics,
            comparison_entities,
            evidence_atom_ids,
            skill_ids,
            stage_artifact_ids,
            operators,
            required_outputs,
        ):
            if not isinstance(items, (list, tuple)) or any(
                not isinstance(item, str) for item in items
            ):
                return None
        try:
            history_intent = HistoryIntent.from_dict(value.get("history_intent"))
        except (ValueError, TypeError):
            return None
        return cls(
            primary_subject=primary_subject,
            secondary_topics=tuple(secondary_topics),
            question_type=question_type,
            answer_owner=answer_owner,
            comparison_entities=tuple(comparison_entities),
            inherited_from_turn=inherited_from_turn,
            evidence_atom_ids=tuple(evidence_atom_ids),
            skill_ids=tuple(skill_ids),
            stage_artifact_ids=tuple(stage_artifact_ids),
            time_horizon=time_horizon,
            operators=tuple(operators),
            required_outputs=tuple(required_outputs),
            timeframe=timeframe,
            task_frame_hash=task_frame_hash,
            pending_task_frame=pending_task_frame,
            clarification_rounds=clarification_rounds,
            history_intent=history_intent,
        )


@dataclass(frozen=True)
class ResearchPlan:
    primary_subject: str | None
    question_type: str
    answer_owner: AnswerOwner | None
    retrieval_stages: tuple[str, ...]
    comparison_entities: tuple[str, ...] = ()
    inherited_from_turn: str | None = None
    evidence_atom_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    stage_artifact_ids: tuple[str, ...] = ()
    time_horizon: str = "unspecified"
    operators: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    timeframe: str | None = None
    task_frame_hash: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_intent(cls, intent: TurnIntent) -> ResearchPlan:
        stages = (
            OWNER_WORKFLOW_SPECS[intent.answer_owner].retrieval_stages
            if intent.answer_owner is not None
            else ()
        )
        return cls(
            primary_subject=intent.primary_subject,
            question_type=intent.question_type,
            answer_owner=intent.answer_owner,
            retrieval_stages=stages,
            comparison_entities=intent.comparison_entities,
            inherited_from_turn=intent.inherited_from_turn,
            evidence_atom_ids=intent.evidence_atom_ids,
            skill_ids=intent.skill_ids,
            stage_artifact_ids=intent.stage_artifact_ids,
            time_horizon=intent.time_horizon,
            operators=intent.operators,
            required_outputs=intent.required_outputs,
            timeframe=intent.timeframe,
            task_frame_hash=intent.task_frame_hash,
        )


@dataclass(frozen=True)
class ResearchDeadline:
    expires_at: float
    # P0：为最终合成保留的硬预算（秒）。前置检索阶段的 stage_timeout 不得
    # 消费这段时间，避免检索耗尽预算后合成剩 0ms 只能降级为模板。
    synthesis_reserve: float = 0.0

    @classmethod
    def from_timeout(
        cls,
        timeout: float,
        *,
        synthesis_reserve: float = 0.0,
    ) -> ResearchDeadline:
        return cls(
            time.monotonic() + max(0.0, float(timeout)),
            synthesis_reserve=max(0.0, float(synthesis_reserve)),
        )

    def remaining(self) -> float:
        return max(0.0, self.expires_at - time.monotonic())

    def stage_timeout(self, configured_limit: float) -> float:
        available = max(0.0, self.remaining() - self.synthesis_reserve)
        return max(0.0, min(float(configured_limit), available))

    def synthesis_timeout(self, configured_limit: float) -> float:
        """合成阶段可用全部剩余时间（含保留段）。"""
        return max(0.0, min(float(configured_limit), self.remaining()))

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def bounded_stage(self, configured_limit: float) -> ResearchDeadline:
        """Intersect a child grant with this absolute research-stage window."""

        limit = max(0.0, float(configured_limit))
        return ResearchDeadline(
            expires_at=min(
                self.expires_at - self.synthesis_reserve,
                time.monotonic() + limit,
            )
        )


# 单个 episode 的产品级硬顶：任何 tier、升档、grant 都不得越过。2026-09-06 之前这两个
# 数（24 次 / 240s）就是 deep 档本身，写死在 promote_caps 与 tier_promotion 两处；
# 加 max 档后抬到 max 档的账本上限，并收成一对常数，改一处两处同时变。
# 2026-09-07 二改：48 → 60 / 32 → 40。三道可拆题 9 支分支读数见 runtime/sub_research.branch_limits：
# 分支调用从父账本扣，max 档 3 支 × 10 次 = 30，父臂自己还要 10+ 次；起步 32 会把父臂饿死。
PRODUCT_MAX_TOOL_CALLS = 60
PRODUCT_MAX_SECONDS = 600.0

RESEARCH_TIERS: frozenset[str] = frozenset({"quick", "standard", "deep", "max"})

# turn 级 LLM 调用保险丝（``ResearchExecutionPolicy.max_llm_calls``，缺省 40）按档位放大。
# 2026-09-07 04:11 读数：max 形状 + 两次 sub_research（5 支分支合计 28 次模型调用）把 40 烧穿，
# 最后一个要发的调用是**判官**——被拒后 judge unavailable、答案降级。保险丝的对象是失控，
# 不是并行分支的正常开销；max 档给 120：5 支 × 10 + 父臂 ~15 + 判官 3 + 控制器 ~5 ≈ 75。
LLM_CALL_FUSE_BY_TIER: dict[str, int] = {"max": 120}
DEFAULT_LLM_CALL_FUSE = 40


def llm_call_fuse_for_tier(tier: str | None) -> int:
    return LLM_CALL_FUSE_BY_TIER.get(str(tier or "").strip().lower(), DEFAULT_LLM_CALL_FUSE)


@dataclass(frozen=True)
class ResearchPolicy:
    """Generic owner 的确定性档位，不允许由 LLM 提高上限。"""

    tier: str
    max_steps: int
    total_seconds: float
    synthesis_reserve: float

    @classmethod
    def for_tier(cls, tier: str) -> "ResearchPolicy":
        policies = {
            "quick": cls("quick", 3, 30.0, 20.0),
            "standard": cls("standard", 6, 90.0, 20.0),
            "deep": cls("deep", 12, 240.0, 48.0),
            # 「能力 max」档（用户 2026-09-06 决策：先找到能力上限，再按超限的部分设约束，
            # 而不是上来就约束）。knevo 同题打了 22 次工具；我们 standard 档 8 次里
            # 2 次零授予。这一档给足调用与墙钟，出口硬层（admit_finish / 判官 / 来源分档）
            # 一字不动——放开的是输入侧预算，不是正确性。
            "max": cls("max", 40, PRODUCT_MAX_SECONDS, 60.0),
        }
        return policies.get(tier, policies["standard"])


@dataclass(frozen=True)
class StageCaps:
    """Derived tool / judge caps for one :class:`ResearchPolicy`."""

    tool_batch_seconds: float
    judge_window_seconds: float
    # 单次判官尝试的档位地板；None = 沿用 verifier 构造时配置的帽（历史行为）。
    judge_attempt_seconds: float | None = None


# Shared judge window per second of synthesis reserve.  Current deep reserve
# is 48s; 50/48 pins the shared window at 50s (08-10 arm C / R-10 floor).
# Spec numbers (75s reserve / 60s standard reserve) are stale vs for_tier().
_JUDGE_WINDOW_PER_RESERVE = 50.0 / 48.0
# R-06 / 2026-08-16: standard reserve is 20s → derived window ≈20.83s. Live
# asked=5.208 (retry) timed out 11/11; terra judge-shaped p95=10.75s (N=8).
# Floor standard to deep's 50s. 08-20: first attempt uses the full window
# (cap 50), not window×0.5. Does not change synthesis_reserve or tool_batch.
_STANDARD_JUDGE_WINDOW_FLOOR = 50.0
# max 档判官：单次尝试 75s、共享窗 150s（= 两次完整尝试）。
#
# 2026-09-07 max 档 D5 两发 judge=unavailable（glm-5.3-flash 思考臂，答案 21/27 句、
# 判官载荷 13.3K/13.6K 字符）。把留在收据里的 judge_request 原样重放 grok-4.6
# （grok-cli 1.0.5，与生产同二进制）n=6：44.1 / 60.6 / 50.6 / 12.4 / 58.4 / 53.3s，
# p50 52.0、max 60.6，**4/6 超过 50s 单次帽**；给足 180s 时 6/6 返回有效判定
# （拒 0–13 句）。也就是在 max 档载荷上 50s 帽是「中位数即超时」，不再是尾部。
# 75 = 实测 max 60.6 加约 24% 余量（n=6 小样本，余量比 GLM 修复帽的 16% 放宽）。
# 窗取两次完整尝试：首发超时后仍能发一次完整重试，重试机制才有意义——此前
# 首发吃满整窗、第二发拿 0 秒，收据写「deadline exhausted」而根期限还剩 400s+。
#
# 只加 max 档：quick / standard / deep 的窗与帽一字不变（standard 地板 50、deep
# 48×50/48=50 仍由上面两条钉住）。收据 ~/.finance-runtime/glm-ceiling-20260907/。
_MAX_TIER_JUDGE_ATTEMPT_SECONDS = 75.0
_MAX_TIER_JUDGE_WINDOW_FLOOR = 2.0 * _MAX_TIER_JUDGE_ATTEMPT_SECONDS


def derive_stage_caps(policy: ResearchPolicy) -> StageCaps:
    """Derive stage caps from tier totals.  Env ceilings are applied by callers.

    Tool batch gets the pre-synthesis remainder — the same quantity
    ``stage_timeout`` already mins against — so the old 30.0 literal is no
    longer the source of truth.  Judge window is a fixed fraction of reserve.
    Draft protection stays ``policy.synthesis_reserve`` (not changed here).
    """

    total = max(0.0, float(policy.total_seconds))
    reserve = max(0.0, float(policy.synthesis_reserve))
    judge_window = reserve * _JUDGE_WINDOW_PER_RESERVE
    judge_attempt: float | None = None
    if policy.tier == "standard":
        judge_window = max(judge_window, _STANDARD_JUDGE_WINDOW_FLOOR)
    elif policy.tier == "max":
        judge_window = max(judge_window, _MAX_TIER_JUDGE_WINDOW_FLOOR)
        judge_attempt = _MAX_TIER_JUDGE_ATTEMPT_SECONDS
    return StageCaps(
        tool_batch_seconds=max(0.0, total - reserve),
        judge_window_seconds=judge_window,
        judge_attempt_seconds=judge_attempt,
    )


def apply_env_ceiling(derived: float, env_name: str) -> float:
    """Env is a fuse that can only lower a derived cap, never raise it."""

    raw = os.environ.get(env_name)
    if raw is None or not str(raw).strip():
        return max(0.0, float(derived))
    try:
        ceiling = float(raw)
    except ValueError:
        return max(0.0, float(derived))
    if ceiling <= 0:
        return max(0.0, float(derived))
    return max(0.0, min(float(derived), ceiling))


def policy_for_env(tier: str | None = None) -> ResearchPolicy:
    raw = tier if tier is not None else os.environ.get("ASK_RESEARCH_TIER", "standard")
    return ResearchPolicy.for_tier(str(raw or "standard").strip().lower())


class RootBudgetLedger(Protocol):
    """The single mutable budget authority shared by one research episode."""

    initial_calls: int
    episode_id: str
    hard_calls_cap: int
    initial_seconds: float
    hard_seconds_cap: float
    remaining_calls: int
    remaining_seconds: float

    @property
    def allocated_calls(self) -> int: ...

    @property
    def allocated_seconds(self) -> float: ...

    def grant(self, grant: object) -> bool: ...

    def promote_caps(
        self,
        *,
        episode_id: str,
        promotion_id: str,
        hard_calls_cap: int,
        hard_seconds_cap: float,
    ) -> bool: ...

    def consume_call(self, *, seconds: float) -> None: ...

    def consume_call_slot(self) -> None: ...

    def consume_seconds(self, *, seconds: float) -> None: ...

    def settle_seconds(self, *, seconds: float) -> float: ...


class InMemoryRootBudgetLedger:
    """Thread-safe root budget implementation used by runtime adapters.

    Initial allocation is the budget before repair. The hard cap is the
    episode-wide ceiling; grants reserve unused headroom and never reset
    already consumed calls or seconds.
    """

    def __init__(
        self,
        *,
        episode_id: str = "",
        initial_calls: int,
        hard_calls_cap: int,
        initial_seconds: float,
        hard_seconds_cap: float,
    ) -> None:
        for name, value in (
            ("initial_calls", initial_calls),
            ("hard_calls_cap", hard_calls_cap),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if hard_calls_cap < initial_calls:
            raise ValueError("hard_calls_cap must cover initial_calls")
        if initial_seconds < 0 or hard_seconds_cap < initial_seconds:
            raise ValueError("invalid root seconds budget")
        self.episode_id = str(episode_id or "").strip()
        if not self.episode_id:
            raise ValueError("episode_id must be non-empty")
        self.initial_calls = initial_calls
        self.hard_calls_cap = hard_calls_cap
        self.initial_seconds = float(initial_seconds)
        self.hard_seconds_cap = float(hard_seconds_cap)
        self.remaining_calls = initial_calls
        self.remaining_seconds = float(initial_seconds)
        self._allocated_calls = initial_calls
        self._allocated_seconds = float(initial_seconds)
        self._initial_hard_calls_cap = hard_calls_cap
        self._initial_hard_seconds_cap = float(hard_seconds_cap)
        # Keep accepted amounts with the dedup identity: recovery must not mint
        # headroom by losing an ID or by reconstructing from today's policy.
        self._grants: dict[str, tuple[int, float]] = {}
        self._promotions: dict[str, tuple[int, float]] = {}
        self._lock = RLock()

    @property
    def allocated_calls(self) -> int:
        with self._lock:
            return self._allocated_calls

    @property
    def allocated_seconds(self) -> float:
        with self._lock:
            return self._allocated_seconds

    def grant(self, grant: object) -> bool:
        calls = int(getattr(grant, "calls_granted", 0) or 0)
        seconds = float(getattr(grant, "seconds_granted", 0.0) or 0.0)
        grant_id = str(getattr(grant, "grant_id", "") or "").strip()
        episode_id = str(getattr(grant, "episode_id", "") or "").strip()
        if calls < 0 or seconds <= 0 or not grant_id or not episode_id:
            return False
        with self._lock:
            if episode_id != self.episode_id:
                return False
            if grant_id in self._grants:
                return False
            if self._allocated_calls + calls > self.hard_calls_cap:
                return False
            if self._allocated_seconds + seconds > self.hard_seconds_cap:
                return False
            self._grants[grant_id] = (calls, seconds)
            self._allocated_calls += calls
            self._allocated_seconds += seconds
            self.remaining_calls += calls
            self.remaining_seconds += seconds
            return True

    def promote_caps(
        self,
        *,
        episode_id: str,
        promotion_id: str,
        hard_calls_cap: int,
        hard_seconds_cap: float,
    ) -> bool:
        """Raise this episode's hard ceiling once without minting a new ledger."""

        episode = str(episode_id or "").strip()
        promotion = str(promotion_id or "").strip()
        if (
            not episode
            or not promotion
            or isinstance(hard_calls_cap, bool)
            or not isinstance(hard_calls_cap, int)
            or hard_calls_cap < 0
        ):
            return False
        try:
            seconds_cap = float(hard_seconds_cap)
        except (TypeError, ValueError):
            return False
        if (
            seconds_cap < 0
            or hard_calls_cap > PRODUCT_MAX_TOOL_CALLS
            or seconds_cap > PRODUCT_MAX_SECONDS
        ):
            return False
        with self._lock:
            if episode != self.episode_id:
                return False
            previous = self._promotions.get(promotion)
            requested = (hard_calls_cap, seconds_cap)
            if previous is not None:
                return previous == requested
            if (
                hard_calls_cap < self.hard_calls_cap
                or seconds_cap < self.hard_seconds_cap
                or hard_calls_cap < self._allocated_calls
                or seconds_cap < self._allocated_seconds
            ):
                return False
            self.hard_calls_cap = hard_calls_cap
            self.hard_seconds_cap = seconds_cap
            self._promotions[promotion] = requested
            return True

    def consume_call(self, *, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("consumed call seconds must be positive")
        with self._lock:
            if self.remaining_calls <= 0:
                raise ValueError("root call budget exhausted")
            if seconds > self.remaining_seconds + 1e-9:
                raise ValueError("root seconds budget exhausted")
            self.remaining_calls -= 1
            self.remaining_seconds = max(0.0, self.remaining_seconds - seconds)

    def consume_call_slot(self) -> None:
        """Spend one finance-tool call slot without debiting wall time.

        分支视图用它向父账本记调用。秒是墙钟：三支并行跑 150s 对父臂只是 150s，
        由父臂对 ``sub_research`` 那一批做批结算时按墙钟记**一次**；分支自己的秒只记在
        自己的视图里。2026-09-07 候选口读数：分支把秒累加记到父账本（450s）+ 批结算
        再记 180s，540s 的账本在墙钟 190s 归零，父臂墙钟还剩 396s 却 deadline_exhausted。
        """

        with self._lock:
            if self.remaining_calls <= 0:
                raise ValueError("root call budget exhausted")
            self.remaining_calls -= 1

    def consume_seconds(self, *, seconds: float) -> None:
        """Debit wall time without spending a finance-tool call slot."""

        if seconds < 0:
            raise ValueError("consumed seconds must be non-negative")
        with self._lock:
            if seconds > self.remaining_seconds + 1e-9:
                raise ValueError("root seconds budget exhausted")
            self.remaining_seconds = max(0.0, self.remaining_seconds - seconds)

    def settle_seconds(self, *, seconds: float) -> float:
        """Clamp and debit wall time atomically, returning the amount actually spent.

        Callers settling finished work cannot undo it, so this never raises on
        overdraft: it debits at most the remaining balance and reports what was
        taken. Doing the clamp inside the lock is what makes concurrent settling
        safe -- reading ``remaining_seconds`` first and then debiting is a
        check-then-act race that silently loses debits.
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
                "initial_calls": self.initial_calls,
                "episode_id": self.episode_id,
                "hard_calls_cap": self.hard_calls_cap,
                "initial_seconds": self.initial_seconds,
                "hard_seconds_cap": self.hard_seconds_cap,
                "remaining_calls": self.remaining_calls,
                "remaining_seconds": self.remaining_seconds,
                "allocated_calls": self._allocated_calls,
                "allocated_seconds": self._allocated_seconds,
            }

    def to_snapshot(self) -> dict[str, object]:
        """Detached recovery state, not the model-facing ``to_dict`` summary.

        One lock covers counters AND dedup identities. This is only a local
        checkpoint image, not reconciliation of effects after that checkpoint.
        """
        with self._lock:
            return {
                "schema_version": 1,
                "kind": "root_budget",
                **self.to_dict(),
                "initial_hard_calls_cap": self._initial_hard_calls_cap,
                "initial_hard_seconds_cap": self._initial_hard_seconds_cap,
                "grants": {
                    key: {"calls_granted": calls, "seconds_granted": seconds}
                    for key, (calls, seconds) in sorted(self._grants.items())
                },
                "promotions": {
                    key: {"hard_calls_cap": calls, "hard_seconds_cap": seconds}
                    for key, (calls, seconds) in sorted(self._promotions.items())
                },
            }

    @classmethod
    def from_snapshot(
        cls, payload: Mapping[str, object], *, episode_id: str,
    ) -> InMemoryRootBudgetLedger:
        """Validate a complete snapshot, without registering a live owner.

        Legacy summaries lack dedup identities and cannot be upgraded by guess.
        This reader is also used before persistence; it never normalizes corrupt
        counters into valid-looking balances. Registration belongs to the factory
        below, under the same lock as fresh allocation.
        """
        expected = {
            "schema_version", "kind", "episode_id", "initial_calls", "initial_seconds",
            "hard_calls_cap", "hard_seconds_cap", "remaining_calls", "remaining_seconds",
            "allocated_calls", "allocated_seconds", "grants", "promotions",
            "initial_hard_calls_cap", "initial_hard_seconds_cap",
        }
        if not isinstance(payload, Mapping) or set(payload) != expected:
            raise ValueError("root budget snapshot fields are incomplete or unknown")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("unsupported root budget snapshot version")
        if payload["kind"] != "root_budget":
            raise ValueError("snapshot is not a root budget")
        if (
            not isinstance(episode_id, str) or not episode_id.strip()
            or payload["episode_id"] != episode_id
            or episode_id != episode_id.strip()
        ):
            raise ValueError("root budget snapshot episode identity mismatch")

        def integer(value: object) -> int:
            if type(value) is not int or value < 0:
                raise ValueError("snapshot call counts must be non-negative integers")
            return value

        def seconds(value: object) -> float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("snapshot seconds must be finite non-negative numbers")
            try:
                result = float(value)
            except (ValueError, OverflowError) as exc:
                raise ValueError("snapshot seconds must be finite non-negative numbers") from exc
            if not math.isfinite(result) or result < 0:
                raise ValueError("snapshot seconds must be finite non-negative numbers")
            return result

        initial_calls = integer(payload["initial_calls"])
        allocated_calls = integer(payload["allocated_calls"])
        remaining_calls = integer(payload["remaining_calls"])
        hard_calls = integer(payload["hard_calls_cap"])
        initial_seconds = seconds(payload["initial_seconds"])
        allocated_seconds = seconds(payload["allocated_seconds"])
        remaining_seconds = seconds(payload["remaining_seconds"])
        hard_seconds = seconds(payload["hard_seconds_cap"])
        initial_hard_calls = integer(payload["initial_hard_calls_cap"])
        initial_hard_seconds = seconds(payload["initial_hard_seconds_cap"])
        if not (
            initial_calls <= initial_hard_calls <= hard_calls
            and initial_seconds <= initial_hard_seconds <= hard_seconds
            and initial_calls <= allocated_calls <= hard_calls
            and remaining_calls <= allocated_calls
            and initial_seconds <= allocated_seconds <= hard_seconds
            and remaining_seconds <= allocated_seconds
        ):
            raise ValueError("root budget snapshot balances exceed their allocation/caps")

        def records(key: str, calls_key: str, seconds_key: str) -> dict[str, tuple[int, float]]:
            entries = payload[key]
            if not isinstance(entries, Mapping):
                raise ValueError(f"snapshot {key} must be an object")
            result = {}
            for identity, entry in entries.items():
                if not isinstance(identity, str) or not identity.strip() or identity != identity.strip():
                    raise ValueError(f"snapshot {key} contains an invalid identity")
                if not isinstance(entry, Mapping) or set(entry) != {calls_key, seconds_key}:
                    raise ValueError(f"snapshot {key} contains incomplete records")
                result[identity] = (integer(entry[calls_key]), seconds(entry[seconds_key]))
            return result

        grants = records("grants", "calls_granted", "seconds_granted")
        promotions = records("promotions", "hard_calls_cap", "hard_seconds_cap")
        if any(amount <= 0 for _, amount in grants.values()):
            raise ValueError("snapshot grants require positive seconds")
        if (
            initial_calls + sum(calls for calls, _ in grants.values()) != allocated_calls
            or not math.isclose(
                initial_seconds + math.fsum(amount for _, amount in grants.values()),
                allocated_seconds, rel_tol=1e-12, abs_tol=1e-8,
            )
        ):
            raise ValueError("snapshot grant identities do not reconcile with allocations")
        # Promotion records form a non-decreasing chain of ceilings. Their IDs
        # may sort differently from application order, but the caps cannot cross.
        previous_calls, previous_seconds = initial_hard_calls, initial_hard_seconds
        for calls, amount in sorted(promotions.values()):
            if not (
                previous_calls <= calls <= hard_calls and previous_seconds <= amount <= hard_seconds
                and calls <= PRODUCT_MAX_TOOL_CALLS and amount <= PRODUCT_MAX_SECONDS
            ):
                raise ValueError("snapshot promotions do not reconcile with caps")
            previous_calls, previous_seconds = calls, amount
        if (previous_calls, previous_seconds) != (hard_calls, hard_seconds):
            raise ValueError("snapshot last promotion does not match current caps")
        ledger = cls(
            episode_id=episode_id, initial_calls=initial_calls, hard_calls_cap=hard_calls,
            initial_seconds=initial_seconds, hard_seconds_cap=hard_seconds,
        )
        ledger.remaining_calls = remaining_calls
        ledger.remaining_seconds = remaining_seconds
        ledger._allocated_calls = allocated_calls
        ledger._allocated_seconds = allocated_seconds
        ledger._initial_hard_calls_cap = initial_hard_calls
        ledger._initial_hard_seconds_cap = initial_hard_seconds
        ledger._grants = grants
        ledger._promotions = promotions
        return ledger


_LIVE_ROOT_BUDGETS: WeakValueDictionary[str, InMemoryRootBudgetLedger] = (
    WeakValueDictionary()
)
_LIVE_ROOT_BUDGETS_LOCK = RLock()


def root_budget_for_policy(
    policy: ResearchPolicy,
    *,
    episode_id: str,
) -> InMemoryRootBudgetLedger:
    """Allocate one root ledger from the immutable tier policy."""

    episode = str(episode_id or "").strip()
    if not episode:
        raise ValueError("episode_id must be non-empty")
    hard_calls = {
        "quick": 4,
        "standard": 8,
        "deep": 24,
        "max": PRODUCT_MAX_TOOL_CALLS,
    }.get(str(policy.tier).strip().lower(), policy.max_steps)
    with _LIVE_ROOT_BUDGETS_LOCK:
        if episode in _LIVE_ROOT_BUDGETS:
            raise ValueError(f"root budget already exists for live episode: {episode}")
        ledger = InMemoryRootBudgetLedger(
            episode_id=episode,
            initial_calls=policy.max_steps,
            hard_calls_cap=max(policy.max_steps, hard_calls),
            initial_seconds=max(
                0.0,
                policy.total_seconds - policy.synthesis_reserve,
            ),
            hard_seconds_cap=policy.total_seconds,
        )
        _LIVE_ROOT_BUDGETS[episode] = ledger
        return ledger


def restore_root_budget(
    payload: Mapping[str, object],
    *,
    episode_id: str,
    unreconciled_effects: Sequence[Mapping[str, object]],
) -> InMemoryRootBudgetLedger:
    """Restore balances/identities, never allocate afresh from a tier policy.

    The live registration is process-local, NOT a cross-process writer lease.

    ``unreconciled_effects`` is **required**, not defaulted. A snapshot is taken
    at a phase boundary while both accounting paths debit *after* the external
    work finished, so the balance in it says an in-flight call cost zero. Handing
    that balance to a spender is how the same money gets spent twice -- and under
    a crash loop, N times. The caller must therefore state what it knows about
    the window, and a non-empty list is refused here: recovering a ledger is not
    the place to decide that an unknown charge can be ignored. Reconciling means
    charging (``episode_effects.charge_unknown_effects``) and clearing the list
    on the checkpoint, as one durable transition; the list is its own dedup
    token, so reconciling twice is impossible rather than merely discouraged.
    """
    outstanding = unknown_effects_from_payload(list(unreconciled_effects))
    if outstanding:
        raise ValueError(
            f"root budget for {episode_id} has {len(outstanding)} unreconciled effect(s); "
            "reconcile them before spending this balance"
        )
    ledger = InMemoryRootBudgetLedger.from_snapshot(payload, episode_id=episode_id)
    with _LIVE_ROOT_BUDGETS_LOCK:
        if episode_id in _LIVE_ROOT_BUDGETS:
            raise ValueError(f"root budget already exists for live episode: {episode_id}")
        _LIVE_ROOT_BUDGETS[episode_id] = ledger
    return ledger


def release_root_budget(episode_id: str) -> None:
    """Drop the live registration for one episode once that episode is over.

    The registry exists to catch *two concurrent* root budgets for the same
    episode, so the entry must not outlive the episode. Garbage collection
    alone is not enough to guarantee that: when an episode ends by raising,
    the exception traceback keeps the owning frame — and therefore the
    ledger — reachable, so the next caller for the same episode id fails
    against a registration that is already dead in every sense but memory.
    Callers own the release; this is a no-op if nothing is registered.
    """

    episode = str(episode_id or "").strip()
    if not episode:
        return
    with _LIVE_ROOT_BUDGETS_LOCK:
        _LIVE_ROOT_BUDGETS.pop(episode, None)


# 前瞻假设槽：这些输出的本体是「对未来的条件化判断」——情景路径、持续/证伪
# 阈值不可能出现在既有证据里（证据不含未来）。episode_factory 在前瞻类题型下
# 据此把槽签成 model_reasoning，episode_semantic_verifier 的数值门禁据此豁免
# 条件句里模型提出的新阈值。两处共用本集合：各存一份词表必漂（route_table
# 的 QUICK_FACT_PATTERN 注释里有同款事故）。
FORWARD_HYPOTHESIS_OUTPUT_IDS = frozenset(
    {
        "scenario_paths",
        "continuation_conditions",
        "invalidation_conditions",
        # Knevo 结论元素④的时点件：verify_by = 指标 × 时间窗。判断句要能回答
        # 「什么时候、看什么数，就知道这句话对不对」，否则进不了回检闭环。
        "verification_timepoints",
    }
)


@dataclass(frozen=True)
class RequiredOutput:
    output_id: str
    description: str
    evidence_types: tuple[str, ...] = ()
    required: bool = True
    grounding_mode: GroundingMode = "evidence"
    # W2：静态预检 / 动态不可达降级预置的缺口声明。空串表示没有预置。
    preplaced_gap: str = ""
    # History is an operation-scoped contract, not a blanket capability grant.
    # Empty means this output accepts ordinary evidence only.
    allowed_history_operations: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutputStatus:
    output_id: str
    # fulfilled is D5's answered projection; legal_gap is disclosed, not answered.
    status: Literal["fulfilled", "legal_gap", "gap", "missing"]
    evidence_ids: tuple[str, ...] = ()
    gap: str = ""


class ResearchContractError(ValueError):
    """任务契约不满足 schema 或能力白名单。"""


@dataclass(frozen=True)
class ResearchTaskContract:
    task_id: str
    question: str
    subject: str | None
    subject_kind: str | None
    question_type: str
    required_outputs: tuple[RequiredOutput, ...]
    allowed_capabilities: tuple[str, ...]
    research_tier: str = "standard"
    presentation_profile: str = "general"
    freshness: str = "current"
    timeframe: str | None = None
    evidence_plan: EvidencePlan = field(default_factory=EvidencePlan)
    contract_version: str = "1"
    task_frame_hash: str = ""
    material_contract: MaterialContract | None = None
    premise_calculation: PremiseCalculation | None = None
    material_grounding: MaterialGrounding | None = None

    def __post_init__(self) -> None:
        if isinstance(self.material_grounding, dict):
            object.__setattr__(self, "material_grounding", MaterialGrounding.from_dict(self.material_grounding))
        if self.material_grounding is not None and not isinstance(self.material_grounding, MaterialGrounding):
            raise ResearchContractError("material_grounding 必须是 MaterialGrounding")
        if isinstance(self.material_contract, dict):
            object.__setattr__(self, "material_contract", MaterialContract.from_dict(self.material_contract))
        if self.material_contract is not None and not isinstance(self.material_contract, MaterialContract):
            raise ResearchContractError("material_contract 必须是 MaterialContract")
        if isinstance(self.premise_calculation, dict):
            object.__setattr__(self, "premise_calculation", PremiseCalculation.from_dict(self.premise_calculation))
        if self.premise_calculation is not None and (
            not isinstance(self.premise_calculation, PremiseCalculation)
            or not self.material_contract or not self.material_contract.premise_calculation
        ):
            raise ResearchContractError("premise calculation requires the user premise contract")
        # Backwards compatibility for callers that expand ``to_dict()`` into
        # the constructor (older tests/integrations predate EvidencePlan).
        if isinstance(self.evidence_plan, dict):
            raw_requirements = self.evidence_plan.get("requirements", ())
            requirements = tuple(
                EvidenceRequirement(
                    provider_name=str(item.get("provider_name") or ""),
                    capability=str(item.get("capability") or ""),
                    mandatory=bool(item.get("mandatory", False)),
                    freshness=str(item.get("freshness") or "current"),
                    reason=str(item.get("reason") or ""),
                )
                for item in raw_requirements
                if isinstance(item, dict)
            )
            object.__setattr__(
                self,
                "evidence_plan",
                EvidencePlan(
                    profile=str(self.evidence_plan.get("profile") or "general"),
                    requirements=requirements,
                    freshness=str(self.evidence_plan.get("freshness") or "current"),
                ),
            )
        if not self.task_id.strip() or not self.question.strip():
            raise ResearchContractError("task_id/question 不能为空")
        if self.research_tier not in RESEARCH_TIERS:
            raise ResearchContractError(f"未知研究档位：{self.research_tier}")
        if any(not item.output_id.strip() for item in self.required_outputs):
            raise ResearchContractError("required output id 不能为空")
        if any(
            item.grounding_mode not in {"evidence", "user_premise", "model_reasoning"}
            for item in self.required_outputs
        ):
            raise ResearchContractError("required output grounding_mode 无效")
        for requirement in self.evidence_plan.requirements:
            if not requirement.provider_name.strip() or not requirement.capability.strip():
                raise ResearchContractError("evidence plan requirement 必须声明 provider/capability")
        if self.material_contract is not None and self.material_contract.data_scope == "material_only":
            if self.allowed_capabilities or self.evidence_plan.requirements:
                raise ResearchContractError("material_only 不允许读能力或材料外证据计划")
            if any(output.evidence_types for output in self.required_outputs):
                raise ResearchContractError("material_only 输出槽不能要求材料外工具证据")
            for question in self.material_contract.questions:
                matches = tuple(item for item in self.required_outputs if item.output_id == f"answer_{question.question_id}")
                if len(matches) != 1 or not matches[0].required:
                    raise ResearchContractError("material_only 每题须保留唯一必需输出槽：" + question.question_id)
        if self.material_contract is not None and self.material_contract.data_scope == "local_only":
            if restrict_read_capabilities(tuple(self.allowed_capabilities), "local_only") != tuple(self.allowed_capabilities):
                raise ResearchContractError("local_only 含未审定的读取能力")
            if any(item.capability not in self.allowed_capabilities for item in self.evidence_plan.requirements):
                raise ResearchContractError("local_only 证据计划超出冻结读取授权")
            if any(LOCAL_EVIDENCE_PRODUCERS.get(cap, cap) not in self.allowed_capabilities
                   for output in self.required_outputs for cap in output.evidence_types):
                raise ResearchContractError("local_only 输出工具证据超出冻结读取授权")
        mandatory = set(self.evidence_plan.mandatory_capabilities)
        if not mandatory.issubset(set(self.allowed_capabilities)):
            raise ResearchContractError(
                "evidence plan 的 mandatory capability 未被 allowed_capabilities 授权"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "question": self.question,
            "subject": self.subject,
            "subject_kind": self.subject_kind,
            "question_type": self.question_type,
            "required_outputs": [asdict(item) for item in self.required_outputs],
            "allowed_capabilities": list(self.allowed_capabilities),
            "research_tier": self.research_tier,
            "presentation_profile": self.presentation_profile,
            "freshness": self.freshness,
            "timeframe": self.timeframe,
            "evidence_plan": self.evidence_plan.to_dict(),
            "contract_version": self.contract_version,
            "task_frame_hash": self.task_frame_hash,
            **({"material_contract": self.material_contract.to_dict()} if self.material_contract is not None else {}),
            **({"premise_calculation": self.premise_calculation.to_dict()} if self.premise_calculation is not None else {}),
            **({"material_grounding": self.material_grounding.to_dict()} if self.material_grounding is not None else {}),
        }

    @classmethod
    def from_dict(cls, value: object) -> "ResearchTaskContract":
        if not isinstance(value, dict):
            raise ResearchContractError("任务契约必须是 object")
        raw_outputs = value.get("required_outputs")
        if not isinstance(raw_outputs, (list, tuple)):
            raise ResearchContractError("required_outputs 必须是 list")
        outputs: list[RequiredOutput] = []
        for raw in raw_outputs:
            if not isinstance(raw, dict):
                raise ResearchContractError("required output 必须是 object")
            evidence_types = raw.get("evidence_types", ())
            if not isinstance(evidence_types, (list, tuple)):
                raise ResearchContractError("evidence_types 必须是 list")
            outputs.append(
                RequiredOutput(
                    output_id=str(raw.get("output_id") or ""),
                    description=str(raw.get("description") or ""),
                    evidence_types=tuple(str(item) for item in evidence_types),
                    required=bool(raw.get("required", True)),
                    grounding_mode=str(raw.get("grounding_mode") or "evidence"),
                    preplaced_gap=str(raw.get("preplaced_gap") or ""),
                    allowed_history_operations=tuple(
                        str(item) for item in raw.get("allowed_history_operations", ())
                    ) if isinstance(raw.get("allowed_history_operations", ()), (list, tuple)) else (),
                )
            )
        capabilities = value.get("allowed_capabilities", ())
        if not isinstance(capabilities, (list, tuple)):
            raise ResearchContractError("allowed_capabilities 必须是 list")
        raw_plan = value.get("evidence_plan")
        if raw_plan is None:
            evidence_plan = EvidencePlan()
        elif isinstance(raw_plan, dict):
            raw_requirements = raw_plan.get("requirements", ())
            if not isinstance(raw_requirements, (list, tuple)):
                raise ResearchContractError("evidence_plan.requirements 必须是 list")
            requirements = tuple(
                EvidenceRequirement(
                    provider_name=str(item.get("provider_name") or ""),
                    capability=str(item.get("capability") or ""),
                    mandatory=bool(item.get("mandatory", False)),
                    freshness=str(item.get("freshness") or "current"),
                    reason=str(item.get("reason") or ""),
                )
                for item in raw_requirements
                if isinstance(item, dict)
            )
            evidence_plan = EvidencePlan(
                profile=str(raw_plan.get("profile") or "general"),
                requirements=requirements,
                freshness=str(raw_plan.get("freshness") or "current"),
            )
        else:
            raise ResearchContractError("evidence_plan 必须是 object")
        return cls(
            task_id=str(value.get("task_id") or ""),
            question=str(value.get("question") or ""),
            subject=(
                str(value["subject"]) if value.get("subject") is not None else None
            ),
            subject_kind=(
                str(value["subject_kind"])
                if value.get("subject_kind") is not None
                else None
            ),
            question_type=str(value.get("question_type") or "general_finance_qa"),
            required_outputs=tuple(outputs),
            allowed_capabilities=tuple(str(item) for item in capabilities),
            research_tier=str(value.get("research_tier") or "standard"),
            presentation_profile=str(value.get("presentation_profile") or "general"),
            freshness=str(value.get("freshness") or "current"),
            timeframe=(
                str(value["timeframe"]) if value.get("timeframe") is not None else None
            ),
            evidence_plan=evidence_plan,
            contract_version=str(value.get("contract_version") or "1"),
            task_frame_hash=str(value.get("task_frame_hash") or ""),
            material_contract=(MaterialContract.from_dict(value["material_contract"]) if "material_contract" in value else None),
            premise_calculation=(PremiseCalculation.from_dict(value["premise_calculation"]) if "premise_calculation" in value else None),
            material_grounding=(MaterialGrounding.from_dict(value["material_grounding"]) if "material_grounding" in value else None),
        )


@dataclass(frozen=True)
class InformationCutoff:
    as_of_date: date
    source: InformationCutoffSource

    def __post_init__(self) -> None:
        if type(self.as_of_date) is not date:
            raise ValueError("information cutoff must use a date")
        if self.source not in {
            "requested",
            "latest_available",
            "runtime_default",
        }:
            raise ValueError("unsupported information cutoff source")

    @classmethod
    def runtime_default(cls) -> InformationCutoff:
        return cls(date.today(), "runtime_default")

    def to_dict(self) -> dict[str, str]:
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "source": self.source,
        }


@dataclass(frozen=True)
class ResearchRunContext:
    contract: ResearchTaskContract
    deadline: ResearchDeadline
    policy: ResearchPolicy
    trace_parent_id: str
    # Prompt context only: never treated as evidence. Appending defaults keeps
    # positional construction in older integrations backwards compatible.
    today: str | None = None
    latest_data_date: str | None = None
    conversation_context: str = ""
    information_cutoff: InformationCutoff = field(
        default_factory=InformationCutoff.runtime_default
    )
    root_budget: RootBudgetLedger | None = None
    # Prompt-only KOL perspective constraints (perspective_lab runtime prompt);
    # never evidence.  Empty means neutral.  Trailing default keeps positional
    # construction in older integrations backwards compatible.
    perspective_context: str = ""
    # 本轮已经交付过的交易日。窗口闸门认这个集合，不认题型。
    # 可变 set：同一 context 对象在多次 execute 之间累加。
    authorized_trade_dates: set[str] = field(default_factory=set)
    # 个性化接合核。缺席 = 本题未触发 StancePack；只作锁格，不是证据。
    stance_pack: object | None = None
    # Prompt-only：owner 工作流的检索阶段序列（经 ResearchPlan 送达）。
    # R-20260827-09：此前阶段表止步于 trace，episode 拿不到。空元组 = 无
    # owner 阶段，构造逐字节兼容。永不作为证据。
    retrieval_stages: tuple[str, ...] = ()
    # Domain research state. Full result rows live in RunStore artifacts, not prompts.
    history_intent: HistoryIntent | None = None
    history_results: list[dict[str, object]] = field(default_factory=list)
    history_artifact_index: list[dict[str, object]] = field(default_factory=list)
    prior_evidence: PriorTurnEvidence | None = None
    # 入口身份（控制面，永不进提示词、永不作证据）：这一轮属于哪个用户 / 会话 /
    # run / 助手消息。由入口在核对过 run 归属之后绑定；None = 没有可信入口
    # （离线驱动、CLI、测试），恢复时按「未绑定」处理，不会与任何门匹配上。
    entry_identity: EpisodeEntryIdentity | None = None


@dataclass(frozen=True)
class EvidenceAtom:
    atom_id: str
    claim_text: str
    entity_id: str | None
    metric: str | None
    value: str | int | float | None
    unit: str | None
    period: str | None
    evidence_tier: str
    source_id: str
    source_date: str | None
    provenance: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> EvidenceAtom | None:
        if not isinstance(value, dict):
            return None
        try:
            return cls(
                atom_id=str(value["atom_id"]),
                claim_text=str(value["claim_text"]),
                entity_id=(
                    str(value["entity_id"])
                    if value.get("entity_id") is not None
                    else None
                ),
                metric=(
                    str(value["metric"])
                    if value.get("metric") is not None
                    else None
                ),
                value=value.get("value"),
                unit=(
                    str(value["unit"])
                    if value.get("unit") is not None
                    else None
                ),
                period=(
                    str(value["period"])
                    if value.get("period") is not None
                    else None
                ),
                evidence_tier=str(value["evidence_tier"]),
                source_id=str(value["source_id"]),
                source_date=(
                    str(value["source_date"])
                    if value.get("source_date") is not None
                    else None
                ),
                provenance=(
                    dict(value["provenance"])
                    if isinstance(value.get("provenance"), dict)
                    else {}
                ),
            )
        except KeyError:
            return None


@dataclass(frozen=True)
class StructuredClaim:
    claim_id: str
    claim: str
    evidence_atom_ids: tuple[str, ...]
    claim_type: ClaimType

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StageArtifact:
    stage: str
    status: StageStatus
    elapsed_ms: int
    producer: str = ""
    input_hash: str = ""
    artifact_type: str = ""
    required_output: bool = False
    timeout_seconds: float = 0.0
    on_failure: str = ""
    evidence_atom_ids: tuple[str, ...] = ()
    payload: dict[str, object] = field(default_factory=dict)
    degrade_reason: str | None = None
    # 阶段异常的可诊断详情（异常消息，截断）。degrade_reason 是给人看的简短
    # 措辞，只带异常类名；光有类名诊断不了——真实 run 里出现过两次
    # "company_mapping 执行失败（TypeError）"，消息和位置全被丢弃，事后无从下手。
    failure_detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> StageArtifact | None:
        if not isinstance(value, dict):
            return None
        try:
            status = str(value["status"])
            if status not in {
                "pending",
                "completed",
                "partial",
                "timeout",
                "failed",
                "skipped",
            }:
                return None
            evidence_atom_ids = value.get("evidence_atom_ids", ())
            if not isinstance(evidence_atom_ids, (list, tuple)):
                return None
            return cls(
                stage=str(value["stage"]),
                status=cast(StageStatus, status),
                elapsed_ms=int(value.get("elapsed_ms") or 0),
                producer=str(value.get("producer") or ""),
                input_hash=str(value.get("input_hash") or ""),
                artifact_type=str(value.get("artifact_type") or ""),
                required_output=bool(value.get("required_output")),
                timeout_seconds=float(value.get("timeout_seconds") or 0.0),
                on_failure=str(value.get("on_failure") or ""),
                evidence_atom_ids=tuple(
                    str(item) for item in evidence_atom_ids if str(item)
                ),
                payload=(
                    dict(value["payload"])
                    if isinstance(value.get("payload"), dict)
                    else {}
                ),
                degrade_reason=(
                    str(value["degrade_reason"])
                    if value.get("degrade_reason") is not None
                    else None
                ),
                failure_detail=(
                    str(value["failure_detail"])
                    if value.get("failure_detail") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _top_level_follow_up_query(query: str) -> tuple[str, bool]:
    raw = str(query or "")
    visible, _uncertain = top_level_message_text(raw)
    cleaned = visible.strip()
    return cleaned, cleaned != raw.strip()


def is_follow_up(query: str) -> bool:
    cleaned, _protected = _top_level_follow_up_query(query)
    return bool(
        classify_reference(cleaned) != "none"
        or _COMPARISON_PATTERN.search(cleaned)
    )


def is_contextual_follow_up(
    query: str,
    envelope: QueryEnvelope,
    previous_intent: TurnIntent | None,
    *,
    resolution: QueryResolution | None = None,
) -> bool:
    if previous_intent is None:
        return False
    cleaned, protected_content_present = _top_level_follow_up_query(query)
    if not cleaned:
        return False
    if requests_previous_answer_review(cleaned):
        return not _EXPLICIT_SWITCH_PATTERN.search(cleaned) and (
            envelope.subject is None or envelope.subject == previous_intent.primary_subject
        )
    if is_follow_up(cleaned) or (
        resolution is not None
        and resolution.context_dependent
        and not protected_content_present
    ):
        return True
    if (
        not cleaned
        or len(cleaned) > 80
        or _EXPLICIT_SWITCH_PATTERN.search(cleaned)
        or not _CONTEXT_DEPENDENT_RESEARCH_PATTERN.search(cleaned)
    ):
        return False
    return (
        envelope.subject is None
        or envelope.subject == previous_intent.primary_subject
        or bool(_CONTEXT_DEPENDENT_RESEARCH_PREFIX_PATTERN.search(cleaned))
    )


def answer_owner_for_question_type(question_type: str) -> AnswerOwner | None:
    return QUESTION_OWNER_SKILLS.get(question_type)


def build_turn_intent(
    query: str,
    envelope: QueryEnvelope,
    *,
    previous_intent: TurnIntent | None = None,
    previous_turn_id: str | None = None,
    resolution: QueryResolution | None = None,
    task_frame: TaskFrame | None = None,
) -> TurnIntent:
    cleaned, protected_content_present = _top_level_follow_up_query(query)
    follow_up = is_contextual_follow_up(
        query,
        envelope,
        previous_intent,
        resolution=resolution if not protected_content_present else None,
    )
    explicit_task_type = _explicit_task_type(cleaned)
    explicit_task_switch = (
        explicit_task_type is not None
        and previous_intent is not None
        and explicit_task_type != previous_intent.question_type
    )
    explicit_subject_switch = bool(
        previous_intent is not None
        and envelope.subject
        and envelope.subject != previous_intent.primary_subject
        and _EXPLICIT_SWITCH_PATTERN.search(cleaned)
    )
    comparison_entities: tuple[str, ...] = ()
    if (
        previous_intent is not None
        and envelope.subject
        and envelope.subject != previous_intent.primary_subject
        and _COMPARISON_PATTERN.search(cleaned)
    ):
        comparison_entities = (envelope.subject,)

    if (
        follow_up
        and explicit_task_switch
        and previous_intent is not None
        and not explicit_subject_switch
    ):
        question_type = explicit_task_type or envelope.question_type
        return TurnIntent(
            primary_subject=previous_intent.primary_subject,
            secondary_topics=previous_intent.secondary_topics,
            question_type=question_type,
            answer_owner=answer_owner_for_question_type(question_type),
            comparison_entities=previous_intent.comparison_entities,
            inherited_from_turn=previous_turn_id,
            evidence_atom_ids=previous_intent.evidence_atom_ids,
            skill_ids=previous_intent.skill_ids,
            stage_artifact_ids=previous_intent.stage_artifact_ids,
            time_horizon=envelope.time_horizon,
            timeframe=envelope.timeframe,
            operators=envelope.operators,
            required_outputs=envelope.required_outputs,
            task_frame_hash=(
                task_frame.task_frame_hash if task_frame is not None else ""
            ),
        )

    inherit = follow_up and not explicit_task_switch and not explicit_subject_switch
    if inherit and previous_intent is not None:
        return TurnIntent(
            primary_subject=previous_intent.primary_subject,
            secondary_topics=_merge_topics(
                previous_intent.secondary_topics,
                _secondary_topics(envelope, previous_intent.primary_subject),
            ),
            question_type=previous_intent.question_type,
            answer_owner=previous_intent.answer_owner,
            comparison_entities=_merge_topics(
                previous_intent.comparison_entities,
                comparison_entities,
            ),
            inherited_from_turn=previous_turn_id,
            evidence_atom_ids=previous_intent.evidence_atom_ids,
            skill_ids=previous_intent.skill_ids,
            stage_artifact_ids=previous_intent.stage_artifact_ids,
            time_horizon=(
                envelope.time_horizon
                if envelope.time_horizon != "unspecified"
                else previous_intent.time_horizon
            ),
            timeframe=(
                envelope.timeframe
                if envelope.timeframe is not None
                else previous_intent.timeframe
            ),
            operators=_merge_topics(
                previous_intent.operators,
                envelope.operators,
            ),
            required_outputs=_merge_topics(
                previous_intent.required_outputs,
                envelope.required_outputs,
            ),
            task_frame_hash=(
                task_frame.task_frame_hash if task_frame is not None else ""
            ),
        )

    # 无 task_frame 时不能直接用 envelope.question_type：主语是"大盘/市场"这类泛指时
    # 信封只给 general_finance_qa，要靠 answer_orchestrator 的规则兜底才认得出复盘类问题。
    # 与 plan_answer_question 共用同一个解析器，避免 CLI 与会话两条路径给出不同答法。
    if task_frame is not None:
        question_type = task_frame.question_type
    else:
        from intelligence.services.answer_orchestrator import resolve_question_type

        question_type, _ = resolve_question_type(cleaned, envelope)
    return TurnIntent(
        primary_subject=(
            task_frame.subject if task_frame is not None else envelope.subject
        ),
        secondary_topics=_secondary_topics(
            envelope,
            task_frame.subject if task_frame is not None else envelope.subject,
        ),
        question_type=question_type,
        answer_owner=answer_owner_for_question_type(question_type),
        comparison_entities=comparison_entities,
        inherited_from_turn=None,
        time_horizon=envelope.time_horizon,
        timeframe=(
            task_frame.timeframe if task_frame is not None else envelope.timeframe
        ),
        operators=envelope.operators,
        required_outputs=(
            task_frame.required_outputs
            if task_frame is not None
            else envelope.required_outputs
        ),
        task_frame_hash=(
            task_frame.task_frame_hash if task_frame is not None else ""
        ),
    )


def contextualize_intent_query(query: str, intent: TurnIntent) -> str:
    cleaned = query.strip()
    if intent.inherited_from_turn is None or not intent.primary_subject:
        return cleaned
    comparison = (
        "；比较对象：" + "、".join(intent.comparison_entities)
        if intent.comparison_entities
        else ""
    )
    return f"主体：{intent.primary_subject}{comparison}\n追问：{cleaned}"


def _explicit_task_type(query: str) -> str | None:
    for question_type, pattern in _TASK_SWITCH_PATTERNS.items():
        if pattern.search(query):
            return question_type
    return None


def _secondary_topics(
    envelope: QueryEnvelope,
    primary_subject: str | None,
) -> tuple[str, ...]:
    if envelope.subject and envelope.subject != primary_subject:
        return (envelope.subject,)
    return ()


def _merge_topics(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group if item))


OPERATOR_STRICT_DOUBLE_RED = "market.strict_double_red_snapshot"
OPERATOR_CROSS_TABLE = "market.cross_table_exact_intersection"
OPERATOR_AGGREGATE_COUNT = "market.aggregate_count"
OPERATOR_DETAIL_ROWS = "market.detail_rows"
OPERATOR_CATALOG_PREFLIGHT = "catalog.preflight"
OPERATOR_CONTRADICTION_AUDIT = "market.contradiction_audit"
OPERATOR_SUBSTITUTE_OBSERVATION = "market.substitute_observation"
OPERATOR_VOLUME_QUALIFICATION = "market.volume_qualification"
OPERATOR_STEP_TRAJECTORY = "market.volume_step_trajectory"
OPERATOR_WIDTH_RESONANCE = "market.width_resonance"

QueryRecipeIntent = Literal["aggregate", "detail", "timeseries", "cross_table"]


@dataclass(frozen=True)
class DefinitionReceipt:
    definition_id: str
    face_id: str = ""
    version: str = ""


@dataclass(frozen=True)
class QueryRecipe:
    intent: QueryRecipeIntent
    dataset: str = ""
    strict_date: bool = True


@dataclass(frozen=True)
class FactSlot:
    slot_id: str
    required: bool = True


@dataclass(frozen=True)
class ResearchProgram:
    """输入侧研究程序。operators 只许 ``compile_research_program`` 写入。"""

    program_id: str
    question_class: str
    operators: tuple[str, ...]
    definition_receipts: tuple[DefinitionReceipt, ...] = ()
    query_recipes: tuple[QueryRecipe, ...] = ()
    required_fact_slots: tuple[FactSlot, ...] = ()
    stop_rules: tuple[str, ...] = ()
    fallback_policy: str = ""
    publication_policy: str = "verified"

    def to_dict(self) -> dict[str, object]:
        return {
            "program_id": self.program_id,
            "question_class": self.question_class,
            "operators": list(self.operators),
            "definition_receipts": [
                {
                    "definition_id": item.definition_id,
                    "face_id": item.face_id,
                    "version": item.version,
                }
                for item in self.definition_receipts
            ],
            "query_recipes": [
                {
                    "intent": item.intent,
                    "dataset": item.dataset,
                    "strict_date": item.strict_date,
                }
                for item in self.query_recipes
            ],
            "required_fact_slots": [
                {
                    "slot_id": item.slot_id,
                    "required": item.required,
                }
                for item in self.required_fact_slots
            ],
            "stop_rules": list(self.stop_rules),
            "fallback_policy": self.fallback_policy,
            "publication_policy": self.publication_policy,
        }


_SLOT_BY_OPERATOR = {
    OPERATOR_STRICT_DOUBLE_RED: FactSlot("dual_red_snapshot", required=False),
    OPERATOR_AGGREGATE_COUNT: FactSlot("aggregate_count", required=False),
    OPERATOR_DETAIL_ROWS: FactSlot("detail_rows", required=False),
    OPERATOR_CROSS_TABLE: FactSlot("cross_table_intersection", required=False),
    OPERATOR_CATALOG_PREFLIGHT: FactSlot("catalog_preflight", required=False),
    OPERATOR_CONTRADICTION_AUDIT: FactSlot("contradiction_audit", required=False),
    OPERATOR_SUBSTITUTE_OBSERVATION: FactSlot(
        "substitute_observation", required=False
    ),
    OPERATOR_VOLUME_QUALIFICATION: FactSlot(
        "volume_qualification", required=False
    ),
    OPERATOR_STEP_TRAJECTORY: FactSlot(
        "volume_step_trajectory", required=False
    ),
}


def compile_research_program(
    query: str,
    *,
    question_class: str = "",
) -> ResearchProgram:
    """词面信号 → 稳定 operator id。唯一允许构造 ``ResearchProgram`` 的函数。"""

    from intelligence.services.query_understanding import (
        SIGNAL_AGGREGATE,
        SIGNAL_CONTRADICTION,
        SIGNAL_CROSS_TABLE,
        SIGNAL_DETAIL,
        SIGNAL_DOUBLE_RED,
        SIGNAL_FERMENTATION,
        SIGNAL_MARKET_WATCH,
        SIGNAL_STEP_TRAJECTORY,
        SIGNAL_SUBSTITUTE_OBSERVATION,
        surface_research_signals,
    )

    text = str(query or "").strip()
    klass = str(question_class or "").strip() or "general_finance_qa"
    signals = surface_research_signals(text, question_class=klass)
    operators: list[str] = []
    recipes: list[QueryRecipe] = []
    receipts: list[DefinitionReceipt] = []
    market_watch = SIGNAL_MARKET_WATCH in signals
    if market_watch:
        operators.append(OPERATOR_CATALOG_PREFLIGHT)
    if SIGNAL_DOUBLE_RED in signals or SIGNAL_FERMENTATION in signals:
        operators.append(OPERATOR_STRICT_DOUBLE_RED)
        receipts.append(
            DefinitionReceipt(
                definition_id="DOUBLE_RED_SQL",
                face_id="predicate.double-red",
            )
        )
        recipes.append(
            QueryRecipe(intent="timeseries", dataset="sector_daily", strict_date=True)
        )
    if SIGNAL_AGGREGATE in signals:
        operators.append(OPERATOR_AGGREGATE_COUNT)
        recipes.append(QueryRecipe(intent="aggregate", strict_date=True))
    elif SIGNAL_DETAIL in signals:
        operators.append(OPERATOR_DETAIL_ROWS)
        recipes.append(QueryRecipe(intent="detail", strict_date=True))
    if SIGNAL_CROSS_TABLE in signals:
        operators.append(OPERATOR_CROSS_TABLE)
        recipes.append(QueryRecipe(intent="cross_table", strict_date=True))
    if SIGNAL_CONTRADICTION in signals:
        operators.append(OPERATOR_CONTRADICTION_AUDIT)
    if SIGNAL_SUBSTITUTE_OBSERVATION in signals:
        operators.append(OPERATOR_SUBSTITUTE_OBSERVATION)
        recipes.append(
            QueryRecipe(
                intent="detail", dataset="sector_stock_daily", strict_date=True
            )
        )
    if SIGNAL_STEP_TRAJECTORY in signals:
        # 资格盘先于台阶：先定资格再谈板块（一个信号发两枚 operator）。
        # 不发 DefinitionReceipt——P0 无读取方，unread-fields 门禁先例
        # （替补单 probe_id 教训：为将来预留的字段不要先写）。
        # 宽度对照与资格盘/台阶同门（一个信号发三枚 operator）：板块前瞻题
        # 固定「资格→台阶→宽度」三件事实，判语留给画像。不发 slot——可选供给。
        operators.append(OPERATOR_VOLUME_QUALIFICATION)
        operators.append(OPERATOR_STEP_TRAJECTORY)
        operators.append(OPERATOR_WIDTH_RESONANCE)
        recipes.append(
            QueryRecipe(
                intent="timeseries", dataset="sector_daily", strict_date=True
            )
        )

    operators = list(dict.fromkeys(operators))
    slots = tuple(
        _SLOT_BY_OPERATOR[operator]
        for operator in operators
        if operator in _SLOT_BY_OPERATOR
    )
    fallback = (
        "empty_pool_one_shot" if OPERATOR_CATALOG_PREFLIGHT in operators else ""
    )
    stop_rules = ("calendar_or_empty_standing_day",) if market_watch else ()
    canonical = {
        "fallback_policy": fallback,
        "operators": operators,
        "publication_policy": "verified",
        "query": text,
        "question_class": klass,
        "stop_rules": list(stop_rules),
        "definition_receipts": [asdict(item) for item in receipts],
        "query_recipes": [asdict(item) for item in recipes],
        "required_fact_slots": [asdict(item) for item in slots],
    }
    program_id = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return ResearchProgram(
        program_id=program_id,
        question_class=klass,
        operators=tuple(operators),
        definition_receipts=tuple(receipts),
        query_recipes=tuple(recipes),
        required_fact_slots=slots,
        stop_rules=stop_rules,
        fallback_policy=fallback,
        publication_policy="verified",
    )
