# Market Validation Design

## Goal

P3 第一版把已有 `theme-candidates` 盘面字段转成可读的 L4 盘面验证摘要，让 `agent-daily` 能解释“这条逻辑今天是不是被市场重新定价”。

## Scope

本版不依赖另一台 Mac 的 DuckDB，也不计算 CAR。只读取已经生成并提交/同步的 `market_feature_store/exports/*-theme-candidates.json`。

使用字段：

- `priority_score`
- `trigger_types`
- `score_detail`
- `market_evidence.sector_metrics`
- `market_evidence.limit_heat`
- `market_evidence.new_high_direction`
- `market_evidence.strong_stocks`
- 最近历史同题材候选，用于计算 priority、涨停、新高、强势股变化。

## Output

每条非占位逻辑新增 `market_validation`：

- `盘面验证强度`：强验证 / 中等验证 / 弱验证 / 无盘面验证
- `验证结论`：一句人话
- `当前盘面`
- `边际变化`
- `关键触发`
- `强势股`
- `下一步`

## Rules

- 强验证：priority 高、触发类型多、涨停/新高扩散明显，或容量前三 + 多信号共振。
- 中等验证：有明确盘面信号，但扩散度或持续性还不够。
- 弱验证：只有单一信号或强势股很少。
- 无盘面验证：没有候选或属于占位/噪音。

P3 只描述市场是否验证，不决定是否做 IMA。研究动作仍由 P2 `research_queue` 结合证据层判断。

## Testing

新增 `tests/test_market_validation.py` 覆盖强验证、中等验证、弱验证、历史边际变化；更新 `tests/test_daily_agent.py`，确认 JSON/Markdown/HTML 都显示“盘面验证”。
