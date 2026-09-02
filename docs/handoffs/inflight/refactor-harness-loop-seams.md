# 在途交接 · refactor/harness-loop-seams

更新：2026-09-02 11:40 CST · **已闭环：PR #525 已合 `gitea/main=71a2c846`，主干门禁可采信（7364P/5F 同基线红、webapp 四连绿，读数见 `inflight/main.md` 顶行与收据），8792 未切（零 live 判据，随下批）。** 后续 P1b 见 `inflight/refactor-harness-interpret-turn.md`。

## 一句话

给「金融题怎样才算答完」立了 `ResearchHarness` Protocol
（`intelligence/services/research_harness.py`）。P0 把 `ContinuousAgentEpisode` 里手焊的
三道领域门（终局准入 ×5、批后停机 ×2、prompt ×1）改成 loop 调 `self._harness`；
P1a 让另两条 loop（`openai_agents_runtime`、`codex_headless_runtime`）的终局门与 prompt
也走同一个 harness——**三条 loop、一道门**。默认 `FinanceResearchHarness` 纯委托，
行为等价（P0 唯一已知差见 spec §7，已钉测试）。这是 09-01 形状对齐 spec §11
第三条「把领域门抽到外壳钩子」的头两刀。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`

## 提交

| 提交 | 内容 |
|---|---|
| `5f945d10` | P0：协议 + 默认实现 + `agent_episode` 8 焊点（+87/−151）+ 13 测试 + spec + 收据 |
| （第二个，见 `git log`） | P1a：另两条 loop 改走 harness（各 ~75 行对换）+ `FinishAdmission.declared_gaps` + 测试 13→19 |

## 离线读数（对分支尖成立，解释器 `.venv-workbench`）

见收据。要点：全量 pytest 与 main 基线同一组 5 红（`test_dream_mine.py`，环境项），
passed 只多出新测试数；ruff 绿；`layer_audit` ERROR 0 == 基线。

反向验证（假绿防线，P0）：同一死钟脚本在 main 树跑出 bindings `('rank-1',)`、分支
`('rank-1','rank-2')`；棘轮在 main 树报出 4 个泄漏名、分支 0。

## 红线遵守自证

- 未改任何秒数 / 档位 / reserve；未改 `episode_protocol.py` 判定。
- durable 事件种类、payload 键、顺序零改动；三条 loop 的 gap 口径**各自原样**
  （`agent_episode` 合并口径用 `gaps`；另两条只并声明 gap 用 `declared_gaps`）。
- `services/` 不 import `runtime/`（`layer_audit` + 新测试双守）。
- 生产构造（`glm_agent_runtime` / `continuous_sub_research` / `api/app.py` 三处 runtime
  构造）**零改动**，都拿默认 harness。
- 8792 / 启动器 / 快照未碰。

## 下一步（按序）

1. 用户确认 → 合 PR #525（等价四件套：ruff ✅ pytest ✅ layer_audit ✅；未动前端，
   frontend/e2e 不触发）。
2. **P1b**：`interpret_turn`（PLAN 协议：`parse_plan_candidate` / `validate_plan_revision`
   出 loop）、`after_tool_batch`（`_EpisodeToolAccumulator.consume` 的 prune / budget /
   ledger ingest）、`assemble_prompt` 扩展（回灌与 finalization 文案；另两条 loop 修复
   prompt 里的 `build_episode_input` / `build_episode_instructions`）。这三条抽完，loop 里
   不再出现「PLAN」「FINAL_JSON」字面——**这是 P2' 第二条 loop 的前置**。
3. **gap 口径统一**（P1b 后单独一刀）：先量三条 loop 的绑定 gap 分布，再拍是否都用合并口径。
4. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写一条只调 harness 四方法 +
   `ResearchToolRegistry` 的最小 loop，跑 09-01 同题——「run 层可替换」从设计图变实测。

## 顺手发现（不属本单）

- `intelligence/services/episode_scope.py` 文首「生产链路目前没有任何一处构造
  EpisodeScope」已过时（`agent_episode.py` 入口在构造）。文档腐烂，另单修。
- `run()` 主门驳回后的兜底 `_stopped_outcome(stop_reason="invalid_model_finish")` 对
  INTEGRITY 也写 `invalid_model_finish`，只有 `invalid_action.disposition` 是
  `integrity_violation`。现状保留；统计侧按 `disposition` / `rejection_code` 分。
- 三条 loop 的 gap 口径不一致（见上）。
