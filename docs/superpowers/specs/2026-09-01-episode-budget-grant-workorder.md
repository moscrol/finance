# 2026-09-01 Episode 工具授权额与假超时工单

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 前置：底座形状对齐已结（包装门重判绿）。本单是生产 Episode 单，与 `finance-base-ab` 对照树并行、各开各的分支。

## 背景与动机

2026-09-01 从 `finance-base-ab/out/attempt-4-aligned/` 与 6 份 `continuous-episode.json` 重读（未新跑 LLM，配额 16）。序列差不是模型选工具噪声，也不是外壳分叉。

生效链（standard / `financial_analysis`，不在 heavy 集）：

1. `ResearchPolicy.for_tier("standard")` → 6 步 / 90.0s（`research_contract.py` `for_tier`）
2. `effective_timeout = min(90, 300)` → **90**（`episode_factory.py`；启动器 300 被档位硬顶）
3. `GLMAgentRuntime.synthesis_reserve_for_task` → `min(75, 60)` → **60**
4. `reserve = min(60, 90 × 2/3)` → **60**（`episode_factory.py`）
5. `stage_timeout = max(0, remaining − 60)`（`research_contract.py`）

研究阶段约 30s 可派发工具。`remaining_slots` 从 6 走到 3，次数闸从未生效。对照臂首轮 LLM 32.57s 后授权额 0。`episode_tool_batch.py` 在 `stage_timeout_granted ≤ 0` 时不进线程池，却回 `error=tool_timeout`。`agent_episode.py` 对所有 `status=timeout` 强制 `detail=""`。模型看到的字符串与「真跑 17s 再超时」逐字相同，换工具再试。

台账早已占号，不要当新发现：

- `R-20260816-13`：时间闸 `tool_timeout` 与次数闸 `tool_budget_exhausted` **分开计**。P0 不得把零授权并进次数闸。
- `R-20260816-09`：若动 `_BALANCED_SYNTHESIS_RESERVE` / 非 finalize `stage_timeout`，须附 08-08 式延迟实测 + 全路由影响面。只调 T/30 不当修复。
- `R-20260816-07` / `-14` / `-21`：禁止只把 T / 档位 / 批窗数字调大。
- 08-08 首轮借款：`_opening_planning_timeout` 向 reserve 借余量，是故意的（不借则 26.67s < provider P50）。P1 不要补一行借记——按实耗是恒等 no-op，按授予则缺 finalize P95。

**形态决策（已定，勿改）**：先 P0 填 public `detail`（零 LLM、不改秒数）；P0.1 带实授值；P1 挂起——不要借记 opening borrow。

## 目标

1. P0：授权额 ≤0 的工具结果，模型可见 `detail=not_dispatched: stage_timeout_granted=0`，`error` 仍是 `tool_timeout`。真 `TimeoutError` 的 `detail` 仍空。allowlist 有 **consume 链路**集成测试（带 raw detail 的 timeout 结果），不只靠上游不填。
2. `R-20260816-13` 定位改符号，不钉行号。
3. P0.1（本提交之后）：`detail` 带实授值，覆盖授权 >0 仍超时的那一半。
4. P1 挂起：不动公式。不要零授权 fail-closed（repair 还会铸窗）。

## 非目标（写死认领，别顺手做）

- ❌ 不抬 `for_tier` / 不改启动器 300 / 不改 `_BALANCED_SYNTHESIS_RESERVE`（去处：`R-20260816-07` 绊线）。
- ❌ 不把零授权改成 `tool_budget_exhausted`（去处：`R-20260816-13` 两闸词表）。
- ❌ 不实施 `R-20260817-02` 按剩余选检索档（去处：该行本窗禁止动手）。
- ❌ 不切 8792、不改启动器、不烧对照 LLM。
- ❌ 不改包装硬门、不重跑 `finance-base-ab/compare.sh`。
- ❌ 不修 `at` 落盘时刻（取证坑另记，本单不碰 ledger 时钟）。
- ❌ 不按实耗/按授予借记 opening borrow（去处：设计 §4；先离线量 finalize）。
- ❌ 零授权不得 fail-closed 提前收工（live 臂随后有 repair 30s 窗）。

## 证据路径（先读这些，勿臆测）

| 文件 | 看什么 |
|---|---|
| `docs/superpowers/specs/2026-09-01-episode-budget-grant-design.md` | 已锁切片 |
| `docs/verification/2026-09-01-finance-base-shape-alignment.md` 尝试 4 更正 | 6 run 授权额表 |
| `finance-base-ab/out/attempt-4-aligned/budget-chain.json` | 首轮 token / grant 摘录 |
| `intelligence/services/research_contract.py` `stage_timeout` / `for_tier` | `remaining − reserve`；standard=90 |
| `intelligence/services/episode_factory.py` `effective_timeout` / `reserve = min(...)` | 300 被 90 截；`2/3` 只在开场算一次 |
| `intelligence/runtime/glm_agent_runtime.py` `_BALANCED_SYNTHESIS_RESERVE=60` | financial_analysis 走 60 |
| `intelligence/runtime/agent_episode.py` `_opening_planning_timeout` | 首轮向 reserve 借款 |
| `intelligence/runtime/episode_tool_batch.py` 授权额 ≤0 分支 | 不进线程池、原先 detail 空 |
| `intelligence/tests/test_episode_tool_batch.py` `test_expired_standard_batch_*` / `test_r13_frozen_*` | 时间闸 error 码钉死 `tool_timeout` |
| `docs/prediction-ledger.md` `R-20260816-09` / `-13` / `-07` / `-14` / `-21` | 绊线 |

复用夹具：`test_episode_tool_batch.py` 的 `_standard_context(timeout=0.0)`、`test_agent_episode.py` 的 `ScriptedModel`。勿重造批执行器。

## 步骤

1. 开工三连：`git status --short && git branch --show-current && git worktree list`。他人足迹则另开树。本单树：`/Users/a77/fwp-wt-tool-not-dispatched`，分支 `fix/tool-not-dispatched-detail`，基座 `gitea/main@18bf518b`。
2. P0 改两处：`episode_tool_batch.py` 零授权填 `NOT_DISPATCHED_DETAIL`；`agent_episode.py` 用 `_public_timeout_detail` allowlist，禁止再对所有 timeout 清空 detail。
3. 测试：批零授权 detail；allowlist 单测；episode 零授权回灌；**accumulator 带 raw detail 的 timeout 过 consume**。`test_r13_frozen_*` 的 error 序列不得改。
4. 跑：`env -u ASK_TOOL_BATCH_TIMEOUT /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_episode_tool_batch.py intelligence/tests/test_agent_episode.py -q --tb=short`（cwd=本 worktree）。要两个文件全跑，不是点名 3 条。
5. 提交用 pathspec，不合 main，不切 8792。P0.1 另提交。P1 不动。

## 验收

- [x] 零授权：`error=tool_timeout` 且 `detail=not_dispatched: stage_timeout_granted=0`；runner 调用次数 0。
- [x] 真 `TimeoutError`：模型消息无异常原文（含 accumulator 注入 raw detail 的那条）。
- [x] R-13 冻结夹具 error 序列仍是 4×`tool_timeout` + 1×`tool_budget_exhausted`。
- [x] R-13 台账定位改符号，不钉行号。
- [x] diff 不含 T / `_REPAIR_SECONDS_CAP` / 档位 / `_BALANCED_SYNTHESIS_RESERVE` / `ASK_TOOL_BATCH_TIMEOUT`。
- [ ] 未合 main、未切 8792（执行方交付时保持）。
- [x] P1 未施工。

## 红线

- 禁 `git add -A`，一律 `git commit -- <pathspec>`；不合 main、不强推。
- 用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 不改 8792 / 启动器 / 生产 users。
- 台账号若需预注册：`python3 scripts/claim_ledger_id.py claim --branch fix/tool-not-dispatched-detail`，禁手工取号。
