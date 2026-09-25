# #83 / PR #813

## 这个分支做什么
302132固定回填整合；文档树代码旧，不从此验收/生产。不合main、不动8792/launchd/他股。

## 决策与被否方案
- 固定候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59` / base `4cc15e703f81bce8abadee00f68caacdb0c72b4d`；main观测 `d21707ca6` 新组合未验。
- 04-06共52次GLM请求，无自动重试；所有自有进程已结束，PR继续WIP/open/unmerged。
- 工具层已硬拦首bash、阳性对照必交字段、失败用例不得报PASS；离线反例6项和沙箱预检通过。详见日期交接 `docs/handoffs/2026-09-25-backfill-302132-quality-continuation.md`。

## 当前状态
**SPEC_SCOPED_DELIVERED_QUALITY_FINAL_REJECTED**。06执行阶段完成首控件+供应探针10P；报告真实deliver_stage但缺 `verdict`、C1-C7 `id/status/evidence`、标准计数和 `positive_control.status/classification/evidence`，硬门拒收。04因pytest rootdir沙箱错误未交付；05探索耗尽无交付。归档480份/2,389,778字节：`docs/verification/2026-09-25-backfill-302132-quality-continuation/`。未合入、未生产。

## 已验证
- 06：网关4P、探索5请求结构通过、执行9请求结构通过；首bash raw exit1且含 `intentional probe_bug`。
- 06给定来源两组供应探针真实10P（7个旧断言来源+3个窗前适配器来源），作者测试0；`--rootdir=quality/work`后无环境错误。
- 04宿主同沙箱命令诊断10P，仅诊断不移签独审。
- 旧Spec守卫5P、旧作者15457P/四叶/37项仍只在旧范围有效。

## 未验证 / 已知边界
- C3生产形64/39/161未独验；C1/C4-C7未审；当前main组合无工程收据。
- 给定探针来源为前审查断言+宿主夹具修复，不算本轮新写；供应10P不等于完整C3批准。
- 终稿未被接受，不能人工补字段或把模型JSON包装成PASS。

## 下一步
新批次若继续，先核对CURRENT、PR head、main和归档，再补一个标准schema且不掩盖限制的真实报告；完成独立QC后才前向当前main跑工程门禁。合入、生产回填均等逐字授权；生产前重新冻结输入并取本轮父备份。

## 踩过的坑
- pytest绝对路径会把审查根当rootdir，沙箱拒绝扫描；固定`--rootdir=quality/work`。
- 探索probe_files可能是对象而非字符串；宿主解析需取`.path`并对`parsed=None`短路。
- 报告字段即使事实计数正确，缺schema也必须拒收；不可事后补签。
