# Workbench 发布执行

## 这个分支做什么
用户「执行」后的发布准备：数据及固定版本检查全过才切 8792。本轮仅文档，基线 main `626d8a508c1c`。

## 决策与被否方案
| 选了什么 | 否了什么 / 原因 |
|---|---|
| 数据门失败保留现网 | 不直接换 staging：个股 0 行、市场 13 列 NULL |
| 对接既有行情恢复 owner | 不搬在途补丁写生产：代码准入、五问/三合同仍待定 |
| 原收据保留原 SHA | 不移签 preview 到 main：精确版本校验拒绝 |
| 停在前置检查 | 不新增并行全仓或盲重跑：约 9GB 空间、今晚已重试失败 |
详情：`../2026-09-23-workbench-release-blocked.md`。

## 当前状态
BLOCKED；未切服务、未写生产或 staging、未合 main、未调真实模型。8792 仍 `3b7e473575b0`，readlink 未变。独立树 `/Users/a77/fwp-wt-workbench-release-0923`；检查后形成的两份交接随本次文档提交保存。无后台续跑器。

## 已验证
证据根 `~/.finance-runtime/reviews/workbench-release-20260923/`。
- health HTTP 200、dirty=false、code_matches_repo=true；readiness HTTP 503，market_data_consistency=false（快照09-23/库09-22）。
- 干净626树现有检查器读 production/staging：两者 data gate rc=2/INCOMPLETE；生产19表无09-23行，staging个股0行、市场13列NULL；09-22市场也有13列基线外NULL。
- preview `53c51cfd` 收据完整范围/读数对平，但 expect-revision=626与基座校验rc=1；实际差异仅8份docs。不是main代码测试失败。
- 远端main收尾仍626；夜跑日志已归档，18:46拒换库、21:06 finalize失败。

## 未验证 / 已知边界
未跑main完整四叶、新数据恢复与部署后探针。行情恢复其他会话仍在验收，不能借其在途结果放行。现网存活不等于数据就绪。

## 下一步
1. 接行情恢复owner：`/Users/a77/fwp-wt-market-recovery-qc-fix-0923/docs/handoffs/inflight/fix-market-recovery-qc-0923.md`；五问页在contracts-0922树 `docs/handoffs/2026-09-22-market-recovery-decision-page.md`。
2. 口径和修复准入完成后从新生产基线做正式staging恢复，逐列/跨日验收，不直接发布旧副本。
3. readiness绿后，协调空间与测试时段，固定届时main补精确四叶，再按验收规程链切、探针与账本收尾。

## 踩过的坑
默认daily-full包含停采的fupanhui路径；正式夜跑是local，不盲复跑。日期前进不证明字段完整。低空间不擅删他人测试现场。本轮复用现有门，无新增通用工具。
