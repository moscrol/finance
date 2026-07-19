# Market Watch 头部路由修复计划

- [x] 增加 Controller 回归测试，复现知识库别名把 market-watch 污染成题材 owner。
- [x] 增加识别边界测试，区分全市场观察和带明确题材主体的问题。
- [x] 在 `decide_turn()` 构造 `TurnIntent` 前规范化 market-watch resolution。
- [x] 让规范化字段从 `route_table.py` 的 canonical row 派生。
- [x] 运行 Controller、query-understanding、skill-router 相关测试（145 passed）。
- [x] 运行全量 hermetic 测试（2099 passed，1 skipped）。
- [ ] 合并 main、部署不可变 runtime，重跑市场观察与市场复盘端到端。
