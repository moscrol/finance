# 在途交接：fix/backfill-302132-scoped（302132 历史回填执行实现，第五轮交审）

## 状态（2026-09-14 夜）
- **第五轮：异常路径与验收角色加固完成**。复审五轮 3 P1 + 2 P2 全修：探针只删本轮自建（用户路径纯校验）、O_EXCL 竞争不删他写者（inode 再核）、samefile 硬链接别名、收据全 schema 校验（缺证据必红）+ 独立子报告深比较、生产执行后验收对象角色重定义（基线=换库前备份）。tip `5b0cd87e`（代码）+ 文档提交。
- 干净重演练：run9=`efc2b64d8870`、run10=`11bad970c4e1`；验收 v5（生产执行后角色形态：--production=run9 备份）**33/33 PASS**（`dryrun-acceptance-v5.json`；8 份旧收据逐份哈希核验）。
- 单测 26/26（含 4 个新反例子进程/竞争测试）；全量 pytest **9,643 passed / 0 failed / 77 skipped**（收据绑定 5b0cd87e，dirty=false）；ruff 全仓过。
- **未写生产**。生产授权前提见交审文档末节（角色化验收命令已定义）。

## 关键背景
- 教训三条：先提交后跑；清理别用宽前缀 glob；**哈希程序化引用不手打**（第四轮消息中转录错 run5/6 哈希，v5 门禁正确拒签后纠正——文件从未被修改）。
- 旧收据分层隔离：`receipts-run5-run6/`、`receipts-run7-run8/`。
- 合同链：prep-review → execution-review → 三轮（证据绑定）→ 四轮（验收链）→ 五轮（异常路径+角色）。QC 分支 docs/qc-backfill-302132-1b936486。
- 磁盘已回 ~64Gi。前身：换库契约修复与 09-11 生产修复已合 main（1fef3d27）。

## 下一步
1. 代码复审 → 合 main（须用户确认）。
2. 生产执行授权后：干净检出跑 `repair-backfill-302132 --parquet <冻结 parquet>`；当场验收：`--production <执行收据 backup 路径> --clone <canonical> --expected-production-sha256 <收据 backup sha> --expected-old-receipt …`；基线若变先重跑副本演练。
3. 事项 3（并跑表补齐）：授权后先交端点×日期×额外表清单。
