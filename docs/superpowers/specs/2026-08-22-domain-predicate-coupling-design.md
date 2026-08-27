# 设计：领域谓词耦合（原件 + 复印件打成一开关）

- 日期：2026-08-22
- 状态：Draft（穷尽修订：code map 20 词 + 四路 rg；附录 A–F）。**2026-08-22 实施回写**：声明的每一面 / `boards-min` 是参数 / 词表 4/6 不许削齐。
- 作者：Grok（会话 2026-08-22：解耦 = 开关打包 + 真本源；全仓穷尽后回写）
- 复核：2026-08-22 抽查七条核心事实全部成立（正典 / timeline 分叉 / prefetch 引用 / `params.json` / dual_blind 弱口径 / 开根四变体 / `:478`）。改了四处会让第 1 步或门禁落空的判据：**原稿的门禁检法对 `daily_review.py` 实测覆盖为零**（§3.1 / §7.4-1）、**第 1 步是语义收紧不是纯重构**（§8）、`params.json` 定向（§7.1）、§5 表混了「开关」和「工单」。与开关板稿的 `default-v1` 口径已对齐（§7.3）。
- 范围：干净树 `docs/capability-switchboard` ← `gitea/main@4e0c6bf5`。算数 / 说明书 / 路由共一 id。实施改生产路径，但**生产默认读空集合**，与本模块不存在时一致。不合 `main`。
- 父稿：
  - `2026-08-22-capability-switchboard-design.md`（开关板：工具/核验/提示词零件；本文是**另一族**开关，禁止抄进 `allowed_capabilities`）
  - `2026-08-19-local-code-map-design.md`（审查正门：`scripts/code_map.py`；空/缺层不得报结构完整性）
  - `2026-08-20-asof-prefetch-dual-red-design.md`（把 `theme_lifecycle_timeline.is_double_red` 误标成「不要再抄」的正典——见 §3.3）
- 活状态不写本文。实施另开 `docs/superpowers/plans/`。

> 本文不是施工计划。第 0 步可以只钉正典 + 漂移测试，不动 loop。

---

## 0. 一句话

**关正典 ≠ agent 忘了双红。** 领域口径今天拆在三处：算数（SQL / `is_*`）、说明书（思考宪法 / 题型硬字段 / 门文档）、路由特例（问句正则）。原件和复印件必须打成**同一个开关 id**；关了它**声明的每一面**。真本源是 `import`，不是再抄一遍阈值。

「三面」是上限，不是定额。实测只有 `double-red` 三面俱全；`capacity-top3` 等只有算数+说明书；`single-red` 只有算数；`dated-market-topic` 只有路由。正控 = **声明了几面验几面**。硬要三面会把只有两面的谓词判成失败——那是判据错，不是开关坏。

判别：`default-v1 ⊕ predicate.<id>=off` → 它声明的每一面都变。不是「模块互相不认识」，也不是「每个谓词都必须三面一起灭」。

---

## 1. 审查账（先回答「算不算全量 / 走没走 code map」）

### 1.1 上一轮：不算全量，也没用 code map

上一轮只在本开关板树里 `rg` 字面量（`pct_chg > 0 AND diff_ratio > 10`、`sqrt(amount)`、`>=9.8`）。那是**字符串复印件扫描**，不是全量审查。

没做的：

- 没跑 `scripts/code_map.py`（设计正门规定的单一查询门面）
- 没看 doors 自己有没有把正典指错
- 没按符号找「同名函数两份实现」
- 没区分「实验脚本复印件」和「进 episode 的复印件」

### 1.2 第二轮：code map 20 词 + 四路 rg 穷尽本仓

结构图底：`/Users/a77/fwp-wt-code-map-land` @ `f4999051`，`code_map.py status` → **ready n=17411 @f499905**。20 个符号/中文词逐条 `query`（收据 §2.1）。

字面量底：本树 `4e0c6bf5`（`gitea/main`）。四路并行 `rg`：

| 路 | 穷尽对象 |
|---|---|
| A | 双红：10 组模式（词 / 常量 / SQL / 弱口径） |
| B | 单红 + 涨停分叉 + 其它硬阈值 |
| C | 开根加权四变体 + 容量前三 + 路由正则抄写 |
| D | L1–L4 定义正文 + 思考宪法 + 工具说明书 + 偏离度/放量/回流/VIEW |

源码 / 脚本 / spec / skill **逐文件**。生成物（`复盘/daily`、矩阵 HTML、eval runs、exports）**按目录计数**，不把日报正文当正典。实验 `_scripts` **16 个手抄 SQL 全部列出**（附录 A）。

### 1.3 本轮对「本仓」算穷尽；下面这些仍不是谓词源

| 仍没做 | 为什么不必冒充漏审 |
|---|---|
| code map `recall` 探针 | `recall=untested`；召回失败 ≠ 没有复印件 |
| vault / 知识库仓 `wiki/entities` | 外仓，不是本仓谓词 |
| 主仓脏树未跟踪的 `复盘/daily/2026-08-*` | 不在 `gitea/main`；本审查底是干净树 |
| 工程数（超时、容差、`19.80` 假数字题） | 不是领域谓词 |

**结论（第 0 步后收紧）：干净树里「领域口径复印件」已按`scripts/check_double_red_copies.py`的三种形状穷尽，以扫描器输出为准，不以人读过一遍为准。** 第 0 步跑门禁又抓出两处人工那轮漏掉的生产复印件（`ask_blocks.py` / `market_analogs.py`，§3.1）——漏法是**字面搜索按标识符名找，变量改个名就漏**。

宣称「没有第二份 X」要三样齐：跑扫描器（字面形状）+ 跑 §2 表的 code map（具名常量/同名函数）+ 人读散文（两者都不覆盖，如 `daily_review.py:1228` 图例）。少一路就会得出假结论。

---

## 2. 方法：两路缺一不可

代码地图三层压成一句「完整性」是设计禁止项（`2026-08-19-local-code-map-design.md` §2）。本审查对号：

| 层 | 本审查用它找什么 | 它找不到什么 |
|---|---|---|
| **doors** | CLAUDE/AGENTS 把口径指到哪 | 源码里第二份 `def is_double_red` |
| **structure** | 同名函数、import 得到的符号 | `DOUBLE_RED_SQL` 字面、SQL 抄串、中文说明书 |
| **narrative** | wiki 是否只是 door 投影 | 与 doors 重复时不增加新正典 |
| **rg 字面量** | SQL 抄串、`sqrt(...)`、`>=9.8`、思考宪法里的公式 | 「同一个函数名写了两遍」——`rg DOUBLE_RED_SQL` 看不到 timeline 那份 |

替代方案：

| 方案 | 能抓到 | 漏什么 | 结论 |
|---|---|---|---|
| **A. code map + rg** | 双名函数 + 抄串 + 门漂移 | 未索引的常量、未入库的中文 | **选定** |
| B. 只 rg | 抄串 | `theme_lifecycle_timeline.is_double_red` 与 `signals.is_double_red` 同名两实现 | 上一轮就是这个缺口 |
| C. 只 code map | `is_double_red` 两处 | `DOUBLE_RED_SQL`、开根加权、单红、思考宪法公式 | 会误报「没有第二份 SQL」 |
| D. 只读 CLAUDE.md | 人话定义 | 正典其实在 `signals.py`；门自己指去 strategy1-matrix | 门已漂 |

这和 RAG 里「向量 + BM25」是同一形状：一层召回符号，一层召回字面；单路会静默漏。别的仓审「业务口径有没有第二份」也能用。

### 2.1 code map 收据（land 树，20 词，2026-08-22）

| query | doors | structure | 判定 |
|---|---|---|---|
| `is_double_red` | missing | **ok n=2** | **唯一标红重复实现**（signals + timeline） |
| `DOUBLE_RED_SQL` / `DOUBLE_RED_DESCRIPTION` | missing | missing | 模块常量图不索引 → **必须 rg** |
| `DOUBLE_RED_PCT` | missing | ok n=1（挂到 signals 函数） | 真身在 timeline；图挂错文件 |
| `is_single_red` / `SINGLE_RED` / `WEIGHTED_STRENGTH` / `limit_approx` | missing | missing | 无符号正典 |
| `开根加权` / `容量前三` / `sqrt` | missing | missing | 中文/内建 → **必须 rg** |
| `in_capacity_top3` | missing | missing | dict 字段，图看不见 |
| `mainline_context` | ok | ok n=9 | 能力拆分，不像两套算法 |
| `information_cutoff` | missing | ok n=20 | 属性转发，不像两套截止日 |
| `REFLOW_CONFIRM_DAYS` / `MAINUP_CONSECUTIVE` | missing | ok n=2 | **同文件**两个消费者 |
| `load_theme_daily_rows` / `resolve_theme_alias` | missing | ok n=1 | 单点干净 |
| `is_limit` | missing | ok n=2 | 模糊命中，不是重复 `>=9.8` |
| `detect_turning_points` | ok | ok n=6（单脚本） | 本批唯一三层都有货 |
| `双红` / `涨停` / `signals.py` | 见上轮 | 中文/文件名 | doors 有、structure 常空 |

`vault=unavailable`、`recall=untested`。缺边 ≠ 没有路（CRG 本仓调用边约 1/3）。

---

## 3. 已核实事实（实施时不要再探一遍）

底：谓词源码以本树 `4e0c6bf5` 为准；结构查询以 land 树 `f4999051` 为准。

### 3.1 双红：正典在 `signals.py`，第二份函数在 timeline

```text
market_feature_store/signals.py
  DOUBLE_RED_SQL = "pct_chg > 0 AND diff_ratio > 10 AND amount > 500"
  is_double_red(pct_chg, diff_ratio, amount)  # 拒 bool；只要 int/float/Decimal
```

`intelligence/services/theme_lifecycle_timeline.py`（**注意路径：在 services，不在 `market_feature_store/`**）**另写**：

```text
DOUBLE_RED_PCT / DIFF / AMOUNT = 0.0 / 10.0 / 500.0
def is_double_red(row: dict) -> bool   # 只拒 None；float() 其余类型
```

阈值此刻相同，**边界已经不一致**：`signals` 把 `True` 当非法（返回 `False`，不抛）；timeline `float()` 会把 `True` 当成 `1.0`。字符串 `"501"` timeline 能过、signals 不过。正典严格**收窄**于复印件——所以第 1 步不是纯重构，见 §8。这就是复印件开始漂的现场，还没等人改 500→600。

**跨层已清障**：timeline 在 `intelligence/services/`，正典在 `market_feature_store/`。`scripts/layer_audit.py` 只禁 `services → intelligence.runtime`，**不禁** `services → market_feature_store`；`market_timeseries.py` / `metric_spec.py` / `market_midterm.py` / `external_market.py` 已经这么 import（services 真 import 它的共 **4** 个文件；另有约 12 个只在 docstring/路径字符串里提到，不算先例）。§7.1 那条路是通的，不必再论证一遍。

已 `import signals` 且自己不写阈值（7）：`query.py`、`adapters/market.py`（双红查询）、`market_timeseries.py`、`metric_spec.py`、`market_midterm.py`、`api/daily_reports.py`（只要 DESCRIPTION）、`theme-fermentation-tracer/scripts/trace.py`。

**穷尽后新发现的影子（附录 A 全表）：**

| 影子 | 问题 |
|---|---|
| `theme_lifecycle_timeline.py` | 第二份 `def is_double_red` + 三个 float |
| `asof_prefetch.py` | 从 timeline 引常量，不用 `DOUBLE_RED_SQL` |
| `market_regime_analogs.py` | 手写三条件 SQL |
| `daily_review.py` | **混合**：`:9` import `DOUBLE_RED_SQL`、`:938` 用它，另有 `:404` / `:613` / `:708` 手写 SQL 三条件、**`:478` 手写的 Python 内联比较** `pct > 0 and diff > 10 and amount > 500`（驱动日报 🔥 标记），以及 **`:1228` 图例散文抄写三阈值**（中文措辞，与 `DOUBLE_RED_DESCRIPTION` 又是第二种写法） |
| `evolution/params.json` | **第三份阈值** `double_red.pct_chg_min/diff_ratio_min/amount_min`；`strategy1.py` 读 JSON 不读 signals |
| `scripts/dual_blind_answers_to_md.py` + `dual_blind_auto_verdict.py` | **弱口径**：`pct>0 且 diff_ratio>0`，**没有 amount>500**，仍自称「双红」。名字相同、外延更大 |
| `intelligence/services/ask_blocks.py:677` | **第 0 步门禁新抓（人工 rg 那轮漏了）**：`_classify_mainline_volume_state` 写 `(amt is None or amt > 500)`——**NULL 成交额算双红**，还直接贴中文标签「真正双红/增量启动」。第三种口径：正典要 `>500`、dual_blind 不要 amount、它把 NULL 也收。在 ask 路径上、用户可见 |
| `intelligence/services/market_analogs.py:115` | **第 0 步门禁新抓**：`_signature` 里第四份严格阈值实现（`float(r[1])>0 and float(r[2])>10 and float(r[3])>500`）。注意与 `market_regime_analogs.py` 是**两个不同文件**，都在 |

生产 reimplement **16** 文件（原稿 14，第 0 步门禁又抓出 `ask_blocks.py` 与 `market_analogs.py` 两处；**含**两个 `dual_blind_*` 弱口径——§5 那句「另计」指**关法**另计，不是从总数里减掉。数字口径以本行为准，§11-5 对账用这个数）；实验脚本手抄严格 SQL **16**；文档手抄三阈值 **15**（附录 A）。`弱双红` 字面 0 命中——弱的是口径，不是名字。

⚠ **那两处是「按文件穷尽」漏掉的，值得记住漏法**：人工那轮搜的是 `diff_ratio`，而这两处一个把变量名缩成 `diff`/`amt`、一个用 `float(r[2])` 下标取值——**字面搜索按标识符名找，改个名就漏**。所以 §1.3 的「已穷尽」要限定为「按三种形状穷尽，且以可复现的扫描器为准」，不是「人读过一遍」。

**复印件有三种形状，原稿的门禁检法只挡得住第一种：**

| 形状 | 例子 | 单行 `rg` SQL 字面能否命中 |
|---|---|---|
| SQL 抄串，单行 | 16 个 `_scripts`（`... and pct_chg>0 and diff_ratio>10 and amount>500`） | 能 |
| **SQL 抄串，跨行** | `daily_review.py:403-405` / `612-614` / `707-709`（每个条件各占一行） | **不能**——要 `rg -U` |
| **Python 内联比较（变量名已改短）** | `daily_review.py:478` `pct > 0 and diff > 10 and amount > 500` | **不能**——要 AST 或第二条正则 |

**实测（`4e0c6bf5`）：单行检法在 `daily_review.py` 上命中 0 处，而这个文件有 3 处跨行 SQL + 1 处内联 + 1 处散文图例（`:1228`），是本仓最重要的消费者。** 全树对比：单行/`-U` 两命令的文件差集里，唯一的生产文件就是它（绝对文件数随口径浮动，对账只用差集，见附录抬头）。§7.4-1 已按三条形状重写；散文图例三形状都不覆盖，走 §7.2。

### 3.2 门自己指错了正典

code map doors 对 `双红` 命中 CLAUDE.md：

> 严格双红定义（见 strategy1-matrix）：`pct_chg>0 且 diff_ratio>10 且 amount>500`。

strategy1-matrix 是**消费者**。可执行正典是 `signals.py`。思考宪法 `foresight_methodology.md` §七又手抄同一条 SQL。三份说明书，零处指向 `DOUBLE_RED_SQL`。

### 3.3 2026-08-20 预取稿选错了正典

`2026-08-20-asof-prefetch-dual-red-design.md`：

> 双红公式已存在、episode 没用 → `theme_lifecycle_timeline.is_double_red` … **不要再抄一套阈值**

当时 `signals.py` 已经存在，且 fermentation-tracer / metric_spec 已在 import。预取稿把**近处的复印件**写成了「不要再抄」的原件。`asof_prefetch.py` 模块注释仍写「阈值只引用 timeline」。这是「单一真本源」失败的标准形状：新功能就近取用，正典继续当没看见。

### 3.4 单红：没有符号，只有日报 SQL

`signals.py` **无** `SINGLE_RED_*` / `is_single_red`。code map 对这两个 query 三层全 missing。

唯一进日报的算式在 `market_feature_store/reports/daily_review.py`：

```text
pct_chg > 0 AND diff_ratio > 10 AND (amount <= 500 OR amount IS NULL)
```

三处已分叉：

⚠ **同一个 NULL，两处归进互斥的两类**：`daily_review.py:947` 把 `amount IS NULL` 算进**单红**，而 `ask_blocks.py:677`（第 0 步新抓）把 `amt is None` 算进**双红**并贴标签「真正双红」。建单红正典时必须同时钉死这两处的 NULL 语义，否则同一行数据会被两条路径判成两个互斥状态。

| 算式 | 文件 | NULL 成交额 |
|---|---|---|
| `pct>0 AND diff>10 AND (amount<=500 OR amount IS NULL)` | `daily_review.py:947` | **算单红** |
| `pct>0 and diff>10 and amount<=500` | `render_sw_l1_theme_matrix_html.py:177` | **不算** |
| `diff_ratio>10 AND amount<=500`（**漏 pct_chg>0**） | `docs/adapters-design.md:429` | 含糊 |

`get_single_red_themes` 只出现在 `docs/adapters-design.md`，`MarketAdapter` **没实现**。`perspective_lab` 的「缩量上涨且后排不跟」是另一句话，不是这条 SQL。关双红正典，这三处都还在。

### 3.5 开根加权：四套公式（⚠ 原稿「量纲不可比」是错的，2026-08-22 实测更正）

无 `WEIGHTED_STRENGTH_*`。短语「个股加权强度」在 `.py` **零命中**，只在宪法 / CLAUDE。code map 三层 missing。

**更正（第 2 步实测）**：原稿说「D 是亿元再开根，A 与 D 排序不可比」——不成立。
`daily_review.py:616` 那个 `amount_yi` 只是 `max(amount) AS amount_yi` 的**别名**，
同一列同一单位；四个变体读的都是 `fact_sector_stock_daily.amount`，样例值 3.9 / 1.81，
本来就是**亿元**。真正的差别只在**空值/负值怎么挡**（`GREATEST(amount,0)` vs
`amount or 0` vs 靠 WHERE 的 IS NOT NULL）。正典 `WEIGHTED_STRENGTH_SQL` 已建，
单位在 docstring 里写死；缺值返 `None` 不返 `0`（返 0 会把「不知道」排成「中性」）。

| 变体 | 写法 | 出现 |
|---|---|---|
| A | `pct_chg * sqrt(GREATEST(amount,0))` | strategy3/4、三个矩阵脚本 |
| B | `pct * math.sqrt(amount or 0)` | strategy1、6 个 `_scripts` |
| C | `sqrt(amount) * pct_chg AS weighted` | **`adapters/market.py` `_strong_stocks`**（agent 唯一运行时 SQL）、`daily_review` 启动股、`build_market_triggered_theme_brief` |
| D | `sqrt(b.amount_yi) * b.pct_chg` | `daily_review.py` 行业内 Top20（**已是亿元再开根**） |

A 与 D 排序不可比。说明书另写「开根加权强度 / 个股加权强度」（orchestrator / quality / 宪法），没有函数叫这个名字。排除：Sharpe 的 `np.sqrt(244)`、统计 `math.sqrt`、`weighted_gain`（不是开根）。

### 3.6 涨停：至少四条可执行口径，禁止并成一个开关

| 口径 | 正典/实现 | 不是什么 |
|---|---|---|
| 全市涨停家数 | `metric_spec.limit_up` → `fact_market_daily.limit_up` | 不是 9.8 |
| 题材热度 | `fact_theme_limit_heat*`；adapter **再加** `limit_up_count >= 2` 才进榜 | 表字段之上又一道门 |
| 策略近似 | `params.json` `limit_pct: 9.8`；`strategy4.py` 读参数；**render 脚本焊死 `>=9.8`** | 20cm 票涨 9.8 也算 |
| 真涨停价 | `scripts/moneyflow/moneyflow.py` 昨收×1.10/1.20/1.05；`scan_limitup.py` 用 `UpperLimitPrice` | 不是 ≥9.8 |

`research/.../strategy4-dual-engine-regime-validation.md` 还写过 `≥9.8/19.8`。code map `涨停` 只回热度表门，看不到 9.8。

### 3.7 路由词 ≠ 谓词，但必须进同一开关族

`query_understanding.py` `_DATED_MARKET_TOPIC_RE`：

```text
双红|涨停|跌停|连板|梯队|断层|主线|新高|新低|…
```

这是「带日期的盘面复盘题」触发词，不是 `is_double_red`。关算数、留这个正则 → 题仍进 daily-review 路由，答案改口或空壳。所以路由是开关的**第三面**，不是第四个无关模块。

`_DATED_MARKET_TOPIC_RE` 整段交替串全仓**只此一份**。拆开抄的词表/正则（附录 C）：

- 「主线」：本文件另 3 处 + `answer_orchestrator._MARKET_LEVEL_STATE_WORDS` + `evidence_capabilities._MARKET_SUBJECT_MARKERS` + `task_frame` 两处比较正则
- 「涨停/跌停/连板/涨家数」：`task_frame._is_financial_task`、`turn_controller._FINANCE_PATTERN`
- 归因四词：`evidence_capabilities` **注释承认对齐** `_CAUSE_*`
- 展望/研判：`answer_orchestrator` 词表 + `route_table.JUDGMENT_REQUEST_PATTERN`

`mainline_context` 读 `fact_mainline_*`，**不算**容量前三。容量前三是 `industry_1/2/3` + `top3_industry_ratio`，派生布尔 `in_capacity_top3`（adapter）或 `in_top3_industry`（strategy4）。三个 id 禁止绑成一个。

### 3.8 思考宪法 vs 未合入判读基线

本底 **无** `reading_baseline.py`（在 `feat/reading-rules-baseline-batch1`）。`foresight.py` 注入 `foresight_methodology.md`。开关板稿已标「他树候选」。本文把方法论里的**公式抄串**算复印件；把「判断倾向 / KOL 判读」留给那棵树，不在这里发明第二份阅读宪法。

### 3.9 穷尽后仍不第一刀（已审计，不是没扫）

| 族 | 穷尽结论 | 为何不第一刀 |
|---|---|---|
| `information_cutoff` | 定义句 4 处（contract / honesty_gates / factory / protocol），语义已收口 | 不是盘面三阈值 |
| 板块 published VIEW | 机制正文几乎只在 CLAUDE.md；代码在 `sector_universe.py` / `db.py`；「是 VIEW」手抄多处 | 写入纪律 |
| L1–L4 | **6 套词表 / 8 文件**（§3.10） | 改层名炸知识库 |
| 12 个 capability | registry description **无**双红公式 | 已是开关板工具行 |
| 放量>10% | 正典 `turning_points.VOLUME_SURGE_PCT=10`；日报另用 `amount_vs_yesterday_pct>10` 且 `volume_ratio` vs 120 | 另一族 |
| 连板 ≥N | 抓取默认 3、入库默认 2、日报展示 ≥3 | 名单长度会对不上，另开单 |
| 回流天数 | 常量只在 timeline：`REFLOW=2` / `MAINUP=3` / `EBB=5`；策略1 `dr_hits_min:3` 是**题材个数**不是连续日 | 两套「3」禁止一个开关 |
| 偏离度 / UP | 指数周均偏离 vs `UP=MA26+0.764×STD26`，同名不同物 | 另开单 |

### 3.10 L1–L4：6 套定义，L0 已冲突

| 套 | 路径 | 和别人的差别 |
|---|---|---|
| 1 | `skills/theme-radar/references/evidence-layers.md` | 唯一带「能/不能」；**L0=外部定义** |
| 2 | AGENTS Theme-Radar 段 + `foresight_methodology.md` §四 | 互译压缩，无 L0 |
| 3 | `answer_quality.py` + 两份 `docs/learning/stock-*` | L1=「观点叙事」，近逐字互抄 |
| 4 | `answer_model.py` `_PRESENTER_REPLACEMENTS` | 对外改写 |
| 5 | `research_judge.py` `LAYER_ORDER` | **L0=图谱登记**，与套 1 同名不同物 |
| 6 | `pdf_ingest_lint.VALID_EVIDENCE_LAYERS` | 无 L0/L4，有 candidate；`dual_blind_forecast` 另瘦枚举 `{L1..L4}` |

工具说明书（`_TOOL_CONTRACTS`）**不教**双红/开根/容量前三。题型硬字段在 `answer_orchestrator.py` + `answer_quality.py` **两份互抄**（附录 D）。关工具契约关不掉模型背公式。

---

## 4. 术语

| 词 | 含义 |
|---|---|
| **谓词** | 一条可判定的领域口径（双红 / 单红 / 开根加权 / 涨停近似）。不是 tool。 |
| **正典** | 唯一可执行定义。改它，所有消费者跟着变。 |
| **复印件** | 阈值、SQL、同名函数、说明书公式、路由词。改正典它不跟着变。 |
| **开关族** | 一个 id 绑三面：算数、说明书、路由特例。 |
| **焊点** | 关了日报/矩阵会空、或一拧动三件无关事。进清单但标 `welded`，不进第一期实验臂。 |

人话：工具开关关的是「能不能调用 `finance_query`」；谓词开关关的是「双红这三个数还算不算、还讲不讲、还特不特道路由」。

---

## 5. 开关族清单（第一期只登记，默认 on）

id 前缀 `predicate.`，**禁止**写进 `ResearchTaskContract.allowed_capabilities`。

| id | `canonical` | 正典（目标） | 今日复印件（至少） | 关法（三面） | 第一期 |
|---|---|---|---|---|---|
| `predicate.double-red` | **exists** | `signals.DOUBLE_RED_SQL` + 一份 `is_double_red` | timeline 函数；prefetch；daily_review 手写 SQL + `:478` 内联；`params.json`；regime_analogs；14 生产 + 16 实验脚本；15 份文档 | 算数 import；说明书引用 DESCRIPTION；路由「双红」跟 id | **先收真本源**。弱口径标 `alias≠` 不得叫双红 |
| `predicate.single-red` | **missing** | 尚无 | 日报 NULL 算 / 矩阵不算 / adapters-design 漏 pct | 先建正典（先钉 NULL） | 工单，不是开关 |
| `predicate.sqrt-weighted` | **missing** | 尚无；须声明 amount 单位 | 变体 A/B/C/D（D 是亿元） | 先建正典 + 单位 | 工单；agent 侧优先收 `market.py` |
| `predicate.limit-approx-9p8` | exists（在 `params.json`） | `params.json` `limit_pct` | render **焊死** 9.8 | 禁止并进 `limit_up` | 与表字段分叉 |
| `predicate.limit-heat-min2` | exists | adapter `limit_up_count>=2` | 仅此一处可执行 | 进榜门槛，不是家数指标 | 登记，勿与 9.8 合并 |
| `predicate.capacity-top3` | exists | `industry_1/2/3` + ratio | `in_capacity_top3` vs `in_top3_industry` | 与 `mainline_context` 分 id | 登记 |
| `predicate.dated-market-topic` | exists | `_DATED_MARKET_TOPIC_RE` | 词表拆抄 6+ 文件 | 关 = 不再特道路由（**前置：正则可生成**，见 §8 第 2.5 步） | 生成全部正则，禁止再手抄 |
| `predicate.volume-surge-10` | exists | `VOLUME_SURGE_PCT` | 日报转点日另加 volume_ratio 120 | 勿与双红打包 | 降级 |
| `param.boards-min` | n/a（`kind=parameter`） | 无谓词正典 | scrape `--min-boards` 默认 3 / 入库 `--min-boards` 默认 2 | **不是谓词**：两个阶段各自的 argparse 默认。不进默认盒、不进实验臂 | 配置一致性问题（抓 ≥3、入 ≥2，库里永远没有 2 板行） |
| `predicate.mainup-consecutive-3` | exists | timeline `MAINUP_CONSECUTIVE` | 策略1 `dr_hits_min:3` 是个数 | 禁止与 hits≥3 合并 | 登记 |
| `reading-baseline` | other-branch | 他树 | 本底无 | 开关板已排除 | 不进实验臂 |
| L1–L4 层表 | **contested**（6 套） | theme-radar `evidence-layers.md` | 6 套词表 | 另开单；先禁止新抄套 3 | 不进本 runner |

**`canonical` 列是筛子，不是标签。** `missing` / `contested` 的行**不是开关**——正典还不存在，没有东西可关；它们是「待建正典」的工单。原稿把这些行标 `welded`，会把「关不掉（焊死）」和「没得关（不存在）」压成同一个词，第 0 步的 JSON 里就分不出哪些行可拧。落表时 `canonical != exists` 的行必须能被一句查询筛掉，且不得进任何实验臂。

`research/market-hypothesis/_scripts/`：**不进默认盒**。`dual_blind` 弱口径若进用户可见「双红列表」，集合比正典大一圈——第一期必须改名或改公式。

---

## 6. 两层解耦（已对齐，不要再辩）

1. **开关打包**：算数 + 说明书 + 路由特例共一 id。默认 on，生产能力不变。实验 off，**声明的每一面**都灭。不是每个谓词都有三面。
2. **真本源**：复印件改 `import` 正典。禁止再在新模块写 `DOUBLE_RED_PCT = 10`。

错误拆法：timeline 和 signals「互不认识」又不接线 → 预取稿就会把近处复印件封为正典 → 关 `signals.py` 时 episode 预取还在报双红个数。

完全解耦若理解成「各写各的、别 import」，会削默认生产能力（日报、预取、metric 对不齐）。允许的解耦是**接线后能整族拔掉**。

---

## 7. 设计（第 0 步可停在测试）

### 7.1 正典模块

不新建第二套「领域插件」。在 `market_feature_store/signals.py`（或同级 `predicates.py`，**只准一个文件**）登记：

- 双红：已有，函数签名以 `signals.is_double_red(pct, diff, amount)` 为准。
- **三值提成具名常量、`DOUBLE_RED_SQL` 由常量生成**（第 1 步顺手做）：现状三个阈值只活在 SQL 字符串和函数体字面里，没有具名常量——下面 `params.json` 的一致性测试会没有可比对象，§8 第 1 步之 3 的 monkeypatch 也无处 patch。
- timeline 的 `is_double_red(row)` 改成薄包装：拆字段后调用正典。**禁止保留第二份阈值常量。**
- 单红 / 开根加权：有调用方再加常量 + SQL 串 + 纯函数；测试钉字面，仿 `test_theme_fermentation_semantics.py`。

`asof_prefetch` 的 count SQL 改用 `DOUBLE_RED_SQL` 或正典参数，**禁止**再从 timeline import 三个 float。

**`params.json` 定向（原 §12 Q6，已决）：不改成从 `signals` 导出。** 它带 `params_version` + `params_history.md`——那三个数是**版本化的实验输入**，不是口径常量；导出会切断历史回测记录里 `params_version` ↔ 实际阈值的对应关系，旧结论从此不可复现。改为加一条**一致性测试**：`params.json` 的 `double_red.{pct_chg_min,diff_ratio_min,amount_min}` 必须等于 `signals` 当前三值，不等即红——要么改参数，要么在 `params_history.md` 里显式声明这是有意的实验偏移。既保住可复现性，又抓得住无意漂移。

（可迁移：**配置里的数值分两种**——「口径常量」该收敛到单一真本源，「实验参数」该保留独立版本 + 一致性断言。把后者也强行导出，等于用单一真本源换掉了可复现性。）

### 7.2 说明书

`DOUBLE_RED_DESCRIPTION` 已存在。思考宪法表格、metric 口径、CLAUDE 门应**引用模块名 + 常量**，不手抄 SQL。CLAUDE 那行改为「见 `market_feature_store/signals.py`」，不要见 strategy1-matrix。

第一期允许门/宪法仍是人维护的复印件，但必须加一条漂移测试：宪法正文包含 `DOUBLE_RED_SQL` 的当前字面（或从源码生成的片段）。生成优于手抄（搭建模式「单一真本源且生成」）。

**代码里的散文抄写同此列**：`daily_review.py:1228` 的 🔥 图例（三阈值中文，与 `DOUBLE_RED_DESCRIPTION` 又是两种措辞）改为从 DESCRIPTION/常量生成，或进同一条漂移测试——§7.4-1 的三形状门禁都抓不到散文，这一处不点名就会漏。

### 7.3 与开关板的墙

| 开关板 | 本文 |
|---|---|
| `finance_query` 等 12 个 capability | 不表达「双红三个数」 |
| `default-v1` 冻的是**授权面派生函数符号 + 非工具行默认值**（本仓授权面逐 frame 解算，不是一份可冻名单——见开关板稿 §5.3） | 谓词默认 on，**不**出现在工具名单 |
| 独立 runner 一次拧一颗 | 谓词臂另开，或同一 runner 但 id 前缀不同；**一次仍只拧一颗** |
| 禁 Cordis / 禁 `allowed_tools` 进 Profile | 同样适用 |

第一期 0–1 步（真本源收口）**不依赖**开关板 runner 落地。

### 7.4 棘轮

1. 新代码禁止出现双红阈值字面。**原稿写的「`rg` 那条 SQL 失败」实测覆盖为零**——`daily_review.py` 五处复印件，单行 `rg` 一处都抓不到（四处是跨行 SQL、一处是 Python 内联）。测法必须三条：
   - (a) **SQL 字面，单行**：`rg` 命中那条 SQL → 失败。
   - (b) **SQL 字面，跨行**：同一条但加 `-U` + 限长间隔（`[\s\S]{0,120}?`）→ 失败。**缺这条，`:404` / `:613` / `:708` 全部漏网**；实测只有加 `-U` 才把 `daily_review.py` 捞出来（单行/跨行两命令的文件差集里，唯一的生产文件就是它）。
   - (c) **Python 内联比较**：AST 规则，`> 0` / `> 10` / `> 500` 落在同一条 `BoolOp` 比较链里 → 失败。缺这条，`:478` 漏网——把变量名从 `diff_ratio` 改成 `diff` 就能绕过 (a)(b)。
   
   例外：`signals.py` 与其钉字面测试。
   
   **豁免用目录规则，不用文件清单**：`research/market-hypothesis/_scripts/**` 整目录免检。手维护的路径 allowlist 会立刻变成第 17 份复印件，且它自己没有棘轮——附录 A 的 16+15 就是前车之鉴。文档那 15 份走「生成 / 引用」（§7.2），不进豁免名单。
2. 仓内只准一个 `def is_double_red` 带阈值；其余必须 import。code map `query is_double_red` 的 structure 命中实现应变 1（测试文件除外）。
3. 新谓词先登记正典再写 SQL。
4. 宣称「已解耦」必须能指出开关 id **声明的每一面**的符号；只改了一个文件不算。没声明的面不许为了整齐补造。

---

## 8. 四步（每步可停）

### 第 0 步：清单测试

把 §5 表落成机器可读行（可与开关板 JSON 同文件、不同 prefix），每行带 `canonical`。测试两条：`is_double_red` 的生产实现路径只有 `signals.py` 一处阈值；`canonical != exists` 的行能被一句查询筛掉且不出现在任何实验臂。还没有行为变化。

### 第 1 步：双红真本源（**先差分，再切**）

timeline + asof_prefetch 改 import。

⚠ **这一步不是纯重构，是语义收紧**：正典拒 bool/字符串（返回 `False`），timeline `float()` 全收。切过去之后，任何喂 `True` 或 `"501"` 的调用点判定会从 `True` 翻成 `False`。DuckDB 出的 `Decimal` 正典收，但夹具 / JSON / CSV 来的行常常是字符串——**「现有测试保持绿」是假设，不是判据**（现有测试未必覆盖到那些行）。

过关顺序：

1. **差分**：取一批真实行（至少覆盖 prefetch 与日报各自的取数路径），两份实现各判一次，输出判定不同的行数 + 样例。差集为空，或每条都能解释（并写进收据），才允许切。
2. 切 import；现有测试保持绿。
3. 加一条：改正典阈值（测试 monkeypatch）时 prefetch 个数口径跟着变。

（可迁移：**去重两份实现之前先跑差分**。两份「看起来一样」的判定函数，边界条件几乎总有出入；不差分就切，等于把一次静默的行为变更混进一次重构里，出问题时归因会指向无辜的地方。）

### 第 2 步：单红 / 开根加权正典

只收**进 agent 或日报**的调用方。evolution / 矩阵脚本可第二批。

### 第 2.5 步：路由正则生成化（第 3 步的前置，别混进第 3 步）

`_DATED_MARKET_TOPIC_RE` 是**整段交替**，「双红」只是其中一词——要按 id 摘词，正则必须先能生成。做法见附录 E：**共享词汇原子** `intelligence/services/market_topic_terms.py`，各处自己组合外延。收口四处（`query_understanding` / `answer_orchestrator` / `evidence_capabilities` / `task_frame`）。`route_table` 与 `turn_controller` 是另外两套判据，**不许削齐成六处同一张单子**——`query_understanding` 刻意不收「板块」，`evidence_capabilities` 收。

**这是一次比第 1 步更大的重构**（词表收口），原稿把它藏在第 3 步里，照那个排法第 3 步会卡住。单列一步，可停。照字面「生成六处」会改掉路由，那是 §9-C 失败形状的镜像。

### 第 3 步：说明书 + 路由共 id

宪法/CLAUDE 改为引用或生成。`predicate.double-red=off` 时：预取不报个数、方法论不注入该行、dated-topic 不因「双红」二字特道路由。默认盒仍 on。

拧动只发生在 runner 的 composition root：`predicate_faces.using(disabled)` 包住 `adapter.handle`。生产路径读 contextvar 默认空集合，loop 不加产品 if。说明书那一面用真宪法正文验（`foresight_methodology.md`），不另造样例。

第 1 步没过，禁止做第 3 步「能关」——否则关的是空开关，复印件还在说话。第 2.5 步没过，第 3 步的路由那一面根本无从下手。

---

## 9. 方案比较

| 方案 | 内容 | 结论 |
|---|---|---|
| **A. 正典模块 + 开关族三面** | import 收口，再打包 | **选定** |
| B. 只写文档「请记得改三处」 | 零成本 | 否：2026-08-20 已失败一次 |
| C. 模块互不 import，靠约定阈值 | 「解耦」 | 否：削齐、必漂 |
| D. 每个谓词一个 Cordis 插件 | 热插拔 | 否：与开关板同一条禁令 |
| E. 把谓词塞进 `allowed_capabilities` | 少一张表 | 否：关 `finance_query` 会误关全部盘面数 |

---

## 10. 验收（实验树，不是合 main）

1. 本文与开关板互指；谓词 id 不出现在 capability 元组。
2. 第 1 步后：生产代码只有一份双红阈值；`code_map query is_double_red` structure 不再出现第二份带阈值的 `def`。
3. `asof_prefetch` 不再 import `DOUBLE_RED_PCT|DIFF|AMOUNT`。
4. 漂移测试**三条都在**（§7.4-1）：单行 SQL / 跨行 SQL（`-U`）/ Python 内联。自检方式：把门禁指向改前的 `daily_review.py`，**必须报出 4 处**（3 处跨行 SQL 块 + 1 处内联；2026-08-22 于 `4e0c6bf5` 实测）；报 0 处说明装的是原稿那版单行检法。`:1228` 散文图例是该文件第 5 处复印件但**不在门禁覆盖内**（三形状都抓不到散文），走 §7.2 生成/漂移测试，验收时单独点名。
5. 豁免是**目录规则**，不是文件清单（`rg` 一下确认没有手维护的路径 allowlist）。
6. 第 1 步的**差分收据**在（判定不同的行数 + 样例 + 处置），不是只有一句「测试仍绿」。
7. `params.json` 一致性测试在；`params_history.md` 未被改写。
8. 默认盒行为与改前对照（日报双红个数、预取口径、日报 🔥 标记数）一致。
9. 审查方法写进交接：先 `code_map.py query`，缺层再 `rg`，`rg` 之外还有内联形状要人读；禁止只报其中一路。

---

## 11. 对后续 agent 的指令

1. 不要在主仓脏树或 `feat/reading-rules-baseline-batch1` 上实施。
2. 不要把 timeline 再写成双红正典。预取稿 §3 那行作废，以本文 §3.3 为准。
3. 不要为了「解耦」删掉 `from market_feature_store.signals import …`。
4. 不要把 `>=9.8` 并进 `limit_up` 指标开关。
5. 宣称「没有第二份 X」必须对上附录 A–F + 再跑 code map；缺层写 missing，禁止只报一路。新抄双红 SQL 先对照附录 A 的 14+16 名单。
6. 实施计划用 `docs/superpowers/plans/2026-08-22-domain-predicate-coupling.md`，别把步骤写回本文。
7. 第 1 步切 import **之前**先出差分收据（§8）。「现有测试仍绿」不是判据——正典比复印件严格，测试未必覆盖到会翻转的那些行。
8. 说「已经没有第二份双红」之前，附录抬头那**两条** `rg` 都要跑。只跑 SQL 那条，会漏掉变量名改过的内联比较。

---

## 12. 开放问题（不挡第 0–1 步）

1. `signals.py` 扩文件 vs 新建 `predicates.py`：选一个，禁止两文件都有双红。
2. 思考宪法是否改为构建时生成片段（棘轮强）还是测试钉字面（第 3 步可先钉）。
3. dated-topic 正则里的「涨停」跟 `predicate.limit-approx-9p8` / `limit_up` 如何共面——三词不要绑成一个 id。
4. 矩阵 HTML / 策略脚本第二批是否要进同一漂移门禁，还是 allowlist 到策略进化仓。
5. `daily_review` 手写 SQL 与 `{DOUBLE_RED_SQL}` 并存：第 1 步是否连 `:404` / `:613` / `:708` **加 `:478` 那处内联**一起收（3 处 SQL + 1 处 Python，共 4 处；`:1228` 散文图例另走 §7.2 生成）。
6. ~~`params.json` 从 signals 导出，还是 strategy1 改调 `is_double_red`~~ **已答（复核）**：两个都不选——保留独立三值 + 一致性测试，理由见 §7.1（导出会切断 `params_version` 与阈值的对应，旧回测不可复现）。
7. L0 冲突（外部定义 vs 图谱登记）是否先改裁判词表用词，不动 ingest。
8. 内联比较的 AST 规则要不要一并覆盖 `>= 9.8`（`predicate.limit-approx-9p8` 的 render 焊死处）：同一条规则能顺手带上，但会把策略脚本一起拦住——先定豁免目录再开。

---

## 13. 附录：穷尽清单（干净树 `4e0c6bf5`）

生成物按桶计数，不当正典。源码/脚本/spec 必须能在本附录对上号。

**行号会漂：本附录以「文件 + 形状」对账，不以行号对账。** 复核跑这两条（已在 `4e0c6bf5` 实测）：

```bash
# 形状一：SQL 三条件，-U 覆盖单行与跨行。缺 -U 会漏掉 daily_review.py 全部三处跨行 SQL
rg -nU 'pct_chg *> *0[\s\S]{0,120}?diff_ratio *> *10[\s\S]{0,120}?amount *> *500'

# 形状二：Python 内联比较，变量名任意。抓 daily_review.py:478 那一类
rg -n '> *0 .*and .*> *10 .*and .*> *500'
```

实测差距（2026-08-22 @ `4e0c6bf5`）：形状一去掉 `-U`（= 原稿单行检法）与带 `-U` 的**文件差集**里，唯一的生产文件是 `daily_review.py`（另一个是 2026-06-09 的旧 spec 文档）——**本仓最重要的那个消费者，靠原稿的单行检法一处都抓不到。** 绝对文件数不进对账：它随口径浮动（tracked/untracked、本文自身与后续 spec 也命中模式），对账只用「差集里有没有生产文件」这条不变量。

### A. 双红

**canonical（1）：** `market_feature_store/signals.py`

**import 正典、不写阈值（7）：** `query.py` · `adapters/market.py` · `market_timeseries.py` · `metric_spec.py` · `market_midterm.py` · `api/daily_reports.py` · `skills/theme-fermentation-tracer/scripts/trace.py`

**生产 reimplement（16）：** `theme_lifecycle_timeline.py` · `asof_prefetch.py` · `market_regime_analogs.py` · `daily_review.py`（混合）· `evolution/params.json` · `evolution/strategy1.py` · `evolution/strategy4.py` · `scripts/generate_strategy1_mechanical_row.py` · `backfill_strategy3_touch_matrix.py` · `build_market_triggered_theme_brief.py` · `render_sw_l1_theme_matrix_html.py` · `render_strategy4_dual_engine_matrix.py` · `dual_blind_answers_to_md.py`（弱）· `dual_blind_auto_verdict.py`（弱）· **`intelligence/services/ask_blocks.py`（NULL 算双红，第 0 步门禁新抓）** · **`intelligence/services/market_analogs.py`（第 0 步门禁新抓，与 `market_regime_analogs.py` 不同文件）**

**门禁基线（`scripts/check_double_red_copies.py`，字面形状）：16 处 / 11 文件。** 按**文件集合**对账、不按条数——同一文件里挪一处加一处条数会变、集合不变，要拦的是「又多一个文件自己写阈值」。基线钉在 `intelligence/tests/test_capability_switchboard.py`。
注意扫描器**抓不到** `theme_lifecycle_timeline.py` / `asof_prefetch.py`——它们用具名常量没有 `500` 字面，归另一个检测器（同名第二实现）管。两种形状要两个检测器。

**实验脚本手抄严格 SQL（16）：** `_scripts/double_red_anchor_stock_study.py` · `e001_candidates.py` · `e001b_add_0408_state.py` · `e001c_pool.py` · `e001c_reflow_alignment.py` · `strategy1_scan_events.py` · `strategy1_0408_0420_overview.py` · `strategy1_0408_0420_cohorts.py` · `strategy1_double_red_lifecycle_0603.py` · `strategy1_drawdown_risk.py` · `strategy1_forward_0604_0605.py` · `strategy1_full_window_0408_0605.py` · `strategy1_lifecycle_since_0408_0603.py` · `strategy1_limit_ma5_impact.py` · `strategy1_theme_cycles_0408_0605.py` · `strategy1_validate_sample.py`

**实验脚本无公式（2）：** `e001d_combo.py` · `strategy1_forward_lifecycle_rank_0605.py`

**文档手抄三阈值（15）：** `CLAUDE.md` · `docs/adapters-design.md` · `foresight_methodology.md` · `skills/strategy1-matrix/references/generation-flow.md` · `skills/sector-data/SKILL.md` · `skills/sector-data/references/execution-flow.md` · `条件格式公式.md` · `复盘/README.md` · `复盘/templates/daily-review-template.md` · `evolution/params_history.md` · specs `2026-06-08-strategy1-limit-ma5` · `2026-06-09-market-triggered-theme` · `2026-08-13-memory-analog-lifecycle` · `2026-08-20-asof-prefetch-dual-red` · 本文

**实验 md 手抄公式（5）：** `strategy1-cross-sample-validation.md` · `strategy1-0408-0605-full-window-selection.md` · `strategy4-dual-engine-regime-validation.md` · `E001-C-mainline-liquidity-pool.md` · `E001-C-reflow-peak-alignment.md`

**钉字面测试（6）：** `tests/test_theme_fermentation_semantics.py` · `test_theme_lifecycle_timeline.py` · `test_asof_prefetch_dual_red.py` · `test_prefetch_evidence_ordinal.py` · `test_acceptance_board.py` · `eval/cases/acceptance_cases.json`

**生成物（8 桶 / 约 340 文件，模式并集约 599）：**

| 目录 | 约数 |
|---|---:|
| `复盘/daily/` | 107 |
| `复盘/matrices/` | 7 |
| `复盘/selections/` | 1 |
| `docs/learning/forecast-review-ledger/` | 63 |
| `intelligence/eval/runs/` | 20 |
| `intelligence/eval/measurements/` | 3 |
| `market_feature_store/exports/` | 113 |
| `research/market-hypothesis/*.csv` | 26 |

只提词的源码/文档/测试/handoff/verification **不进漂移门禁**（改阈值它们不用改）。完整 mention 表在本轮检索记录里，实施时不必再扫。

### B. 单红

可执行：`daily_review.py:947`、`render_sw_l1_theme_matrix_html.py:177`。文档残式：`docs/adapters-design.md:429`。无 `is_single_red`。生成物含「单红」：`复盘/daily` 45、`复盘/matrices` 3。

### C. 开根加权（`.py` 实现穷尽）

- evolution：`strategy1.py`（B）、`strategy3.py`（A）、`strategy4.py`（A）
- scripts：`generate_strategy1_mechanical_row.py`（A）、`render_strategy4_dual_engine_matrix.py`（A）、`backfill_strategy3_touch_matrix.py`（A）、`build_market_triggered_theme_brief.py`（C）
- intelligence：`adapters/market.py`（C，唯一运行时）；`refresh_profile.py` 只写 docstring
- 日报：`daily_review.py`（C+D）
- 实验：`strategy1_theme_cycles_*` · `strategy1_limit_ma5_impact.py` · `strategy1_full_window_*` · `strategy1_drawdown_risk.py` · `strategy1_0408_0420_cohorts.py` · `double_red_anchor_stock_study.py`（皆 B）

### D. 题型硬字段（工具契约无公式）

`research_tool_registry._TOOL_CONTRACTS`：无双红/开根/容量前三。

`answer_orchestrator.py` 唯一「都必须进入推理」字面：容量前三、双红、单红/缩量上涨、涨停热度、新高集群、开根加权强度。同文件另 4 条近亲清单。

`answer_quality.py`：题材映射 / 双红演变 / 涨停结构 / 行业容量 / 盘面融合门槛 / 最终必须落回盘面——同一篮子，无那六字。

### E. 路由词表（共享原子，外延不许削齐）

词汇层单一真本源：`intelligence/services/market_topic_terms.py`。各处自己组合外延：

| 处 | 收「板块」 | 为什么 |
|---|---|---|
| `query_understanding._DATED_MARKET_TOPIC_RE` | **不收** | 收了会把 theme-research 抢走；over-routing 比 under-routing 更难发现 |
| `evidence_capabilities._MARKET_SUBJECT_MARKERS` | **收** | 主体词，命中后 `mainline_context` 才有意义 |
| `answer_orchestrator` / `task_frame` | 各自组合 | 与上面两处共享原子，不共享列表 |
| `route_table.JUDGMENT_REQUEST_PATTERN` | 不并入 | 展望/研判词，第三套判据 |
| `turn_controller._FINANCE_PATTERN` | 不并入 | 泛金融分道（题材/财报/公司），第四套判据 |

parity 断言「每一处仍等于它改前那一份」，外加一条不许削齐的守卫：`板块` 必须在 `_MARKET_SUBJECT_MARKERS` 里、且必须不在 `DATED_MARKET_TOPIC` 里。今日拆抄见 §3.7。

### F. 其它谓词（已扫，降级）

| 谓词 | 正典 | 复印件要点 |
|---|---|---|
| 放量>10% | `turning_points.VOLUME_SURGE_PCT` | CLAUDE、backtest docstring；日报转点日 + volume_ratio 120 |
| 连板≥N | **不是谓词**（`param.boards-min`） | scrape 默认 3 / 入库默认 2：两个阶段各自的 argparse，不削齐 |
| 连续双红≥3 | timeline `MAINUP_CONSECUTIVE` | 策略1 `dr_hits_min` 是个数 |
| 放量分歧 | 矩阵 `pct<0 & diff>10 & amount>500` | timeline 分歧=成交新高且 `diff≤0` |
| 涨停热度入榜 | adapter `>=2` | — |
| 行业集中度分箱 | sync `n<35/<=45` | 策略4 `top3r` 40–45 是亲戚 |
| 指数偏离 | `sh_deviation_pct` | market-overview steps |
| UP 偏离 | `MA26+0.764×STD26` | up-line skill；策略3 `touch_dev ±3` |
| published VIEW | `sector_universe.py` | CLAUDE 完整；AGENTS/sync/ops 各一句 |
