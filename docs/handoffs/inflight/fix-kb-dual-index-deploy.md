# KB双索引部署 · 2026-09-18 21:40 · 并发写者阻断

## 这个分支做什么
从已验main接手双索引迁移/8792部署；代码与资料根分离，先验副本再切消费者。

## 当前状态
代码c0fa49cf+d95d4921已提交，未push/合/部署。8792仍bf662e9310ff。
**停在用户协调**：另一Cursor进程41455在主KB直跑publish_rag_index.py --build --clobber，生产两索引hash已变化。未杀对方、未覆盖其产物。共享脏正文/冲突未动。
本轮已安装3个post-*维护暂停包装（原钩子备份），但direct build/publish不受它们保护。当前不会自动恢复钩子。

## 决策与被否方案
- 冻结KB91725ea9b代码+资料副本+双索引副本；不拉共享脏树、不原地热部署。
- 新KB_RAG_CODE_ROOT及worker资料参数接prewarm/probe/CLI；KB_RAG_FULL_INDEX_DIR防新旧索引混用。
- 冲突页继续隔离；不为health绿删marker。不擅自终止另一个发布会话。
- 详情：`docs/handoffs/2026-09-18-kb-dual-index-deploy-blocked.md`。

## 已验证
真实钩子6次调用窗口18份索引hash不变（仅该窗口）。普通副本：168861向量复用/0重嵌/774移除，metadata v1，14434入库+14隔离=14448应选，无缺口，全部向量非零归一。health仍degraded（隔离债务）。旧代码新回归4红；候选定向81P、原pre-commit绿。

## 未验证 / 已知边界
普通验收脚本最终production-hash断言失败，整体exit1，不能报整条通过。全文真实BGE仍运行；固定d95d完整门禁也在跑，尚无全量结论。无新消费者BGE/8792真入口验收，不代表答案质量改善。

## 下一步
1. 用户协调direct publisher交接，核全写入口保护；不要自动恢复旧hook。
2. 现场根`~/.finance-runtime/kb-dual-index-20260918/`：migration.pid(40354)、gate.pid(47887)，先核进程身份。两后台均仅副本/测试，无自动提升。看evidence/migration-results.json、rag_index_full-update.log和gate-receipts/{runner.log,all.exit}。
3. 核双索引覆盖/字段/隔离、源码与资料新鲜度，完整门禁并获用户合并确认后才准备切8792。保留旧服务/索引，不代解14页。

## 踩过的坑
hook锁不是全写者锁。source哈希清单含dirty事实，git SHA不能代替。c0fa第一轮全量为补full接线主动中断，不算通过。三钩子原件见现场evidence/post-*.before；切换前必须重新核生产基线。
