# 技能超时测试生命周期 · 2026-09-23

## 这个分支做什么

修复 #883 合后复核发现的测试时序假设。用户 message ddd61757 要求继续至收尾，前置 message 7ca1305d 授权可合内容合入，原文在证据根 authorization.json。

## 决策与被否方案

选实例绑定、可控 Event + 真 Future 结算，覆盖事件构造时仍运行/已结束两态；否延长 sleep、删除断言或改生产语义。隔离本测试无关知识库检索。展开见 `docs/handoffs/2026-09-23-skill-timeout-test-lifecycle.md`。

## 当前状态

基座 main@2edbe4c46595。代码仅改会话集成测试，另两份交接；原 #883 已合/#885 承接关闭，不重复操作。开发期回归已完成，下一步冻结提交并完整验证。最终结果从树外原件回读，不把此冻结快照当实时看板。

## 已验证

实际合并提交两份冻结 JSON 与合前一致。四文件定向 213P/1F：slow-skill 超时事件构造时 Future 已结束，false 合法，旧测试硬要 true。受控红对照 1P/1F；新两态断言 2P；五文件 320P，均开发期定向，不当全量。初稿夹具 2F 单独保留，不冒充复现。

## 未验证 / 已知边界

完整门禁和本分支合入尚未预填。仅测试与文档，不改生产状态机、超时、取消、shutdown；#75/#76/运行时接入和 8792 均不操作。

## 下一步

证据根 `~/.finance-runtime/reviews/claim-scope-postmerge-closeout-20260923/`。原红 `targeted-receipts/gate-l0sKrbus/pytest.json`、`basetemp/` 和 `checkout/finance-workspace-private/` 不动；受控对照 `controlled-red-02.*`，模块 `modules.*`。
冻结后完整门禁写 `gates/`，只签确切 head/tree/范围/解释器/依赖；结果及合入回读写 `closeout.json` / `merge.json` 和 PR，不为填数改 head。若 main 漂移，重新核验组合，不移签。全绿且具授权才合；结束后只清理自有已完成 clean 树，保留红现场。

## 踩过的坑

线程池实际提交 copy_context().run，技能方法是第一个实参；按目标实例识别 Future。方法内完成标志不等于 Future 已结算；必须有界等实际 Future。超时状态与任务此刻是否还活着是两个事实。
