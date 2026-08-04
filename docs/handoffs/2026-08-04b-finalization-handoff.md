# 显式收口交接（finalization handoff）— Codex 对齐 TODO（2026-08-04 第二轮）

> **给 Codex 的读法**：第 0 节是**已验收的定案**，不要重新论证、不要重跑标定。
> T0 是强制开工动作。T1 是测量仪器，**必须先于 T2**——没有它你无法判断 T2 是否
> 生效。T3 是验收。每个任务给了完成判据，判据没满足就不要报完成。
>
> **本轮只做一件事：让研究窗口关闭后有一次显式的收口交接。**
> 不要动 root 总时长、不要动 `floor_ratio`、不要动 `max_tool_calls`——
> 上一轮已经证明移墙无效。

---

## 执行结果（2026-08-04，Codex 回填）

本轮已在 `eval/budget-calibration` 上执行 T0→T3，没有合并 main、没有重跑 a/b/d、
没有修改 `total_seconds/floor_ratio/max_tool_calls`。

| 项 | 结果 |
|---|---|
| T1 仪器 | 已完成；`84c1eb73`，payload timestamp 可归一化；T1 live 为 60 events / 0 unmapped / 1 finalization |
| T2 显式交接 | 已完成；`3dd867e9`，deadline-pressure / tool-cap result 带 instruction，transition 后 fail-closed；真实 wrapper seam 单测通过 |
| T3 主判 | **失败**；瑞华泰事件级 `headless_protocol_rejected` / 135.555s，不是 `model_finish` |
| R-09 | **refuted**，不得恢复为 pending |

决定性序列：瑞华泰第 5 个 `tool_request(evidence_search)` 没有 result/error；5 个请求
只有 4 个 mailbox exchange，随后 runtime 记 `headless_command_failed`。代码中的
wrapper 固定 60 秒等待是与该序列吻合的退出路径；artifact 未保留 command stderr，
所以精确退出字符串仍是推断。T3 全批 `finalization=0`，不是因为收尾瞬间完成，
而是 result/rejection activation point 没有被执行到。

因此下一层不是再改 finalization 文案，也不是移预算墙，而是 **in-flight tool 的
deadline-aligned handoff/cancellation contract**。已在 prediction ledger 新开
`R-20260804-10`：先用 deterministic slow tool 证明 handoff 阈值处一定有配对响应、
只发一次 finalization、迟到结果不污染 episode，再决定是否跑下一次 live canary。
R-10 的主门是离线结构契约，单次 live 只作确认；还须让 finalization reason 与
`_budget_payload` 读取同一份 root-ledger 剩余 calls，并把 handoff window 从 profile /
生效预算派生、明确落盘，不能保留隐藏的 `initial_research_seconds * 0.20` 第二 reserve。

后续观测补丁已经把 normalized artifact 的 `unpaired_tool_requests` 变成可重算字段，
并在每条 `tool_request` 上记录 timestamp、root 入口余量和扣除 synthesis reserve 后的
research 入口余量。T1/T2 raw artifact 复算为 **0 / 1**；本步没有改预算或跑 live。

完整证据见
[`docs/verification/2026-08-04b-finalization.md`](../verification/2026-08-04b-finalization.md)。

---

## 0. 起点：已验收的定案，不要重开

基线：`eval/budget-calibration` 分支（`9fd55ba9`），含四臂标定产物。
上一轮的 M2 分诊结论**已逐条独立复算验收通过**（数字全部精确命中，无一偏差）。

### 0.1 PRIMARY 已确认：不是阈值，不是调用数，是未收口的尾段

| 假设 | 状态 | 决定性证据 |
|---|---|---|
| 0.65 关门阈值是 PRIMARY | **REJECTED** | floor 归零后 `research_stage_closed` 确实消失，但 timeout 从 0 增至 2；唯一真实激活的 case 反而正常 `model_finish` |
| 6-call 上限是 PRIMARY | **REJECTED** | 瑞华泰在 c/d 两臂都只用了 5 calls，从未触顶 |
| **root 总时长墙前的未收口尾段是 PRIMARY** | **CONFIRMED** | 瑞华泰在 floor=0、calls 未触顶时连撞 60/150/150 秒 root；**加时长只把失败延后** |

**推论（已定案）**：继续加 `total_seconds` 是死路。这一点与上一轮「继续调 cap 是死路」
是同一个形状——**先识别绑定约束，再验证扩容是否真正改善终态**。

### 0.2 机制：关门之后没有人接手

`headless_tool_gateway.py:538-563`——研究窗口关闭时，模型收到的是：

```json
{"status": "rejected", "tool": "...", "error": "research_stage_closed", "budget": {...}}
```

**没有 `retry_hint`，没有任何「停止研究、现在写答案」的指令。**
`retry_hint` 分支（`:552`）只在 `invalid_arguments` 时触发。

对比 `agent_episode.py:1459-1463`：它有显式的 `_start_finalization`，会发
`ledger.add("finalization", {"reason": reason})`。**`codex_headless_runtime` 没有对应
路径**——它只有被动的 `finalization_floor_ratio`（关闸门）和事后的
`_recover_finalization`（补救），中间缺一次主动交接。

> 这与 `mode_decision` 是同一个结构性缺口：共享 episode 驱动有的东西，codex
> headless 自建路径没有。上一轮补 `plan` 时已经遇到过一次。

### 0.3 测量前提：现在根本量不出收尾耗时

- 四臂 **202 个 runtime event 中，`finalization` 事件数 = 0，带 timestamp 的 = 0**。
- 上一轮给出的「收尾上界中位数 24.0 秒」是**推算的上界**
  （`latency − (initial_root − last_remaining_research)`，n=10，范围 20.9–62.9），
  **不是实测收尾耗时**。d/weekly 的 62.9 秒长尾说明普通路径与长尾路径差一倍以上。
- **不要把这个上界当成「收尾需要 24 秒」去设计 deadline。** 它只能用来做 sanity check。

### 0.4 本轮基线（c_long_capped，180s / 6 calls / floor 0）

T3 的对照就是这一列，不要重新生成：

| case | 事件级 stop_reason | latency | tool_calls |
|---|---|---|---|
| `rebound-duration` | `model_finish` | 73.1 | 3 |
| **`ruihuatai-valuation`** | **`headless_timeout`** | **150.3** | **5/6** |
| `weekly-market-cause` | `headless_protocol_rejected` | 144.7 | 4 |
| `current-mainline` | `model_finish` | 44.4 | 2 |
| `unfamiliar-methodology` | `model_finish` | 37.6 | 0 |

同一 profile 在 T1 中，`weekly-market-cause` 又翻成
`model_finish / 74.1s / 6 calls`。因此上表与 T1 的单次 stop/latency 都不能充当稳定
回归门；真正可复验的是 `finalization`、请求/响应配对和生效预算等结构字段。

---

## 1. 工作区现状（开工前核对）

```bash
git -C /Users/a77/finance-workspace-private-synthesis-release status --short
git branch --show-current      # 应为 eval/budget-calibration
```

| 项 | 值 |
|---|---|
| 基线分支 | `eval/budget-calibration` @ `9fd55ba9`（**尚未合并 main，等用户确认**） |
| `main` | `fd0f77e3` |
| 解释器 | **必须** `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` |
| 全量基线 | `13 failed, 3687 passed`：其中 11 红是 userspace/subconscious 环境耦合（8+3）；另外 2 个 `test_acceptance_board` 是父 revision 已存在的确定性 CLI contract/test drift。都不是本轮回归，但后两项不是宿主环境噪声 |
| 已知 flake | `test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state`，不要归到本轮 |
| CLI | 须在仓库根执行；`--compare` 现可直接吃 `*.normalized.json` |

---

## 2. T0 — 强制开工动作

读 `docs/prediction-ledger.md` 的 Open 表回填。**先回填再归因**，顺序不能反。
当前 pending：`R-20260804-02`（需真 rollout JSONL）、`R-20260804-09`（本轮主题）。

**完成判据**：每行 outcome 已更新，或明确写「本轮无新证据」。

---

## 3. T1 — 装上测量仪器（必须先于 T2）

没有它，T2 做完你无法判断是修好了还是运气好。

### T1.1 让 codex headless 发 `finalization` 事件

在研究窗口关闭 / 预算耗尽、准备让模型收口的那一刻发一条，payload 至少含：

- `reason`（`research_stage_closed` / `tool_budget_exhausted` / `deadline_pressure`）
- `remaining_seconds`（交接时刻的剩余 root）

`finalization` **已经在落盘白名单里**（`_DIAGNOSTIC_EVENT_KINDS`），也**已经有归一化
映射**（`_BENCHMARK_STEPS: finalization → synthesize`）。不需要改这两处。

### T1.2 让事件带时间戳

当前 `EpisodeEvent` 只有 `(sequence, kind, payload)`，没有时间字段。两条路，自己选：

- 在 `payload` 里放 `timestamp`，并让 `normalize_harness_trace._event_timestamp`
  也读 payload（它现在只读 record 顶层）；
- 或在 `RuntimeDiagnostics` 序列化时提到事件顶层。

**约束**：必须活过 `_sanitize_diagnostic_value`，且归一化产物里能读到。

### 完成判据

- 用 `c_long_capped` 跑一次五题，产物中 `finalization` 事件数 **≥ 1**；
- 至少能算出**一个 case 的实测收尾耗时**（`finish.timestamp − finalization.timestamp`）；
- 归一化后 `unmapped_count` 仍为 0（覆盖率契约测试守着）。

---

## 4. T2 — 显式收口交接（本轮唯一的产品改动）

研究窗口关闭时，除了拒绝那次工具调用，还要**明确告诉模型接下来做什么**。

参考 `agent_episode._start_finalization` 的形状，但**不要**把 codex headless
硬塞进 `agent_episode` 的路径——两者的事件构造方式不同（上一轮补 `plan` 时已确认）。

最小实现方向（不强制，按证据选）：

- 在 `research_stage_closed` / `tool_budget_exhausted` 的 rejection payload 里补一条
  明确指令 + 剩余秒数，形状可参照现有 `retry_hint`（`headless_tool_gateway.py:552`）；
- 同时发 T1.1 的 `finalization` 事件。

### 完成判据

- **不修改** `total_seconds` / `floor_ratio` / `max_tool_calls` 的任何默认值或 profile；
- `git diff` 里生产改动只落在收口交接这条路径上；
- 全量测试仍维持同一分账：11 个环境耦合 + 2 个 acceptance CLI contract/test drift；
  不能只对齐总数后统称“宿主环境红”。

---

## 5. T3 — 验收（可证伪，不是「看起来好多了」）

用 `c_long_capped` 重跑同五题（`as_of=2026-07-24`），与 §0.4 逐 case 对照。

### 主判据

**`ruihuatai-valuation` 的事件级 `stop_reason` 从 `headless_timeout` 变为
`model_finish`，且 `latency < 150`。**

### 必须同时记录（决定下一轮改哪层）

| 观测 | 说明什么 |
|---|---|
| 交接时刻的 `remaining_seconds` | 是否 ≥30 秒（R-09 的原始预测） |
| 实测收尾耗时 | 与 24.0 秒上界中位数对比；若远大于它，说明收尾本身太慢 |
| 已能完成的 case 本次是否仍 `model_finish` | 单次确认；同 profile 有随机翻转，不能单独作为无回归门 |
| `weekly-market-cause` 的 `headless_protocol_rejected` 有无变化 | 它不是 timeout，属另一条线 |

### 三种结局，分别怎么记

| 结局 | 结论 | 账本 |
|---|---|---|
| 瑞华泰 `model_finish` | PRIMARY 确认为「缺显式交接」，修复有效 | `R-09` → `confirmed` |
| 仍 timeout，但**实测收尾耗时 > 交接时剩余** | PRIMARY 转移到「收尾本身太慢」，是**另一层**（合成链，不是交接） | `R-09` → `refuted`，新开一条 |
| 仍 timeout，且收尾耗时 < 剩余 | 交接没真正生效，先查生效值不是配置值 | `R-09` → `refuted`，回查 T2 |

**`refuted` 不要粉饰成 `pending`。** 它是「上次判错了层」的硬证据，
`HARNESS_FIX` 的 streak 会因此累计——连续 3 次触发架构升格线。

---

## 6. 硬约束

### 不要做

- ❌ **不要移墙**：`total_seconds` / `floor_ratio` / `max_tool_calls` 一律不动。上一轮已证无效。
- ❌ **不要重跑四臂标定**。结论已验收。只跑 `c_long_capped` 做对照即可。
- ❌ **不要把 24.0 秒当成收尾实际需要的时间**——它是推算上界，长尾到 62.9 秒。
- ❌ **不要发明 `fix_type`**。冻结七值。本轮预期是 `HARNESS_FIX`。
- ❌ **不要为满足指标制造事件**。`finalization` 是真实存在的交接点才发，不是为了让 `synthesize` 列非空。
- ❌ **不要合并 `main`**——等用户确认；不强推。

### 必须做

- ✅ 验证时**断言生效值，不是配置值**（本项目最贵的教训：配置 180、到模型手上约 21）。
- ✅ 归因用**事件级** `finish.payload.stop_reason`，不是 arm 级（arm 级是事后裁决，见 `docs/trace-profile.md` §2）。
- ✅ 新发现的字段陷阱回写 `docs/trace-profile.md`。
- ✅ 每条建议带可证伪 `verification_prediction`，写进 `docs/prediction-ledger.md`。
- ✅ 提交前 `git status --short && git branch --show-current`。

---

## 7. 交付物

```
intelligence/eval/measurements/2026-08-04b-finalization/*.json    重跑产物 + 归一化
docs/verification/2026-08-04b-finalization.md                     结论 + 逐 case 对照
docs/prediction-ledger.md                                         R-09 回填
docs/trace-profile.md                                             收尾耗时首次可测 → 更新 §3 盲区清单
```

## 8. 延伸阅读

| 文件 | 什么时候读 |
|---|---|
| `docs/verification/2026-08-04-budget-calibration.md` | **开工必读**——本轮的全部前提 |
| `docs/trace-profile.md` §2 / §3 / §8 | **开工必读**——字段陷阱、盲区清单、覆盖矩阵 |
| `docs/prediction-ledger.md` | **开工必读** |
| `intelligence/services/agent_episode.py:1459` | 参照它的 `_start_finalization` 形状 |
| `intelligence/services/headless_tool_gateway.py:536-563` | 拒绝 payload 的构造点，T2 的落点 |
