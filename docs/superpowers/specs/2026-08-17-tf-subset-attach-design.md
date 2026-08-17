# 设计：吸收前底座上只接 EpisodeScope + 工具阶段

日期：2026-08-17
状态：设计稿，待用户审阅；**未实施、未开窗**
前序：追加③ 主检验归位；`2026-08-17-tf-runtime-power.md`（#137）；用户裁定「底座固定，只接跑得通的，不要全接」
权威 pin：底座 `83e83b42`（`2a2523f7^1`）；摘接来源 **只许** `2a2523f7`（#61 merge），不许当前 main
替换关系：本文件是下一对照的权威。全量 A vs A′ 的 450/臂（两臂 900）**不开**。

## 0. 一句话

钉住吸收前底座，只把已经在 live 路径上跑通过的 **EpisodeScope + 工具阶段事件** 接上去，用 1 题 × 每臂 5 次看「还跑不跑、墙钟别差出一个数量级」。摘不干净就停，不退回整包 #61。

## 1. 为什么不走全量 A′

#61 一次焊了 30+ 文件（Scope、工具阶段、RuntimeHandle、事件投影、ResearchProfile、dsh stub…）。
A 对整包 A′ 就算延迟好看，也说不清是哪一块的功。领域侧 ebo / 带 citations 是阶跃函数，加样本没用。

Runtime 功效（#137）只说明：**延迟和 repair@10pp 在 450 内可判**；没授权开 900，也没说必须整包才量得出。

本实验换因果：`底座` vs `底座 + 这一对`。

## 2. 目标与非目标

### 2.1 目标

- 做出一棵 **摘接臂**：`83e83b42` + 白名单文件，能编过、1 题烟测能跑。
- 同一题、同 Provider，两臂各 5 次 live，报墙钟和是否跑完。
- 碰上修复就记进入/恢复；记不住不补跑。
- 摘接失败时留下「哪一处强制拖进 Handle/Profile/stub」的收据，然后停。

### 2.2 非目标

- 不开 900，不锁新的 450/臂，不把本窗读成「吸收兑现」。
- 不切 8792，不动 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` / 档位 / `ASK_TOOL_BATCH_TIMEOUT`。
- 不改冻结 30 构成，不放宽 5pp。
- 不接 RuntimeHandle、ResearchProfile、dsh stub、`episode_projection`、T-B 的 `view()`。
- 不看领域护栏（带 citations / ebo）。本窗不报那条。
- 不宣称 20s 改善或 repair 10pp——n=5 只够看数量级和能不能跑。
- 不把当前 main（#61 之后 100+ 提交）当成摘接来源。

## 3. 术语

| 词 | 含义 |
|---|---|
| 底座 | `gitea/main@83e83b42`，#61 合入前一刻 |
| 摘接来源 | **仅** `2a2523f7`。当前 main 禁止 |
| 这一对 | EpisodeScope + 工具阶段事件（含 `LiveEventSink` 车道）。代码里是一套，拆开接不上 |
| 臂 0 | 纯底座，已有树 `/Users/a77/fwp-wt-tf-arm-a-83e83b42` |
| 臂 1 | 底座 + 这一对。**新开** worktree，不要复用 `/Users/a77/fwp-wt-tf-arm-aprime-2a2523f7`（那是整包） |
| 工程门 | 臂 1 编译 + 相关单测 + 1 题 dry/live 烟测都过，才允许 5×5 |
| 数量级 | 臂 1 墙钟中位数 / 臂 0 墙钟中位数 **< 3**；且两臂都有非 `runner_exception` 的终态 |

## 4. 摘接白名单（从 `2a2523f7` 取）

整文件可取：

- `intelligence/services/episode_scope.py`
- `intelligence/services/episode_event_lanes.py`
- `intelligence/tests/test_episode_scope.py`
- `intelligence/tests/test_episode_event_lanes.py`
- `intelligence/tests/test_tool_stage_events.py`
- `intelligence/tests/test_tool_reachability_audit.py`
- `scripts/audit_tool_reachability.py`

只取接线 hunk（Scope / 阶段事件 / `LiveEventSink`），**不得**顺手带上 Handle / Profile：

- `intelligence/runtime/agent_episode.py`（`run()` 入口构造 Scope）
- `intelligence/runtime/episode_tool_batch.py`（`scope=` 往下传）
- `intelligence/services/research_tool_registry.py`（`TOOL_PRE_EXECUTE` / `TOOL_RESULT` / `TOOL_ERROR` 阶段事件）
- `intelligence/runtime/headless_tool_gateway.py`（可选 `scope`，缺省与接线前一致）

## 5. 禁止名单（`2a2523f7` 有、本窗不准取）

- `intelligence/services/runtime_handle.py` 及其测试
- `intelligence/services/research_profile.py` 及其测试
- `intelligence/runtime/dsh_stub_runtime.py` 及其测试
- `intelligence/services/episode_projection.py` 及其测试
- `intelligence/runtime/agent_runtime_factory.py`（#61 把 backend 名集改挂 Profile）
- `intelligence/runtime/glm_agent_runtime.py` / `openai_agents_runtime.py` 里构造 `RuntimeHandle` 的 hunk（臂 1 留底座原文）
- `intelligence/runtime/continuous_turn_adapter.py` 的投影 / Handle close hunk
- `intelligence/api/app.py`（#61 是 Profile + memory 身份守卫 + `episode_progress` 搬家，不是这一对）
- `episode_progress.py` 从 runtime 迁到 services

注释里提到 RuntimeHandle 可以留（`agent_episode` 里那句「让会话层能钉收据」），**对象不准构造**。

## 6. 工程门（先于 5×5）

在新 worktree：`git checkout 83e83b42`，按 §4 取文件，§5 一份不取。

完成标准（全过才开 5×5，任一失败就停并写收据）：

1. 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
2. `pytest`：上列四个新测试文件必绿。臂 1 若改了 `agent_episode.py` / `episode_tool_batch.py`，对应旧测试红了就停（不准为过门改断言）。
3. `scripts/layer_audit.py` 仍 0 ERROR（领域层不 import `intelligence.runtime.*`）。
4. dry-run + live 各 1 次，题 `A1-market-overview`（冻结 30，烟测已用过）。
5. 两臂 `task_frame_hash` 相同；Provider 只 `gpt-5.6-terra`（`x.ailzd.com`），`FORESIGHT_LLM_KEYCHAIN=0`，不挂 GLM 三件套。
6. 生产 rag `model_load_count` 烟测前后仍为 1；8792 `source_revision` 未变。
7. 臂 1 的 `git diff 83e83b42` 不得出现 §5 路径。

摘接若必须拉进 §5 才能编过：**停**。收据写清是哪一个符号。不准改成整包 A′ 继续跑。

## 7. 小窗（工程门通过之后）

| 项 | 值 |
|---|---|
| 题 | 仅 `A1-market-overview` |
| 重复 | 每臂 5，共 10 次 |
| 臂 0 树 | `/Users/a77/fwp-wt-tf-arm-a-83e83b42` |
| 臂 1 树 | 新 worktree，名字自定，pin 底座 + 摘接，**不是** `2a2523f7` |
| 数据根 | `/Users/a77/finance-workspace-private` + `/Users/a77/knowledge-base-private/wiki` |
| 题集文件 | `/Users/a77/fwp-wt-dsh-sample-lock/intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json` |
| 产物 | `~/.finance-runtime/tf-subset-20260817/` |

读数（只这三行；n=1 的烟测墙钟仍不得读成「臂 1 更快」）：

1. **还能跑**：每臂 5 次里 `runner_exception` 条数；有事件则 `tool_request` 条数 = `tool_result`+`tool_error`。
2. **墙钟**：每臂 `latency_seconds` 的 min / 中位 / max。臂 1 中位 / 臂 0 中位 ≥ 3 → 记「数量级回退」，停，不扩样本。
3. **修复（碰到才记）**：是否出现 `repair_goal`；末条 finish 是否 ∈ {`repair_model_finish`,`repair_model_stop`,`model_finish`}。5 次里碰不到就写「本窗无修复样本」，不准为补这条加跑。

不报：ebo、带 citations、5pp、P95 功效、cancel/resume/restart。

## 8. 判定（本窗能下的唯一三种结论）

| 结论 | 何时 |
|---|---|
| 这一对接得上，数量级没炸 | 工程门过；两臂都能跑完；中位数比 < 3× |
| 这一对接得上，但数量级回退 | 工程门过；中位数比 ≥ 3×。停，不扩、不整包 |
| 这一对摘不干净 | 工程门失败。停，不整包 |

「吸收兑现」不在本窗结论集里。

## 9. 与旧口径的关系

- 吸收设计稿 §9.1 的全量 A / A′ **仍是历史定义**，本窗不执行。
- #68 的 45 条仍是旧 pin，只借方差结构，不当本窗基线。
- 5a / 护栏降级 / 23/45 未定义必须写明——本窗根本不报那条，故不触发。
- 5d（闸前 `source_ids`）仍并行、不挡本窗。

## 10. 实施顺序（本文件批准之后才做）

1. 从 `83e83b42` 开臂 1 worktree，按 §4/§5 摘接。
2. 过 §6 工程门；失败则交收据并停。
3. 跑 §7 的 10 次，写一页读数（handoff），不开 900。
4. 用户看过读数再谈要不要接下一块（Handle 或投影）。下一块另开 spec。
