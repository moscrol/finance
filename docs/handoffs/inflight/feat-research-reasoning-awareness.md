# 研究求证意识候选

## 这个分支做什么
培养机制求证、竞争解释与反证；当前收口零读取复核、旧证据恢复和日期误删保护，不固定流动性视角或模板。

## 决策与被否方案
- 选 `prior_evidence` 服务封装 old/new E 号映射，否 runtime 直接调用协议投影：通过既有分层断言且行为仍为 `E2 -> E1`。
- 选“句首合法短日期 + 已绑定 source_date 月日”局部遮罩，否扩大日期正则/全局放行：保留 `9-11倍` 等真实数量门，语义 judge 仍裁决。
- 保留旧 V4 on2 失败原件，否用修复后运行覆盖：区分程序误删、模型语义和版本证据。
- 不搬 E2 WIP、不给全部槽 `user_premise`：材料资格与推断正确性分开验。

## 当前状态
已提交 `68949b92`、`2cfa9d0d`；当前候选干净@`2cfa9d0d`，求证开关默认 off，未 push/PR/合 main/部署，8792 未动。验证快照见 [prior-evidence-review](../2026-09-21-prior-evidence-review.md)。

## 已验证
- 全仓 pytest `12049P/87S/2X/0F`，收据 `~/.finance-runtime/test-receipts/20260920T195644Z-2cfa9d0d.json`；全仓 Ruff 绿。
- K3 Spec/Quality 均 PASS；报告和执行收据在 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/k3-independent/`。候选/作者树首尾未改；共享 refs/agent-memory 指纹漂移已如实记录，不能称完整隔离。
- 日期隔离补丁338P；撤保护5F/8F；分层回归相关152P，当前相关477P。

## 未验证 / 已知边界
日期修复后的 V4 真实连续入口已在 `2cfa9d0d` 隔离 sidecar 重跑，首答后复核同一会话，两个 run completed；复核保留绑定 `9-11` 证据句并撤回两项资金归因。旧 on2 句子删除原件必须保留。四臂仍有错误归因，n=2 不构成收益趋势；同源 judge/零工具/completed 不等于独立语义通过。虚构供需仍拒答，E2材料binding未合入。Grok/Codex盲审均无有效报告。前端/E2E/registry未合流验收，跨仓 `kb/rag-query` 漂移未处理。

## 下一步
对照日期重跑与旧件，manifest 在外部 `v4/date-fix-rerun/MANIFEST.json`；对齐E2/P5/P6逐句材料来源；补未见题和独立语义复核，失败则封存不写PASS。合main、部署、重启8792、购买外审、删生产全部暂停。

## 踩过的坑
probe打印路径不是隔离users真路径；旧E号不能跨轮复用；合法等长篡改才验证SHA门；`9-11` 既可能是日期也可能是区间，必须先绑定再局部遮罩；K3审核期间共享refs/记忆会受并行环境漂移，收据不能省略。

## 工具沉淀盘点
继续复用既有live_probe/workbench_probe和测试门；K3 runner/报告留在外部证据目录，未造生产通用执行器，因为本轮仍缺独立语义样本，不能把一次审核包装成自动质量量具。
