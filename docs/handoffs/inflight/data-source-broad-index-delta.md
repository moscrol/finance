# data-source/broad-index-delta · 宽基指数回补（两码已落库，北证50 上游无码）

**状态：回补已跑。** `000688.SH` / `000016.SH` 各 996 行至 2026-09-08。`899050.BJ` 上游不认，未入库。代码未提交。

## 目标

`fact_sector_kline_daily` 补科创50 / 上证50 / 北证50。规范在 PR #685：
`~/fwp-wt-knevo-verify` 的 `docs/superpowers/specs/2026-09-09-broad-index-coverage-delta.md`。

## 当前状态

- 树 `~/fwp-wt-broad-index` @ `data-source/broad-index-delta`（底 `f450f4bb`，从 `data-source/hithink-ingest` 开出）。
- 未提交：`sync_hithink_sector_kline.py`（`INDEX_CODES` + 未知码跳过 + dim 名 `COALESCE`）、`tests/test_hithink_sector_kline.py`（9 passed）。
- 生产库（须 `MARKET_FEATURE_STORE_DB` 指主树 `db/`，工作树没有自己的 duckdb）：
  - `000688.SH` 996 行，2022-08-02~2026-09-08，近 5 日 OHLC/volume 非空。
  - `000016.SH` 同上。
  - `899050.BJ`：**0 行**。`tickers/search` 只有 `.OF` 基金；`historical` 报 `Unknown thscode`（试过 `.BJ/.NQ/.TI/.SH/.SZ` 无后缀）。已从 `dim_sector_hithink` 删掉失败跑留下的空行。
- 工作树跑 CLI 必须带：
  `MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`

## 已验证

1. `--full --resume --skip-constituents --end-date 2026-09-08`：`kline 7/7 written_bars=3127 empty=0`，`constituent_rows=0`。
2. 闭环：Knevo「科创50 −5.53%」= **2026-07-10**（收 2064.98 / 前收 2185.83）。7 月另有 −7.70%（7/2）、−7.12%（7/17），不是记错月份。
3. 未知码若硬写进 `INDEX_CODES`，会在 flush 前把已拉的 K 线丢掉；现 `Unknown thscode` 当空跳过。

## 未做

- 未提交、未开/更 PR（本枝叠在未合的 `hithink-ingest` 上，合 main 需用户确认）。
- spec §5.3 混合源接缝（同花顺 × akshare 20 日 close）没跑。北证50 若要补，只能另走 akshare，不进这条同花顺清单。
- dim 里这两个新码 `sector_name` 仍是 NULL（`INDEX_CODES` 只给码）。

## 下一步

1. 用户确认后 pathspec 提交这两处代码改动。
2. 把「`899050.BJ` 上游无指数码」补进 PR #685 spec，避免下一任再写回去。
3. 回滚（只这两码）：
   `delete from fact_sector_kline_daily where sector_ts_code in ('000688.SH','000016.SH')`

## 踩过的坑

- 工作树默认 `DB_PATH` 是自己的 `db/`，不设 env 会新建空库，看起来像「写成功」。
- `INDEX_CODES` 带 `name=None` 做 upsert 会把已有指数名刷空；已改 `COALESCE`。失败那次已刷过一次，旧 6 码名若空是这次留下的。
