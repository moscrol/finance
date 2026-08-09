# 设计：Episode 渐进式组装接缝测试

日期：2026-08-09  
状态：已确认，待实施  
基线：`main@4a65b28a`  
实施分支：`test/episode-seam-ladder`

---

## 0. 一句话

固定连续 Episode 的执行底座，把市场研究能力按阶梯逐组接入；每一阶都以同一问题、同一任务契约、同一预算和同一证据边界运行，定位"从哪一组组件开始，真实 Episode 无法再产出可交付回答"。

这不是 28 题产品验收台，不是裸模型/Workbench/Episode 的质量 A/B，也不是 `layer_audit.py` 所说的目录依赖接缝。它是一个面向运行时组合的**渐进式组装实验**：一次只新增一组能力，观察完成协议化 Episode 所需的链路是否仍闭合。

---

## 1. 第一性原理与目标函数

用户看到的是一个答案；运行时要完成的是一条有约束的链：

```text
问题
  -> 任务理解与路由
  -> TaskFrame / TurnControlResult
  -> ResearchRunContext / contract
  -> 受授权的工具 registry
  -> model tool loop
  -> evidence binding
  -> structural verifier
  -> semantic verifier
  -> public answer
```

其中任一处可单独正确，但组合时仍可能断裂。例如：工具在 registry 内定义但没被 contract 授权、模型 schema 中看见了未开放工具、证据被取到却无法绑定到 required output，或者 verifier 在新工具进入后拒绝结果。完整端到端测试只告诉我们"最终失败了"；单元测试又容易把各层都替身化，遗漏真实装配错误。

本实验的目标函数不是答案优劣，而是每一阶是否满足以下**交付闭环**：

1. 该阶只暴露已声明、已授权的能力；
2. Continuous Episode 实际执行 model/tool loop，而非直接伪造 `AgentOutcome`；
3. 回答非空，且有来自已执行工具的 evidence hash；
4. required outputs 经结构验证完成，语义验证为 passed 或 repaired；
5. 失败时能区分 provider/预算、工具/数据、contract/verifier、runner 自身四类，而不是把所有红灯归因于刚加入的组件。

这是一种可迁移的实验设计：在 RAG 或多工具 Agent 中，新增 retriever、reranker、数据源、guardrail 时，也应保持输入、预算、权限和验收不变，只改变被实验的能力面。

---

## 2. 现有事实与不变约束

### 2.1 已有生产组装路径

生产路径已存在，不能另造第二套 Episode：

```text
TurnControlCore
  -> ContinuousTurnAdapter
     -> build_episode_context
     -> build_episode_registry
     -> GLMAgentRuntime / ContinuousAgentEpisode
     -> verify_episode_outcome
     -> SemanticEpisodeVerifier
     -> ContinuousTurnResult
```

`ContinuousTurnAdapter` 的 `context_factory`、`registry_factory`、runtime、structural verifier 与 semantic verifier 都是注入点。阶梯 runner 必须复用这些边界和 `build_episode_registry()` 的真实工具构造，再以 capability 白名单收窄它，不能复制工具表或重写各 tool runner。

### 2.2 名称去歧义

`continuous_glm` 是历史 runtime backend 名；`GLMModelClient` 已是 provider-neutral adapter。它不能证明本轮实际模型为 GLM。

本机当前生产链的实测口径是单一 OpenAI-compatible relay：provider `openai`、model `gpt-5.6-terra`、base URL `https://x.ailzd.com/v1`。因此：

- 离线阶梯使用 scripted model，不把任何 provider 可用性混入回归结论；
- live 烟雾固定当前生产 relay，产物必须记录 resolved provider、model、revision 与数据日期；
- live 结果表述为"当前生产 relay 下的 smoke"，不得表述为"GLM 验证"。

### 2.3 数据与外部副作用

主库的 `fact_market_daily`、`fact_sector_daily`、`fact_stock_daily` 当前最大 trade date 均为 `2026-08-07`。首版 live questions 必须以 `as_of=2026-08-07` 固定时间坐标，不能复用 `runtime_backend_cases.json` 中 `2026-07-24` 的"当前"题。

工具保持现有 read-only 约束；不新接会写 DuckDB、飞书或外网写入的 skill。live runner 只读本地数据和既有只读检索能力。

### 2.4 既有评测不可被替代

- `intelligence/eval/cases/acceptance_cases.json` 的 28 题与 `/api` Conversation 路径仍是产品验收的唯一口径；本实验不修改题库、gate 或 receipt schema。
- `scripts/run_agent_episode_ab.py` 的 bare/current/episode 三臂仍用于能力比较；本实验不向它塞 capability stage，避免把质量比较和组装定位混在同一 artifact。
- `intelligence/tests/fixtures/runtime_backend_cases.json` 的 9 题仍用于 backend benchmark；本实验新建小题集，不改变其历史锚定条件。
- `check_satisfiability` 维持 `enforced=False`。阶梯 runner 可以记录它的三态观测，但不得据此跳过或拒绝某阶执行。

---

## 3. 方案比较与选择

### 3.1 方案 A：独立单臂 ladder runner（选定）

新建专用 runner，只运行 episode 这一臂，支持 S0-S3 的单阶或全阶执行。它复用 production composition root、现有 episode result 字段与原子 JSON 写入方式，额外写入阶段和 provenance。

优点：实验变量单一，结果回答的是"哪一级新增能力导致装配失败"；不会污染 A/B 或产品验收语义。

### 3.2 方案 B：给 `run_agent_episode_ab.py` 添加 `--capability-stage`

优点：少一个 CLI 文件。

拒绝原因：同一 artifact 同时有 bare/current/episode arms 和 S0-S3 stages，读数很容易被误读为质量回归或能力单调性结论；它们的目标函数不同。

### 3.3 方案 C：只写 pytest 参数化测试

优点：实现最小，CI 稳定。

拒绝原因：只覆盖 scripted model 和固定工具，无法保留当前生产 relay 的真实 smoke receipt；单独采用会退化为替身层测试，不能证明当前组合入口可用。

---

## 4. 阶梯设计

### 4.1 固定变量

同一个 case 在其可运行的所有 stage 固定：

- 原始问题和 conversation context；
- 生产 `TurnControlCore` 解析出的 source `TaskFrame` / task frame hash；
- source `TurnControlResult` 的路由和研究/澄清决定；
- `as_of=2026-08-07`、tier、timeout、deadline 与 synthesis reserve；
- production `build_episode_context()`、`build_episode_registry()`、structural verifier；
- 工具定义的参数 schema、evidence binding 与 future-of-cutoff 过滤规则。

被改变的唯一业务变量是向 episode 暴露的 capability 集合。每一个 stage 从 source control 的 capability 交集派生自己的 `allowed_capabilities`，并从完整 registry 过滤 spec；只过滤 tool schema 而不收窄 stage contract 会制造不真实的越权路径。`tool_schema_names` 是工具名，`enabled_capabilities` 是能力名，二者不得直接比较；所有 schema/执行事件必须经该 stage registry 的 `ToolSpec.name -> ToolSpec.capability` 映射后，再验证 capability 属于 enabled 集合。

offline 为了零网络和可复现，语义 verifier 是只在 structural output 已完成时返回 passed 的确定性 test double；它证明 `ContinuousTurnAdapter` 的 semantic seam 被正确调用，不宣称验证了生产 LLM judge。live smoke 使用生产 `SemanticEpisodeVerifier`，才验证真实语义裁判。

### 4.2 Stage 表

| stage | 新开放 capability | 运行方式 | 本阶段证明 |
|---|---|---|---|
| S0 `planning` | 无 | 不构造 runtime，不调模型、不调工具 | 路由、TaskFrame、contract、阶梯 allowlist 与预检观测都可冻结；它不是回答成功 |
| S1 `market-data` | `market_data` | offline + live | 模型只能看见并调用结构化行情；返回 evidence 后能完成 `direct_assessment` / 市场事实相关绑定 |
| S2 `mainline-context` | S1 + `mainline_context` | offline | 市场主线内容模块加入后，schema、授权、tool loop、binding 和 verifier 仍闭合 |
| S3 `causal-evidence` | S2 + `news_search` + `evidence_search` | offline + live | 周度原因、反证与证据检索加入后，可到达 public answer；真实数据空结果是合法业务状态，接口断裂不是 |

`news_search` 和 `evidence_search` 在首版作为同一因果证据组开放，而不是分成两阶：本题面要验证的是"因果归因 + 反证"这一产品能力闭环，拆开会产生一个没有实际 contract 价值的中间面。后续若需要定位该组内部问题，再以新 stage 在这两者之间细分。

S1/S2/S3 不是"越多能力答案必须越好"的质量单调性承诺。它们的硬约束是：阶段不能暴露未开放工具、不能绕过 verifier、不能因为新 capability 使固定控制链路异常。答案质量由现有 A/B 与 28 题验收另行判断。

---

## 5. 题集与执行模式

### 5.1 新的小型 fixture

新增 3 题市场题 fixture，锚定 `2026-08-07`：

1. 市场状态："以 2026-08-07 收盘为准，A 股整体市场处于什么状态？"，expected stage floor 为 S1，覆盖 `market_data`；
2. 当前市场主线：expected stage floor 为 S2，覆盖 `market_data` 与 `mainline_context`；
3. 本周行情下跌的主要原因：expected stage floor 为 S3，覆盖市场数据、新闻/证据检索、counterpoint 与因果输出。

fixture 除 question、id、as_of、tier、timeout、conversation context 外，还显式给出每题的 expected stage floor。runner 只在 `stage_id >= expected_stage_floor` 时执行该 case；进入更高 stage 后会重跑已到达的 case，检验新增能力没有切断已有闭环。该字段只是执行矩阵约束，不取代生产 route/contract 对 required outputs 的唯一事实源。

### 5.2 Offline ladder：CI 回归门

offline runner 使用 scripted `AgentModelClient`，但它必须真的驱动：

```text
GLMAgentRuntime -> ContinuousAgentEpisode -> tool definitions
  -> scripted tool call -> 真实 registry.execute -> fixed evidence
  -> FINAL_JSON -> structural verifier -> passing semantic verifier
```

禁止让测试直接返回预造 `AgentOutcome`、替换 `registry.execute`，或使用 deterministic fast path；这样才覆盖授权、schema、arguments、tool batch、evidence hash 和 binding 的真实接缝。外部数据源以本地固定工具 runner 或封闭 fixture policy 固定，保证 CI 无网络、无真实模型调用、无时间漂移。

每一个 S1-S3 stage 只执行 expected stage floor 不高于该 stage 的 cases；S0 仅产生 planning result。CI 通过条件：所有应运行的 stage/case 都有期望的 artifact shape；S1-S3 完成结构闭环且 offline semantic seam 返回 passed；tool schemas 和执行事件映射后的 capability 不含未授权项；不产生未分类异常。

### 5.3 Live smoke：本机 opt-in 证据

live runner 仅跑 S1 市场状态题与 S3 周度原因题、各一遍，并固定生产 relay 的已解析 provider/model。它不能作为 CI 或 merge gate，因为 relay P95 约 50 秒、完整 episode 需要多次模型调用，provider 延迟和预算耗尽均属于外部变量。

live 写到 Git 之外：

```text
/Users/a77/.finance-runtime/seam-ladder/<UTC timestamp>-<revision>.json
```

它在运行前检查：runtime readiness、固定 data date 不早于 fixture as_of、continuous mode 为 `on`、当前 revision。任何 preflight 失败都写一个可读 receipt 并以非零退出，不应伪造 stage 结果。

---

## 6. Artifact 与判定

### 6.1 顶层形状

新 artifact 不复用 A/B 的 arm schema，但复用 episode payload 的字段与命名。它至少包含：

```json
{
  "schema_version": 1,
  "artifact_kind": "episode_seam_ladder",
  "mode": "offline|live",
  "source_revision": "<sha or sha-dirty>",
  "generated_at": "<UTC ISO-8601>",
  "fixture": {"path": "...", "sha256": "...", "as_of": "2026-08-07"},
  "runtime": {
    "backend": "continuous_glm",
    "continuous_mode": "on",
    "provider": "openai",
    "model": "gpt-5.6-terra"
  },
  "stages": []
}
```

offline runtime provenance 标记为 scripted，不可填写生产 provider/model。live `provider` 与 `model` 必须从本次 resolved chain 或 runtime health 的单一事实源读取，禁止复述环境变量或 backend 名来猜。

### 6.2 每个 stage/case 的最小证据

每条 result 记录：

- `stage_id`、`enabled_capabilities`、`tool_schema_names`、`task_frame_hash`；
- `execution_kind`、`status`、`answer`、`latency`；
- `evidence_hashes`、`llm_calls`、`tool_calls`、`provider_attempts`、`duplicate_queries`；
- `structural_status`、`semantic_status`、`missing_outputs`、`satisfiability_precheck`；
- `failure_class`、`failure_detail`，成功时均为空。

判定不能只看 HTTP 200、`ready=true`、`provider_attempts>0` 或答案非空。S1-S3 的离线交付通过须同时满足：

```text
execution_kind == continuous_episode
answer.strip() is non-empty
structural_status == completed
semantic_status in {passed, repaired}
evidence_hashes is non-empty
tool_calls > 0
all tool_schema_names and executed tool names map through this stage registry to a capability inside enabled_capabilities
failure_class is empty
```

live 采用同一交付判据，但可另记 `business_incomplete`：例如工具真实返回空证据、日期新鲜度闸门拒绝旧数据、verifier 给出正常的部分完成。它不是 runner 崩溃，不能被归为 stage 装配失败。

### 6.3 失败分类

runner 以稳定 reason code 分类，保留截断的原始 detail 用于排查：

| failure_class | 含义 | 归因纪律 |
|---|---|---|
| `preflight` | readiness、mode、revision 或 data-date 前提不成立 | 不启动 episode；不是 stage 失败 |
| `provider_or_budget` | provider 无法调用、超时、模型 deadline 耗尽 | live 环境噪声；不归因新增能力 |
| `tool_or_data` | 工具 runner、数据源、freshness 或证据检索本身失败/为空 | 记录 capability 与 trace，再判断业务空结果或真实依赖问题 |
| `contract_or_verifier` | 未授权工具、invalid arguments、binding/required output/semantic gate 失败 | 本实验最需要定位的接缝类别 |
| `runner` | artifact、fixture、编排代码的意外异常 | harness 自身缺陷，优先修 harness |
| `business_incomplete` | 运行完整但真实证据不足，诚实 partial/degraded | 正常业务结果，不能算装配通过，也不能冒充技术故障 |

---

## 7. 测试与验收

### 7.1 单元/组件回归

新增专用 test module，至少覆盖：

1. S0 不构造 runtime、模型或工具，并冻结同一 TaskFrame/contract；
2. 每个 S1-S3 从 production registry 得到的 schema 只含该阶 capability；
3. context 的 allowed capabilities 与 schema 白名单一致；
4. scripted model 请求未开放工具时得到 `contract_or_verifier`，不会静默执行；
5. 每个应运行的 S1-S3 stage/case 都实际产生 tool request/result、evidence hash、binding 和 completed structural status；offline 同时断言确定性 semantic seam 为 passed，live 同时断言生产 semantic verifier 为 passed 或 repaired；
6. scripted provider exception、工具异常、binding 缺失分别映射到规定 failure class；
7. live mode 未显式 opt-in 或 preflight 不满足时绝不触网；
8. artifact 写入原子、包含 fixture hash/revision/stage provenance，且 live target 位于 Git 外。

### 7.2 人工 live 检查

在数据日期为 2026-08-07 的本机运行 S1/S3 后，人工查看 receipt：

1. provider/model 与当时 health 的实际 resolved 值一致；
2. S1 schema 不出现 `mainline_context`、`news_search` 或 `evidence_search`；
3. S3 的 tool calls 和 evidence hashes 确有已开放能力；
4. `satisfiability_precheck.enforced` 仍为 false；
5. 若失败，先读 `failure_class` 与 provider/tool trace，再决定是否重试或修组件；不以单次 relay timeout 宣称回归。

### 7.3 不在范围

- 不改生产路由、contract 定义、工具实现或 `produces` 声明；
- 不把 `suspicious` 预检升级成拦截门；
- 不修改 28 题题库、产品 acceptance board 或 reference snapshots；
- 不主张 S1-S3 答案质量单调提升；
- 不接外部可写 skill、DuckDB 写入或飞书写入；
- 不在本阶段恢复或重跑历史 artifact。

---

## 8. 风险与后续扩展

最主要风险是把模型/relay 的高方差误判为组件回归。离线与 live 分轨、固定 as_of、artifact provenance 和失败分类共同控制这个风险。

首版稳定后，只有在某个 stage 的离线或多次 live receipt 持续指向同一能力组时，才将该组继续拆细，例如把 `news_search` 与 `evidence_search` 从 S3 分开，或新增 `finance_query`/`kb_search` 的个股研究阶梯。扩展前须新增相应题面与 contract evidence，而不是因为工具清单里存在就逐个打开。
