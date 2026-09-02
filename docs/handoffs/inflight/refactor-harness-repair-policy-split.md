# 在途交接 · refactor/harness-repair-policy-split

更新：2026-09-02 · **五个提交在本地，未推、未开 PR。** 叠在 `spec/harness-repair-policy`
（PR #531，含状态机 spec + 删 mode 转交壳）之上；#531 合入后本枝只剩自己的 diff。

## 一句话

`repair_policy` 实施的前四刀：把「什么时候允许再来一轮」（预算）和「修什么 / 属哪类 /
算不算进步」（领域）从**同一个函数**里拆开（M1–M4），领域失败分类从 adapter 搬回
services（M6），预算算术与授予入口从 services 搬到 `runtime/repair_budget.py`（M5），
修复轮**执行体**里最后两段领域内容抽成 harness 方法（`repair_goal_message` /
`admit_repair_result` + `repair_finalize` 时点；协议 10 → 12 方法）。
**零行为改动**：五种授予的 `grant_id` / `cycle` / `calls` / `seconds` 逐字段与拆分前
`fed88564` 实跑金标相同；admit_repair 收到的三个 candidate bool 1008 格逐格相同；
修复轮的 REPAIR_GOAL / 收口指令字节相同，48 格裁决逐格相同。

spec：`docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md`（头部「实施进度」随每刀回写）
父线：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §9 最后一条 P2

## 提交

| SHA | 刀 | 改动面 |
|---|---|---|
| `e4657a11` | M1–M4 | `should_reenter` → `repair_is_warranted` ∧ `can_afford_repair`；`work_units` → `repair_work_units` × `calls_for_work_units`；`grant_for_progress` 三行编排；`_mint_grant` 唯一记账点。`should_reenter` 删除（生产只有一处用，测试一处改） |
| `8cc02f1f` | M6 | `classify_repair_failure(outcome, structural, *, missing_outputs, rejected_claims, semantic_gap_outputs) -> RepairFailureShape{delivery, cold_restart, contract_rewrite}`；两个 stop_reason 集合原字面搬入 services 并转公开；adapter 只叠 `allow_delivery_repair`（cycle 状态） |
| `fb0666aa` | M5 | 新 `intelligence/runtime/repair_budget.py`（527 行原文搬入）；`services/repair_coordinator.py` 只剩领域侧 393 行、不再 import `RootBudgetLedger`；六个测试 + adapter + episode 改 import；switchboard `repair-chain` seam 同步 |
| `0866b047` | 交接 | 本文档首版 |
| （本提交） | §4 执行体半 | `ResearchHarness.repair_goal_message(goal, *, tools_open)` / `admit_repair_result(*, admission, previous, performed_tool_action) -> RepairVerdict`；`SteeringKind` 加 `repair_finalize`；`agent_episode.resume()` 三处改走 harness，不再含任何领域文案或「算不算修好」判定；`test_research_harness.py` 第 7 节 6 例（字节等价 / 48 格裁决 / 拒收未接受 admission / 两条有牙 / 棘轮） |

## 现在的层次（对照状态机 spec §4）

```
services/repair_coordinator.py   领域：值对象 / build_repair_goal / unreachable_repair_goal /
                                 max_repair_cycles_for_tier / cycle_within_tier /
                                 repair_is_warranted / repair_work_units / classify_repair_failure
runtime/repair_budget.py         底座：can_afford_repair / calls_for_work_units / size_repair_window /
                                 _mint_grant / grant_for_* ×5 / admit_repair / admit_backfill_repair
runtime/continuous_turn_adapter  编排：算 tools_open / remaining_* → 问 classify → admit_repair → resume
runtime/agent_episode.resume()   执行体：问 harness 要 REPAIR_GOAL 文案 / repair_finalize 收口 / RepairVerdict；
                                 瞬态重试、deadline 构造、_carry_repair_finish（围着 admit_finish 的两行取舍）留 loop
services/research_harness.py     12 方法；修复相关两个的默认实现是 resume() 原文逐字搬入
```

`grant_for_progress` 内部仍直接调 `repair_is_warranted`——领域判据被底座**调用**而不是**被告知**。
这是 §4 准入那一半要翻的方向：harness 出 `RepairNeed`，底座据此铸窗。adapter 现在**不持有
harness**（harness 在 `glm_agent_runtime.py:508` 构造后直接进 Episode），所以准入半要先决定
adapter 怎么拿到它——建议构造注入 `harness: ResearchHarness | None = None`，与 P1a 给另两条
loop 的做法同形；`api/app.py:483` 是唯一生产构造点。

## 验证（venv 解释器 `.venv-workbench/bin/python`，cwd 本树）

- `test_repair_policy_split.py` 38 例：360 格 `should_reenter` 网格（40 放行）、336 格 work_units、
  1008 格失败分类、30 组授予金标、AST 棘轮（adapter 不再持有两个集合 / 不 import
  `is_contract_rewrite_only`）。
- `test_research_harness.py` 第 7 节 6 例：REPAIR_GOAL 两分支 + `repair_finalize` 字节等价；
  48 格 `admit_repair_result` 对 resume() 原三元判定逐格相等；拒收未接受的 admission；
  自定义 harness 的两段话真到模型眼前；同一份「没动手、稿没改」的修复轮默认判
  `repair_model_stop`、改判 harness 让它 `repair_model_finish`（outcome 变，不是日志变）；
  源码棘轮（七个字面量 / 变量名不得回焊）。
- 变异四次全红后恢复：`_MAX_REPAIR_CALLS` 4→5（红 2）；`repair_is_warranted` 去 progressed 闸
  （红 4，含 `test_repair_invariant_regression`）；`cold_restart` 去零证据闸（红 1——adapter 81 例
  不红，因 `admit_repair` 的 `evidence_count == 0` 双保险吞掉差异，正是分类器需要自己那道钉的原因）；
  loop 忽略 `verdict.progressed` 改按 `performed_tool_action` 定 stop_reason（红 4，含
  `test_agent_episode` 两条既有用例）。
- 宽网 `-k "repair or episode or harness or glm or sub_research or continuous or runtime or adapter
  or track_contract or conformance or switchboard or provider_latency or profile or steering or protocol"`
  1979P/5S/1xfail。
- ruff 全过；`layer_audit` ERROR 0 == 基线；pre-commit 十一道门禁每次全过。

## 未做（按序）

1. **§4 准入半 + M7**：`ResearchHarness` 加 `classify_repair_need` / `repair_is_warranted`；
   `admit_repair` 改收 `RepairNeed`（`reopen_tools` 从搭便车字段变 `needs_tools` 具名申请）；
   `repair_budget.grant_for_progress` 从「调 `repair_is_warranted`」改成「被告知」；adapter 构造注入
   harness（`api/app.py:483` 唯一生产构造点）。有牙判据（状态机 spec §5 第 2 条）：换一个
   `repair_is_warranted ≡ False` 的 harness，`repair_cycles` 归零；换一个只报 delivery 的分类器，
   冷启动路径不再触发——两条都看 outcome。
2. **`HarnessReferenceLoop.resume` 真跑一轮**——spec §5 第 5 条的可判定读数；P2'-live 的
   `model_finish` vs `repair_model_stop` 差随之消掉。现在 harness 已有修复轮所需的全部领域方法
   （文案 / 收口 / 裁决），参考 loop 缺的只是底座那半（deadline 构造、瞬态重试、工具批）。
3. `_recover_finalization` 是否并进 repair cycle：独立决定，需用户拍。

## 顺手发现（不属本单）

- `services/mode_governor.py:273` 升档授予在领域层直接 `root.grant()`，与 M5 同一种错层，归
  `govern_mode` 线。
- `intelligence/eval/fixtures/capability_switchboard.json` `repair-chain` 行 notes 里的
  `repair_coordinator.py:36-42 / :328 / :343-346` 是搬前坐标，已追加一句说明，未重写历史文本。

## 红线遵守自证

- `episode_protocol.py` 零改动；`agent_episode.py` 改动限于一行 import + `resume()` 三处改走
  harness（文案与判定逐字搬入 `research_harness.py`，事件 payload 键与顺序不变）；
  8792 / 启动器 / 快照未碰。
- 提交一律 pathspec，未 `git add -A`。合 main 等用户确认。
