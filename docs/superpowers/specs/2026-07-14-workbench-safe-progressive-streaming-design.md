# Workbench 安全渐进式流式回答设计

## 背景与问题

Workbench 已通过 SSE（Server-Sent Events，服务端事件流）发送研究阶段、模块、引用和
`text.delta`。但当前主回答路径仍先等待非流式 LLM 调用结束，再把整篇答案作为一个
`text.delta` 发给前端。因此用户能看到研究进度，却不能逐步看到答案正文。

真实 UI 验收还暴露了两项叠加降级：

1. Hybrid RAG（向量检索 + BM25 关键词检索）在运行环境缺少 `FlagEmbedding` 时直接
   失败，没有自动回退到 BM25；
2. 内置 GLM 已配置并实际尝试调用，但没有在本轮合成预算内返回完整答案，记录为
   `provider_timeout`，最终只能展示确定性 `AnswerSpec` 模板。

本设计的目标不是把未经验证的模型 token 直接暴露给用户，而是在保持证据门禁和 60 秒
硬截止的前提下，显著改善首屏等待感和降级时的可读性。

## 目标

- 检索完成并形成 `AnswerSpec` 后，立即展示可核验的结构化草稿。
- GLM 在后台使用流式接口生成自然语言精修版。
- 只有完整精修版通过现有证据、公司归属、日期、必需 notice 和禁用术语门禁后，才替换
  可核验草稿。
- GLM 超时、不可用或质量门禁拒绝时，保留可核验草稿，不清空、不闪回、不显示“生成
  失败”。
- Hybrid RAG 的向量依赖不可用时自动回退 BM25；BM25 也失败时才回退图谱与结构化证据。
- SSE 断线重连、事件重放和最终 run artifact 必须保持幂等一致。

## 非目标

- 不把未经完整门禁验证的模型 token 直接显示给用户。
- 不在本轮安装或打包 `FlagEmbedding`、BGE-M3 模型等重量级依赖。
- 不放宽 AnswerSpec 事实边界、目标公司证据归属或 60 秒硬截止。
- 不改知识库 relation 数据，不把图谱弱关联升级为公司硬证据。
- 不合并 `main`、不切换 canonical 8792 运行时；发布仍需用户单独确认。

## 方案比较

### 方案 A：安全双阶段流式（采用）

先展示确定性可核验草稿；模型流式内容在服务端缓冲，完整通过门禁后再逐段替换。

优点：首屏有真实内容；模型幻觉不会提前泄露；超时时草稿仍可用。缺点：自然语言精修
本身仍需等待完整门禁，不能做到裸 token 的即时显示。

### 方案 B：直接流式模型 token

模型每个 token 到达就发给前端。

优点：对话感最强、模型首 token 延迟最低。缺点：未经验证的事实、公司和数字可能已经
显示，事后质量门禁无法真正撤回，违背金融回答的 fail-closed 约束。

### 方案 C：生成完成后打字机动画

先生成完整答案，再在前端分片显示。

优点：实现最简单、门禁安全。缺点：不降低真实等待时间，只是视觉动画；不能解决模型
超时和检索降级的体感。

## 总体架构

回答分为两个可识别阶段：

1. `verified_draft`：由已经完成检索和门禁的 `AnswerSpec` 确定性渲染；
2. `validated_synthesis`：GLM 流式生成到服务端缓冲区，完整通过门禁后的自然语言版本。

SSE 增加版本化 answer snapshot 事件，而不复用“只能追加”的裸 `text.delta` 来表达替换：

```json
{
  "event_type": "answer.snapshot",
  "payload": {
    "revision": 1,
    "phase": "verified_draft",
    "text": "...",
    "final": false
  }
}
```

精修通过后发送 `revision=2`、`phase=validated_synthesis` 的完整 snapshot；模型失败时发送
同一草稿的终态 snapshot，`phase=verified_fallback`、`final=true`。Snapshot 是覆盖语义，
因此重放不会重复拼接。

现有 `text.delta` 保留兼容，但新前端优先消费 revision 更高的 `answer.snapshot`。旧客户端
仍可在 run 完成后通过 `answer.md` 获得最终内容。

## 后端数据流

### 1. 检索与可核验草稿

1. 路由和 Skill 执行保持现状。
2. 形成并 `finalize_answer_spec()` 后，调用确定性 renderer 得到草稿。
3. 对草稿运行现有清洗、目标公司 notice 保留和用户层工程术语过滤。
4. 持久化并发送 `answer.snapshot revision=1`。
5. 前端把消息状态显示为“可核验草稿 · 模型精修中”。

草稿只能使用 AnswerSpec 已绑定的事实；不得把 trace、raw warning、路径或内部引用编号
直接放进用户正文。

### 2. GLM 流式生成与门禁

`synthesize_existing_answer_spec()` 改用现有 `synthesize_messages_stream()`：

- token/chunk 只进入服务端受控缓冲区；
- 每次收到 chunk 检查取消信号和共享 `ExecutionBudget`；
- 流仍受本轮剩余 synthesis allowance 和 60 秒总截止约束；
- 流式活动不能延长总截止，也不能把后台线程留在终态之后继续写 run；
- 记录 `first_token_ms`、`chunk_count`、`provider`、`model` 和稳定 fallback reason，禁止记录
  prompt、密钥或高熵 token。

完整文本到达后，依次执行：

1. 数据 notice 与目标公司必需 notice 保留；
2. `validate_llm_answer()` 事实边界检查；
3. 公司归属、日期和禁用工程术语检查；
4. `sanitize_conversation_answer()`；
5. 生成 `answer.snapshot revision=2, final=true`。

任一步失败都不得发布模型文本，而是保留草稿并记录可公开的稳定降级原因。

### 3. 最终一致性

- 最终 `answer.md`、Conversation message、`message.complete` 和最高 revision snapshot 内容必须
  一致。
- report 的 `llm.used=true` 只代表通过门禁并实际采用；收到模型 chunk 但最终被拒绝时仍为
  `used=false`。
- `provider_timeout`、`quality_gate_rejected` 等原因保持稳定枚举，不输出上游响应正文。

## 知识库降级链

正式检索顺序：

```text
Hybrid（dense + BM25，可选 rerank）
  -> BM25
  -> 图谱 / evidence_index / DuckDB 等结构化证据
```

规则：

- Hybrid 因 `FlagEmbedding`/dense 依赖缺失、模型加载失败或可识别的 dense 初始化错误而失败
  时，在剩余检索预算允许的情况下重试 `mode=bm25`。
- Hybrid 超时后只有剩余预算达到 BM25 最低门槛才重试，不能突破共享截止。
- BM25 结果仍须通过 chunk/hash/索引 revision/freshness 校验；回退模式不降低证据新鲜度门禁。
- BM25 成功时不再显示“知识库检索不可用”，而显示来源中立的“知识库关键词检索已采用”；
  Inspector 可记录 `requested_mode=hybrid`、`effective_mode=bm25` 和稳定原因
  `dense_dependency_missing`。
- BM25 也失败时才显示知识库不可用，并继续使用图谱、evidence_index 和 DuckDB。
- 不通过 `pip install FlagEmbedding` 解决本轮问题：它会引入大模型下载、启动延迟和运行环境
  维护成本；自动降级更适合本地产品的可用性目标。

## 前端体验

- `verified_draft` 到达：正文立即出现，状态为“可核验草稿 · 模型精修中”。
- `validated_synthesis` 到达：原地替换草稿，状态为“自然语言精修完成”。替换按段落做短
  过渡，不伪装成模型实时 token。
- GLM 超时或被门禁拒绝：保留草稿，状态为“已保留可核验版本”；运行详情显示来源中立的
  降级原因。
- 页面刷新或 SSE 重连：按最高 revision 恢复，不重复追加旧 delta。
- Inspector 继续展示检索、模型和降级 telemetry，但正文不出现 raw provider 错误、内部路径
  或工程字段。

## 错误与安全边界

- 未形成 AnswerSpec 时不发送空草稿，继续显示阶段进度并走现有保守回退。
- 模型流中断、取消、超时或返回空内容：终止模型采用，草稿成为最终答案。
- 客户端断开不改变 run 事实；服务端继续在硬截止内完成或降级，重连靠事件重放恢复。
- 旧 revision 不能覆盖新 revision；同 revision 重放必须幂等。
- 任何模型 chunk 都不得进入日志、trace 或持久文件，只有通过门禁的最终 synthesis 可持久化。
- 密钥仍只从 Keychain/secret manager 注入，不进入响应、前端环境或 artifact。

## 测试与验收

### 后端

- AnswerSpec 完成后、模型结束前发送 `verified_draft revision=1`。
- 模型流式成功且门禁通过，发送 `validated_synthesis revision=2`，最终 artifact 一致。
- 模型产生多个 chunk 后超时，任何未验证 chunk 都不出现在客户端或 artifact，草稿成为终态。
- 模型返回越界公司、数字、工程术语或漏掉必需 notice 时被拒绝，草稿保留。
- 取消和硬截止后后台模型不得继续写事件。
- Hybrid 缺 `FlagEmbedding` 自动回退 BM25；BM25 结果仍执行 freshness 校验。
- Hybrid 与 BM25 都失败时结构化证据路径仍完成。

### 前端

- snapshot 按 revision 覆盖，不追加重复。
- SSE 重放同一 snapshot 不重复正文；旧 revision 被忽略。
- 草稿、精修成功和精修失败三种状态文案正确。
- 最终重新拉取 run bundle 后与 snapshot 内容一致。
- 旧 `text.delta` 事件仍兼容。

### 真实 UI 验收

在隔离 8795、canonical DuckDB 和内置 GLM 上至少验证一条个股问题：

- 研究期间先出现可核验草稿；
- GLM 成功时替换成精修版，超时时保留草稿；
- 知识库 dense 依赖缺失时自动使用 BM25，而不是直接宣告知识库不可用；
- run/report 完成，DuckDB cutoff 与 readiness 一致或更新；
- 无密钥、内部路径、raw provider 错误或越界公司事实泄露；
- 保存关键阶段截图与 smoke JSON 到 `/tmp`，不提交仓库。

## 发布边界

所有修改继续位于 `fix/workbench-query-retrieval-latency` 隔离分支。完成自动测试和真实 UI
验收后只报告结果；合并 `main`、推送或切换 canonical 8792 必须等待用户明确确认。
