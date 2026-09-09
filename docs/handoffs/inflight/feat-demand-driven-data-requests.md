# feat/demand-driven-data-requests · 能力包 08「问题驱动补数」· 2026-09-09

树 `~/fwp-wt-demand-driven-data`，底 `gitea/main@5eb24515`，两个提交 `9809d10a` / `b8558688`（+ 本文与文档收尾一提交）。**未合 main、未切流、生产库未动。**
范围合同：`docs/superpowers/plans/2026-09-09-capability-upgrade/08-demand-driven-data-goal-brief.md`（在 `codex/docs-capability-upgrade-plan` 分支）；
进度 `…/progress/08.md`，范围外 `…/blocked/08.md`，收据 `docs/verification/2026-09-09-data-requests-08.md`。

## 做了什么（一句话）

`finance_query` 合法查询但窗口没数据时，此前只在给模型的 observation 里说一句、不留痕；现在留一条 `window_uncovered` 数据饥饿事件，
`services/data_requests` 把事件聚合成补数请求（合并 / 消费者 / 路线 / 优先级）、做覆盖检查（交易日历 × 关键值非空 × 历史日不许被实时源覆写）、
只在隔离库调现有 writer 补齐、补齐后沿 Workbench 原会话重问原问题，回执保证同 `data_version` 只恢复一次。

## 当前状态

| 项 | 状态 |
|---|---|
| 已实现 | ✅ `tool_hunger.record_window_uncovered`、`services/data_requests`（build/check/fill/resume/receipts）、`cli data-requests`、`research_queue` 兄弟件 `{date}-data-requests.json`、daily-agent 报告 `data_requests` 块 |
| 已进默认入口 | ✅ 接缝在生产装配的 `finance_query` runner（`episode_tools.build_episode_registry`）；`resume` 走 `POST /api/conversations/{id}/messages` |
| 真实验收 | ⏳ **被 LLM 网关阻塞**：14:51 429 冷却 → 15:22 网关重启后 `usage_limit_reached` / `no auth available`，本机无其他现有凭据。隔离实例 :8808 已起（本树、staging 库、隔离 users），runbook `~/.finance-runtime/data-requests-08/run_acceptance.sh all` 挂在后台等网关回 200 自动跑 |
| 生产生效 | ❌ 未合、未切流、未回补生产（按单只做隔离验收；生产 314 天回补归 #33 / daily-full 维护者） |

排练库（`rehearsal.duckdb`，生产库拷贝）上真 writer + 真 akshare 全链已实测：open → partial（`industry_1` 空，依赖 `sw_l1_daily` open）→
invalid（`sync_akshare_sw_l1_daily` 把当日实时快照写到 2024-06-28，31 行 `index_realtime_sw`）→ satisfied（19/19，关键字段 1.0，`data_version=4c71ef2190ca`）。
门禁：ruff 全绿；`intelligence/tests` 7464P/15S/1x（26 min）；pre-commit 11 道过（`unread-fields` 第一次拦下 5 个只写不读字段，已补 markdown 读取点）。

## 接手第一步

1. `tail -3 ~/.finance-runtime/data-requests-08/gateway-wait.log`：若已「gateway back … acceptance exit=0」，读 `~/.finance-runtime/data-requests-08/acceptance/`
   下 `baseline/*.json`（补前）与 `requests-resume-1.json`（补后 new_run_id）→ 把前后答案差量填进收据 §3；`requests-resume-2.json` 应 0 动作。
2. 若网关仍不可用：`python3 ~/.finance-runtime/data-requests-08/probe_gateway.py` 看状态；不要换模型、不要加 key；隔离实例 pid 见 `lsof -nP -iTCP:8808`。
3. 验收通过后再决定是否开 PR；合 main 等用户确认。

## 决策与被否方案

- 请求**不是**新台账：由各 run 的 `tool_hunger.jsonl` 事件随时重建（同 `intelligence.eval.tool_hunger` 聚合思路）；只登记了回执 `data_request_receipts.jsonl`（ledger-map 已加行）。
  否掉「另建请求队列文件」：会和 research-queue / kb-ingest-queue 并列成第三条写入链。
- 完成信号是**派生的**（从数据状态算），重放天然幂等；「只更新一次」靠回执键 `(request_id, data_version, consumer_run_id)`。
- `fill` 拒绝生产库路径；fupanhui 家族 / OPT-03 三项只显示真正缺什么（manual / pending_sync），不盲重试。
- 没改 `sync_akshare_sw_l1_daily`（writer 归 daily-full 维护者）：历史窗用 `mock.patch` 关实时步，`--no-historical-workaround` 可复现缺陷；已记 blocked B2。

## 踩过的坑

- 工作树没有 `.venv-workbench`，用主树解释器；`rg -E` 是 encoding 不是 regex，第一次全树 grep 因此静默为空。
- `unread-fields` 门禁：dataclass 字段只写不读会被拦，字符串字面量出现即算读；给渲染层补一处真实读取即可，不要进 ALLOWED。
- 从生产进程复制环境用 `ps eww` 解析 `KEY=` token，值不落盘不打印；8 个关键变量用 sha 校验一致。
- 生产判官二进制 `grok-1.0.5` 已不存在，隔离实例改指 `~/.grok/bin/grok`（1.0.24）。
