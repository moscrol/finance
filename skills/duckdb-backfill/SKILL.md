---
name: duckdb-backfill
metadata:
  pattern: tool-wrapper
  also: [pipeline]
description: DuckDB market_feature_store full/backfill workflow for the finance workspace. Use when the user asks to 回补 duckdb、全量回补、补缺口、补 market_feature_store 数据、修复 fact_* 覆盖、同步 stock_high/sector_stock/limit_heat/limit_advance/sw_l1, or when a sync command hangs and the workflow needs short-command retries, coverage audits, timeout handling, and iterative skill optimization.
---

# DuckDB Backfill

## Overview

Use this skill to backfill `/Users/lbq/Desktop/c c/金融/db/market_feature_store.duckdb` safely and incrementally. Prefer small observable commands, read-only audits first, and script improvements whenever a sync path hangs or becomes fragile.

## Mandatory start

Run and report:

```bash
git status --short
git branch --show-current
```

Do not stage DB files or generated exports. DuckDB writes are local state changes; keep source edits separate from data sync.

## CDP proxy 前置

`daily-full` 中的多个 sync 步骤（sync-sectors、sync-market-overview、sync-market-deviation、sync-sector-daily、sync-limit-heat、sync-stock-high、sync-limit-advance）依赖 CDP proxy（localhost:3456）。运行 `daily-full` 前必须确保 CDP proxy 已启动：

```bash
# 检查 Chrome DevToolsActivePort 是否存在（必须已启动 Chrome）
cat ~/Library/Application\ Support/Google/Chrome/DevToolsActivePort
# 启动 CDP proxy
node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs
# 验证
curl -s http://localhost:3456/targets
```

如果不启动 CDP proxy，上述 7 个步骤会全部报错 `无法连接 CDP proxy`，但其余步骤（sync-market-daily、sync-index-daily、sync-sector-stocks、sync-sector-resonance、advancers-chart）不依赖 CDP，会正常完成。

## Core rules

- **Audit first**: Run `python3 skills/duckdb-backfill/scripts/audit_coverage.py` before writing.
- **Use short units**: Prefer one table, one quarter/month, or 5 trading days. Avoid long SQL heredocs and silent range jobs.
- **Stop silent hangs**: If a command has no output and CPU is 0 for about 2 minutes, terminate it and improve the skill/script instead of retrying blindly.
- **Prefer idempotent CLI commands**: Use existing `python3 -m market_feature_store.cli ...` commands before adding new data logic.
- **全A日线分两条路径**: 单日盘后增量用东财快照 `sync-stock-daily-snapshot`（数十秒，`daily-full`/`daily-update` 默认 `--stock-source snapshot`）；补历史多日区间仍用 mootdx `sync-stock-daily`（`--stock-source mootdx` 可强制）。详见 `references/backfill-runbook.md`「单日快照 vs 历史 mootdx」。
- **Separate facts from sparse tables**: `fact_limit_advance_presence` is the daily coverage table; `fact_limit_advance_daily` is sparse by design.
- **Record blockers**: Keep a list of skipped dates/sectors and explain why they were skipped.

## Backfill runbook（顺序 / 常用命令 / 已知覆盖状态）

回补 runbook（按表顺序：日历/基础 fact → 轻表 → stock_high 中表 → limit_heat/sector_stock 重表；常用 CLI 命令清单；以及 2026-06-15 起的已知覆盖状态、卡死/超时/CDP 500 日期与 skip 文件）见 `references/backfill-runbook.md`。回补前加载，按顺序小批执行。

## 已知问题（2026-06-20 更新）

- **sync-market-deviation tooltip 提取失败**：`sync-market-deviation` 通过 hover K 线图 tooltip 提取周均线/偏离度，偶发失败。Fallback：手动查询最近 5 个交易日上证收盘价，计算 MA5，然后直接 SQL 写入：
  ```sql
  UPDATE fact_market_daily SET sh_week_ma = <MA5>, sh_deviation_pct = <dev> WHERE trade_date = 'YYYY-MM-DD'
  ```
- **sync-stock-daily 东财快照 502**：东财 `push2.eastmoney.com` API 从 Mac 偏发性返回 502。通常重试可解，也可用 `--stock-source mootdx` 回退。
- **sync-sw-l1-daily SSL 错误**：swsresearch.com 的 SSL 连接偏发性失败，重试通常可解。

## Iteration rule

Whenever a backfill path hangs, returns misleading success, or needs manual rescue, update this skill or its scripts immediately before continuing large-scale backfill.
