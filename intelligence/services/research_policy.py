from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from intelligence.services.research_contract import ResearchDeadline


@dataclass(frozen=True)
class ResearchExecutionPolicy:
    max_skill_calls: int = 3
    max_elapsed_seconds: float = 120.0
    max_retries_per_skill: int = 0


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
        return {
            "max_skill_calls": self.policy.max_skill_calls,
            "max_elapsed_ms": round(self.policy.max_elapsed_seconds * 1000),
            "max_retries_per_skill": self.policy.max_retries_per_skill,
            "call_count": self.call_count,
            "attempt_count": len(self.attempts),
            "elapsed_ms": round(self.elapsed_seconds * 1000),
            "remaining_ms": round(self.remaining_seconds * 1000),
            "attempts": [asdict(attempt) for attempt in self.attempts],
        }
