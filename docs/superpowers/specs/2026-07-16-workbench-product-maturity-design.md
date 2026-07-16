# Workbench Product Maturity Design

- 日期：2026-07-16
- 状态：待用户书面复核
- 基线：`main@07edd75`（PR #235 → #238 → #240 → #243）
- 产品目标：把本地 Workbench 建成架构清晰、路由正确、证据可信、响应可控、可持续学习的成熟金融研究 Agent

## 1. 问题定义

当前 Workbench 已具备 Conversation、Turn Controller、Owner DAG、
`EvidenceAtom → StructuredClaim → AnswerSpec → Presenter`、统一 deadline、
Skill Registry 和流式 UI。它已经形成正确主干，但还没有通过产品成熟门：

1. 自然问法仍可能逃离专项 owner，例如“中际旭创怎么看”“这个逻辑呢”。
2. stage 对外超时后，线程内任务仍继续运行，超时不是资源终止边界。
3. BGE-m3 仍由查询子进程冷加载，首查慢且重复消耗内存。
4. AkShare 降级快照可以 `quality=partial`、`freshness=fresh`，同时通过
   snapshot contract 与 readiness，数据存在被误当成数据可用。
5. followup 按钮只有一个 `question` 字段，展示文案和实际 prompt 耦合。
6. verdict、批注和错因已有原始台账，但尚未形成“候选 → 人审 → 生效 →
   可回滚”的学习闭环。

“成熟”不能由测试数量或 CI 全绿定义，而要由真实问题路由、证据边界、
延迟、失败语义、用户可读性和连续自用共同证明。

## 2. 范围与拆分

这是一个持续产品化目标，拆成五个边界清晰、可独立验收的子项目：

1. **Routing Maturity**：正确理解主体、题型、指代、任务切换和关系问题。
2. **Retrieval Runtime Maturity**：真正可终止的 deadline 和常驻 Hybrid RAG worker。
3. **Data Readiness Maturity**：快照生产、质量等级、交易日与 readiness 同口径。
4. **Conversation and Learning Maturity**：followup 契约、胜率面板、错因与批注回流。
5. **Product Acceptance**：canonical 部署、黄金题回放、10 个交易日 Self-use Gate。

每个子项目使用独立 implementation plan 和独立 commit/PR。依赖顺序是
1 → 2 → 3 → 4 → 5；D6/D8 特征库生成管线保持独立立项，不进入本设计。

## 3. 技术方案比较

### 方案 A：继续增加正则和超时阈值

优点是改动小、上线快。缺点是语义规则散落在 Controller、Contract、Router、
Orchestrator，容易出现同一句在不同层判断不同；提高超时也不能终止已开始的线程，
只会延后降级。该方案只适合作为紧急补丁，不作为成熟架构。

### 方案 B：全部交给 LLM 路由与 Agent 自由调用工具

优点是覆盖自然语言长尾。缺点是路由不可复现、成本和延迟上升，且 LLM 可能创造
不存在的主体、Skill 或事实路径。金融场景不能让概率模型成为唯一控制面。

### 方案 C：分层确定性控制面 + 结构化 LLM 长尾 + 证据门禁（采用）

1. 确定性层完成代码、已知实体、题材 alias、追问指代和显式任务词识别。
2. 只有 `unknown` 或低置信度输入进入结构化 LLM 分类；输出受枚举 Schema 和
   Registry allowlist 约束。
3. Controller 是唯一 owner 决策者；Router 只能补 tool，不得替换 owner。
4. Retrieval worker 只返回 typed evidence，不决定结论。
5. 所有事实仍经 `EvidenceAtom → AnswerSpec → Presenter` 输出。

它比方案 A 更稳定，比方案 B 更可审计。代价是需要维护实体快照、协议和业务评测集。

## 4. 目标架构

```text
React Workbench
  -> Conversation API
  -> Turn Controller
       -> Deterministic Query Resolver
            code / company lexicon / theme aliases
            reference phrase / ellipsis / explicit switch
       -> Structured LLM Classifier (only low confidence)
       -> persisted TurnIntent + ResearchPlan
  -> Owner Executor
       -> killable stage boundary
       -> shared turn cache + absolute deadline
       -> local Hybrid RAG worker client
  -> Evidence Registry
       -> EvidenceAtom / StructuredClaim / AnswerSpec quality gates
  -> Presenter
       -> mature narrative + concise followups
  -> ConversationStore / RunStore / Review Candidate Store
```

核心职责：

- `query_resolution`：只回答“用户在问谁、问什么、是否承接上一轮”。
- `turn_controller`：只决定 lane、owner、capability 和是否需要澄清。
- `owner executor`：按 deadline 执行检索阶段并产出 typed partial artifact。
- `rag worker client`：负责通信、健康检查、超时和降级，不理解金融结论。
- `snapshot readiness`：只回答数据能否用于正式研究，不负责生成答案。
- `presenter`：只渲染经过门禁的 claim，不暴露内部 stage/表名/错误代码。
- `review candidate store`：只保存候选经验；未审批内容不得进入 prompt。

## 5. Routing Maturity

### 5.1 单一 Query Resolver

把当前散落的 follow-up pattern 收口到一个无副作用的 resolver，输出：

```text
subject
subject_kind
question_type
reference_kind
context_dependency
explicit_switch
confidence
matched_by
```

解析顺序：

1. 股票代码精确匹配。
2. 公司实体最长匹配，复用 `entity_exposures` 生成的轻量 lexicon。
3. 题材 alias 精确/规范化匹配。
4. 指代短语和省略句：这个逻辑、这个方向、这条链、边际变化、它、该公司等。
5. 显式任务切换：改看、换成、比较、分析财报、公告影响等。
6. 低置信度时调用结构化 LLM classifier。
7. 仍低置信时澄清，不静默落入 general answer。

实体 lexicon 在进程启动时加载为内存快照，使用来源文件的 size/mtime/hash 作为
fingerprint；来源变化后原子刷新。每次请求不得直接解析大型 relation JSON。

### 5.2 关系问题

“谁是谁上游、A 与 B 什么关系、哪些公司暴露在某环节”标记为 `relation` operator，
主路径查询 graph / `entity_exposures` / `concept_graph`。Wiki RAG 只补原文和解释；
图上没有边时输出“关系未被当前证据确认”，不得用两段语义相似内容拼关系。

### 5.3 路由验收题

至少覆盖：

- `中际旭创怎么看` → company / stock-deep-dive
- `光模块怎么看` → theme / theme-research
- `这个逻辑呢` → 继承上一轮 subject、owner、evidence set
- `这个方向怎么看` → 继承
- `这条链有哪些公司` → 继承并增加 relation/company_mapping operator
- `边际变化呢` → 继承并增加 market-change operator
- `改看贵州茅台估值` → 显式切换主体，`valuation_estimate` 由
  `stock-deep-dive` owner 承接
- `液冷和 PCB 谁在上游` → relation 主路径
- 无上下文的 `这个方向呢` → clarify，不编造主体

## 6. Retrieval Runtime Maturity

### 6.1 真正可终止的 stage

线程 `future.cancel()` 不作为终止机制。昂贵的 RAG、外部 HTTP、模块和 provider 调用
必须满足至少一种边界：

- 子进程可在 deadline 时 `terminate`，宽限期后 `kill`；或
- 常驻 worker 支持请求级 deadline/cancel token，并在模型推理边界停止；或
- HTTP client 使用连接/读取 timeout 且不在超时后后台重试。

每个 stage 记录 `queued_ms / execution_ms / cancel_requested / cancel_effective /
background_work_detected`。对外返回 timeout 后，测试必须证明工作不再继续修改事件、
缓存或 artifact。

### 6.2 常驻 BGE-m3 worker

采用知识库专用 venv 内的本地单实例 worker：

- 启动时加载 BM25、dense index、BGE-m3 和可选 reranker。
- 通过 Unix Socket 或仅监听 `127.0.0.1` 的 HTTP 接口提供查询。
- 请求包含 query、mode、k、filters、index fingerprint、deadline 和 request ID。
- 响应保留当前 `rag_index.py query --json` 的 hit 契约和 freshness 字段。
- 有 bounded queue、健康检查、模型/index 版本、加载次数和 p50/p95 telemetry。
- worker 不可用时回退 BM25/CLI；不得静默改变检索模式。

不把 BGE 直接 import 进 Workbench API 进程：两套 venv 的依赖边界清晰，模型崩溃
不会带走 Conversation API。CLI 子进程继续作为兼容降级，但不再承担默认热路径。

### 6.3 性能门

在 canonical 机器以冷启动和热启动分别验证：

- 同一 worker 生命周期内模型加载次数为 1。
- warm Hybrid RAG p95 由实测基线确定，目标先设为 ≤5 秒。
- 普通研究题 15 秒内出现 verified draft 或明确阶段进度。
- 60 秒内完成或返回可读 typed partial answer。
- 超时后 5 秒内 active/background work 归零。

## 7. Data Readiness Maturity

### 7.1 生产者与消费者分离

AkShare 使用独立 data-source venv 和 LaunchAgent，负责生成 canonical snapshot；
Workbench 只消费 snapshot。不要把 AkShare 装入 Workbench API venv，避免第三方
数据源升级、代理或导入失败影响聊天服务。

### 7.2 质量状态机

快照质量使用：

```text
complete  = 全市场 spot + 必需涨跌停/主题字段可用
partial   = 只有局部池或部分字段
stale     = source_data_date 不是目标交易日
failed    = 无可用正式数据
```

`freshness` 与 `quality` 正交：`fresh + partial` 只能用于局部提示，不能满足正式
market readiness。Snapshot contract 必须校验质量、源日期、交易日和必需字段非空。

### 7.3 覆盖规则

- 新快照不得以较低质量覆盖同日或更新日期的高质量快照。
- AkShare 是 fallback，不得覆盖 canonical daily-full/DuckDB 生成的 complete snapshot。
- 代理失败先记录实际 provider 错误，再按显式 provider chain 降级。
- 定时任务只在 A 股交易日收盘后运行，交易日来自 canonical DuckDB calendar。
- readiness 返回 `ready / degraded / not_ready`，并给出 machine-readable reason。

CLI 统一支持 `python -m scripts.sync_akshare_market_snapshot`；直接脚本入口要么正式支持，
要么从 runbook 删除，不能存在文档可见但不可执行的入口。

## 8. Conversation and Learning Maturity

### 8.1 Followup v2

新契约：

```json
{
  "label": "核对真实订单",
  "full_prompt": "请继续核对英维克液冷业务的真实订单证据，并按公告、互动易和研报分层。",
  "type": "evidence",
  "source": "gap:claim-id"
}
```

- `label` 不超过 20 个中文字符，用于按钮。
- `full_prompt` 使用用户口吻，点击后作为真实下一轮 query。
- 后端一版兼容旧 `question`，读取时转换，写入只产 v2。
- followup 必须继承 subject/owner/evidence/stage artifact，不得重置为 general answer。

### 8.2 胜率统计

只聚合已完成 verdict/recheck 的裁决样本。少于 25 个有效样本时展示“样本积累中”，
不输出稳定胜率结论；达到阈值后按 question type、time window、source 分桶，显示样本数、
命中率和 Wilson 置信区间。面板是评估工具，不直接调整答案权重。

### 8.3 错因与批注回流

未命中 verdict 或 §8 批注生成 versioned candidate：

```text
candidate_id
source_run / source_verdict / source_annotation
error_taxonomy
proposed_principle
proposed_prompt_rule
evidence
status: pending | approved | rejected | retired
reviewed_by / reviewed_at
```

只有 `approved` candidate 进入 lessons/prompt rule；每条规则带版本和来源，可单独 retired。
自动反思不得直接写正式 prompt，避免一次误判形成自我强化污染。

## 9. 输出成熟度

成熟回答不等于固定长模板。Presenter 根据题型选择段型，但必须保持：

1. 开头直接回答用户真正的问题。
2. 区分事实、推断、市场信号和个人/KOL 观点。
3. 给最强证据及来源，不把记忆当当前事实。
4. 给反证、条件边界和下一验证窗口。
5. 缺数据时说清“缺什么、仍能判断什么、不能判断什么”。
6. 主正文不出现 stage ID、内部表名、EvidenceAtom ID、provider 错误堆栈。
7. 简单问题短答，深挖问题才展开；followup 负责继续深入。

输出评测同时包含确定性 gate 和用户可读性评分。LLM-as-judge 只辅助评价叙事质量，
不能覆盖引用、数值和 evidence tier 的程序化失败。

## 10. 测试与验收

### 10.1 四层证据

1. **单元测试**：resolver、contract、quality state、candidate approval。
2. **集成测试**：Controller → Router → Owner → AnswerSpec → Presenter；worker 协议。
3. **故障注入**：RAG 超时、worker 崩溃、proxy error、partial/stale snapshot、LLM malformed。
4. **真实回放**：canonical 数据和 provider 的黄金题、连续追问、并发与取消。

### 10.2 成熟度矩阵

| 维度 | 完成证据 |
|---|---|
| 架构 | owner 唯一、边界文档与协议测试一致，无平行旧路径偷偷接管答案 |
| 路由 | 黄金题逐条记录 expected/actual subject、owner、operators，正式集 100% 通过 |
| 证据 | factual claim 均绑定有效 atom/source；弱证据不晋升 CORE/确定性结论 |
| 延迟 | cold/warm p50/p95、首次可读输出、总时长、取消收敛均有实测报告 |
| 数据 | complete/partial/stale/failed 故障注入与 readiness 结果一致 |
| 对话 | 三轮追问保留主体、owner、证据集合；显式切换不错误继承 |
| 输出 | 黄金题无人类不可读内部术语，短答/深挖长度符合题型 |
| 学习 | pending 不进 prompt；approved 可生效、可追踪、可 retired |
| 运行 | canonical commit = 已验收 main；只保留一个长期 8792 服务 |

### 10.3 Self-use Gate

代码与回放门通过后，才启动连续 10 个真实 A 股交易日自用。每天至少覆盖市场、题材、
个股、消息/公告、财报/估值中的三类，并记录路由、延迟、证据、输出评分和人工 verdict。
任何 P0 正确性回归会暂停计时，修复并重放通过后再恢复。

## 11. 实施顺序与交付物

### Phase A：P0 Routing

- 单一 resolver、实体/题材 lexicon、追问省略句、relation operator、黄金路由集。
- 交付：独立 PR、路由矩阵、真实 Conversation 三轮回放。

### Phase B：P0.5 Runtime and Readiness

- 可终止执行边界、取消 telemetry、snapshot quality contract/readiness。
- 交付：故障注入报告，证明 timeout 后没有后台工作；partial 不再误报 ready。

### Phase C：P1 Retrieval and Data Producer

- 常驻 BGE-m3 worker、客户端、CLI fallback；AkShare 独立 venv/LaunchAgent/provider chain。
- 交付：冷/热性能报告、模型加载次数、交易日快照运行记录。

### Phase D：P1/P2 Conversation and Learning

- Followup v2、胜率面板、错因/批注 candidate 审批与回滚。
- 交付：UI/E2E、25 样本门、pending/approved/retired 流程测试。

### Phase E：Canonical Acceptance

- 合并经批准的 PR，按 runbook 原子切换 `/Users/a77/finance-workspace-runtime`，
  重启 8792，完成黄金题与 10 交易日 Self-use Gate。
- 交付：最终 maturity report；所有矩阵项有直接证据后才声明产品成熟。

## 12. 非目标

- 不在本阶段建设公开多租户、计费、外部用户认证或自动交易。
- 不自动把反思、verdict 或用户批注写入正式 prompt。
- 不重写已通过门禁的 `AnswerSpec`/Presenter 主干。
- 不把 D6/D8 特征库生成管线塞进 Workbench 成熟化 PR。
- 不以增加超时阈值、增加 prompt 字数或增加 Skill 数量替代根因修复。
