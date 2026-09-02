# 在途交接 · refactor/harness-reference-loop

更新：2026-09-02 12:45 CST · **已闭环：PR #528 已合 `gitea/main=5292175c`，主干门禁可采信（7381P/5F 同基线红、webapp 70P 绿，见 `inflight/main.md` 顶行），8792 未切。** 后续 P2 `govern_mode` 见 `inflight/refactor-harness-govern-mode.md`。

## 一句话

第二条 loop 落地：`intelligence/runtime/harness_reference_loop.py`（`HarnessReferenceLoop`）
只调 `ResearchHarness` 八方法 + `ResearchToolRegistry` + 底座 `ToolBatchExecutor`，一行领域
逻辑不写。`test_harness_reference_loop.py` 拿同一脚本化模型、同一注册表把它和
`ContinuousAgentEpisode` 并跑：**首轮请求字节相同；无 PLAN 全程消息一致（只差底座
`runtime_budget` 一键）、outcome 一致；有 PLAN 差恰好一条 Episode 独有的 `MODE_DECISION`。**
「run 层可替换」自此是可判定的读数。前序 P0–P1c 已全部合 main（`e360895b`）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§9 P2' 已实施；P2'-live 未做）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P2' 节）

## 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/runtime/harness_reference_loop.py` | 新：最小 loop（调模型 / 经 `ToolBatchExecutor` 派工具 / 数槛 / 记 durable 子集事件），其余全问 harness |
| `intelligence/tests/test_harness_reference_loop.py` | 新：6 例（首轮身份 / 无 PLAN 全程等价 / 有 PLAN diff 恰一条 / 有牙 / 底座停机 / 九模块棘轮） |
| 既有文件 | **零改动**（不进 `RUNTIME_BACKEND_NAMES`，与 `dsh_stub_runtime` 同纪律） |

## 离线读数（对分支尖成立）

见收据 P2' 节表格。ruff 绿；`layer_audit` ERROR 0（`runtime/` 17→18 模块，门禁只查方向）；全量见收据回填。

## 为什么放仓内而不是 finance-base-ab

09-01 把两份形状外壳放 `finance-base-ab` 是为了不污染 `intelligence/`、不进快照。P2' 的价值在
**持续判定**——「新的领域文案有没有又焊回 Episode」要靠 CI 每次都问，放仓外就没人问。
`finance-base-ab` 的 `pi-shape/packages/agent_core` 将来直接 import 本类即可（P2'-live）。

## 红线遵守自证

- 未改任何既有源文件；生产装配零改动；8792 未碰。
- 参考 loop 与 Episode 的全部差异都落在 spec §4 标「底座」或 P2 的行上，测试逐条钉住。

## 下一步（按序）

1. 用户确认 → 合 PR #528。
2. **P2 `govern_mode`**：从 P2' 读数出发——`_append_mode_decision_message` 的 `MODE_DECISION` 文案 +
   `mode_decision` 事件 + 子研究消息投影（三个序号函数）进 harness；做完后有 PLAN 脚本的 diff 应归零。
3. **P2 `repair_policy`**：`_recover_finalization` / `_repair_model_complete` / `RepairGoal` /
   `apply_unreachable_downgrade` / `EpisodeFinalizer`——先画状态机。
4. **P2'-live**：8792 快照切到含 harness 的 revision 后，用 `finance-base-ab` 隔离配方把
   `HarnessReferenceLoop` 当第四臂跑 09-01 同题（硬门：首轮 `task_frame_hash` / `input_tokens`±3 /
   `financial_data`）。烧配额，另拍。

## 顺手发现（不属本单）

- Episode 的 `_decide_mode` 在**每次** PLAN 轮都会给模型追加 `MODE_DECISION`，即使 quick 档
  没有任何裁决变化——这条消息是否该存在，是 P2 `govern_mode` 的第一个问题。
