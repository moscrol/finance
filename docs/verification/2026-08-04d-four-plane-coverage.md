# 四平面覆盖诊断（2026-08-04d Batch B）

> **性质**：只读诊断，零生产代码改动。判据来自
> `agent-memory/10_knowledge/finance-agent-knevo-derived-knowledge-runtime-contract.md`
> （下称「运行时契约」）的 §1 四类数据平面与 §9 吸收优先级。
>
> **基线**：`agent-memory/10_knowledge/finance-agent-capability-graph.md`
> （`graph_audit.py` 跑过，30 节点 / 32 路径 / exit 0，无漂移）。
>
> **结论摘要**：工具面**不是**主要瓶颈——provider 平面覆盖充分，`user_memory` 平面
> 存在**一个已确认的结构性缺口**（agent 无法主动检索），`graph` 平面返回结构比契约
> §5 少四个字段。§9 的两条 P0 都只是**部分**落地。详见 §3。

---

## 0. 先修正三个数字

前两版清单的工具数（先 2、后 8）和这轮 MOC 记的「~10」都不准。逐个数下来：

| 来源 | 代码位置 | 工具名 | 个数 |
|---|---|---|---|
| catalog | `research_tool_registry.py` `_DEFAULT_TOOL_METADATA` | `finance_query` `evidence_search` `kb_search` `web_search` `news_search` `graph_lookup` `evidence_lookup` `l3_lookup` `market_data` `financial_data` `mainline_context` | **11** |
| 技能桥 | `agent.py:44` → `skill_tools.run_skill` | `run_skill`（注册表内仅 `serenity-alpha`） | 1 |

**catalog 共 11 项，不是 8**——之前漏的是 `kb_search`。加技能桥 **12 个工具名**。

`build_default_tools` 只造 `kb_search`/`web_search`/`news_search` 三个；
`build_graph_tools`（`agent_research.py:367`）另加 `graph_lookup`/`evidence_lookup`，
在 `ask.py:1570` 与 `ask.py:2919` 两处装配进去。其余由 `episode_tools.build_episode_registry`
按 capability 逐个 gate 后追加。

---

## 1. 四平面覆盖体检（B1）

### 1.1 `provider` — 覆盖充分

| 工具 | 承载 | 门控 |
|---|---|---|
| `market_data` | 结构化行情与市场时序 | `allowed_capabilities` |
| `financial_data` | 结构化逐季财务指标 | 同上 |
| `mainline_context` | 同日主线与板块结构 | 同上 |
| `finance_query` | 语义化本地结构化查询（DuckDB） | `episode_tools.py` 显式 `if "finance_query" in context.contract.allowed_capabilities` |
| `l3_lookup` | 官方公告 / 互动易 | 显式 gate，且 `fixture_policy.external_search_enabled` 为假时**不注册** |
| `news_search` / `web_search` | 新闻 / 全网 | 有 `causal_tool_cutoff` 因果截断（防未来信息） |

**门控机制是「定义了 ≠ ���着」的**：注册发生在 `build_episode_registry` 内，逐工具检查
`context.contract.allowed_capabilities`。`DEFAULT_RESEARCH_CAPABILITIES` 由 catalog 全集
推导，但单次 run 的 contract 可以更窄——所以「日常问答实际开几个」由 contract 决定，
不是看 catalog。

**评价：够。** 这个平面没有值得优先补的缺口。

### 1.2 `graph` — 有工具，但返回结构比契约少四个字段

工具：`graph_lookup`、`evidence_lookup`（`agent_research.py:367` 起，纯本地 JSON 查询，
零外呼，与固定管线 G/R provider 同源）。

运行时契约 §5 要求返回六字段：

```text
entities / edges / edge_claims / facts / evidence / gaps
```

实测返回签名是 `tuple[list[AgentEvidence], str, ProviderTrace]`——一个**扁平证据列表**
加一句 observation 文本。concepts 与 exposures 被拍平成同一批 `AgentEvidence`，
`edges` / `edge_claims` / `facts` / `gaps` 四个字段在返回结构里不存在。

空结果路径（实测）：

```python
observation = "；".join(...) or "图谱无命中（概念与公司暴露均为空）"
trace = ProviderTrace(..., status="success" if evidence else "empty", ...)
```

所以**有**空结果信号（`status="empty"` 是机器可读的，observation 是给模型看的），
但**没有**契约要求的结构化分级——无法区分 `no_neighbors`（有实体无边）与
`no_facts`（有边无事实），也无法表达「只有 candidate」。契约 §5 的状态表要求按这三种
情况给不同的允许回答范围，当前实现只能给「有/无」二值。

**评价：部分。** 工具在、空结果不会静默，但降级粒度不足以支撑契约 §5 的状态机。

### 1.3 `shared_memory` — 三口径在，检索 provenance 不在

`evidence_search`（`episode_tools.py` `evidence_search_runner`）：

- **窄/宽/反在**：工具 description 明写「对本地知识证据执行 narrow→broad→counter
  闭环检索」，实现走 `evidence_search.EvidenceSearch`，带 `semantic_judge` 与
  `information_cutoff` / `deadline`。
- **跨 query 去重在**：`evidence_search.py:299` 与 `:541` 两处
  `seen: set[tuple[str, str]]`，命中即跳过。
- **provenance 不在**：全树 grep `cross_query_support` → **0 命中**；
  `evidence_search` 结果里没留 `query_id` / `rank`。

契约 §4 的排序层次（候选召回 → 相关性 → 时间过滤 → 来源分层 → 跨 query 去重 →
反方覆盖 → provider 核验）里，去重和反方覆盖有实现，可解释输入（query_id/rank/
cross_query_support）缺失。

**评价：部分。** 功能够用，但缺的这层是**为将来做 Hybrid 检索 / rerank / 离线评测
留的钩子**——现在不补，以后想做 rerank 就没有训练与评估信号。

### 1.4 `user_memory` — ⚠️ 确认缺口：agent 不能主动检索

**这是本批最重要的结论，也是唯一一条有明确代码证据的结构性缺口。**

现状是：`user_memory` 只被**固定管线（planner 侧）**当作 prompt 块注入，
**从来不是 agent 可调用的工具**。

证据（全部为 grep 实测）：

| 检查 | 结果 |
|---|---|
| `user_memory.memory_block_for_query` 的调用方 | 只有 `ask.py:621` 和 `ask.py:3733`，都在固定管线内，且被 `evidence_registry.provider_enabled(options, "M")` 门控 |
| `agent_research.py` 内出现 `user_memory\|memory_block\|experience_cards\|corrections` | **0 命中** |
| `agent.py` 内同上 | **0 命中** |
| `research_tool_registry.py` 内同上 | **0 命中** |
| 全树是否有名为 memory 的 ToolSpec | 只有 `workflows/foresight.py:114` 的 `name="memory"`，那是 foresight 工作流的**块名**，不是 agent 工具 |

`ask.py:621` 的实际形状——注入后追加一条 `Citation("M", "用户记忆检索块", ...)`，
紧接着加载 `experience_cards`：

```python
if evidence_registry.provider_enabled(options, "M"):
    memory_block = user_memory.memory_block_for_query(options.query, user=options.user)
    if memory_block:
        prior_parts.append(memory_block)
        result.citations.append(Citation("M", "用户记忆检索块", "历史判断与纠偏原则，仅作先验，不替代当前市场事实"))
    ...
    cards, card_warning = experience_cards.load_cards(...)
```

这与能力图谱的 `Cards → Planner`、`Verdicts → Foresight`、`UserState → Cards/Foresight`
三条路径一致——**图谱画的是对的，只是这些路径的终点都不是 agent 的工具面。**

**必答判断题的答案：不能。**

后果具体化：Knevo 每次研究第一步是 `finance_memory_query`（22 份快照里出现 24 次，
与 `finance_instrument` 并列第三高频），并按记忆条数决定检索深度
（≥10 条 → 2-3 个工具；0-2 条 → 5+ 个工具）。我们这边 agent 在循环内**看不到**
「这个用户对这个话题有多少历史判断」，所以：

1. 「按记忆条数定检索深度」这条自适应策略**当前无法实现**——不是参数没调，是信号进不到决策点；
2. 记忆只在**进入循环前**由 planner 注入一次，agent 在多轮研究中**无法按需复查**用户偏好；
3. 多轮追问时如果话题漂移到 planner 注入时未覆盖的方向，agent 拿不到对应的用户先验。

补充（`checkpoint_recall.py`）：该模块的 docstring 明写 M 块给的是「用户自己的核心
判断/纠偏原则 + 类别级聚合胜率」，并 `from intelligence.services.user_memory import
select_relevant`——也就是说**选择相关记忆的能力已经写好了**，只是没有以工具形式暴露。
这降低了后续补这条的成本（见 §3.3 方案 A）。

---

## 2. 对照运行时契约 §9 吸收优先级（B2）

| # | 条目 | 判定 | 代码位置 / 反证 |
|---|---|---|---|
| P0 | 类型纯度：每条召回带 `source_plane`/`kind`/`evidence`/`status` | **部分** | `AgentEvidence`（`agent_research.py:~120`）有 `tool`/`evidence_tier`/`supports`/`contradicts`/`independent_key`/`freshness`/`content_hash`，**无 `source_plane`、`kind`、`status`**。`EvidenceAtom`（`research_contract.py:871`）有 `evidence_tier` + `provenance: dict`，同样无这三个字段名。全树 grep `source_plane`（排除 json）→ **0 命中**。等价信息部分由 `tool` 名与 `evidence_tier` 承载，但**没有按平面做来源隔离的显式字段** |
| P0 | 图谱空结果门控：无边/事实/证据时结构化降级 | **部分** | 见 §1.2。有 `status="empty"` 与 observation 文本，缺 `edges`/`edge_claims`/`facts`/`gaps` 四字段，无法区分 `no_neighbors` 与 `no_facts` |
| P1 | 检索 provenance 与 `cross_query_support` | **未落地** | `cross_query_support` 全树 0 命中；`evidence_search` 不留 `query_id`/`rank`。跨 query 去重**已有**（`evidence_search.py:299`、`:541`） |
| P1 | 推荐与长期 memory 分库分状态，用户确认是显式写入 seam | **已落地** | `corrections` 的唯一写入入口是 `cli.py:1005` 的 `record-correction`——用户显式命令，agent 不持有写权限。这正是契约 §6「`user_memory`：Agent 只能提出候选，用户确认后写入」要求的形状 |
| P2 | 运行一致性验收（payload/事件/持久化/索引四层） | **未落地** | 全树 grep `execution_consistency` → 不存在。相关但不同层的东西**有**：`episode_semantic_verifier.py` 的 `_bound_evidence_quantities`（`:2063`）/ `_bound_evidence_dates`（`:2030`）做的是**证据绑定**校验，不是契约 §8 的四层运行一致性 |

### 2.1 `.claude/skills` 全量清单（19 个）

旧版验收标准要求「覆盖 `.claude/skills/` 下全部 skill，数量对得上」。实测 19 个，
逐个列出以便对账：

```text
advancers-chart          foresight-feedback      high-volume-gainers
hithink-market-query     ifind                   l2-moneyflow
limit-advance            market-overview         report-search
task-planner             theme-fermentation-tracer                theme-radar
top-gainers              top-gainers-feishu      up-line
watchlist-ma             公司画像页               潜意识模式
行业概览
```

`skill_tools.SKILL_REGISTRY` 只注册 **1 个**（`serenity-alpha`，
`skill_tools.py:167-181`）。**这是刻意设计，不是缺口**：其余多数要拉实时数据或写库
（飞书 / DuckDB 写入），接入会破坏 agent 的只读 / 无外呼红线。本节按验收标准列全，
不作为「差距」计入 §3。

---

## 3. 差距清单与取舍（B3）

### 3.1 反向结论先说

**工具面不是主要瓶颈。** 依据：

- `provider` 平面 7 个工具覆盖行情/财务/公告/新闻/网页/主线/本地 DuckDB，**够**；
- `graph`、`shared_memory` 两个平面**都有**工具，且是纯本地零外呼；
- 「skill 一个都调不到」是**错的**——技能桥存在，只开一个是红线约束下的设计决定；
- 编排层完备（`answer_orchestrator` / `question_router` / `research_task_planner` /
  `retrieval_planner` / `ask_planner` / `route_table` / `research_plan` /
  `generic_research_owner`）。

所以 B/C 对比 `knevo_wins 9 : workbench_wins 2` 的原因，**不能**归给「工具数量少」。
另一条已有旁证指向别处：`acceptance_cases.json` 里我们自己的工具痕迹分析写着，Knevo
主力是新闻检索（`finance_news` 57 次），而**涨停家数、连板梯队、新高家数这类需要全
市场结构化截面的题它只能重建，因为它没有可按历史日期查询的截面数据源，而我们有
`fact_*` 表**——即这类题**真值在我们这边**。这与「壁垒在数据授权」的 Knevo 逆向结论
一致，也说明胜负差异更可能来自题型分布与表达/裁决层，不是工具面。

### 3.2 确认的差距（按价值排序，均有代码证据）

| # | 差距 | 证据 | 补上能答什么现在答不了的 |
|---|---|---|---|
| G1 | `user_memory` 不可被 agent 主动检索 | §1.4 四处 grep 全 0 | ①「按我的历史判断，这个题材我以前怎么看的」在多轮研究中途无法复查；②自适应检索深度（记忆多→少查、记忆少→多查）无法实现；③话题漂移后拿不到对应用户先验 |
| G2 | `graph_lookup` 返回缺 `edges`/`edge_claims`/`facts`/`gaps` | §1.2 返回签名 | 「A 和 B 到底有没有供应关系、依据是哪条证据」——当前只能给扁平证据列表，无法按契约 §5 状态表判定「可以引用关系」还是「只能说存在实体」 |
| G3 | 检索 provenance（`query_id`/`rank`/`cross_query_support`）缺失 | 全树 0 命中 | 不影响当前回答质量，但**挡住** Hybrid 检索 / rerank / 离线检索评测——没有可解释输入就没有训练和评估信号 |
| G4 | 类型纯度字段（`source_plane`/`kind`/`status`）未显式化 | `AgentEvidence` / `EvidenceAtom` 字段表 | 跨平面来源隔离靠 `tool` 名隐式推断；平面一多容易把 `shared_memory` 的观点当 `provider` 事实引用 |
| G5 | 契约 §8 四层运行一致性验收未落地 | `execution_consistency` 不存在 | 异步 / SSE / worker 路径的静默降级（正如 `fast_daily_sync.py` 那类「行数对、值是空壳」）只能靠人发现 |

### 3.3 取舍对比（四条路线）

**方案 A：接 `user_memory` 检索工具**（对应 G1）

| 维度 | 评估 |
|---|---|
| 能力增益 | **高且唯一**——是四个平面里唯一「完全缺一条通路」的。解锁自适应检索深度 |
| 安全风险 | **低**。纯本地文件读取（`intelligence/users/<user>/`），零外呼；**只读**，写入仍走 `cli.py:1005` 的显式 seam，不碰契约 §6 的写权限分层 |
| 证据可追溯性 | **可绑定，但必须标平面**。已有先例：`ask.py:621` 注入时就挂了 `Citation("M", "用户记忆检索块", "…仅作先验，不替代当前市场事实")`。工具化后必须沿用这个 disclaimer，且**不能**让用户记忆冒充客观事实（契约 §1 明确 `user_memory` 「可作为用户基线，不能冒充客观事实」） |
| 实现工作量 | **低**。`user_memory.select_relevant` / `memory_block_for_query` / `experience_cards.select_relevant_cards` 都已存在（`checkpoint_recall.py` 已在复用），主要是包一层 ToolSpec + 加 capability 门控 |
| 适合场景 | 多轮研究、个性化问答、需要「我以前怎么看」的题 |

**方案 B：扩 `skill_tools` 注册表**

| 维度 | 评估 |
|---|---|
| 能力增益 | **低到中，且与红线冲突**。19 个 skill 里绝大多数要么拉实时数据（需 CDP proxy / 登录态 / iFinD 凭证），要么写库（飞书 / DuckDB）。**能安全接的本来就少** |
| 安全风险 | **高**。破坏只读 / 无外呼红线；写库类 skill 进 agent 循环等于让模型持有副作用权限 |
| 证据可追溯性 | 中。skill 输出多为报告文本，绑定到具体数字出处需要额外结构化 |
| 实现工作量 | 中到高（逐个封装参数 + 隔离副作用） |
| 适合场景 | 只读、无外呼、输出结构化的少数 skill（`serenity-alpha` 已是这类）。**不建议**作为本轮主线 |

**方案 C：放开只读 SQL**

| 维度 | 评估 |
|---|---|
| 能力增益 | 中。`finance_query` 已覆盖语义化查询；只读 SQL 主要多出**跨 dataset join** 与**任意衍生指标** |
| 安全风险 | 中。需防御 SQL 注入、资源耗尽（全表扫）、以及**绕过 `fact_sector_daily` 是 VIEW 只暴露 `published` 快照**这层治理——直接 SQL 可能读到 `*_generation` 底表的非 published 版本 |
| 证据可追溯性 | **差**。这是主要反对理由：任意 SQL 的结果绑不回具体证据 id，与「每个数字必须绑定出处」（`bound_evidence` / `citation`）冲突。要补就得给每行结果造 provenance |
| 实现工作量 | 中（parser 白名单 + 行数上限 + 快照约束） |
| 适合场景 | 探索性分析、人在环路复核；**不适合**直接进回答链 |

**方案 D：受控代码执行（sandbox 内只调数据 API）**

| 维度 | 评估 |
|---|---|
| 能力增益 | **最高**。任意衍生计算、多步聚合、统计检验 |
| 安全风险 | **最高**。需要真沙箱（进程隔离 / 无网络 / 文件白名单 / CPU-内存上限）。这是四条里唯一引入新攻击面的 |
| 证据可追溯性 | 差到中。计算结果是**派生量**，绑定的是「输入证据 + 计算过程」而非单一出处；要可信必须留可复现脚本 |
| 实现工作量 | **高** |
| 适合场景 | 成熟期的量化分析；**当前阶段不建议** |

### 3.4 建议

按「增益 ÷ 风险 ÷ 工作量」排序：**A ≫ C > B > D**。

方案 A 是唯一「补一条完全缺失的通路、且不破任何红线、且底层函数已就绪」的选项。
G2（图谱六字段）价值次之但工作量更实——它动的是返回契约，会牵动所有消费方。
G3/G4 是**投资性**的（为将来的 Hybrid 检索与来源隔离铺路），不解决当下失分。

**但要说清楚**：以上都是工具面 / 知识运行时层的改进。§3.1 的反向结论意味着
**如果目标是缩小 B/C 对比的胜负差**，先做工具面可能投错方向——证据指向题型分布与
表达/裁决层。要定位真实失分点，下一步该做的是**按题拆 B/C 那 11 场的失分原因**
（缺数据？缺工具？还是答了但表达/裁决不达标？），而不是继续加工具。
这个诊断本身也说明：**清单 §0 的「工具面差距很大」假设，被本批推翻。**

---

## 4. 回写能力图谱（B4）

图谱现状：`graph_audit.py` exit 0，30 节点 / 32 路径，无漂移。

**发现的缺口**：节点清单里没有「agent 工具面」相关节点——grep 节点表未命中
`skill_tools` / `agent_research` 的工具构建函数 / `research_tool_registry`。而按图谱
自己的维护口径（「新增入口命令、服务模块、运行时证据源…都要回到本页追加节点」），
11 个 catalog 工具 + 技能桥属于**稳定能力**，应当在册。

已按其维护口径追加（详见该文件 diff），追加后重跑 `graph_audit.py` 必须仍为 exit 0。

**没有**新建平行的能力清单文档——图谱是唯一事实源，本文件只做本批诊断记录。
