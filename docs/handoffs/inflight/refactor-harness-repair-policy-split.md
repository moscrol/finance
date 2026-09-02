# 在途交接 · refactor/harness-repair-policy-split

更新：2026-09-02 · **`repair_policy` 线实施完毕，状态机 spec §5 五条验收全闭。九个提交已推 gitea，
PR #532（叠 #531）。合 main 等用户确认；8792 未切。**

## 一句话

按 `2026-09-02-repair-policy-state-machine.md` 把修复轮的**预算边与领域边**彻底拆开：七处混合
（M1–M7）各归其位，`ResearchHarness` 从 10 方法到 15 方法（修复轮五个：申请两个 / 不可达裁决 /
开场话 / 修完算不算数），预算算术整体进 `runtime/repair_budget.py`，adapter 与 Episode 都只问
harness，`HarnessReferenceLoop` 从「没有修复轮」变成「与 Episode 在同一段历史上各修一轮、消息 /
事件 / outcome 一致」。**零行为改动**：每一刀都用拆分前 `fed88564` 的实跑金标或网格逐格钉住，
共变异六次全红后恢复。

spec：`docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md`（头部「实施进度」+「§5 五条验收现状」）
父线：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §5 协议（十五方法）/ §9 P2

## 提交（按序，均叠在 #531 的 `fed88564` 上）

| SHA | 刀 | 改动面 |
|---|---|---|
| `e4657a11` | M1–M4 | `should_reenter` → `repair_is_warranted` ∧ `can_afford_repair`；`work_units` → 格数 × 换算；`grant_for_progress` 三行编排；`_mint_grant` 唯一记账点 |
| `8cc02f1f` | M6 | 三个 candidate 判据 + 两个 stop_reason 集合从 adapter 搬进 `services/repair_coordinator.classify_repair_failure -> RepairFailureShape` |
| `fb0666aa` | M5 | 新 `runtime/repair_budget.py`（五种 `grant_for_*`、两个 `admit_*`、预算算术）；`services/repair_coordinator.py` 只剩领域侧 |
| `0866b047` | 交接 | 本文档首版 |
| `3df916c2` | §4 执行体半 | harness 加 `repair_goal_message` / `admit_repair_result`（→12）；`SteeringKind` 加 `repair_finalize`；`resume()` 三处改走 harness |
| `6b68c98b` | 交接 | 补 SHA |
| `5288d4c4` | §4 准入半 + M7 | `RepairNeed`（+ `needs_tools`）/ `RepairWarrant`；harness 加 `classify_repair_need` / `warrant_repair`（→14）；`repair_budget` 改为**被告知**；adapter 构造注入 harness（`api/app.py` 零改动） |
| `d9b46afa` | 不可达降级 | harness 加 `downgrade_unreachable -> RepairDowngrade`（→15）；Episode 与 adapter 都问它；Episode 从 `repair_coordinator` 只剩 `RepairGoal` |
| `fa5e162a` | 参考 loop | `ReferenceLoopState` + `_ingest_batch` + `resume()` 一轮修复；与 Episode 同一台机器 |

## 现在的层次

```
services/repair_coordinator.py   领域：值对象（RepairGoal / RepairNeed / RepairWarrant / RepairFailureShape …）
                                 build_repair_goal / unreachable_repair_goal / tier·进度·格数判据 /
                                 classify_repair_failure / classify_repair_need / warrant_repair
services/research_harness.py     15 方法；修复五方法的默认实现是 resume() / adapter 原文逐字搬入
runtime/repair_budget.py         底座：can_afford / calls_for_work_units / size_repair_window / _mint_grant /
                                 grant_for_* ×5 / admit_repair(need, warrant, …) / admit_backfill_repair
                                 —— 只读申请，不 import 任何领域判据
runtime/continuous_turn_adapter  编排：算余量 → 问 harness 要 need / warrant → admit_repair → resume →
                                 按 harness 降级后的契约验
runtime/agent_episode.resume()   执行体：问 harness 五件事；deadline·瞬态重试·工具批·_carry_repair_finish 留 loop
runtime/harness_reference_loop   第二条 loop：run + resume，只调 harness + ToolBatchExecutor
```

授予协议落地：**领域申请（`RepairNeed` / `RepairWarrant`），底座授予（`_mint_grant` 是修复线唯一
`root_budget.grant()` 调用点），领域不碰账本。** M7 的 `reopen_tools` 从 goal 上搭便车的 bool 变成
`RepairNeed.needs_tools` 申请 + 底座 `grant_for_cold_restart` 批准后盖章。

## 与状态机 spec §4 建议签名的两处差（有意）

- `repair_is_warranted -> bool` 改成 `warrant_repair -> RepairWarrant{cycle_allowed, progressed}`：交付
  修复只需 tier 闸不需进度闸，两个事实得分开摆。`repair_is_warranted` 仍在 services 作 bool 便写。
- `classify_repair_need` 不返回 `None`：等价优先；「不值得修」由 shape 全 False + 进度闸表达，与拆分前
  `admit_repair` 的分流逐格相同。

## 验证（venv 解释器 `.venv-workbench/bin/python`，cwd 本树）

- `test_repair_policy_split.py` 38 例：360 格 `should_reenter`、336 格 work_units、1008 格失败分类、
  30 组授予金标、AST 棘轮（adapter 不 import 六个判据符号、必经 `self._harness.*`）。
- `test_research_harness.py` 第 7 节 8 例：REPAIR_GOAL / `repair_finalize` 字节等价；48 格裁决；不可达
  裁决三形状逐字段等价；有牙三条（自定义话真到模型眼前；改判 harness 让 stop 变 finish；不降级 harness
  让 trace 无 `unreachable_without_tools`、模型仍看到那个格）；棘轮（Episode 从 `repair_coordinator` 只
  import `RepairGoal`、不 import `mandatory_satisfiability`）。
- `test_continuous_turn_adapter.py` +4：`warrant_repair ≡ 不容忍` → `repair_cycles` 1→0；只报 delivery 的
  分类器 → 冷启动窗不出现（均看 outcome）。
- `test_harness_reference_loop.py` 6 → 9：零额度修复轮 / 带额度修复轮两条 loop 消息、`repair_goal` 事件、
  outcome 一致；修复失败结转上一轮稿。
- 变异六次全红后恢复：`_MAX_REPAIR_CALLS` 4→5（红 2）；去 progressed 闸（红 4）；冷启动去零证据闸
  （红 1）；loop 忽略 `verdict.progressed`（红 4）；`admit_repair` 忽略 warrant（红 8）。
- 宽网 `-k "repair or episode or harness or glm or sub_research or continuous or runtime or adapter or
  track_contract or conformance or switchboard or provider_latency or profile or steering or protocol or
  fault or satisfiab or reference"` **2160P / 5S / 1xfail**；ruff `intelligence/` 全过；`layer_audit`
  ERROR 0 == 基线；pre-commit 十一道门禁每次全过。

## 下一步（按序）

1. 用户确认 → 先合 #531，再合 #532（叠着的；#531 若 squash 合入，#532 需 rebase）。
2. 合后 8792 切流时带上（零 live 判据，与前六张 PR 同纪律）。若想复现 P2'-live 第四臂：
   `finance-base-ab/shape_lib/reference_loop_arm.py` 里「resume 抛无修复轮」的壳改调
   `HarnessReferenceLoop.resume`（实验树，本仓不动）；预期 Episode 臂 `repair_model_stop` 与参考 loop 臂
   的差不再是「没有修复轮」造成的。
3. **`fallback_after_empty_batch`**（decouple spec §4 #8）：与 `repair_policy` 同为「持状态、改控制流」，
   先画状态机再抽。`_maybe_execute_empty_pool_fallback` 在 `agent_episode.py`，`empty_pool_fallback.py` 253 行。
4. `_recover_finalization` 是否并进 repair cycle：独立决定，需用户拍。

## 顺手发现（不属本单）

- `services/mode_governor.py:273` 升档授予在领域层直接 `root.grant()`，与 M5 同一种错层，归 `govern_mode` 线。
- `intelligence/eval/fixtures/capability_switchboard.json` `repair-chain` 行 notes 里的旧 file:line 是搬前坐标，
  已追加一句说明，未重写历史文本。

## 红线遵守自证

- `episode_protocol.py` / `evidence_ledger` / verifier 判定零改动；事件 payload 键与顺序不变（Episode 三处
  只是改从 harness 取值）；`api/app.py` / 8792 / 启动器 / 快照未碰。
- 未放宽任何闸门：`unreachable_repair_goal` 原样；A→B→C 优先级链原样；`_TRANSIENT_RETRY_LIMIT` 原样。
- 提交一律 pathspec，未 `git add -A`。合 main 等用户确认。
