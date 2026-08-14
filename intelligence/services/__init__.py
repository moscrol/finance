from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["ThemeRadarService"]

if TYPE_CHECKING:
    from intelligence.services.theme_radar import ThemeRadarService


def __getattr__(name: str) -> Any:
    # Lazy export so importing intelligence.services.ask does not pull in
    # theme_radar (which depends on the duckdb-backed MarketAdapter).
    if name == "ThemeRadarService":
        from intelligence.services.theme_radar import ThemeRadarService

        return ThemeRadarService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
