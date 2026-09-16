"""fact_sector_stock_daily -> fact_stock_daily 当日兜底回填。

当 mootdx `sync-stock-daily` 卡死/不可用, 但复盘只需要当日量价时, 用复盘会板块成分股
当日行情 (price/pct_chg/amount) 聚合补当日 fact_stock_daily, 让完整性闸门和策略矩阵可继续。

口径与边界:
- 只写指定 trade_date 一天, 不动历史; 同一股票跨多个板块映射时取一致行情 (max 即原值)。
- source 标记为 'fupanhui:sector_stock_daily:fallback', 与 mootdx 原生口径区分, 便于审计。
- pre_close 由 close 和当日 pct_chg 反推; pct_chg=-100 等异常值不反推。
- turnover 不可得, 置空。
不是 mootdx 的等价替代 (无前复权历史序列); 仅用于当日复盘兜底。
"""
from __future__ import annotations

from datetime import datetime

from ..db import connect, init_db

FALLBACK_SOURCE = "fupanhui:sector_stock_daily:fallback"

UPSERT_SQL = """
INSERT INTO fact_stock_daily
  (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, amount, turnover, source, updated_at)
SELECT
  trade_date,
  stock_ts_code,
  any_value(stock_name) AS stock_name,
  max(price) AS close,
  CASE WHEN max(pct_chg) IS NOT NULL AND max(pct_chg) != -100
       THEN max(price) / (1 + max(pct_chg) / 100.0) ELSE NULL END AS pre_close,
  max(pct_chg) AS pct_chg,
  max(amount) AS amount,
  NULL AS turnover,
  ? AS source,
  ? AS updated_at
FROM fact_sector_stock_daily
WHERE trade_date = ?
GROUP BY trade_date, stock_ts_code
ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
  stock_name = EXCLUDED.stock_name,
  close = EXCLUDED.close,
  pre_close = EXCLUDED.pre_close,
  pct_chg = EXCLUDED.pct_chg,
  amount = EXCLUDED.amount,
  turnover = EXCLUDED.turnover,
  source = EXCLUDED.source,
  updated_at = EXCLUDED.updated_at
"""


def fill_stock_daily_fallback(trade_date: str, ma_window: int = 5,
                              recompute_deviation: bool = True) -> dict:
    """用 fact_sector_stock_daily 当日行情兜底补 fact_stock_daily, 可选复算上证均线偏离。

    recompute_deviation: True 时用最近 ma_window 个交易日 sh_index_close 复算
    fact_market_daily.sh_week_ma / sh_deviation_pct (标注为本地复算口径)。
    """
    init_db()
    con = connect()
    try:
        src_rows = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT stock_ts_code) FROM fact_sector_stock_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()
        if not src_rows or src_rows[0] == 0:
            return {
                "trade_date": trade_date,
                "source_rows": 0,
                "stock_rows": 0,
                "deviation": None,
                "note": "fact_sector_stock_daily 当日无数据, 无法兜底",
            }

        now = datetime.now()
        con.execute(UPSERT_SQL, [FALLBACK_SOURCE, now, trade_date])
        stock_rows = con.execute(
            "SELECT COUNT(*) FROM fact_stock_daily WHERE trade_date = ?", [trade_date]
        ).fetchone()[0]

        deviation = None
        if recompute_deviation:
            closes = con.execute(
                "SELECT trade_date, sh_index_close FROM fact_market_daily "
                "WHERE trade_date <= ? AND sh_index_close IS NOT NULL "
                "ORDER BY trade_date DESC LIMIT ?",
                [trade_date, ma_window],
            ).fetchall()
            if closes and str(closes[0][0]) == trade_date and len(closes) >= 1:
                ma = sum(float(r[1]) for r in closes) / len(closes)
                close = float(closes[0][1])
                dev = (close / ma - 1) * 100 if ma else None
                con.execute(
                    "UPDATE fact_market_daily SET sh_week_ma = ?, sh_deviation_pct = ? WHERE trade_date = ?",
                    [round(ma, 2), round(dev, 2) if dev is not None else None, trade_date],
                )
                deviation = {
                    "sh_week_ma": round(ma, 2),
                    "sh_deviation_pct": round(dev, 2) if dev is not None else None,
                    "window": len(closes),
                    "note": "本地最近交易日 sh_index_close 复算",
                }
    finally:
        con.close()

    return {
        "trade_date": trade_date,
        "source_rows": src_rows[0],
        "source_stocks": src_rows[1],
        "stock_rows": stock_rows,
        "source": FALLBACK_SOURCE,
        "deviation": deviation,
    }
