# 在途交接：fix/daily-swap-lock-all-callers（已合入 main；生产修复已落并验收；302132 回填准备完成待审）

## 状态（2026-09-14 深夜）
- **gitea/main = 1fef3d27**（含换库契约修复 + hithink 重建 + 卡口脚本 + 证据，fast-forward 已推）。
- **生产库 09-11 修复已落**：run_id=1ef953440995；用户独立复核 24/24 **PASSED**（评审分支 315ff05f）。
- **302132 回填·准备阶段完成**（授权：只读审计+副本验证，未写生产）：交审文档 `docs/handoffs/2026-09-14-302132-backfill-prep.md`（缺口 53 行+06-23 空壳、字段映射、派生影响、副本验证 10/10 PASS、执行方案草案）。证据 `~/.finance-runtime/db-repair/hithink-20260911/backfill-prep-302132/prep-evidence.json`。复审合同 `docs/handoffs/2026-09-14-302132-prep-review.md`：数据准备通过、初版执行草案两条 P1 被挡。
- **执行实现已移交新分支 `fix/backfill-302132-scoped`**（worktree `/Users/a77/fwp-wt-backfill-302132`，从 main 1fef3d27 开出）：复审五项退修已全部修复、副本演练 13/13 PASS（tip efe2d28b + 文档），交审文档 `2026-09-14-302132-backfill-execution-design.md`。**后续 302132 工作去新分支，本分支不再动。**
- 等授权：事项 2 生产执行（先过执行实现代码评审）；事项 3 并跑表补齐（届时先交端点×日期×额外表清单）。

## 关键背景
- 302132=中航成飞（重组更名），并跑表有 2016+ 全历史；缺口 06-15..09-10 共 53 日。映射复用修复模块 DECIMAL 语义。
- **约束发现**：整日重算派生会改写他股（名称规范化+修订史漂移）→ 执行必须 scoped 写入（compute_features 需加按股过滤）。
- 生产库回滚备份 `db/market_feature_store.duckdb.bak-20260914T021947-1ef953440995` **保留勿删**；磁盘实际可用 ~8.5Gi（交接旧值 9.4 已过期），下次动工前重验。

## 门禁记录
候选期四叶全绿见 `docs/handoffs/2026-09-13-daily-swap-candidate-gate.md`（main 上有）。本轮准备阶段为只读+副本，无需门禁。

## 下一步（接管者只做授权内事项）
1. 事项 2 执行授权后：先审新分支执行实现（ef90ea7d），授权生产执行后从合入修订干净检出跑 `repair-backfill-302132 --parquet <冻结 parquet>`；基线若变先重跑副本演练。
2. 事项 3 授权后：先交端点×日期×额外表清单（个股日K增量无 end_date；板块日K重写重叠窗+目录；竞价/成分跳过终止态；稀疏表区分源空/同步失败；复权事件 ex_date 是事件日）。
