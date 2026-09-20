# 8792 算例与行情修复

## 这个分支做什么
修原始8792探针暴露的题设/行情/交付问题。授权修复，不含合并或部署。

## 当前状态
树 `~/fwp-wt-8792-premise-market`；代码tip df186f9b，基座728f3271。5个修复提交已落，未push/PR/merge。财务正确性验收仍阻塞，不得宣称8792修好。
最终首题 run_20260921_000637_338373 错用2024利润8计算静态PE=22.5，题设最近年度2025利润9应得20；judge仍passed。v5后两题未跑。18892已停止，active/queued清零后停；生产8792仍bf662e93，未改。

## 决策与被否方案
- 题设计算单独标记user_premise；否了删除真实事实证据闸。
- 不需要检索仍进入Episode；否了转旧管线，真实追问已证明会拒答。
- canonical同日全截面聚合计数；否了限额后数返回行。
- 来源区分.FP复盘会/.TI同花顺与local等权加工。
- 坏JSON恢复保留草稿引用的真实证据；不直接交付草稿、不接受伪造编号、不无限扩上下文。
- 更多提示与同题重试不是财务正确性保证，v4/v5已反证。
展开：`docs/handoffs/2026-09-21-8792-premise-market-repair.md`。

## 已验证
固定解释器 `~/finance-workspace-private/.venv-workbench/bin/python`；clean df186f9b相关测试1728P/12S、全仓Ruff及提交门禁过。收据 `~/.finance-runtime/test-receipts/20260920T160558Z-df186f9b.json`。恢复丢E28/E29/E30回归先红后绿，伪造E999仍拒。
13次隔离真实调用跨5候选全部保留；v4行情关键数值/前三正确，v4算例与追问利润基数错。不能用其他版本答对为最终版签字。

## 未验证 / 已知边界
未跑全仓Python、前端/E2E、完整跨仓registry、独立QC。模型judge同源，实际漏错。恢复仍限12条；纯算例双次格式错误仍受恢复要求非空evidence限制。题设计算输入尚无年份/性质/单位的程序校验合同。

## 下一步
先给原始用户题设建带来源的年度/单位/实际-预测-假设计算合同，并校验静态PE基数及跨轮更新，再重跑原题。现有derived_calculation/sandbox_fincalc/inputs_from_calc可复用，但前者要求已绑定事实证据，不能把虚构题设冒充事实，也不能只执行模型选错的180/8。然后独立验收和完整门禁；未绿不合不部署。

## 踩过的坑
公开答案优先于completed/judge passed。v3行情查到前三但恢复投影丢了，不能写成供应商缺数。工件在 `~/.finance-runtime/8792-premise-market-evidence/` 的v1-runs到v5-runs与SHA256SUMS；原users也保留。probe打印默认users路径不适用隔离目录。共享记忆只追加，不提交他人混合改动。
