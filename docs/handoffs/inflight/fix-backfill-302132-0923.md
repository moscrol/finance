# #83 / PR #813

## 这个分支做什么
将 302132 固定范围回填整合到当前 main，只到 PR 就绪；合入与生产执行均未授权。工作树 `/Users/a77/fwp-wt-backfill-302132-0923`。

## 决策与被否方案
- 窗外全列双向零差，否决要求窗外无行：已有 09-21/22 合法日线。
- 并跑来源上界固定 max(gap_parallel)，否决随日更扩大缺口：冻结 parquet 仍独占尾两日。
- 新增可重跑量具 `scripts/review_probes/rehearse_302132_backfill.py`，仅写新建隔离目录；不靠手搓 SQL。
- 详情及生产/回滚待授权模板：`docs/handoffs/2026-09-23-backfill-302132-integration.md`。

## 当前状态
基于 main `626d8a508c1c`，整合 `10642b9af`，源码修复 `b9b59a9af` 已推 #813。#802 已关闭，评论 6446 接替到 #813，历史分支保留。
证据根 `~/.finance-runtime/reviews/backfill-302132-0923/`；运行中的最新状态和最终候选 SHA 只看 `CURRENT.json` 及其原始收据。缺文件、红灯、head 不匹配均不可合；不能把本文 b9 读数移签文档提交。

## 已验证
b9 干净树全仓 ruff + 定向 118P/0F；finance-only registry 通过，merge-tree 干净。`rehearsal-b9b59a9a/summary.json` 为完整副本演练成功：apply/verify 0，验收 37 项 PASS，1e15 amount 对照 rc2 且仅 oracle 失败；恢复 SHA 与基线相同。非空 10/11→64/64，无相邻三元值整行克隆；生产 SHA/stat/fact 最新日均未变。整库演练副本已删，报告与冻结 parquet 保留。

## 未验证 / 已知边界
生产回填未执行、授权未取得。b9 首轮前端 116P/4F（3 timeout+1断言）；前端目录与 main tree 相同不等于可豁免。完整四叶与最终 head 身份以 CURRENT 为准。机器多 agent 并发、负载曾 291、磁盘曾 8.1 GiB，勿叠加重测或停止他人任务。

## 下一步
读取 CURRENT，完成缺失/失败叶与必要的最终 head 演练；四叶全绿且 head 匹配后回读 #813，提交用户决定合入。生产命令/日期范围/回滚点另行逐字确认，CLI 无 --record 参数，授权另存 JSON。

## 踩过的坑
旧副本/旧收据不能背书新 revision。注册表从嵌套隔离 candidate 跑才是 finance-only。前端测试用独立端口，不碰 8792。恢复只认本轮父收据，不取“最新备份”，出现 WAL 停下。不得改 launchd、补他股或合 main。
