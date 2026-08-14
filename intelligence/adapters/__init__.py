from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["KnowledgeAdapter", "MarketAdapter"]

if TYPE_CHECKING:
    from intelligence.adapters.knowledge import KnowledgeAdapter
    from intelligence.adapters.market import MarketAdapter


def __getattr__(name: str) -> Any:
    # Lazy export so importing KnowledgeAdapter does not require duckdb
    # (only MarketAdapter depends on it).
    if name == "KnowledgeAdapter":
        from intelligence.adapters.knowledge import KnowledgeAdapter

        return KnowledgeAdapter
    if name == "MarketAdapter":
        from intelligence.adapters.market import MarketAdapter

        return MarketAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
