# 预测台账首批逐条分诊

任务：FINANCEWORKS-10；父目标见 `docs/superpowers/specs/2026-10-03-harness-quality-closeout-spec.md`。本批只按已存在的证据处置，未启动模型或生产 canary。

## 裁决

| 编号 | 原验收要求与已查证据 | 本批处置 |
|---|---|---|
| R-20260804-10 | 原预测要求 slow-tool handoff 离线主门全部通过，再做一次瑞华泰 canary；`docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0 明确取消 Task 3–6，因为它服务 benchmark_only 的 headless 路径，主线转工具面诊断。台账后续多次重申 Task 1/2 完成不能代签完整预测 | `expired`：依既有取消决定未验证关闭。保留完整预测和恢复条件；不是 confirmed、refuted 或质量改善 |
| R-20260815-03 | 要用原 6 个 run 的冲突夹具证明 answer_coverage/structural_verifier 同判据；台账后续记录只处理缺口模板一类，未统一判据、夹具未齐，不能代签 | 保持 pending；重验队列：先定位 6 个原 run/夹具，核对两判据输入与输出，再决定可复验或因材料不可恢复而明确关闭 |
| R-20260815-04 | 字段存在性测试且 ≥3 个同形空稿样本；08-16 仍无 draft_source，08-18 的 28 个 completed 样本没有空稿，均不满足条件 | 保持 pending；重验队列：固定候选版本定位空稿样本，核对 draft_source/remaining_ms；没有同形样本不能用正常 completed 代替 |

## 范围与剩余

起始 102 条过期待处理，本批处置 1 条，剩余 101 条仍须逐条核证。全部条目的原“怎么验”和可能的后续提及已保存在本机 `~/.finance-runtime/harness-quality-closeout-1003/ledger-worksheet.json`；关键词归类只是检索提示，不是裁决。

未把长期 pending 批量改成 confirmed，也未改其余假设或冻结 fix_type 枚举。后续优先检查“有后续证据但台账漏回写”及“已明确取消/被替代”的条目；需要真实样本的保留原样本量、入口与预算要求。

复核原件：`ledger-status.json` / `ledger-status-after-batch1.json`，以及只修改一条 outcome 的 Git diff。正式任务仍 in_progress。
