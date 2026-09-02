# 在途交接 · refactor/harness-loop-seams

更新：2026-09-02 · **P0 已实施、离线全绿，未提交 PR、未合 main、未切 8792。** 等用户确认合并。

## 一句话

给「金融题怎样才算答完」立了 `ResearchHarness` Protocol
（`intelligence/services/research_harness.py`），把 `ContinuousAgentEpisode` 里手焊的
三道领域门（终局准入 ×5 处、批后停机 ×2 处、prompt 拼装 ×1 处）改成 loop 调
`self._harness`。默认 `FinanceResearchHarness` 是纯委托，行为等价（唯一已知差见
spec §7，已钉测试）。这是 09-01 形状对齐 spec §11 第三条「把领域门抽到外壳钩子」
的第一刀。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`

## 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | 新：`ResearchHarness` / `FinishAdmission` / `FinanceResearchHarness` |
| `intelligence/runtime/agent_episode.py` | +87 / −151：import 段去掉 4 个领域符号 + `forecast_residual_budget`；`__init__(harness=)`；8 处焊点改走 harness；删 `_finish_gaps` / `_snapshot_surface_satisfied`；`_carry_*` 改实例方法返回 `FinishAdmission \| None` |
| `intelligence/tests/test_research_harness.py` | 新：13 例（等价 ×5 / 协议 ×1 / loop 真在问 ×2 / 有牙 ×2 / 棘轮 ×2 / §7 差 ×1） |
| `glm_agent_runtime.py` / `continuous_sub_research.py` | **零改动**（生产构造不传 harness，拿默认） |

## 离线读数（对分支尖成立，解释器 `.venv-workbench`）

见收据。要点：全量 pytest 与 main 基线同一组 5 红（`test_dream_mine.py`，环境项），
passed 多出正好 13（新测试）；ruff 绿；`layer_audit` ERROR 0 == 基线。

反向验证（假绿防线）：同一死钟脚本在 main 树跑出 bindings `('rank-1',)`、分支
`('rank-1','rank-2')`；棘轮在 main 树报出 4 个泄漏名、分支 0。脚本
`/Users/a77/tmp/probe_dead_clock_main.py`（临时，不入库）。

## 红线遵守自证

- 未改任何秒数 / 档位 / reserve；未改 `episode_protocol.py` 判定。
- durable 事件种类、payload 键、顺序零改动（`test_agent_episode.py` 81 处构造全绿）。
- `services/` 不 import `runtime/`（`layer_audit` + 新测试双守）。
- 8792 / 启动器 / 快照未碰。

## 下一步（按序）

1. 用户确认 → 开 PR 合 main（CI 等价四件套：ruff ✅ pytest ✅ layer_audit ✅；frontend/e2e 未动前端，不触发）。
2. **P1a**：`openai_agents_runtime.py`（:1146 / :1408）与 `codex_headless_runtime.py`
   （:924 / :1017 / :1415）的终局门改走 `FinanceResearchHarness.admit_finish`——
   三条 loop 共用一道门。验收：同一份 FINAL_JSON 三处得到同一 `FinishAdmission`。
3. **P1b**：`interpret_turn`（PLAN 协议）/ `after_tool_batch`（accumulator）/ 回灌与
   finalization 文案进 `assemble_prompt`。
4. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写一条**只调四方法 +
   registry** 的最小 loop 跑 09-01 同题——「run 层可替换」从设计图变实测。

## 顺手发现（不属本单）

- `intelligence/services/episode_scope.py` 文首「生产链路目前没有任何一处构造
  EpisodeScope」已过时：`agent_episode.py` 入口在构造（第 4 步已接）。文档腐烂，
  另单修。
- `run()` 主门驳回后的兜底 `_stopped_outcome(stop_reason="invalid_model_finish")`
  对 INTEGRITY 也写 `invalid_model_finish`，只有 `invalid_action.disposition` 是
  `integrity_violation`。现状保留（本单不改行为），统计侧按 `disposition` 或
  `rejection_code` 分，不按 outcome `stop_reason`。
