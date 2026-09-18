# KB双索引部署 · 2026-09-18 22:23 · 写者已协调、验收未过

## 这个分支做什么
隔离双索引迁移+8792部署接线；不碰共享脏正文。

## 当前状态
代码c0fa49cf/d95d4921、旧交接ac75a374已提交；未push/合/部署。8792仍bf662e9310ff。
用户授权本会话协调。原发布41455实际来自Grok Bot父22475，非Cursor；22:04已正常完成退出，无进程被杀。“待用户关Cursor”撤销并已落纠偏。
两个生产索引目录+24文件已加macOS uchg防写；三post-*仍skip。Grok Bot/8792未停；staging后台仍运行。

## 决策与被否方案
- 不杀整个应用、不覆盖对方已发布产物；临时文件防写保护本机目标，读取不变。
- 不把新防写窗口基线代替旧基线；原production-hash失败保留。
- 正文冲突继续隔离，不删除marker洗白。
- 本轮更正/回退：`docs/handoffs/2026-09-18-kb-index-writer-coordination.md`。

## 已验证
固定d95d后端11486P/73S/2xf，收据check严格匹配；前端107P、lint/typecheck/build、Ruff/registry绿。
**E2E31P/3F/2S，all.exit=1，禁止上线**：desktop/mobile报告按钮缺失，tablet追问消息未显示。
普通副本168861向量、14434页+14隔离=14448，无缺口。fence临时6类写拒绝；生产24文件O_WRONLY拒绝、字节未变；原CLI双索引各3 fresh命中，8792健康不换版。

## 未验证 / 已知边界
全文迁移尚未完；未验新消费者真实BGE/8792。uchg是同用户可主动解除的本地防误写，不封Gitea发布或资料编辑，不是全系统互斥。新代码未合，历史14页冲突未解。

## 下一步
1. 现场OP=`~/.finance-runtime/kb-dual-index-20260918`。migration.pid父40354/子41233（先核身份）；evidence/rag_index_full-update.log、migration-results.json。没有自动提升。
2. 查E2E3红，原件gate-receipts/e2e.txt与gate/.../webapp/test-results。门禁已结束，不再是后台待跑。
3. 双索引覆盖/新鲜度/隔离与消费者验过、用户确认合并后才准备切换。

## 踩过的坑
进程身份查父链，不读模板标记猜应用。防写原flags/哈希见OP/evidence/production-file-fence.json；解除仅走fence_production_indexes.py --restore-original-flags <日记>（未执行）。不要递归清uchg或恢复旧hook；共享.git/kb-index-maintenance.json有通知。正常双索引维护入口仍待部署。
