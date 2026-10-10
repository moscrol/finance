
WITH idx AS (SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) AS i FROM fact_market_daily),
px AS (
    SELECT s.trade_date, s.stock_ts_code, rtrim(replace(s.stock_name, chr(0), '')) AS stock_name, s.close, c.i
    FROM tf_src_stock_daily s JOIN idx c USING (trade_date)
    WHERE s.close IS NOT NULL AND s.close > 0
),
lagged AS (
    SELECT *,
           LAG(close, 20) OVER w AS base_close_20, LAG(i, 20) OVER w AS base_i_20
    FROM px WINDOW w AS (PARTITION BY stock_ts_code ORDER BY i)
),
gains AS (
    SELECT trade_date, i, stock_ts_code, stock_name, 20 AS window_days, (close / base_close_20 - 1) * 100 AS gain_pct
    FROM lagged WHERE base_close_20 IS NOT NULL AND base_close_20 > 0 AND base_i_20 = i - 20
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY window_days, trade_date ORDER BY gain_pct DESC, stock_ts_code) AS rank
    FROM gains
),
-- 个股的申万一级：fact_sector_stock_daily.sw_industry 只从 2026-04 起逐日覆盖全市场（更早只有零星日子），
-- 而行业归属基本不随时间变（5574 只里 97 只在覆盖期内换过一次一级）。取每只股票最近一天的归属作静态维表，
-- 用到全部日期；同日多行按 sw_industry 排序取首，确定性。
l1_latest AS (
    SELECT stock_ts_code, split_part(sw_industry, '-', 1) AS sw_l1,
           ROW_NUMBER() OVER (PARTITION BY stock_ts_code ORDER BY trade_date DESC, sw_industry) AS rn
    FROM fact_sector_stock_daily WHERE sw_industry IS NOT NULL
),
l1 AS (SELECT stock_ts_code, sw_l1 FROM l1_latest WHERE rn = 1),
lim AS (
    SELECT trade_date, stock_ts_code, MAX(limit_times) AS limit_times
    FROM fact_theme_limit_stock_daily WHERE limit_status = 'U' GROUP BY 1, 2
)
SELECT r.window_days, r.trade_date, r.rank, r.stock_ts_code, r.stock_name, r.gain_pct, l1.sw_l1, lim.limit_times
FROM ranked r LEFT JOIN l1 USING (stock_ts_code) LEFT JOIN lim USING (trade_date, stock_ts_code)
WHERE r.rank <= 30
ORDER BY r.window_days, r.trade_date, r.rank

