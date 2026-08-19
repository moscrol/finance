# P0 基线审阅收据 — Workbench runtime hardening

- 日期：2026-08-19
- 审阅树：`/Users/a77/fwp-wt-runtime-hardening`（干净 worktree，不碰主仓脏树）
- 分支：`feat/workbench-runtime-hardening` ← `gitea/main`
- revision：`882498573bb24ad493e07ea17bbd7b8c6d49d6a8`
- 第一轮：只读。本文件是审计，不是实现。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13）

主仓 `feat/reading-rules-baseline-batch1` 有他人未提交改动，spec §12.8 禁止混入。本轮全部证据都在这棵干净树上。

## 0. 定向测试

命令（cwd = 本 worktree）：

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_seam_ladder.py \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_p1b_runtime.py \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_progress.py
```

| 项 | 值 |
|---|---|
| 结果 | `259 passed in 2.33s`，exit 0 |
| 机器收据 | `~/.finance-runtime/test-receipts/20260819T123804Z-88249857.json` |
| 采信 | 在本 worktree 上 `check_test_receipt.py` → 可采信（`dirty=false`） |
| 原 spec 四文件 | 在 `gitea/main` 上 collect 为 **136** 条，不是 spec 写的 127 |

spec §1.7 的 `127 passed @ 78391e8e` 是阅读规则分支上的读数，**不是**本实现基线。本轮以 88249857 / 259 为准。

## 1. 与 spec 的冲突（先报告，不改实现）

这些不是「缺能力」，是词汇或基线对不上。P1 必须顺着已有投影走，不要再发明第四套状态枚举。

### C1. 三套终态词表，spec I1 对齐的是投影层

| 层 | 类型 | 词表 |
|---|---|---|
| Episode 内核 | `EpisodeStatus`（`agent_runtime.py`） | `completed \| partial \| clarification \| failed`。取消 = `failed` + `stop_reason=cancelled` |
| Adapter 交付 | `ContinuousTurnStatus` | `completed \| partial \| degraded \| failed` |
| Run 持久化 | `run_store` | `queued \| running \| completed \| failed \| cancelled`。`degraded` 在 `run.degrades[]`，不是 status |
| **对外合流** | `status_projection._EPISODE_STATUSES` | **`completed \| partial \| degraded \| failed \| cancelled`** ← 与 spec I1 一致 |

人话：同一场比赛有三块记分牌（内核 / 交付 / 落盘），再加一块「对外翻译」。spec 的终态枚举已经是翻译层，不是内核 `EpisodeStatus`。P1 的 `EpisodePhase` 终端应复用 `status_projection`，不要改 `AgentOutcome.status`。

`clarification` 只存在于内核/TurnControl；adapter 在进 Episode 之前就以 `status=completed` 返回。spec `EpisodePhase` 没列它——映射为进 loop 前的早退，不单开一相。

### C2. 投影栈已存在，禁止另起事件日志

gitea/main 已有四层，spec 预审表没写（预审对着另一棵树）：

| 模块 | 职责 | fail 策略 |
|---|---|---|
| `episode_event_lanes` | Durable / Live 分类表 | 发射未登记 kind → 抛错 |
| `episode_projection.project_durable_events` | artifact `events[]` 唯一口径 | 未登记 kind **保留**并记 `unregistered_kinds` |
| `episode_progress` | 对用户的进度文案（无预算字段） | 未知 kind → `None`（UI 沉默） |
| `status_projection` | episode / run / report / transport 三份 status 唯一投影 | 未知 → `failed` |

P1 必须是**第五个 sidecar 投影**（审计用 phase 序列），写入 `private_artifact`，**不**进 `DURABLE_EVENT_KINDS`，不改 `events[]` 形状。Live→Durable 是加法、Durable→Live 破坏重放——这条已经写在 `episode_event_lanes.py` 头注释里。

### C3. `finish` 事件 ≠ 公开终态

`resume()` 在同一 ledger 上追加事件，所以一次成功 repair 的历史里可以有**多条** `finish`。`EpisodeSession` 用「只增、前缀相等」守这条。若把每条 `finish` 当成 I4 终态，所有成功 repair 都会被误判「终态后仍有写入」。

公开终态是 adapter 返回的 `ContinuousTurnStatus` → `status_projection` → `claim_terminal_run`。P1 投影必须把中间 `finish` 留在 `finalizing`，只把最后一次公开 outcome 标成终端。

## 2. 当前状态图

```text
TurnControl
  ├ clarification ──► adapter completed（不进 Episode）
  ├ deterministic fast path ──► ContinuousTurnStatus
  └ research
        ContinuousAgentEpisode.run
          planning (task/plan/mode_decision)
            → research (model_turn / tool_* / branch_*)
            → finalizing (tools=[]；可 finalization_recovery)
            → finish  (EpisodeStatus；可被 resume 后续再写)
        adapter
          structural_verify
            → [repair loop / backfill] ──► session.resume ──► 又一段 research/finalizing/finish
          semantic_verify   （deadline.synthesis_timeout；不 debit remaining_calls）
            → [repair loop] ──► resume ──► 再 verify
          公开 ContinuousTurnStatus
        orchestrator
          project_artifact_statuses
          claim_terminal_run          ← run 层唯一终态
          revise_message              ← 紧挨 claim，中间不准插 artifact IO
          add_artifact                ← 有意在 claim 之后
```

公开进度阶段（`episode_progress._PROGRESS_STAGES`，给 UI 的，不是审计状态机）：

`understanding | planning | research | repair | verification | finalizing`

审计要的 `structural_verify` / `semantic_verify` 目前**折叠**在 `verification` 文案里，durable 事件里没有对应 kind。

## 3. 当前预算图

```text
ResearchPolicy          静态档位（tier / max_steps / total_seconds / synthesis_reserve）
        │ root_budget_for_policy()
        ▼
InMemoryRootBudgetLedger
  initial_calls = policy.max_steps
  hard_calls_cap = max(max_steps, tier表 quick=4/standard=8/deep=24)
  initial_seconds = total_seconds - synthesis_reserve
  hard_seconds_cap = total_seconds
  grant() 只能从 hard cap 未分配余量加水，不能恢复已消费
  promote_caps() 深档一次抬天花板，不另开 ledger

ResearchDeadline        绝对 monotonic expires_at
  stage_timeout()       检索：remaining - synthesis_reserve
  synthesis_timeout()   合成/语义 judge：可用剩余（含 reserve）
  bounded_stage()       子区间，不能从「现在」重新完整计时

消费点（root ledger）
  主模型轮     _consume_root_seconds
  工具批次     _settle_batch_calls → consume_call
  子研究       _BranchBudgetView 把消费打回 parent（grant 恒 False）
  repair 模型  _consume_root_seconds；瞬态重试可 grant_for_transient_model_retry
  cold restart grant_for_cold_restart（零证据 + 窗/模型饿死；cycle 1）

不走 remaining_calls 的时间片
  语义 verifier     只用 ResearchDeadline.synthesis_timeout
                    源码零 consume_call / 零 root_budget 引用
                    → 产品语义：judge 是 deadline 子授权，不是 call-budget 子授权
                    （P2 要用测试钉住，不能只靠「初始化时相等」）

槽位权威
  _remaining_tool_slots：有 root_budget 时完全听 remaining_calls，
  不与 policy.max_steps 取 min。隐含前提「ledger 是 policy 的投影」
  目前只靠 root_budget_for_policy() 维持。全仓唯一相关断言仍是
  test_run_agent_runtime_benchmark.py 里 initial_calls == 12。
```

## 4. 当前并发 / 取消 / 终态图

```text
取消
  orchestrator._check_cancelled → LLMStreamCancelled
  adapter.handle / _run_episode 多点 is_cancelled
  episode 主循环：模型前、模型后
  EpisodeToolBatchSession：提交前、等待中；取消则 future.cancel + guard.close(rollback=True)
  episode_tools.check_cancelled
  公开：run_store.STATUS_CANCELLED；Episode 内核仍是 failed+cancelled

终态认领
  claim_terminal_run(run_id, status) → (Run, claimed)   持锁、已终态则 claimed=False
  finish_run → 同一路径
  orchestrator._claim_terminal_run：未抢到 → RunTerminalClaimLost
  连续研究路径：claim → revise_message → add_artifact（注释写明为何这个顺序）
  ask / skill / 取消路径：有的先 add_artifact 再 finish_run

add_artifact 自身不看 run.status
  连续路径靠「没抢到 claim 就抛错」挡住输家后续写入
  缺口：任何绕过 _claim_terminal_run 的 add_artifact，终态后仍能改公开文件
  调用方还包括 api/app.py、workbench_skills/*

late result
  QueryPublishGuard：关后丢弃晚到结果，允许重试（test_p1b_runtime）
  工具批次创建并 close 自己的 guard
  无 late_result_discarded 事件名；诊断靠 guard 关 + 不写入 ledger
  未证明：repair provider 晚到、sub-research 晚到是否都经过同一 guard

进程恢复
  进程内：EpisodeSession.resume（活 provider 历史闭包）——已测
  进程外：requeue_incomplete_runs 只是把 queued/running 打回 queued
           不恢复 messages / ledger / budget snapshot
           → capability gap，不是没搜到
```

## 5. 不变量对照

| ID | 现状 | 证据 | 缺口？ |
|---|---|---|---|
| I1 状态收敛 | 行为上会停；不可从一份 phase 序列重建 | 无 `EpisodePhase`；进度与审计混在 `episode_progress` | 观测缺口（P1） |
| I2 预算单一真相源 | ledger 设计正确；一致性靠初始化 | `root_budget_for_policy`；无 `initial_calls == policy.max_steps` 通用测试 | 测试缺口（P2） |
| I3 deadline 单调 | `bounded_stage` / `stage_timeout` 存在 | `ResearchDeadline` | P2 要钉 timeout≤remaining |
| I4 终态唯一 | **run 层有**；Episode 内部写入与 child 晚到未闭环 | `claim_terminal_run` + 测试；`add_artifact` 无终态闸 | 覆盖边界（P3） |
| I5 repair 单调 | CoverageDelta + 空 draft 结转已有 | `progressed`；adapter ~修复不得倒退注释 | 缺 presentation 三分法字段（P1 观测） |
| I6 权限单调 | contract.allowed_capabilities 门控 | registry | 本轮不扩 |
| I7 事实/诊断分离 | durable vs live 已分；phase 审计未分出 | `episode_event_lanes` | P1 sidecar |

## 6. 缺口表（P0 冻结，执行时引用）

| ID | 缺口 | 位置 | 触发 | 当前行为 | 是否缺陷 | 最小复现 |
|---|---|---|---|---|---|---|
| G1 | 无审计用 phase 序列 | 无 `episode_phase` 模块 | 任何 Episode | 只有 UI 进度 + durable 事件 | 观测缺口 | 对 `outcome.events` grep 不到 `structural_verify` |
| G2 | verify 不在 durable 事件里 | adapter `_run_episode` structural/semantic 调用点 | 核验与 repair 交错 | 只能从 private_artifact 的 verifier 字典事后知道发生过 | 观测缺口 | scripted adapter 只有 `task` 事件仍跑完 verify |
| G3 | `initial_calls == policy.max_steps` 无通用测试 | `root_budget_for_policy` | 改初始化或 promotion | 只靠函数体维持 | 测试缺口 | `rg 'initial_calls == policy'` 空 |
| G4 | 语义 judge 不借记 remaining_calls | `episode_semantic_verifier.py` | 多次 rejudge | 只吃 deadline 合成窗 | **产品语义未钉**，不是漏接 | `rg consume_call episode_semantic_verifier.py` 空 |
| G5 | `add_artifact` 不检查终态 | `RunStore.add_artifact` | claim 失败的并发者若绕过 `_claim_terminal_run` | 可覆盖公开文件 | 覆盖边界；连续路径有例外闸 | 读 `add_artifact`：无 `_TERMINAL_STATUSES` 判断 |
| G6 | 无 `late_result_discarded` 统一口径 | 工具批次有 guard；repair/child 未举证 | 终态后晚到 | 丢弃但不记该事件名 | 审计缺口 | `rg late_result_discarded intelligence/` 空 |
| G7 | 进程重启不能续 Episode | `requeue_incomplete_runs` | 进程死在 repair 边界 | 重排队，不恢复 ledger | **声明为不支持**，不要伪造 | 无 messages/budget snapshot 字段 |

G5/G6 按 spec 第三轮才修：先有观测收据证明绕过，再改行为。

## 7. 建议进入 P1–P5 的顺序

1. **P1（本轮即可）**：`intelligence/services/episode_phase.py`，仿 `episode_projection`（sidecar + anomalies 进收据，发射不抛、不改主路径）。`PhaseRecorder` 接在 adapter 的 structural / repair / semantic 点上，因为纯事件投影排不出 verify↔repair 交错。禁止新 durable kind。
2. **P2**：通用不变量测试（initial_calls、deep promotion、grant≤未分配余量、timeout≤deadline remaining、usage 对账）。顺手钉 G4「judge 不计 call」。
3. **P3**：只审计/补齐覆盖。不重写 `claim_terminal_run` / `QueryPublishGuard`。先证明 G5/G6 的绕过路径再加闸。进程重启保持「不支持」。
4. **P4/P5**：等 phase + budget 收据能重建后再做 SLO / fault matrix。

## 8. 符号索引（gitea/main @ 88249857，行号会漂）

| 符号 | 文件 |
|---|---|
| `ContinuousAgentEpisode.run` / `_remaining_tool_slots` / `_begin_finalization` | `intelligence/runtime/agent_episode.py` |
| `MAX_EPISODE_TOOL_CALLS=24` `MAX_PLAN_TURNS=2` | 同上 |
| `ContinuousTurnAdapter._run_episode` / `_resume_for_gap` | `intelligence/runtime/continuous_turn_adapter.py` |
| `EpisodeFinalizer` | `intelligence/runtime/episode_finalizer.py` |
| `SubResearchCoordinator` / `_BranchBudgetView` | `intelligence/runtime/sub_research.py` |
| `TurnOrchestrator._claim_terminal_run` | `intelligence/runtime/conversation_orchestrator.py` |
| `ResearchDeadline` `ResearchPolicy` `InMemoryRootBudgetLedger` `root_budget_for_policy` | `intelligence/services/research_contract.py` |
| `CoverageDelta.progressed` `grant_for_cold_restart` | `intelligence/services/repair_coordinator.py` |
| `claim_terminal_run` `add_artifact` `requeue_incomplete_runs` | `intelligence/services/run_store.py` |
| `QueryPublishGuard` | `intelligence/services/query_ledger.py` |
| `project_artifact_statuses` | `intelligence/services/status_projection.py` |
| `DURABLE_EVENT_KINDS` | `intelligence/services/episode_event_lanes.py` |
| `EpisodeSession.resume` | `intelligence/services/episode_session.py` |
