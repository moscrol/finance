# 在途交接：fix/backfill-302132-scoped（302132 历史回填执行实现，第四轮交审）

## 状态（2026-09-14 傍晚）
- **第四轮：验收链加固 + 干净修订重演练完成**。复审四轮 3 P1 + 2 P2 全修（验收脚本别名预检/旧收据核验/parquet 身份/TOCTOU 首尾双核/健壮解析；`_guarded_write_json` 全阶段 fail-closed + 半成品清理）。tip `399ac41a`（代码）+ 文档提交。
- 干净重演练：run7 apply=`205a94a4b531`、run8 verify=`cabdeaca07b7`；验收 v4 **25/25 PASS**（`~/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/dryrun-acceptance-v4.json`；含 run5/run6 四份旧收据逐份哈希核验）。
- 单测 22/22；全量 pytest **9,639 passed / 0 failed / 77 skipped**（收据 20260914T051535Z-399ac41a.json，dirty=false）；ruff 全仓过。交审文档 `docs/handoffs/2026-09-14-302132-backfill-execution-design.md`（四轮沿革）。
- **未写生产**。生产授权需另行申请（前提见交审文档末节）。

## 关键背景
- 教训两条：演练必须「先提交后跑」（dirty 树证据无效）；手工清理别用会吞收据的宽前缀 glob（run3/run4 收据系我误删，非代码覆盖——已在文档如实披露）。
- 旧收据现隔离于 `receipts-run5-run6/`；验收脚本 `--expected-old-receipt 路径=sha256` 显式核验。
- 合同链：prep-review → execution-review（五项）→ 三轮（证据绑定）→ 四轮（验收链）。QC 分支 docs/qc-backfill-302132-1b936486。
- 磁盘已回 ~69Gi。前身脉络：换库契约修复与 09-11 生产修复已合 main（1fef3d27）。

## 下一步
1. 代码复审 → 合 main（须用户确认）。
2. 生产执行授权后：干净检出跑 `repair-backfill-302132 --parquet <冻结 parquet>`，当场跑验收脚本（--expected-revision=合入修订、--expected-old-receipt 带前序收据）；基线若变先重跑副本演练。
3. 事项 3（并跑表补齐）：授权后先交端点×日期×额外表清单。
