# feat/eval-variance-baseline

## 这个分支做什么
W7：同 rev 同题 N 次翻转率基线 + A/B 方差门，避免 N=1 探针被当成回归。

## 当前状态
已实现未推。基线 `b42a82d6`。规格写的 `docs/learning/acceptance-workflow.md` 不存在，规则写进 `docs/workflows/acceptance-workflow.md`，learning 下只留指针。

## 已验证
`intelligence/tests/test_eval_variance_baseline.py` 4 passed：`--help`；fixture replay 翻转率 0.2；`ab_decision(0.05, 0.2)==no_call`；`--live --port 8792` exit 2。

## 未验证 / 已知边界
- 未 live，无 `441c60f2` 真基线。`~/fwp-wt-live-verify/state/live-verify/20260819T06*` 不存在。
- 仓内收据 `intelligence/eval/runs/20260819T080000Z-fixture-var5.json`：`live=false` `fixture=true`。
- 与 W2 未共存：判官桶现用 `judge_status ∈ {unavailable, None}` / timeout。

## 下一步
对 `441c60f2` sidecar（端口 8796，禁 8792）：
`python scripts/eval_variance_baseline.py --live --rev 441c60f2 --n 5 --port 8796`
同 rev 同题，勿跨修复混跑。合 main 等用户确认。

## 踩过的坑
翻转率只能同 rev 同题复跑。`judge_unavailable` 造成的 degraded 会抬高 `baseline_flip_rate`；内容对照用 `content_flip_rate`。

## 工具沉淀盘点
脚本防「N=1 当回归」。方法论已在 `eval-harness-variance-governance.md`。未改 `~/harness-reference/KIT.md`（仓外，合入后再挂）。
