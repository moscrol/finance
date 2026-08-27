# V9b：kb_search 消费侧 top-k 槽位重排（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-22-kb-chunk-rerank-design.md` §4.1 B5 / §7.2
> 台账：`R-20260822-02`（pending；live 由验收方回填，本单不得 confirmed）
> 上游：`R-20260822-01`（窗内容，已分表；本单不主张 #1 换正文）
> 分支：`feat/v9b-topk-rerank`
> **验收面**：哪些页进最终 k。不得从本文件推出窗内容变化（V9a）或送达字符数量级（V3）。

## 0. 一句话

`retrieve()` 在 V9a `reexcerpt_hits` 之后、`sanitize_hits` 截 k 之前，把
`via_neighbor` 且代表段为「相关实体 / 相关概念」的页排到队尾。过采样够时，
这些页被截 k 挤出槽位。纯启发式，不调 cross-encoder。

人话：换窗只改了「翻到哪一段」，没改「哪几页坐在前排」。邻页因为链接里写了
长电而进来，窗已经是它们自己的一句话，但仍占 3 个槽。本单按「怎么进来的」
往后排，不改窗里写了什么。

## 1. 方案选型

**启发式 B5，不开 `mode=rerank`。**

| 方案 | 做什么 | 救不救本形状 | 预算 | 为何不选 / 选 |
|---|---|---|---|---|
| **B5 机械排后（本单）** | via_neighbor ∧ 代表段 ∈ {相关实体, 相关概念} → 队尾，sanitize 截 k | **对。** 台账行就是这个谓词 | ~0.002ms / 10 候选 | **选。** BM25 档也付得起；不进 `_DENSE_MODES`；不改 15.0 真值表 |
| B1 开已有 cross-encoder（`bge-reranker-v2-m3`） | 对 (query, title+best_chunk) 重打分 | **弱。** V9a 后 best 窗已是邻页自己的「一句话」，模型可能把封测同行判成相关，槽位仍在 | S9 热态 p50 预注册 ≤500ms；本机历史 CPU p50=62.5s，冷加载数秒 | **不选。** 默认 episode 仍是 hybrid；升 rerank 必须另附热态 p50/p95 + 成稿轮 `model_finish` 不降。做不到就保持 hybrid，只上 B5（spec §7.2 原文） |
| B2 LLM listwise | 成稿模型重排 top-20 | 可能强 | 2–8s，压穿成稿残值 median 13s | **禁止进默认** |

**原理（可迁移）：** 召回负责「别漏」，精排负责「别把错的排前面」。
Hybrid = BM25 + 稠密向量 + RRF，已经是两路融合。本形状不是缺 RRF，是
**邻居扩展策略把链接节当代表块**。机械信号（via_neighbor + section）比
再打一次语义分更对准病因。

面试常问「为什么 hybrid 还要 rerank」：双塔快、扫全库；交叉编码器把
`(query, doc)` 拼成一句过分类头，慢、只打几十条。本单的教训是：**精排
看见的文本若已经是换过的正文，它解决不了「页不该进槽」**——那是分配问题，
不是相关性打分问题。这个在任何「图扩展 / 邻页召回」的 RAG 里都能用。

替代方案对比：若以后要开 B1，必须挂进既有 `_DENSE_MODES`（rerank 已在集合里），
remaining 4s / 11.955s 零次 `score`、20s 才允许；禁止第二套降档函数，禁止改
`select_mode_for_remaining` 与 15.0。

## 2. 判别规则

| 命中 | 机制 | 本单主张 | 不主张 |
|---|---|---|---|
| #1 长电逻辑跟踪 | 同页错段，via_neighbor=false | **仍占槽**（窗内容是 `-01`） | #1 头变成「封测」 |
| #2 长电实体 | 已是正文 | 仍占槽 | — |
| #3 baseline pointer | V9a drop | 不进入本单 top-k（V9a 已丢） | — |
| #4 颀中 / #5 华天 / #6 莱宝 | via_neighbor + 相关实体/相关概念 | **不再占 3 槽（≤1 或 0）** | 它们的窗是不是正文（V9a 已换） |
| 通富 / 先进封装 / 封测 | 过采样补位，非结构代表 | 填进被挤出的槽 | 长电相关性 |
| 晶方科技 | via_neighbor 但 section=公司简介 | **不降权**（真语义邻页） | 一定进最终 k（过采样比它更前的正文页可以把它截掉） |

独立判据（测试内字面检查，不复用 `is_structural_neighbor_rep`）：
stem ∈ {颀中科技, 华天科技, 莱宝高科} ∧ `via_neighbor` ∧ section crumb ∈ {相关实体, 相关概念}。

## 3. TDD 红绿

文件：`intelligence/tests/test_kb_topk_rerank.py`。
夹具：`intelligence/tests/fixtures/v9b-jcet-candidates.json`（10 条过采样候选）
+ 页侧车 `v9a-jcet-pages/` + `v9b-jcet-pages/`。不扫 181MB `chunks.jsonl`。
解释器 `.venv-workbench`，cwd 本 worktree。

红（实现前，基线 `d5cb4e2f`，`allocate_topk_slots` 恒等桩）：

```
7 failed, 18 passed
test_jcet_neighbors_no_longer_take_three_slots
test_true_semantic_neighbor_stays
test_oversample_then_cut_fills_k
test_identity_sorter_is_not_the_default
test_empty_neighbor_gate_is_not_the_default
test_remaining_tight_never_calls_cross_encoder
test_retrieve_pipeline_squeezes_neighbors_after_reexcerpt
```

收据：`~/.finance-runtime/test-receipts/20260822T042901Z-d5cb4e2f.json`（dirty）。

恒等下仍绿的钉锁的是「别改窗 / 别误杀无 via_neighbor 的相关实体页 /
别另建降档 / 遥测缺字段=None」——它们不是「必须挤槽」。

绿（实现后）：同文件 13 passed；连同 V9a / V5 / V3 / V4 / retrieval-tier
`test_kb_window_reexcerpt.py` + `test_kb_selection_noise_filter.py` +
`test_kb_search_coarse_pipe.py` + `test_kb_index_hygiene.py` +
`test_retrieval_tier_by_remaining_budget.py` 零回退（51 passed @
`20260822T042936Z-d5cb4e2f`，当时 dirty）。

最终全量收据见文末——**必须打在提交后的 HEAD**，中间 revision 的绿不采信。

## 4. 变异击杀

映射（spec 写的是 rerank 门控；本单无模型，给等价形状）：

| spec 原文 | 本单映射 | 为什么等价 |
|---|---|---|
| ① 把 rerank 移出 `_DENSE_MODES` | `allocate_topk_slots` 恒等返回 | 排序能力停摆，三邻页仍占 3 槽 |
| ② remaining=4s 仍打 rerank | `NEIGHBOR_REP_SECTIONS = frozenset()` | 门控失效，结构代表不再被识别 |

每条打完立即还原。击杀 **2/2**：

1. 恒等桩 → `test_identity_sorter_*` + `test_jcet_neighbors_*` 两钉红。
   收据 `~/.finance-runtime/test-receipts/20260822T042954Z-d5cb4e2f.json`（dirty）。
2. 门控集合清空 → `test_empty_neighbor_gate_*` + `test_jcet_neighbors_*` 两钉红
   （台账行独立字面检查，不复用实现谓词）。
   收据 `~/.finance-runtime/test-receipts/20260822T043037Z-d5cb4e2f.json`（dirty）。

还原后 13 + V9a 12 = 25 passed（`20260822T043048Z-d5cb4e2f`）。

未做「把 rerank 移出 `_DENSE_MODES`」的字面变异：本单没有新增 rerank 调用，
那条变异打在既有 `test_retrieval_tier_by_remaining_budget` 上会红，但那是
**既有门禁的回归**，不是本单排序器的击杀。本单声称的 2 条是上表映射。

## 5. 预算读数

本机（worktree，不跑 live RAG / 不打 8792）：

| 动作 | 墙钟 |
|---|---|
| `allocate_topk_slots` 10 候选 | **0.0020ms**（200 次平均） |
| spec B5 预注册 | <10ms |

与 `_DENSE_MODES` 的关系：启发式**不进**稠密档。remaining=4s / 11.955s
时 `effective_mode` 仍为 bm25，worker 命令无 `rerank`，零次模型 `score`；
20s 仍请求 hybrid，不升 rerank。`select_mode_for_remaining` 真值表与 15.0
零改动，本模块源码不含该函数名 / `HYBRID_MIN_REMAINING` / `15.0`。

默认 episode 仍请求 hybrid。本单**不**把默认改成 rerank。

## 6. 遥测

新字段 `structural_neighbor_demoted: int | None`：

- 写方：`kb_rag.retrieve` → `WikiRagTelemetry` → `AgentEvidence` →
  `kb_delivery_telemetry`（有值才落盘）。
- 读方：`scripts/audit_ceiling_sensors.inspect_shape_iii`
  （与 V9a `pointer_dropped` / `reexcerpted` 同口径）。
- 历史 run 缺字段 → `None`，**不报 0、不翻 unjudgeable**。

## 7. 诚实边界

1. **不主张窗内容。** #1 是否「封测」正文是 `R-20260822-01`，分表记录。
2. **不主张答案质量 / 引用密度。** 槽里换成通富/先进封装，不保证成稿引用它们。
3. **依赖 `via_neighbor` 戳。** BM25 直接命中「相关实体」节、未打邻居标的页
   **不挤**——这是与 V9a `test_pointer_drop_lets_oversample_fill_k`（section=
   相关实体、无 via_neighbor）共存的刻意边界。若 live 三邻页其实是直接命中，
   本单离线绿、live 槽位可能不动。须验收方探针看页身份，不得用 hit_count=6
   当成功。
4. **过采样不够时允许 ≤1 个结构邻页留在 k 内**（排后但截 k 仍轮到它）。
   台账允许 ≤1 或 0。夹具 10 候选时为 0。
5. **via_neighbor ∧ 正文代表段（如公司简介）不降权。** 晶方这类真语义邻页
   可以留；过采样里更靠前的正文页也可以把它截出最终 k——「不降权」≠「保送」。
6. **不开 B1/B2。** 无热态 rerank p50/p95，不成稿轮对照。
7. **不改 `_repair` / V5 fail-open / V9a `reexcerpt_hits` / timeout / 字符梯 /
   `KB_SEARCH_DETAIL_CHARS`。**
8. live 由验收方用 `probe-v9b-<mmdd>` 对页集合回填，本行保持 `pending`。
   不代结 `R-20260822-01` / `R-20260821-17` / 任何其他行。

## 8. 不做什么

- 不改 `select_mode_for_remaining` 真值表与 15.0。
- 不把默认 hybrid 升成 rerank。
- 不扫 `chunks.jsonl`，不把 181MB 索引接进测试。
- 不打 8792，不跑 live 探针，不把任何台账行标 confirmed。
- 不开 V9c 跨仓重切。
- 不在主检出树 `feat/reading-rules-baseline-batch1` 工作或提交。

## 9. 接线

```
worker 过采样 (fetch_k)
  → V9a reexcerpt_hits（换窗 / drop pointer）
  → V9b allocate_topk_slots（结构邻页排后）
  → sanitize_hits(..., k)（工件排除 + 同族折叠 + 截 k）
```

## 10. live 回填（2026-08-22 13:30，验收方）

台账 `R-20260822-02` 的 live 腿。生产身份：#338/#339/#340 合入后部署，8792 health
`loaded_tree_fingerprint`==`repo_tree_fingerprint`==`fb7a0d5d…`（639 模块），ready 全绿，
部署账本 `switch` 行已补记（脚本等待循环中退，账本手工按脚本原参数补，无杂散文件）。

两条腿：

1. **episode 探针** `probe-v9b-0822` / `run_20260822_132015_150481`（同题「长电科技怎么看」）：
   LLM 计划本轮只走 `finance_query`（10 条行情证据），未调 `kb_search`——episode 层工具选择
   随机，不构成检索层证据，只留档。
2. **检索层重放**（部署树 `kb_rag.retrieve` × 生产索引，冻结 query「长电科技怎么看」，k=6，
   默认 hybrid，与 R-16 live 腿同法）：

| 判据 | 读数 | 结果 |
|---|---|---|
| via_neighbor ∧ 结构代表段（相关实体/相关概念）∧ 颀中/华天/莱宝 占槽数 | **0**（台账允许 ≤1 或 0） | ✅ |
| V9b 机制 live 开火 | `structural_neighbor_demoted=1`（一个 via_neighbor 结构代表候选被排后挤出） | ✅ |
| V9a 联动 | `pointer_dropped=1`；最终 6 命中 excerpt 全为正文段（#1 头=「长电科技作为国内封测龙头…」） | ✅ |

**入径注记（按 §7 诚实边界 #3 预登记的情形如实记录）**：本轮颀中/华天/莱宝以
**直接命中**身份进榜（`via_neighbor=False`，命中块仍是「相关实体」节、被 V9a 换成
各页正文），不是设计捕获时的邻页扩展入径——V9a 丢弃 baseline 指针页后过采样回补
改变了候选组成。边界 #3 预判「若 live 三邻页其实是直接命中，本单离线绿、live 槽位
可能不动」，实测三页确实留在 #3–#5 槽位；但判据度量的对象（via_neighbor 结构代表
占槽）为 0，且设计针对的失败形状（结构链接堆占槽挤掉正文）live 不存在：6 槽全部
正文窗。离线冻结夹具腿（10 候选 3→0）+ live 机制开火（demoted=1）两腿成立，
台账行翻 `confirmed`。
