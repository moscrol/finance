from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from intelligence.services.research_contract import ResearchDeadline


@dataclass(frozen=True)
class GroundedBudgetProfile:
    """Immutable wall-clock contract for one grounded two-phase chain.

    ``measurement_basis`` is deliberately data, not only a comment, so tests
    and traces can keep the provenance honest: this profile comes from one
    frozen preregistered canary/replay, not from a latency distribution.
    """

    name: str
    root_seconds: int
    synthesis_reserve_seconds: int
    child_seconds: int
    composer_grant_seconds: int
    judge_reserve_seconds: int
    minimum_two_phase_entry_seconds: int
    measurement_basis: str


grounded_deep = GroundedBudgetProfile(
    name="grounded_deep",
    # 146.55s observed end-to-end need * 1.2 = 175.86s; round the bounded
    # deployment profile up to 180s rather than claiming percentile coverage.
    root_seconds=180,
    # 97s two-phase minimum plus 3s of local hand-off room; retrieval keeps 80s.
    synthesis_reserve_seconds=100,
    # Preserve the preregistered bounded synthesis-child ceiling below root.
    child_seconds=115,
    # ceil(33.338s * 1.2), from the frozen composer replay.
    composer_grant_seconds=40,
    # ceil(46.982s * 1.2), from the frozen semantic-judge replay.
    judge_reserve_seconds=57,
    # Exact admission floor: 40s composer grant + 57s judge reserve.
    minimum_two_phase_entry_seconds=97,
    measurement_basis=(
        "single preregistered A4 canary plus frozen replay: 146.55s observed "
        "end-to-end need, 20% slack = 175.86s; engineering headroom only, "
        "not p95 or another latency percentile"
    ),
)


@dataclass(frozen=True)
class ResearchExecutionPolicy:
    max_skill_calls: int = 3
    max_elapsed_seconds: float = 120.0
    max_retries_per_skill: int = 0
    # turn 级 LLM 调用硬上限（按 provider 尝试计）：controller/judge/agent/
    # 合成/修订/影子链共用一本账，超额后新调用被拒发并降级。默认宽松，
    # 定位是失控保险丝而不是常态限流。
    max_llm_calls: int = 40
    # Legacy presenter 在根 turn 内的合成保留段。默认保留旧 20s；产品
    # conversation entry 会显式注入 grounded_deep 的 100s。
    synthesis_reserve_seconds: float = 20.0
    grounded_budget_profile: GroundedBudgetProfile | None = None


@dataclass(frozen=True)
class ToolAttempt:
    tool: str
    input_summary: str
    provider: str
    status: str
    elapsed_ms: int
    retry_count: int = 0
    failure_reason: str = ""


@dataclass
class ResearchExecutionBudget:
    policy: ResearchExecutionPolicy
    started_at: float = field(default_factory=time.monotonic)
    attempts: list[ToolAttempt] = field(default_factory=list)
    deadline: ResearchDeadline | None = None

    def __post_init__(self) -> None:
        if self.deadline is None:
            self.deadline = ResearchDeadline.from_timeout(
                self.policy.max_elapsed_seconds
            )

    def can_start(self) -> bool:
        # 用 remaining_seconds 而非 stage_remaining_seconds：预算紧张时仍允许
        # 启动 skill 去拿部分结果（有总比没有好），真正的保护在调用处对
        # allowed_seconds 的钳制——skill 最多只能用 stage 预算，吃不到预留段。
        return (
            self.call_count < self.policy.max_skill_calls
            and self.remaining_seconds > 0
        )

    @property
    def call_count(self) -> int:
        return sum(
            attempt.status not in {"skipped_budget", "skipped_duplicate"}
            for attempt in self.attempts
        )

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    @property
    def remaining_seconds(self) -> float:
        if self.deadline is None:
            return 0.0
        return self.deadline.remaining()

    @property
    def stage_remaining_seconds(self) -> float:
        """前置阶段（skill/工具调用）可用的秒数：剩余预算扣除合成保留段。

        与 :attr:`remaining_seconds` 的区别是后者含 ``synthesis_reserve``。
        前置阶段必须用本属性，否则一个慢/失败的 skill 会吃光整轮预算，
        让最终合成只剩 0ms 而降级为模板（见 ResearchDeadline.synthesis_reserve）。
        """
        if self.deadline is None:
            return 0.0
        return self.deadline.stage_timeout(self.deadline.remaining())

    def record(
        self,
        tool: str,
        *,
        input_summary: str,
        provider: str,
        status: str,
        elapsed_ms: int,
        failure_reason: str = "",
    ) -> None:
        self.attempts.append(
            ToolAttempt(
                tool=tool,
                input_summary=input_summary,
                provider=provider,
                status=status,
                elapsed_ms=elapsed_ms,
                failure_reason=failure_reason,
            )
        )

    def to_trace(self) -> dict[str, object]:
        trace: dict[str, object] = {
            "max_skill_calls": self.policy.max_skill_calls,
            "max_elapsed_ms": round(self.policy.max_elapsed_seconds * 1000),
            "synthesis_reserve_ms": round(
                min(
                    max(0.0, self.policy.synthesis_reserve_seconds),
                    max(0.0, self.policy.max_elapsed_seconds),
                )
                * 1000
            ),
            "max_retries_per_skill": self.policy.max_retries_per_skill,
            "call_count": self.call_count,
            "attempt_count": len(self.attempts),
            "elapsed_ms": round(self.elapsed_seconds * 1000),
            "remaining_ms": round(self.remaining_seconds * 1000),
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }
        if self.policy.grounded_budget_profile is not None:
            trace["grounded_budget_profile"] = asdict(
                self.policy.grounded_budget_profile
            )
        return trace
