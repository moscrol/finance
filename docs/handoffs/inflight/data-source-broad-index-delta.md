# data-source/broad-index-delta · 宽基指数补三码（未开工，树已备好）

**状态：只建了树，一行代码没改，一次 API 没打。** 接手直接干。

## 目标

`fact_sector_kline_daily` 补 `000688.SH`(科创50) / `000016.SH`(上证50) / `899050.BJ`(北证50)，
三码现各 **0 行**。规范：`docs/superpowers/specs/2026-09-09-broad-index-coverage-delta.md`
（在 PR #685 分支 `docs/knevo-m-probes-verification`，本树没有，去 `~/fwp-wt-knevo-verify` 读）。

起因：核对 Knevo 断言「科创50 −5.53%」时本库无表可查，只能记「无法核」（E-008 §7.3）。

## 已查清的事实（别重查）

- 表**已建且已填**：814,305 行 / 854 码 / 2022-08-02~2026-09-08。#41 列的 6 个指数码全已回补，各 996 行。
  所以这单不是「建管线」，是**加常量 + 补跑**。
- 唯一改动点：`market_feature_store/sync/sync_hithink_sector_kline.py:27` 的 `INDEX_CODES` 元组。
  没有 `--codes` 参数，码写死在这里。
- CLI 不传 `db_path` → 写生产库 `db/market_feature_store.duckdb`，撞写锁时**抛错**不落 sidecar（已读 `cli.py:849`）。
  跑之前确认夜跑没在写。

## 命令（`--skip-constituents` 不可省）

```bash
market_feature_store.cli sync-hithink-sector-kline \
    --full --resume --skip-constituents --end-date 2026-09-08
```

`--resume` 只过滤 K 线的 `codes`；成分股那段的 `member_codes` 从**未过滤的** `catalog_rows`
重算（同文件 586-590 行），省掉旗标会多打 848 次成分接口 + 写 `fact_sector_constituent_hithink`
+ UPDATE `dim_sector_hithink`，全在本单范围外。

`--resume` 判据 `MAX(trade_date) >= end_day AND COUNT(*) >= 100`：854 码里 849 个被跳过，
5 个会重拉（`886112/886111/886110/883443.TI` 行数不足 100，`883401.TI` max=2026-09-03）。
前四个是新板块、行数天然到不了 100，**每次 resume 都重拉是判据固有行为，不是 bug**。
实际请求 ≈ 4 目录 + 8~15 K 线。

回滚：`delete from fact_sector_kline_daily where sector_ts_code in ('000688.SH','000016.SH','899050.BJ')`。

## 验收（spec §5）

1. 三码各 `count(*) > 0` 且 `max(trade_date)` = 最近交易日。
2. 非空壳：三码各抽 5 日，`open/high/low/close/volume` 非 NULL。
3. 闭环：重核「科创50 −5.53%」——给出对应交易日，或判定 2026-07 全月不成立。

## 边界

- key 只从钥匙串 `hithink-finance / a77-api-key` 或 `HITHINK_FINANCE_API_KEY` 取，**不进代码/日志/收据/对话**。
- 限流 ≤5 QPS，不并发。窗口必须 <1500 天（超了上游静默返空，不报错）。
- 本分支从 `data-source/hithink-ingest`(5fb33d46, 领先 main 3 提交未合) 开出，**PR 叠在它上面**，
  用户明确要求「不动他的分支」。合并 main 需用户确认。
