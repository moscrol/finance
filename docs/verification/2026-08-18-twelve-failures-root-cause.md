# 12 道失败的分层归因 + 过拟合风险评估（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-land` `land/caliber-stack`
- 数据源：`intelligence/eval/runs/20260818T2100Z-caliber-p123-pure-ruler.json`（纯尺子跑，零产品改动）
  + 各题 episode 账本 `~/.finance-runtime/live-probe-traceability/users/live-probe/runs/<run_id>/continuous-episode.json`
- 归因工具：`intelligence.eval.tool_payload.attribute_failed_fact`（Phase 3 建的）

## 0. 三句话

1. **会过拟合，而且已经在过拟合**：B6 的新判据在冻结答卷上绿、两次实跑都红——判据是照着一份固定答案调出来的。C4 是另一形状：判据里冻的算子已经和主库现值对不上。
2. **不存在「一个」共性**，12 道分属五层。但存在**一个元共性**：每一层都缺「声明 → 校验」的闭环，所以每层都能**自洽地错**。
3. **最要命的一条**：题目从来不声明自己要哪张表（`expect_facts` 里 `caliber`/`dataset` 声明数 = **0 / 28**）。这不只让产品选表靠自觉，还**让 Phase 3 建的归因工具给出确信但错误的答案**——见 §2，A5 实测被误判成 `synthesize`，真相是 `retrieve`。

## 1. 12 道的分层归因

| 题 | 失败理由 | episode 账本实际取到的口径 | 层 |
|---|---|---|---|
| **A5**-limit-heat | `储能.limit_up_count=40` 未命中 | `fact_market_daily` / `fact_mainline_theme_daily` / `fact_mainline_sector_daily` / `fact_stock_high_daily`——**从未碰 `fact_theme_limit_heat_daily`** | ① 契约：口径没跟着题走 |
| **A7**-mainline | `芯片概念.limit_up_count=66` 未命中 | `fact_mainline_theme_daily` / `fact_mainline_sector_daily`——**同样没碰热度表** | ① 同上，**与 A5 同一处错** |
| **A9**-sentiment-contradiction | `strength_marginal_pct=-66.3` 未命中 | `fact_market_daily`(12) + 两张主线表 | ① 口径不全 |
| **A10**-new-high-structure | `stock_high_count_20d=339` 未命中 | **取对了** `fact_stock_high_daily` | ② 合成：取到了没写进答案 |
| **A4**-dual-red | `pct_chg=6.65` 未命中，抽到 8.18/8.03/7.82 | **取对了** `fact_sector_daily` | ② 取到了但选错行/没写对 |
| **A3**-stock-deep-dive | `missing expected entities: 立新能源` | 8 条 tool_result | ② 合成 |
| **A6**-limit-advance-ladder | `missing product terms: 断层` | 20 条 tool_result | ③ 判据：要求特定措辞 |
| **B6**-sellside-distillation | 四个澄清短语一个没中 | **无 episode 账本** | ③ **判据过拟合（已确诊）** |
| **C4**-unit-anomaly | `amount_raw=6112588.6` 未命中 | **无 episode 账本** | ③ **判据的期望值已过期**：主库 07-21 MLCC 现为 `611.26`，脏行只剩 06-18 / 06-22 |
| **C3**-empty-table | 没明说数据不可得 | 8 条 tool_result | ④ 产品行为（Phase 4.3 已修，纯尺子版不含） |
| **C5**-data-contradiction | 没标矛盾；`reason_code=knowledge_lane_answer` | **无 episode 账本** | ④ 路由（Phase 4.4/4.5 已修，纯尺子版不含） |
| **C10**-multi-turn-consistency | 追问丢已建立的上下文 | 12 条 tool_result | ⑤ 会话状态 |

**分布**：契约层 3 / 合成层 3 / 判据层 3 / 产品行为与路由 2 / 会话状态 1。

**所以「有没有共性」的诚实答案是：没有单一根因。** spec §3 原来那句
「12 道不是四层各有 bug，是同一个不变量在四层显影」**只对了一半**——
量纲/口径确实是一条贯穿线，但它直接解释的只有 3 道；
另外 3 道的根因是**修尺子的过程中新造出来的尺子缺陷**（B6/C4/A6），这是原 spec 没预料到的一层。

## 2. 最要命的一条：契约只有一半，导致归因工具确信地判错

### 2.1 实测

`expect_facts` 的 schema 是 `{field, value, tol_abs}`。**全 28 题声明 `caliber` / `dataset` 的数量 = 0。**
（`grep -c '"caliber"' intelligence/eval/cases/acceptance_verdict_contracts.json` → 0）

于是 `attribute_failed_fact` 永远以 `expected_dataset=None` 被调用，它的
「表不对 → retrieve」那条分支**永远不会触发**，只剩「字段名在不在 payload 里」这一条。

A5 的现场：

| 实际取到的表 | payload 字段名 |
|---|---|
| `fact_market_daily` | `trade_date`, `limit_up`, `total_amount`, `index_return_pct` |
| `fact_mainline_theme_daily` | `theme_name`, `rank`, `sector_count` |
| **`fact_mainline_sector_daily`** | `theme_name`, `sector_name`, **`limit_up_count`**, `return_pct`, `strength` |
| `fact_stock_high_daily` | `plate`, `amount` |

期望字段是 `储能.limit_up_count`，取尾段 = `limit_up_count`。
**错的那张表里恰好有一个同名列。** 于是工具返回 **`synthesize`**（「数取到了，只是没写进答案」），
而真相是 **`retrieve`**（「压根查的不是那张表」）。

### 2.2 这正是设计时预料到、但只做了一半的事

spec §Phase 3 原文写着：

> 字段名清单只能切开「取到了但没写进答案」和「根本没取到」。**切不开错表**：
> 错表也可能有「家数」「成交额」这种同名字段。A5 这种「选错表」要靠 `dataset` / `caliber` 才能判。

Phase 3 把 **答案侧**的 `dataset`/`caliber` 做出来了（现在每条 `tool_result` 都带）。
**期望侧从来没做。** 没有期望就没有比对，比对不了就退化成字段名匹配，而字段名匹配在错表上会假阳。

### 2.3 它还违反了本仓自己的一条模式

`~/harness-reference/BUILD.md` 七个模式里有一条「**认不出来就 fail closed**」。
这里是 **fail open**：缺期望口径时不返回 `unknown`，而是返回一个看起来很确信的 `synthesize`。
**判错方向比判不出来更贵**——它会把人力导向合成层，而 bug 在检索层。

## 3. 「每一步都有 trace 可追溯」目前不成立

12 道里 **3 道（B6 / C4 / C5）没有 episode 账本**。它们走的是罐头短路 / 降级 / lane
应答路径，这些路径不写 `continuous-episode.json`。

后果：**恰恰是最需要归因的三道，一步 trace 都没有。**（C4/C5 还正是 Phase 4.5 重点动的两道。）

这不是埋点埋错位置，是**有些交付路径根本不经过埋点所在的那条主链**。

## 4. 过拟合风险

### 4.1 已发生的两个实例

| 实例 | 形状 |
|---|---|
| **B6** | 判据照着 `20260818T051630Z` 里那句罐头澄清调，只认 `你指的是 / 请补充 / 请提供 / 缺少`。冻结答卷 ✅，`1749Z` 与 `2100Z` **两次独立实跑都 ❌** |
| **判据 I** | 目标值 `≥22` 达不到（实测 18），裁决改判为观察项。改判的理由成立且代价已写明（spec §8.1），但**「指标不达标就改指标」本身是同一族风险** |

### 4.2 结构性原因

28 题这套集子**已经被反复看过、反复照着调**：改判分器、改题面、改 overlay、改澄清短语。
它现在的功能是**回归集**（防退步），**不再是泛化读数**。
在它上面调出来的绿，泛化性未知——B6 就是证据。

### 4.3 解药已经存在，且从没跑过

**不要新建题集。** 本仓已有：

| 件 | 位置 | 状态 |
|---|---|---|
| 冻结 30 题分层集 | `intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json`（13.9 KB，30 题） | **存在** |
| 加载器与分层约束 | `intelligence/eval/frozen_question_set.py`（quick / daily-review / deep 三层各 10 题） | **存在** |
| 派单 | `docs/handoffs/2026-08-18-frozen-thirty-live-baseline.md` | **已派，先决已齐** |
| live 读数 | `intelligence/eval/runs/*frozen*` | **零**——从没跑过 |

题号与 28 题**完全不重叠**（`rebound-duration` / `index-rebound-space` / `ruihuatai-valuation` …
vs `A1-market-overview` …）。**这就是现成的 holdout。**

## 5. 建议的下一步（按性价比排序）

| # | 动作 | 成本 | 为什么是它 |
|---|---|---|---|
| 1 | **`expect_facts` 增加 `caliber` 字段并给 28 题填上** | EVAL_ONLY，零 LLM | 补上契约缺的那一半。补完 `attribute_failed_fact` 才有比对基准，A5/A7 当场能判成 `retrieve`。**这一条同时修好归因工具和产品的选表约束**，是唯一一个「一处修、三层受益」的改动 |
| 2 | **`attribute_failed_fact` 缺期望口径时返回 `unknown` 而非 `synthesize`** | 几行 | 把 fail open 改成 fail closed。在 #1 落地前它会让所有归因显示为 `unknown`——**那是诚实的读数，比现在的假确信好** |
| 3 | **跑一次冻结 30 题，拿泛化读数** | 一次 live 跑 | 28 题已是回归集不是泛化集。两份读数一起看才知道「修的是真本事还是这 28 道题」 |
| 4 | **让罐头 / 降级 / lane 路径也写 episode 账本** | HARNESS_FIX | 否则「每步可追溯」永远差那三道，而它们恰好是产品改动最密集的三道 |
| 5 | **B6 / C4 两条判据重定** | EVAL_ONLY | B6 别再拿 051630Z 验；C4 的冻结算子 `6112588.6` 要么改成现值 `611.26`，要么把脏行日期换成 06-18 / 06-22。**不要伪造数据去迁就判据** |

> **#1 和 #3 不冲突，而且顺序不能反。** 先补口径声明（让尺子能判对方向），
> 再跑 holdout（拿泛化读数）。反过来做，holdout 那次跑出来的归因同样是错的方向。
