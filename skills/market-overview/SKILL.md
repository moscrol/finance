---
name: market-overview
metadata:
  pattern: pipeline
  also: [tool-wrapper]
description: 每日市场复盘（fupanhui API → DuckDB）。触发词：帮我复盘、复盘、看一下今天的市场、市场总览、今日行情、市场数据、fupanhui。
---

# Market Overview

## 触发条件

用户要求复盘、查看市场总览、今日行情、市场数据，或提到 fupanhui.com 时触发。支持指定任意交易日（含历史日期）。

## Overview

通过 fupanhui.com 内部 REST API 获取 A 股市场数据，写入本地 DuckDB（`market_feature_store.duckdb`），输出结构化每日总结。

> **⚠ 飞书 Bitable 写入已废弃。** 复盘数据统一走 `daily-full` → DuckDB 路径。原 Steps 4（写飞书）和 Step 5（verify_and_patch）不再执行。

## 数据源

fupanhui.com 数据源说明（CDP proxy + `fetch_api` 取数代码、6 个 REST API 端点表、`market` API 关键字段映射）见 `references/data-source.md`。取数前加载该文件按端点和字段对照。

## Steps

### 当前流程（DuckDB 路径）

用户说「复盘」「全量复盘」时，执行 `duckdb-backfill` skill 的 `daily-full` 命令：

```bash
# 前置：确保 CDP proxy 已运行（见下文「CDP proxy」节）
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD
```

`daily-full` 会自动执行：sync-sectors → sync-market-overview → sync-index-daily → sync-sw-l1-daily → sync-market-deviation → sync-sector-daily → sync-sector-stocks → sync-limit-heat → sync-stock-high → sync-limit-advance → sync-stock-daily → **sync-mainline-daily** → **sync-theme-flow-daily** → advancers-chart → daily-review。飞书 `sync-market-daily` 已退役。

> 新增两步走**公开 API 直接 HTTPS**（`api_get_public()`），不需要 CDP proxy：
> - `sync-mainline-daily`：每日主线题材 + 龙头个股池 → `fact_mainline_theme_daily` / `fact_mainline_stock_daily`
> - `sync-theme-flow-daily`：题材级资金流向 → `fact_theme_flow_daily`

> **全A日线取数路径（stock-daily 这步）：日常单日复盘用默认的东财快照，不要带 `--stock-source mootdx`。**
> - `daily-full` 默认 `--stock-source snapshot`（东财全市场快照 `sync-stock-daily-snapshot`），单日盘后增量、几十秒完成。实测与 mootdx 对比：收盘价 100% 一致、成交额 100% 在 1% 内；除权日涨跌幅快照更准（用除权后昨收），且覆盖更全（含北交所 920xxx）。
> - `--stock-source mootdx`（通达信逐只 TCP，~50 分钟）**仅用于首次建库 / 多日历史回填**——快照只有当天单帧、无历史 K 线序列。日常增量用不上。
> - 注意：快照必须**盘后**跑（盘中会写实时价）；快照写入的 `source=eastmoney`、`pre_close` 为除权后昨收，与历史 mootdx 行口径略有差异。

执行后用 `audit_coverage.py` 验证覆盖。

### ~~收尾：导出当天增量 → iCloud~~（已废弃，2026-08-12 用户确认）

> ⛔ **iCloud 增量导出不再执行。** DuckDB 数据现在只在这一台电脑，双机同步的前提不存在了。
> `db_delta_export.py` / `db_delta_pull.py` 保留在 `scripts/`（将来再起第二台机器可复用），
> 但**复盘收尾不包含导出步骤**。复盘收尾 = daily-full 三道门通过 + `audit_coverage.py` 验证覆盖，到此为止。

### 旧流程（仅供参考，已废弃飞书写入部分）

原 7 步流程见 `references/steps.md`。其中 Step 4（写飞书）和 Step 5（verify_and_patch）已废弃，不再执行。

## CDP proxy

`daily-full` 中多个 sync 步骤依赖 CDP proxy（localhost:3456）。启动方法：

```bash
# Chrome 必须已启动且 DevToolsActivePort 存在（默认端口 9222）
node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs
```

CDP proxy 通过 Chrome DevTools Protocol 在用户已登录的 Chrome 中执行 XHR，自动携带 fupanhui session cookie。

**验证 CDP proxy 是否可用**：
```bash
curl -s http://localhost:3456/targets
```

如果 Chrome 未开启 remote debugging，检查 `~/Library/Application Support/Google/Chrome/DevToolsActivePort` 是否存在。

## 批量复盘多日

批量复盘多日的协同方式（子 agent 并行 API 抓取的 prompt 模板 + 主 agent 串行写飞书 + `check_coverage.py` 覆盖检查）见 `references/batch-review.md`。

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| 误触飞书写入流程 | 飞书写入已废弃，复盘数据统一走 `daily-full` → DuckDB |
| Copying AI summary verbatim | Condense to 2-3 key sentences |
| Adding personal market opinion | Report data, don't interpret beyond the reference ranges |
| Reading K-line tooltip before it renders | Wait 500ms after mousemove |
| Missing fields after write | 用 `audit_coverage.py` 检查 DuckDB 覆盖，逐表补 |
| Using DOM scraping for industry data | Use market API `.industry_spread` for reliable structured data |
| Assuming API field names | Check actual response keys first (`latest_date` not `trade_date`, `trade_date` not `date`) |
| Hover 位置偏左取到14:30蜡烛 | 用 `width * 0.97`（非0.9），提取后用上证日收交叉验证偏离符号 |

## 输入契约（给足→满分 / 缺料→降级）

| 你提供什么 | 输出质量 |
|---|---|
| 指定日期（交易日）+ 关注的题材/个股清单 | 满分：全景复盘 + 定向深看你关注的对象 |
| 只说"复盘"（默认最近交易日） | 标准：全景复盘，不定向深看 |
| 日期为非交易日/数据未出 | 降级：回退最近有数据的交易日并显式声明，不硬造当日数据 |
| API 部分接口失败 | 降级：能取的段照常输出，缺的段显式标「数据缺失」而非跳过 |
