---
name: duckdb-backfill
disable-model-invocation: true
metadata:
  pattern: tool-wrapper
  also: [pipeline]
description: "DuckDB market_feature_store 回补。用户说「回补 duckdb」「全量回补」「补缺口」「修 fact_* 覆盖」或 sync 挂起需短命令重试时用。按覆盖审计与超时兜底跑。不改策略、不改 vault。"
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

如果不启动 CDP proxy，上述 7 个步骤会全部报错 `无法连接 CDP proxy`，但其余步骤（sync-market-daily、sync-index-daily、sync-sector-stocks、advancers-chart）不依赖 CDP，会正常完成。

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

## 复盘会公开资产（2026-08-13 起）

十类公开 API 资产（keywords/相似日/龙头高度/外盘/龙虎榜/监管/核心个股/竞价/事件/研报目录/题材挖掘）已进 `daily-full` 一步 `sync-fupanhui-public-assets`，无需 CDP。回补与质检：

```bash
# 按其它日表窗口回补缺口（跳过已有行；空结果记 ops 不死循环）
python3 -m market_feature_store.cli sync-fupanhui-public-assets --align --sleep 0.2
# 定点重刷单个子任务（如龙头 as-of）
python3 -m market_feature_store.cli sync-fupanhui-public-assets --align --only leader_height --refresh
# 质检：结构门（全窗口）+ 公开 API 抽查对账，只读
python3 skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py
QA_SAMPLE=2026-07-01,2025-06-03 python3 skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py
```

三条硬约束（都是实测事故换来的）：

- **外盘/核心股等主键 = 请求的 A 股日历日**，不能信接口回写的 `trade_date`（DESC 回补会互相覆盖，390 日只剩 258）。
- **龙头高度：请求日 as-of UPSERT，趋势图历史点只填洞**（同一天在当天图和事后图上龙头可不同）。
- **验收不能只数行数**：必须跑 QA 脚本对源头抽查（本仓有过「行数全对、值是空壳」的静默降级）。

恒定宇宙（core 每日 50 / global_index 每日 5 / global_stock 每日 194）已进 `check_daily` 的断档 + 行数收缩门禁；auction / events / mapping / regulation_event 天然稀疏，不进门禁，靠 ops `empty` 台账区分「接口没有」和「没同步」。

## 已知问题（2026-06-20 更新）

- **sync-market-deviation tooltip 提取失败**：`sync-market-deviation` 通过 hover K 线图 tooltip 提取周均线/偏离度，偶发失败。Fallback：手动查询最近 5 个交易日上证收盘价，计算 MA5，然后直接 SQL 写入：
  ```sql
  UPDATE fact_market_daily SET sh_week_ma = <MA5>, sh_deviation_pct = <dev> WHERE trade_date = 'YYYY-MM-DD'
  ```
- **sync-stock-daily 东财快照 502**：东财 `push2.eastmoney.com` API 从 Mac 偏发性返回 502。通常重试可解，也可用 `--stock-source mootdx` 回退。
- **sync-sw-l1-daily SSL 错误**：swsresearch.com 的 SSL 连接偏发性失败，重试通常可解。

## Iteration rule

Whenever a backfill path hangs, returns misleading success, or needs manual rescue, update this skill or its scripts immediately before continuing large-scale backfill.
