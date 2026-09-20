# 研究求证意识候选

## 这个分支做什么
培养机制求证、竞争解释与反证；当前收口旧证据恢复和日期误删保护，不固定视角或模板。

## 决策与被否方案
- 选 `prior_evidence` 封装 old/new E 号映射，否 runtime 直接投影：分层断言通过，行为仍为 `E2 -> E1`。
- 选“句首短日期 + 绑定 source_date 月日”局部遮罩，否扩大日期正则/全局放行：保留 `9-11倍` 等数量门，语义 judge 仍裁决。
- 保留旧 V4 on2 失败原件，否用修复后运行覆盖：区分程序误删、模型语义和版本证据。
- 不搬 E2 WIP、不把全部槽改 `user_premise`：材料资格与推断正确性分开验。

## 当前状态
已提交 `68949b92`、`2cfa9d0d`；代码验证 revision 仍为 `2cfa9d0d`，本轮只补文档/外部收据，求证开关默认 off，未 push/PR/合 main/部署，8792 未动。验证快照见 [prior-evidence-review](../2026-09-21-prior-evidence-review.md)。

## 已验证
- 全仓 pytest `12049P/87S/2X/0F`，收据 `~/.finance-runtime/test-receipts/20260920T195644Z-2cfa9d0d.json`；Ruff 绿。
- K3 Spec/Quality 均 PASS；报告在 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/k3-independent/`。候选树首尾未改，但共享 refs/agent-memory 漂移，不能称完整隔离。
- 日期隔离338P；撤保护5F/8F；相关回归477P。

## 未验证 / 已知边界
真实入口 sidecar 在 `2cfa9d0d` 重跑，首答/复核 completed；新答用全日期，未命中旧 on2 的 `9-11` 路径。旧 on2 原件只读重放：目标句未被数量门删除并到达 stub judge，收据 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v4/on2/semantic-replay-2cfa.json`，不等于真实模型验收。四臂仍有错误归因，n=2 不成趋势；同源 judge/零工具/completed 不等于语义通过。独立盲审为负向观察（拒绝 `[1,2,3,5]`），Grok/Codex 仍失败。供需仍拒答，E2 binding未合入；前端/E2E/registry和跨仓漂移未验。

## 下一步
对照重跑与旧件，manifest 在外部 `v4/date-fix-rerun/MANIFEST.json`；对齐E2/P5/P6材料来源，补真实入口短日期证据。独立语义负向结果封存，不写PASS。合main、部署、重启8792、购买外审、删生产均暂停。

## 踩过的坑
probe打印路径不是隔离users真路径；旧E号不能跨轮复用；合法等长篡改才验证SHA门；`9-11` 既可能是日期也可能是区间，必须先绑定再局部遮罩；K3审核期间共享refs/记忆会受并行环境漂移，收据不能省略。

## 工具沉淀盘点
继续复用既有 probe 和测试门；K3 runner/报告留外部，未造生产执行器，不能把一次审核包装成质量量具。
