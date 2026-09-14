# 在途交接：fix/backfill-302132-scoped（302132 历史回填执行实现，第三轮交审）

## 状态（2026-09-14 午后）
- **第三轮：干净修订重演练完成**。第二轮因 run3/run4 收据绑定 1b936486+dirty（在 efe2d28b 提交前运行）被判证据无效；已在干净提交 `f9b3663e` 重跑：run5 apply=`1a34c356050a`、run6 verify=`432521cb81cd`，验收 v3 **16/16 PASS**（父=子收据 revision==f9b3663e、dirty==false、备份哈希与收据一致、生产未变；`~/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/dryrun-acceptance-v3.json`）。
- 代码补强同提交：收据换库前预校验（不可写/冲突在换库前拦截，有反例测试）、写后失败响亮 rc=2、单测身份断言、验收脚本入库 `scripts/verify_302132_backfill_acceptance.py`。
- 单测 20/20；全量 pytest **9,637 passed / 0 failed / 77 skipped**（收据 20260914T043925Z-f9b3663e.json，dirty=false）；ruff 全仓过。交审文档 `docs/handoffs/2026-09-14-302132-backfill-execution-design.md`（三轮沿革）。
- **未写生产**。生产授权需另行申请（前提见交审文档末节，含当场 `--expected-revision` 复核）。

## 关键背景
- 教训：演练也必须「先提交后跑」——dirty 树的演练收据不能充当目标修订证据（P2-3 自查自证）。
- 合同链：prep-review（P1×2+合同）→ execution-review（五项退修）→ 三轮（证据绑定阻断）。QC 分支 docs/qc-backfill-302132-1b936486。
- 磁盘一度降至 ~4.3Gi（他 agent 占用）；演练目录含 fake-prod.duckdb + 两轮 CoW 备份 + 证据 JSON，评审期间保留。
- 前身脉络：换库契约修复与 09-11 生产修复已合 main（1fef3d27）；准备阶段审计在施工分支 742c3ff5。

## 下一步
1. 代码复审 → 合 main（须用户确认）。
2. 生产执行授权后：干净检出跑 `repair-backfill-302132 --parquet <冻结 parquet>`，当场跑验收脚本（--expected-revision=合入修订）；基线若变先重跑副本演练。
3. 事项 3（并跑表补齐）：授权后先交端点×日期×额外表清单。
