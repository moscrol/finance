# #83 / PR #813

## 这个分支做什么
302132固定范围回填整合，只到工程送审；合入与生产另行授权，不动8792/launchd/他股。

## 决策与被否方案
main有源码/门禁前进就重新冻结并全验，旧绿不移签；文档留本分支，被验代码另树固定。作者工程绿不代#75独审，WIP保留防误合。理由与发现顺序见 `docs/handoffs/2026-09-24-backfill-302132-current-main-ready.md`（此前背景在engineering-ready和gate-continuation两份快照）。

## 当前状态
**ENGINEERING_READY_PENDING_QC**。#813 head `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，base `4cc15e703f81bce8abadee00f68caacdb0c72b4d`，已推。四叶及整库均通过，当前main核验一致，自有进程已退出。
证据根 `~/.finance-runtime/reviews/backfill-302132-0923/`，动态入口 `CURRENT.json`；唯一被验树 `forward-02/tree`；原件 `continue-08/`。本任务分支代码仍旧，不能从这里运行验收/生产。归仓镜像与待授权稿：`docs/verification/2026-09-24-backfill-302132-current-main-ready/`。
#813保持WIP/open/unmerged；#802已关，6446→#813。ca4与更早轮次只保留为历史证据。

## 未验证 / 已知边界
#75独审未完成，未获合入或生产授权；未写生产。副本证据只对冻结数据成立，生产前重新冻结。中性basetemp不代表修了来源路径股票代码误判；旧红/中断与旧绿原件不删不移签。

## 下一步
1. #75以3c5独审，核CURRENT/PR head/main，勿拿文档HEAD或旧收据。
2. 独审通过后请用户确认合入；版本变化先评估重验，本文不是滚动许可。
3. 生产对命令/日期/冻结输入/本轮真实父备份另行逐字授权；模板指向forward-02/3c5，CLI无--record，授权另存JSON。WAL/后续业务写入先停。

## 已验证
3c5定向118P；ruff/全量15457P、0F/0E、85S/2X，完整收集15544，身份/范围校验0、漂移0；前端120P、E2E34P+2既有跳过；registry五项0；整库37PASS、金额负对照/恢复/值审计正确，64行三项全非空，生产未变。merge-tree无冲突。完整原件及哈希对账见continue-08/verified-closeout.json。

## 踩过的坑
临时路径含302132会触发业务扫描；中性路径、原生成功清理失败保留。系统函数模拟先于框架清理恢复。E2E先归档。恢复只认本轮父收据，不用演练或“最新”备份；不停止他人任务。
