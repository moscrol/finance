# 记忆机制质检 + agent book 对照（第 3 / 8 章）

> 日期：2026-08-13
> 范围：六 slice 落地后（`main` @ `187e918f`）的实现质检，对照
> [bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book) **原书**第 3 章（记忆与知识库）
> 与第 8 章（持续进化）。原书从 GitHub raw 精读，不只沿用 08-10 章节审计稿。
> 单测收据：`intelligence.tests.test_{retrieval_recall,memory_status,track_contract,theme_lifecycle_timeline,market_regime_analogs}` **64 passed / 0 failed**（本轮重跑）。

---

## 0. 一句话结论

六 slice **骨架对、门禁对、单测绿**；对照原书，真正该做的优化不是上 RAPTOR / GraphRAG / 向量库，
而是把已经写出的尺子和契约变成**可判定的观测量**：

1. recall@k 尺子还没有标注集 → 还不能回答「证据不足是召回问题还是题目超纲」；
2. 跟踪契约仍是 prompt-only → live 遵守部分，要用仓内已有的结构 verifier 把门，不要再堆提示词；
3. 第 8 章的「离线候选更新 → 独立审核 → 发布」在 **user_memory 平面还没有**，但仓内
   `forecast_learning_loop` 已经是同一构件——扩平面，不另起炉灶。

---

## 1. 质检：实现层（相对设计稿）

### 1.1 已兑现、且形状正确

| Slice | 兑现 | 质检要点 |
|---|---|---|
| 1+2 D10 | `market_regime_analogs.py` + registry D10 + 意图双词面 | 后续 5/10/20 日只报事实；claim 状态 INFERRED；缺维覆盖率惩罚。单测钉住「不抢 D8」 |
| 3+3.1 时间线 | `theme_lifecycle_timeline.py` | 与 `theme_lifecycle.py` 词表分离；滞回默认 2 日；缺数声明而非伪造 |
| 4 跟踪契约 | `track_contract.py` + `contract_guidance` 独立段 | 修复 PR #322 后契约不再塞进「历史经验卡片」标题下 |
| 5 退出机制 | `memory_status.py` append-only 覆盖行 | 无状态行行为不变（棘轮）；CLI 拒绝悬空 target；loader 过滤 archived/rejected |
| 6 recall@k | `intelligence/eval/retrieval_recall.py` | 同时报学术 recall@k 与 hit_rate@k；归档记录不入召回（与 slice 5 联动） |

入口 fail-closed 晋升门 `memory_gate.py` **本轮没改、也不该改**——它已经是 E-006
candidate→accepted 的本仓版本。Mem0 v3 的「仅追加写入、检索时消歧」与本仓
append-only + 退出覆盖行同构；不要退回 Mem0 v2 的写入期 UPDATE/DELETE。

### 1.2 实现层缺陷（按能否用 0 档复现排序）

| # | 缺陷 | 证据 | 成本档 | 建议 |
|---|---|---|---|---|
| Q1 | recall@k **没有人工标注集** | 尺子 CLI 要求 `--cases`；仓内无 JSONL | 0：先建 10–20 条 | 尺子才能干活。没有标注，分数不存在 |
| Q2 | `user_memory_retriever` 在 `limit=k` 时 judgments/corrections **各**取 k，召回集合可达 2k | `retrieval_recall.py` 注释已承认「与生产一致」 | 0：改尺子文档口径，或合并后截断到 k | 标注时写清：生产 @k = 每通道 k，不是全局 top-k |
| Q3 | 记录身份 = `ts`，同秒并发可能碰撞 | `relevant_memory_records` / `record_status(target_ts=)` | 1：新增时写 `id=sha256(kind+ts+content)[:12]`，旧行仍认 ts | 退出机制、标注集都绑在这个键上 |
| Q4 | 跟踪契约 prompt-only；live 四态对照 / 无基线声明 / 下期关注仍不全 | workbench 实测（设计稿 §8 后修复仍部分遵守） | 1：接到已有 `repair_coordinator.missing_outputs` | 书第 8 章：能确定执行的约束进程序，不堆 Prompt |
| Q5 | `experience_cards` 有 `invalidated` / `promotion`，**不走** `memory_status` | 两套退出语义 | 1：卡片退出继续用 `invalidated`；不要硬并 | 文档写清两套出口，避免第三次「无状态机」误判 |
| Q6 | D10 **未接** workbench `research_owner` stage | 设计稿 slice 2 已标明留待 | 2：仅当 workbench 路径真的问环境类比 | 不要为接线而接线 |
| Q7 | 板块口语名（液冷 / AI概念）对不上 `fact_sector_daily.sector_name` | live 显式降级 | 1：别名表走已有 `resolve_query_themes` / `dim_sector` | 时间线入口问题，不是阶段算法问题 |
| Q8 | 时间线 25 段仍偏碎 | live 固态电池 53→25 | 1：再加最短阶段时长（如 <3 日切段合并） | 滞回只解决了回流抖动 |
| Q9 | 设计稿文首仍写「**设计稿，未动产品代码**」 | `2026-08-13-memory-analog-lifecycle-design.md` L4 | 0：改状态栏 | 下一任 agent 会按未实施来规划 |

Q5 不是 bug：经验卡片记的是「以后怎么答」，judgments 记的是「我对市场的判断」，
退出理由不同（坏指标 vs 过时判断）。并成一套 status 会把两种失败形状混在一起。

---

## 2. 对照原书第 3 章（记忆与知识库）

书的收敛结论（原书本章小结 + 实验 3-11）：**双层记忆**——少量关键事实用
Advanced JSON Cards **常驻上下文当概览**；海量细节用上下文感知检索 **按需召回**。
共同痛点：冲突、过期、检索不准。

| 书的要素 | 本仓现状 | 要不要补 | 说明 |
|---|---|---|---|
| 四种存储格式（Notes / JSON Cards / Advanced Cards） | experience_cards / corrections 是按 query 相关性召回的规则条，**不是**常驻概览卡片；缺 backstory / person / relationship | 🟡 小补，不要换格式 | 本仓消歧对象是**题材/公司**不是「张医生」。缺的是「少量纠偏原则常驻」vs「大量判断按需召回」这一分层，不是 Mem0 字段抄过来 |
| Mem0 v3：仅追加 + 检索时消歧 | append-only JSONL + `memory_status` 覆盖行 | 🟢 已同构 | 不要退回写入期 UPDATE/DELETE |
| 冲突解决：场景限定（qualification），不能「留最新」 | 退出机制能归档旧条，但**不会**把「A 在条件 X 下成立、B 在条件 Y 下成立」写成两条限定 | 🟡 P1 | 用户纠偏常是「不是这样，是在双红确认后才算发酵」——这是限定，不是替换 |
| recall@k | 尺子有了；书脚注：该书 recall@k = hit rate/success@k | 🔴 缺标注集 | 我们同时报学术 recall@k 与 hit_rate@k，**对齐书时用 hit_rate@k**；标注集建好前不要横向对比 Anthropic 数字 |
| 上下文感知检索（索引期给 chunk 加 LLM 前缀） | retrieval planner 有；wiki-rag 在 Mac 实测过告警/找不到知识库仓脚本 | ⚪ 暂缓 | 书明确：这是索引期加法。本仓 [M] 块是短 JSONL，不是切碎的对话；前缀收益小。wiki 侧才是这块该落地的地方 |
| RAPTOR / GraphRAG | 已有 `wiki/relations/` 图谱；无层次摘要 | ⚪ 不做 | 原书判断标准：查询主要是「找到含某信息的片段」→ 混合检索够用；**跨文档综合 / 多层次导航**才值得上。theme-radar 已经在用图谱关系，不是缺 GraphRAG |
| 知识更新：Proposer PR → 异源 Reviewer | 知识库 ingest 有 gold review / 双人一致；user_memory **没有**提案层 | 见第 8 章 | 第 3 章这条与第 8 章离线循环是同一形状，只是尺度不同 |
| 失效内容检索期过滤 | `memory_status` 过滤 archived/rejected；experience_cards 跳过 `invalidated` | 🟢 | 与书「版本号 + 生效/失效时间」同思路，事件覆盖行比改字段更可回放 |
| 三层评估：基础回忆 / 多会话检索 / 主动服务 | 基础回忆 ✅；多会话检索有 [M] 但无 recall 数字；主动服务（护照过期那种跨会话预警）❌ | ⚪ 主动服务不做 | 本仓「越用越懂」的产品形态是答题先验 + foresight 排序，不是行程助理 |

### 第 3 章真正该迁移的三句话

1. **双层是「常驻概览 + 按需细节」，不是「两个 JSONL」。** 现在 corrections / experience_cards /
   judgments 三条都走「按 query 打分取 top-k」。结果是：关键纠偏原则可能没被召回，
   而一条弱相关旧判断占了槽。最小补法：把 `promotion=methodology` 的卡片和
   `principle` 非空的纠偏 **无条件注入一小段常驻块**（条数硬顶，例如 5），其余仍按需。
2. **冲突写限定，不写覆盖。** `memory_status rejected` 适合「记错了」；
   「以前那句在退潮期成立、发酵期不成立」应追加一条带 `applies_when` 的新判断，
   旧条保留。这就是书里的 qualification。
3. **recall@k 是检索层尺子，不是答案正确性。** 本仓模块注释已经写对；缺的是标注集。

---

## 3. 对照原书第 8 章（持续进化）

书的闭环：**在线只记录证据 → 离线生成候选更新 → 独立验证后发布 → 可回滚。**
四种载体：知识 / Prompt·Skill / 程序 / 参数；优先可归因、可回滚的局部修改。
评价器与进化模块必须分开（不能既当裁判又改规则）。

| 书的环节 | 本仓现状 | 缺口 |
|---|---|---|
| 在线记录证据 | corrections / judgments / checkpoints / verdicts / interactions / answer_scores | 🟢 齐 |
| 离线生成候选更新 | **双盲复盘**已有：`forecast_learning_loop` 的 reflection → `lessons.jsonl` / `rule_candidates.jsonl`（pending→approved/rejected） | user_memory / experience_cards **没有**等价提案层；`memory_gate` 是同步入口门，不是离线提案 |
| 验证后再发布 | gold review（知识库）、forecast 人工 approve | 经验卡片 `promotion=candidate` 字段在，但没有离线审核流把它推到 `promoted` |
| 可回滚 | git + append-only 状态行 | 🟢 记忆条目可回滚；Prompt 规则没有「这条经验导致了哪次回答变差」的归因 |
| 睡眠学习五步（触发→定向→比较→提案→修剪） | 🟢 **夜间整理已经存在，不要再开一条**。采集半 `intelligence/dream/nightly.py`；策略建议半 `evolve_suggest.py`（suggest-only 分支）；判断回检 `checkpoint-recheck`；潜意识收工 `subconscious.consolidate`；双盲 `forecast_learning_loop`。缺的不是「夜间进程」，是 user_memory 平面还没接到这些已有出口 |
| Curator：跟踪陈旧并归档 | `memory_status` 是**人工**出口 | 缺 TTL / 长期未命中 → 建议归档（建议，不自动删） |
| 评价器 ≠ 进化模块 | semantic judge / 结构 verifier 评回答；`memory_gate` 决定能否进 durable | 🟢 已分开。不要让 judge 直接 `record_card` |
| Prompt 膨胀 | 跟踪契约进了 system prompt；live 仍部分不遵守 | 书：能确定执行的约束进程序。对应 Q4 |
| Harness-updating vs harness-benefit | 契约写进 prompt = 更新了产物；模型不激活 = 受益失败 | 实测已发生。拆开评估：先测「段在不在」（单测已钉），再测「答里有没有四态」（缺 verifier） |

### 不要重新发明的仓内部件

`forecast_learning_loop` 已经是第 8 章骨架在「双盲复盘」平面上的实现：
候选与正式能力隔离、人工批准、拒绝也留日志。user_memory 平面缺的是**把同一骨架接过去**，
不是再写一套进化框架。

同样，第 8 章「将经验写成程序」——跟踪契约的四态标题、无基线声明、下期关注清单，
属于**可确定检查的输出结构**，应进 `repair_coordinator.missing_outputs`（仓内已有
direct/counterpoint 缺口修复环），而不是再加一段更长的 prompt。

### 第 8 章明确不要做的

- 不要在线改正式记忆 / 正式 Skill（一次偶发成功或提示注入会跨会话生效）。
- 不要让同一个模型既打分又写规则（judge 不得直接晋升 experience_cards）。
- 不要一上来优化「产生更新提案的优化器」——书：优先局部规则，搜索空间越大越难归因。

---

## 4. 优化点（按成本档，能用 0 档复现的绝不上 4 档）

> 档位对齐 `~/harness-reference/TOOLKIT.md`：0 = 已有数据/已有测试能判定；
> 1 = 小补丁 + 单测；2 = 接线/live；4 = 新子系统。

### 现在就值得做（0–1 档）

1. **建 user_memory 标注集（Q1）** ✅ 本轮已落合成夹具
   `intelligence/eval/fixtures/user_memory_recall/`（3 case：命中纠偏、过题材、负例）。
   **不是真人标注**——真人标注仍要你出 10–20 条才有生产读数。夹具只证明尺子能跑。

2. **跟踪契约进结构 verifier（Q4）** ✅ 本轮已做
   `ensure_track_contract_visible`：缺四态/无基线声明、TTL、下期关注时追加可见补全段，
   不覆盖模型正文。与 `ensure_forecast_scenarios_visible` 同形状。
   `include_track_guidance=False` 时不补。

3. **设计稿状态栏改成「已落地，质检见本文」**（Q9） ✅ 上一提交

4. **常驻概览小块** ✅ 本轮已做
   `experience_cards.select_resident_cards`（promotion ∈ promoted/methodology）+
   `corrections.select_resident_principles`（带 principle），硬顶 5，注入经验卡通道。
   [M] 块仍按 query 召回，棘轮不变。

### 标注集跑出数字之后再做（1 档）

5. **k 口径收口（Q2）**：要么生产改成合并后 top-k，要么尺子改名叫 `@k_per_ledger`。
   没有标注数字时改这个是盲调。
6. **记录身份（Q3）**：新写入加稳定 `id`；标注集改绑 `id`。旧 `ts` 继续可解析。
7. **冲突 qualification**：`record-correction` 增加可选 `--applies-when`，
   渲染成「在 {条件} 下：…」。旧条不自动归档。
8. **板块别名（Q7）** + **最短阶段时长（Q8）**：时间线可读性，与记忆闭环正交，
   可单独开 `theme-radar/` 小分支。

### 明确暂缓（2–4 档，书也不建议现在上）

| 想法 | 为什么暂缓 |
|---|---|
| RAPTOR / GraphRAG / 层次摘要 | 原书：混合检索够用时不上。本仓图谱已服务 theme-radar |
| wiki-rag 上下文前缀 | 索引期加法，落点在知识库仓，不在本轮记忆平面 |
| user_memory 离线提案层 | 夜间整理已有（dream / checkpoint-recheck / subconscious / forecast_learning_loop）。扩平面等真人标注集证明召回问题再做 |
| 自动 Curator 归档 | 没有 hitCount / lastHit，陈旧检测会误伤低频但正确的纠偏。先人工 `memory-status` |
| D10 接 research_owner | 仅当 workbench 路径确实问环境类比；episode 级 D10 已 6/6 PASS |
| 给历史类比上 HMM / embedding | 设计稿 §7 已否；库厚度才是 q9 瓶颈 |

---

## 5. 教学：为什么这张对照表这样排

**原理：失败方式不同的能力不能混成一个「记忆系统」。**  
第 3 章管「世界/用户是什么样」（陈述性知识），第 8 章管「在什么条件下该怎样做」（行为经验）。
Knevo 四平面（文本 / 图谱 / 用户记忆 / 预测台账）是同一刀法。本仓已经按平面拆了文件；
质检发现的问题几乎都是**平面内部缺尺子或缺门**，不是缺一个统一向量库。

**选型对比（反复会被问到的三条）：**

| 问题 | 选 | 不选 | 可迁移到 |
|---|---|---|---|
| 记忆冲突 | 追加新条 + 场景限定；错记才 rejected | 就地 UPDATE 成最新 | 任何 append-only 台账（公告、研报观点） |
| 契约遵守 | 结构 verifier + repair | 更长的 system prompt | 一切「模型该按模板输出」的场景（财报摘要、复盘段落） |
| 检索好不好 | 人工标注 + recall@k / hit_rate@k | 用答案分数反推检索 | RAG 面试常考点：检索层与生成层必须分开度量 |

**面试常考点：** 书脚注把 recall@k 定义成 hit rate。被问到时要能说出：
学术 recall@k = |命中相关| / |全部相关|；hit@k = 前 k 里有没有至少一条相关。
本仓两个都报，对比 Anthropic Contextual Retrieval 论文时应对他们的 hit-rate 口径。

---

## 6. 续作（2026-08-13）：夜间整理不是缺口；二阶提问要踏一层

### 6.1 夜间整理——纠偏前一版质检

前一版把「睡眠学习五步」写成缺口，**说错了**。仓内已经有一整条夜间链，不要再开：

| 已有件 | 做什么 |
|---|---|
| `intelligence/dream/nightly.py` | 采集半：脱敏 digest 提交到 `dream-loop/transcripts-<date>`，不合 main |
| `intelligence/dream/evolve_suggest.py` | 策略建议半：`evolve.py suggest` 只读 DuckDB，建议进独立分支 |
| `checkpoint-recheck` launchd | 到期核对可证伪判断 → verdict → 校准回注 foresight |
| `subconscious.consolidate` | 潜意识收工：缓冲信号 → 提案 → 人确认后落 judgments |
| `forecast_learning_loop` | 双盲 reflection → lessons / rule_candidates（pending→approved） |

user_memory 平面若要「夜间整理记忆」，接这些出口，不新写 sleep-learn 进程。

### 6.2 二阶提问——还需要，但要停在一阶事实之上

三套生成器不是重复建设，触发不同：

| 生成器 | 触发 | 去留 |
|---|---|---|
| `foresight.py` 猜你想问 | 盘面驱动、每日主动 | **留**。这是 Knevo「进阶提问」和书第 3 章「主动服务」的本仓实现 |
| `followups.generate_answer_spec_followups` | 本轮 AnswerSpec 的缺口/触发/动作 | **留**。workbench 已在用，追问锚在本轮证据 |
| `followups.generate_followups` 五类模板 | 答后芯片；API `foresight_followups` 步 | **留，但改成二阶**。跟踪题去掉 `recheck`（与下期关注重复）；模板不再问「近 5 日双红如何」（D 块已答） |
| `ask.py` 后续验证点 | 答案正文里的确定性跟踪句 | 留。与芯片是不同落点（正文 vs 可点击） |
| 跟踪契约「下期关注」 | 仅跟踪题 | 留。是输出契约，不是提问器 |

**不要删 foresight。** 新切片（D10 / 时间线 / 跟踪契约）回答的是一阶事实；二阶提问的产品价值是「由此推出的下一层后果」。优化是禁止它再问已经被数据块答过的问题：

- 不要问「有没有历史上类似情绪环境」→ D10
- 不要问「题材处于哪个生命周期阶段」→ 时间线
- 不要问「上期结论有什么变化」→ 跟踪契约
- 跟踪题不要再生成盘面回检芯片

本轮已改 `_SYSTEM_PROMPT`（foresight）和 followups 模板/过滤。

