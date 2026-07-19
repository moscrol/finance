# Deep Research Runtime Hardening Design

## 目标

修复 `fix/deep-research-p1b-runtime` 审查中确认的运行时缺口，使金融回答的事实闸门、LLM 调用预算、根截止时间、证据跨轮继承和查询去重都具备可证明的硬约束，同时避免新增一套平行研究管线。

## 方案取舍

### 1. 市场复盘统一进入 Grounded Composer

市场复盘不再豁免 `AnswerSpec` 事实门禁。开启通用 Grounded Presenter 时，复用现有 `DecisionBrief → Grounded Composer → deterministic validator → semantic judge → presenter` 链路；模型可自然改写，但每句必须绑定 claim 和 EvidenceAtom，展示层再删除 marker。

如果 Grounded Composer 不可用或未通过门禁，直接保留结构化 `AnswerSpec` 投影。旧的无 marker 散文不再作为可信降级路径。

没有采用“公司名、数字、日期词面差集”作为主闸门，因为它无法识别不含新实体的语义偷换；词面检查只适合作为纵深防御。

### 2. LLM 预算改为逐 HTTP 尝试原子预占

`LLMCallLedger` 在每次 `_post_chat*` 真正进入网络边界前执行 `try_reserve()`。预算判断与预占由同一把锁保护，provider fallback、重试、流式降级和并发线程都逐次消耗预算。

预占成功的调用无论成功或失败都写一条完成记录；预算不足时不发 HTTP，并以 typed exception 向公共入口返回稳定的“预算耗尽”降级原因。

### 3. Agent loop 使用绝对根 deadline

`run_agent_loop` 接收 `ResearchDeadline`。未传入时才由 `total_seconds` 创建本地 deadline；不再强制最少运行一秒。

每次 LLM 决策和工具执行前检查剩余时间。LLM timeout 为 `min(配置上限, remaining)`；工具通过 `AgentToolContext` 接收同一个绝对 deadline，内置 Web、资讯和知识库工具据此设置其底层 timeout。超时后不再启动下一次副作用。

### 4. 证据契约完整 round-trip

跨轮合并必须保留 `candidate_facts`；`EvidenceRef` 反序列化必须恢复 `content_hash/source_revision`；从 AnswerSpec 派生 EvidenceAtom 时将这两个字段写入 provenance。

验收以 `to_dict → merge/rehydrate → EvidenceAtom` 等价测试为准。

### 5. QueryLedger 使用 per-key single-flight

全局锁只保护 `entries/inflight` 映射。首个调用者登记该 key 的 Future 后在锁外执行 fetch；相同 key 等待同一 Future；不同 key 并行执行。

失败不会写入成功缓存，但会把同一次 in-flight 异常广播给所有等待者。Web 查询 key 加入 `limit` 和 proxy 标识等影响结果形态的参数。

### 6. 控制面与展示面来源分离

`AgentEvidence` 同时携带公开来源标签和内部 locator。引用只消费公开标签；relation JSON 路径只保留在控制面。

Conversation citations 在公开投影前按稳定语义键去重，避免 owner `SkillOutput` 与原始 `AskResult` 双重追加同一来源。

## 错误处理

- 预算耗尽：typed refusal，不发 HTTP，走既有模板/结构化降级。
- deadline 耗尽：agent 返回已收集部分证据并标记 `预算耗尽：总时长`。
- Grounded Composer 不可用：保留结构化 AnswerSpec，不尝试无约束市场散文。
- Query fetch 失败：同一轮等待者收到同一异常，后续新调用允许重试。

## 验收

- 市场复盘新增证据外“算力主线”必须被拒绝；合法 grounded 市场复盘可通过。
- `max_calls=1` 时两个 provider fallback 最多只发一个 HTTP。
- `total_seconds=0` 或根 deadline 已过期时 agent 不调用 LLM/工具。
- provenance 和 candidate facts 跨轮不丢失。
- 同 key 并发只 fetch 一次，不同 key 能真实并行。
- 公开引用不包含 `wiki/relations/*.json`，重复 citation 被去重。

