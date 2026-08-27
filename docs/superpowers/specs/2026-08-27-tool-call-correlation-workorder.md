# 工单：episode 事件 tool_request/tool_result/tool_error 共用 call_id（2026-08-27）

- 状态：**待认领**。P0 单变量、零模型可见字节改动；§6 的 P1/P2 是指针不是本单范围。
- 来源：2026-08-27 harness 六层架构审查 L6 缺口 + 独立复核实测
  （复核在 live 8792 样本 run 上证实：`tool_request` 4/4 带 `call_id`，
  `tool_result` 0/4 **连字段都没有**）。
- 基座：`gitea/main@61dd5f79`，工单分支 `docs/foresight-root-and-span-io`
  （干净树 `/Users/a77/fwp-wt-l6-spanio`，用后待删）；实施方另开 `fix/` 分支。
- 台账：预注册 `R-20260827-15`，行与本单同提交（crosswalk 正向门要求）。
- 设计事实源分工：`docs/span-io-trace-prd.md`（Draft v2）管 **`trace.jsonl` 面**的
  结构化 IO / `parent_span_id`；本单只治 **episode 事件面**的 call 配对，
  两面不重叠、不互相等待。本单是 L6 里改动面最小、可独立验收的一片。

---

## 0. 一句话

**请求有名，结果无名。** 模型上下文里配对是全的（`role=tool` 消息带
`tool_call_id`），但 durable 事件流里只有 `tool_request` 带 `call_id`，
`tool_result` / `tool_error` 不带——事后分诊在同名工具重复调用时无法可靠配对。
这是 L6「request/result 配对」缺口的最小根。

## 1. 现状实测（2026-08-27，live 8792 @41d9d8d2 样本）

样本 `users/probe-cutover-0827e/runs/run_20260827_195210_064576/continuous-episode.json`：

| 事件 | payload 是否带 call_id | 实测 |
|---|---|---|
| `tool_request` | ✅ 有 | 4/4 非空 |
| `tool_result` | ❌ **无该字段** | 0/4 |
| `tool_error` | ❌（本样本无 error 事件，代码同形，见 §2） | — |

同 run 的 `trace.jsonl` 19 步均无 `input` / `parent_span_id` / `call_id` 字段——
那是 PRD 的面，本单不动。

## 2. 机制：三个发射点，`call.call_id` 都在作用域内

`intelligence/runtime/agent_episode.py`（行号锚定 `61dd5f79`，漂移时以符号/字符串锚为准）：

| 发射点 | 现状 | 关键约束 |
|---|---|---|
| `ledger.add("tool_request", request_payload)`（:415 邻域） | payload 已含 `call_id` | 不动 |
| `ledger.add("tool_result", {**public_observation, **timing})`（:502 邻域） | 缺 | ⚠ `public_observation` 同时是模型视图底稿（:503 `model_view = dict(public_observation)`）——**`call_id` 必须像 `timing` 一样只进 `ledger.add` 的展开，不得写进 `public_observation`** |
| `_append_tool_error` 的 `ledger.add("tool_error", {**payload, **(timing or {})})`（:541 邻域） | 缺 | ⚠ 同一个 `payload` 在 :546 **原样喂模型**——`call_id` 只进 ledger 展开（照抄 :539 注释里 timing 的纪律：「审计要全量、模型要够用，同一份事实两个出口」） |

投影链：ledger 事件 → `intelligence/services/episode_projection.py::project_durable_events`
→ `continuous-episode.json` 的 `events[]`。payload 透传（实测 `telemetry` 等字段
在产物里都在），**无需改投影**。

## 3. P0 · 做什么（单变量）

`tool_result` / `tool_error` 两处 `ledger.add` 的展开里补 `"call_id": call.call_id`。
就这一件事。

### 红线

1. **模型可见字节零改动**：`messages` 里喂模型的 content 不得因本单变化。
   §2 两处 ⚠ 是唯一的踩雷位——加错位置（写进 `public_observation` / 模型 `payload`）
   就同时污染模型上下文与既有 prune/预算逻辑。
2. **消费侧 fail-open**：历史产物的 `tool_result` 无 `call_id`，任何读取/统计侧
   必须容缺（`.get()`，不得下标硬取）。**不回填旧 run**（对齐 trace-profile 的
   「不回填」既有纪律）。
3. 不动 `trace.jsonl` schema（PRD 面）、不动 `stream.jsonl` / `run_events` 合同、
   不做 SQLite 投影、不据 call_id 加任何拦截门。

## 4. 验收判据（五条）

1. 修后新 run：每个 `tool_result` / `tool_error` 事件 payload 带非空 `call_id`，
   且与同 episode 内**恰好一个** `tool_request` 配对（单射）。
2. 同名工具重复调用用例：同一 episode 两次调用同名工具，配对靠 `call_id`
   不靠 `name` / 顺序（两对各自闭合）。
3. 模型可见字节不变：同一夹具下修前修后 `messages` 内容逐字节相等。
4. 旧产物容缺：对无 `call_id` 的历史 `tool_result` 读取/统计不抛错。
5. 全量 pytest 不降（基线以领单当天 `check_test_receipt.py --expect-revision`
   收据为准）。

## 5. 变异点（先红后绿，四条逐个精确击杀；⚠ 变异前先 commit）

| # | 变异 | 预期 | 抓的是 |
|---|---|---|---|
| 1 | 去掉 result 侧 `call_id` | 判据 1 钉**红** | 字段真的带上了 |
| 2 | `call_id` 值换成 `call.name` | 判据 2（同名重复）钉**红** | 配对键是 id 不是名字 |
| 3 | 把 `call_id` 写进 `public_observation` / 模型 `payload` | 判据 3（字节不变）钉**红** | §3 红线 1 有测试守着，不只写在文档里 |
| 4 | 消费侧改成 `payload["call_id"]` 硬取 | 判据 4（容缺）钉**红** | fail-open 真的在 |

## 6. 后续批次（指针，不在本单）

- **P1**：PRD Phase 1（`append_step` 接线 `input` + `parent_span_id` + 结构化 IO）。
  设计判据在 PRD，认领时另开单变量批次、另预注册台账号。
- **P2**：revision / join-key 戳（`capability_id` / `map_revision` / `code_revision`）
  与 SQLite 投影——同上。
- 记忆根合并（A 独有 12 条 corrections / 21 条 answer_scores / 14 卡 +
  C 根独有 12 条 / 2 卡）——见 `R-20260827-16` 成立条件，另立工单（未立）。

## 7. 台账预注册

`R-20260827-15`，行随本单同提交。

**判据**：§4 五条验收（第 5 条 = pytest 收据）全过 + §5 四条变异逐个精确击杀。

**失败形状**：字节变了 → `call_id` 写进了模型视图底稿；同名重复配不上 →
拿 `name` 当了配对键；旧 run 统计炸了 → 消费侧硬取键。

**成立条件**：本单只证明 durable 事件面可靠配对成立；**不覆盖** `trace.jsonl`
面的因果链（PRD/P1），也**不证明**任何路由质量结论。离线绿≠confirmed，
须一次 live run 回读 events 配对。
