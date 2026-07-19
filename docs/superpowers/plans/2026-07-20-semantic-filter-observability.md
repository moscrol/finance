# 语义过滤可观测性修复计划

- [x] 先修改语义闸门测试，证明成功过滤不应产生 warning。
- [x] 给 `ClosedLoopRetrievalResult` 增加 diagnostics，并纳入 inspector。
- [x] 将 `_apply_semantic_judge()` 的成功过滤记录迁移到 diagnostics。
- [x] 运行语义闸门、闭环检索、owner skill 和编排相关测试（117 passed）。
- [x] 运行全量 hermetic 测试（2101 passed，1 skipped）。
- [ ] 合并 main、部署不可变 runtime，重跑个股深挖与最终健康审计。
