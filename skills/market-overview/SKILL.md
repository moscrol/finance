---
name: market-overview
description: 每日市场复盘（fupanhui API+飞书入库）。触发词：帮我复盘、复盘、看一下今天的市场、市场总览、今日行情、市场数据、fupanhui。
---

# Market Overview

## 触发条件

用户要求复盘、查看市场总览、今日行情、市场数据，或提到 fupanhui.com 时触发。支持指定任意交易日（含历史日期）。

## Overview

通过 fupanhui.com 内部 REST API 获取 A 股市场数据，输出结构化每日总结，并写入飞书 Bitable。

## 数据源

fupanhui.com 数据源说明（CDP proxy + `fetch_api` 取数代码、6 个 REST API 端点表、`market` API 关键字段映射）见 `references/data-source.md`。取数前加载该文件按端点和字段对照。

## Steps

单日复盘 7 步流程（取数 → hover K 线提取周均线/偏离度并交叉验证 → 格式化总览输出模板与量能/集中度区间 → 写飞书查重 → verify_and_patch → 清理 tab → 同步涨家数）见 `references/steps.md`，逐步执行。

## 批量复盘多日

批量复盘多日的协同方式（子 agent 并行 API 抓取的 prompt 模板 + 主 agent 串行写飞书 + `check_coverage.py` 覆盖检查）见 `references/batch-review.md`。

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Writing Feishu records without checking duplicates | Always query by date first, skip if exists |
| Copying AI summary verbatim | Condense to 2-3 key sentences |
| Adding personal market opinion | Report data, don't interpret beyond the reference ranges |
| Reading K-line tooltip before it renders | Wait 500ms after mousemove |
| Missing fields after write | Run verify_and_patch.py |
| Using DOM scraping for industry data | Use market API `.industry_spread` for reliable structured data |
| Assuming API field names | Check actual response keys first (`latest_date` not `trade_date`, `trade_date` not `date`) |
| Hover 位置偏左取到14:30蜡烛 | 用 `width * 0.97`（非0.9），提取后用上证日收交叉验证偏离符号 |
