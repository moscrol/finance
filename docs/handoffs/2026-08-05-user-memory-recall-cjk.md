# ⛔ 本 handoff 已作废（2026-08-05，修错了层）

> **不要按本文档施工。** 它把问题当成「怎么从原始字符串猜出实体」，
> 而**实体在上游已经被 LLM 抽好了，只是没往下传**。
>
> 事实：
> - `user_memory.memory_block_for_query` / `relevant_memory_records` **本来就有
>   `theme` / `entity` 参数**，`_query_terms` 会把它们直接当 term 追加——传了就绕开分词。
> - `ask.py:3733` **已经正确传了**：`memory_block_for_query(options.query, theme, anchored_name, ...)`
> - `ask.py:621` 与 `episode_tools.memory_lookup_runner` **没传**，只给了原始 query。
> - `ResearchTaskContract`（`research_contract.py:668` 起）有 `subject` / `subject_kind`，
>   而 `episode_tools` 已在用 `context.contract.*`——**抽好的实体就在手边**。
>
> **正确的修法**是把上游已有的结构化意图接下去（约三行），不是造分词器：
>
> ```python
> recall = user_memory.relevant_memory_records(
>     query,
>     entity=context.contract.subject,   # 已在手里，不必从字符串猜
>     user=memory_user,
>     users_root=memory_users_root,
> )
> ```
>
> 下文的三条路线（双向包含 / N-gram / jieba）**全部是在错误的层上做取舍**，
> 保留仅供追溯——若接完结构化意图后仍有残留漏召回（例如题材没进 `subject` 的情形），
> 再回来评估，届时它是个小得多的问题，不是"工具不工作"。
>
> 接替文档：`docs/handoffs/2026-08-05b-user-memory-pass-structured-intent.md`

---

# （已作废）修 user_memory 召回的中文连写失效

> 承接 `3cde899a`（memory_lookup 工具已交付）。工具装好了，但**多数自然中文提问召回为空**。
> 这不是新引入的缺陷，planner 侧注入（`ask.py:621`/`:3733`）一直有；memory_lookup 与它
> 共用同一份召回，所以**一次修复同时救两个消费方**。

## 0. 症状（实测，可复现）

```python
from intelligence.services.user_memory import _query_terms
_query_terms("光刻胶怎么看")        # -> ['光刻胶怎么看']       ← 一个 term
_query_terms("光刻胶，现在怎么看")   # -> ['光刻胶', '现在怎么看'] ← 两个
_query_terms("PI膜产能")           # -> ['PI膜产能']
```

用户自然提问基本不带标点，于是查询词变成一整句，**匹配不到任何标签**。

## 1. 先搞清机制——它不是分词问题，是**方向**问题

`select_relevant` 的打分是**子串包含**，不是词元相等：

```python
for term in terms:
    nt = _norm(term)
    if nt in tag_hay:   s += 4     # 标签命中
    if nt in text_hay:  s += 2     # 正文命中
```

所以失败是**单向**的：

| 情形 | 结果 |
|---|---|
| term=`光刻胶怎么看`，tag=`光刻胶` | ❌ 长 term 不是短 tag 的子串 |
| term=`光刻胶`，memo=`光刻胶这轮我看好…` | ✅ 短 term 是长正文的子串 |

**结论：不一定需要分词。让包含判断变成双向，就能覆盖主要场景。**

⚠️ **这一点决定了方案选型，别一上来就装分词库。**

## 2. 仓内已有先例——不要另起炉灶

`experience_cards.select_relevant_cards` 面对**同一个问题**，用的是两个手段（都没上分词）：

```python
if q and (q in hay or hay in q):      # ← 整句双向包含
    score += 6
...
intent_terms = _query_intent_terms(query)   # ← 手工意图词表：关键词 → 展开概念
```

`_query_intent_terms` 是为经验卡的「行为概念」定制的，**不能直接复用**到 user_memory
（后者匹配的是 themes/stocks 标签）。但**双向包含那一招可以直接借**。

**动手前先读这两段代码**，理解为什么当时选了这条路。

## 3. 三条候选路线（必须对比后再选，并在报告里写明取舍）

| | 方案 | 改动量 | 新依赖 | 主要风险 |
|---|---|---|---|---|
| **A** | **双向包含**：`nt in tag_hay` 之外再判 `tag in nt` | 最小（打分函数几行） | 无 | **短标签假阳性**：2 字标签会命中大量长句 |
| **B** | **N-gram**：把 query 切成 2/3/4 字滑窗当候选 term | 中 | 无 | 召回噪声大、打分需重新标定 |
| **C** | **真分词**（jieba 等） | 中 | **有**（本仓当前无任何分词依赖，已 grep 确认） | 引入依赖 + 词典对金融新词（题材名、简称）覆盖差 |

**我的倾向是 A**，理由是改动最小、无依赖、仓内有先例。但**不要因为我倾向就跳过对比**——
你要实测三者在同一组查询上的差异再定。

**A 必须解决的问题**：短标签假阳性。至少要有长度下限（比如 tag 长度 ≥2 或 ≥3 才做反向
包含），并且**给出你选这个阈值的依据**，不能拍脑袋。

## 4. 这是相关性改动，必须有前后对照

改召回排序**不能只靠单测通过**——单测只证明代码按你想的跑，不证明召回变好了。

**要求建一个小评测集**（10-20 条），每条形如：

```
query（自然中文，不带标点） | 期望召回的标签/记录特征 | 不该召回的
```

给出**改前 / 改后**的命中数与假阳性数对照表。允许结论是「A 方案假阳性太多，选了 B」——
**反向结论算有效产出**。

⚠️ **评测集用构造 fixture，不要用用户真实台账。** 记忆台账含用户私有判断，
不读、不入断言、不进提交物。参考 `3cde899a` 里新测试的 `users_root=` 临时目录写法。

## 5. 范围

**做**：`user_memory.select_relevant` / `_query_terms` 的召回改进 + 评测集 + 回归测试。

**不做**：
- ❌ 不动 `experience_cards.select_relevant_cards`。它已有自己的缓解手段，且匹配对象
  不同（行为概念 vs 题材标签）。**顺手统一两套实现属于越界**——真要统一是另一轮。
- ❌ 不改 `memory_lookup` 的工具契约、evidence_tier、白名单相关的任何东西
  （`3cde899a` 刚验收过，别动）。
- ❌ 不加分词依赖，除非你的对照数据能证明 A 和 B 都不够用。

## 6. 验收

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_user_memory.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_experience_cards.py \
  intelligence/tests/test_ask.py
.venv-workbench/bin/python -m ruff check intelligence/
```

**先跑一次记下改动前基线**，改完逐项对比。

**通过标准**：

- 上述文件零新红；`test_experience_cards.py` 尤其要绿（证明没波及隔壁那套）
- 新增测试至少三条：中文连写能召回、假阳性被挡住、空结果仍给明确信号
- **每条新测试做变异测试**（改坏被测那行必须转红，然后还原）
- 评测集对照表进报告，前后数字都要有

## 7. 报告要求

除常规三段外必须回答：

1. 三条路线你实测的对照数据是什么？为什么选中的那条？
2. 假阳性阈值定在哪？依据是什么？
3. 改完之后，`ask.py` 的 planner 注入行为变了吗？变了多少？
   （两个消费方共用同一召回，**这条不能不答**）

## 8. 不要踩的坑

- **数数/读代码别用固定行号**，用 `sed -n '/^def xxx/,/^def /p'` 或 AST。
  本轮已有人栽过，一次还写进了 CLAUDE.md。
- **改完 grep 复核**，别只看工具返回值。本仓多 worktree、同名文件多份。
- **断言「我们没有 X」前**：全树 grep 同义词 + 读能力图谱 + 读 MOC 看板，见 `CLAUDE.md` §🗺️。
- 完成后按维护口径回写能力图谱并跑
  `python3 /Users/a77/agent-memory/scripts/graph_audit.py`（须 exit 0），不要新建第二份清单。
