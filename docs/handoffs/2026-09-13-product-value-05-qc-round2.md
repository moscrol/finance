# 2026-09-13 · 05 product_value QC 第二轮（PV4/PV5）修复快照

## 背景

QC 第二轮（`~/.finance-runtime/reviews/research-evolution-repair-qc-20260913/`，review.md + spec_03_05_review.md）确认：上一轮修复让原 13 项固定反例转绿，但扩大边界后确证 8 项问题，05 占 2 项 P1。本轮只改实现与测试，不合并 main。修复提交 `24bce5e8`（父 `7c7c388b`）。

## 按发现顺序

1. **PV4[P1] 空壳收据核销缺口**：`summarize.py` 的 `measured_task_ids` 只查 task_id 是否出现在任一收据的 `tasks` 里。只有分配、没有耗时/尝试/费用的空壳收据（`measure_pair` 对仅 consent+assignment 的事件流产出 `status=incomplete`、`attempts=[]`、`timing.reason=no_timing_evidence`、`cost_items=[]`）会把 `unmeasured_task` 缺口核销，完整成本从 unknown 洗成 known（探针：unknown_component_count 2→0，CNY 仍 0.46 却判 known）。
2. **PV5[P1] 后续窗口收缩分母**：复用分母取每人最晚 `observation_window.end`；给已完成首轮观察周的人追加一个未结束的后续窗口，他们被移出分母——2/6 fail 变 2/3 pass。本轮新回归，上轮总结未覆盖。

## 决策与方案对比

| 决策 | 选了 | 否了 | 为什么 |
|---|---|---|---|
| PV4 判据 | `_receipt_task_is_measured`：终态≠open / attempts 非空 / timing.reason 为 None，三者有其一才算被测量 | 按 `receipt.status` 整票判 | 单独质量漏审也产 incomplete，整票判会把真测量误杀；QC 明确不建议 |
| PV4 缺口分列 | 「无收据」`no_measurement_receipt_for_assigned_task` 与「收据在但没测」`measurement_receipt_without_task_evidence` 两种 reason | 共用一个 reason | 补的动作不同：前者补测量流程，后者该收据对应任务根本没有可入账观察 |
| PV4 原流程无模型费用 | 由收据自己的 cost_items / unknown_cost_components 表达 | 靠收据存在性顶替 | spec §3/§4：未观察到调用不作零费用依据 |
| PV5 资格 | `completed_window_end`（只收窗末 ≤ as_of 的窗），资格 = 任一完整窗 | 沿用最晚窗末 | spec §4 分母是「激活后进入完整观察周者」；§3 失败/退出不能为改善读数删除 |
| PV5 后续窗 | 另列 `later_observation_window_incomplete`（仅对已在分母者） | 静默跳过 / 剥夺资格 | QC：「把后续窗口的缺测另外列明」；只有未来窗的人仍走 `observation_window_incomplete` 不进分母（既有测试 p20 锁） |

## 验证与收据

- 新增 2 条回归测试先红后绿：`test_shell_receipt_without_task_evidence_keeps_cost_unknown`、`test_later_unfinished_window_does_not_shrink_reuse_denominator`（`intelligence/tests/test_product_value_summarize.py`）。
- 本轨 110 passed；全仓 9650 passed / 77 skipped / 2 xfailed（386s）；ruff 干净。
- QC 探针 `probe_05_extra.py` 复跑（修后）：PV4 with-stub 的 full_cost_status=unknown、known_cost={'CNY': 0.46}、unknown_count=2，与 without-stub 完全一致；PV5 after 分母 q1..q6、value 0.3333、unknowns 逐条列 q4/q5/q6 `later_observation_window_incomplete`。探针输出快照 `/tmp/probe05_after.json`（临时，复核请重跑探针）。

## 后续要做 / 不要做

- 要做：06 用 `24bce5e8` 联测；合并 main 等用户确认，合前跑等价 CI（含前端）。
- 不要做：不要把 `_receipt_task_is_measured` 放宽成「有 receipt 即 measured」——那是 PV4 病灶本身；不要把 `later_observation_window_incomplete` 加进判据 gating（它只列示，gating 仍只看 `reuse_observation_missing`）。

## 口径纠偏（用户要求）

- 上轮口头汇报「13 项已修复」→ 准确口径「原 13 项固定反例转绿」，扩大边界后 QC 又确证 8 项。
- 上轮「41 条测试先红后绿」不准确：至少 `test_consented_pairs_still_reach_a_verdict` 修前修后都绿。
- 各轨交接引用的 `docs/superpowers/summaries/2026-09-13-*.md` 从未落盘；总结以交接 + commit message + 本快照为准。

## 上轮遗留坑（从 inflight 挪存）

- CLI 把无配对号事件附给每一对 → `orphan_task_events` 误报，已改为只对带本配对号的事件判孤儿。
- zsh 里 `${PIPESTATUS[0]}` 为空，记退出码用 `$?` 紧跟命令。
