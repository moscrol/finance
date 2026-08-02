from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ProviderStatus = Literal[
    "not_attempted",
    "success",
    "partial",
    "empty",
    "disabled",
    "proxy_unavailable",
    "request_error",
    "parse_error",
    "stale",
    "fallback_success",
    "fallback_failed",
    "future_of_cutoff",
]


@dataclass(frozen=True)
class ProviderTrace:
    provider: str
    capability: str
    status: ProviderStatus
    detail: str = ""
    source_trade_date: str | None = None
    result_count: int = 0
    parent_id: str | None = None
    step_id: str | None = None
    requested_date: str | None = None
    served_date: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> "ProviderTrace":
        if not isinstance(value, dict):
            raise ValueError("ProviderTrace must be an object")
        return cls(
            provider=str(value.get("provider") or ""),
            capability=str(value.get("capability") or ""),
            status=value.get("status", "not_attempted"),
            detail=str(value.get("detail") or ""),
            source_trade_date=(
                str(value["source_trade_date"])
                if value.get("source_trade_date") is not None
                else None
            ),
            result_count=int(value.get("result_count") or 0),
            parent_id=(
                str(value["parent_id"]) if value.get("parent_id") is not None else None
            ),
            step_id=(
                str(value["step_id"]) if value.get("step_id") is not None else None
            ),
            requested_date=(
                str(value["requested_date"])
                if value.get("requested_date") is not None
                else None
            ),
            served_date=(
                str(value["served_date"])
                if value.get("served_date") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
