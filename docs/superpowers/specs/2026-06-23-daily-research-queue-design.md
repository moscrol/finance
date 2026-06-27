# Daily Research Queue Design

## Goal

把 `agent-daily` 从“显示证据和生命周期”升级为“告诉人今天要做什么”。P2 不新增自动回补动作，只把已有的证据裁判、生命周期、向量旧材料和数据缺口翻译成可读的研究任务队列。

## Scope

本版只做四类研究动作：

- `今日该做 IMA`：盘面或旧逻辑触发，但 L1/L2 叙事和基线材料不足，需要先补题材地图或 deep-dive。
- `今日该找公告/调研/订单`：已有 L2 或 L3 候选，但缺 L3 官方验证，需要找公告、互动易、调研、订单、客户验证。
- `今日等盘面验证`：L2/L3 较完整，但 L4 盘面验证不足，先观察市场是否重新定价。
- `今日降级/观察`：生命周期转弱、证伪、分歧加大，除非新增 L3 或盘面重新扩散，否则不追加研究投入。

数据缺口和占位信号不强行进入研究队列；它们继续留在回补队列或待确认区域，避免把污染词、别名、连板占位误判成 IMA 任务。

## Architecture

新增 `intelligence/services/research_queue.py`，负责把一条 daily decision row 归入研究任务队列。`daily_agent.py` 只负责调用、保存到 `report["research_queue"]`，并在 Markdown/HTML 渲染。

输入来自已有字段：

- `research_judgment.证据状态`
- `research_judgment.已有证据层`
- `research_judgment.缺失证据层`
- `logic_lifecycle.生命周期阶段`
- `semantic_hits`
- `data_gaps`
- `priority_score`
- `strong_stocks`

## Rules

第一版使用保守规则：

- 有 `missing_concept`、`missing_entity_exposure`、`missing_evidence`、`missing_source_trace` 的条目不进研究队列，由原回补队列处理。
- `新出现` 或 `旧逻辑唤醒` 且缺 L1/L2，进入 `今日该做 IMA`。
- `能力栈候选`、`重点验证`、`旧逻辑待验证` 且缺 L3 官方验证，进入 `今日该找公告/调研/订单`。
- 已有 L2 和 L3，但缺 L4，进入 `今日等盘面验证`。
- `高位分歧`、`衰退观察`、`证伪退出`，进入 `今日降级/观察`。

## Output

`report["research_queue"]` 结构：

```json
{
  "today_do_ima": [],
  "today_find_official_evidence": [],
  "today_wait_market_validation": [],
  "today_downgrade_or_watch": [],
  "summary": {}
}
```

每个 item 至少包含 `目标`、`动作`、`理由`、`优先级`、`生命周期阶段`、`证据状态`、`缺失证据层`、`强势股`。

## Testing

新增 `tests/test_research_queue.py` 覆盖四类动作和数据缺口跳过；更新 `tests/test_daily_agent.py`，确认 JSON、Markdown、HTML 都展示“今日研究任务队列”。
