# feat/empty-pool-fallback-query

## 这个分支做什么
空观察池时 Episode 内恰好一次换同窗成交额前排（D3 输入加法）。不改发布门。

## 当前状态
树 `/Users/a77/fwp-wt-empty-pool-fallback` @ `feat/empty-pool-fallback-query`，基线 `gitea/main@3fc47e91`。台账 `R-20260824-08` pending。本提交落地代码 + 离线夹具。

修复轮不挂 fallback（只在主循环调）。`market_watch` 不触发。与 `plan_issue_backfill` 互斥。

## 未验证 / 已知边界
- 挂钩测试无真 DuckDB；池空不是某个 `required_output` 槽。
- C3 不罩 Engine A。本单不主张 Engine B 闸已罩住成交额前排。
- live 单发不得 confirmed。未合 main、未切端口。

## 下一步
1. Gitea #349 已开。合 main 等用户。
2. live 空池题看 `fallback_query=true` + as-of = 问句日。

## 踩过的坑
互斥要两头验：propose 见到 backfill 计划则不 fallback；事后补枪见到 `fallback_query` 则摘掉 `finance_query`/`market_data`。只测一头会漏。

## 已验证
`test_empty_pool_fallback.py` 绿；ruff 绿。修复路径未调用 `_maybe_execute_empty_pool_fallback`。
