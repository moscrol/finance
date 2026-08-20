# 2026-08-20 Worktree 合入看板

已合 Gitea **#265** `gitea/main=b58a7a9b`。零件配对 harness-reference **#4**（#3 基线过期已关）。

## 8792

已切 `~/.finance-runtime/finance-workspace-b58a7a9b9f1a`（合入后现场建快照，11:13）。
回滚锚：`~/.finance-runtime/finance-workspace-be7c1e7eac81`（当时 HEAD `a97bfd57`）。
账本：`audit_deploy_ledger.py check` ok，`port=8792` 与 health rev 一致。

三读 health：`b58a7a9b9f1a` / `source_dirty=false` / `code_matches_repo=true` / `status=healthy`。
readiness：`status=ready`，13 checks，`missing_critical=[]`。

长电探针 `run_20260820_111625_486267`（90s，收据
`~/.finance-runtime/live-probe-traceability/20260820-b58a7a9b-changdian.json`）：
`run_status=completed`，`caliber=fact_stock_daily`×4 / `dataset=stock_daily`×12，
无「没有连接本地市场数据」，`secret_scan.hit_count=0`，`content_degraded_count=0`。
`degrade_count=1` 全是 `judge_status=unavailable`（Grok 判官暂态，W2 不计入内容质量；
`correlated_judge=false`）。未再打 1.3G gitea 包：11:14 已有 `~/backups/gitea-20260820-post264.tar.gz`。

## 看板本身

`python3 scripts/worktree_board.py`（`--this` 给 SessionStart）。看 `git cherry`，不看 ahead。
脚本不拆树。已拆 37 棵干净 leftover + 2 棵仅 venv 软链。脏 leftover / 生产快照未动。

未验证：frontend/e2e（diff 不含 webapp）；全量 5777P/16F 为 ceiling 夹具，本 PR 未改。
别的 worktree 要 rebase/合到这份 main，SessionStart 才会出现「合入:」行。

## 下一步

无必做。可选：认领后拆脏 leftover（`retire-feishu-im` / bookgap / tf-arm 等）。
勿手写合入状态进 `inflight/main.md`。
