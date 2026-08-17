# 死资产接通 live 三问（#152 sidecar，不碰 8792）

日期：2026-08-18
代码：`/Users/a77/fwp-wt-dead-assets` @ `60a4e339`（Gitea **#175**）
探针：`scripts/live_probe.py ask` → sidecar `:8796`，`WORKBENCH_GROUNDED_PRESENTER=0`
入口：`POST /api/runs`（`task_type=ask`，`compose=true`）→ `ask_retrieve_compose`
结论：**够得着已由语义层测试证明；这三发 live 都没调 `finance_query`，属「想得到用」缺口，本单不硬修。**

## 三发

| 题 | slug / run | question_type | 实际走的源 | 目标 dataset | finance_query |
|---|---|---|---|---|---|
| 今天竞价哪些昨日涨停在抢筹 | `dead-assets-auction` `run_20260818_022205_913700` 49.4s | `market_forecast` | M1 市场总览 + D4 主线 | `auction_stock_daily` | **0** |
| 最近有哪些算力/AI 方向的研报 | `dead-assets-catalog` `run_20260818_022340_911815` 176.6s | `theme_analysis` | wiki/R 证据链（4–6 月卖方合集） | `research_report_catalog` | **0** |
| 近期有什么值得盯的事件催化 | `dead-assets-event` `run_20260818_022850_412229` 165.2s | `general_finance_qa` | wiki 商业航天 7 月发射窗口 | `event_daily` | **0** |

三发 `trace.jsonl` / `llm_context.json` 均无 `finance_query`、无四个新 dataset 名。sidecar 已停。8792 未动。

## 现象（一手）

1. **竞价**：模型写「本轮证据里没有个股集合竞价…明确缺口」。库里 `fact_auction_stock_daily` 有到 08-14 的 `panel_key=zt`（蓝盾光电等）。问句被路由成 `market_forecast`，只吃盘面总览。
2. **研报**：答的是 4–6 月 wiki 卖方合集；目录表最新是 08-13「腾讯 Q2 算力租赁…」。路由 `theme_analysis` → graph/wiki/R，不进语义层。
3. **催化**：答 7 月商业航天发射窗口（已过期）；`fact_event_daily` 有 13 条 `is_future=true`（最新 08-17 固态电池大会等）。路由 `general_finance_qa` → wiki。

## 裁决边界

执行单原文：若 agent 没调工具，把现象记进验收报告，那是工具描述/prompt 引导问题，**另行裁决，本单不硬修**。

本单只证明：注册后 `FinanceQuery.run` + 参数面 enum 绿（够得着）。想得到用要另开单：ask 车道是否要把这四张表编进 `ask_retrieve_compose` 的 D 块，或让这三类题走进 episode `finance_query`。

## 路径

- 收据：`~/.finance-runtime/live-probe-traceability/dead-assets-{auction,catalog,event}.json`
- run 目录：`~/.finance-runtime/live-probe-traceability/users/live-probe/runs/run_20260818_022{205_913700,340_911815,850_412229}`
- pytest：`~/.finance-runtime/test-receipts/20260817T181939Z-ac6c43cd.json`（5387 passed / 12 skipped）
