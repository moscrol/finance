# R6 财务比例别名与单位修复记录

用户已授权先复核设计再推进。协调者选择从 R6 `d8d6196baebdb1108a81ae01466e9df6397dc4fc` 独立补最小缺口；本片不合 main、不切生产，不调真实模型，不与主协调全量检查并跑。

源设计：协调树 `docs/superpowers/specs/2026-09-20-research-closeout-design-review.md`；原反例 `/Users/a77/.finance-runtime/reviews/research-closeout-20260920/research-design/probe_delivery_seams.py` 未修改。新树 code_map query 返回 empty/unavailable，定位依赖精确源码，未据空图声称能力缺失。

## 发现与修复

第一步用已有财务夹具复现“含金量”别名：输入 706.91/445.17 对产物 9.999、同结构出口0.133错值、无其他财务词面的正文，四个失败；净现比与OCF/净利润同错对照仍能拒绝。修改 `_RATIO` 同时让正文前置 financial 判据引用同一别名识别。相同31个断言通过。

第二步覆盖单位所处位置：表头 bp/BP/基点/百分点、cell 差值后缀、明确正文值槽、计算产物列。原实现35F/41P，修改后76P。表头与 cell 分别传入判定，先拒任一差值单位，再按显式倍/百分比核数；所以 `含金量(bp)` + `1.588倍` 也不能认证。正常无单位、倍、158.8%、声明精度舍入仍过。

财务产物复算仍受绑定、单一主体、明确报告期和同期间原始输入控制。正文仍不补猜报告年份。增长/变化列与收入列继续排除；本轮将 delivery 的“增长”单词补到原排除族，与 financial 一致。

交付产物映射保留“有产物但单位不适用”的该期空集合；不能简单删除非法产物，否则无强制计算要求时会静默变成“不用检查”，也不能择取同期间另一个好值掩盖单位冲突。`None` 才代表没有该期产物。

| 方案 | 判断 |
|---|---|
| 把 bp 除以 10000 后继续认证 | 否：差值量纲不是绝对比例，数值换算不能证明本题结果 |
| cell 单位总覆盖表头 | 否：会丢掉表头已明确声明的差值量纲 |
| 整文件采用 q | 否：会把本片扩成约292行语法整合，丢失失败归属 |
| 在两个既有模块局部补识别与判定 | 采用：保留既有出口、额度与修复债务机制 |

## 验证身份与证据

代码提交 `8d281985fc3739832881f3cbab0d174a532caeb5`。`financial_claim_checks.py`、`research_delivery_checks.py`、三个现有测试文件与执行计划构成代码提交；后续只有本记录、inflight 与计划勾选的文档变化。

证据目录 `/Users/a77/.finance-runtime/reviews/research-closeout-20260920/financial-ratio-fix/`：

- `alias-red.log` / `alias-green.log`：4F/27P→31P。
- `units-red.log` / `units-green.log`：35F/41P→76P。
- `exit-baseline-red.log`：临时放回原 R6 两模块，新增真出口14F。`exit-green.log`：修复版14P，涵盖 judge off 与 passed stub；不是自然模型通过。
- `mutation-results.json` 与 `mutation-*.log`：只撤别名/表头优先/产物单位拒绝，各2F/5F/8F；所有源码 finally 恢复并核实 SHA256。
- `fixed-targeted-green.log`：固定干净代码提交7模块351P，4.22秒；时间只说明本次运行，不作性能结论。全局收据 `20260920T034936Z-8d281985.json`。
- `ruff.log`：改动5个Python文件无问题；提交时11道门禁执行通过或按文件范围跳过。
- `original-probe-after.json`：原探针在修复工作树的结果，文件内 HEAD 是提交前基线；不能冒充固定提交收据。源码身份由上述变异恢复hash和代码提交对应。

七模块：`test_financial_r6_regressions`、`test_research_delivery_checks`、`test_financial_delivery_integration`、`test_financial_contracts_r5`、`test_financial_publication_integration`、`test_research_delivery_repair`、`test_frozen_research_delivery`。入口测试证明本片缺口到达真实 verifier，并保留归档草稿/证据，表格坏格不吞输入及邻句，修正后清债。

## 交接边界

实施自审不替代独立 Spec→Quality。未吸收 q 保邻句和多值对应规则，未改保稿/E2、恢复、预算或模型。原 R6 逗号邻句漏保留仍可由原探针复现，明确属于后续片。未跑全量Python/前端/E2E、未做真实模型/真实输入金融交付、未部署；协调者在合流固定版本上另走完整门禁。

没有新建通用测试运行器；测试继续落已有公共函数和真实出口，撤保护只是本片承重证据。通用方法已是既有“撤保护验证”纪律，不再复制第二份工具清单。
