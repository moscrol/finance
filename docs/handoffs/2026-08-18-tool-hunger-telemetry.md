# Handoff：工具饥饿信号——把「agent 想要但没有的能力」变成结构化需求数据

日期：2026-08-18
派单人：主 agent（2026-08-18 评估盘点批次，ai-agent-book 第 5 章判定更正的第一步）
关联：与 `2026-08-18-dead-assets-consumption-wiring.md`（死资产接线）天然联动——饥饿数据是「下一批注册什么 dataset」的输入。两单改动面不同文件，可并行。

## 背景

生产 agent 是封闭工具注册表，自己不能造工具；每种新问法都靠人工判断要不要注册新
dataset（今天的死资产单就是拍脑袋选了四张表）。书里第 5 章的元能力（代码=能造工具的
工具）在运行时层是有意缺口；补它之前先要**可观测**：agent 到底在哪些问题上「想要
而不得」。本单只做观测，不做任何自动造工具。

## 已核实事实（派单前实测）

1. `intelligence/runtime/agent.py` `_run_tool()`：模型点名不存在的工具 → 只回
   `未知工具「name」。` 一句话给模型，**无结构化留痕**。
2. `intelligence/services/episode_tools.py` `_finance_query_failure_result()`：语义层
   拒绝（dataset/字段/筛选无效）已产出结构化 `ToolRunResult`（`failure_code=
   "invalid_query"`），但 observation 截 160 字，**被拒的 dataset/metrics 请求名是否
   完整落盘待核实**。
3. 生产 run 目录：`$FORESIGHT_USERS_DIR/<user>/runs/`（linxiaoqi5111 现有 376 个 run），
   sidecar 探针 run 另落 `~/.finance-runtime/live-probe-traceability/.../runs/`。
4. 两条运行时车道：continuous episode（生产 ask 主路）与 inline agent
   （`runtime/agent.py` 12 工具 dispatch dict）。**执行方第一步先核实每条车道的工具事件
   分别持久化到哪**，别照抄本单假设。

## 目标

1. 三类饥饿事件结构化落盘（随 run 持久化，不新建全局服务）：
   - `unknown_tool`：模型点名注册表外的工具（工具名、参数键名、run_id、时间戳）
   - `finance_query_rejected`：语义层拒绝（完整请求 spec：dataset/metrics/dimensions/
     filters 摘要 + failure_code）——若现有 ToolRunResult 已够，只补缺失字段，别重造
   - `capability_denied`：工具在册但本轮 contract 未授权而模型点名要（若装配期已对模型
     隐藏、结构上观测不到，就在交接里写明「此类不可观测」并给理由，不硬造）
2. 聚合器：一条命令扫描 runs 目录出饥饿汇总（按事件类型 × 请求名计数 + 样本 run_id），
   人读 md + 机读 json 落 `intelligence/eval/measurements/`。CLI 形态执行方定
   （`python -m intelligence.cli tool-hunger --since 7d` 或 eval/ 脚本均可）。
3. 台账登记复查节奏建议（例如每周扫一次、进决策队列），最终节奏用户定。

## 非目标（明确不做）

- 不改 agent 行为：回给模型的文案一个字不动，检索/合成/prompt 不动
- 不做答案文本挖掘（「算不了」语义识别是另一档，噪声大，不在本单）
- 不自动注册工具、不造代码解释器（那是有先决条件的后续，见章审追记）

## 实施边界

只动：

- `intelligence/runtime/agent.py` `_run_tool` 未知工具分支（加落痕）
- `intelligence/services/episode_tools.py` 拒绝路径（补字段，若需要）
- 聚合器新文件 + 测试
- `docs/handoffs/inflight/main.md` 登记

不动：#164（数据根）、#165（stale 旁路）、#170 死资产单的实现面；8792；launcher。

## 测试要求（先红后绿）

1. 未知工具调用 → 事件落盘且回给模型的文案不变（逐字节同旧）
2. finance_query 拒绝 → 事件含完整请求 dataset 名（造一个不存在的 dataset 断言）
3. 遥测写入抛异常 → 主流程不受影响（try/except 降级），且该降级有测试
4. 聚合器对 fixture runs 目录出正确计数与样本引用
5. 空 runs 目录 → 聚合器出空报告不崩

## live 验证（合并后，#152 sidecar，不碰 8792）

问一题引导 agent 用 finance_query 查**当前不存在的 dataset**（例：竞价——若死资产单
已先落地，换任意仍不存在者），跑完用聚合器扫 sidecar runs：应看见对应
`finance_query_rejected` 事件与请求名。收据路径写进交接。

## 红线

- 遥测失败不许影响主流程（宁可丢事件）
- 不切 8792
- 事件里不落用户身份之外的敏感内容（记 run_id 即可回溯）

## 验收标准

1. 四件套绿；上述 5 类测试全绿
2. live 收据：一条真实饥饿事件被聚合器看见
3. 交接说明含：两条车道的持久化事实核实结论、capability_denied 可观测性结论
4. 台账 + inflight 登记

## skill 与工具建议

skill：leila-runtime + tdd。工具：git worktree、pytest、live_probe、Gitea API。

## 执行回执（2026-08-18）

树：`/Users/a77/fwp-wt-tool-hunger` `feat/tool-hunger-telemetry`。未切 8792。

### 两条车道的持久化核实

**Episode（生产 conversation / continuous，12 工具注册表）**

- Durable 仍是 `continuous-episode.json`：`events`（`tool_request` / `tool_result` / `tool_error`）+ `traces[]`。
- `finance_query` 拒绝：既有 `trace.detail=dataset=<name>; failure=<code>`，**dataset 名完整**；metrics / dimensions / filters 原先不在结构化字段里（observation 截 160 字，retry hint 可能带字段名）。
- 未知或未授权工具：durable 继续压扁为 `unknown_or_unauthorized_tool`（模型可见文案不变）。`authorize()` 的区分只在 Live `tool/error`，**不进** durable ledger。
- 本单新增旁路：`run_dir/tool_hunger.jsonl`。`ConversationOrchestrator` 进入 continuous `handle()` 时 `bind_run_hunger`；写入失败吞掉。

**Inline（`runtime/agent.py` 的 7 工具 dispatch）**

- 原先只回 `未知工具「name」。`，无 run 目录、无结构化留痕。
- 本单在未知分支 `record_unknown_tool`（只记工具名和参数**键**）。没有 sink 时事件丢弃（fail-open）。`intelligence.cli agent` 默认不绑 run 目录。

**`POST /api/runs`（#152 live_probe 默认口）**

- 走 `_run_ask` → `answer_query`，**不进** episode `finance_query`。live 验证若只用 `live_probe.py ask` 将看不到 `finance_query_rejected`。要打到饥饿接缝须走 conversation 口（sidecar 上 `POST /api/conversations/.../messages`）。

### capability_denied 可观测性

- 装配期：未授权工具不进模型 schema，模型默认看不见——「没用某能力」本身不可观测。
- 模型幻觉点名在册但本轮未授权的工具：batch 门用 `registry.resolve` 区分未注册 vs 未授权。本单分别写 `unknown_tool` / `capability_denied`。wire 仍是 `unknown_or_unauthorized_tool`。
- 结论：幻觉点名 **可观测**；安静地未选用某能力 **不可观测**（不是拒绝，是未调用）。

### 聚合与复查节奏

```sh
python -m intelligence.eval.tool_hunger --runs-dir "$FORESIGHT_USERS_DIR/<user>/runs" --since 7d
# 或
python -m intelligence.cli tool-hunger --runs-dir "$FORESIGHT_USERS_DIR/<user>/runs" --since 7d
```

建议每周扫一次，把 count 最高的 dataset/工具名推进「下一批注册什么」决策队列。最终节奏用户定。台账地图已登记。

### live 验证（sidecar :8797，未切 8792）

口：`POST /api/conversations` + `.../messages`（`skill_mode=auto`）。users 根
`~/.finance-runtime/tool-hunger-live/users/live-probe/runs/`。sidecar 已停。

1. **竞价 dataset 题 miss（schema enum）**：题面要求 `finance_query` 原样传入
   `auction_stock_daily`。模型承认该名不在 enum，改走 `market_daily` /
   `stock_daily` 成功查询。run `run_20260818_023904_259785`，无 `tool_hunger.jsonl`。
   未知 dataset 饥饿在生产上被工具 schema 的 `enum` 挡住，离线单测用
   `hunger_probe_nonexistent_dataset` 覆盖记录器。
2. **跨表字段题命中**：`stock_daily` + `metrics=["total_amount"]`（`total_amount`
   属 `market_daily`，但在公共 metrics enum 里）→ 语义层 `invalid_query`。
   run `run_20260818_024120_665888`，`tool_hunger.jsonl` 一条
   `finance_query_rejected`，`dataset=stock_daily` 完整。聚合器扫 2 个 run、事件 1 条。
   收据 `~/.finance-runtime/tool-hunger-live/receipt-cross-field.json`；
   汇总 `~/.finance-runtime/tool-hunger-live/aggregate/tool-hunger-live.{json,md}`。

### 四件套

- 本单 10 条 `test_tool_hunger.py` 全绿；ruff 绿。
- 全量 pytest：5386 passed / 12 skipped / 2 failed（未改这些文件）：
  `test_fallback_provider_failure_enters_its_own_backoff`（机械检查先写
  `PROVISIONAL_WRITTEN`）、`test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state`
  （context id 碰撞，单测重跑已绿）。收据 `~/.finance-runtime/test-receipts/20260817T183800Z-d0bc026b.json`。
- webapp：`pnpm lint` / `typecheck` / `test`（65）/ `build` 绿。
