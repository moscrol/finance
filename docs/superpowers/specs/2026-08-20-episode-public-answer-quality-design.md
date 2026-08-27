# 设计：投影修好之后，公开稿仍然不好用

- 日期：2026-08-20
- 状态：Draft **v2.1**（v2 二次取证 + 与路由稿的合入顺序 / `market_cause` 闸门）
- v1 → v2：三个现场里两个的归因被 trace 推翻，重心从「对账门禁」改成「先修取数、再上护栏」。见 §1.3。
- v2 → v2.1：相邻路由稿 `2026-08-20-market-cause-sector-routing-design.md` 核稿确认 T2 是板块归因改路由的前置；§6.2/§6.3 补 `market_cause`，§10 写成三阶段链。不改 P0/P1 刀法。
- 父稿：`docs/judge-evidence-projection-contract-spec.md`（C1–C4，判官入参契约）
- 相邻路由稿：`docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`（树 `/Users/a77/fwp-wt-market-cause-spec`）。合入顺序 §10.1：先本单 P0，再路由，再本单 P1。`R-20260820-07`（T2）是路由的前置。
- 实测目录：
  - Knevo 四题对照 `~/.finance-runtime/live-probe-traceability/20260820-judge-projection-live/`
  - Holdout `~/.finance-runtime/live-probe-traceability/20260820-judge-projection-holdout/`（**只有 summary**，归因证据不在这里）
  - **归因证据（§1.3 全部来自这里）**：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/<run_id>/continuous-episode.json`
    - `events[].payload.arguments` = 模型**实际发出**的请求参数 ← 翻案靠的是这个
    - `outcome.traces[]` = 收据摘要（只记服务到哪天，**记不了问了哪段**）
    - `semantic_verifier.public_answer` = 人看到的稿
    - run_id ↔ 题目对照：`20260820-judge-projection-holdout/holdout-runs.json`
- 代码树：必须在 `/Users/a77/fwp-wt-judge-projection`（`fix/judge-evidence-projection-contract`）上叠加，或等该分支合入后再从 `gitea/main` 开新树。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 verifier。

## 0. 一句话

上一单修好了「判官看错材料、把整篇删光」。人现在能读到判断和反证了，但稿子仍常出现三种**可机械化**的质量事故：缺口说明对不上账、问句里的那天没数、修完只剩一句。

**v2 改定**：二次取证推翻了初版的归因。三个现场里有两个**不是模型的错**——它查了正确的窗口、诚实报了缺口、还主动标 gap 拒绝编因果，是 **harness 在上游把数吃掉了**（§1.3）。于是本单重心改为：**P0 先修三条丢数路径**（截断不可见 / 时点检索被自己滤空 / 单位标签不一致），**P1 才上对账护栏**（Q1、Q3 保留并重述），**P2 兜底**（Q2 补枪降级）。仍不把「写得像研报」当成目标。

人话：阅卷老师终于拿到完整附件了，但**送附件的路上还在漏页**。初版以为是学生撒谎说「我查过」；取证之后发现学生真查了，是传达室把回执扣了。先修传达室，再立「不许谎报」的规矩——顺序反了会**逼着老实学生改口说假话**。遣词造句、判官偶发挂掉、把「铝」听成伦敦铝价，另开单。

## 1. 背景：上一单解决了什么、没解决什么

### 1.1 已经成立（不要重做）

`docs/judge-evidence-projection-contract-spec.md` 的 C1–C4 在 worktree 上已落地、未合 main：

| 不变式 | 现场 |
|---|---|
| 判官看得到 `title` | holdout 盛新 E10/E12、商业航天 E8–E21 的公司名和新闻标题都在 registry |
| E 号与写手同一空间 | 锂矿 registry 出现 `E7…E82` 空洞，没有密排成 E1、E2、E3 |
| 不许一次删光全部必填格 | Knevo 电网从三格 `missing` 变成三格 `fulfilled`；锂矿只丢产业链一格 |
| 失真可数 | 进了 episode 判官的 run：`projection_dropped_field_chars=0`，`projection_ordinal_mismatch_count=0` |

 Knevo 原题和新题（锂矿 / 盛新 / 商业航天 / A 股铝）上都成立。不是只对四道熟题有效。

### 1.2 人读到的稿仍然只有「中等草稿」

对照旧稿，变好的是**完整性**（不再半句「未核验表述已删除」）。绝对质量仍是工作台答辩稿：数字和 E 号堆在一段里，条件句套话多。

这些「写得不好看」**本单不做**——改 prompt 会和判官、视角叙事抢同一层，且没有可红可绿的尺子。

本单只收现场里能钉成「调用收据 vs 文案」的几刀。**下表的「根因」列已按 §1.3 的取证改写，初版的两行是错的**：

| 现场 | run | 人看到什么 | 根因（**已二次取证**，见 §1.3） |
|---|---|---|---|
| 锂矿发酵 | `run_20260820_160509_857370` | 「7/23 当日数据未取到」；库里 07-23 锂矿 +4.4% / 628.5 亿 / `diff_ratio` 11.73（确为双红） | ~~traces 里没有针对 07-23 的 `finance_query`~~ ← **错**。模型三次把 `time_range.end` 打到 `2026-07-23`，被 `ORDER BY trade_date ASC + LIMIT 25` 砍掉尾巴，且**截断没提示**。harness 丢数 |
| 电网发酵（投影后） | `run_20260820_155347_650140` | 「news 检索未返回 7-23 催化」 | ~~本轮 0 次 `news_search`~~ ← **错**。`REQ 10` 调了，工具回「无资讯（future_of_cutoff）」，4 页全被自家 cutoff 滤光。harness 自己滤空 |
| A 股铝为什么涨 | `run_20260820_161218_462670` | 公开稿 43 字，只剩「盘中 2.66%、宏桥/南山/神火」 | 现象成立：C3 只拦「三格全灭」，判断槽仍算 `fulfilled`。**但**删掉唯一硬事实那句的理由是「226.41**亿**」多写了单位——而 `sector_daily` 的 metric 标签本就没带单位。harness 制造的删稿理由 |
| 铝（第一问） | `run_20260820_160914_079382` | 拒答商品铝、零检索 | 路由把「铝」当成商品。**本单不做**，见 §2.2 |
| 盛新第一发 | `run_20260820_160641_849717` | 判官 `invalid provider response` | grok 回了非法 JSON。**本单不做** |

判别变量（验收只锁这几句，不要锁「更好看」）：

**P0（取数，先做）**

1. 工具撞到行数上限时，模型必须**被告知**截断；带锚定日的盘面查询，锚定日不得落在被截掉的那一侧。
2. 时点归因题的资讯检索不得被自身 cutoff **静默**滤成 0 条——要么换能取历史区间的路径，要么把越界结果**标注**给模型而不是丢掉。
3. 同一物理量在所有数据集的 metric 标签口径一致（带不带单位不能各表一套）。

**P1（对账护栏，P0 之后）**

4. 文案声称「没查到 / 没返回」时，traces 里必须有对应**能力**的收据（判据是 capability 名，不是工具名）。
5. 语义 repair 若把公开稿塌成残句，走 withhold；但回退目标是「修前稿**减去**判官点名的越界句」，不是整篇修前稿。

**P2（兜底）**

6. 问句里的日历日，盘面题必须查过那一天（或留下「查了、库无行」的收据）。P0-1 落地后这条大概率自动满足，留作兜底。

第 4 条是「声称试过就必须真试过」家族，本仓已有实例：`test_market_financials.py` 里「备源没跑过不得写两源均未取到」。本单把同一形状从财报块扩到 episode 公开稿。

**⚠ 取证后必须补一格**：初版只分「空结果 / 没调用」两态，现场证明**至少要四态**——

| 态 | 判据 | 正文可否写缺口 |
|---|---|---|
| 没调用 | traces 无该 capability | ❌ 不许写「未返回」 |
| 调了返回空 | `status=empty` | ✅ |
| **调了但被自己的门滤空** | `status=future_of_cutoff` 等 | ✅（初版会误判成「没调用」） |
| **调了但结果被截断** | `row_count == applied_limit` | ✅（初版同样会误判） |

后两态在初版真值表里会被判成第一态，也就是**把真话改成假话**。可迁移到任何「模型自己写缺口说明」的系统；面试问「空结果和没调用要不要分开」时，正确答案是**分开还不够**——还要把「被本系统自己丢掉」单列一态。

### 1.3 二次取证：三个现场的真实 traces（2026-08-20，[实测]）

落盘位置（**不在** `~/.finance-runtime/`，那里只有 summary，别再找错）：

```
~/.local/share/finance-workbench/users/linxiaoqi5111/runs/<run_id>/continuous-episode.json
```

`events[]` 有 `tool_request` 的完整 `arguments`；`outcome.traces[]` 是收据；`semantic_verifier.public_answer` 是人看到的稿。run_id ↔ 题目对照见 `20260820-judge-projection-holdout/holdout-runs.json`。

#### A. 锂矿：模型查了 07-23，三次

| event | 请求窗口 | limit | 实际返回 |
|---|---|---|---|
| REQ 3 | 07-01 → **07-23** | 25 | 07-01..07-03（25 行撞顶） |
| REQ 10 | 07-10 → **07-23** | 25 | 07-10..07-22（25 行撞顶） |
| REQ 17 | 07-21 → **07-23**（`theme_limit_heat_daily`） | 15 | `tool_budget_exhausted`，**没跑** |

两个叠加缺陷：

1. **`ORDER BY <锚定维度> ASC + LIMIT` 会系统性地先丢掉问句里的那天**——升序时锚定日永远排在最后一行，于是 LIMIT 第一个砍掉的正好是用户最想要的。**本单最可迁移的一条**：任何「回溯到某天」的分页取数都踩；面试里的游标分页 vs `OFFSET` 取舍是同一个考点。
2. **截断没告诉模型。** `episode_tools.py` 约 1140 行：

```python
if (
    normalized.limit > result.audit.applied_limit      # ← 只有"harness 压低了你的 limit"才提示
    and result.audit.row_count >= result.audit.applied_limit
):
```

`applied_limit = min(spec.limit, max_rows=200)`（`finance_query.py:156/1603`）。模型自己写 `limit=25` ⇒ `25 > 25` 为假 ⇒ **不提示**。真正的撞顶信号是第二个子句 `row_count == applied_limit`，它单独为真，却从来没人单独判。

于是模型手上只有「07-22 之后没有行」，写「7/23当日数据未取到…属数据缺口」是它能给出的**最诚实**表述。

#### B. 电网：模型调了 `news_search`，被自家 cutoff 滤成 0 条

```
REQ 10  news_search {"query": "电网设备 板块 大涨 特高压 2026年7月23日"}
RES     observation: "无资讯（future_of_cutoff：… pages=4; future_of）"
trace   capability=directional_news   status=future_of_cutoff   requested_date=2026-07-23
```

`research_tool_registry.py` 的 `cutoff_resolver` 把 as_of 压成 `min(今天, 问句日)` = 2026-07-23；`market_news.py` 的 `_news_at_or_before_cutoff` 再把东财标题检索结果全判成「未来」。东财标题检索**只回最近的**（同轮锂矿那次回的是 08-17/18），于是 4 页全滤光。这是个**结构上不可满足的请求**：对一个只按时效排序的源，问一个月前的时点。

公开稿原话：「②news检索未返回7-23同时间窗口的催化消息，无法把上涨归因为特高压/订单等具体事件，**该归因为gap**」——逐字属实，且主动拒绝了编造催化。

#### C. 铝：判官删对了 5 句，第 6 句删错在 harness

draft 384 字 → public 43 字，Q3 判据成立。判官 6 条 issue 里 5 条实质正确（E17/E18 是 07-29 的复盘拿来解释 07-23，时点越界；发明「产能天花板+海外供给受限」；给出未被要求的前瞻条件）。

但被删的第 1 句是全稿**唯一**一条 07-23 收盘口径硬事实，删它的理由是：

> 第1句将E1成交额226.41写成"226.41**亿**"，证据未给出单位，属无直接证据的数字扩写

E1 原文确为 `…涨跌幅=5.33；成交额=226.41`（无单位）。而 `finance_query.py` 里同一物理量**八处声明、两种标签**（[实测]，用 AST/正则扫出来的，不要抄行号去数）：

| 行 | 数据集 | label |
|---|---|---|
| 303 | `stock_daily` | `成交额` ← 无单位 |
| **326** | **`sector_daily`（铝案走的就是这张）** | `成交额` ← 无单位 |
| 356 | `sector_stock_daily` | `成交额` ← 无单位 |
| 392 | `stock_high_daily` | `成交额` ← 无单位 |
| 443 | `mainline_sector_daily` | `成交额` ← 无单位 |
| 513 | `dragon_tiger_daily` | `成交额亿` ← **有单位** |
| 535 | `core_stock_daily` | `成交额亿` ← **有单位** |
| 274 | `market_daily` | `市场成交额` ← 无单位 |

模型把单位补对了，被当成扩写删掉整句。**注意这不是「铝案孤例」**：6 张表都无单位，任何一次「成交 X 亿」都可能被同样判掉。

#### D. 结论

**「LLM 没消费好检索到的证据」在这三个现场都不成立。反过来：模型的表现好于 harness。** 初版 Q1 的两个现场事实前提是反的，照初版实施会**新增一类「门禁逼模型说谎」**——见 §6.1 的陷阱注。

## 2. 范围

### 2.1 做（P0 三条 + P1 两刀 + P2 一条，**按序**）

| 序 | 刀 | 名字 | 治哪条现场 |
|---|---|---|---|
| **P0-1** | **T1** | 截断可见 + 锚定日不落在被截的一侧 | 锂矿「7/23 未取到」的**真根因** |
| **P0-2** | **T2** | 时点检索不得静默滤空 | 电网「news 未返回」的**真根因**；铝第二问同因 |
| **P0-3** | **T3** | 度量标签统一带单位 | 铝案被删掉的那句唯一硬事实 |
| **P1-1** | **Q1** | 未尝试不得写成未命中（**重述**） | P0 之后仍可能出现的真谎称；当回归护栏 |
| **P1-2** | **Q3** | 残稿下限（C3 的下一格，**回退语义改** ） | 铝板块修到 43 字仍算 `fulfilled` |
| **P2** | **Q2** | 问句锚定日补一枪（**降级为兜底**） | P0-1 落地后锂矿本就查得到，故降级 |

P0 三条都是既有代码路径的小改（一个布尔条件、一处 as_of 传参、六处 metric 标签），**不新增模块**。
P1 两刀是 harness：确定性函数 + 夹具。P2 不新开 LLM 调用（补枪是已有的 `finance_query`，本地 DuckDB）。

> **顺序是硬的，不是建议。** P0 未落地就实施 Q1，会把电网/锂矿两句**真话**改成假话（§6.1 陷阱注）。实施者若因为「Q1 看起来更像本单主题」而先做 Q1，本单的净效果是负的。
>
> **与路由稿也是硬顺序。** 板块「为什么涨」改走 `market_cause` 之后，证据计划会把 `news_search` 设成 mandatory，窗口钉在问句日。T2 未合就先合路由，会把铝题现在的一次软缺口升级成每道板块归因必现的 `missing_mandatory_capability: news_search`。三阶段链见 §10.1。

### 2.2 不做

- 不重开 C1–C4，不改投影字段，不改 E 号真本源。
- 不改写手人设、不压 E 号密度、不把稿子改成「研报口吻」。
- 不强制所有「发酵 / 为什么涨」必须调 `news_search`。Q1 只禁止**一次没调却写「检索没返回」**；真想强制催化检索，另开台账（和 `R-20260820-05` 热度过滤同类）。**例外不是本单改的**：现役 `market_cause` 证据计划里 `news_search` 已经是 mandatory（`episode_factory.py:239-245`）。路由稿会把板块归因送进这条契约，T2 必须先让它回得了内容（§10.1）。Q1 管谎称，路由管题型，两件事不要揉成「本单去强制 news」。
- **不调预算/工具批常数**。锂矿 `REQ 17`（`theme_limit_heat_daily` 07-21→07-23）死于 `tool_budget_exhausted`，是本单取证时发现的**相邻**问题：模型第三次尝试拿锚定日数据被预算掐掉。它归 `R-20260816-07` 绊线管，本单**只记录不动手**。P0-1 修完后模型少走弯路、预算自然宽裕，届时再看这条是否还复现。
- 不修 `market_data` 强制能力缺失（Knevo B4 仍在，投影 spec 已列为不做）。
- 不修 grok 非法 JSON、不修「铝」商品路由、不修固态电池热度（`-05`）。
- 不调 T / `_REPAIR_SECONDS_CAP` / 工具批常数（`R-20260816-07` 绊线）。
- 不把 Knevo 四题再当唯一验收集。Holdout 题目必须进 §7。

## 3. 选型

| 方案 | 做法 | 为什么不选 / 为什么选 |
|---|---|---|
| **A′. 先修取数、再上对账护栏（本单 v2 选定）** | P0 修三条丢数路径；P1 才对账文案 vs traces；Q2 降为兜底 | 取证证明两个现场是 harness 丢数。护栏放在下游**只能让模型换个说法，数还是没有**。P0 三条都便宜，且修完 Q2 大概率不必发 |
| ~~A. 纯收据门禁 + 锚定日补一枪 + 残稿 withhold（v1）~~ | 只在下游对账 + 补枪 | **已被 §1.3 推翻**：两个现场的模型是诚实的。单做 A，锂矿会从「未取到」改口成「未查询 07-23」——**改成了假话**，而人依然拿不到那天的涨幅 |
| B. 只改 system prompt：「一定要查问句里的日期、不要谎称检索」 | 零代码 | 08-13 诚实度那批已经证明：休市、截止日、退役表交给模型转述会漏。`honesty_gates.py` 模块注释写明「Prompting the model to mention them has failed in production」 |
| C. 判官加一条「稿太短 / 没回答问题」的 LLM 审 | 第二轮语义审 | 判官窗口已经 50s；铝案是判官**按句删对了**（事后稿、发明供给），不是判官没看见。再加一轮会把「删超证」和「留下能用的判断」混成同一把刀 |
| D. Q2 做成规划器必选步骤 | 改 research plan 模板 | 爆炸面大（所有 question_type），且模型仍可跳步。补枪放在**合成之前的确定性缝**，跳不掉 |

P0 与 Q1/Q2 的关系（**v2 改写，v1 这段的前提已不成立**）：

- v1 写「只做 Q1，锂矿会改成『未查询 07-23』——诚实了，人还是看不到涨幅」。取证后更糟：**那句改口本身是假的**，模型确实查了。Q1 在 P0 之前就是一台说谎机。
- P0-1 落地后，锂矿这条链是：模型看到「已截断至 25 条」→ 收窄窗口或改降序重查 → 拿到 07-23 的 +4.4% / 628.5 亿。**数真的到手了，不是改个说法。**
- Q2 补枪的价值随之下降：它原本要解的「库里有、没查到」在 P0-1 之后不成立。保留为兜底（预算耗尽、模型不重试等残余情形），优先级 P2。
- Q1 仍要做，但**角色变了**：从「抓现行」变成「防回归」——P0 修完之后如果还出现「没收据却写未返回」，那才是真事故。

Q3 与 C3 的关系：C3 的尺子是「必填格是不是全 `missing`」。铝案 `direct_answer=fulfilled`，C3 不亮。Q3 的尺子是「修后公开稿是不是塌成残句」。两把尺子都要，不要把 C3 的阈值放宽成「留一句也算全灭」——那会误伤本来就短的 quick_fact。

**但 Q3 的回退目标必须改**（v1 未处理的张力）：铝案里判官删对了 5 句（07-29 复盘解释 07-23 属时点越界、发明供给机制、未被要求的前瞻条件）。v1 的「留修前稿」会把这些**已知有毒**的句子原样放回给用户。正确做法见 §6.3：回退到「修前稿 **减去** 判官 issues 点名的句子」。

## 4. 术语

| 词 | 含义 |
|---|---|
| **问句锚定日** | 问句里用 `_EXPLICIT_DATE_RE`（`task_frame.py`）匹配到的**最后一个**日历日。锂矿 / 电网 / 盛新 / 铝板块题都是 `2026-07-23`。「商业航天」无日期 → 本单 Q2 不适用 |
| **尝试收据** | `outcome.traces` 里 `ProviderTrace`：`capability` + `status != not_attempted`。⚠ **v1 说的「用 `requested_date` / `source_trade_date` / `served_date` 对齐锚定日」实测做不到**，见下方 `requested_date` 一行。**P0-1 必须把 `requested_time_range` 落进 trace**，否则 Q1/Q2 的对账必然误判 |
| **`requested_date`（别拿它当锚定日判据）** | 实测**同名不同义，按 capability 分裂**：`finance_query` 的三条全是 `2026-08-20`（＝`today`，与模型请求的 `time_range` 无关）；`directional_news` 的是 `2026-07-23`（＝生效 as_of）。`source_trade_date` / `served_date` 则是**实际服务到的最大日**。所以「问了哪段」在现有 trace 里**结构上无法表达**——这本身也是一处数据契约气味：同一字段名承载两种语义，谁读谁踩 |
| **未命中** | 调过且 `status in {empty, success}` 但正文说没有可用行——允许写缺口 |
| **被门滤空** | 调过且 `status in {future_of_cutoff, …}`：**算尝试过**，允许写「检索未返回」。v1 把它归进「未尝试」是错的（电网现场） |
| **被截断** | 调过且 `row_count == applied_limit`：**算尝试过但取数不全**。模型应被告知（INV-8），正文允许写缺口（锂矿现场） |
| **未尝试** | traces 里没有对应 capability 的**任何**收据，正文却写未取到 / 未返回 / 无检索 |
| **capability ≠ 工具名** | 判据一律用 capability。实测 `news_search`（工具）落到 traces 里是 `directional_news`（capability）。照工具名写判据 = 零命中 = 把真话判成谎话 |
| **残稿** | 修后公开稿相对修前草稿，句子数 < 2 **且** 字符数 < 修前的 20%（下限 80 字）。quick_fact / 休市罐头不适用 |
| **补枪** | 合成前对锚定日 + 主实体发一次 `finance_query`。单飞、本地库、不新开判官窗口 |

## 5. 不变式

编号续父稿 C1–C4。**P0 三条（INV-8/9/10）先落地**，P1/P2（INV-5/6/7）在其之后。

### P0

8. **INV-8（截断可见 + 锚定日不被截）**：
   - a) `finance_query` 结果 `row_count >= applied_limit` 时，observation **必须**带截断提示——**去掉** `normalized.limit > applied_limit` 这个前置条件（它使模型自设 limit 时永不提示）。
   - b) 带锚定日的盘面查询，锚定日不得落在被截的一侧：`ORDER BY <日期维度> DESC`，或对 `time_range` 端点行保底单取一次。
   - c) trace 落 `requested_time_range`，使「问了哪段」与「服务到哪天」成为两个可读字段。
9. **INV-9（时点检索不得静默滤空）**：资讯类工具因 as_of 把结果**全部**滤掉时，trace `status` 保持 `future_of_cutoff`（已成立），且 observation 必须让模型区分「源里没有」与「被本系统的时点门滤掉」。对**只按时效排序**的源（东财标题检索），不得用一个月前的 as_of 去要求命中——要么换能取历史区间的路径，要么把越界条目**标注后交给模型**。
10. **INV-10（度量标签自带口径）**：同一物理量在所有 `_DatasetDefinition` 里 label 一致；金额类一律带单位（§1.3-C 那 6 处补齐）。判官不得因模型补上 schema 本该给出的单位而删句。

### P1 / P2

5. **INV-5（未尝试 ≠ 未命中）**：公开稿（及送进判官的 draft）若匹配 §6.1 的缺口声称，则 traces 必须有对应尝试收据。判据用 **capability 名**；`future_of_cutoff` / `tool_budget_exhausted` / 截断 **一律算尝试过**。否则不得把这句话交给用户；改成「本次未查询 …」或在补枪之后重写该句。
6. **INV-6（锚定日覆盖）**：`has_explicit_date(question)` 且 question_type 属于盘面研究集（§6.2）时，合成前必须存在覆盖锚定日的 `finance_query` 尝试收据。判据读 **`requested_time_range`**（INV-8c 新落）；**只有** traces 里没有任何请求窗口覆盖锚定日才算 `missing`。「请求窗口覆盖了但结果被截断」记 `truncated`，**不算 missing**，由 INV-8 负责修。
7. **INV-7（残稿下限）**：semantic repair 之后，若稿子变成 §4 的残稿，走与 C3 相同的 withhold 分支：`repair_withheld=True`，`judge_status` 仍为 `repaired`，**不**扩 `JudgeStatus` 枚举。**回退目标改为**「修前 draft **减去** 判官 issues 点名的句子」；减完仍是残稿才回退整篇修前稿并在 issues 说明。**不得**把判官删对的越界句原样放回给用户。

落盘（沿用 C4 风格，可回归）：

| 字段 | 含义 | 归属 |
|---|---|---|
| `query_truncated_count` | 本 episode 撞顶（`row_count == applied_limit`）的查询数 | INV-8 |
| `anchor_date_in_truncated_tail` | 锚定日是否落在被截的一侧（修好后应恒 `False`） | INV-8 |
| `cutoff_filtered_empty_count` | 因 as_of 被全滤成 0 条的检索数 | INV-9 |
| `unattempted_claim_count` | INV-5 命中条数。**注意**：P0 修完后电网 / 锂矿那两条应为 **0**（它们本来就不是谎称）；若初版实现让它们 >0，说明判据写错了 | INV-5 |
| `asked_date_coverage` | `covered` / `truncated` / `not_applicable` / `missing` | INV-6 |
| `repair_collapsed_to_stub` | Q3 是否触发 | INV-7 |
| `repair_rollback_mode` | `minus_flagged_sentences` / `whole_pre_repair` | INV-7 |

## 6. 变更清单

新纯函数不要塞进已 3500+ 行的 `episode_semantic_verifier.py` 正文。新建 `intelligence/services/episode_answer_hygiene.py`，verifier / 合成前各调一次。这是「圈小而稳的一侧」：圈对账规则，不圈写手。

**P0 三条不进新模块**——它们是既有取数路径上的定点修，硬塞进 hygiene 模块反而是把底座逻辑挪进积木层。

### 6.0 P0 — 先把数取回来

#### T1（INV-8）截断可见 + 锚定日不被截

`intelligence/services/episode_tools.py`（约 1140 行，条件当前为）：

```python
if (
    normalized.limit > result.audit.applied_limit
    and result.audit.row_count >= result.audit.applied_limit
):
```

改为**只判第二个子句**。第一个子句的语义是「harness 压低了你的 limit」，它让「模型自设 limit 且刚好撞顶」这一最常见情形永不提示——锂矿现场 `limit=25`、`applied_limit=min(25,200)=25`、`row_count=25`，三值相等，提示被 `25 > 25` 挡掉。

提示文案要能让模型判断**尾巴被切了**，而不只是「还有更多」。建议在现有串后追加实际返回的日期区间，例如 `…实际覆盖 2026-07-10..2026-07-22`，让「我要的 07-23 不在里面」一眼可见。

`intelligence/services/finance_query.py`：

- b) 编译期：`time_range` 存在且 `order_by` 是日期维度 `asc` 时，**改成 `desc` 取数、返回前再翻回 asc**；或对 `time_range.end` 那天单独保底取一次并入结果。前者改动小、后者语义更直白，二选一，在 PR 里写清选了哪个和为什么。
- c) `QueryAudit` 增 `requested_time_range`，一路带进 `ProviderTrace`。**这是 INV-6 的前置**，没有它 Q1/Q2 只能靠 `source_trade_date` 猜。

> 可迁移：`ORDER BY <锚定维度> ASC + LIMIT` 会先丢掉查询者最关心的那一端。任何「回溯到某天」「截至某版本」的分页取数同形。

#### T2（INV-9）时点检索不得静默滤空

`intelligence/services/research_tool_registry.py` 的 `cutoff_resolver` + `market_news.py` 的 `_news_at_or_before_cutoff`。

现状：as_of 被压成 `min(context_cutoff, 问句日)`，东财标题检索只回最近条目，4 页全判「未来」→ 0 条。

三个候选，**在 PR 里选一个并说明**：

| 选项 | 做法 | 取舍 |
|---|---|---|
| **T2-a（推荐）** | 全滤时不返回空，而是返回**标注为「晚于问句日」的条目** + 明确 observation，让模型自己决定引不引 | 不丢信息；模型已被证明会正确处理（锂矿那轮拿到 8 月新闻后主动写「与 7 月窗口不匹配」） |
| T2-b | 对时点题换用支持历史区间的检索路径 | 更正确，但要确认存在这样的源；工作量大于本单 |
| T2-c | 时点题直接不压 as_of | 会引入事后信息泄漏，**不选**——铝案判官正是抓这个（E17/E18 时点越界） |

> T2-c 被否的理由值得记：**「别让模型看到未来信息」和「别让模型看不到任何信息」是两个都要满足的约束**，不能靠放弃一个来满足另一个。T2-a 的本质是把二元的「过滤」换成带标签的「标注」——判官那层已经能抓时点越界，信息在下游还有一道闸。

#### T3（INV-10）度量标签统一带单位

`finance_query.py` 里 §1.3-C 表中 6 处无单位的 `amount` 补成带单位口径，与 `dragon_tiger_daily` / `core_stock_daily` 对齐。改标签会动到证据正文渲染，**必须跑一遍现有 finance_query 相关测试**看有没有断言吃死了旧串。

### 6.1 Q1 — 未尝试不得写成未命中（P1，**必须在 P0 之后**）

`episode_answer_hygiene.py`：

```python
@dataclass(frozen=True)
class UnattemptedClaim:
    capability: str          # news_search | finance_query | ...
    asked_date: str | None   # ISO 或 None
    snippet: str             # 命中的原文片段，供改口

def find_unattempted_claims(
    text: str,
    traces: tuple[ProviderTrace, ...],
    *,
    asked_date: str | None,
) -> tuple[UnattemptedClaim, ...]:
    """无 IO。只读文案和 traces。"""
```

> ### ⚠️ 陷阱注：v1 的真值表会把真话判成谎话
>
> v1 那张表有两处致命错误，**实施者照抄就会造出一台说谎机**：
>
> 1. **判据写了工具名 `news_search`，而 traces 记的 capability 是 `directional_news`。** 照写 = 零命中 = 电网那句**属实**的「news 检索未返回」被判谎称 → 改口成「本次未查询 news_search」→ **这才是全场唯一的谎言，且是门禁自己造的**。
> 2. **「只有 7/1–7/22 的收据」被当成「没查过 07-23」。** 实测模型三次请求都把 `time_range.end` 打到 07-23，是被 LIMIT 截了尾。缺的不是调用，是 `requested_time_range` 这个字段（INV-8c）。
>
> 通用形状：**对账门禁的判据字段必须来自被对账方真实写入的那张表**，不能来自你以为它会写的那张。这条在任何「声明 vs 执行」体检里都成立——先 grep 一条真实落盘记录，再写判据。

声称 → 收据 真值表（**v2 改定**；实施不得改行，只能改实现）：

| 文案形状（正则语义，不是要写死这一句） | 需要的收据 | 现场核对 |
|---|---|---|
| `news` / `资讯` + `未返回` / `未检索` / `无检索` | **`capability=directional_news`**（不是 `news_search`）且 `status != not_attempted`；`future_of_cutoff` **算尝试过** | 电网 `REQ 10` 有该收据 → **不命中，判为合法缺口报告** |
| `当日` / 锚定日 / `这天` + `数据未取到` / `未取到` | `capability=finance_query` 且**存在请求窗口覆盖锚定日**（读 `requested_time_range`）；被截断算尝试过 | 锂矿三次窗口 end=07-23 → **不命中**；改由 INV-8 修数 |
| `本次未提供任何检索` / `retrieved_material 为空` | 至少一条非 configure 的研究 trace | 铝第一问整段拒答；该问没进 episode，Q1 管不到（路由，§2.2） |

反向（**Q1 不是禁止报缺口**）：真的调过且 `status in {empty, future_of_cutoff}`、或结果被截断，一律允许写「检索未返回 / 当日数据未取到」。

**验收的方向性要求**：P0 修完之后，电网与锂矿两条现场的 `unattempted_claim_count` **必须是 0**。若某个实现让它们 >0，那不是「抓到了」，是判据写错了——见上方陷阱注。

调用点：`episode_semantic_verifier` 进判官**之前**扫 draft。有命中：

1. 若 Q2 补枪即将发生且 capability 是 `finance_query`：先补枪，再扫一次（避免改口后又查出数）。
2. 否则把声称句改成「本次未查询 {capability}{日期}」，或从 draft 删除该句并在 `issues` 加 `code=unattempted_claim`。**首选改口**，不整段重写。改口函数必须无 LLM。

对标：`intelligence/tests/test_market_financials.py::FallbackAttemptedDisclosureTests`。

### 6.2 Q2 — 锚定日补一枪（**P2 兜底，取证后降级**）

> **降级理由**：v1 把 Q2 定为「锂矿库里有 07-23 却没查那天」的解药。取证证明模型**查了**，缺的是 INV-8 的截断可见性。P0-1 落地后这条主路径自愈，Q2 只剩残余情形：预算耗尽（锂矿 `REQ 17` 就是 `tool_budget_exhausted`）、模型看到截断提示后不重试。
>
> **所以 Q2 可以在 P0 之后重新评估要不要做。** 若 §7.7 的 live 重跑在只做 P0 的情况下已经拿到 07-23 数字，Q2 记 `deferred`，不占实现工时——但账本行保留，不要撤号。

盘面研究集（写死，避免「所有题都补枪」）：

```python
ASKED_DATE_COVERAGE_TYPES = frozenset({
    "theme_analysis",
    "stock_analysis",
    "market_review",
    "causal_review",
    "market_cause",  # v2.1：路由稿合入后，铝/板块归因会落到这里；漏了则 Q2/Q3 闸门不触发
    "fermentation_trace",  # 若路由枚举里没有这个名字，用 theme_analysis + 问句含「发酵」
})
```

实施时以 `TaskFrame.question_type` **现役枚举**为准：先 `rg "question_type" intelligence/services/task_frame.py`，把上表映射到真实字符串。现场 Knevo/holdout 的电网/锂矿在**路由前**是题材分析，盛新是个股；铝板块归因在路由前是 `general_finance_qa`，路由后是 `market_cause`。`market_cause` 已是现役枚举，不要漏。若盛新的现役字符串是 `stock_deep_dive` 而不是 `stock_analysis`，按源码改集合，不要发明新 type。

补枪时机：研究循环结束、**第一次合成之前**（`agent_episode` 里 draft 仍空、evidence 已在）。这时加一条 `finance_query` 不会打乱已绑定的 E 号——`evidence_ordinal_table` 按全表发号，新卡拿到新号，写手还没引用。**不要**在判官之后再补枪（写手看不到新卡，D2 会复发成「有卡没引用」）。

补枪参数（最小）：

- 日期 = 问句锚定日
- 主体 = task_frame 已解析的板块名或股票名（锂矿 / 盛新锂能）；解析不到则**不补**，只记 `asked_date_coverage=missing` + Q1 改口，不要猜主体
- dataset：个股 `stock_daily`，板块 `sector_daily`（与现役 `finance_query` 描述一致）
- 剩余墙钟 < 2s：跳过补枪，走 Q1 改口

单飞键：`(finance_query, dataset, subject, asked_date)`。同 episode 已有成功/空收据则不发。

锂矿夹具（冻结 holdout 的 traces 形状，不要提交整份 620KB episode）：

- **真实形状（v1 记错了）**：三条 `finance_query` 收据，`requested_time_range.end` 均为 `2026-07-23`，`source_trade_date` 分别是 07-03 / 07-22 / 07-08，`row_count == applied_limit`（25/25/15）；另有一条 `tool_budget_exhausted`。**不是**「无 7/23 请求」。
- 该夹具首先是 **INV-8 的**：断言截断提示出现、`anchor_date_in_truncated_tail=True`（修前）→ `False`（修后）。
- Q2 若仍实现：只有在「请求窗口覆盖锚定日 **且** 结果被截断 **且** 无剩余预算重试」时才补枪；补枪后出现 `source_trade_date=2026-07-23`，或 `empty` + `requested_time_range` 覆盖 07-23。
- 草稿不得再写「7/23 当日数据未取到」，**除非**收据确为 `empty`（库里实际有行，所以修好后不应为 `empty`）。

### 6.3 Q3 — 残稿下限

`episode_semantic_verifier.py` 里 `_marker_loss_or_withhold` 旁增加 `_repair_collapsed_to_stub(before: str, after: str, question_type: str) -> bool`，实现放 hygiene 模块。

真值表：

| before 字数 | after 字数 | after 句子数 | question_type | 结果 |
|---|---|---|---|---|
| 800 | 43 | 1 | 盘面研究集（含 `market_cause`） | withhold（铝现场的**形状**；type 见下） |
| 640 | 600 | 3 | theme_analysis | 不触发（电网新稿） |
| 80 | 40 | 1 | `quick_fact` | 不触发 |
| 400 | 90 | 2 | theme_analysis | 不触发（过了 20% 或句子数 ≥ 2 任一即可留下——**必须同时**「<20% **且** 句子 <2」才 withhold，避免误伤删了一段超证但仍有判断+反证的稿） |

铝现场：`run_20260820_161218_462670`，修前 draft **384 字**、修后公开 **43 字一句**。修前 draft 从该 run 的 `outcome.draft` 读取作夹具（只提交 draft 字符串 + 字数 + 判官 issues，不提交整包 evidence）。

> **v2.1 夹具寿命**：这份 384→43 的 draft 是在 `general_finance_qa`（槽位 `[direct_answer, evidence_boundary]`）下产生的。路由稿合入后，同一题面变成 `market_cause`，槽位换成 `[direct_assessment, causal_chain, counterpoint, evidence_boundary]`，证据计划也换成 `time_aligned_market_causal`。**现在就冻进 Q3 测试等于冻一个即将作废的形状。** P0 阶段可以用它证明「残句 withhold」这条函数；P1/Q3 合入闸必须换路由后的 live draft。闸门的 `question_type` 集合从第一天起就要包含 `market_cause`，不要等路由后再补——否则路由一合，铝题从盘面研究集掉出去，Q3 根本不触发。

触发后与 C3 共用 `_marker_loss_or_withhold` 的 withhold 分支：不要第二条「留修前稿」的实现。`repair_collapsed_to_stub=True` 写入 `to_dict()`。

#### 回退目标：不是整篇修前稿（**v2 新增，v1 的坑**）

v1 写「公开文本必须 `view(before)`」。铝案证明这样做会**把判官删对的内容还给用户**——那 6 条 issue 里 5 条实质正确：

| 判官 issue | 删得对吗 |
|---|---|
| 第4句用 07-29 的复盘解释 07-23 上涨，时点越界 | ✅ 对 |
| 第5句发明「产能天花板+海外供给受限」 | ✅ 对 |
| 第5句给出未被要求的前瞻条件 | ✅ 对 |
| 第3句把「69.72%」改成「69.72% 以上」 | ✅ 对 |
| 第2句混淆 E1 收盘口径与 E15–E18 | ✅ 对 |
| 第1句「226.41**亿**」属数字扩写 | ❌ **错**，是 schema 没给单位（T3 修） |

所以 withhold 的回退目标定为：

```
rollback = 修前 draft − 判官 issues 点名的句子
```

- 减完 **≥ 2 句且 ≥ 80 字** → 用它，`repair_rollback_mode=minus_flagged_sentences`
- 减完仍是残稿 → 才回退整篇修前稿，`repair_rollback_mode=whole_pre_repair`，并在 `issues` 写明「已回退至未经语义修复的稿，其中含 N 条未通过判官的表述」

**铝案在 T3 修完后走的是第一条**：第 1 句不再被删（单位来自 schema），减去其余 5 句后剩「盘面事实 + 盘中快照」两句、约 90 字，够用且干净。这也说明 **P0-3 与 Q3 是同一个现场的两半，不要分开验收**。

> 可迁移：「回退到上一个版本」在有质检的流水线里几乎总是错的默认值——上一版之所以被改，正因为它有已知缺陷。正确形状是**回退到「上一版减去已确认的坏部分」**，并把「减完还是不可用」当成单独一种终态上报。

## 7. 验收（逐条报，不报混合百分比）

解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

**P0 —— 先绿这一组**

| # | 案例 | 通过 |
|---|---|---|
| 1 | `test_truncation_notice_when_model_sets_own_limit` | `limit=25`、`applied_limit=25`、`row_count=25` → observation **必须**含截断提示。**这是修前会红的那条**（`25 > 25` 为假） |
| 2 | `test_truncation_notice_reports_covered_range` | 提示里含实际覆盖区间（如 `2026-07-10..2026-07-22`），使「锚定日不在其中」可判 |
| 3 | `test_anchor_date_not_dropped_by_limit` | 锂矿形：窗口 07-10→07-23、每日 2–3 行、limit 25 → 结果**必须**含 07-23；`anchor_date_in_truncated_tail=False` |
| 4 | `test_requested_time_range_lands_in_trace` | trace 有 `requested_time_range={"start":…,"end":"2026-07-23"}`，且**不等于** `requested_date`（后者实测恒为 today） |
| 5 | `test_cutoff_filtered_news_not_silently_empty` | 电网形：as_of=07-23、源只回 08-17/18 → 不得静默 0 条；按选定的 T2-a/b 断言 observation 可区分「源里没有」与「被时点门滤掉」 |
| 6 | `test_amount_metric_labels_carry_unit` | §1.3-C 那 8 处 label 口径一致；金额类均带单位 |

**P1 —— P0 绿了再做**

| # | 案例 | 通过 |
|---|---|---|
| 7 | `test_directional_news_receipt_counts_as_attempted` | 电网形：draft 含「news 检索未返回」，traces 有 `capability=directional_news` / `status=future_of_cutoff` → `unattempted_claim_count == 0`，**文案不得被改口**。⚠ 这条专抓 §6.1 陷阱注的第 1 点 |
| 8 | `test_truncated_finance_query_counts_as_attempted` | 锂矿形：`requested_time_range.end=07-23` 且被截断 → `unattempted_claim_count == 0`，`asked_date_coverage == "truncated"`（**不是** `missing`） |
| 9 | `test_unattempted_news_claim_without_any_trace` | 构造 traces **完全没有**资讯类 capability 的情形 → `unattempted_claim_count>=1`，改口后不再含「未返回」。这才是 Q1 真正该抓的形状 |
| 10 | `test_undated_theme_skips_asked_date_coverage` | 「商业航天」→ `not_applicable` |
| 11 | `test_repair_withholds_collapsed_stub` | 铝形 **384→43** 字一句 → `repair_withheld=True`、`repair_collapsed_to_stub=True` |
| 12 | `test_rollback_subtracts_judge_flagged_sentences` | 铝形回退 → `repair_rollback_mode="minus_flagged_sentences"`，公开稿**不含**「07-29 复盘解释 07-23」与「产能天花板+海外供给受限」 |
| 13 | `test_rollback_falls_back_to_whole_draft_when_still_stub` | 减完仍 <2 句 且 <80 字 → `whole_pre_repair` + issues 说明 |
| 14 | `test_repair_keeps_trimmed_but_usable_draft` | 电网形删一句跨口径、仍 ≥3 句 → 不 withhold |

**live（无 sidecar 记 `not_run`）**

| # | 案例 | 通过 |
|---|---|---|
| 15 | live 重跑锂矿原问 | 公开稿含 **2026-07-23 锂矿 +4.4% / 628.5 亿**（或明确「已查无行」，但库里有行故不应出现）；不得再写「7/23 当日数据未取到」 |
| 16 | live 重跑「2026-07-23 A股铝板块为什么涨，给出证据来源」 | 公开稿不是单句 43 字；含 07-23 收盘口径 **5.33% / 226.41 亿**；**不含**判官点名的时点越界归因 |
| 17 | live 重跑电网原问 | 若仍写「news 未返回」，traces 里必须有 `directional_news` 收据（即该句合法）；按 T2 选项断言模型是否拿到了标注后的越界条目 |

第 15–17 条无 sidecar 则记 `not_run`，**不得用单测绿把 `-06`…`-11` 写成 confirmed**。

**变异**（`.pyc` 同长度改回会假绿，变异后还原再跑一遍）：

| 变异 | 应该红的用例 |
|---|---|
| 截断提示恢复 `normalized.limit > applied_limit` 前置 | 1 |
| 日期排序改回 `asc` 且不做端点保底 | 3 |
| Q1 判据把 capability 换成工具名 `news_search` | **7**（会从「不命中」变成「命中」＝造谣） |
| Q1 把「被截断」当成未尝试 | 8 |
| 回退改成整篇 `view(before)` | 12 |
| 残稿阈值 20% → 1% | 11 |

## 8. 落点与文件

| 文件 | 职责 | 序 |
|---|---|---|
| Modify: `intelligence/services/episode_tools.py`（约 1140 行） | T1a 截断提示条件去前置 + 提示带覆盖区间 | **P0** |
| Modify: `intelligence/services/finance_query.py` | T1b 日期排序/端点保底；T1c `QueryAudit.requested_time_range`；T3 六处 `amount` label 补单位 | **P0** |
| Modify: `intelligence/services/research_tool_registry.py` / `market_news.py` | T2 时点检索不静默滤空（按选定的 a/b 落地） | **P0** |
| Create: `intelligence/tests/test_finance_query_truncation.py` | §7 第 1–4、6 例 | **P0** |
| Create: `intelligence/tests/test_news_cutoff_disclosure.py` | §7 第 5 例 | **P0** |
| Create: `intelligence/services/episode_answer_hygiene.py` | INV-5/6/7 纯函数 + 改口 + 回退裁剪 | P1 |
| Create: `intelligence/tests/test_episode_answer_hygiene.py` | §7 第 7–14 例 | P1 |
| Create: `intelligence/tests/fixtures/answer-hygiene/h1-lithium-traces.json` 等最小夹具 | 只冻 traces + draft 片段 + 判官 issues，不冻整份 episode（锂矿那份 620KB） | P1 |
| Modify: `intelligence/services/episode_semantic_verifier.py` | 进判官前跑 Q1；`_marker_loss_or_withhold` 兼 Q3 + 回退裁剪；`to_dict()` 新字段（§5 那张表） | P1 |
| Modify: `intelligence/services/agent_episode.py`（合成前） | Q2 补枪；先 `rg` 现役合成入口，不要猜错函数名。**P0 后若已自愈则不改** | P2 |
| Modify: `docs/prediction-ledger.md` | `R-20260820-06`…`-11` | 收尾 |
| Modify: `docs/trace-profile.md` | 截断/覆盖区间、cutoff 滤空、未尝试声称、锚定日覆盖、残稿与回退模式 | 收尾 |

不要改 `honesty_gates.py` 的休市/退役表路径——那是另一条交付层。Q1 形状相同、入口不同（episode draft vs lane canned answer）。

## 9. 账本

`R-20260820-01`…`-05` 已占用（[实测] `docs/prediction-ledger.md:60-64`）。本单占 `-06`…`-11`。

> **v1 的 `-06/-07` 现象描述已被取证推翻，本表已重写。** 号不撤、不改指向别的东西——ledger ID 是标识符不是优先级，`-06/-07/-08` 现在指 P0 三条，`-09/-10/-11` 指 P1/P2。

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260820-06` | `finance_query` 撞顶不提示（`normalized.limit > applied_limit` 前置使模型自设 limit 时永不告警），且 `ORDER BY 日期 ASC + LIMIT` 先丢锚定日 | `HARNESS_FIX` | P0 | §7.1–7.4、§7.15 |
| `R-20260820-07` | 时点归因题的资讯检索被自身 as_of 全滤成 0 条（东财标题检索只回近期）。**路由稿前置**：板块归因改 `market_cause` 后这条会变成 mandatory `news_search` | `HARNESS_FIX` | P0 | §7.5、§7.17、§10.1 |
| `R-20260820-08` | `amount` 度量 8 处声明两种 label，6 处无单位；模型补对单位反被判「数字扩写」删句 | `DATA_CONTRACT_FIX` | P0 | §7.6、§7.16 |
| `R-20260820-09` | 缺口声称与收据对不上账（P0 之后的**回归护栏**；两个已知现场本身**不是**谎称） | `HARNESS_FIX` | P1 | §7.7–7.10 |
| `R-20260820-10` | 铝：repair 塌成残句仍 `fulfilled`；且回退到整篇修前稿会把判官删对的越界句还给用户 | `HARNESS_FIX` | P1 | §7.11–7.14、§7.16 |
| `R-20260820-11` | 锚定日补枪（**兜底**；P0-1 后若 §7.15 已绿则记 `deferred`，不撤号） | `HARNESS_FIX` | P2 | §7.8、§7.15 |

**结案纪律**：

- 禁止把 08-15 Open 表的 F-001/F-002/F-003 标 refuted。
- `-06/-07` 结案时必须写明「v1 归因（模型谎称）已 refuted，实际为 harness 丢数」——**这条 refute 是本单最有价值的产出，不要在重写时把它抹掉**。
- 单测绿不足以让 `-06`…`-10` 转 confirmed，需 §7.15–7.17 的 live 收据。

## 10. 实施顺序

### 10.1 跨 PR 三阶段（v2.1，与路由稿互文）

路由稿：`docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`（树 `/Users/a77/fwp-wt-market-cause-spec`）。两稿几乎零文件冲突，但 **runtime 契约冲突**：路由把板块归因送进 `time_aligned_market_causal`，其中 `news_search` 是 mandatory，窗口钉在问句日；T2 未修时那次检索结构上滤成 0 条。

| 阶段 | PR | 内容 | 为什么必须这个顺序 |
|---|---|---|---|
| **1** | 本单 | **P0 全部**（T1 / T2 / T3） | T2 是路由的前置。P0 与路由改的不是同一批文件 |
| **2** | 路由稿 | 板块「为什么涨」→ `market_cause`（含词序无序合取） | 此时 news 能回内容，mandatory 才不是必红 |
| **3** | 本单 | **P1**（Q1 / Q3）；Q2 仍按 §6.2 条件执行 | Q3 夹具依赖路由后的 `question_type` 和新 draft；Q1 的「未尝试」在强制 news 之后才有稳定形状 |

禁止：阶段 2 插到阶段 1 前面。失败形状见路由稿 §12。

P1 可以在阶段 1 之后、阶段 2 之前**写测试骨架**（`market_cause` 已在 §6.2 集合里），但 Q3 的铝 draft 夹具不要在阶段 2 之前锁死为合入闸。

### 10.2 本单内部（P0 → P1 → P2）

1. 确认仍在 `fwp-wt-judge-projection`；C1–C4 未提交也没关系，本单叠在上面。主仓脏树只许 pathspec 加这份 spec。
2. **竖切 T1**：§7.1 夹具红（`limit=25/applied=25/row=25` 无提示）→ 去掉前置条件 + 提示带覆盖区间 → 绿；再 §7.3 红（07-23 被截）→ 排序/端点保底 → 绿；§7.4 落 `requested_time_range`。
3. **竖切 T2**：§7.5 红 → 按选定的 T2-a/b 落地 → 绿。**在 PR 里写清选了哪个、为什么不选 T2-c。**
4. **竖切 T3**：§7.6 红 → 六处 label 补单位 → 绿。跑一遍现有 finance_query 测试看有无断言吃死旧串。
5. **P0 中场验收**：能跑 sidecar 就先跑 §7.15（锂矿）。**若此时公开稿已含 07-23 的 +4.4% / 628.5 亿，则 Q2 记 `deferred`，跳过第 7 步。**
6. **竖切 Q1**：§7.7/7.8 必须**绿在「不命中」**（这两条是防造谣的），§7.9 绿在「命中」。变异：判据换成工具名 `news_search` → §7.7 必须红。
7. （条件执行）竖切 Q2：见第 5 步。
8. **竖切 Q3**：§7.11 红 → withhold 走现有分支 → 绿；§7.12 红 → 回退改为「减去判官点名句」→ 绿；§7.14 不 withhold。
9. 跑 §7.16 / §7.17。合 main 等用户确认。

> **反向执行的代价**：先做 Q1 再做 P0，会先造出一台把两句真话改成假话的门禁，然后 P0 修完还要回头把那两条「命中」再改回「不命中」——中间任何一次 live 都会留下带谣言的公开稿。先合路由再合 T2，会把「news 被滤空」从软缺口变成 mandatory 能力缺失，板块归因题结构核验必红。

## 11. 回写

项目级：`.agent-memory/20_projects/finance-workspace-private.md` 交接一行（P0 三条 + P1 两刀 + 账本号）。不要把 live 问句全文抄进 vault。

方法论（本单产出四条，都不止用于本仓）：

1. **未尝试 ≠ 未命中，且至少要四态**——`没调用 / 返回空 / 被自己的门滤空 / 被截断`。补 `10_knowledge/` 里 evidence-hygiene 那篇的实例。
2. **`ORDER BY <锚定维度> ASC + LIMIT` 先丢掉查询者最关心的那一端**。任何「回溯到某天 / 截至某版本」的分页取数同形。
3. **对账门禁的判据字段必须来自被对账方真实写入的那张表**——先 grep 一条真实落盘记录再写判据。本单差点用 `news_search`（工具名）去查 `directional_news`（capability 名），零命中会被读成「抓到谎称」。这与已沉淀的 [[contract-vs-delivery-mismatch]]「填了但没人读」是同一族的镜像：**读了，但读的是不存在的字段**。
4. **「回退到上一版」在有质检的流水线里几乎总是错的默认值**——上一版之所以被改，正因为它有已确认的缺陷。正确形状是「上一版减去已确认的坏部分」，并把「减完仍不可用」当成单独一种终态上报。

第 2、3、4 条属「搭建」那一件，**回写 `~/harness-reference/KIT.md` 的指针，不另建清单**。

**取证方法本身也值得沉淀**：本单的全部翻案来自读 `continuous-episode.json` 的 `events[].payload.arguments`——即**模型实际发出的请求参数**，而不是 `traces[]` 的收据摘要。收据只记「服务到了哪天」，记不了「问了哪段」；只看收据必然得出「它没查」的错误结论。**判断「模型有没有做 X」，要读它发出的请求，不是读返回的回执。**
