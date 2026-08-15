# 2026-08-16 S7 挂夜跑 staging，不切 8792

roadmap_ref: L1-S7

00:10 裁决：含 S7 的 main tip **不要**用来切 8792。S7 不在
`intelligence/`，`deploy_workbench_runtime.sh` 只 rsync 那棵树；夜跑写库
走的是 `run_review_sync.py` 的 `sync-*`，从不调用 `daily-full`。切 8792
带不上写锁消除，还会把已合的 R-24（#49）叠上 episode 路径。

## 实际切的是哪条路

- 18:30 LaunchAgent `com.financeworkspace.daily-full-review-sync` 改跑
  `~/.local/bin/nightly-full-review-s7.sh`。
- 包装脚本 `~/.local/bin/nightly-review-sync-staged.py`：用干净树
  `~/.finance-runtime/finance-s7-sync` @ `360950e0` 的 S7 `db.py` 做
  clone / 守卫 / `os.replace`；子进程仍跑
  `finance-workspace-private` 上的 `run_review_sync.py`（保留未提交的
  主线 `mode=static` 回退和 public-assets 步）。
- 写锁只落在 `market_feature_store.duckdb.staging`。子进程非 0 不换名。
- 20:40 finalize、8792（`fdb23114`，healthy）未动。
- 旧 plist 备份：
  `~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist.bak-pre-s7-*`

## 验收（本机已做）

- S7 夹具 `tests/test_market_feature_store_staging_swap.py` 12 passed。
- 生产库只读探针：无活跃写者，50 表，`fact_market_daily` 覆盖到 2026-08-14。
- 周末入口 `nightly-full-review-s7.sh 2026-08-16` 直接跳过。
- 真同步窗口：下个交易日 18:30。回滚：把 plist 脚本路径改回
  `skills/daily-full-review/scripts/nightly_full_review.sh` 再 bootstrap。
