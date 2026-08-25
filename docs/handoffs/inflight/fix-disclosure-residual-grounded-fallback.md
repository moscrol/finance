# fix/disclosure-residual-grounded-fallback

## 这个分支做什么

P1-① 残差写手 live R5 未过的止血刀：有据呈现器拒收时兜底骨架不得出稿（回 P0 纯包 + degrade `grounded_rejected`）；闸加复述判据（点名 >8 家整丢 `roster_renarration`）。全案见计划 §8 与 `~/.finance-runtime/cutover-20260825m-8792.md`。

## 当前状态

**生产已回滚 `54a6f096`（P0.5 版），健康、账本对齐。** main=`db7c5581` 含 P1-① 原样（有骨架出稿缺陷）——**本刀合入前不要把 8792 切回 main HEAD**。代码已完成待全量收据后提交开 PR。

## 下一步

1. 合本刀 → 切 8792 → 重放冻结题：预期公开稿=P0 纯包形状 + degrade `disclosure_residual_dropped:grounded_rejected`（残差安全空转）。
2. 残差真上场是 P1-①c：全行 claims/atoms（不走 `[:8]` 通用 builder）或披露专用 presentation profile；模型 raw_answer 质量可用，存证 `grounded_composer_shadow.json`。
3. 嫌空转贵（此题型多 ~35s 模型调用）：bind 放行条件收回 False 一行即关。

## 未验证 / 已知边界

- 本刀后冻结题未重放（等合并切码）。
- `/api/runs/{id}/trace` 端点只回粗粒度事件，查闸活性要读 run 目录 `trace.jsonl`。

## 已验证

ruff 绿；定向 25 条含新增复述闸与拒收源码断言；全量收据见提交信息。R5 探针全档案在 `~/.finance-runtime/disclosure-scan-p1-probe-20260825/`。

## 踩过的坑

- **有据呈现器的 claim 集也吃 `[:8]` 截断**——计划只预警了合成输入没预警 claim 集；对全名单解读题，claim 覆盖不足=必然拒收。
- 模型复述名单不带【档位】括号，名单行正则挡不住；复述判据要按 distinct 码数。
- 拒收兜底（spec 骨架）对确定性包题型比纯包差——「synthesis 非空」≠「模型写的」。

## 工具沉淀盘点

无新脚本。`ResidualGateResult` 走「认不出来就 fail closed」既有模式；「拒收兜底不得出稿」可视为该模式在合成层的应用，不另立条目。
