-- Market Feature Store schema
-- 设计文档: docs/superpowers/specs/2026-06-02-market-feature-store-design.md
--
-- 分层约定:
--   dim_*      维表
--   fact_*     镜像层事实表 (来自飞书/复盘会, 可重建, 只读)
--   config_*   人工维护配置层 (别名/题材映射/策略参数/自选)
--   feature_*  特征层 (由事实表计算, 可删除重算)
--
-- 所有事实表带 source / updated_at 以便追溯来源与刷新时间。

-- ============================================================
-- 维表
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_sector (
    sector_ts_code   TEXT PRIMARY KEY,
    sector_name      TEXT NOT NULL,
    sw_l1            TEXT,
    is_active        BOOLEAN,
    first_seen_date  DATE,
    last_seen_date   DATE,
    source           TEXT,
    updated_at       TIMESTAMP
);

-- ============================================================
-- 事实层: 镜像
-- ============================================================

CREATE TABLE IF NOT EXISTS fact_market_daily (
    trade_date               DATE PRIMARY KEY,
    market_stage             TEXT,
    stage_day                INTEGER,
    ice_point                TEXT,
    total_amount             DOUBLE,
    amount_vs_yesterday_pct  DOUBLE,
    amount_ma20              DOUBLE,
    volume_ratio             DOUBLE,
    volume_state             TEXT,
    advancers                INTEGER,
    limit_up                 INTEGER,
    limit_down               INTEGER,
    sh_week_ma               DOUBLE,
    sh_deviation_pct         DOUBLE,
    top3_industry_ratio      DOUBLE,
    concentration_state      TEXT,
    industry_1               TEXT,
    industry_1_ratio         DOUBLE,
    industry_2               TEXT,
    industry_2_ratio         DOUBLE,
    industry_3               TEXT,
    industry_3_ratio         DOUBLE,
    strength_avg_pct         DOUBLE,
    strength_amount_pct      DOUBLE,
    strength_amount          DOUBLE,
    strength_marginal_pct    DOUBLE,
    strength_yesterday_avg_pct DOUBLE,
    strength_ma5_avg_pct     DOUBLE,
    strength_ma20_avg_pct    DOUBLE,
    strength_status          TEXT,
    strength_source          TEXT,
    strength_updated_at      TIMESTAMP,
    note                     TEXT,
    source                   TEXT,
    updated_at               TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_sector_daily (
    trade_date      DATE,
    sector_ts_code  TEXT,
    sector_name     TEXT,
    sw_l1           TEXT,
    pct_chg         DOUBLE,
    amount          DOUBLE,
    diff_ratio      DOUBLE,
    strength        DOUBLE,
    multi_period_resonance BOOLEAN,
    multi_period_source TEXT,
    multi_period_updated_at TIMESTAMP,
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (trade_date, sector_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_date ON fact_sector_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_sector ON fact_sector_daily(sector_ts_code);

CREATE TABLE IF NOT EXISTS fact_sector_stock_daily (
    trade_date        DATE,
    sector_ts_code    TEXT,
    sector_name       TEXT,
    sw_l1             TEXT,
    stock_ts_code     TEXT,
    stock_name        TEXT,
    price             DOUBLE,
    pct_chg           DOUBLE,
    amount            DOUBLE,
    pct_chg_3d        DOUBLE,
    pct_chg_5d        DOUBLE,
    pct_chg_10d       DOUBLE,
    pct_chg_20d       DOUBLE,
    high_status       TEXT,
    high_status_label TEXT,
    limit_times       INTEGER,
    fund_flow_1d      DOUBLE,
    fund_flow_5d      DOUBLE,
    sw_industry       TEXT,
    leader_plate      TEXT,
    leader_sub_plate  TEXT,
    role_tags_json    TEXT,
    circ_mv           DOUBLE,
    float_mcap_yi     DOUBLE,
    total_mcap_yi     DOUBLE,
    free_float_mcap_yi DOUBLE,
    mcap_source       TEXT,
    source            TEXT,
    updated_at        TIMESTAMP,
    PRIMARY KEY (trade_date, sector_ts_code, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_date ON fact_sector_stock_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_stock ON fact_sector_stock_daily(stock_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_sector ON fact_sector_stock_daily(sector_ts_code);

CREATE TABLE IF NOT EXISTS fact_stock_daily (
    trade_date     DATE,
    stock_ts_code  TEXT,
    stock_name     TEXT,
    close          DOUBLE,
    pre_close      DOUBLE,
    pct_chg        DOUBLE,
    amount         DOUBLE,
    turnover       DOUBLE,
    source         TEXT,
    updated_at     TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_stock_daily_date ON fact_stock_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_stock_daily_stock ON fact_stock_daily(stock_ts_code);

CREATE TABLE IF NOT EXISTS fact_high_volume_gainers (
    start_date         DATE,
    end_date           DATE,
    stock_ts_code      TEXT,
    stock_name         TEXT,
    themes             TEXT,
    avg_amount         DOUBLE,
    interval_gain_pct  DOUBLE,
    weighted_gain      DOUBLE,
    rank               INTEGER,
    source             TEXT,
    updated_at         TIMESTAMP,
    PRIMARY KEY (start_date, end_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_hvg_range ON fact_high_volume_gainers(start_date, end_date);

CREATE TABLE IF NOT EXISTS fact_top_gainers (
    start_date         DATE,
    end_date           DATE,
    stock_ts_code      TEXT,
    stock_name         TEXT,
    sw_industry        TEXT,
    themes             TEXT,
    interval_gain_pct  DOUBLE,
    avg_amount         DOUBLE,
    up_value           DOUBLE,
    deviation_pct      DOUBLE,
    rank               INTEGER,
    source             TEXT,
    updated_at         TIMESTAMP,
    PRIMARY KEY (start_date, end_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_tg_range ON fact_top_gainers(start_date, end_date);

CREATE TABLE IF NOT EXISTS fact_limit_advance_presence (
    trade_date   DATE,
    stock_name   TEXT,
    sequence_no  INTEGER,
    source       TEXT,
    updated_at   TIMESTAMP,
    PRIMARY KEY (trade_date, stock_name)
);
CREATE INDEX IF NOT EXISTS idx_fact_lap_date ON fact_limit_advance_presence(trade_date);

CREATE TABLE IF NOT EXISTS fact_limit_advance_daily (
    trade_date        DATE,
    stock_ts_code     TEXT,
    stock_name        TEXT,
    boards            INTEGER,
    first_limit_date  DATE,
    theme             TEXT,
    pct_chg           DOUBLE,
    promotion_rate    TEXT,
    source            TEXT,
    updated_at        TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_lad_date ON fact_limit_advance_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_stock_technical_snapshot (
    trade_date     DATE,
    stock_ts_code  TEXT,
    stock_name     TEXT,
    up_value       DOUBLE,
    deviation_pct  DOUBLE,
    source_table   TEXT,
    source         TEXT,
    updated_at     TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code, source_table)
);
CREATE INDEX IF NOT EXISTS idx_fact_sts_date ON fact_stock_technical_snapshot(trade_date);

-- ============================================================
-- 配置层: 人工维护
-- ============================================================

CREATE TABLE IF NOT EXISTS config_sector_alias (
    alias           TEXT,
    sector_ts_code  TEXT,
    sector_name     TEXT,
    confidence      DOUBLE,
    note            TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (alias, sector_ts_code)
);

CREATE TABLE IF NOT EXISTS config_theme_sector_link (
    theme           TEXT,
    direction       TEXT,
    sector_ts_code  TEXT,
    sector_name     TEXT,
    match_type      TEXT,
    confidence      DOUBLE,
    note            TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (theme, direction, sector_ts_code)
);

CREATE TABLE IF NOT EXISTS config_strategy_rule (
    rule_name    TEXT PRIMARY KEY,
    rule_type    TEXT,
    params_json  TEXT,
    enabled      BOOLEAN,
    note         TEXT,
    updated_at   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS config_watchlist (
    stock_ts_code  TEXT,
    stock_name     TEXT,
    group_name     TEXT,
    reason         TEXT,
    updated_at     TIMESTAMP,
    PRIMARY KEY (stock_ts_code, group_name)
);

-- ============================================================
-- 特征层: 可重算
-- ============================================================

CREATE TABLE IF NOT EXISTS feature_sector_window (
    as_of_date        DATE,
    start_date        DATE,
    end_date          DATE,
    sector_ts_code    TEXT,
    sector_name       TEXT,
    sw_l1             TEXT,
    interval_pct_chg  DOUBLE,
    amount_avg        DOUBLE,
    amount_change_pct DOUBLE,
    diff_start        DOUBLE,
    diff_end          DOUBLE,
    diff_max          DOUBLE,
    diff_min          DOUBLE,
    diff_change       DOUBLE,
    diff_trend        TEXT,
    calculated_at     TIMESTAMP,
    PRIMARY KEY (as_of_date, start_date, end_date, sector_ts_code)
);

CREATE TABLE IF NOT EXISTS feature_stock_window (
    as_of_date         DATE,
    start_date         DATE,
    end_date           DATE,
    stock_ts_code      TEXT,
    stock_name         TEXT,
    interval_gain_pct  DOUBLE,
    avg_amount         DOUBLE,
    weighted_gain      DOUBLE,
    sector_count       INTEGER,
    sector_names       TEXT,
    sw_l1_names        TEXT,
    calculated_at      TIMESTAMP,
    PRIMARY KEY (as_of_date, start_date, end_date, stock_ts_code)
);

CREATE TABLE IF NOT EXISTS feature_market_window (
    as_of_date        DATE,
    start_date        DATE,
    end_date          DATE,
    advancers_start   INTEGER,
    advancers_end     INTEGER,
    advancers_change  INTEGER,
    advancers_ma5     DOUBLE,
    limit_up_avg      DOUBLE,
    limit_down_avg    DOUBLE,
    amount_avg        DOUBLE,
    breadth_trend     TEXT,
    calculated_at     TIMESTAMP,
    PRIMARY KEY (as_of_date, start_date, end_date)
);

CREATE TABLE IF NOT EXISTS feature_limit_advance_window (
    as_of_date       DATE,
    start_date       DATE,
    end_date         DATE,
    stock_ts_code    TEXT,
    stock_name       TEXT,
    advance_days     INTEGER,
    max_boards       INTEGER,
    first_seen_date  DATE,
    last_seen_date   DATE,
    themes           TEXT,
    calculated_at    TIMESTAMP,
    PRIMARY KEY (as_of_date, start_date, end_date, stock_name)
);

CREATE TABLE IF NOT EXISTS feature_stock_technical_daily (
    trade_date     DATE,
    stock_ts_code  TEXT,
    stock_name     TEXT,
    close          DOUBLE,
    ma26           DOUBLE,
    std26          DOUBLE,
    up_value       DOUBLE,
    deviation_pct  DOUBLE,
    calculated_at  TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_feature_stech_date ON feature_stock_technical_daily(trade_date);
