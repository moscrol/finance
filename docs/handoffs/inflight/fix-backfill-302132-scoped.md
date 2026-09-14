# 在途交接：fix/backfill-302132-scoped（302132 历史回填执行实现，第二轮交审）

## 状态（2026-09-14 中午）
- **第二轮修复完成并重演练**：QC 复审（6abd08ac，2 P1 + 3 P2，7 条误放行复现）已全部修复——tip `efe2d28b`（代码）+ 文档提交。交审文档 `docs/handoffs/2026-09-14-302132-backfill-execution-design.md`（含逐项修复对照表）。
- 单测 19/19（7 条误放行探针翻转为必须拒绝 + 2 条收据守卫）；全量 pytest **9,636 passed / 0 failed / 77 skipped**（收据 20260914T035247Z-efe2d28b.json，dirty=false）；ruff 全仓过。
- 全新副本演练 ×2（真实父流程）：apply run_id=dc6d8a7a174f、verify run_id=de751020ba23；**每轮不可覆盖收据**（backfill-report/execution 按 run_id 命名，绑定 revision/dirty/备份身份）。外部验收 v2 **13/13 PASS**（`~/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/dryrun-acceptance-v2.json`）。
- **未写生产**。生产授权需另行申请（前提清单见交审文档末节）。

## 关键背景
- 合同源：准备复审 `docs/handoffs/2026-09-14-302132-prep-review.md`；执行复审 `docs/handoffs/2026-09-14-302132-execution-review.md`（QC 分支 docs/qc-backfill-302132-1b936486）。
- 修复要点：源日期集合与市场历逐日相等（LAG 前驱身份）；验收分母=spec 键集+全字段 oracle+标签守恒；保留 10 行全列含 updated_at 指纹；window 黄金三元组；`_guarded_write_json` O_EXCL+别名隔离。
- 磁盘 ~8Gi；备份不删；演练目录保留 fake-prod.duckdb（第二轮产物）+ 证据 JSON + 日志。
- 前身脉络：换库契约修复与 09-11 生产修复已合 main（1fef3d27）并验收；准备阶段审计在施工分支 742c3ff5。

## 下一步
1. 代码复审 → 合 main（须用户确认）。
2. 生产执行授权后：从合入修订干净检出跑 `repair-backfill-302132 --parquet <冻结 parquet>`；基线若变（新日更）先重跑副本演练。
3. 事项 3（并跑表补齐）：授权后先交端点×日期×额外表清单。
