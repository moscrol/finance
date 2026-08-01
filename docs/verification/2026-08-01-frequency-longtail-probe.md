# 探针结论：高频/长尾信号能不能进暴露选择（2026-08-01）

**问题**（承 `docs/handoffs/2026-08-01b-claude-session-continuation.md` §3）：
knevo 能识别高频/长尾，我们有 `mention_frequency.json` 和 `evidence_index`，
能不能 join 进暴露选择、把固态电池 86 家候选分层？

**一句话结论**：`mention_frequency` **不可用**（题材粒度 + 2.6% 覆盖 + 固态电池根本不在表里）；
`evidence_index` 的 concept join **可用且已验证**（90% 命中），但它只能干一件事——
**切开 strength/confidence 排完后残余的那一组并列**。值得做，作用域比「高频/长尾分层」小得多。

---

## 1. mention_frequency.json —— 否决

| 项 | 实测 |
|---|---|
| schema | `{anchor_date:"2026-07-29", window:"7d vs prev 7d", n_sources:4161, themes:{...}}` |
| themes | **dict，115 个**，值 = `{total, last7, prev7, trend, recent_days}` |
| 粒度 | **题材级，没有公司维度** |
| 固态电池 | **不在 115 个题材里**（只有 `SST固态变压器`/`固态变压器SST`，`含"电池"的键 0 个`）|
| 与 entity_exposures 概念的交集 | **70 / 2689 = 2.6%** |
| 判别力 | `last7` 中位数 = 0，**74/115 个题材 last7==0**；trend 一半是 `→` |
| 谁消费 | 知识库仓 `scripts/build_theme_vertical_slice_queue.py`（题材工作队列）；**工作台 runtime `intelligence/` 零消费**（唯一命中是 `path_registry.json` 里的一个 outputs 描述字符串，不是读取）|

三条否决理由，任意一条单独成立：

1. **粒度不对**。暴露选择要在**一个题材内部**排 86 家公司；mention_frequency 是**题材之间**的热度对比。它连输入接口都对不上，不是 join 不上的问题。
2. **覆盖不够**。2.6%。公司数最多的 25 个概念里 16 个查无此题材（化工 166 家、AI算力 162 家、医药生物 120 家全缺）。
3. **主战场直接 miss**。固态电池就是那个 86 家的题材，它不在表里。

> ⚠️ 上一段 handoff 记的「今天做暴露选择器时没用它 → 又一次信息没送到」——**这条要撤回**。
> 不是没送到，是**送到也没用**：粒度错、覆盖 2.6%、目标题材缺失。
> 这属于 [[info-not-delivered-bug-pattern]] 的反面样本：先证明那份信息真能回答问题，再说它「没送到」。

**唯一可复用的东西**：`build_theme_vertical_slice_queue.py:505` 用
`route_term(raw, valid_concepts, aliases)` 把 mention_frequency 的原始题材名路由到合法概念上。
这套 alias 路由层将来做任何跨库 join 都要用，别重造。

---

## 2. evidence_index join —— 可行，已验证

### 2.1 上次为什么 0 家（根因）

`items` 23904 条，`target_type` 分布：**entity 21145 / concept 2759**。
公司级证据的字段布局是：

```json
{"target":"宁德时代", "target_type":"entity", "concept":"固态电池",
 "evidence":"...", "source":"[[...]]", "confidence":"medium"}
```

**公司在 `target`，概念在 `concept`**。上次「按 concept 含『固态』筛公司」得 0，
是因为拿 `concept` 去比对了公司名那一侧。字段没对上，不是数据没有。

### 2.2 join 命中率（86 家候选，实测）

| 口径 | 命中 |
|---|---|
| A 严格 `concept == '固态电池'` | **77 / 86（90%）** |
| B 族 `concept ∈ {固态电池, 全固态电池, 半固态电池, 固态电解质}` | 77 / 86（90%）|
| C 跨概念总覆盖（这家公司在全库被提及多少次）| 86 / 86（100%）|

B 相对 A 零增量——同义概念在 entity_exposures 侧已经被归一到「固态电池」了，**别加同义词展开**，白花钱。

### 2.3 C（跨概念总覆盖）不能用作相关性

分位数：`min=1 p25=9 p50=16 p75=20 max=42`，判别力最强（12 家里 10 个唯一值）。
但 Top 是 `宁德时代:42 中材科技:39 天赐材料:36 比亚迪:33`——
**它测的是「这家公司在我们库里有多红」，不是「它跟固态电池多相关」**。
中材科技的 39 条绝大多数是玻纤/风电。用它排序＝按知名度排序＝系统性偏向大市值。

**选 A，不选 C。** 这是本探针最容易踩反的一处。

---

## 3. 它到底能干什么活（作用域，比预想小）

先看**当前已上线**的确定性排序还剩多少并列——这才是 coverage 唯一的施力点：

```
score=20 core     high     :  8 家 (累计  8)   ← 全进，无争议
score=20 core     medium   : 12 家 (累计 20)   ← 12 家争第 9–12 席，组内纯靠中文字典序
score=20 core     low      :  1 家
score=20 related  high     : 16 家 (累计 37)   ← 宁德时代在这里 (#29)
...
```

**残余静默截断在这里**：core+high 只有 8 家填不满 12 席，第 9–12 席由 12 家 core+medium 争，
`(-score, strength, confidence, company)` 走到最后一维，**又是字典序**。实测结果：

| # | 公司 | 标注 | A严格覆盖 |
|---|---|---|---|
| 12 | 先导智能 | core/medium | **6** ← 覆盖最高，侥幸进了 |
| 15 | 国轩高科 | core/medium | 2 |
| **19** | **当升科技** | core/medium | 2 |
| **20** | **赣锋锂业** | core/medium | **3** ← 覆盖第 3 高，被字典序切掉 |

**加 A 严格覆盖后**，这 12 家的取值是 `[6,5,4,3,2,2,2,2,2,1,1,1]`，前 4 =
`先导智能(6) 上海洗霸(4) 赣锋锂业(3) 东方锆业(2)`。
赣锋锂业进来了；判别力 5/12 个唯一值，**能定 3 席，第 4 席仍落在 6 家并列的 2 上**——
比字典序好，但不是全解。

### 三个它干不了的活（写清楚免得下次重复论证）

1. **跨 strength 档救不回来**。宁德时代 `related/high` 在 #29，任何 tiebreaker 都不会把它拉进前 12——
   它是**标注问题**（宁德时代对固态电池被标成 related），不是排序问题。混淆这两者会导致改错层。
2. **不是「高频/长尾分层」**。A 严格的取值域只有 `[0,6]`，77 家挤在 1–3。
   这是个 tiebreaker，不是一个能把 86 家分成高频层/长尾层的分布。想要真分层，数据不支持。
3. **线上主路径已经不靠它**。`mode=llm` 时是模型从 60 家候选按意图挑 12 家，
   确定性排序只在 **fail-closed 回退**时生效。所以 coverage 的收益 = 回退路径质量 + 86→60 候选池切口质量。

---

## 4. 建议（三选一，按性价比）

| 方案 | 改动 | 收益 | 风险 |
|---|---|---|---|
| **① 只读 telemetry**（建议先做） | `_exposure_ref` 加 `evidence_count` 字段，进 trace 的 `graph_exposure`，**不进排序不进正文** | 待办 I 从「人看 trace」变成有量化维度可比；积累几天真实分布再决定要不要进排序 | 近零。不改行为 |
| ② 进确定性排序 | 排序键 `(-score, strength, confidence, -evidence_count, company)` | 回退路径 + 候选池切口变好；赣锋锂业类进正文 | 中。会改答案。需按 §7.4 做突变验证（摘掉 evidence_count 必须变红）|
| ③ 进选择器 prompt | 候选行附 `evidence_count` 给模型 | 模型多一个判别维度 | 中高。prompt 变了要重测 `hallucinated=0`；且模型可能把它当权威分 |

**推荐 ① → 观察 → 再定 ②**。理由是十原则 9.5 的同一条：现在没有证据说明模型选得不好
（待办 I 还没验），先把可观测性补上，不要在没有判据的时候改行为。
②的成本不高，但它会改用户看到的答案，而**我们现在还没有「选得对不对」的判据**——先造判据。

**成本**：`evidence_index` 已在 `_RELATION_CACHE` 里（带 mtime+size 失效，`knowledge.py:20`），
加一个 `Counter` 预聚合缓存即可，单次问答一次 23904 条遍历。**不烧 LLM 配额，不加延迟量级。**

**分层归属**：`evidence_count` 是「候选装不下配额时留谁」，属**通用层**（宽容），
不判断某家公司对不对。符合第一原则，不碰领域门禁。

---

## 5. 对照 knevo（探针第 6 问）

用户原话是「它的架构能识别高频和长尾信息」。查 `knevo-harness-reverse-engineering.md`：

- knevo 的记忆检索是**纯关键词匹配**（tag + content），`hitCount` / `core` / `winRate` **不回接排序**（A1 实测已证伪早期推断，见该文 §A1）。
- 它的 `hitCount` 最高 84，但**不由对话实时递增**，推测由 `recall_short_term` 异步更新。

**结论：knevo 没有「高频/长尾识别层」这个东西。** 那是我们从它的 UI 展示 hitCount 反推出来的印象。
所以这里**不存在需要追平的差距**——我们的 A 严格 coverage 反而是它没有的（我们有 concept×entity 的二维证据账本，它只有一维记忆条目）。

⚠️ 这是本项目第三次「推断被当成发现」。前两次是 A1 本身和密封夹具 `9053b0c4`。

---

## 6. 顺手核对的两件事

### 6.1 8792 的 `source_revision` —— 不是 751ef706，但**代码没问题**

```
/api/health  source_revision = 0430d54471cf...  source_dirty = true
             code_root       = /Users/a77/finance-workspace-private
进程 cwd      = /Users/a77/.finance-runtime/finance-workspace-751ef706   ← 真正决定加载哪份代码
软链          = /Users/a77/.finance-runtime/finance-workspace-751ef706
RAG env 数    = 4 ✅
```

`0430d544` + dirty 正是**数据仓** `/Users/a77/finance-workspace-private` 的 HEAD
（分支 `fix/degrade-disclosure`，有未提交改动）。所以：

> **health 的 `source_revision`/`code_root` 报的是数据根，不是运行中的代码版本。**
> 上一段 handoff 观测到的「软链 751ef706 但 health 报 0430d544」**不是不一致**，
> 是这个字段本身就在报另一个东西。判代码版本只能看 `lsof -a -p <pid> -d cwd`。

这本身是个「留证说假话」形状的字段命名问题（和 `751ef706` 修的那一刀同族），
但它在通用层、只影响运维判断，**不阻塞任何事**，记下不改。

### 6.2 fact 表最新日期 —— 仍停在 2026-07-30

```
fact_market_daily          max=2026-07-30   389 行
fact_sector_daily          max=2026-07-30   96,208
fact_stock_daily           max=2026-07-30   1,965,664
fact_sector_stock_daily    max=2026-07-30   10,739,766
fact_stock_high_daily      max=2026-07-30   232,147
fact_theme_limit_heat_daily max=2026-07-30  41,516
fact_limit_advance_daily   max=2026-07-30   4,547
```

7 张表整齐停在 07-30，**7-31 一天都没补**（今天 08-01）。与待办 K 描述的事故形状一致。
补 7-31 需要你侧 Chrome 登录 fupanhui，agent 不能代登。

---

## 7. 复现命令

```bash
# join 命中率
python - <<'EOF'
import json, collections
ev=json.load(open('/Users/a77/knowledge-base-private/wiki/relations/evidence_index.json'))['items']
ent=[i for i in ev if i.get('target_type')=='entity']
strict=collections.Counter(i['target'] for i in ent if i.get('concept')=='固态电池')
print(len(strict), strict.most_common(10))
EOF

# 残余并列分组
cd /Users/a77/finance-workspace-runtime
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
from intelligence.adapters.knowledge import KnowledgeAdapter, _exposure_rank_key
import collections
items=KnowledgeAdapter().get_exposure_matches('固态电池', limit=1000)['items']
g=collections.OrderedDict()
for it in sorted(items,key=_exposure_rank_key): g.setdefault(_exposure_rank_key(it)[:-1],[]).append(it['company'])
for k,v in g.items(): print(k, len(v))
"
```

**本探针零 LLM 消耗**（全部离线复现台，§10 配额未动）。
