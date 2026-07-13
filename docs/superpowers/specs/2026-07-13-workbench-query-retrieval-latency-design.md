# Workbench 问题理解与检索延迟优化设计

日期：2026-07-13
状态：待用户复核
分支：`fix/workbench-query-retrieval-latency`
基线：`origin/main@bb9754f`

## 1. 背景与已验证问题

PR #216–#221 合并后的真实 UI 验收表明，Workbench 的技能注册、owner 边界、无模型回退和 readiness 契约已有改善，但回答主链仍有两个互相放大的问题：

1. `answer_model._theme_name()` 在未识别到别名或候选题材时，会退回完整问句。通用市场方法论问题因此被伪装成一个题材，后续可能召回无关的 AI 算力或半导体材料。
2. `closed_loop_retrieval` 的 narrow、broad、counter 三个检索口径各最多改写三次。每次 `kb_rag.retrieve()` 都通过子进程调用 `rag_index.py query`，而 Hybrid 模式会重新加载 BGE-m3 向量模型；全空路径最多加载九次。真实 UI 中同一道题耗时约 227 秒。

另一个无技能基础金融问题在约 275 秒后仍未完成，说明超时只存在于局部调用，没有覆盖路由、检索、证据质检和最终生成的整条请求链。

## 2. 目标

本轮同时通过正确性和延迟两道门：

- 通用市场现象不得被完整问句伪装成公司或题材。
- 明确公司、证券代码或题材仍能进入对应专项研究链。
- 单次请求最多初始化一次 BGE-m3；其余扩展查询使用 BM25 或直接停止。
- 从 UI 提交到终态回答的总耗时不超过 60 秒；失败或预算耗尽时也必须产生可读的保守回答。
- 非 fresh 的知识库命中继续严格禁止进入正式证据。
- 检索结果必须通过主题或实体相关性门禁，硬来源身份本身不能替代相关性。
- 个股深挖、连续追问、新对话 owner 清空和无模型无证据回退不回归。

## 3. 非目标

- 本轮不搭建常驻向量数据库或独立 embedding 服务。
- 不修改知识库正文、关系 JSON、向量索引内容或证据分层规则。
- 不扩展题材研究、消息冲击、财报分析的业务覆盖面。
- 不推进 hosted beta，不改变组织密钥、blueprint 或审批状态。
- 不承诺所有深度研究都在 60 秒内获得完整的多轮扩展证据；预算不足时优先保证相关、可解释、可降级。

## 4. 方案选择

### 4.1 未采用：最小补丁

只删除“完整问句作为题材”的兜底，并把九次检索缩成一次。优点是改动少，缺点是问题分类、相关性和端到端预算仍各自为政，换一种通用问法可能复发。

### 4.2 采用：结构化问题信封 + 预算化分层检索

在进入专项 owner 前生成结构化 `QueryEnvelope`，再用共享 `ExecutionBudget` 控制整条链。检索先走关键词 BM25，仅在确有明确研究对象、关键词召回不足且预算允许时补一次 BGE-m3 语义召回。

BM25 是关键词相关性排序，适合公司名、代码和明确题材；向量召回适合别名和语义近义表达。两者分层使用，比每次都跑 Hybrid 更符合“便宜且确定的步骤在前，昂贵且模糊的步骤在后”的检索系统设计原则。

### 4.3 暂缓：常驻向量检索服务

让模型常驻内存可获得更高吞吐，但会引入进程生命周期、健康检查、端口、部署和跨仓库接口。本地单用户阶段先证明查询规划和预算正确，再根据并发与冷启动指标决定是否服务化。

## 5. 核心数据结构

### 5.1 QueryEnvelope

`QueryEnvelope` 是一次请求唯一的问题理解结果，建议包含：

```python
@dataclass(frozen=True)
class QueryEnvelope:
    question_type: str
    subject_kind: Literal["company", "theme", "market_pattern", "unknown"]
    subject: str | None
    decision_goal: str
    timeframe: str | None
    matched_by: Literal["ticker", "entity", "candidate", "alias", "quoted", "generic"]
    confidence: float
```

解析优先级从确定性高到低：

1. 证券代码和已解析实体；
2. 当日候选题材或知识库规范别名；
3. 引号、书名号或明确的“研究 X 题材”句式；
4. 通用市场现象或方法论模式；
5. 无法识别则为 `unknown`。

硬约束：`subject` 无可靠匹配时必须为 `None`，不得退回 `query.strip()`。

示例：

```text
问：如果一个A股题材连续上涨，但板块成交占比开始下降……
question_type = market_methodology
subject_kind = market_pattern
subject = None
decision_goal = 区分健康分歧与行情高潮
```

```text
问：液冷题材连续上涨但成交占比下降，怎么看？
question_type = theme_analysis
subject_kind = theme
subject = 液冷
decision_goal = 判断题材生命周期
```

### 5.2 ExecutionBudget

`ExecutionBudget` 使用单调时钟保存绝对截止时间，并向路由、owner、检索和最终生成传递：

```python
@dataclass(frozen=True)
class ExecutionBudget:
    started_at: float
    deadline_at: float

    def remaining_seconds(self) -> float: ...
    def child_timeout(self, requested: float, reserve: float = 0) -> float: ...
```

所有外部调用的 timeout 必须取“自身上限”和“请求剩余时间减保留时间”的较小值。这是 deadline propagation（截止时间传递）：避免每个子模块各自拥有 90 秒，最终串联成数分钟。

默认总预算为 60 秒，可通过非敏感配置覆盖，测试中使用更小预算验证降级。

## 6. 请求流程

```text
接收问题
  -> 构建 QueryEnvelope
  -> owner 路由
  -> 确定性数据与 BM25 召回
  -> 必要时一次 BGE-m3 语义补召回
  -> 相关性与新鲜度门禁
  -> AnswerSpec / 保守回退
  -> 有预算则模型润色，无预算则确定性渲染
  -> 60 秒内发送 completed 或 degraded 终态
```

### 6.1 路由规则

- 自动或 hybrid 模式下，`subject_kind=market_pattern` 的方法论问题进入 Base Finance，不进入题材 owner。
- 明确公司进入个股深挖；明确题材进入题材研究。
- 用户手动选择专项 skill 时尊重用户选择，但 owner 不得虚构研究对象；没有 subject 时只能输出通用框架或回退。
- 连续追问可以继承当前 owner，但只有先前已确认的 subject 才能继承；新对话继续清空 owner。

### 6.2 检索计划

对明确公司或题材：

1. narrow BM25：公司名、证券代码、规范题材名；
2. broad/counter BM25：从明确 subject 和首轮命中提取扩展词；
3. 如果 BM25 无足够相关命中、索引可用、剩余预算满足语义召回最低门槛，则只执行一次 Hybrid/BGE-m3 查询；
4. 任何一次 `skipped`、索引 stale、不可恢复 error 或 timeout 都触发 fail-fast，不再做同模式改写重试。

对 `market_pattern` 或没有可靠 subject 的问题：

- 跳过题材知识库语义检索；
- 使用当前市场快照、结构化指标和金融方法论生成回答；
- 缺少市场快照时明确披露缺口，不用其他题材材料填空。

检索执行器必须记录 `dense_initializations` 或等价计数，生产契约为单次请求 `<= 1`。

## 7. 证据相关性门禁

当前实现允许“硬来源”在缺乏主题重合时进入 conclusion。新规则把“相关性”和“证据硬度”拆开：

1. 先判断是否与 `QueryEnvelope.subject`、实体代码、规范别名或决策目标的关键术语直接相关；不相关则进入 discarded。
2. 通过相关性后，再用 evidence layer、fact hardness 和 freshness 决定进入 verified fact、clue 或 counter clue。
3. `freshness != fresh` 的命中继续 fail-closed，只保留告警和遥测，不能进入 LLM 证据上下文。
4. counter 查询也必须相关，不能因为包含“风险”二字就接纳其他题材的负面材料。

该顺序对应检索系统中的两阶段门禁：先回答“是不是这件事”，再回答“证据够不够硬”。

## 8. 超时与降级行为

建议的软预算不是各阶段固定配额，而是上限和保留时间：

- 问题理解应为本地确定性逻辑，目标小于 100 毫秒；
- 检索最多使用约 25 秒，并为最终渲染保留时间；
- 模型调用只获得当前剩余预算；
- 到达 deadline 前必须停止新增检索或重试。

终态规则：

- 有正式证据：正常回答并列出来源和缺口；
- 只有结构化市场数据：输出“基于盘面指标”的方法论回答；
- 无模型或模型超时：从 AnswerSpec 确定性渲染，不返回空白；
- 无 fresh 证据：使用保守措辞，明确“未形成可追溯事实”；
- 内部异常：返回 degraded 终态和用户可理解的缺口，不暴露模型下载日志或堆栈。

60 秒 SLA 以“提交请求到收到 completed/degraded 终态”为准，不以某个子进程完成为准。

## 9. UI 可观测性

复用现有流式事件通道，统一阶段名：

1. `understanding`：识别问题与研究对象；
2. `deterministic_recall`：读取盘面、图谱和 BM25；
3. `semantic_recall`：可选的一次语义补召回；
4. `evidence_gate`：相关性、新鲜度和硬度质检；
5. `synthesis`：模型生成或确定性回退。

每阶段至少记录开始时间、结束时间、状态和降级原因。检索遥测增加查询口径、mode、命中数、耗时和语义模型初始化次数。用户界面显示人话阶段，不显示内部命令和 Hugging Face 下载进度。

## 10. 预计代码边界

实施计划阶段再以测试驱动方式确认最终文件，预计涉及：

- 新增或扩展问题理解模块，供 answer orchestrator 与 skill router 共用；
- `answer_model.py`：移除完整问句作为题材的兜底；
- `closed_loop_retrieval.py`：改为预算化、分层和可提前停止的查询计划；
- `kb_rag.py`：接收剩余 timeout 并输出模型调用遥测；
- Workbench owner / conversation orchestrator：传递 envelope 和 deadline；
- 流式事件层：映射五个可观测阶段；
- 对应单元测试、集成测试和真实 UI 回归脚本。

本轮优先在 finance-workspace 内完成，不要求修改 knowledge-base 的 `rag_index.py`。若“一次 Hybrid”冷启动仍无法满足 60 秒，再单独设计 batch CLI 或常驻检索服务，避免在本 PR 引入跨仓库部署耦合。

## 11. 测试策略

### 11.1 问题理解单元测试

- 通用题材生命周期问法得到 `subject=None` 和 `market_pattern`；
- “液冷题材……”得到 `subject=液冷`；
- “英维克/002837……”得到 company；
- 引号中的新题材可以作为显式 subject，但标记较低 confidence；
- 空字符串或无法识别的问题不得成为题材名。

### 11.2 检索单元测试

- 全空路径不再调用九次 Hybrid；
- 单次请求 Hybrid 调用次数不超过一次；
- timeout、error、stale index 会 fail-fast；
- 无关 hard hit 进入 discarded；
- 相关 hard fresh hit 才能进入 conclusion；
- deadline 不足时跳过语义召回并产生明确告警。

### 11.3 Workbench 集成回归

- 个股深挖首轮仍由 stock owner 负责；
- 连续追问继承 owner 和 subject；
- 新对话 owner 清空；
- 自动模式的通用市场现象进入 Base Finance；
- 手动题材 skill 在没有 subject 时不虚构题材；
- 无模型、无 fresh 证据均返回可读的保守答案。

### 11.4 真实 UI 验收

重复原始两道问题，分别记录冷启动和热启动：

1. “如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断它是健康分歧还是行情高潮？请给出直接判断、证据、反证和下一步验证。”
2. “A股里，指数上涨但涨停家数下降、成交额放大，这种背离应该怎么理解？请直接给出判断、最关键的证据、可能的反证和下一步验证，不要写成检查清单。”

通过条件：

- 两题都在 60 秒内收到非空终态；
- 第一题不产生完整问句题材，不注入无关 AI 算力或半导体证据；
- 输出包含直接判断、证据、反证和下一步验证；
- inspector 显示 BGE-m3 初始化次数不超过一次；
- 无证据时保守措辞质检不产生 error，已有 warning 必须有明确原因。

## 12. 发布与回退

- 所有实现留在独立分支，通过单元、集成和真实 UI 验收后再开 PR。
- 不直接修改当前 canonical runtime；PR 未合并前使用干净 worktree 启动临时端口测试。
- 合并和切换 canonical runtime 必须由用户明确确认。
- 若上线后出现回归，可回退到原检索策略配置；严格 freshness 和证据门禁不允许被回退关闭。

## 13. 可复用知识点

- **Query Envelope**：把自然语言先转成稳定的结构化请求，可复用于搜索、客服路由和多 Agent owner 选择。
- **Cost-aware retrieval**：先跑便宜的 BM25，再按需运行向量召回或 rerank，可复用于任何有延迟预算的 RAG。
- **Deadline propagation**：整条请求共享截止时间，可避免微服务或工具链的局部超时相加。
- **Relevance before authority**：来源权威不代表回答当前问题，检索结果必须先过相关性，再判断证据硬度。
