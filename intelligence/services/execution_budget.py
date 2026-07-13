"""Shared monotonic deadline helpers for workbench execution."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionBudget:
    """Represent one end-to-end time budget using a monotonic deadline."""

    started_at: float
    deadline_at: float

    @classmethod
    def start(cls, total_seconds: float) -> ExecutionBudget:
        if not math.isfinite(total_seconds) or total_seconds < 0:
            raise ValueError("total_seconds must be finite and non-negative")
        started_at = time.monotonic()
        return cls(started_at=started_at, deadline_at=started_at + total_seconds)

    def remaining_seconds(self, now: float | None = None) -> float:
        current = time.monotonic() if now is None else now
        return max(0.0, self.deadline_at - current)

    def child_timeout(
        self,
        requested: float,
        reserve: float = 0,
        now: float | None = None,
    ) -> float:
        if not math.isfinite(requested) or requested < 0:
            raise ValueError("requested must be finite and non-negative")
        if not math.isfinite(reserve) or reserve < 0:
            raise ValueError("reserve must be finite and non-negative")
        available = max(0.0, self.remaining_seconds(now=now) - reserve)
        return min(requested, available)

    def exhausted(self, now: float | None = None) -> bool:
        return self.remaining_seconds(now=now) <= 0
