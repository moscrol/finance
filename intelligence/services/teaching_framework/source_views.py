"""授课框架读口切到同花顺并跑表（工单 #41 E）。

同一连接上建 TEMP VIEW。新表在就切过去；夹具只有旧表时 view 等于旧表，
现有测试不用改。个股名在切主后为空（产品面不出个股）。
"""

from __future__ import annotations

import duckdb

STOCK_VIEW = "tf_src_stock_daily"
SECTOR_PX_VIEW = "tf_src_sector_px"
HIGH_VIEW = "tf_src_new_high_1y"
DRAGON_VIEW = "tf_src_dragon"
AUCTION_ZT_VIEW = "tf_src_auction_zt"

NEW_HIGH_PERIODS = ("1y", "2y", "3y", "history")


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    # 只读连接 / TEMP VIEW 并存时 information_schema 的 catalog 不一定是 main；直接探表。
    try:
        con.execute(f"SELECT 1 FROM {name} LIMIT 0")
    except duckdb.CatalogException:
        return False
    return True


def attach_teaching_sources(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """在 ``con`` 上建五个 TEMP VIEW，返回逻辑名 → 实际物理源（写进收据）。"""

    sources: dict[str, str] = {}

    if table_exists(con, "fact_stock_daily_hithink"):
        # dump 是未复权的，裸 close/LAG(close) 在除权日会把分红送转算成下跌
        # （实测 8,390 个除权日里 946 行偏离旧表 >0.5pp，最大 −36.76pp）。
        # 用复权事件表还原交易所口径的前收盘：
        #   adj_prev = (prev − 每股现金红利 + 配股价 × 配股比例) / (1 + 每股送转 + 配股比例)
        # 该公式在「旧表恰好也复权」的 946 行上与旧表中位绝对差 0.0037pp（已验证）。
        if table_exists(con, "fact_stock_adjustment_hithink"):
            adj_join = """
            LEFT JOIN fact_stock_adjustment_hithink a
              ON a.stock_ts_code = l.stock_ts_code AND a.ex_date = l.trade_date
            """
            adj_prev = """
            CASE WHEN a.stock_ts_code IS NULL THEN l.prev_close ELSE
                (l.prev_close
                 - COALESCE(a.dividend_per_share, 0)
                 + COALESCE(a.allotment_price, 0) * COALESCE(a.allotment_ratio, 0))
                / NULLIF(1 + COALESCE(a.per_share_bonus, 0)
                           + COALESCE(a.allotment_ratio, 0), 0)
            END
            """
        else:
            adj_join = ""
            adj_prev = "l.prev_close"
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {STOCK_VIEW} AS
            WITH lagged AS (
                SELECT
                    trade_date, stock_ts_code, close, high, low, open, turnover,
                    LAG(close) OVER (
                        PARTITION BY stock_ts_code ORDER BY trade_date
                    ) AS prev_close
                FROM fact_stock_daily_hithink
                WHERE close IS NOT NULL
            )
            SELECT
                l.trade_date,
                l.stock_ts_code,
                CAST(NULL AS VARCHAR) AS stock_name,
                l.close, l.high, l.low, l.open,
                l.turnover / 1e8 AS amount,
                (l.close / NULLIF({adj_prev}, 0) - 1) * 100 AS pct_chg
            FROM lagged l
            {adj_join}
            """
        )
        sources["stock"] = (
            "fact_stock_daily_hithink+adjustment"
            if adj_join
            else "fact_stock_daily_hithink"
        )
    elif table_exists(con, "fact_stock_daily"):
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {STOCK_VIEW} AS
            SELECT trade_date, stock_ts_code, stock_name, close, high,
                   CAST(NULL AS DOUBLE) AS low, CAST(NULL AS DOUBLE) AS open,
                   amount, pct_chg
            FROM fact_stock_daily
            """
        )
        sources["stock"] = "fact_stock_daily"
    else:
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {STOCK_VIEW} AS
            SELECT CAST(NULL AS DATE) AS trade_date, CAST(NULL AS VARCHAR) AS stock_ts_code,
                   CAST(NULL AS VARCHAR) AS stock_name, CAST(NULL AS DOUBLE) AS close,
                   CAST(NULL AS DOUBLE) AS high, CAST(NULL AS DOUBLE) AS low,
                   CAST(NULL AS DOUBLE) AS open, CAST(NULL AS DOUBLE) AS amount,
                   CAST(NULL AS DOUBLE) AS pct_chg
            WHERE FALSE
            """
        )
        sources["stock"] = "absent"

    if table_exists(con, "fact_sector_kline_daily"):
        # 目录里 6 个宽基指数（000001.SH 等）和 848 个板块同表。指数不是板块，
        # 不能进「板块涨幅中位 / 上涨比」的分母，用 category 排掉（目录缺失时不过滤）。
        has_dim = table_exists(con, "dim_sector_hithink")
        name_join = "LEFT JOIN dim_sector_hithink d USING (sector_ts_code)" if has_dim else ""
        name_col = "d.sector_name" if has_dim else "CAST(NULL AS VARCHAR)"
        not_index = (
            "AND COALESCE(d.category, '') <> 'index'" if has_dim else ""
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {SECTOR_PX_VIEW} AS
            SELECT
                k.trade_date,
                k.sector_ts_code,
                {name_col} AS sector_name,
                (k.close / LAG(k.close) OVER (
                    PARTITION BY k.sector_ts_code ORDER BY k.trade_date
                ) - 1) * 100 AS pct_chg,
                k.turnover / 1e8 AS amount,
                k.close
            FROM fact_sector_kline_daily k
            {name_join}
            WHERE k.close IS NOT NULL AND k.close > 0 {not_index}
            """
        )
        sources["sector_px"] = "fact_sector_kline_daily"
    elif table_exists(con, "fact_sector_daily"):
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {SECTOR_PX_VIEW} AS
            SELECT trade_date, sector_ts_code, sector_name, pct_chg, amount,
                   CAST(NULL AS DOUBLE) AS close
            FROM fact_sector_daily
            """
        )
        sources["sector_px"] = "fact_sector_daily"
    else:
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {SECTOR_PX_VIEW} AS
            SELECT CAST(NULL AS DATE) AS trade_date, CAST(NULL AS VARCHAR) AS sector_ts_code,
                   CAST(NULL AS VARCHAR) AS sector_name, CAST(NULL AS DOUBLE) AS pct_chg,
                   CAST(NULL AS DOUBLE) AS amount, CAST(NULL AS DOUBLE) AS close
            WHERE FALSE
            """
        )
        sources["sector_px"] = "absent"

    if table_exists(con, "fact_stock_daily_hithink"):
        if table_exists(con, "fact_sector_stock_daily"):
            l1_cte = """
            , l1_latest AS (
                SELECT stock_ts_code, split_part(sw_industry, '-', 1) AS sw_l1,
                       ROW_NUMBER() OVER (
                           PARTITION BY stock_ts_code
                           ORDER BY trade_date DESC, sw_industry
                       ) AS rn
                FROM fact_sector_stock_daily
                WHERE sw_industry IS NOT NULL
            ),
            l1 AS (SELECT stock_ts_code, sw_l1 FROM l1_latest WHERE rn = 1)
            """
            l1_select = "l1.sw_l1"
            l1_join = "LEFT JOIN l1 USING (stock_ts_code)"
        else:
            l1_cte = ""
            l1_select = "CAST(NULL AS VARCHAR) AS sw_l1"
            l1_join = ""
        # 「1 年新高」= 当日最高价 ≥ 过去 365 个**日历日**内的最高价，且该股在表里
        # 至少有满一年的历史（次新不算）。用日历窗而不是「252 个连续交易行」：
        # 后者会因为一年里停牌过一天就把整只股永久剔除（实测 09-01 少算 6 只）。
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {HIGH_VIEW} AS
            WITH px AS (
                SELECT trade_date, stock_ts_code, high
                FROM fact_stock_daily_hithink
                WHERE high IS NOT NULL AND high > 0
            ),
            w AS (
                SELECT
                    trade_date, stock_ts_code, high,
                    MAX(high) OVER (
                        PARTITION BY stock_ts_code ORDER BY trade_date
                        RANGE BETWEEN INTERVAL 365 DAY PRECEDING AND CURRENT ROW
                    ) AS max_1y,
                    MIN(trade_date) OVER (PARTITION BY stock_ts_code) AS first_day
                FROM px
            ),
            highs AS (
                SELECT trade_date, stock_ts_code
                FROM w
                WHERE first_day <= trade_date - INTERVAL 365 DAY
                  AND high >= max_1y
            )
            {l1_cte}
            SELECT h.trade_date, h.stock_ts_code, {l1_select}
            FROM highs h
            {l1_join}
            """
        )
        sources["new_high"] = "fact_stock_daily_hithink"
    elif table_exists(con, "fact_stock_high_daily"):
        periods = ", ".join(f"'{p}'" for p in NEW_HIGH_PERIODS)
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {HIGH_VIEW} AS
            SELECT trade_date, stock_ts_code, sw_l1
            FROM fact_stock_high_daily
            WHERE primary_high_period IN ({periods})
            """
        )
        sources["new_high"] = "fact_stock_high_daily"
    else:
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {HIGH_VIEW} AS
            SELECT CAST(NULL AS DATE) AS trade_date, CAST(NULL AS VARCHAR) AS stock_ts_code,
                   CAST(NULL AS VARCHAR) AS sw_l1
            WHERE FALSE
            """
        )
        sources["new_high"] = "absent"

    if table_exists(con, "fact_dragon_tiger_hithink"):
        # 同花顺龙虎榜只回溯一年，旧表回到 2025-01：直接替换会让日历前段整段丢标签
        # （实测 416 天日历里旧表 405 天有值、新表 242 天，tf.dragon_* 会空 166 天）。
        # 与竞价同一个写法：按**日**回退，新源有行的日子用新源，整天没有才用旧表，
        # 不逐行 UNION（同一天两源都有会重复计数）。
        legacy_fill = (
            """
            UNION ALL
            SELECT trade_date, stock_ts_code, net_amount
            FROM fact_dragon_tiger_daily
            WHERE net_amount IS NOT NULL
              AND trade_date NOT IN (SELECT DISTINCT trade_date FROM h)
            """
            if table_exists(con, "fact_dragon_tiger_daily")
            else ""
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {DRAGON_VIEW} AS
            WITH h AS (
                SELECT trade_date, stock_ts_code, net_value / 1e8 AS net_amount
                FROM fact_dragon_tiger_hithink
                WHERE net_value IS NOT NULL
            )
            SELECT * FROM h
            {legacy_fill}
            """
        )
        sources["dragon"] = (
            "fact_dragon_tiger_hithink+legacy_fill"
            if legacy_fill
            else "fact_dragon_tiger_hithink"
        )
    elif table_exists(con, "fact_dragon_tiger_daily"):
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {DRAGON_VIEW} AS
            SELECT trade_date, stock_ts_code, net_amount
            FROM fact_dragon_tiger_daily
            WHERE net_amount IS NOT NULL
            """
        )
        sources["dragon"] = "fact_dragon_tiger_daily"
    else:
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {DRAGON_VIEW} AS
            SELECT CAST(NULL AS DATE) AS trade_date, CAST(NULL AS VARCHAR) AS stock_ts_code,
                   CAST(NULL AS DOUBLE) AS net_amount
            WHERE FALSE
            """
        )
        sources["dragon"] = "absent"

    # 「昨日涨停股竞价」要日历表定「昨日」，三张缺一张就退回旧 zt 面板。
    if (
        table_exists(con, "fact_auction_hithink")
        and table_exists(con, "fact_theme_limit_stock_daily")
        and table_exists(con, "fact_market_daily")
    ):
        old_fill = (
            """
            UNION ALL
            SELECT trade_date, stock_ts_code, auction_pct, auction_amount
            FROM fact_auction_stock_daily
            WHERE panel_key = 'zt'
              AND trade_date NOT IN (SELECT DISTINCT trade_date FROM snap)
            """
            if table_exists(con, "fact_auction_stock_daily")
            else ""
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {AUCTION_ZT_VIEW} AS
            WITH idx AS (
                SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) AS i
                FROM fact_market_daily
            ),
            lim AS (
                SELECT nxt.trade_date, l.stock_ts_code
                FROM fact_theme_limit_stock_daily l
                JOIN idx cur USING (trade_date)
                JOIN idx nxt ON nxt.i = cur.i + 1
                WHERE l.limit_status = 'U'
            ),
            snap AS (
                SELECT a.trade_date, a.stock_ts_code, a.auction_pct, a.auction_amount
                FROM fact_auction_hithink a
                JOIN lim ON lim.trade_date = a.trade_date
                       AND lim.stock_ts_code = a.stock_ts_code
                WHERE a.kind = 'snapshot'
            )
            SELECT * FROM snap
            {old_fill}
            """
        )
        sources["auction_zt"] = (
            "fact_auction_hithink+legacy_fill" if old_fill else "fact_auction_hithink"
        )
    elif table_exists(con, "fact_auction_stock_daily"):
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {AUCTION_ZT_VIEW} AS
            SELECT trade_date, stock_ts_code, auction_pct, auction_amount
            FROM fact_auction_stock_daily
            WHERE panel_key = 'zt'
            """
        )
        sources["auction_zt"] = "fact_auction_stock_daily"
    else:
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW {AUCTION_ZT_VIEW} AS
            SELECT CAST(NULL AS DATE) AS trade_date, CAST(NULL AS VARCHAR) AS stock_ts_code,
                   CAST(NULL AS DOUBLE) AS auction_pct, CAST(NULL AS DOUBLE) AS auction_amount
            WHERE FALSE
            """
        )
        sources["auction_zt"] = "absent"

    return sources
