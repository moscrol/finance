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

如果不启动 CDP proxy，上述 7 个步骤会全部报错 `无法连接 CDP proxy`，但其余步骤（sync-index-daily、sync-sector-stocks、advancers-chart）不依赖 CDP，会正常完成。飞书 `sync-market-daily` 已退役。

## Core rules

- **Audit first**: Run `python3 skills/duckdb-backfill/scripts/audit_coverage.py` before writing.
- **Use short units**: Prefer one table, one quarter/month, or 5 trading days. Avoid long SQL heredocs and silent range jobs.
- **Stop silent hangs**: If a command has no output and CPU is 0 for about 2 minutes, terminate it and improve the skill/script instead of retrying blindly.
- **Prefer idempotent CLI commands**: Use existing `python3 -m market_feature_store.cli ...` commands before adding new data logic.
- **全A日线分两条路径**: 单日盘后增量用东财快照 `sync-stock-daily-snapshot`（数十秒，`daily-full`/`daily-update` 默认 `--stock-source snapshot`）；补历史多日区间仍用 mootdx `sync-stock-daily`（`--stock-source mootdx` 可强制）。详见 `references/backfill-runbook.md`「单日快照 vs 历史 mootdx」。
- **Separate facts from sparse tables**: `fact_limit_advance_presence` is the daily coverage table; `fact_limit_advance_daily` is sparse by design.
- **Record blockers**: Keep a list of skipped dates/sectors and explain why they were skipped.
- **入库后必接消费层**：新增/回填一张 `fact_*` 表后，**必须**判断要不要在 `intelligence/services/finance_query.py` 的 `_DATASETS` 注册成 dataset。**入库 ≠ agent 能查到**——agent 读 DuckDB 只走 `finance_query`，没注册的表它够不着（2026-08-13 实测：龙虎榜/核心股/龙头高度/外盘入库多轮但从未注册，agent 一直用不上）。详见下方「收尾对齐」。

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
# 席位表大窗口回补（~70 次 detail/日，断点续跑+撞锁退避+完整性修复，建议 spawn.py 守护）
python3 skills/duckdb-backfill/scripts/backfill_dragon_seats_full.py --start-date 2025-01-02 --end-date 2026-05-19
```

三条硬约束（都是实测事故换来的）：

- **外盘/核心股等主键 = 请求的 A 股日历日**，不能信接口回写的 `trade_date`（DESC 回补会互相覆盖，390 日只剩 258）。
- **龙头高度：请求日 as-of UPSERT，趋势图历史点只填洞**（同一天在当天图和事后图上龙头可不同）。
- **验收不能只数行数**：必须跑 QA 脚本对源头抽查（本仓有过「行数全对、值是空壳」的静默降级）。

恒定宇宙（core 每日 50 / global_index 每日 5 / global_stock 每日 194）已进 `check_daily` 的断档 + 行数收缩门禁；auction / events / mapping / regulation_event 天然稀疏，不进门禁，靠 ops `empty` 台账区分「接口没有」和「没同步」。

## 收尾对齐（每次入库/新表后逐条过，别漏）

一张 fact 表从「写进 DuckDB」到「agent 真能用」有三段，缺任一段都白做。落库后对着走：

1. **门禁**（数据别悄悄断/塌）：稳定每日有的表进 `market_feature_store/quality.py` 的 `GAP_TABLES`（断档）；宇宙规模恒定的再进 `ROW_ANOMALY_TABLES`（行数收缩）。**棘轮**：历史空的先回补齐再进门禁，否则天天误报。天然稀疏的表不进，靠 `ops_pipeline_run_daily` 的 `empty` 台账区分「源头没有」和「没同步」。
2. **消费层**（agent 够得着）：在 `intelligence/services/finance_query.py` 的 `_DATASETS` 注册成语义 dataset（`dimensions`/`metrics` 映射到真实列，列名对齐 `schema.sql`）。工具的 dataset/字段枚举从 `_DATASETS` 自动派生，注册即生效，无需改工具 schema。稀疏/半结构、低查询价值的可暂不注册以收敛工具面，但要在收尾里显式说明「暂不注册及原因」，不能默认漏。
3. **质检**（值对不对，不只是行数对）：跑对源头的抽查对账（参考 `scripts/qa_fupanhui_public_assets.py` 的结构门 + API 抽样两层），别只数 `COUNT(*)`。

写锁约束：DuckDB 单写者，线上 agent API 服务（`uvicorn intelligence.api.app`，端口 8792）在跑时会占写锁，批量回填得在其停止的写窗口进行，或走 `daily-full` 既有写窗口。

## 已知问题（2026-08-27 更新）

- **🔴 快照禁止补历史日（2026-08-27 取证的两起整分区覆盖事故）**：东财快照只反映「最近一个交易日」，`sync-stock-daily-snapshot` 对历史 `trade_date` 执行会把**当前快照值盖到所传日期上**，行数全对、覆盖率审计全绿。实锤两起：07-22 00:36 补写 2026-07-20（整分区变成 07-21 数据，5526/5526 行同值）；08-09 23:05 补写 2026-08-06（整分区变成 08-07 数据，例：立新能源真 08-06 跌停 -9.9% 被覆盖成 +7.96%）。`sync_eastmoney_stock_snapshot.py` docstring 写明了这一限制但没有闸门。**硬规则：补任何非当日的 stock-daily 一律走 mootdx；快照只允许当日盘后。** 检测与修复：`python3 skills/duckdb-backfill/scripts/repair_duplicated_stock_daily.py --scan`（只读，发现复制对退出码 1，可进门禁），修复流程见该脚本 docstring（mootdx 取真值 → 与 fact_sector_stock_daily 交叉验证 → `--apply` 单事务 upsert；截至 2026-08-27 两个分区待修，等四臂实验收尾 + 8792/8796 写窗口）。后续应在 `sync_eastmoney_stock_snapshot.py` 加 fail-closed 闸门（所传 trade_date ≠ 快照实际数据日即拒写，需另开分支改核心代码）。

- **sync-market-deviation tooltip 提取失败**：`sync-market-deviation` 通过 hover K 线图 tooltip 提取周均线/偏离度，偶发失败。Fallback：手动查询最近 5 个交易日上证收盘价，计算 MA5，然后直接 SQL 写入：
  ```sql
  UPDATE fact_market_daily SET sh_week_ma = <MA5>, sh_deviation_pct = <dev> WHERE trade_date = 'YYYY-MM-DD'
  ```
- **sync-stock-daily 东财快照 502**：东财 `push2.eastmoney.com` API 从 Mac 偏发性返回 502。通常重试可解，也可用 `--stock-source mootdx` 回退。
- **sync-sw-l1-daily SSL 错误**：swsresearch.com 的 SSL 连接偏发性失败，重试通常可解。

## Iteration rule

Whenever a backfill path hangs, returns misleading success, or needs manual rescue, update this skill or its scripts immediately before continuing large-scale backfill.
