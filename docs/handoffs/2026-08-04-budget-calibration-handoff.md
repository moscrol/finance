# 预算标定与账本闭环 — Codex 对齐 TODO（2026-08-04）

> **给 Codex 的读法**：第 0 节是已定案事实，**不要重新论证、不要重新发现**。
> T0 是强制开工动作（5 分钟），T1 只有你能做（需要 codex CLI），T2 是本轮主线。
> T3 依赖 T2 的数字。每个任务给了完成判据，判据没满足就不要报完成。
>
> **本轮的性质是标定，不是观测。** 观测层已经够用了（见 §0.4），继续补埋点是在
> 优化已经够好的那层。真正让用户吃亏的是预算容量，它一次都没被动过。

---

## 0. 起点状态：已定案，不要重开

基线 commit `292a58f1`（已合入并推送 `main`）。以下是本轮的**前提**，不是待验证项。

### 0.1 上一轮发现的根本形状：信道有损

控制面信息在**跨层投影**那一跳被静默丢弃或改写，导致归因被推到错误的层。
三个已确证实例（均已修复并合入）：

| 实例 | 真相 | 传到上层变成了什么 | 证据 |
|---|---|---|---|
| `invalid_actions` | harness 超时 | 「模型动作违规」 | `codex_headless_runtime` 原写 `len(unique_issues)`；`e179b15c` 两题的 `runtime_invalid_actions:1` 实为 `headless_timeout`，**真实违规 0 次** |
| `task` 事件 | runtime 发了 sequence=1 的 intent 地标 | 整条被落盘白名单吃掉 | 所有历史 artifact 的 `sequence` 从 2 起跳 |
| 映射覆盖 | 白名单放行 13 种 kind | 归一化只认 5 种，`mode_decision`/`invalid_action` 静默掉出比较 | `_BENCHMARK_STEPS` 补齐前 5/13 |

**这是本项目的主要失败形状。做任何归因前先问：这份信息有没有送到？**

### 0.2 五题的真实失败原因（不是模型能力问题）

`e179b15c` 五题中 2 题 `partial / headless_timeout`。失败链已定案：

```
ⓐ 研究窗口给太紧
      ↓
L5 网关关门（research_stage_closed）—— 按设计工作，不是 bug
      ↓
模型既没拿到数据、也没时间收尾 → headless_timeout
      ↓
L4 把 issue 计数错记成 invalid_actions=1     ← 已修
      ↓
ⓑ 审计读成「模型有违规动作」                   ← 已修
```

`rebound-duration` / `weekly-market-cause` 唯一的 `tool_error` 都是
`research_stage_closed`，由 `headless_tool_gateway.py:639` **主动拒绝**。
模型请求的是合法工具、合法参数。**不要把这两题当作模型能力证据。**

### 0.3 预算级联：配置 180s，到模型手上约 21s

实测（`e179b15c` / `rebound-duration`）：

| 层 | 值 | 出处 |
|---|---|---|
| case timeout | 180.0s | 题面配置 |
| `effective_timeout_seconds` | 90.0s | arm 字段 |
| `root_budget.allocated_seconds` | 60.0s | `diagnostics.root_budget` |
| 第 1 次取证后 `remaining_research_seconds` | 50.242s | `tool_result.payload.budget` |
| 第 2 次取证后 | 43.301s | 同上 |
| 第 3 次取证 | **被拒 `research_stage_closed`** | `tool_error` |
| 实际 `latency_seconds` | **60.0s** | == root budget，**没碰到 180 也没碰到 90** |

关门阈值（`headless_tool_gateway.py:134-141`）：

```python
_finalization_floor_seconds = min(45.0, max(5.0, initial_research_seconds * floor_ratio))
# 默认 floor_ratio = 0.65
```

60s × 0.65 ≈ **39s 预留收尾，研究窗口实际约 21s**。这与观测一致（43.3s 后再过约 4s
即跌破 39s → 关门），但**未经消融证明**——那正是 T2 要做的。

> 这个 65% 是**本轮唯一还没被证伪也没被证实的关键参数**。

### 0.4 观测层现状：够用了，不要继续补

词表已对齐 `agent-run-triage` skill 的 L1 九步（`vocabulary: triage-l1-9`）：

```
configure → intent → plan → route → retrieve → tool → observe → synthesize → stop
```

两侧真实路径实测覆盖：

| | workbench | codex |
|---|---|---|
| 序列 | `configure→intent→plan→route→retrieve→synthesize→observe` | `configure→intent→plan→tool→observe→observe→stop` |
| 九步覆盖 | 7/9 | 5/9 |

- **两侧共有 4/9**（`configure`/`intent`/`plan`/`observe`），埋点前只有 1/9。
- 门槛 `configure → intent → plan` **3/3 达标**，`first_divergence_step` 在该前缀内已有行为含义。
- 剩余缺口：workbench 缺 `tool`/`stop`，codex 缺 `retrieve`/`synthesize`。
  **`route` 在 codex 侧是结构性不存在，不要补**——codex episode 不做 skill 分派。

---

## 1. 工作区现状（开工前核对）

```bash
git -C /Users/a77/finance-workspace-private-synthesis-release log --oneline -1   # 应为 292a58f1
git worktree list
```

| 项 | 值 |
|---|---|
| 基线 | `main` = `292a58f1`，已推 origin |
| 解释器 | **必须** `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（系统 `python3` 是 3.14，缺依赖） |
| 全量测试基线 | `13 failed, 3684 passed` —— **13 红是宿主环境泄漏，不是回归** |
| 13 红构成 | `test_subconscious`(8) + `test_userspace`(3) + `test_acceptance_board`(2)，均因解析到真实 `/Users/a77/agent-memory` 而非 tmp |
| 已知 flake | `test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 四次中失败一次，未归因，**不要归到 08-04 的改动** |
| 其它 worktree | `finance-workspace-private` 在 `fix/grounded-chain-critical-path`（勿动） |

CLI（**须在仓库根执行**，否则 `ModuleNotFoundError`）：

```bash
python -m intelligence.eval.normalize_harness_trace <input> --kind auto
python -m intelligence.eval.normalize_harness_trace <a> --compare <b>   # 出 first_divergence_step
```

---

## 2. T0 — 强制开工动作（先做，5 分钟）

读 `docs/prediction-ledger.md` 的 Open 表，用本轮 trace 回填 `confirmed`/`refuted`。

**顺序不能反**：先回填再归因，否则新证据会被本轮结论污染。当前 3 条 pending：

| ID | 预测 | 卡在哪 |
|---|---|---|
| `R-20260804-02` | 真 rollout 的 `function_call_output` → `observe` | 需一份真 rollout JSONL |
| `R-20260804-04` | 仅超时的 case 不再出现 `runtime_invalid_actions` | **需 codex CLI —— 见 T1** |
| `R-20260804-07` | triage 报告的 `first_bad_step` 与本仓 `first_divergence_step` 同空间 | 需一次真分诊 |

**完成判据**：账本 Open 表每行 outcome 已更新或明确写明「本轮无新证据」。

---

## 3. T1 — 结掉 R-04（只有你能做）

上一轮无法执行：本机 PATH 上没有可执行的 codex CLI（`~/.codex/auth.json` 在，
`Codex.app` 在废纸篓）。你有。

已验证的两段：

| 段 | 断言 | 状态 |
|---|---|---|
| A | `count_invalid_actions(('headless_timeout',)) == 0` | 实测（单元） |
| B | `usage.invalid_actions=1` ⇒ `protocol_issues == ['runtime_invalid_actions:1']` | 实测（端到端） |

缺的是中间那跳：**codex runtime 由 stdout issues 得出 usage** —— 只有 code_reading 支撑。

**动作**：跑一次真 headless run（可复用 `e179b15c` 的五题题面，`as_of=2026-07-24`）。

**完成判据**：
- 至少一个 `headless_timeout` 的 case，其 `arms[].protocol_issues` **不含** `runtime_invalid_actions`；
- 该 case 的 `runtime_result.payload.issues` 确实含 `headless_timeout`；
- 账本 `R-20260804-04` 标 `confirmed`，evidence 写 artifact 路径 + 该两个字段的实际值。

---

## 4. T2 — 预算标定（本轮主线）

### 不要重新设计实验，它已经预注册了

`scripts/run_agent_runtime_benchmark.py:108` 已有四臂：

| profile | total_s | max_calls | synth_reserve | floor_ratio | 消融的变量 |
|---|---|---|---|---|---|
| `a_control` | 90 | 6 | 30 | **0.65** | 对照 |
| `b_floor_ablation` | 90 | 6 | 30 | **0.0** | 单变量：网关关门阈值 |
| `c_long_capped` | 180 | 6 | 30 | 0.0 | 加时长 |
| `d_long_expanded` | 180 | **12** | 30 | 0.0 | 加时长 + 加调用数 |

用 `--headless-budget-profile <id>` 注入，**只影响 benchmark，不动生产 tier 默认值**。

### 要回答的问题（按信息增益排序）

1. **`a_control` vs `b_floor_ablation`**：把 39s 的收尾预留降到 0，超时率变不变？
   这是最关键的单变量——如果 b 显著改善，PRIMARY 就是**关门阈值**而非总时长。
2. **`b` vs `c`**：floor 已归零后，再从 90s 加到 180s 还有没有边际收益？
3. **`c` vs `d`**：时长够了之后，瓶颈是不是转移到工具调用数（6 → 12）？

### 每臂必须记录

| 字段 | 从哪读 |
|---|---|
| 终态分布（completed/partial/failed） | `arms[].status` |
| `stop_reason` | **事件级** `finish.payload.stop_reason`，不是 arm 级（arm 级是事后裁决，见 `docs/trace-profile.md` §2） |
| 每次取证后的 `remaining_research_seconds` | `tool_result.payload.budget` |
| `research_stage_closed` 出现次数与发生在第几次取证 | `tool_error` 事件 |
| 实际 `latency_seconds` vs profile 的 `total_seconds` | 判断撞的是哪层墙 |
| 归一化后的 step 序列 | `--kind runtime-benchmark` |

### 完成判据

- 四臂各跑完五题，artifact 冻结进 `intelligence/eval/measurements/2026-08-04-budget-calibration/`；
- 能明确回答：**超时的 PRIMARY 是关门阈值、总时长、还是调用数上限**；
- 结论写成一条带 `fix_type` 的建议 + `verification_prediction`，记入账本；
- **不要顺手改生产默认值**——本轮只出标定结论，改值走下一轮。

---

## 5. T3 — L5 闸门阈值（依赖 T2）

`headless_tool_gateway.py:639` 的关门条件逻辑正确，**阈值从未标定**：

```python
if self._executed_count > 0 and remaining_research_seconds <= self._finalization_floor_seconds:
    return "research_stage_closed"
```

拿 T2 的数字回答：0.65 是不是过高？收尾真正需要多少秒（看 `finalization` 事件到
`finish` 的间隔）？**在 T2 出数字前不要改这个常量。**

---

## 6. 硬约束

### 不要做

- ❌ **不要继续补观测埋点**。门槛已 3/3，边际收益递减。
- ❌ **不要为满足指标制造事件**。`route` 在 codex 侧结构性不存在——造一个只为凑 5/9 是重编码。
- ❌ **不要发明 `fix_type`**。冻结七值：`SYSTEM_PROMPT_FIX` / `TOOL_DESCRIPTION_FIX` / `ROUTING_FIX` / `DATA_CONTRACT_FIX` / `HARNESS_FIX` / `EVAL_ONLY` / `NO_SYSTEM_FIX`。
- ❌ **不要静默压缩词表**。九步是 skill 的 L1，压缩必须先声明损耗。
- ❌ **不要把 `unknown` / `not_evaluable` 计入失败分母。**
- ❌ **不要合并 `main`**——等用户明确确认；不强推。

### 必须做

- ✅ 每条修复建议带**可证伪的** `verification_prediction`，写进 `docs/prediction-ledger.md`。
- ✅ 分诊/归因前先看 `docs/trace-profile.md` §2 字段陷阱（已有 11 条，含 `stop_reason` 分层、`invalid_actions` 口径、`sequence` 从 2 起跳的成因）。
- ✅ 新发现的字段陷阱回写 trace-profile —— 那是它随每次诊断增值的机制。
- ✅ 验证时**断言生效值，不是配置值**（本项目最贵的教训：配置 180、生效约 21）。
- ✅ 提交前 `git status --short && git branch --show-current`，大任务开分支。

---

## 7. 交付物

```
intelligence/eval/measurements/2026-08-04-budget-calibration/*.json   四臂冻结产物
docs/verification/2026-08-04-budget-calibration.md                    结论 + 证据
docs/prediction-ledger.md                                            回填 + 新增预测
docs/trace-profile.md                                                新发现的字段陷阱
```

## 8. 延伸阅读（按需，不必全读）

| 文件 | 什么时候读 |
|---|---|
| `docs/trace-profile.md` | **开工必读** §2 字段陷阱、§8 覆盖矩阵 |
| `docs/prediction-ledger.md` | **开工必读** |
| `docs/verification/2026-08-03-cross-harness-shared-layer-audit.md` | 想知道为什么跨 harness A/B 目前不成立 |
| `docs/verification/2026-08-04-improvement-loop-design-review.md` | 想知道 Improvement Loop 设计与 skill 的 7 处契约差 |
| `intelligence/eval/normalize_harness_trace.py` | 要做 A/B 首次分叉 |
