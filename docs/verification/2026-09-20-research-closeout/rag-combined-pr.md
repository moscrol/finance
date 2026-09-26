切换受管知识库版本后，旧 RAG 热进程原先可能仍显示 ready，缺失绑定时还会回退旧 CLI。现在实例固定代际、双索引、代码与 venv 入口；状态读取只检查小型元数据，退役或失效立即显示不可用，查询/预热/恢复拒绝旧身份。保留独立 root 并存、legacy 路径和普通协议故障处理。

本候选包含 #789 的前端测试身份守卫与收尾证据归档：已审 RAG 1931b3a3 与 #789 62bbc4ec 正常合并为 e51c5157c9ea9aa86491c486663700e7d7696a6f，包含当前 main 4ace5ec2。独立 Spec/Quality 和最终合并增量双轴复核均通过，自动合并树及组件 blob 逐一一致。

固定候选完整检查：Python 11855 passed / 85 skipped / 2 xfailed；前端110 passed；E2E 34 passed / 2 skipped；Ruff、类型检查、构建与五项注册表检查全部通过。首尾 SHA 相同且工作树干净，严格收据 expect-revision=e51c5157、base-drift-max=0 通过。门禁与独立复核原件归档在协调 PR #799，外部证据目录为 research-closeout-20260920/gate-rag-retirement 和 rag-combined-review。

该 PR 尚未获准合 main；生产8792/索引/launchd未切换。旧两页 hash/BM25 真实换版回滚只绑定 d6812e62，不冒称本轮重跑或 BGE 大索引验收。合入本候选后 #789 可标明接替提交再关闭，当前保持开放。
