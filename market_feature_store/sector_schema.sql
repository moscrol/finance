-- 板块宇宙 (sector universe) 代际存储 schema
-- 设计文档: docs/superpowers/specs/2026-07-29-daily-sector-universe-root-repair-design.md
--
-- 本文件只由 market_feature_store/sector_universe.py 加载, 是唯一定义物理代际表
-- 的地方 (DDL-only, 不含任何读写逻辑)。
--
-- 分层约定:
--   ops_sector_universe_snapshot_daily  每日快照表头 (candidate/published/superseded/rejected)
--   fact_sector_universe_daily          快照内每个板块的声明成员数 (精确分母)
--   ops_sector_member_sync_daily        每个板块成员抓取的持久化回执
--   fact_sector_daily_generation        板块日行情, 绑定快照代际 (物理表, 私有)
--   fact_sector_stock_daily_generation  板块成员日行情, 绑定快照代际 (物理表, 私有)
--   fact_sector_daily / fact_sector_stock_daily
--       对外唯一公开读口 (VIEW): 有 published 表头的交易日只暴露该代际;
--       没有表头的历史交易日只暴露 legacy 迁移行。读者因此不会跨代际混池。
--
-- 'legacy' 是迁移保留的哨兵代际, 永远不会出现 published 表头。

CREATE TABLE IF NOT EXISTS ops_sector_universe_snapshot_daily (
    trade_date                  DATE NOT NULL,
    snapshot_id                 TEXT NOT NULL,
    provider_source             TEXT NOT NULL,
    sector_count                INTEGER NOT NULL,
    declared_relationship_count BIGINT NOT NULL,
    status                      TEXT NOT NULL
        CHECK (status IN ('candidate','published','superseded','rejected')),
    captured_at                 TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (trade_date, snapshot_id)
);
CREATE INDEX IF NOT EXISTS idx_ops_sector_universe_snapshot_status
    ON ops_sector_universe_snapshot_daily(trade_date, status);

CREATE TABLE IF NOT EXISTS fact_sector_universe_daily (
    trade_date           DATE NOT NULL,
    snapshot_id          TEXT NOT NULL,
    sector_ts_code       TEXT NOT NULL,
    sector_name          TEXT NOT NULL,
    expected_stock_count INTEGER NOT NULL,
    provider_source      TEXT NOT NULL,
    captured_at          TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (trade_date, snapshot_id, sector_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_universe_snapshot
    ON fact_sector_universe_daily(snapshot_id);

CREATE TABLE IF NOT EXISTS ops_sector_member_sync_daily (
    trade_date           DATE NOT NULL,
    snapshot_id          TEXT NOT NULL,
    sector_ts_code       TEXT NOT NULL,
    status               TEXT NOT NULL
        CHECK (status IN ('pending','success','empty','error')),
    expected_stock_count INTEGER NOT NULL,
    actual_stock_count   INTEGER,
    attempt_count        INTEGER NOT NULL DEFAULT 0,
    last_error_code      TEXT,
    first_attempted_at   TIMESTAMPTZ,
    last_attempted_at    TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ,
    PRIMARY KEY (trade_date, snapshot_id, sector_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_ops_sector_member_sync_status
    ON ops_sector_member_sync_daily(snapshot_id, status);

CREATE TABLE IF NOT EXISTS fact_sector_daily_generation (
    trade_date                  DATE,
    sector_universe_snapshot_id TEXT NOT NULL,
    sector_ts_code              TEXT,
    sector_name                 TEXT,
    sw_l1                       TEXT,
    pct_chg                     DOUBLE,
    amount                      DOUBLE,
    diff_ratio                  DOUBLE,
    strength                    DOUBLE,
    multi_period_resonance      BOOLEAN,
    multi_period_source         TEXT,
    multi_period_updated_at     TIMESTAMP,
    source                      TEXT,
    updated_at                  TIMESTAMP,
    PRIMARY KEY (trade_date, sector_universe_snapshot_id, sector_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_generation_date
    ON fact_sector_daily_generation(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_generation_sector
    ON fact_sector_daily_generation(sector_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_sector_daily_generation_snapshot
    ON fact_sector_daily_generation(sector_universe_snapshot_id);

CREATE TABLE IF NOT EXISTS fact_sector_stock_daily_generation (
    trade_date                  DATE,
    sector_universe_snapshot_id TEXT NOT NULL,
    sector_ts_code              TEXT,
    sector_name                 TEXT,
    sw_l1                       TEXT,
    stock_ts_code               TEXT,
    stock_name                  TEXT,
    price                       DOUBLE,
    pct_chg                     DOUBLE,
    amount                      DOUBLE,
    pct_chg_3d                  DOUBLE,
    pct_chg_5d                  DOUBLE,
    pct_chg_10d                 DOUBLE,
    pct_chg_20d                 DOUBLE,
    high_status                 TEXT,
    high_status_label           TEXT,
    limit_times                 INTEGER,
    fund_flow_1d                DOUBLE,
    fund_flow_5d                DOUBLE,
    sw_industry                 TEXT,
    leader_plate                TEXT,
    leader_sub_plate            TEXT,
    role_tags_json              TEXT,
    circ_mv                     DOUBLE,
    float_mcap_yi               DOUBLE,
    total_mcap_yi               DOUBLE,
    free_float_mcap_yi          DOUBLE,
    mcap_source                 TEXT,
    source                      TEXT,
    updated_at                  TIMESTAMP,
    PRIMARY KEY (trade_date, sector_universe_snapshot_id, sector_ts_code, stock_ts_code)
);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_generation_date
    ON fact_sector_stock_daily_generation(trade_date);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_generation_stock
    ON fact_sector_stock_daily_generation(stock_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_generation_sector
    ON fact_sector_stock_daily_generation(sector_ts_code);
CREATE INDEX IF NOT EXISTS idx_fact_sector_stock_generation_snapshot
    ON fact_sector_stock_daily_generation(sector_universe_snapshot_id);

-- 公开读口: 保留历史事实表名, 语义升级为"单一已发布代际"。
-- 列序沿用迁移前的物理列序, 代际列追加在末尾, 以免打断按位置读取的旧调用方。
CREATE OR REPLACE VIEW fact_sector_daily AS
SELECT
    g.trade_date,
    g.sector_ts_code,
    g.sector_name,
    g.sw_l1,
    g.pct_chg,
    g.amount,
    g.diff_ratio,
    g.strength,
    g.multi_period_resonance,
    g.multi_period_source,
    g.multi_period_updated_at,
    g.source,
    g.updated_at,
    g.sector_universe_snapshot_id
FROM fact_sector_daily_generation AS g
WHERE EXISTS (
    SELECT 1
    FROM ops_sector_universe_snapshot_daily AS h
    WHERE h.trade_date = g.trade_date
      AND h.snapshot_id = g.sector_universe_snapshot_id
      AND h.status = 'published'
)
   OR (
    g.sector_universe_snapshot_id = 'legacy'
    AND NOT EXISTS (
        SELECT 1
        FROM ops_sector_universe_snapshot_daily AS h
        WHERE h.trade_date = g.trade_date
          AND h.status = 'published'
    )
);

CREATE OR REPLACE VIEW fact_sector_stock_daily AS
SELECT
    g.trade_date,
    g.sector_ts_code,
    g.sector_name,
    g.sw_l1,
    g.stock_ts_code,
    g.stock_name,
    g.price,
    g.pct_chg,
    g.amount,
    g.pct_chg_3d,
    g.pct_chg_5d,
    g.pct_chg_10d,
    g.pct_chg_20d,
    g.high_status,
    g.high_status_label,
    g.limit_times,
    g.fund_flow_1d,
    g.fund_flow_5d,
    g.sw_industry,
    g.leader_plate,
    g.leader_sub_plate,
    g.role_tags_json,
    g.circ_mv,
    g.float_mcap_yi,
    g.total_mcap_yi,
    g.free_float_mcap_yi,
    g.mcap_source,
    g.source,
    g.updated_at,
    g.sector_universe_snapshot_id
FROM fact_sector_stock_daily_generation AS g
WHERE EXISTS (
    SELECT 1
    FROM ops_sector_universe_snapshot_daily AS h
    WHERE h.trade_date = g.trade_date
      AND h.snapshot_id = g.sector_universe_snapshot_id
      AND h.status = 'published'
)
   OR (
    g.sector_universe_snapshot_id = 'legacy'
    AND NOT EXISTS (
        SELECT 1
        FROM ops_sector_universe_snapshot_daily AS h
        WHERE h.trade_date = g.trade_date
          AND h.status = 'published'
    )
);
