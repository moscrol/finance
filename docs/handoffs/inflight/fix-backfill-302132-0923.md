# #83 / PR #813

## 这个分支做什么
整合 302132 固定范围回填，只到 PR 就绪。合入、生产均未授权；不动 8792/launchd/他股。

## 决策与被否方案
- 窗外全列零差，不要求窗外无行；并跑来源上界固定，冻结 parquet 独占尾两日。
- 中性 basetemp + pytest 失败保留，不筛测试或删运行中目录。三处系统函数模拟限定作用域，额外断言已恢复，不放宽业务断言。
- 交接只推进任务分支，不推进 #813，避免文档提交再次改变被验版本。
- 背景/被否方案/收据：`docs/handoffs/2026-09-24-backfill-302132-gate-continuation.md`。

## 当前状态
**BLOCKED_RESOURCE，#813 仍 WIP**。正式候选 `fd6d8cc5be24c6f3a85af5c960be7766f88deaa7` 已推，基线 main `3bb81b96`。#802 已关，评论 6446 → #813，分支保留。
证据根 `~/.finance-runtime/reviews/backfill-302132-0923/`，动态入口 `CURRENT.json`；被验树是其 `candidate/`。本文所在任务分支的文档提交不是候选 SHA。本轮验收进程已全部退出。

## 未验证 / 已知边界
fd6 的 Python 全量 307 秒后因整机磁盘跌破 4 GiB 中断，无完整收据；临停前自有临时目录仅约 112 KiB。fd6 整库演练因不足 8 GiB 在复制前拒绝。旧 c2 的 37 项演练绿不能移签；独立 QC 未完成。生产未执行。

## 下一步
1. 协调稳定容量窗口（演练至少 8 GiB），读取 CURRENT，核对 PR head/候选干净状态/main 漂移。
2. 新输出目录 + 中性 basetemp 补完整 Python；保持 `-o tmp_path_retention_policy=failed`，无筛选。完整收据再过 `check_test_receipt.py --expect-revision <候选SHA> --require-full-scope`。
3. 同 head 用现有 rehearsal 量具重跑整库闭环。四叶及数据证据全绿后更新 #75、解除 WIP、请用户决定合入。生产命令/日期/本轮父备份回滚点另行逐字授权，模板见证据根 `production-authorization-draft.md`。

## 已验证
fd6 干净树定向 118P、前端 120P/E2E 34P+2 原有跳过、注册表 CI 五项全0、ruff 通过。撤模拟作用域在仓外测试副本触发新增恢复断言。main 3bb 与 fd6 的 merge-tree 无冲突。全部原件在 `continue-04/`。

## 踩过的坑
目录名 302132 会进入带读文本并触发股票检查；只换中性路径不等于修了产品边界。旧 trace 归档晚于清理而丢失，后续两轮已先归档。registry check 一条不代表五项全叶。恢复只认本轮父收据，WAL 出现即停；不停止他人任务，不把定向/中断/旧版本读数拼绿。
