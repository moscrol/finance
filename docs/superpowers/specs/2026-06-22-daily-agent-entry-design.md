# Daily Agent Entry Design

## 背景

金融仓已经有两类能力：

- 展示层：每日复盘 HTML、题材候选 HTML、策略组合工作台、知识库 dashboard。
- 问答层：`ask/chat/agent` 可以针对单个题材或问题调盘面、图谱、证据和 wiki。

缺口在每日开工入口：用户每天需要先知道“今天该看什么、哪些是旧逻辑唤醒、哪些只是数据缺口、哪些以后统一回补”。这不应该重做驾驶舱，也不应该自动回补知识库。

## 目标

新增 `python3 -m intelligence.cli agent-daily --date YYYY-MM-DD`。

它只读聚合：

1. `daily_ops_ledger` 的日常产物完整性。
2. 当日或近几日 `theme-candidates`。
3. `logic-match-batch` 的逻辑-盘面匹配结果。
4. 知识库 concept/entity/evidence/source trace 状态。

输出：

- `market_feature_store/exports/{date}-daily-agent.md`
- `market_feature_store/exports/{date}-daily-agent.json`

## 非目标

- 不做新的聊天 UI。
- 不自动执行 source/concept/IMA 回补。
- 不替代 `daily` 全量复盘 workflow。
- 不替代已有 strategy workbench 或知识库 dashboard。

## 决策口径

`agent-daily` 把候选分成四类：

- `old_logic_wakeup`：盘面与知识库已有逻辑、entity exposure、evidence 对齐。
- `new_logic_candidate`：有盘面信号，但知识库沉淀不足，适合先 `brief/front-map`。
- `data_gap`：影响判断的数据缺口，只进入统一回补等待队列。
- `noise_or_unconfirmed`：暂不处理，等待更多盘面或证据。

每条候选给出建议路径，例如 `front-map / deep-dive`、`brief / front-map`、`统一回补队列`。

## 边界

这是日常研究员总控入口，不是实时交易系统。所有结论来自本地已生成产物，市场数据新鲜度由上游 daily workflow 保证。
