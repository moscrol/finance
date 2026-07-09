---
type: knevo_corpus
id: q9
date: 2026-07-09
credits: 未回报
topic: finance-associate 第 6 维「历史模式匹配」的实现工具
key_finding: 历史类比引擎=finance_memory_query（双层记忆检索），不查行情/web/图谱——匹配的是"场景结构"而非价格曲线；类比质量与记忆库厚度成正比，薄则显式"暂无显著匹配"
---

# Q9：finance-associate 历史类比靠什么工具（Knevo 原文回贴摘要）

## 调用链（skill 原文）
```
Step 3: 查记忆
调 finance_memory_query 查同主题/同板块历史观点、矛盾观点、推理模式
→ 填维度 5(KOL 交叉)和 6(历史模式)
```

## 关键设计
1. **只查记忆，不查数据**：历史类比不用 finance_quote（K 线回测）、不用 web_search（召回太泛无结构化场景标签）、不用 finance_graph_context（图谱管产业链结构不管时间维模式）。
2. **双层记忆来源**：user-finmemory（用户自己的复盘/thesis/"当时发生了什么→后来怎么走"）+ finmemory 共享库（策展方沉淀的历史场景模板，如"2023 算力第一波""2021 周期股见顶特征"）。
3. **匹配的是场景结构**：供需结构、估值位置、政策周期、资金行为模式的相似性——"是否出现过类似场景"而非"类似 K 线形态"。
4. **诚实降级**：记忆薄则第 6 维标"数据不足，暂无显著历史模式匹配"，deliverable 允许"暂无显著关联"——不编造。

## 架构解读
- 台账记录2 的疑问解开：它的历史类比不是 web 印象流，而是**策展记忆库里预沉淀的场景模板**——本质是"人肉标注的 case library + 语义检索"。质量瓶颈=库的厚度，不是模型能力。
- 三库分工进一步清晰：共享库=历史场景模板+操作框架（常驻高优先级），用户库=个人复盘/thesis，图谱=产业链关系——各管一维，检索时按维度定向路由，不是混合召回。

## 与本地对照 / 回灌
- **更新（2026-07-09 检查）：台账 #11 已落地**——PR #157 feat/ask-analog-block（已合并）实现 D8 历史类比检索块（intelligence/services/market_analogs.py）：①同题材形态签名（双红天数/成交额首末比/均涨）滑窗加权距离取 K 段相似窗口，后续 5/10/20 日走法只报 fact_sector_daily 事实不给概率；②跨题材剧本卡库 market_playbooks.jsonl（特征向量匹配：drawdown_pct/rebound_retrace_ratio/volume_shrink_ratio 归一化距离），仅 review_status=approved 的人工审核卡生效。
- 对照结论：我们的实现已同时覆盖 Knevo 的"场景模板"层（剧本卡=其共享库场景模板的可溯源版）+ 它没有的定量层（DuckDB 逐日行）。剩余差距只在剧本卡数量（需持续从复盘提炼入 market_playbooks.jsonl）。
- q9 原回灌候选"建 case-library"作废，改为：**持续扩充 market_playbooks.jsonl 卡片数**，历届复盘中的切换/见顶案例按卡片 schema 提炼送审。
