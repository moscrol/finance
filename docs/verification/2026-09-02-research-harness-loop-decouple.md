# 收据：领域 Harness 与底座 loop 解耦 P0（2026-09-02）

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
分支：`refactor/harness-loop-seams` @ 基线 gitea/main `18bf518b`（本收据的读数取自提交前脏树，脏路径恰为本单三个代码文件；提交后未再改代码）。

**结论：P0 验收 §8 八条全绿。默认 harness 下行为等价——全量 pytest 与 main 同一组 5 红、passed 恰多 13（新测试）。接缝有牙，棘轮在 main 上会红。未合 main、未切 8792。**

## 成立条件

| 项 | 值 |
|---|---|
| 树 | `/Users/a77/fwp-wt-harness-loop-seams`（新开，非主树；主树有 187 行他人足迹未动） |
| revision | `18bf518b82954ce7ac49260ea5419e4b9aabe0a2` + 本单未提交改动（收据 `dirty_paths` 三文件） |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` 3.12.13，依赖指纹 `786fd167a42126c6` |
| 基线树 | `/Users/a77/tmp/fwp-baseline-18bf518b`（detached @ 同 SHA，干净） |
| 读数收据 | 基线 `~/.finance-runtime/test-receipts/20260902T022008Z-18bf518b.json`（跑于 02:20–02:29）；分支 `20260902T023825Z-18bf518b.json` |
| 8792 | 未读、未碰（本单纯离线；不需要 revision 哨兵） |

## 读数

### 全量 pytest（§8 第 3 条）

| 树 | passed | failed | skipped | xfailed | 用时 |
|---|---:|---:|---:|---:|---|
| main 基线 | 7345 | 5 | 15 | 1 | 8:46 |
| 分支 | **7358** | **5** | 15 | 1 | 8:05 |

5 红两边**同一组**：`intelligence/tests/test_dream_mine.py::RunMineTests::{test_degrade_without_key_keeps_watermark_and_marks_md, test_dry_run_writes_nothing_but_store, test_max_signals_cap, test_mine_appends_proposals_suggest_only_and_idempotent, test_quote_redaction_survives_into_proposal}`——与 Episode 无关，是 main 上既有的环境项。7358 − 7345 = 13 = `test_research_harness.py` 用例数。

### 门禁

- `ruff check .`：All checks passed。
- `scripts/layer_audit.py`：ERROR 0 == 基线（对 `refactor/harness-loop-seams@18bf518b` 成立）；`runtime/` 17 模块。
- 直接构造 Episode 的七个测试文件（`test_agent_episode` 81 处构造 + `test_repair_carry_just_written_finish` + `test_episode_tools` + `test_empty_pool_fallback` + `test_runtime_fault_matrix` + `test_tool_stage_events` + `test_tool_observation_noise`）：221 passed，6.23s。这是「durable 事件 payload 零改动」的回归网（§8 第 2、5 条）。

### 新测试 `intelligence/tests/test_research_harness.py`：13 passed

| 组 | 例 | 守什么 |
|---|---:|---|
| 等价 | 5 | `admit_finish` 接受 / FORMAT / INTEGRITY 三路与直接调 `validate_episode_finish` + `expand_episode_snapshot_bindings(draft=)` + `_merge_gaps` + `rejection_response` + `finish_rejection_fields` 逐字段相等；`assemble_prompt` == `split_episode_prompt`；`halt_after_tool_batch` 复现 `FORECAST_RESIDUAL_SPIN`；`retrieval_complete` 三种 registry；`FinishAdmission` 拒绝两侧形状不一致 |
| 协议 | 1 | `isinstance(FinanceResearchHarness(), ResearchHarness)`；只实现 `admit_finish` 的类不算 |
| loop 真在问 | 2 | 录音 harness 在 tool→finish 一次 episode 上按控制流顺序收到 `assemble_prompt → halt_after_tool_batch → retrieval_complete → admit_finish`；不注入时默认是金融 harness |
| 有牙 | 2 | 伪造哈希稿：默认 harness → `invalid_action.code=forged_hash / kind=integrity / disposition=integrity_violation`、finish `rejection_code=forged_hash`、draft 空；放行 harness → `model_finish / completed`、无 invalid_action、`rejection_code=none` |
| 棘轮 | 2 | AST：`agent_episode.py` 从 `episode_protocol` 只剩 `finish_rejection_fields` 等非门符号，不 import `forecast_residual_budget`，import 了 `research_harness`；`research_harness.py` 不 import `intelligence.runtime` |
| §7 差 | 1 | 死钟结转 + 比较句稿 + 两条同题证据 → bindings `('rank-1','rank-2')` |

### 反向验证（防假绿）

同一脚本 `/Users/a77/tmp/probe_dead_clock_main.py`（临时，不入库）在两棵树 cwd 下各跑一次：

| 树 | stop_reason / status | bindings | 棘轮泄漏 |
|---|---|---|---|
| main 基线 | `model_finish` / `completed` | `[('rank-1',)]` | `expand_episode_snapshot_bindings, rejection_response, split_episode_prompt, validate_episode_finish` |
| 分支 | `model_finish` / `completed` | `[('rank-1', 'rank-2')]` | `[]` |

即：§7 那条差在 main 上确实存在（比较集展开在死钟路径被丢），本单把它并到同一份 admission；棘轮测试放到 main 上会红——不是同义反复。

## 改动面（§8 第 4 条）

`git diff --stat`：`intelligence/runtime/agent_episode.py | 238 (+87 / −151)`。新增 `intelligence/services/research_harness.py`、`intelligence/tests/test_research_harness.py`、spec、本收据、inflight 交接。`glm_agent_runtime.py` / `continuous_sub_research.py` 零改动。

`agent_episode.py` import 段：从 `episode_protocol` 去掉 4 个符号（`validate_episode_finish` / `expand_episode_snapshot_bindings` / `rejection_response` / `split_episode_prompt`），去掉整条 `forecast_residual_budget` import；新增 `research_harness` 三个名字。删除 `_finish_gaps`（搬到 harness `_merge_gaps`）与 `_snapshot_surface_satisfied`（成为 `retrieval_complete`）。

## 未做 / 红线

- 未改秒数、档位、reserve、`episode_protocol.py` 判定、8792、启动器、快照。
- 未动 `openai_agents_runtime` / `codex_headless_runtime` 的终局门（P1a）。
- 未写第二条 loop（P2'）；「run 层可替换」目前是**接缝已抽 + 有牙已证**，不是**换过一次**。
- 未跑 LLM。配额未动。
