# fix/disclosure-residual-grounded-fallback（已收口：#397 已合、8792 已切、R5 重放通过）

## 这个分支做什么

P1-① 残差写手 live R5 未过的止血刀：有据呈现器拒收时兜底骨架不得出稿（回 P0 纯包 + degrade `grounded_rejected`）；闸加复述判据（点名 >8 家整丢 `roster_renarration`）。全案见计划 §8 与 `~/.finance-runtime/cutover-20260825m-8792.md`（失败轮）/ `…n-8792.md`（本轮收口）。

## 当前状态

**已收口（2026-08-25 晚）。** #397 已合（merge `a6a269e5`），8792 已从回滚位 `54a6f096` 切到 `a6a269e59e06`：T+153s healthy / dirty=false / match=true / readiness 13/13，账本 record+check 对齐。冻结题 R5 重放**通过**（`run_20260825_222216_702341`）：公开稿=P0 纯包形状（骨架 0 命中）、名单 35 行全部包内且主 24 行零删除、report 带 `disclosure_residual_dropped:grounded_rejected`、trace 闸事件 `applied=true dropped=true`、shadow 存证模型真实产出 2541 字符后被拒收丢弃。P1-① 进入安全空转（公开稿恒=P0 纯包，此题型多一次 ~15s 模型调用）。合并闸：ruff 绿 + 全量 6497P/0F/12S（`787235d6` 干净树本体；merge commit 与其零 diff）。

## 下一步

1. **P1-①c（残差真上场的前置）**：全行 claims/atoms（不走 `[:8]` 通用 builder）或披露专用 presentation profile；模型 raw_answer 质量可用，存证 `grounded_composer_shadow.json`。
2. 排查 judge 侧 zhipu URLError（`judge_unavailable`，m/n 两轮同形；composer 同 provider 调用成功，疑 judge 端点/超时问题）。
3. 嫌空转贵：bind 放行条件收回 False 一行即关。

## 未验证 / 已知边界

- `/api/runs/{id}/trace` 端点只回粗粒度事件，查闸活性要读 run 目录 `trace.jsonl`。
- 拒收根因（answer_spec claim 集 `[:8]` 截断）未修，属预期——修它就是 P1-①c。

## 踩过的坑

- **有据呈现器的 claim 集也吃 `[:8]` 截断**——对全名单解读题，claim 覆盖不足=必然拒收。
- 模型复述名单不带【档位】括号，名单行正则挡不住；复述判据要按 distinct 码数。
- 拒收兜底（spec 骨架）对确定性包题型比纯包差——「synthesis 非空」≠「模型写的」。
- **R5 探针必须走对话入口**（`POST /api/conversations/{id}/messages`，skill_mode=auto）：裸 `POST /api/runs` 是独立旧入口 `_run_ask`，不建 task_frame、不走披露扫描包（误发样本 `run_20260825_221628_021184`，不算 R5 证据）。
- `test-receipts/latest.json` 是单槽，多 agent 并行互相覆盖；合并闸读数以终端原始输出留证。

## 工具沉淀盘点

无新脚本。`ResidualGateResult` 走「认不出来就 fail closed」既有模式；「拒收兜底不得出稿」是该模式在合成层的应用，不另立条目。
