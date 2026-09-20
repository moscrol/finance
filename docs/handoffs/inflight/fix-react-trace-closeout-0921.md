# ReAct trace 最小修复

## 这个分支做什么
在 PR #809 WIP 上维护 ReAct trace 工程修复，并修补真实历史研究分页的原件行身份；不是 #790-#794 全完成。

## 决策与被否方案
- 条件一致性：只在本轮确实删掉升级/降级定义时清理悬空“满足条件中的 N 条”，保留观察；不放宽数字门、不重写整段。
- 历史分页：`sample` 使用不可变原件的绝对行号，并返回 `offset/next_offset`；不按页重置、不把分页卡数当完整分母。
- 否决自动补绑未引用数字、全局改 ranking_intent、重发同题自然 run；这些会混淆证据绑定、题型合同和质量验收。
- 保持 WIP；不合 main、不部署 8792、不新增付费外审、不删生产原件。
- 背景见 `docs/handoffs/2026-09-21-condition-coherence-repair.md`、`docs/handoffs/2026-09-21-history-page-identity.md`。

## 当前状态
HEAD `3765af67b70bf4b39c3c7cb7e22920b808c30d5c`，已推送 `gitea/fix/react-trace-closeout-0921`，树 clean；PR #809 open/WIP。生产 8792 仍 `bf662e93`，8856/8857 已停。

## 已验证
- 准确 SHA 全仓 pytest：`11986 passed / 85 skipped / 2 xfailed / 17 warnings`；收据 `/Users/a77/.finance-runtime/test-receipts/20260920T212038Z-3765af67.json`，revision/解释器/Python/依赖/clean/base drift 0 均通过严格校验。
- 全仓 Ruff、diff check、提交 hooks 通过；历史相关选集 `364 passed`。
- 225 行真实 `find_analogues` 原件离线分页：9 页、225 个唯一行号，特征与原件一致、保存原件不变；自然模型调用 0。首次用过期截止日的回放被权限门拒绝，原失败保留。
- 三个变异（行号重置、缺 next_offset、旧 partial-page 判据）均使对应回归失败；源码未被变异改写。

## 未验证 / 已知边界
- 真实金融质量仍 `not_passed`：未绑定 225/25、AI手机PC/MiniLED 数值及相关定性仍需 #794；`ranking_intent=false`、#793 比较合同/假设槽未完成。
- 本修复保证分页身份和导航，不保证模型会引用分页值、不自动补绑定；跨工具 hash 稳定性尚未验证。
- 新修复未跑自然模型验收、前端验收或独立 K3；registry `check` 的跨仓 `kb/rag-query` 漂移仍与基线同红。

## 下一步
优先推进 #793 比较合同/假设槽与 #794 历史结果证据绑定；另补 #790 finance_query 自然纠参验收、#791 集合排序、#792 卡类型。任何合 main、部署、付费外审或删除生产内容先取得授权。

## 踩过的坑
全量测试必须在业务提交后重跑并绑定准确 SHA；共享 refs 变化不能写成全局未变。历史 artifact 的 `knowledge_cutoff` 早于回放截止日会被正确拒绝，回放必须沿用原件截止日。