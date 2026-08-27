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
    requested_time_range: tuple[str | None, str | None] | None = None

    @classmethod
    def from_dict(cls, value: object) -> "ProviderTrace":
        if not isinstance(value, dict):
            raise ValueError("ProviderTrace must be an object")
        raw_range = value.get("requested_time_range")
        requested_time_range = None
        if isinstance(raw_range, dict):
            requested_time_range = (
                str(raw_range["start"]) if raw_range.get("start") is not None else None,
                str(raw_range["end"]) if raw_range.get("end") is not None else None,
            )
        elif isinstance(raw_range, (list, tuple)) and len(raw_range) == 2:
            requested_time_range = (
                str(raw_range[0]) if raw_range[0] is not None else None,
                str(raw_range[1]) if raw_range[1] is not None else None,
            )
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
            requested_time_range=requested_time_range,
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.requested_time_range is not None:
            start, end = self.requested_time_range
            payload["requested_time_range"] = {"start": start, "end": end}
        return payload


_AGENT_PROVIDER_PREFIX = "agent:"


def provider_trace_tool_name(trace: "ProviderTrace") -> str:
    """从一条 trace 里取出**真实工具名**。

    为什么需要这个函数：agent 工具的 trace 在成功和失败两条路上把工具名放在
    了不同字段——

        成功  provider="agent:kb_search"   capability="agent_loop"
        失败  provider="agent:kb_search"   capability="kb_search"

    于是任何 ``group by capability`` 的统计，都会把所有成功扫进 ``agent_loop``
    这个桶，真名下面只剩失败。2026-08-14 实测被这个坑到过一次：按 capability
    算出「kb_search 20 次调用 0% 成功」，按真名重算是另一回事。**这类偏差不是
    噪声，它单向地把每个工具都读成接近全灭。**

    统一口径：``provider`` 带 ``agent:`` 前缀时以它为准（那一侧两条路都对），
    否则回落 ``capability``（非 agent 工具没有这个歧义）。

    可迁移：同一事实在不同代码路径上写进不同字段，比"字段缺失"更难发现——
    缺失会露出 None，而错位会给你一个看着挺合理的错数。
    """

    provider = str(getattr(trace, "provider", "") or "")
    if provider.startswith(_AGENT_PROVIDER_PREFIX):
        name = provider[len(_AGENT_PROVIDER_PREFIX):].strip()
        if name:
            return name
    return str(getattr(trace, "capability", "") or "")
