"""飞书「每日指标」表同步已退役。

市场指标（成交/涨家/阶段等）统一由 sync-market-overview
（复盘会 reviews/market → fact_market_daily）写入。
保留此路径，避免旧自动化得到一个看似成功但实际打退役飞书的结果。
旧实现见 git 历史。
"""

from __future__ import annotations


def sync_fact_market_daily() -> dict:
    raise RuntimeError(
        "sync-market-daily 已退役；市场指标用 "
        "python3 -m market_feature_store.cli sync-market-overview"
    )
