from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ProviderStatus = Literal[
    "not_attempted",
    "success",
    "empty",
    "disabled",
    "proxy_unavailable",
    "request_error",
    "parse_error",
    "stale",
    "fallback_success",
    "fallback_failed",
]


@dataclass(frozen=True)
class ProviderTrace:
    provider: str
    capability: str
    status: ProviderStatus
    detail: str = ""
    source_trade_date: str | None = None
    result_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
