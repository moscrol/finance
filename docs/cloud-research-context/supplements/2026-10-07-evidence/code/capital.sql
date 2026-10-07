
WITH cal AS (SELECT trade_date, total_amount FROM fact_market_daily),
idx AS (SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) AS i FROM fact_market_daily),
dt AS (
    SELECT trade_date, COUNT(DISTINCT stock_ts_code) AS dragon_count,
           CAST(SUM(CAST(net_amount AS DECIMAL(18, 6))) AS DOUBLE) AS dragon_net_amount,
           CAST(SUM(CAST(CASE WHEN net_amount > 0 THEN net_amount ELSE 0 END AS DECIMAL(18, 6))) AS DOUBLE) AS buy_sum,
           CAST(SUM(CAST(CASE WHEN net_amount < 0 THEN -net_amount ELSE 0 END AS DECIMAL(18, 6))) AS DOUBLE) AS sell_sum
    FROM tf_src_dragon WHERE net_amount IS NOT NULL GROUP BY trade_date
),
dt_day AS (
    SELECT c.trade_date, c.i, dt.dragon_count, dt.dragon_net_amount,
           CASE WHEN cal.total_amount > 0 THEN 1000.0 * dt.dragon_net_amount / cal.total_amount END AS dragon_net_amount_ratio_pm,
           CASE WHEN dt.sell_sum > 0 THEN dt.buy_sum / dt.sell_sum END AS dragon_buy_sell_ratio
    FROM idx c JOIN cal USING (trade_date) LEFT JOIN dt USING (trade_date)
),
dt_w AS (
    SELECT trade_date, dragon_count, dragon_net_amount, dragon_net_amount_ratio_pm, dragon_buy_sell_ratio,
           AVG(dragon_net_amount_ratio_pm) OVER w AS ratio_ma5, AVG(dragon_buy_sell_ratio) OVER w AS bs_ma5,
           COUNT(dragon_net_amount_ratio_pm) OVER w AS n5_ratio, COUNT(dragon_buy_sell_ratio) OVER w AS n5_bs,
           LAG(i, 4) OVER (ORDER BY i) AS i_lag4, i
    FROM dt_day WINDOW w AS (ORDER BY i ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
),
seal AS (
    SELECT trade_date, stock_ts_code, MAX(fd_amount) AS fd, MAX(circ_mv) AS mv
    FROM fact_theme_limit_stock_daily WHERE limit_status = 'U' GROUP BY 1, 2
),
seal_day AS (
    SELECT trade_date, MEDIAN(fd) AS limit_seal_amount_median_wan, MEDIAN(fd / NULLIF(mv, 0)) AS limit_seal_mv_ratio_median,
           CAST(SUM(CASE WHEN fd / NULLIF(mv, 0) >= 100 THEN 1 ELSE 0 END) AS DOUBLE) * 100.0 / NULLIF(COUNT(fd), 0) AS limit_thick_seal_share_pct
    FROM seal GROUP BY trade_date
),
au AS (
    SELECT trade_date, MEDIAN(auction_pct) AS auction_zt_pct_median,
           CAST(SUM(CASE WHEN auction_pct > 0 THEN 1 ELSE 0 END) AS DOUBLE) * 100.0 / NULLIF(COUNT(auction_pct), 0) AS auction_zt_positive_share_pct,
           CAST(SUM(CAST(auction_amount AS DECIMAL(18, 6))) AS DOUBLE) AS auction_zt_amount
    FROM tf_src_auction_zt GROUP BY trade_date
)
SELECT cal.trade_date, dt_w.dragon_count, dt_w.dragon_net_amount, dt_w.dragon_net_amount_ratio_pm, dt_w.dragon_buy_sell_ratio,
       CASE WHEN dt_w.n5_ratio = 5 AND dt_w.i_lag4 = dt_w.i - 4 THEN dt_w.ratio_ma5 END AS dragon_net_amount_ratio_pm_ma5,
       CASE WHEN dt_w.n5_bs = 5 AND dt_w.i_lag4 = dt_w.i - 4 THEN dt_w.bs_ma5 END AS dragon_buy_sell_ratio_ma5,
       seal_day.limit_seal_amount_median_wan, seal_day.limit_seal_mv_ratio_median, seal_day.limit_thick_seal_share_pct,
       au.auction_zt_pct_median, au.auction_zt_positive_share_pct, au.auction_zt_amount
FROM cal LEFT JOIN dt_w USING (trade_date) LEFT JOIN seal_day USING (trade_date) LEFT JOIN au USING (trade_date)
ORDER BY cal.trade_date

