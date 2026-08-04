# 2026-08-04b Codex headless finalization 验证

## 结论

T1 仪器有效，T2 的显式指令也能穿过真实 `finance-tool` wrapper；但 T3 主判据失败，`R-20260804-09` 必须记为 **refuted**。

瑞华泰没有从 `headless_timeout` 变成 `model_finish`，而是在 135.555 秒以事件级 `headless_protocol_rejected` 结束。决定性证据不是“收尾耗时超过余量”，而是本次 live **根本没有进入 finalization**：第 5 个 `evidence_search` 只有 `tool_request`，没有 `tool_result`、`tool_error`、mailbox response 或 finalization；runtime 随后记为 `headless_command_failed`。

因此，本轮证伪的是“只要在 result/rejection 边界补显式交接，就能修复瑞华泰”的判断。真实绑定约束前移到 **in-flight tool 阻塞控制面交接**；不能再通过调 root、floor 或 calls 处理。

## 产物与可复现性

| 阶段 | revision | raw SHA-256 | normalized SHA-256 | source_dirty |
|---|---|---|---|---|
| T1（交接改动前） | `84c1eb73` | `a51fe2123441eb57ec1ce66414626690005fa441a02177720848d96de8cc23bd` | `ac0dbe713f6b77b6c06a39fb359b3725777e37b2c7cb7fbdaa3b4c200a5d5ac9` | `false` |
| T3（交接改动后） | `3dd867e9` | `93a097edc8bff3e9ec28b14d81aa4d77f2315669dd4097289b1aa52065d1e5ee` | `46f320bbefb18d89e32a4e925a376029595fc6f0d6a1ac763956f36e210fd0df` | `false` |

两次都只跑 `c_long_capped`；profile 逐字段相同：`total_seconds=180`、`max_tool_calls=6`、`synthesis_reserve_seconds=30`、`gateway_floor_ratio=0.0`。没有跑 a/b/d，也没有改生产 runtime。

归一化契约：T1 为 60 events / 0 unmapped / 6 timestamped / 1 finalization；T3 为 54 events / 0 unmapped / 5 timestamped / 0 finalization。
用新增派生字段从两份 raw artifact 复算，`unpaired_tool_requests` 为 **0 / 1**。两份
冻结产物早于 request id 埋点，因此这是 case 内 FIFO 的 legacy 弱配对；新产物会把
headless `request_id` 独立投影为 normalized `correlation_id`，mismatched id 不会互相
消费。该计数比手工对 mailbox exchange 更直接，但本身不宣称超时因果，也不能单独
证明迟到结果隔离。

## T1：仪器读数

T1 瑞华泰在既有 invalid-finish recovery 开始时发出：

- `finalization(reason=headless_invalid_finish)`；
- `remaining_seconds=16.165`；
- timestamp=`2026-08-03T19:41:27.312Z`；
- finish timestamp=`2026-08-03T19:41:43.502Z`，stop reason=`headless_timeout`。

两事件相隔 16.190 秒。因为 finish 是 timeout，这只是 **right-censored lower bound**：能说 recovery 至少用了 16.190 秒，不能说自然 finalization 需要 16.190 秒，更不能把旧推算的 24.0 秒当实测值。

## T2：实现与离线契约

生产改动只在 headless 收口交接路径：

- 成功 tool result 进入冻结 handoff window 时携带固定 instruction，并发一次幂等 finalization；
- 最后一个工具槽位耗尽时同样交接；
- transition 后后续研究调用 fail-closed；
- 原 `invalid_arguments.retry_hint`、模型、工具 schema 和预算 profile 不变。

离线测试证明两条边界成立：

1. mutable deadline 从 150 秒降到 25 秒后，成功 result 返回 instruction，事件为 `finalization(deadline_pressure)`；
2. `max_steps=1` 时首个 result 返回 instruction，事件为 `finalization(tool_budget_exhausted)`；
3. fake Codex 只有读到 wrapper JSON 中的 instruction 才给合法 finish，最终事件顺序为 `tool_result → finalization → finish`，stop reason=`model_finish`。

focused 回归：97 passed / 1 skipped；Ruff 通过。

## T3：逐题事件级对照

下表的 stop reason 只读 `diagnostics.events[kind=finish].payload.stop_reason`，不用 arm 级后处理字段。

| case | T1 stop / latency | T3 stop / latency | finalization | 判读 |
|---|---:|---:|---:|---|
| `rebound-duration` | `model_finish` / 61.574s | `model_finish` / 62.513s | 0 | 本次仍为 `model_finish`；T3 arm 被后处理为 `semantic_repair`，不能覆盖事件级读数 |
| **`ruihuatai-valuation`** | **`headless_timeout` / 150.043s** | **`headless_protocol_rejected` / 135.555s** | **0** | **主判失败；没有进入交接** |
| `weekly-market-cause` | `model_finish(partial)` / 74.122s | `model_finish(completed)` / 83.871s | 0 | 事件级仍完成；arm 的 mandatory-capability 缺口是另一层 |
| `current-mainline` | `model_finish` / 50.059s | `model_finish` / 49.465s | 0 | 本次仍为 `model_finish` |
| `unfamiliar-methodology` | `model_finish` / 33.900s | `model_finish` / 35.793s | 0 | 本次仍为 `model_finish` |

已能完成的四题在 T3 这一次仍为事件级 `model_finish`；这只是单样本观察，不能叫
稳定“无回归”。同 profile 的更早运行中，`weekly-market-cause` 曾在
`headless_protocol_rejected / 144.7s / 4 calls` 与
`model_finish / 74.1s / 6 calls` 之间翻转。瑞华泰虽未把 150 秒用满，但没有合法
finish，所以不满足“`model_finish` 且 `<150s`”的合取门禁。

## 瑞华泰的第一次失败边界

事件序列的最后一段是：

1. `kb_search` result：`remaining_research_seconds=89.691`、executed=4/6；
2. `tool_request(evidence_search)`；
3. 没有对应 `tool_result` / `tool_error`；
4. `runtime_result.issues=[headless_command_failed]`；
5. `finish(headless_protocol_rejected)`。

动态计数也一致：5 个 tool request、4 个 mailbox exchange。静态路径显示 mailbox wrapper 等 response 的 deadline 固定为 60 秒，超时后 `raise SystemExit("finance tool mailbox timed out")`；Codex parser 将非零 command exit 记为 `headless_command_failed`。artifact 没有保留该 command 的 stderr，因此“本次具体命中 60 秒 timeout 字符串”是由动态缺失响应与静态唯一等待路径共同支持的推断，不冒充直接日志读数。

这解释了为何 T2 单测为绿、live activation 却为 0：instruction 只附着在 **已返回的** result/rejection；in-flight 工具没有返回时，gateway 无法在同一边界交接。把 T3 的 0 个 finalization 当成“收尾很快”或“仪器坏了”都不成立。

## 归因与下一层

- `R-20260804-09`: **refuted**。
- 本轮 first bad boundary：`tool_request(evidence_search) → response absent → mailbox 60s nonzero exit`。
- 当前 PRIMARY：headless 的 in-flight 工具没有 deadline-aligned preemption/return contract，finalization transition 依赖工具先返回；精确的 wrapper 退出字符串仍缺原始 stderr。
- fix type 仍为冻结枚举 `HARNESS_FIX`；本项目连续 refuted streak 从 0 变为 1。

下一轮优先验证 **per-tool deadline handoff**，不是再加总预算：当工具的剩余安全执行窗口小于 handoff reserve 时，gateway 必须在阈值处返回 `research_stage_closed + instruction`、发一次 finalization，并隔离迟到结果。主门是 deterministic slow-tool 离线测试：同一 request id 恰好一个预期 error 终态、`unpaired_tool_requests=0`、finalization remaining 约等于冻结 handoff window，且 late result 不写入 episode。单次瑞华泰 live 只能在离线主门通过后作确认，不能单独把 R-10 记为 confirmed。

R-10 还必须同时关掉两个潜伏契约：`_pending_finalization_reason` 的剩余 calls 要和
`_budget_payload` 一样读取 root ledger 的生效余量；handoff window 要从 profile / 生效
预算派生并落盘，不能继续把 `initial_research_seconds * 0.20` 当成不可见的第二份 reserve。

替代方案是提前终止研究进程并开 no-tools finalizer；它更确定，但会丢同一进程上下文并新增一次 provider 调用。只延长 mailbox 的 60 秒或 root 总时长不会创建交接点，已排除。

## 测试账

- Focused（gateway/runtime/normalizer/benchmark）：`97 passed, 1 skipped`。
- 全量 `intelligence/tests`：`2 failed, 3704 passed, 2 skipped`。
- 两个失败均为 handoff 已列的 `test_acceptance_board` **确定性 CLI contract/test drift**；在 T2 父 revision `f4b8c589` 单独复跑同名测试仍为 `2 failed`，因此不是本轮回归，但也不是宿主环境噪声。
- handoff 记录的另外 11 个 userspace/subconscious 环境红在本次显式 `env -u FORESIGHT_USERS_DIR` 下未复现；不把“13 变 2”写成产品修复。

## 2026-08-04c：R-10 观测前置补充验证

本补充不修改上面的 T1/T3 历史读数，也不提前执行 R-10。新增契约只有三项：

1. headless gateway 的同一次 `tool_request` 与其 `tool_result/tool_error` 共享 32-hex
   request id；mailbox 路径直接复用 request filename stem，不生成第二个身份；
2. normalized event 用独立 `correlation_id` 保留 benchmark `request_id` 或 Codex
   `call_id/tool_call_id`。有 id 时严格同 id 配对，只有历史双方均无 id 时才按 case FIFO；
3. `unpaired_tool_requests` 为 `int | null`：benchmark/Codex 有配对词表，Workbench
   不具备逐工具词表所以明确为 `null`，不再用假健康的 0 表示“没埋点”。

离线可证伪结果：mismatched benchmark id 保持 1 个 pending；Codex synthetic 的一组
完成调用加一个悬空调用得到 1；Workbench 得到 `null`；T1/T3 legacy raw artifact 仍为
`0/1`。旧 v2 event 缺 `correlation_id` 时窄兼容补 `null`，其他未知字段仍显式拒绝；
派生计数不一致的异常恢复同时报告 declared 与 recomputed 安全值；合法整数显示值，
非法字符串/容器只显示类型，不能把篡改内容复制进 CI 日志。

测试账：

- Focused（gateway / normalizer / Codex runtime / benchmark）：`111 passed, 1 skipped`；
- Ruff：通过；
- 首轮继承本机 `FORESIGHT_USERS_DIR/SUBCONSCIOUS_VAULT`：
  `13 failed, 4199 passed, 3 skipped`，其中 11 条为已知 userspace/subconscious 环境耦合；
- clean-host（同时 unset 用户目录与 vault override）：
  `2 failed, 4211 passed, 3 skipped`；两条均为父 revision 已存在且同名同数的
  `test_acceptance_board` 确定性 CLI contract/test drift，不是本轮回归，也不是宿主噪声。

本步没有修改 budget/profile、没有运行 live、没有实现 slow-tool handoff。R-02 因仍缺
真 rollout JSONL 保持 pending；R-10 因生产控制流尚未实现保持 pending。

另对 `/Users/a77/agent-memory` 的未推分支做了只读审计：它已相对远端
`173 ahead / 2 behind`，本地侧涉及 401 个路径、66,378 行新增，包含两个红线禁止的
`workbench.sqlite3` 和大量完整 run 产物。因此本轮没有 push 该 memory 分支；这与本代码
分支的独立交付不互相阻塞。
