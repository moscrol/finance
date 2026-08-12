# 在途交接 · cursor/repair-retry-headroom-d7ac

更新：2026-08-13 · Cursor Cloud（R5 隔离端口验证已过，等用户审 #297）

## 这个分支做什么

修 #296 部署后 R4 验收暴露的两处重试缺陷（PR #297）：

1. `grant_for_transient_model_retry` 按 `goal.remaining_seconds`（=刚烧穿的 16s/8s 授予）铸新窗 → 改按 `min(hard-cap 未分配余量, 30)`；
2. 耗时略超账本残余时 `consume_seconds` fail closed → `budget_alive=False` → 连重试闸门都进不去（R4 A6/A7）→ 改为先 `settle_seconds` 结平残余再铸。

## 生产收据

- **R4**（`intelligence/eval/runs/20260813T0159Z-r4-repair-retry.json`，canonical 8792 @ `190abf21`）：重试触发 5 次全部再超时（窗口 16s/8s 对中转 P50≈28s）；A6/A7 未进闸门。
- **R5**（`intelligence/eval/runs/20260813T0245Z-r5-headroom-fix.json`，隔离 8794 @ `3f2ed71e`，A4–A10 七题）：重试窗全部 `asked=30.0`；A4 完整走通（`repair_model_finish`，2 证据 0 降级）；A6/A7 形状进了闸门；降级 6/7 → 2/7，带证据 2/7 → 5/7。
- 两轮都跑在北京时间凌晨（中转最差时段），跨轮对比有噪声；**窗口尺寸收据（30 vs 16/8）是确定性的**。

## 新形状（本分支不修，待立案）

30s 重试窗内 provider 正常返回、但模型没吐合法修复 FINISH：`repair_model_stop`（A6/A7/A8/A10）、`invalid_repair_finish`（A5）。是模型协议问题不是超时问题。答案靠「保草稿保绑定」survived（A7 2 证据 / A8 14 证据、0 降级）。

## 环境状态

- canonical 8792 = `190abf21`（#296 合并版），**未动**。
- 验证用 worktree `/Users/a77/.finance-runtime/finance-workspace-retryfix-3f2ed71e16e2`（8794 已停，worktree 保留）。
- 测试：coordinator+episode 89 passed、邻接 5 文件 144 passed、ruff 干净（云端 `/usr/bin/python3` + `FWP_ALLOW_ANY_PYTHON=1`）。

## 下一步

1. 用户审 #297 → 合并 → 切 8792 → 挑白天稳定时段重跑全 A 组做公平对照。
2. `repair_model_stop` / `invalid_repair_finish` 立案：30s 窗够到货了，卡在修复 FINISH 协议。
3. A3（`continuous_runtime_failed`，31s 无产物）与 A1-R2（主路径超时+零证据）两个形状仍待立案。
