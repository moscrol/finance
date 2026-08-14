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
    sh_index_close           DOUBLE,
    sh_index_pct_chg         DOUBLE,
    sh_index_open            DOUBLE,
    sh_index_high            DOUBLE,
    sh_index_low             DOUBLE,
    sh_index_volume          DOUBLE,
    sh_index_amount          DOUBLE,
    sh_index_source          TEXT,
    sh_index_updated_at      TIMESTAMP,
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
    stock_high_count_history INTEGER,
    stock_high_count_3y      INTEGER,
    stock_high_count_2y      INTEGER,
    stock_high_count_1y      INTEGER,
    stock_high_count_120d    INTEGER,
    stock_high_count_60d     INTEGER,
    stock_high_count_20d     INTEGER,
    stock_high_source        TEXT,
    stock_high_updated_at    TIMESTAMP,
    note                     TEXT,
    summary_keywords         TEXT,
    source                   TEXT,
    updated_at               TIMESTAMP
);
ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS summary_keywords TEXT;

-- 板块 universe 快照台账：同一交易日可有多份候选，只有 published 那份对外可见。
-- 供应商会换代码、改名单，没有这层就无法回答「当时用的是哪一版板块清单」。
CREATE TABLE IF NOT EXISTS ops_sector_universe_snapshot_daily (
    trade_date      DATE,
    snapshot_id     TEXT,
    provider_source TEXT NOT NULL,
    sector_count    INTEGER NOT NULL,
    declared_relationship_count BIGINT NOT NULL,
    status          TEXT NOT NULL,
    captured_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    CHECK (status IN ('candidate', 'published', 'superseded', 'rejected')),
    PRIMARY KEY (trade_date, snapshot_id)
);

-- 快照内的板块名单及其「应有个股数」：用于校验抓取完整度
-- （expected_stock_count vs 实际落库行数），是快照能否 published 的依据。
CREATE TABLE IF NOT EXISTS fact_sector_universe_daily (
    trade_date           DATE,
    snapshot_id          TEXT,
    sector_ts_code       TEXT,
    sector_name          TEXT NOT NULL,
    expected_stock_count INTEGER NOT NULL,
    provider_source      TEXT NOT NULL,
    captured_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (trade_date, snapshot_id, sector_ts_code)
);

-- 逐板块抓取进度台账：断点续抓的依据，也让「哪些板块抓空了/报错了」可查。
-- expected vs actual 的差额就是这一版快照的缺口。
CREATE TABLE IF NOT EXISTS ops_sector_member_sync_daily (
    trade_date           DATE,
    snapshot_id          TEXT,
    sector_ts_code       TEXT,
    status               TEXT NOT NULL,
    expected_stock_count INTEGER NOT NULL,
    actual_stock_count   INTEGER,
    attempt_count        INTEGER NOT NULL DEFAULT 0,
    last_error_code      TEXT,
    first_attempted_at   TIMESTAMP WITH TIME ZONE,
    last_attempted_at    TIMESTAMP WITH TIME ZONE,
    completed_at         TIMESTAMP WITH TIME ZONE,
    CHECK (status IN ('pending', 'success', 'empty', 'error')),
    PRIMARY KEY (trade_date, snapshot_id, sector_ts_code)
);

-- 写入落 *_generation 表（snapshot_id 进主键，同日多版互不覆盖），
-- 读走同名 VIEW（只暴露 published 那版）。消费方查询无需改写。
CREATE TABLE IF NOT EXISTS fact_sector_daily_generation (
    trade_date      DATE,
    sector_universe_snapshot_id TEXT,
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
    PRIMARY KEY (trade_date, sector_universe_snapshot_id, sector_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_gen_date
    ON fact_sector_daily_generation(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_gen_sector
    ON fact_sector_daily_generation(sector_ts_code);

-- 'legacy' 是快照机制上线前的历史数据：当日没有任何 published 快照时才可见，
-- 保证回填出 published 版本后旧行自动让位、不会双份并存。
CREATE OR REPLACE VIEW fact_sector_daily AS
SELECT g.trade_date, g.sector_ts_code, g.sector_name, g.sw_l1, g.pct_chg, g.amount,
       g.diff_ratio, g.strength, g.multi_period_resonance, g.multi_period_source,
       g.multi_period_updated_at, g.source, g.updated_at, g.sector_universe_snapshot_id
FROM fact_sector_daily_generation AS g
WHERE EXISTS (
        SELECT 1 FROM ops_sector_universe_snapshot_daily AS h
        WHERE h.trade_date = g.trade_date
          AND h.snapshot_id = g.sector_universe_snapshot_id
          AND h.status = 'published'
      )
   OR (g.sector_universe_snapshot_id = 'legacy'
       AND NOT EXISTS (
             SELECT 1 FROM ops_sector_universe_snapshot_daily AS h
             WHERE h.trade_date = g.trade_date AND h.status = 'published'
           ));

CREATE TABLE IF NOT EXISTS fact_sector_period_rank_daily (
    trade_date      DATE,
    period_type     TEXT,
    rank            INTEGER,
    sector_ts_code  TEXT,
    sector_name     TEXT,
    change_pct      DOUBLE,
    limit_up_count  INTEGER,
    badge           TEXT,
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (trade_date, period_type, rank, sector_name)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_period_rank_date
    ON fact_sector_period_rank_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_sw_l1_daily (
    trade_date      DATE,
    sw_l1_code      TEXT,
    sw_l1           TEXT,
    close           DOUBLE,
    pre_close       DOUBLE,
    pct_chg         DOUBLE,
    amount          DOUBLE,
    fupanhui_ratio  DOUBLE,
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (trade_date, sw_l1)
);
CREATE INDEX IF NOT EXISTS idx_fact_sw_l1_daily_date ON fact_sw_l1_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sw_l1_daily_sw ON fact_sw_l1_daily(sw_l1);

-- 同 fact_sector_daily：写 *_generation，读同名 VIEW（只暴露 published 快照）。
CREATE TABLE IF NOT EXISTS fact_sector_stock_daily_generation (
    trade_date        DATE,
    sector_universe_snapshot_id TEXT,
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
    PRIMARY KEY (trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_gen_date
    ON fact_sector_stock_daily_generation(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_gen_stock
    ON fact_sector_stock_daily_generation(stock_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_gen_sector
    ON fact_sector_stock_daily_generation(sector_ts_code);

CREATE OR REPLACE VIEW fact_sector_stock_daily AS
SELECT g.trade_date, g.sector_ts_code, g.sector_name, g.sw_l1, g.stock_ts_code,
       g.stock_name, g.price, g.pct_chg, g.amount, g.pct_chg_3d, g.pct_chg_5d,
       g.pct_chg_10d, g.pct_chg_20d, g.high_status, g.high_status_label, g.limit_times,
       g.fund_flow_1d, g.fund_flow_5d, g.sw_industry, g.leader_plate, g.leader_sub_plate,
       g.role_tags_json, g.circ_mv, g.float_mcap_yi, g.total_mcap_yi, g.free_float_mcap_yi,
       g.mcap_source, g.source, g.updated_at, g.sector_universe_snapshot_id
FROM fact_sector_stock_daily_generation AS g
WHERE EXISTS (
        SELECT 1 FROM ops_sector_universe_snapshot_daily AS h
        WHERE h.trade_date = g.trade_date
          AND h.snapshot_id = g.sector_universe_snapshot_id
          AND h.status = 'published'
      )
   OR (g.sector_universe_snapshot_id = 'legacy'
       AND NOT EXISTS (
             SELECT 1 FROM ops_sector_universe_snapshot_daily AS h
             WHERE h.trade_date = g.trade_date AND h.status = 'published'
           ));

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

CREATE TABLE IF NOT EXISTS fact_stock_high_daily (
    trade_date              DATE,
    stock_ts_code           TEXT,
    stock_name              TEXT,
    primary_high_period     TEXT,
    primary_high_label      TEXT,
    high_periods_json       TEXT,
    is_new                  BOOLEAN,
    price                   DOUBLE,
    pct_chg                 DOUBLE,
    pct_chg_10d             DOUBLE,
    amount                  DOUBLE,
    market_cap              DOUBLE,
    fund_today              DOUBLE,
    limit_status            TEXT,
    limit_times             INTEGER,
    sw_l1                   TEXT,
    sw_l2                   TEXT,
    plate                   TEXT,
    whitelist_sectors_json  TEXT,
    source                  TEXT,
    updated_at              TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_stock_high_date ON fact_stock_high_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_stock_high_stock ON fact_stock_high_daily(stock_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_stock_high_period ON fact_stock_high_daily(primary_high_period);

CREATE TABLE IF NOT EXISTS fact_theme_limit_heat_daily (
    trade_date             DATE,
    sector_ts_code         TEXT,
    sector_name            TEXT,
    dimension              TEXT,
    scope                  TEXT,
    data_stage             TEXT,
    is_realtime            BOOLEAN,
    source_update_time     TIMESTAMP,
    market_limit_up_count  INTEGER,
    limit_up_count         INTEGER,
    total_count            INTEGER,
    limit_up_ratio         DOUBLE,
    market_share           DOUBLE,
    fd_amount              DOUBLE,
    rank                   INTEGER,
    top_stocks_json        TEXT,
    source                 TEXT,
    updated_at             TIMESTAMP,
    PRIMARY KEY (trade_date, sector_ts_code, dimension, scope)
);
CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_heat_date ON fact_theme_limit_heat_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_heat_sector ON fact_theme_limit_heat_daily(sector_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_heat_rank ON fact_theme_limit_heat_daily(trade_date, rank);

CREATE TABLE IF NOT EXISTS fact_theme_limit_stock_daily (
    trade_date             DATE,
    sector_ts_code         TEXT,
    sector_name            TEXT,
    stock_ts_code          TEXT,
    stock_name             TEXT,
    price                  DOUBLE,
    pct_chg                DOUBLE,
    pct_chg_3d             DOUBLE,
    pct_chg_5d             DOUBLE,
    pct_chg_10d            DOUBLE,
    pct_chg_20d            DOUBLE,
    amount                 DOUBLE,
    vol                    DOUBLE,
    circ_mv                DOUBLE,
    total_mv               DOUBLE,
    sw_l1                  TEXT,
    sw_l2                  TEXT,
    sw_l3                  TEXT,
    ths_concept_top        TEXT,
    fund_flow_1d           DOUBLE,
    fund_flow_5d           DOUBLE,
    limit_times            INTEGER,
    limit_status           TEXT,
    first_limit_time       TEXT,
    last_limit_time        TEXT,
    open_times             INTEGER,
    leader_plate           TEXT,
    leader_sub_plate       TEXT,
    theme_names_json       TEXT,
    up_stat                TEXT,
    up_stat_days           INTEGER,
    up_stat_boards         INTEGER,
    high_status            TEXT,
    high_status_label      TEXT,
    fd_amount              DOUBLE,
    limit_update_time      TIMESTAMP,
    source                 TEXT,
    updated_at             TIMESTAMP,
    PRIMARY KEY (trade_date, sector_ts_code, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_stock_date ON fact_theme_limit_stock_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_stock_sector ON fact_theme_limit_stock_daily(sector_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_theme_limit_stock_stock ON fact_theme_limit_stock_daily(stock_ts_code);

CREATE TABLE IF NOT EXISTS fact_mainline_theme_daily (
    trade_date    DATE,
    theme_code    TEXT,
    theme_name    TEXT,
    sector_count  INTEGER,
    min_sort      INTEGER,
    source        TEXT,
    updated_at    TIMESTAMP,
    PRIMARY KEY (trade_date, theme_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_theme_date ON fact_mainline_theme_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_mainline_stock_daily (
    trade_date      DATE,
    theme_code      TEXT,
    theme_name      TEXT,
    group_type      TEXT,
    stock_ts_code   TEXT,
    stock_name      TEXT,
    price           DOUBLE,
    pct_chg         DOUBLE,
    amount          DOUBLE,
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (trade_date, theme_code, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_stock_date ON fact_mainline_stock_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_stock_theme ON fact_mainline_stock_daily(theme_code);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_stock_stock ON fact_mainline_stock_daily(stock_ts_code);

CREATE TABLE IF NOT EXISTS fact_theme_flow_daily (
    trade_date    DATE,
    theme_code    TEXT,
    theme_name    TEXT,
    total_fund    DOUBLE,
    total_amount  DOUBLE,
    stock_count   INTEGER,
    source        TEXT,
    updated_at    TIMESTAMP,
    PRIMARY KEY (trade_date, theme_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_theme_flow_date ON fact_theme_flow_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_mainline_sector_daily (
    trade_date              DATE,
    theme_code              TEXT,
    theme_name              TEXT,
    sector_ts_code          TEXT,
    sector_name             TEXT,
    sort_no                 INTEGER,
    today_pct               DOUBLE,
    limit_up_count          INTEGER,
    max_limit_height        INTEGER,
    amount                  DOUBLE,
    amount_estimated        DOUBLE,
    amount_relative_ratio   DOUBLE,
    net_inflow_1d           DOUBLE,
    strength                DOUBLE,
    strength_chg            DOUBLE,
    cycle_level             TEXT,
    cycle_status            TEXT,
    startup_date_small      DATE,
    startup_date_big        DATE,
    startup_date_super      DATE,
    startup_date_extend     DATE,
    high_status             TEXT,
    high_status_label       TEXT,
    near_breakout_status    TEXT,
    near_breakout_label     TEXT,
    near_breakout_gap_pct   DOUBLE,
    note                    TEXT,
    source                  TEXT,
    updated_at              TIMESTAMP,
    PRIMARY KEY (trade_date, theme_code, sector_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_sector_date ON fact_mainline_sector_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_sector_theme ON fact_mainline_sector_daily(theme_code);
CREATE INDEX IF NOT EXISTS idx_fact_mainline_sector_sector ON fact_mainline_sector_daily(sector_ts_code);

CREATE TABLE IF NOT EXISTS fact_historical_mapping (
    source_date     DATE,
    similar_date    DATE,
    similarity      DOUBLE,
    external_cycle  TEXT,
    cycle_day       INTEGER,
    summary         TEXT,
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (source_date, similar_date)
);
CREATE INDEX IF NOT EXISTS idx_fact_hist_mapping_date ON fact_historical_mapping(source_date);

-- 复盘会龙头高度（/reviews/leader-ladder.height_trend，一次可回填约 120 日）
CREATE TABLE IF NOT EXISTS fact_leader_height_daily (
    trade_date       DATE PRIMARY KEY,
    height           INTEGER,
    leader_ts_code   TEXT,
    leader_name      TEXT,
    limit_times      INTEGER,
    fd_amount        DOUBLE,
    first_limit_time TEXT,
    source           TEXT,
    updated_at       TIMESTAMP
);

-- 外盘指数（请求日=A股交易日，source_trade_date=外盘实际会话日）
CREATE TABLE IF NOT EXISTS fact_global_index_daily (
    trade_date         DATE,
    source_trade_date  DATE,
    code               TEXT,
    name               TEXT,
    market_group       TEXT,
    close              DOUBLE,
    pct_chg            DOUBLE,
    data_stage         TEXT,
    source             TEXT,
    updated_at         TIMESTAMP,
    PRIMARY KEY (trade_date, code)
);
CREATE INDEX IF NOT EXISTS idx_fact_global_index_date ON fact_global_index_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_global_stock_daily (
    trade_date         DATE,
    source_trade_date  DATE,
    ts_code            TEXT,
    name_cn            TEXT,
    name_en            TEXT,
    exchange           TEXT,
    close              DOUBLE,
    pct_chg            DOUBLE,
    pct_chg_5d         DOUBLE,
    market_cap_usd     DOUBLE,
    business           TEXT,
    industry_position  TEXT,
    source             TEXT,
    updated_at         TIMESTAMP,
    PRIMARY KEY (trade_date, ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_global_stock_date ON fact_global_stock_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_dragon_tiger_daily (
    trade_date      DATE,
    stock_ts_code   TEXT,
    stock_name      TEXT,
    close           DOUBLE,
    pct_change      DOUBLE,
    turnover_rate   DOUBLE,
    amount          DOUBLE,
    l_buy           DOUBLE,
    l_sell          DOUBLE,
    l_amount        DOUBLE,
    net_amount      DOUBLE,
    net_rate        DOUBLE,
    amount_rate     DOUBLE,
    reason          TEXT,
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_dragon_date ON fact_dragon_tiger_daily(trade_date);

-- 龙虎榜席位级明细（/data/dragon/detail），比 fact_dragon_tiger_daily 深一层：
-- 谁买谁卖（营业部/游资/机构席位）。一日 × 一股 × 一席一行。
CREATE TABLE IF NOT EXISTS fact_dragon_seat_daily (
    trade_date      DATE,
    stock_ts_code   TEXT,
    stock_name      TEXT,
    side            TEXT,      -- buy / sell（席位在买方榜还是卖方榜）
    seat_no         INTEGER,   -- 榜内序号（1 起）
    exalter         TEXT,      -- 营业部/席位全称
    seat_type       TEXT,      -- 营业部 / 游资 / 机构
    hm_name         TEXT,      -- 游资名（游资席位才有）
    buy             DOUBLE,    -- 买入额（亿）
    sell            DOUBLE,    -- 卖出额（亿）
    buy_rate        DOUBLE,    -- 买入占成交比（%）
    sell_rate       DOUBLE,
    net_buy         DOUBLE,    -- 净买入（亿）
    source          TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code, side, exalter)
);
CREATE INDEX IF NOT EXISTS idx_fact_dragon_seat_date ON fact_dragon_seat_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_dragon_seat_stock ON fact_dragon_seat_daily(stock_ts_code);

-- 龙虎榜全市场日汇总（/data/dragon/all 的 summary）：机构/游资净买入、上榜数、活跃营业部。
CREATE TABLE IF NOT EXISTS fact_dragon_summary_daily (
    trade_date      DATE PRIMARY KEY,
    stock_count     INTEGER,   -- 上榜个股数
    inst_net_buy    DOUBLE,    -- 机构净买入（亿）
    youzi_net_buy   DOUBLE,    -- 游资净买入（亿）
    active_brokers  INTEGER,   -- 活跃营业部数
    source          TEXT,
    updated_at      TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fact_dragon_summary_date ON fact_dragon_summary_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_regulation_event_daily (
    effective_date           DATE,
    stock_ts_code            TEXT,
    stock_name               TEXT,
    start_date               DATE,
    end_date                 DATE,
    days_remaining_trading   INTEGER,
    status_type              TEXT,
    event_type               TEXT,
    event_types              TEXT,
    leader_plate             TEXT,
    source                   TEXT,
    updated_at               TIMESTAMP,
    PRIMARY KEY (effective_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_reg_event_date ON fact_regulation_event_daily(effective_date);

CREATE TABLE IF NOT EXISTS fact_regulation_pool_daily (
    effective_date   DATE,
    stock_ts_code    TEXT,
    stock_name       TEXT,
    pool_status      TEXT,
    close            DOUBLE,
    pct_chg_10d      DOUBLE,
    safe_space_10d   DOUBLE,
    safe_days_10d    INTEGER,
    pct_chg_30d      DOUBLE,
    safe_space_30d   DOUBLE,
    source           TEXT,
    updated_at       TIMESTAMP,
    PRIMARY KEY (effective_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_reg_pool_date ON fact_regulation_pool_daily(effective_date);

CREATE TABLE IF NOT EXISTS fact_core_stock_daily (
    trade_date       DATE,
    rank             INTEGER,
    stock_ts_code    TEXT,
    stock_name       TEXT,
    close            DOUBLE,
    pct_chg          DOUBLE,
    amount           DOUBLE,
    circ_mv          DOUBLE,
    sw_l1_name       TEXT,
    leader_plate     TEXT,
    fund_flow_today  DOUBLE,
    gain_5d          DOUBLE,
    gain_10d         DOUBLE,
    source           TEXT,
    updated_at       TIMESTAMP,
    PRIMARY KEY (trade_date, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_core_stock_date ON fact_core_stock_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_auction_stock_daily (
    trade_date       DATE,
    panel_key        TEXT,
    panel_label      TEXT,
    stock_ts_code    TEXT,
    stock_name       TEXT,
    auction_pct      DOUBLE,
    pct_chg          DOUBLE,
    auction_amount   DOUBLE,
    day_amount       DOUBLE,
    limit_seq        INTEGER,
    leader_plate     TEXT,
    source           TEXT,
    updated_at       TIMESTAMP,
    PRIMARY KEY (trade_date, panel_key, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_auction_date ON fact_auction_stock_daily(trade_date);

CREATE TABLE IF NOT EXISTS fact_event_daily (
    event_date     DATE,
    event_id       TEXT,
    title          TEXT,
    content        TEXT,
    importance     INTEGER,
    event_type     TEXT,
    source_types   TEXT,
    sectors        TEXT,
    is_future      BOOLEAN,
    source         TEXT,
    updated_at     TIMESTAMP,
    PRIMARY KEY (event_date, event_id)
);
CREATE INDEX IF NOT EXISTS idx_fact_event_date ON fact_event_daily(event_date);

CREATE TABLE IF NOT EXISTS fact_research_report_catalog (
    report_id      INTEGER PRIMARY KEY,
    title          TEXT,
    report_date    DATE,
    report_type    TEXT,
    is_hot         BOOLEAN,
    sector_tags    TEXT,
    concept_tags   TEXT,
    stock_count    INTEGER,
    stocks         TEXT,
    created_at     TEXT,
    source         TEXT,
    updated_at     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fact_research_report_date ON fact_research_report_catalog(report_date);

CREATE TABLE IF NOT EXISTS fact_theme_fundamental_doc (
    document_pk          INTEGER PRIMARY KEY,
    title                TEXT,
    produced_at          TEXT,
    workflow_name        TEXT,
    analysis_type        TEXT,
    core_theme           TEXT,
    verification_points  TEXT,
    linked_themes        TEXT,
    linked_sectors       TEXT,
    kb_path              TEXT,
    source               TEXT,
    updated_at           TIMESTAMP
);

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

-- ============================================================
-- 特征层: Level2 大单资金流（数据源 ClickHouse share 库逐笔成交,
-- 计算脚本 scripts/moneyflow/, 原始 tick 不落 DuckDB, 只落每日结果）
-- ============================================================

-- 昨日涨停榜(limitup) / 全市场成交额前100榜(top100) 大单资金流
CREATE TABLE IF NOT EXISTS feature_l2_capital_flow_daily (
    trade_date              DATE,
    scan_type               TEXT,      -- 'limitup' | 'top100'
    stock_code              TEXT,      -- 裸代码 如 000725
    stock_ts_code           TEXT,      -- 000725.XSHE, 便于与其它表 join
    stock_name              TEXT,
    main_buy_net_wan        DOUBLE,    -- 主买净额(万): 主动买入-主动卖出(大单口径)
    total_buy_net_wan       DOUBLE,    -- 总买净额(万): 主买净额+被动净额
    float_mktcap_yi         DOUBLE,    -- 流通市值(亿)
    score                   DOUBLE,    -- (0.7*主买+0.3*总买)/流通市值 净流入强度%
    pct_change              DOUBLE,    -- 当日涨幅%
    big_order_threshold_wan DOUBLE,    -- 大单阈值(同一委托单当日累计成交额)
    rank                    INTEGER,   -- 按 score 降序的当日名次
    prev_limitup_date       DATE,      -- 仅 limitup: 涨停发生日
    source                  TEXT,
    calculated_at           TIMESTAMP,
    PRIMARY KEY (trade_date, scan_type, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_feature_l2flow_date ON feature_l2_capital_flow_daily(trade_date);

-- 规律量化买单榜: 大买单中金额±1%窄带、反复出现>=10笔的簇
CREATE TABLE IF NOT EXISTS feature_l2_quant_orders_daily (
    trade_date              DATE,
    stock_code              TEXT,
    stock_ts_code           TEXT,
    stock_name              TEXT,
    quant_amount_wan        DOUBLE,    -- 量化单总额(万)
    quant_pct_of_big_buy    DOUBLE,    -- 占该股大单总买入比例%
    cluster_count           INTEGER,   -- 簇数
    order_count             INTEGER,   -- 笔数
    biggest_cluster         TEXT,      -- 最大簇描述 如 849-857万x55笔=46695万
    pct_change              DOUBLE,
    quant_threshold_wan     DOUBLE,    -- 量化单单笔金额下限
    big_order_threshold_wan DOUBLE,
    rank                    INTEGER,   -- 按占比降序名次
    source                  TEXT,
    calculated_at           TIMESTAMP,
    PRIMARY KEY (trade_date, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_feature_l2quant_date ON feature_l2_quant_orders_daily(trade_date);

CREATE TABLE IF NOT EXISTS ops_pipeline_run_daily (
    trade_date      DATE,
    pipeline        TEXT,
    step            TEXT,
    status          TEXT,
    row_count       INTEGER,
    input_count     INTEGER,   -- 候选输入数（如扫描名单股票数）
    processed_count INTEGER,   -- 成功处理数（含合法零结果个股）
    failed_count    INTEGER,   -- 兜底后仍失败数
    message         TEXT,
    source          TEXT,
    finished_at     TIMESTAMP,
    PRIMARY KEY (trade_date, pipeline, step)
);
ALTER TABLE ops_pipeline_run_daily ADD COLUMN IF NOT EXISTS input_count INTEGER;
ALTER TABLE ops_pipeline_run_daily ADD COLUMN IF NOT EXISTS processed_count INTEGER;
ALTER TABLE ops_pipeline_run_daily ADD COLUMN IF NOT EXISTS failed_count INTEGER;
CREATE INDEX IF NOT EXISTS idx_ops_pipeline_run_date
    ON ops_pipeline_run_daily(trade_date, pipeline);
