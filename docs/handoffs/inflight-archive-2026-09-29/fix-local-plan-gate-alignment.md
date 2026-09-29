# local 日报计划对齐

## 这个分支做什么
同步器、同日/跨日门、intelligence daily 与 HTML 内部门共用计划，不改资金口径。

## 当前状态
代码 `4fbc8c42`；树 `/private/tmp/fix-local-plan-gate-alignment`，基线 `gitea/main@1fef3d27`。未 push/合并/部署/补跑。后续#50在独立分支`fix/generation-stage-code-root`，不能把其提交当成本枝HEAD。

## 决策与被否方案
- 显式--plan > REVIEW_SYNC_PLAN > full；auto按目标交易日解析，options冻结后各门显式传递。
- theme_flow保留local豁免；否了本地篮子资金凑面板，口径不同。连板/新高/主线/核心股仍须检查。
- 旧daily-update不支持local/cheap，选中同步时拒绝而非偷跑full；不新造写库旁路。
- 计划背景：`docs/handoffs/2026-09-14-local-plan-gate-alignment.md`；#50后续及补充收据在该分支`docs/handoffs/2026-09-15-generation-stage-code-root.md`。

## 未验证 / 已知边界
没在生产库跑同日/跨日/L2门，没部署/生成，不得称日报恢复。资金历史行返回Gap只覆盖新增River测试，不泛化所有消费者。旧/Users验收副本后来有非预期疑似凭证污染，勿动；凭证撤销/污染来源未确认。

## 下一步
本枝计划修复由#50分支继承；需独立复核及用户明确合并授权。获准合并后若继续部署，使用完整代码快照并分别验import/数据/外置用户态/episode。真实三门过后另行授权日报。继续不请求复盘会/不写资金兜底/不碰原数据树WIP。

## 踩过的坑
/tmp下Codex minimal允许读/tmp，live-root-read为unexpected_success；三项网络/套接字实际denied，不是网络隔离flaky。换/Users同代码重验，不修改沙箱规则。变异须独立副本，不与读同一树的正常测试并行。

## 已验证
- 针对性144P（新增39）；删跨日--plan变异9F，恢复144P。
- /tmp原全量9654P/2F/77S/2x，收据`20260914T160652Z-4fbc8c42.json`保留；基线仅两项2F，没有跑基线全量。
- /Users同代码`07d42891`：全量9656P/0F，收据`20260914T163249Z-07d42891.json`；frontend76P及lint/typecheck/build通过；旧E2E完整日志核对15P/47.2s。
- #50另行冻结`0f6c2810`新干净/Users树：全量9679P/77S/2x；frontend76P、E2E15P、registry四条exit0（三仓现场树）。这些是后续提交的收据，不写成本枝全量。
- 日志与边界均见#50日期快照；原红收据与竞争污染日志不删除。
