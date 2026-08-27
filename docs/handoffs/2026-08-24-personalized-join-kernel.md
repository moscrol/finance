# 2026-08-24 个性化接合核 P0

## 这个分支做什么

买卖题在 `handle()` 前跑 StancePack：用户旧账 × 站立日现价两袋 join。不是持仓本，不是账户规则求值器。

## 当前状态

干净树 `feat/personalized-join-kernel` @ `gitea/main` `34fcbaaa`。P0 已接线；live 冻结题过线；`research_context.stance_pack` 瘦收据已补。P1/P2 未做。未切 8792/8796/8802。

## 未验证 / 已知边界

- 探针用户无旧账、当日 DuckDB 被回填持锁 → 两袋 `empty`（合法，不是没跑）。
- episode 审计文件仍不存模型可见整段锁格，只存袋 status。
- 跨天记住成本价 / 账户表 = P2，需明示。

## 下一步

合 main 后观察，不要默认切 8792。P1 等收据字段用稳再叠。

## 踩过的坑

包不能挂 compose：`trade_advice` 走 Engine A 早退。V 块禁止再自查台账。正门是会话口，不是 `/api/runs`。

## 已验证

ruff 绿；全量 pytest 6312P / 13S；webapp lint/typecheck/test/build 绿。
sidecar `:8817` 题「宁德时代要不要止损」：`same_bind:f20a2b20753d474b`，公开稿有条件、无「现在卖」。
