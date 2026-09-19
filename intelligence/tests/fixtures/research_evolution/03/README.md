# 03 · 夹具（全部 synthetic）

这里的每一份文件都是**工程验收夹具**，只用来证明合同、幂等、结算、评分与曝光判定的代码路径；
不含任何真实市场事实。由它们生成的收据一律带 `tags: ["synthetic"]` / `synthetic: true`，
不得用于声明方法有效、用户效果或付费状态。

| 文件 | 用途 |
|---|---|
| `forward_protocol_synthetic.json` | forward 协议输入体的静态部分；日历与前向窗口由测试按工作日生成后填入 |
| `ablation_draft_synthetic.json` | 规则二桶消融草稿（base / full / minus_track 三臂）；`FILL` 字段由测试按旁路库日历改写，基准与版本由 runner 填 |
| `replay_records_synthetic.jsonl` | 历史 LLM 演练适配器输入；含一条非法概率与一条未知臂，用来验证跳过而非静默修补 |

旁路库（`history_labels.duckdb` 形状）在测试里用 `methodology_backtest.store.open_labels_db` 现场生成，不落在仓里。
