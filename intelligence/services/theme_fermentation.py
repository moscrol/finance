"""发酵摘要（P1a）：清单题材命中主线/双红后，回看近窗口的袋内轨迹。

Spec: docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md §3.3 P1
台账: R-20260827-01

口径纪律：双红与涨停热度的**判定**不在本模块——逐交易日委托
``market_watch_pack._query_dual_red`` / ``_query_limit_heat``，与当日简报
接合用的是同一份袋口径；两袋都有 LIMIT 截断，所以计数语义是「在袋 / 在榜」
而非全市场绝对计数（措辞在 ``FermentationSummary.text`` 里锁死）。
本模块自有 SQL 只许碰交易日历（fact_market_daily）；
机械核查见 test_theme_fermentation.test_module_contains_no_second_caliber_sql。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from intelligence.services.market_watch_pack import (
    _names_match,
    _open,
    _query_dual_red,
    _query_limit_heat,
)

DEFAULT_WINDOW = 10


@dataclass(frozen=True)
class FermentationSummary:
    """单个清单项的窗口轨迹：全部字段来自袋行，事后对账只对 to_dict()。"""

    subject: str
    sector_name: str
    standing_date: str
    window_days: int
    window_start: str | None
    dual_red_days: int
    dual_red_streak: int
    first_dual_red: str | None
    latest_dual_red: str | None
    heat_days: int
    peak_limit_up: Any | None
    peak_limit_up_date: str | None
    daily: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "sector_name": self.sector_name,
            "standing_date": self.standing_date,
            "window_days": self.window_days,
            "window_start": self.window_start,
            "dual_red_days": self.dual_red_days,
            "dual_red_streak": self.dual_red_streak,
            "first_dual_red": self.first_dual_red,
            "latest_dual_red": self.latest_dual_red,
            "heat_days": self.heat_days,
            "peak_limit_up": self.peak_limit_up,
            "peak_limit_up_date": self.peak_limit_up_date,
            "daily": list(self.daily),
            "text": self.text(),
        }

    def text(self) -> str:
        """确定性拼装的一句话摘要；数字全部能在 to_dict() 里逐字找到。"""

        if self.dual_red_days:
            dual = f"严格双红在袋 {self.dual_red_days} 天（最近 {self.latest_dual_red}"
            if self.dual_red_streak >= 2:
                dual += f"，连 {self.dual_red_streak} 天"
            dual += "）"
        else:
            dual = "严格双红在袋 0 天"
        if self.heat_days:
            heat = f"涨停热度在榜 {self.heat_days} 天"
            if self.peak_limit_up is not None:
                heat += f"（峰值 {self.peak_limit_up} 家 @{self.peak_limit_up_date}）"
        else:
            heat = "涨停热度在榜 0 天"
        return (
            f"「{self.sector_name}」近 {self.window_days} 交易日：{dual}；{heat}。"
        )


def trace_sectors_fermentation(
    subjects: Sequence[tuple[str, str]],
    *,
    market_db_path: str | Path | None,
    standing_date: str | None,
    window: int = DEFAULT_WINDOW,
) -> tuple[FermentationSummary, ...]:
    """批量回看：subjects = ((清单项原文, 命中的袋内板块名), ...)。

    每个交易日各查一次双红袋与热度袋（主体数不放大查询数），
    再按 ``_names_match`` 的同一套包含规则把板块名对到袋行上。
    日历解析不到（站立日之前无交易日）或库不可用时返回空元组，
    调用方按「无摘要」处理，不得编造。
    """

    if not subjects or not standing_date:
        return ()
    opened = _open(market_db_path)
    if opened is None or not opened.available:
        return ()
    con = opened.connection
    try:
        dates = _trading_window(con, standing_date, window)
        if not dates:
            return ()
        dual_rows_by_day = {d: _query_dual_red(con, d).rows for d in dates}
        heat_rows_by_day = {d: _query_limit_heat(con, d).rows for d in dates}
    finally:
        con.close()

    out: list[FermentationSummary] = []
    for subject, sector_name in subjects:
        daily: list[dict[str, Any]] = []
        dual_days = 0
        heat_days = 0
        first_dual: str | None = None
        latest_dual: str | None = None
        peak: Any | None = None
        peak_date: str | None = None
        streak = 0
        for day in dates:
            dual_row = _match_row(sector_name, dual_rows_by_day[day])
            heat_row = _match_row(sector_name, heat_rows_by_day[day])
            if dual_row is not None:
                dual_days += 1
                streak += 1
                latest_dual = day
                if first_dual is None:
                    first_dual = day
            else:
                streak = 0
            if heat_row is not None:
                heat_days += 1
                count = heat_row.get("limit_up_count")
                if count is not None and (peak is None or count > peak):
                    peak = count
                    peak_date = day
            daily.append(
                {
                    "trade_date": day,
                    "dual_red": dual_row is not None,
                    "dual_red_row": dual_row,
                    "limit_up_count": (
                        heat_row.get("limit_up_count")
                        if heat_row is not None
                        else None
                    ),
                }
            )
        out.append(
            FermentationSummary(
                subject=subject,
                sector_name=sector_name,
                standing_date=standing_date,
                window_days=len(dates),
                window_start=dates[0] if dates else None,
                dual_red_days=dual_days,
                dual_red_streak=streak,
                first_dual_red=first_dual,
                latest_dual_red=latest_dual,
                heat_days=heat_days,
                peak_limit_up=peak,
                peak_limit_up_date=peak_date,
                daily=tuple(daily),
            )
        )
    return tuple(out)


def _match_row(
    sector_name: str, rows: Sequence[dict[str, Any]]
) -> dict[str, Any] | None:
    for row in rows:
        name = str(row.get("sector_name") or "")
        if name and _names_match(sector_name, name):
            return dict(row)
    return None


def _trading_window(con: Any, standing: str, window: int) -> list[str]:
    """近 window 个交易日（含站立日），来自 fact_market_daily 日历，升序返回。"""

    fetched = con.execute(
        """
        select distinct trade_date from fact_market_daily
        where trade_date <= cast(? as date)
        order by trade_date desc
        limit ?
        """,
        [standing, int(window)],
    ).fetchall()
    return [str(row[0]) for row in reversed(fetched)]
