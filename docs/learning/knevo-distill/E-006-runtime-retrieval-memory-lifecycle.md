# E-006：运行态检索、Fundacore 图谱与记忆生命周期实测

> 日期：2026-08-02
> 目的：用只读实验补齐 Knevo 逆向中尚未验证的三块：`finmemory` 检索排序、`fundacore` 正确查询通路、记忆候选到长期记忆的生命周期。
> 实验会话：Knevo UI 正常 composer 链路；未点击任何“接受 / 拒绝 / 更新 / 删除”。
> 证据等级：页面工具卡和 DOM turn 为 `[实测]`；排序机制的解释为 `[推断]`；涉及后端未公开实现的部分标记 `[待验证]`。

## 1. 执行边界与重要失败

### 1.1 API 直写不是有效实验通路

早期尝试直接调用 `POST /api/turns`，接口返回 200、turn 状态为 `completed`，但会话详情出现：

- 用户消息正文为空；
- 助手返回旧的短期记忆问候；
- 会话列表 `messageCount` 与页面运行态不一致。

这条路径被判定为无效实验，不纳入检索结论。随后改用已登录页面的 textarea、真实 input 事件和发送按钮完成实验。

**[实测] 产品一致性问题：** UI 运行态、持久化 transcript、会话列表缓存可能不同步。验证一次任务是否真正运行，至少要联合检查：

```text
页面 turn DOM
+ 工具卡 / SSE 事件
+ turn status
+ 持久化 transcript
```

不能只依赖 `/api/conversations/{id}`。

### 1.2 只读原则

本轮没有调用或点击：

```text
接受
拒绝
更新
删除
```

没有接受任何 memory recommendation，也没有主动写入用户长期记忆。

## 2. Finmemory 检索矩阵

通过正常 UI composer 提交一个 finmemory-only 问题，要求并行运行 5 个 `finance_memory_query`，每次 `limit=5`：

1. `AI硬件供给侧通胀五段框架`
2. `AI硬件供给弹性涨价扩产`
3. `供应商数量扩产周期认证定价权`
4. `CCL ABF 光模块 HBM 液冷`
5. `2026年7月 AI硬件供给侧`

页面工具卡显示：5 次 `finance_memory_query`，随后还有一次 `finance_memory_stage_extraction`。

### 2.1 结果摘要

| Query 类型 | 结果特征 |
|---|---|
| 精确框架词 | 命中 `fmr-6397bed7`、`fmr-6dde4e37`、`fmr-08e0a9a8` 等核心框架卡 |
| 泛化机制词 | 混入 Lumentum、云涨价、DRAM、台积电涨价、Anthropic 提价等相邻观察/事件 |
| 供应链实体组合词 | 命中五段框架、2026H1 框架谱系、AI 链选股排序等核心卡 |
| 月份/时间词 | 结果偏向 7 月下旬新产生的退潮风控、利润池迁移、AI 变现等邻近判断 |

跨 query 去重统计：

- `fmr-6dde4e37` 出现 4/5 次；
- `fmr-08e0a9a8` 出现 3/5 次；
- `fmr-6397bed7` 出现 2/5 次。

### 2.2 可以确认的行为

**[实测]**：精确主题/实体组合词能稳定召回核心框架；泛化词会扩大召回面并引入相邻材料；时间词会改变结果分布；多 query 之间存在明显重复项。

**[实测]**：`finance_memory_stage_extraction` 是独立的后处理工具，会在记忆查询后做阶段/框架提炼。

**[推断]**：排序至少混合了以下因素：

```text
语义相关性
+ 关键词/实体匹配
+ 时间新鲜度
+ 主题覆盖度或重要性
+ 去重后的跨 query 支持度
```

目前工具卡没有返回分数，因此不能断言具体实现是 BM25（基于词项统计的稀疏检索）、向量检索、混合检索或 rerank（重排序模型）。

### 2.3 对本地 Agent 的直接启示

不要用一次宽 query 代替检索规划。建议保留：

```text
窄 query：实体 + 产品 + 代码
宽 query：上游 + 下游 + 同业 + 宏观
反 query：产能过剩 + 需求不及 + 替代 + 竞争恶化
时间 query：近期变化 / 指定窗口
```

每次检索记录：

```json
{
  "query_id": "q-001",
  "query_text": "...",
  "source": "finmemory",
  "limit": 5,
  "result_ids": ["..."],
  "retrieved_at": "...",
  "cross_query_support": 3,
  "ranking_score": null
}
```

`cross_query_support` 可作为主题稳定性信号，但不能冒充预测胜率。

## 3. Fundacore 正确查询通路

### 3.1 错误通路

用以下方式查询：

```text
finance_memory_query(
  query="生益科技 兴森科技 宏发股份 CCL ABF 光模块",
  sources=["fundacore"],
  limit=10
)
```

结果为：

```text
count: 0
items: []
```

**[实测]**：`fundacore` 不是 `finance_memory_query` 的记忆源。不能把它当成带 `title/content/tags/kind` 的文本记忆库。

### 3.2 正确通路

Knevo 页面建议并实测执行：

```text
finance_entity_resolve
→ finance_graph_context
```

查询实体：生益科技、兴森科技、宏发股份、CCL 覆铜板、ABF 载板。

实体解析结果：

| 提及 | entityId | 规范名/类型 | 置信度 | 动作 |
|---|---|---|---:|---|
| 生益科技 | `fent-fc-0bdb1834de278ff6cf73` | 生益 / company | 0.98 | link |
| ABF 载板 | `fent-fc-fef8460baf55bcd66540` | ABF / product | 0.72 | link |
| 兴森科技 | null | concept | 0.35 | create_candidate |
| 宏发股份 | null | concept | 0.35 | create_candidate |
| CCL 覆铜板 | null | company | 0.35 | create_candidate |

图谱上下文返回：

```text
centerEntityIds: ["fent-fc-15b7f6e42b0762c926fb"]
entities: 1
edges: []
edgeClaims: []
facts: []
evidence: []
gaps: ["no_neighbors", "no_facts"]
```

中心实体是 `CCLA覆铜板资讯`，但没有邻接关系、事实或证据。

### 3.3 结论

**[实测]**：

```text
有实体节点 != 有图谱关系
有图谱关系 != 有可用事实
有实体解析结果 != 查询中心一定使用该 entityId
```

对本次 AI 硬件供给侧主题：

- `fundacore` 有少量实体覆盖；
- 产业链边、事实和证据基本为空；
- 供应商数量、扩产周期、认证壁垒、定价权等方法论主要存在 `finmemory` 文本卡；
- 不能因为图谱返回了实体，就宣称存在上下游、竞对或客户关系。

### 3.4 本地实现建议

图谱结果必须有显式质量门槛：

```text
entity_resolve:
  resolved / candidate / unresolved

graph_context:
  entities
  edges
  facts
  evidence
  gaps
```

当 `edges=[]` 或 `facts=[]` 时，回答必须明确写“图谱未提供关系/事实”，并降级到文本记忆或 provider 核验，不得根据实体名称臆补关系。

## 4. 记忆推荐生命周期

### 4.1 只读状态快照

实验时观察到：

```text
长期 memories: 37 条
pending recommendations: 18 条
pending batches: 7 个
reflect-insights: 0
```

推荐项字段包括：

```text
id
 title
 content
 conversationId
 conversationTitle
 batchId
 createdLabel
 items
```

batch 字段包括：

```text
id
title
content
conversationId
conversationTitle
createdLabel
itemCount
items[]
```

### 4.2 可确认的生命周期

```text
对话
→ 候选提炼
→ batch 聚合
→ 单条 recommendation
→ 用户接受/拒绝
→ 长期 memory
→ 后续检索命中
```

**[实测]**：本轮只读的 finmemory 和 fundacore 实验没有进入长期 `memories`，也没有出现在新的 pending recommendation batch 中。

**[实测]**：普通对话结束后，候选提炼可能异步生成；页面右侧 pending 数量变化不能单独证明已写入长期记忆。

### 4.3 必须区分的指标

```text
hitCount / lastHit
  = 记忆被召回/使用的次数

prediction win rate
  = 判断经过验证后的命中率
```

两者不是同一指标。`hitCount` 不能用于证明某条投资判断有效。

同样：

```text
memory confidence
  = 记忆条目可信程度或系统置信度

calibrated probability
  = 可被历史结果校准的事件概率
```

两者也不能互换。

## 5. 对本地 Agent 的回灌优先级

### P0：建立统一知识卡协议

至少支持：

```text
id
source_plane: graph | shared_memory | user_memory | provider
kind: fact | event | observation | insight | reasoning_pattern | relation
content
tags
entity_refs
confidence
source_evidence
updated_at
status: candidate | accepted | rejected | archived
```

### P0：检索结果必须带 provenance

每个命中保留：

```text
query_id
source_plane
retrieved_at
result_rank
cross_query_support
```

### P1：图谱结果必须带 gaps

没有 edges/facts/evidence 时，结构化返回空数组和 gap 原因，不允许让 LLM自行补全。

### P1：推荐和长期记忆分开存储

推荐状态机建议：

```text
candidate
→ pending_review
→ accepted / rejected
→ active_memory / discarded
```

### P1：预测验证单独建 ledger

不要用 memory 的 `hitCount` 替代预测回检。预测结果应至少记录：

```text
forecast_id
claim
horizon
verification_conditions
outcome: hit | miss | unverifiable
error_class
verified_at
```

### P2：运行态一致性监控

对有 UI/异步任务的 Agent，验收应同时检查：

```text
turn created
user payload persisted
tool events observed
assistant output persisted
conversation index refreshed
```

任一不一致都应标记为 `execution_consistency_warning`，不能只看 HTTP 200。

## 6. 未解决问题

以下仍是 `[待验证]`：

1. `finmemory` 的精确排序公式与权重；
2. `finance_memory_stage_extraction` 是否会改变原始检索排序；
3. recommendation 去重、合并和淘汰规则；
4. 接受/拒绝后长期 memory 的具体写入接口与可逆性；
5. 短期记忆、长期记忆、项目上下文的冲突裁决细节；
6. `fundacore` 覆盖范围是否只是在 AI 硬件主题稀疏，还是整体图谱都较浅；
7. UI 运行态与持久化 transcript 不同步的具体缓存/会话状态根因。

## 7. 结论

Knevo 的可迁移价值不在于复制某个黑盒排序公式，而在于清晰分离四种东西：

```text
文本记忆：承载判断、框架和观察
实体图谱：承载可结构化的世界关系
用户记忆：承载个人判断和交互史
预测台账：承载可验证的判断结果
```

本地 Agent 应优先吸收这种类型纯度和状态机，而不是把所有内容塞进一个向量库或把所有“命中”都当成正确。
