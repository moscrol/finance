# 验收开放决策包（2026-08-02）—— 只写建议，不实施

按 2026-08-01e checkpoint 第 6 条：**决策包只写不实施**。以下每条都需要用户拍板，
本段一律没有动代码或题库。

---

## K：L2 独立 DAG 是否保留

**推荐：保留。**

理由：L2（资金流）不依赖同步段产物。夜跑 `all` 阶段现在是
`run_sync → rc=$? → run_l2_branch → if rc≠0 then exit`，即**同步段失败也照跑 L2**。
合并成一条 DAG 会让一次 CDP 掉线连带丢掉当天的 L2 数据。

该不变量已有测试保护：`tests/test_pipeline_p0.py::test_nightly_script_attempts_l2_before_sync_failure_exit`。

---

## A8 / C6：题目缺陷是否破封

**推荐：单独做 benchmark version migration 后再破封，不要现在改。**

现状（已由 `_reproducibility_diagnostics` 确定性命中）：

| 题 | 缺陷 |
|---|---|
| A8-market-stage | query 是相对时间「现在」，`expect_facts` 冻结在 2026-07-23；日期锚到不了产品 |
| C6-strict-definition | query 是相对时间「最近」，`expect_answer_set` 冻结在 2026-07-23 |

这两条红是**假的且永远不会变绿**——行情会漂移，冻结的期望值只会越来越错。

**破封的代价（必须一起做，不能只做一半）**：

1. 把日期写进 query 正文 → 破 `CANONICAL_CASES_SHA256` 密封
2. 更新 hash 常量
3. **使这两题的 codex/knevo 参照快照失效**——它们回答的是相对时间版问题
4. `_reproducibility_diagnostics` 的 freeze 测试是具名清单 `{A8, C6}`，要同步改

**不建议的做法**：只改 query 不换快照。那会让参照答案和问题对不上，比现在更糟。

---

## Codex 参照快照：是否补齐 28 份

**推荐：可以补，但必须走 `freeze --via` 记录真实来源；禁止伪造。**

现状：参照快照已冻结 22 / 28。缺的 6 份导致信息量对比里 4 题 `missing`。

`cmd_freeze` 的 docstring 写得很清楚：`via` 必填，因为「参照答案的价值全在来源可
追溯」，且必须能分清「这是机器跑的」还是「这是人问的」、问的是哪一天。

⚠️ **本段用 cockpit 的 `gpt-5.6-sol` 做的是 evaluator（评审），不是 reference
（参照答案）。** 两者不能混：参照快照必须是外部 agent 对**同一问题**的独立作答，
而不是评审对两份答案的打分。用 evaluator 的输出去填参照快照就是伪造。

---

## J：确定性正文补写

**推荐：基线之后单独做一批。**

理由：涉及 humanize 单渲染边界收敛 + `数据源状态` / `检索可观测` 移出用户 sections，
golden 全域波动，需要专门的快照迁移批次。

**新增依据（本段查出的）**：`AnswerSpec 质检` 的 13 条降级里 6 条是结构性假阳性——
`ask.py:1478-1489` 把检索遥测 / 路由元信息 / 免责声明 / TTL 一并塞进
`answer_spec.summary` 当 claim，再要求它们绑定证据。「图谱命中 0 概念、证据 0 条」
是对检索过程的度量，结构上不可能有证据。**J 这批正好可以把这四类一起挪出去。**

详见 `docs/verification/2026-08-02-degradation-taxonomy-95-events.md`（在
`fix/kb-rag-worker-attribution` 分支）。

---

## 新增建议 ①：selector 的 backfill 阈值

**推荐：单意图回填占比 > 50% 时标 `unjudgeable`，不参与 `discriminative` 判定。**

依据：本段 probe 里 `expansion` 意图 **12 家中 11 家是确定性回填（LLM 只选出 1 家）**，
整体 46% 的选择来自回填。当前 `discriminative` 判定不看这个比例，等于**回填可以
伪造出分辨率**。

详见 `docs/verification/2026-08-02-exposure-selector-resolution.md`。

---

## 新增建议 ②：阶段超时移出降级通道

**推荐：改记性能指标，不进 `degrades`。**

依据：4 条「公司映射/公司本体超过阶段时限 40 秒」的消息自己写着
**「结果已完整收束并保留」**，且这 4 题（B1/B2/B3/B8）恰恰是全场证据最丰富的
（B8 33 条证据 / 40 条引用、B2 3396 字，均为全场最高）。

延迟观测记进降级通道，污染的正是最好的样本。

---

## 新增建议 ③：契约未完成的根因在路由，不在门禁

**推荐：修路由，不要再修门禁判定条件。**

依据：C5「立新能源 2026-07-20 和 07-21 分别涨了多少、收盘价多少」是**纯查价题**，
被路由到 `theme-research` → `theme_analysis` 契约要求 `counterpoint` → 正文缺
措辞标记 → **27/28 已绑定证据的答案被整份丢弃，换成 192 字桩**。

系统里本就有 `quick_fact = (fact_value, as_of_date, evidence_boundary)`，不要求
counterpoint。

`task_fulfillment.py` 的注释记着这道门禁 07-31 已经修过**两次**同型失败
（「905 字完整答案被整份丢弃，换成 190 字的『请补充数据源或稍后重试』」、
「counterpoint 永远判缺、整份答案被 fail-closed」）——两次修的都是判定条件。
**只要路由还会把查价题送进 `theme_analysis`，就会有第四次。**
