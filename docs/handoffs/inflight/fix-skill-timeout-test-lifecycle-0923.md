# 技能超时测试生命周期 · 2026-09-23

## 这个分支做什么

修复 #883 合后复核发现的测试时序假设。用户 message ddd61757 要求继续至收尾，前置 message 7ca1305d 授权可合内容合入，原文在证据根 authorization.json。

## 决策与被否方案

选实例绑定、可控 Event + 真 Future 结算，覆盖事件构造时仍运行/已结束两态；否延长 sleep、删除断言或改生产语义。隔离本测试无关知识库检索。展开见 `docs/handoffs/2026-09-23-skill-timeout-test-lifecycle.md`。

## 当前状态

#888@ad3b176564a4 完整门禁全绿，但期间 main 合 #887 至 0525e780e，零漂移校验及 expect-base 拒合，未发合入 POST。已前向收入该基座（1608806b9），相对新 main 仍只有原测试与两份交接；不操作其部署。现冻结第二轮组合，最终看树外原件，不把此快照当实时状态。#883/#885 不重复操作。

## 已验证

实际合并提交两份冻结 JSON 与合前一致。四文件定向 213P/1F：slow-skill 超时事件构造时 Future 已结束，false 合法，旧测试硬要 true。受控红对照 1P/1F；新两态断言 2P；五文件 320P，均开发期定向，不当全量。初稿夹具 2F 单独保留，不冒充复现。

## 未验证 / 已知边界

ad3 首轮：14621P/0F/85S/2X（收集14708），前端120P、E2E34P/2S、registry5/5（98 warning），七个回归实跑。85S 对应本树无代码地图，3个空图用例实跑、1个有图探针跳过；未缩范围。第二轮尚无预填结果，旧绿不移签。仅测试与文档，#75/#76/运行时接入和 8792 均不操作。

## 下一步

证据根 `~/.finance-runtime/reviews/claim-scope-postmerge-closeout-20260923/`。原红 `targeted-receipts/gate-l0sKrbus/pytest.json`、`basetemp/` 和 `checkout/finance-workspace-private/` 不动；受控对照 `controlled-red-02.*`，模块 `modules.*`。
首轮 `gates/` 和 `gate-summary.json` 只签ad3，拒合原件 `merge-aborted-base-drift.json`。第二轮只读 `retry-02/gates/` 与 `retry-02/runner.log`，只签确切head/tree/范围/解释器/依赖；最终 `closeout.json` / `merge.json` 和PR回读。全绿、零基座漂移且具授权才合；不要为填数改被测head。已合则只清理自有已完成clean树，保留红现场。

## 踩过的坑

线程池实际提交 copy_context().run，技能方法是第一个实参；按目标实例识别 Future。方法内完成标志不等于 Future 已结算；必须有界等实际 Future。超时状态与任务此刻是否还活着是两个事实。
