# 在途交接 · refactor/tier-promotion-budget-to-runtime

更新：2026-09-03 03:45 CST · **已闭环：PR #535 已合 `gitea/main=6b9f5300`，主干门禁可采信（7454P/5F 同基线红，收据 `20260902T192336Z-f5679c3e.json`，见 `inflight/main.md` 顶行），8792 未切。本线无后续单；`services/**` 零账本写入由 `test_tier_promotion` 棘轮看守。**

## 这个分支做什么

把 `services/` 里最后两处 root ledger 写入（`mode_governor.ModeGovernor.apply`、
`forecast_residual_budget.promote_forecast_residual`）逐字搬到 `runtime/tier_promotion.py`；
`FinanceResearchHarness.govern_mode` 只出裁决，loop 拿 `decision` 调 `apply_mode_promotion`
落账。M5（#532）那条「领域申请、底座授予、领域不碰账本」纪律至此全仓成立，有 AST 棘轮。

## 决策与被否方案

| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| `ModeGovernance` 去掉 `context`，loop 自己调 runtime 落账 | 保留 `context` 字段原样透传 | 透传一个 harness 没改过的 context 是误导：读者会以为 harness 还在落账 |
| 两处升档各搬各的，不合并成一个函数 | 合成一个 `promote_to_deep` | 二者行为真不同（抛 ValueError vs 静默返回；延长 vs 重建 deadline；改不改 contract tier），合并就是改行为 |
| 棘轮按 AST `Call.func.attr ∈ {grant, promote_caps, consume_call, consume_seconds}` 扫 `services/**` | 只扫字符串 `root.grant(` | 变量名一换字符串扫描就漏；`research_contract.py`（账本自身）整文件豁免 |
| 加反向测试「记账点真在 runtime」 | 只有「services 没有」 | 否则「谁都不记账」也能绿 |

## 当前状态

已合（见顶行）。实现 `8ccd1a4e`，docs `3719e700` / `f5679c3e`。8792 未切。

## 已验证

- 定向 388P（tier_promotion / mode_governor / root_budget_invariants / runtime_fault_matrix /
  forecast_residual_budget / research_harness / harness_reference_loop / agent_episode /
  continuous_turn_adapter / repair_policy_split / watchlist_digest_pack / route_composition_gate）。
- 变异四组全红：Episode 不落账 3 / 参考 loop 不落账 2 / services 回焊一处 `root.grant` 1 / 算术多给一次 6。
- ruff 绿；`layer_audit` ERROR 0 == 基线。

## 未验证 / 已知边界

- 零 live 判据（结构等价重构），随下次 8792 切流带上。
- 展望升档只有 adapter 一个调用点，Episode 内没有；参考 loop 也不做展望升档（它没有 adapter 那步开场）。

## 下一步

本线无。同批待用户拍：`_recover_finalization` 并不并（生产 0 触发，见
`docs/verification/2026-09-03-finalization-recovery-offline.md`，建议不动）；预算 P1（25–35s）；8792 切流。

## 踩过的坑

- 变异测试恢复文件**不要用 `git checkout --`**：它还原到已提交态，把未提交实现一起冲掉
  （本轮 `forecast_residual_budget.py` 中招一次，重做）。用 `.bak` 换回，或先提交再变异。
