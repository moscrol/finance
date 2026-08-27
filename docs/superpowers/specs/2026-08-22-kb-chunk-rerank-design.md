# 设计：KB 检索链 chunk 重切 / rerank（V5 遗留第二腿）

- 日期：2026-08-22
- 作者：执行方（只出设计，不接生产代码、不部署、不打 8792、不跑 live 探针）
- 状态：Draft（待验收方复算 + 用户确认跨仓裁决后再派实施）
- 上游：台账 `R-20260821-17`（V5 选段质量；噪声头腿 live 成立，零信息窗换正文腿 pending）
- 总纲：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md`（调用 / 检索 / 送达三层；§V3 / §V5；纪律第 6 条预算账）
- 立案：`docs/verification/2026-08-21-inputside-delivery-window.md`（形状 IV「词频绑架选段」）
- 落地边界：`docs/verification/2026-08-22-inputside-selection-quality.md`（长电 4 条窗内无正文可换）
- 分档真本源：`docs/superpowers/specs/2026-08-20-retrieval-tier-by-remaining-budget-design.md`（`select_mode_for_remaining`，剩 <15s → BM25）。实施 plan `docs/superpowers/plans/2026-08-20-retrieval-tier-by-remaining-budget.md` 未合 main，语义以已合 spec + 本树 `kb_rag.py` 为准。
- 台账行号预留：`R-20260822-01`（本仓换窗）/ `-02`（排序）/ `-03`（跨仓重切，需用户裁决）

## 0. 一句话

V5 能剥标签汤，不能从「来源清单 / wikilink 堆 / 路径行」里变出正文——那些命中 chunk 本身就是结构段。收口要**换窗**（同页另取正文，或重切索引）或**换页排序**（别把邻页链接堆排进 top-k）。两条可分批验收；物理重切是跨仓单，本仓先有一条不重建索引的替代。

人话：现在的病不是「窗太窄」或「头上多了 `tags:`」，是检索把目录页和友情链接当成了正文。再加过滤规则等于对着空抽屉擦桌子。

---

## 1. 本文件是什么 / 不是什么

### 1.1 是

给 V5 诚实边界之后的**第二腿**一张可派单合同：

1. 长电案 4 条零信息窗是怎么被切出来的（索引取证，不是推断）；
2. chunk 侧 / rerank 侧各自原理、替代方案、延迟量级；
3. 跨仓 vs 纯本仓两条路都写清，留给用户裁决；
4. 怎么按层分开预注册，避免「送达变大但仍是词频段」的下一代混杂（邻页正文冒充长电正文）；
5. 可逐字抄进台账的 `verification_prediction`。

### 1.2 不是

- 不是实施计划，不改 `kb_rag.py` / `chunking.py` / 生产默认 mode。
- 不是 V3 送达量单、不是 V4 工件页卫生、不是 V5 再加一条过滤规则。
- 不是 S9（`2026-08-15-bookgap-s9-kb-rerank-eval-loop.md`）的重做——KB 仓 `mode=rerank` + `bge-reranker-v2-m3` **已经落地**；本单问的是 finance 消费链要不要开、开在哪一档、以及它救不救形状 IV。
- 不是第二套降档。任何新增检索开销必须进已有 `select_mode_for_remaining`（`rerank` 已在 `_DENSE_MODES`），禁止再写一个阈值函数。

### 1.3 三层还有效（沿 R2，勿压成一条线）

| 层 | 本单碰不碰 | 判别变量 |
|---|---|---|
| 调用 | 不碰 | 题形是否进 plan（V1） |
| 检索 / 排序 | V9b | **哪些页**进 top-k（邻页还是目标页） |
| 送达 / 选段 | V9a | **同一页里哪一段**被送出去 |
| 索引构建 | V9c（跨仓） | 物理 chunk 边界；改了必须重嵌 |

R2 已预注册：只修 III 不修 IV → 送达变大但仍是词频段。本单对称预注册：只修排序不换窗 → 颀中掉出 top-k，但长电逻辑跟踪页仍送「原始资料链接」；只换窗不修排序 → 颀中槽位还在，只是变成颀中自己的「一句话」（正文，但答非所问）。

---

## 2. 问题定位：长电 4 条零信息窗是怎么切出来的

### 2.1 现行切法（知识库仓，本仓只消费）

权威脚本：`knowledge-base-private/skills/lib/rag/chunking.py`（`chunk_file` / `_split_sections` / `_split_long`）。
现行索引：`/Users/a77/knowledge-base-private/.rag_index/`（2026-08-22 采样，**禁止整读** `chunks.jsonl`，181MB / 实测 172.7MB）。

| 项 | 读数 |
|---|---|
| `chunking_version` | `rag-chunking-v3` |
| `num_chunks` | 146595 |
| `built_at` | 2026-08-19T15:35:47Z |
| `include_raw` | false |
| `max_tokens` | 448（BGE 窗口 512 − 64 边距） |
| `target_tokens` | 336（超长 section 再切目标） |
| `overlap_ratio` | 0.15 |

算法（人话 + 面试口径）：

1. **结构感知切**：按 `#`～`######` 标题切 section，面包屑写入 `section`（如 `长电科技｜最新逻辑跟踪 > 原始资料链接`）。
2. **固定窗 + overlap 兜底**：单个 section 超过 `max_tokens` 时按段落贪心打包到 `target_tokens`，尾部留 15% 重叠。大表格/长列表再按行、再按字符硬切。
3. **每块强制前缀**：`# 标题` + `tags:` + `section:`。这就是 V5 剥掉的标签汤——它是为嵌入「自带上下文」设计的，不是 bug。
4. **页首 lead**（`CHUNK_LEAD_TOKENS`）默认 0，现行索引没开。

这是业界常见的 **Markdown heading split + token window**（LlamaIndex / LangChain 的默认形状）。它比纯固定字数窗更尊重文档结构，但有一个本库特有的失败形状：**结构小节本身就是合法 heading，于是「相关实体」「原始资料链接」「Raw / Manifest Trace」各自成块**。块可以很短（90～200 字），BM25 对「查询词反复出现」仍然给高分。

可迁移点：任何「标题切块」的 wiki/Notion/手册 RAG，都要先列一张**禁止单独成块的 section 名**（来源、相关链接、目录、frontmatter），否则词频检索必然先命中目录。面试常问 chunking 策略，答「按标题切」只答对一半——还要答「哪些标题不该切成检索单元」。

### 2.2 检索怎么把块变成「页命中」（本仓消费链）

Finance 侧 `kb_rag.retrieve` 调 KB 仓 `rag_index.py query`。默认 `mode=hybrid`：

```
dense top-80 ∪ BM25 top-80 → 实体/代码 boost → RRF(k=60) → 按 page_id 聚合成页
→ 沿 wikilink 一跳邻居补候选（NEIGHBOR_HOP=True）
→ 每页只留分数最高的 best_chunk
→ llm_evidence = 命中块 + 同 section 相邻 1 块（ADJACENT_CHUNKS=1）
```

要点（实施时不要再探一遍）：

- **RRF 已经有了。** `kb_rag._MODE_RECALL_DESC["hybrid"]` 原文：「BM25 关键词 + 稠密向量(BGE-m3) + RRF 融合」。本单再提「上 RRF」是重复建设。
- **`mode=rerank` 在 KB 仓已经有了**（`bge-reranker-v2-m3`，对前 50 个**页**用 title+best_chunk 重打分）。Finance 默认 structured 档案 `hybrid`；`full` 档案才映射 `rerank`。S9 写「rerank 层缺失」已过时。
- **页级聚合 + 邻居代表**按查询词字数密度选块（`_neighbor_representative_row`）：`matched = sum(len(term) for term in terms if term in body)`。这就是形状 IV 的机械定义——「长电科技」在来源清单/相关实体里出现次数最多。
- **V3 的 detail 通道已是 small-to-big 雏形**：召回看 snippet/excerpt（～160～200 字），送达看 `llm_evidence`（默认 1200 字/条，总预算 4800，上限 8000），且带「命中块 + 相邻块」。**可复用点**：换窗不必重切索引，只要换「代表块」或换「父窗」。缺口是相邻块被锁在**同一 section**——命中「原始资料链接」时邻居仍是清单第 5～7 条。
- **过采样已有**：`kb_index_hygiene.fetch_k` = `max(k×4, k+16)`，丢掉工件/折叠同族后再截 k。形状可复用到「丢掉结构段后再填满 k」，不要另写一套 fetch。

时间降档（已在本树 `kb_rag.py`，与 retrieval-tier spec 真值表一致）：

| 请求 mode | 剩余秒 | 实跑 |
|---|---|---|
| hybrid / dense / rerank | < 15 | bm25，`fallback_reason=remaining_budget` |
| 同上 | ≥ 15 | 保持请求档 |
| bm25 | 任意正数 | bm25，不标降档 |

热态 hybrid 4.25s / 5.10s；冷启动 ～39s 不在请求路径（worker prewarm）。成稿轮残值 median 13s（W4）——**默认路径上开 rerank 必须先过这把 15s 尺**，否则会在最紧的成稿轮被整段降成 BM25，或把残值压穿。

### 2.3 长电夹具 6 命中 × 索引采样

夹具：`intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json`（V3 冻结，不重跑 live RAG）。
采样：对 `chunks.jsonl` 按 `file_path` 过滤 6 页（2026-08-22，python 按行，未整读）。

| # | 页 | 冻结 best_chunk | 该块 `section` | 同页有没有正文 | V5 为何 fail-open |
|---|---|---|---|---|---|
| 1 | `wiki/sources/长电科技_最新逻辑跟踪.md`（28 块） | `::24` | `原始资料链接` | **有。** `::0` 一句话结论；`::3`～`::7` 五条最新市场逻辑；`::17`～`::19` 预期差 | 相邻 `::25` 仍是清单第 5～7 条。窗内无正文 |
| 2 | `wiki/entities/长电科技.md`（51 块） | `::38` | `IMA 最新逻辑跟踪 > …` | 有（一句话）。V5 已正文前置 | 不是本单对象 |
| 3 | `wiki/sources/长电科技 2025年度报告 baseline 2026-04-08.md`（**仅 4 块**） | `::2` | `Raw / Manifest Trace` | **页级几乎无正文。** `::0` 一句「本 source note 用于追踪…」；`::1` 分类元数据；`::3` 使用口径 | 相邻 `::1` 是 `annual_report_baseline / L2`，不是年报正文 |
| 4 | `wiki/entities/颀中科技.md`（28 块） | `::3` | `相关实体` | **有。** `::10` 一句话（债转股/TGV/显示驱动） | 相邻 `::2` 是 `相关概念` wikilink 堆 |
| 5 | `wiki/entities/华天科技.md`（40 块） | `::4` | `相关实体` | **有。** `::0` 公司简介；`::26` IMA 一句话 | 相邻 `::3` 是 `相关概念` 11 个 wikilink |
| 6 | `wiki/entities/莱宝高科.md`（24 块） | `::3` | `相关实体` | **有。** `::5` IMA 一句话（MED/玻璃基） | 相邻 `::2` 是 `相关概念` |

`::24` 正文采样（来源清单自成 chunk 的直接证据）：

```
section = 长电科技｜最新逻辑跟踪 > 原始资料链接
1. **长电科技2025年度、2026年第一季度业绩暨现金分红说明会记录**（2026-05-08）- 公司官方
   - https://www.cnfin.com/announ/detail/index.html?...
2. **长电科技2026年一季报** …
```

同一 heading 下列了 9 条带「长电科技」的来源，超过 336 token，被 `_split_long` 切成 `::24` / `::25` / `::26` 三块——**重叠的是清单，不是结论**。查询「长电科技怎么看」在这块上的词频高于 `::0` 那句只出现一次公司名的结论。

`相关实体` 块更极端：整段就是 `[[长电科技]] · [[通富微电]] · [[华天科技]]`（颀中 `::3`，106 字含前缀）。邻居扩展把「链过长电的页」拉进候选，代表块又按词密度选中这一行。

### 2.4 三种机制，不要压成「再过滤」

| 机制 | 命中 | 过滤救不了的原因 | 该换什么 |
|---|---|---|---|
| **同页错段** | #1 | 窗 = 清单 ± 清单 | 同页换代表块 / 父窗，或重切时不让清单单独成块 |
| **页本身是指针** | #3 | 4 块全是分类/路径/口径 | 换页，或 ingest 时别把 pointer page 当知识正文 |
| **邻页链接堆** | #4 #5 #6 | 窗 = 相关实体 ± 相关概念 | 排序：邻居折扣 / rerank / 相关实体不当代表块 |

R-17 原文「4 条零信息 excerpt 变正文段」若不加分层，会逼执行方用颀中的「一句话」去凑「变正文」——那是邻页正文，不是长电证据。本单把这句拆开，见 §7 / §8。

---

## 3. 路线 A：chunk 侧（换窗 / 换切）

原理：检索的原子是 chunk。原子是清单，后面所有 rerank 都在清单里打分。换切 = 改原子；换窗 = 原子暂时不改，送达时换一段。

### 3.1 方案展开

| 方案 | 做法 | 救 #1 | 救 #3 | 救 #4–6 | 延迟（请求路径） | 落点 |
|---|---|---|---|---|---|---|
| **A1. 消费侧按页重摘录（推荐先做）** | 命中后用 `file_path` 读 wiki 原文，按标题跳过结构小节，取「一句话 / 核心逻辑 / 预期差」等正文段当 `llm_evidence` | 是（`::0` 在同页） | 否（页无正文；应标 pointer 或丢弃该 hit） | 只把链接堆换成**邻页自己的**一句话，不主张长电相关性 | 读 6 个本地 md：量级 **1–20ms**（远低于 hybrid 5s） | **纯本仓** |
| **A2. 消费侧同页换块（索引内）** | 不读原文，按 `file_path` 扫该页其它 chunk（或 worker 回传 `page_to_rows`），跳过结构 section 再跑词密度 / 简单打分 | 是 | 否 | 同 A1 | 按行过滤 172MB 太贵（本次采样全库扫描 ～0.6s）。要做成 **page→chunk 侧索引** 或让 worker 带同页候选，否则不要在请求路径扫 jsonl | 本仓可做侧索引；更好是 KB query 多回同页块（跨仓小改、不重嵌） |
| **A3. 结构感知重切（物理）** | 构建期：`相关实体` / `相关概念` / `原始资料链接` / `Raw / Manifest Trace` 不单独成检索块（并入上一节，或标 `retrievable=false`） | 是（清单不再是 best_chunk） | 部分（pointer 整页可排除） | 是（链接堆不再是代表块） | 查询侧 **0**；构建侧重切 + **重嵌 14.6 万块**（小时级，一次性） | **跨仓** |
| **A4. 固定窗 + overlap（替代标题切）** | 整页按 336 token 滑窗，不管 heading | 不保证（清单仍可能单独成窗） | 否 | 不保证 | 查询 0；全量重嵌 | 跨仓。本库页面结构强，纯滑窗是退步 |
| **A5. 语义切分** | 用 embedding 找主题边界再切 | 不针对结构段 | 否 | 不针对 | 构建极贵；查询 0 | 跨仓。本失败形状是 heading 语义，不是主题漂移 |
| **A6. parent-child / small-to-big** | 小块召回、大块（整节或整页）送达。V3 `llm_evidence` + `ADJACENT_CHUNKS` 已是同节版 | 要父窗跨节才救 #1 | 否 | 要父窗跨到「一句话」才救 | 送达多读 1–3 块，**+10–50ms** 若块已在内存；若只扩 `ADJACENT_CHUNKS` 且仍限同节则 **0 收益** | 扩「跨节父窗」可本仓（重摘录）或 KB `_llm_evidence_text`（跨仓、不重嵌） |

### 3.2 对比与取舍

- **先 A1，不先 A3。** V4 先例写明：物理 `.rag_index` 由知识库仓 `rag_index.py build` 生成，本仓只改消费侧。A1 是同一纪律下的「换窗」：不改原子，改送达。长电 #1 的正文已经在同页 `::0`，不需要重嵌才能看见。
- **A4 / A5 不解决本案。** 失败原因是「结构小节被当成检索单元 + 词频选代表」，不是「窗太碎」或「主题切错」。语义切在通用 PDF 上有用，对本库高度模板化的实体页是杀鸡用牛刀。
- **A6 复用 V3，不要重造。** 把「相邻块」从「同 section ±1」改成「同页优先正文 section」，就等于 parent-child。实现可以是 A1（读原文）或 KB 改 `_neighbor_rows_for_evidence`（不重嵌）。不要新写一套 parent 索引格式，除非 A1 证伪。
- **#3 诚实残留。** baseline source note 不是年报。换窗不能发明年报数字。验收不得要求 #3 变成「营收 388 亿」——那是 ingest 单，不是检索单。

延迟账：A1 加在 `kb_search_hit_text` / retrieve 之后，**BM25 档也付得起**（不进 `_DENSE_MODES`）。这是它能当第一张派单的原因。

---

## 4. 路线 B：rerank 侧（换排序）

原理：召回（recall）负责「别漏」；重排（rerank）负责「别把错的排前面」。本库召回已经是 hybrid（两路 + RRF）。形状 IV 的邻页问题是**排序 + 邻居策略**，不是缺 RRF。

### 4.1 方案展开

| 方案 | 做法 | 救 #1 | 救 #3 | 救 #4–6 | 延迟（请求路径） | 落点 |
|---|---|---|---|---|---|---|
| **B1. 开已有 `mode=rerank`（cross-encoder）** | hybrid 候选页上用 `bge-reranker-v2-m3` 对 (query, title+best_chunk) 重打分。KB 已实现 | **弱。** 打分文本若仍是清单，模型看到的还是清单 | 弱（pointer 页短，可能仍排前） | **中。** 页级重排可能把「只有链接提到长电」的邻页压下去 | S9 预注册 p50 ≤500ms（模型已热）。冷加载 reranker **数秒～十秒+**，会砸 15s 档。必须走已有 prewarm，禁止请求路径首次 load | 本仓改请求 mode；模型在 KB `.rag_venv`。**剩余 <15s 必须仍是 BM25**（`rerank ∈ _DENSE_MODES`，已写死） |
| **B2. LLM listwise rerank** | 把 top-20 标题+摘要交给成稿模型重排 | 同 B1，看你塞什么摘要 | 同 B1 | 可能强 | **2–8s 量级**（一次额外模型调用）。成稿轮残值 median 13s，p95 必穿。默认路径否决 | 本仓可接，但只许 deep/full 且 remaining 远大于 15s。本单不推荐进默认 |
| **B3. 「再上一次 RRF」** | BM25+向量再融合一遍 | 否 | 否 | 否 | 0（已付过） | **禁止。** hybrid 已是 RRF。第三路没有新信号 |
| **B4. MMR 去冗** | 在已取 embedding 上做 Maximal Marginal Relevance：分数高且与已选页不相似才进 top-k | 否 | 否 | 部分（三页链接堆彼此很像，可能压成 1 页） | **<20ms**（已有向量点积） | 本仓或 KB。便宜，但是去冗不是选段 |
| **B5. 邻居 / 代表块策略（机械，推荐与 A1 一起估）** | ① `via_neighbor` 且 best section ∈ {相关实体, 相关概念} → 不当代表或降权；② 代表块禁止结构 section；③ 过采样后丢掉结构段再 `sanitize_hits` | 是（#1 换代表） | 可丢 pointer | 是（邻页不再用链接堆占槽） | **<10ms** | 本仓能做 ③（V4 `sanitize_hits` 形状）。①② 改 KB `_aggregate` / `_expand_neighbors` 更干净，属跨仓小改、**不重嵌** |

### 4.2 对比与取舍

- **Cross-encoder 是什么：** 双塔（BGE-m3）把 query 和文档**各自**编码再比向量，快、适合召回；交叉编码器把 `(query, doc)` **拼成一句**过分类头，慢、适合精排。面试常问 hybrid + rerank 为什么分成两段：召回要扫全库，精排只能打几十条。
- **B1 不能当 V5 的替身。** `_rerank` 用的是 `_page_text` = 标题 + **当前 best_chunk**。best_chunk 若是 `相关实体`，reranker 看见的就是那一行链接。先换代表（A1/B5）再 rerank，才有东西可排。
- **B2 默认否决。** 不是质量差，是预算形状：W4 成稿轮残值 median 13s，已低于 hybrid 门槛 15s。再塞一次 LLM，成稿轮先死。
- **B4 是配菜。** 液冷案同族挤占已由 V4 折叠；长电邻页是**不同 slug**，MMR 可能丢掉两个邻页，也可能丢掉一篇真相关的通富微电。要单独夹具，不能和「零信息变正文」绑死。
- **已有融合不要重做。** 若评测发现 BM25 噪声稀释 dense（KB `config.py` 注释：40 题 dense MRR 0.73 > hybrid 0.59），那是 **RRF 权重**（`HYBRID_DENSE_WEIGHT`）扫参，属 KB 仓评测单，不是本单。

延迟账（与 15s 档对齐，不另建梯子）：

| 动作 | 建议挂哪一档 | 理由 |
|---|---|---|
| A1 重摘录 / B5 丢结构段 | **所有档，含 BM25** | 毫秒级，不成稿轮威胁 |
| B1 cross-encoder | 仅 `remaining ≥ 15` 且请求已是 rerank/full；**不要**把默认 hybrid 自动升级成 rerank | 升级是改 `select_mode_for_remaining` 真值表，须另立台账行 + 延迟实测，本设计不改 15.0 |
| B2 LLM rerank | 默认禁止；deep 另议 | 秒级，压穿 median 13s |
| B4 MMR | 所有档 | 毫秒级；质量另验 |

---

## 5. 跨仓边界（两条都要有）

物理索引由知识库仓构建。V4 被硬约束「只改本仓」拦在消费侧（`kb_index_hygiene.py` 注释原文）。本单沿用，不偷偷改 `chunking.py`。

### 5.1 跨仓单（V9c，需用户裁决）

**何时才需要：** A1+B5 上线后，结构段仍大量以 best_chunk 身份进召回池（过采样填不满、或 pointer 页污染 top-k），且消费侧重摘录 p95 开始可见（例如每次读页 + 解析 >100ms，或 wiki 路径在 worker 对侧不可读）。

**改什么：**

| 仓 | 文件 | 行为 |
|---|---|---|
| knowledge-base-private | `skills/lib/rag/chunking.py` | 结构小节不单独 `retrievable`；或 parent-child 两级 id |
| 同上 | `skills/lib/rag/config.py` | `chunk_profile` 变更 → 旧索引 stale → 全机重建 |
| 同上 | 全量 `rag_index.py build` | 14.6 万块重嵌；`include_raw=false` 的干净索引与 `.rag_index_full` 可能都要 |
| finance-workspace-private | 无强制；消费侧 A1 可留作双保险 |

**影响面：** 索引指纹变了，所有机器 `fetch_rag_index` / 本地 build 要对齐，否则 freshness 守卫 fail-closed（本仓已有「索引不可用作证据」文案）。查询延迟不升。构建窗口按 KB 仓日常 build 估：**小时级 + 模型加载**。期间 8792 必须仍能用旧指纹或明确降级，不能半套新切。

**本设计不批准开工。** 用户点头后另开 KB 仓分支，finance 仓只跟消费契约。

### 5.2 纯本仓可达（V9a，默认推荐）

可行性（已核对，不是假设）：

- `WikiHit.file_path` 已是仓根相对路径（如 `wiki/sources/长电科技_最新逻辑跟踪.md`）。
- `retrieve()` 已有 `wiki_root` / `kb_root`。
- 12 个 agent 工具里**没有**「读页面全文」——那是给模型的缺口。消费侧 Python 读本地 md **不是**新工具，是 retrieve 后处理，与 V4/V5 同层。
- 页面体量：实体页 / 逻辑跟踪是 KB，不是 181MB jsonl。读 6 个文件 ≪ 一次 hybrid。
- 重摘录算法应 **复用标题切**（与 `chunking._split_sections` 同形，可抄规则勿抄包——KB 包不在 finance 依赖里），跳过 section 名黑名单：`原始资料链接` / `相关实体` / `相关概念` / `Raw / Manifest Trace` / `Source 分类` / `使用口径`。认不出则 fail-open 保持现状（沿 V5）。
- #3：重摘录后仍无正文 → 丢掉该 hit，让 `fetch_k` 过采样补位；禁止用路径行充数。

成本：实现量小（V5 邻域：`kb_search_hit_text` 或 retrieve 出口）；无重嵌；BM25 档也能跑。风险见 §9。

### 5.3 决策句（给用户）

- **现在不改知识库仓切块脚本。** 先做本仓 A1（+ 机械 B5 能做的那部分）。
- 物理重切列为 `R-20260822-03`，outcome 保持 pending，直到 A1 live 读数证明「同页换窗不够」或用户主动要统一切块契约。

---

## 6. 派单切分（必须能独立验收）

沿 R2「按层分开预注册」。两张实施单可以并行写测试，但 **live 探针不得共用一条「变好了」**。

```
V9a 本仓换窗（A1，可选本仓 B5③） ── 判别：同页 excerpt 是不是正文
V9b 排序（B5①② 与/或 开 rerank） ── 判别：top-k 里还是不是邻页链接堆
V9c 跨仓重切                         ── 用户裁决后才派；判别：结构 section 不再出现在 best_chunk 分布里
```

| | V9a | V9b |
|---|---|---|
| 改的变量 | 给定命中页，送哪一段 | 哪些页进 top-k / 何页当邻居 |
| 夹具 | 冻结 6 页**原文或同页 chunk 目录**（现 `v3-kbsearch-jcet-hits.json` 只有窗，**不够**，须加 page 侧车，不重跑 live RAG） | 冻结 hybrid 候选页列表 + `via_neighbor`；断言颀中/华天/莱宝不在 top-3 或 `via_neighbor` 被丢 |
| 绿了不主张 | 邻页离开 top-k；答案引用密度；送达字符数量级（那是 V3） | 长电逻辑跟踪窗变成一句话；噪声比（那是 V9a/V5） |
| 混杂禁句 | 「4 条都变正文所以检索好了」——#4–6 变颀中一句话算换窗成功、排序失败 | 「邻页没了所以选段好了」——#1 可能仍是清单 |

独立验收顺序建议：先 V9a（不依赖 KB 仓、预算最便宜、直接打 R-17 遗留的同页腿），V9b 可并行但 live 用不同探针用户或同题对照「页集合 vs 窗内容」两张表。

---

## 7. 验收判据草案

TDD 一律先红后绿；变异在已提交树上做；live 由验收方回填，执行方不得 `confirmed`。探针用户 `probe-v9a-<mmdd>` / `probe-v9b-<mmdd>`（字段是 `user` 不是 `user_id`）。

### 7.1 V9a · 本仓换窗（预留 `R-20260822-01`）

**TDD**

- 长电侧车夹具：6 页原文（或同页 chunk 列表）+ 冻结 query「长电科技怎么看」。
- #1 重摘录后头 80 字含「封测」或「一句话」类正文，且**不含** `cnfin.com` / `原始资料` 清单头。
- #4 #5 #6 重摘录后不再是「只含 `[[` 的 wikilink 堆」（独立字面检查，不复用实现分类器）。**不要求**这三段谈长电——谈颀中/华天/莱宝自己的业务也算本单换窗成功。
- #3 不得用路径行充正文：要么 drop，要么只剩「本 source note 用于追踪」且测试标明 pointer。
- 合成页（正文 + `## 原始资料链接`）选段落正文（沿 V5 合成钉，升级为「可跨节」）。

**变异**

- 重摘录恒等返回原 `llm_evidence` → #1 钉红。
- section 黑名单清空 → #1 钉红。

**live（部署后，与 V7 联动）**

- 同题钙钛矿对照：标签汤头保持 0（V5 不回退）。
- 长电或同形个股题：`detail_chars` **不作为本单主判据**（V3 已管数量级）。主判据是质检抽样：目标页 excerpt 为正文段。
- 新增只读字段建议（V7 邻域，可并进 V9a，不必等新传感器单）：`reexcerpted: bool` / `pointer_dropped: int`。没有字段时历史 run 报不可判，不报 0。

**预算**

- 夹具断言：重摘录路径不调用 dense/rerank worker。
- live：`effective_mode` 在 remaining<15s 时仍为 bm25；重摘录不得把单次 `kb_search` 墙钟抬到接近 15s（预注册：p95 增量 <100ms，超量先停开，改 A2 侧索引）。

### 7.2 V9b · 排序（预留 `R-20260822-02`）

**TDD**

- 冻结候选：含长电逻辑跟踪、长电实体、三邻页 `via_neighbor=true` + 结构 best_chunk。
- 机械策略：三邻页不进最终 k=6，或进了但 observation 不把链接堆当头（依赖 V9a 则本条标「联合」禁止单独绿）。
- 若本单选择开 `mode=rerank`：`remaining=4` / `11.955` **零次** reranker.score；`remaining=20` 才允许。变异：把 rerank 移出 `_DENSE_MODES` → 4s 夹具红（沿 retrieval-tier 变异闸形状）。

**live**

- 长电同题 top-k 页集合：颀中/华天/莱宝不再占 3/6。允许 0～1 个邻页若 rerank 认为正文真相关（须抽样，不得用「命中数=6」当成功）。
- `hit_count` 仍由过采样填满；主张的是**页身份**，不是条数。

**预算**

- 默认 episode 仍请求 `hybrid`。要把默认改成 rerank，必须附热态 p50/p95（对照 S9 ≤500ms）+ 成稿轮 `model_finish` 不降。做不到就保持 hybrid，只上 B5。
- 禁止 B2 进默认路径。

### 7.3 V9c · 跨仓重切（预留 `R-20260822-03`，默认不开工）

用户裁决后才写实施 spec。预注册形状：重建后的索引里，长电 6 页的 `best_chunk` 在 hybrid 重放中不再落在 `原始资料链接` / `相关实体` / `Raw / Manifest Trace`；`chunk_profile.chunking_version` 变更；旧指纹机器 fail-closed 而不是静默混用。

### 7.4 明确不算通过（两单共用）

- 再加一条 V5 过滤正则，「窗内仍无正文」却声称 4/4 变正文。
- 用 `delivered_chars` / `detail_chars` 上升冒充选段改善（R-12 预测③ / V3 测量缝在案）。
- 用颀中「一句话」满足「长电案零信息变正文」而不拆 #4–6。
- 新增 `select_mode_for_remaining` 之外的秒数门槛或字符阶梯。
- 改 `ASK_TOOL_BATCH_TIMEOUT` / 成稿 reserve / 生产 timeout（`R-20260816-07`）。
- 执行方自行把 `R-20260821-17` 标 confirmed。

---

## 8. 台账行（可逐字抄）

溯源：本文件；非标准四阶段分诊，`fix_type`/`verification_prediction` 可进 streak，不得当 PRIMARY 根因引用。`R-20260821-17` 保持 pending，本三行是它的下游，不代结。

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-20260822-01` | 本 spec §7.1 V9a 本仓换窗（形状 IV 同页错段 / 指针页） | `HARNESS_FIX` | 长电冻结夹具（页侧车，不重跑 live RAG）重放：#1 `长电科技_最新逻辑跟踪` 的 excerpt/llm_evidence 头为同页正文（一句话或市场逻辑），不再是 `原始资料链接` 清单；#3 baseline pointer 被丢弃或不再以 `raw/cninfo-baseline/` 路径行当头；#4–6 不再是纯 wikilink 堆（允许改为各该页自己的正文，不主张长电相关性）。TDD 先红后绿。变异：重摘录恒等 → #1 红。live：验收方探针抽样目标页为正文段；V7 `delivered_chars`/`detail_chars`/`hit_count` 只作联动读数，不得单独结案。p95 重摘录增量 <100ms，且 remaining<15s 时 `effective_mode` 仍为 bm25。 | 离线：新夹具 + `test_kb_search_coarse_pipe` / V5 过滤钉不回退。live：`probe-v9a-<mmdd>`，执行方不得 confirmed。与 V9b 分开验收。 | `pending` |
| `R-20260822-02` | 本 spec §7.2 V9b 排序（形状 IV 邻页链接堆占槽） | `HARNESS_FIX` | 长电同 query 的最终 top-k 中，`via_neighbor` 且代表段为「相关实体/相关概念」的颀中/华天/莱宝不再占 3 个槽（降至 ≤1 或 0）。不主张 #1 窗变成正文（那是 `-01`）。若开启 `mode=rerank`：remaining 4s 与 11.955s 零次 cross-encoder 调用，20s 才允许；不得新增第二套降档函数。变异：rerank 移出 `_DENSE_MODES` 或 4s 仍打 rerank → 红。 | 离线：冻结候选页列表。live：`probe-v9b-<mmdd>` 对页集合，与 `-01` 的窗内容分表记录。 | `pending` |
| `R-20260822-03` | 本 spec §5.1 / §7.3 物理重切（跨仓，需用户裁决） | `DATA_CONTRACT_FIX` | 用户批准并重建后：hybrid 重放长电 query，六页 best_chunk 的 `section` 不再落入 `原始资料链接` / `相关实体` / `Raw / Manifest Trace`；`chunk_profile` 变更导致旧索引 stale（fail-closed 提示重建，不静默混用）。未裁决前本行不得开工、不得用消费侧绿测冒充本行。 | KB 仓重建收据 + 本仓夹具重放。无用户裁决 → 保持 pending。 | `pending` |

---

## 9. 推荐、预算、风险

**推荐路线（一句）：** 先 V9a 本仓按 `file_path` 读页、跳过结构小节换窗（复用 V3「送达比召回大」和 V4「消费侧过滤」），机械丢掉 pointer；V9b 用邻居/代表块策略（必要时才开已有 rerank，且必须待在 15s 档内）；物理重切留待用户裁决。

**跨仓决策点（一句）：** 默认不改知识库仓 `chunking.py`、不重嵌 14.6 万块；A1 证伪或用户要统一切块契约再开 `R-20260822-03`。

**预算账（一句）：** 换窗走所有档（含 BM25），增量目标 <100ms；cross-encoder 不得在 remaining<15s 运行、不得把默认 hybrid 自动升档；LLM rerank 默认禁止——成稿轮残值 median 13s 是硬门，不是软提醒。

**最大风险（一句）：** 用邻页正文（颀中一句话）把「4 条变正文」做成假绿，把排序病报成选段已愈——所以 `-01` / `-02` 必须分表，禁止一条探针结两行。

### 9.1 成立条件

- 实施树从最新 `gitea/main` 另开，不在脏主树、不在本设计分支改生产代码。
- 解释器 `.venv-workbench/bin/python`。
- 变异前先 commit（W1：`git checkout --` 是未提交树的删除器）。
- pathspec 提交；禁止 `git add -A`。
- 不打 8792；live 只由验收方发探针。

### 9.2 不做什么

- 不改 V3 `KB_SEARCH_DETAIL_CHARS` / max_hits，不加第二套字符阶梯。
- 不改 V5 `filter_structural_noise` 的 fail-open 哲学去「滤成空再怪数据」。
- 不把 S9 当「还没做 rerank」的缺口清单。
- 不扫 `chunks.jsonl` 进请求路径。
- 不写 recon/probe 脚本留在仓里。

---

## 10. 术语（首次出现已在正文释义，这里给对照）

| 词 | 人话 |
|---|---|
| chunk | 索引里的一块文本，检索的最小硬币 |
| BM25 | 关键词打分：字出现得越多越靠前，短文档更占便宜 |
| 向量 / dense / BGE-m3 | 把句子变成数字，意思近的靠在一起；不一定要字面相同 |
| RRF | 两路排名各投一票再合成，避免只听关键词或只听向量 |
| rerank / cross-encoder | 对已经召回的几十条，把问句和段落拼在一起重新打分 |
| MMR | 既要相关，又不要 top-k 全是近亲 |
| parent-child / small-to-big | 用小块找到页，用大块（整节/整页）回答 |
| remaining_budget | 这批工具还剩多少墙钟；<15s 就改步行（BM25） |
