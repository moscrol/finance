# 设计：盘面题由组件包当第一执行者

- 日期：2026-08-24
- 状态：**P0 已落地**（离线绿；live / 合 main 未做）
- v1 → v2：落点从「拒收后走进 `_answer_market_review`」改成「四袋落在 owner 分叉之前」；`as_of` 从「传上界」改成「显式站立日必须精确命中当日」；C1 从「本单形状已对」改成「另一条路的回归锁」。见 §0.1。
- 来源：Knevo 四臂 A1/C1（2026-08-23）agent-run / trace-diff。核稿复验 2026-08-24。
- 实测目录：`~/.finance-runtime/four-arm-knevo-20260823/`
  - A1：`A1-market-overview/workbench-8792|8796|codex-component|live-toolkit/`
  - C1：`C1-future-date-no-data/` 同结构
  - 网页真源是 `continuous-episode.json` + `trace.jsonl`，不是 UI 的 `trace.json`
- 代码树：从 `gitea/main` 开干净树 `feat/market-watch-component-first`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`
  - `docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`
  - `intelligence/services/honesty_gates.py`（休市**判定**不改；Engine B **调用点**本单要补）

## 0. 一句话

`market_watch` 已经认出「该走模板」，也已经有总览块、主线块、严格双红 SQL、涨停热度适配器。卡住的是 **Engine A（`continuous_glm`）抢了成文权**：第一轮 0 工具空转到 `deadline_exhausted`，修复轮再补两袋，然后自由写。本单把第一执行者换成已经存在的盘面组件包；模型只写格与格冲突的残差。

**判别变量**（验收只锁这一条，v1/v2 未改）：冻结题「2026-07-23 今天市场怎么样」在模型开口之前，必须已经跑完四袋规定查询（总量 / 主线 / 严格双红 / 涨停热度），格内数字进公开稿且不可被模型改口径。不是「多调一次工具」，不是「稿子像不像 ReAct」，也不是「一定走进 `_answer_market_review`」。

人话：厨房里菜谱和食材都在。点菜员写了「要套餐」，后厨却让厨师先空等一分钟再随便抓两样。本单让套餐先出锅，厨师只解释两盘对不上的地方。

### 0.1 v2 核稿改定（[实测]，实施按本节不是按 v1 的 §5/§8）

方向与 §4 的 A/B/C 对照保留。v1 三个阻断级洞全部来自复验，不是推断：

| ID | v1 会让 P0 落不了地 | v2 |
|---|---|---|
| **洞 1** | §7.1 #2「走到 `_answer_market_review`」。拒收 A 之后，`is_market_watch_query` 会插入 `daily-review`；该 skill `role=workflow` + `can_own_answer=True`，`lane=workflow` 时兼容闸只看 role。指定日若存在 `<date>-daily-review.md`（A1 冻结日主树有 `2026-07-23-daily-review.md`），走 `prepare_existing_answer`，`_run_answer_query_with_watchdog` 不执行。四袋零调用。 | **选 (a)**：四袋落在 `if owner_output is not None` **之前**的汇合处。不选 (b) 把 daily-review 降成证据贡献者——那会改 `dated_market_review` 现有行为，推翻 §1.2。 |
| **洞 2** | 「把 `as_of` 传进两个块」不够。块查询是 `trade_date <= as_of ORDER BY desc LIMIT 1`。`<= 2026-07-25` 实测回到 `2026-07-24`。叠加 `_resolve_market_data_context`：有 `requested_date` 就原样返回、不查库，正文写「截至 07-25」、块里是 07-24 的数。§6.2「数来自该日行」抓不住——数确实来自真行，只是不是问句日。 | 显式站立日必须 `trade_date = ?`。0 行就是 0 行，禁止 `<=` 回落邻日。`_resolve_market_data_context` 是第四个日期解析点：库无该日行时不得回显问句日。 |
| **洞 3** | §3 事实 1 把 A1/C1 写成同一个 `market_watch` 信封。`is_market_watch_query("2026-07-25 市场怎么样")` 实测 `False`（缺「今天/今日」）。C1 冻结 controller：`lane=research`，`question_type=general_finance_qa`，`generate=lane_direct_answer`。休市句在旧座位上：`lane_generation` 只对 `quick_fact` 调 `calendar_disclosure`；`with_calendar_disclosure` 的调用点在 `continuous_turn_adapter` 与 `lane_generation`，**Engine B 的 ask.py / ask_blocks.py / ask_synthesis.py 零调用**（负面断言，三处都查过）。真正会走进新座位的休市题是「2026-07-25 **今天**市场怎么样」，它会同时撞洞 2，且拿不到休市句。 | 事实 1 拆开。#5 保留为**另一路径**回归锁。P0 另加「2026-07-25 今天市场怎么样」。Engine B 补休市披露调用点，不改判定函数。 |

换座位的可复用失败形状（已回写 `~/harness-reference/BUILD.md` 模式 5）：**先查被腾空的椅子上还坐着什么。** v1 只盘点「要搬走的四袋」，没盘点挂在旧座位上的 daily-review owner 权和 C1 休市句。这是「结论携带成立条件」的另一面——旧路径碰巧对，是因为椅子上还坐着别的东西。

### 0.2 不是加法悖论

四臂里得分高的一侧**没有多长新组件**。分差来自谁先动手。禁止用这些当「追上」：加 prompt「请先查双红」、加一轮 repair、加更严质检条、产品内嵌完整 ReAct。那些是在「模型当老板」的环上叠层。

追上天花板 = 换座位 + 汇合处跑包。追上现场写多出来的那半档 = 残差写手看两张表。Knevo 外盘叙事不追。

## 1. 范围

### 1.1 做

- 让 `question_type=market_watch` 加入 `DETERMINISTIC_OWNER_TYPES`，Engine A 拒收。拒收之后**不假设**下一站是 `_answer_market_review`。
- 四袋在编排器 **owner 分叉之前**跑完（洞 1-(a)）。daily-review 仍可 own 人话结构；不得跳过包，不得用日报 md 顶替四袋收据。
- 显式站立日用 `trade_date = ?` 精确查。禁止把现役块函数的 `<= as_of` 当作「当日」。块函数要么加 `strict_date=True`，要么只渲染、查询由包来做。
- `_resolve_market_data_context` 纳入站立日清单：问句日在库中无行时返回「无该日」，禁止回显问句日当 `result.trade_date`。
- 0 行或休市：公开稿只留日历/无行情句。不改查邻日。残差关：复用现役 `AskOptions.compose=False`（编排器今日硬编码 `True`，P0 必须在包跑完后 `replace`）。不新增第二套开关。
- P0 休市题面是 `2026-07-25 今天市场怎么样`（`market_watch=True` 且 `requested_date=2026-07-25`）。Engine B 侧补 `calendar_disclosure` / `with_calendar_disclosure` 调用点。
- 原题 `2026-07-25 市场怎么样`（C1）保持现役旁路，本单只加回归锁，不把它改路由成 `market_watch`。
- 主线 ∩ 双红为空时必须写缺口，不许把「名单上有某题材」写成「该题材当天在加量」。
- 未注册方法语言不得留在公开稿。质检条不上桌。
- `AskOptions.date` 改成站立日后，`knowledge_anchor` 的时间边界跟着变——这是行为变更，进验收，不是顺手副作用。

### 1.2 不做

- 不把 A1 改路由成 `dated_market_review`。
- **不**把 `daily-review` 在 `market_watch` 上下打成证据贡献者（洞 1-(b)）。那是另一单。
- 不改 `honesty_gates` 里的休市**判定**；只补 Engine B **调用点**。
- 不把 C1 原题改写成 `market_watch`，不把 `lane_generation` 的 `quick_fact` 休市句撤掉。
- 不把 `market_cause` / `market_forecast` / 个股深挖收进这个包。
- 不在产品里做完整 ReAct loop。
- 不追 Knevo 的谷歌财报 / 铜价 / 邻日午盘叙事。
- 不改生产超时、不改 8792/8796、不在脏树改 runtime。
- 不重做质量稿的截断 / 时点滤空 / 单位标签。
- 不把「写得像研报」写成验收。
- 不按 CLAUDE.md「`fact_mainline_sector_daily` 停在 06-30」写默认预期。核稿日实测该表已到 `2026-08-21`。07-23 有没有主线行，以当日查询为准。

## 2. 术语

| 词 | 含义 |
|---|---|
| **Engine A** | `continuous_episode` / `continuous_glm`。模型自选工具。生产默认。 |
| **Engine B** | 编排器拒收 A 之后的那条链：可能是 `daily-review` owner → `prepare_existing_answer`，也可能是 `_run_answer_query` → `_answer_market_review`。v1 把 Engine B 写成「就是 `_answer_market_review`」是错的。 |
| **拒收** | `continuous_turn_adapter` 见 `DETERMINISTIC_OWNER_TYPES` 就 `_declined_result()`。 |
| **汇合处** | `conversation_orchestrator` 里 `if owner_output is not None` **之前**。两条后续路径都能看见同一份包收据。 |
| **组件包** | `run_market_watch_pack(standing_date) -> MarketWatchPack`。四袋：总量、主线、严格双红、涨停热度。services 层纯函数，禁止 import runtime。 |
| **显式站立日** | 问句解析出的 ISO 日，或任务 `information_cutoff`。有它就必须精确命中该日。 |
| **隐式站立日** | 问句只有「今天」且解析不出日历日：才允许 `max(trade_date) <= cutoff`。A1/P0 休市题都是显式，走精确命中。 |
| **格** | 包产出的锁死字段。公开稿必须带这些值或显式「本袋 0 行」。`served_date` 必须等于显式站立日，或袋为 empty。 |
| **残差写手** | 只解释格与格冲突。现役开关就是 `AskOptions.compose`，不另造 `residual_enabled`。 |
| **严格双红** | `market_feature_store.signals.DOUBLE_RED_SQL`。 |
| **C1 旁路** | 原题「2026-07-25 市场怎么样」：`general_finance_qa` + `lane_direct_answer`。不是本单换的座位。 |
| **P0 休市题** | 「2026-07-25 今天市场怎么样」：`market_watch=True`。这才是新座位上的休市验收。 |
| **synthesis-heavy** | 防回退进 A 时才改。P0 拒收成功后盘面题不应再走它。 |

## 3. 已核实事实（实施时不要再探一遍）

v1 事实经 2026-08-24 核稿复验。行号以核稿时主仓工作树为准，导航用符号名。

**复验通过（不要重探）：**

2. `route_table.market_watch` capabilities = `memory, market_quote, graph`（`route_table.py` 该行；与 A1 冻结 `decision.capabilities` 一致）。`needs_template=True`，`answer_owner=None`。
3. `DETERMINISTIC_OWNER_TYPES` 无 `market_watch`。命中即 `_declined_result()`。
5. A1 修复轮各 2 次工具，无 `sector_daily`。8792 traces=`finance_query` + `mainline_context`；结构 `partial`，语义 `repaired`。
6. `missing_mandatory_capability: market_data` 原文照录；`finance_query.produces` 不含 `market_summary`（`research_tool_registry.py` 两处对照）。`satisfiability.enforced=false`。
7. `market_watch ∈ _SYNTHESIS_HEAVY_QUESTION_TYPES`。
8. 两个块函数收 `as_of`；`_answer_market_review` 没传。`options.date` 今日只喂给 `knowledge_anchor`。
11. 库尖 `2026-08-21` 时 cutoff=`2026-07-23` 仍有 1 行。验收不许要求 `db_max == cutoff`。
- §6.2 冻结对照数逐个对上 DB：`21949.97` / `-17.27` / `116` / `2` / `0.2519` / 缩量观望 / 反弹阶段。
- 07-23 四袋都有数：严格双红 7 个、涨停热度 138 行、主线 theme 5 行。live 可达成。不要按 CLAUDE.md 旧句假设主线表停在 06-30。

**复验推翻 / 新钉死：**

1. ~~A1 / C1 都是 `question_type=market_watch`。~~ **只对 A1 成立。** C1 冻结 controller：`lane=research`，`question_type=general_finance_qa`，`generate=lane_direct_answer`，约 2 秒、`provider=null`。`is_market_watch_query("2026-07-25 市场怎么样") is False`。`is_market_watch_query("2026-07-23 今天市场怎么样") is True`。`is_market_watch_query("2026-07-25 今天市场怎么样") is True` 且 `requested_date=2026-07-25`。
4. `needs_template=true` 仍只用来记 `llm_unavailable_template_answer`，不是包入口。本条未推翻。
9. 双红 SQL 与涨停热度适配器仍在。本条未推翻。
10. C1 产品/天花板公开稿同句周六无行情，**成立条件是 C1 旁路**，不是 `market_watch` 换座。Knevo 邻日叙事仍不当产品缺口。
12. **[新增，洞 1]** `workbench_skills/router.py`：`is_market_watch_query` 为真时插入 `daily-review`。`registry.py`：`role="workflow"`，`can_own_answer=True`。`_skill_output_compatible_with_turn` 在 `lane=="workflow"` 只看 role。有 `answer_contract` 则 `owner_output` 非空，走 `prepare_existing_answer`。代码自己写了 `is_market_review = owner_output is None and ...`。
13. **[新增，洞 1]** `structured_reports.daily_projection_modules`：指定日没有 `<date>-daily-review.md` 则 `date_text=None`，skill 不带 `answer_contract`，才会落到 `_answer_market_review`。主树存在 `market_feature_store/exports/2026-07-23-daily-review.md`。A1 live 臂 `finance_root` 是主树时，#2 的 v1 判据必红，且红法随这个 md 漂。
14. **[新增，洞 2]** `_daily_market_overview_block_for_llm`：`where trade_date <= as_of order by desc limit 1`。`_market_data_asof` 同样 `<=`。`<= DATE '2026-07-25'` 实测返回 `2026-07-24`。
15. **[新增，洞 2]** `_resolve_market_data_context`：`requested_date` 原样返回，不查库。`result.trade_date` 可与块内 `served_date` 分裂。
16. **[新增，洞 3]** `with_calendar_disclosure` 调用点：`continuous_turn_adapter`、`lane_generation`。`ask.py` / `ask_blocks.py` / `ask_synthesis.py` 零调用。`deterministic_lane_answer` 只在 `question_type=="quick_fact"` 时吐休市句。

## 4. 方案对比

| 方案 | 做法 | 追上什么 | 追不上 / 代价 |
|---|---|---|---|
| **A. 拒收 A + 汇合处跑包（推荐）** | `market_watch` 加入拒收名单；包在 owner 分叉前跑；显式日精确命中；Engine B 补休市句；残差复用 `compose` | 天花板供数；A1 不空转；P0 休市题不回落 07-24 | daily-review 仍可 own 人话，必须把锁格并进公开稿；`compose=True` 仍可能发明阈值，P1 删句 |
| B. 留在 A，episode 前先跑包 | 第一轮前注入四袋 | 供数能齐 | 仍受 synthesis-heavy / repair / 假缺口；和换座位相反 |
| C. 产品内嵌 ReAct | 模型自选下一查 | 偶尔写出冲突句 | 贵、不稳；本单不做 |

选 A。洞 1 的 (b)（降级 daily-review）不是第三方案，是 A 的错误落点，已否决。

## 5. 目标态

```
intent（is_market_watch_query → question_type=market_watch）
  → Engine A 拒收
  → 解析显式站立日（问句日或 cutoff）
  → 汇合处：run_market_watch_pack(standing_date)
        精确查四袋；每袋收据 = 命中该日 或 empty
        休市：calendar_disclosure 写入公开稿首句
        0 行：compose=False，停
  → 分叉（包已经跑完，两路都能读同一份收据）：
        owner 是 daily-review → prepare_existing_answer，锁格必须进入公开稿
        无 owner → _answer_market_review 只渲染包，不再用 <= as_of 自己查
  → 有行且 compose=True：残差只解释冲突
  → 交付闸：未注册方法语言删除；质检不上桌
```

C1 旁路（无「今天」）不进上图。它继续 `lane_direct_answer`。#5 只保证没把它改坏。

## 6. 契约

### 6.1 站立日（四个解析点）

优先级：

1. `market_review_requested_date(query)`（A1 = `2026-07-23`；P0 休市题 = `2026-07-25`）
2. 任务 `information_cutoff.as_of` / 评测 cutoff
3. **仅当 1、2 都空**（隐式「今天」）：库内 `max(trade_date) <=` 上界
4. `_resolve_market_data_context`：这是第四个写入 `result.trade_date` 的点。有显式站立日时，库无该日行必须返回「无该日 / None」，**禁止**把问句日原样写回。有行则 `trade_date` 与包的 `served_date` 同一天。

`AskOptions.date` 带显式站立日。禁止只靠 daily-review skill 的 `as_of`。

查询语义：

| 情况 | SQL |
|---|---|
| 显式站立日 | `trade_date = ?`。0 行 = empty，不回落 |
| 隐式站立日 | 允许 `<=` 取最新 |

禁止：只把现役 `as_of` 塞进块函数、语义仍是 `<=`。两条落地任选其一，§8 写死选用哪条：**(i)** 块函数加 `strict_date=True`；**(ii)** 包负责查询，块只渲染传入的行。推荐 (ii)，避免第三条 `<=` 语义漏网。

标题写「指定日盘面」，不写「最新」——除非隐式日且取到的就是库尖。

### 6.2 四袋规定查询

| 袋 | 源 | 0 行时公开稿必须 |
|---|---|---|
| 总量 | `fact_market_daily` **该站立日** 1 行 | 「该日无行情数据」（休市句优先） |
| 主线 | 现役主线块改为读包行，或对**该日**精确查 | 「主线表该日无行 / 仅有题材汇总」。有行就列该日行。不得用邻日冒充。不要预设 07-23 无行。 |
| 严格双红 | `fact_sector_daily` + `DOUBLE_RED_SQL`，该日 | 「严格双红 0 个」 |
| 涨停热度 | `get_limit_heat_themes(站立日)` 或该日 `fact_theme_limit_heat_daily` | 「涨停热度该日无行」 |

每袋收据必须带 `requested_date` 与 `served_date`。显式站立日下：`served_date == requested_date` 或袋 status=`empty`。缺收据 = 包没跑完。

总量锁字段（有则原样）：`total_amount`、`amount_vs_yesterday_pct`、`limit_up`、`limit_down`、`sh_index_pct_chg`、`volume_state`、`market_stage` + `stage_day`。A1 对照：`21949.97`、`-17.27`、`116`、`2`、`+0.25`（库内 `0.2519`）、缩量观望、反弹阶段。

验收两锁，缺一不可：数字来自真行 **且** `served_date` 等于问句日。只锁数字会放过 07-25 问句吃 07-24 行。

### 6.3 残差写手与 `compose`

现役没有「残差可关」开关。`conversation_orchestrator` 硬编码 `compose=True`。`_answer_market_review` 只在 `compose=False` 时走 `_build_base_answer_spec_from_sections`。

本单复用 `compose`，不新增参数：

| 包结果 | `compose` | 模型 |
|---|---|---|
| 休市或总量袋 empty | `False`（包跑完后 `replace`） | 不上场 |
| 有行 | 保持 `True` | 只写残差 |

有行时约束不变：格内数字与收据一致；主线有、双红无则写缺口；未注册阈值删除；质检不上桌。

### 6.4 能力记账（P1 / 方案 B 退路，不是 P0 门禁）

P0 拒收成功后，盘面题不应再撞 `missing_mandatory_capability: market_data`。**禁止**把「不报这条」写成 P0 必绿测试——那会永远绿。

只在这两处验收：方案 B 退路仍进 episode 时；或 P1 专门测「若有人把 `market_watch` 移出拒收名单」。

同时：`market_watch` 移出 `_SYNTHESIS_HEAVY_QUESTION_TYPES`，防回退。

### 6.5 `knowledge_anchor` 时间边界（行为变更）

今日 `knowledge_anchor` 吃 `options.date`，而 `options.date` 常常是 daily-review 的 `as_of` 或 `None`。本单把 `AskOptions.date` 改成立立日之后，锚点按站立日收口。

验收：A1 的 knowledge 块 `as_of=2026-07-23`（或显式「该日无积累」），不得在站立日已钉死时按「最新」扫库。这是有意变更，写进 §7.3 #12。

### 6.6 Engine B 休市披露

判定仍只读 `honesty_gates.calendar_disclosure(frame)` / `task_frame.assumptions`。

新调用点（§8 写死一处，不要两处各写各的）：

- 汇合处包跑完后，若 disclosure 非空：公开稿首句 = 该句；`compose=False`；四袋收据仍在（empty）。
- 不要指望 `lane_generation` 的 `quick_fact` 分支给 `market_watch` 休市句。
- 不要改 C1 旁路现有调用。

## 7. 验收

离线单测必须红→绿。Live 只在干净树、不覆盖四臂旧迹。夹具必须自带「有 / 无 `2026-07-23-daily-review.md`」两种 owner 分叉，禁止依赖主树 exports 是否存在。

### 7.1 拒收与汇合处

| # | 输入 | 必须 |
|---|---|---|
| 1 | `TaskFrame.question_type=market_watch` 进 `ContinuousTurnAdapter` | `handled=False` |
| 2 | A1 题面进编排器，**无论** owner 是不是 daily-review | 四袋收据齐；`requested_date=served_date=2026-07-23` 或该袋 empty。**不**断言一定走进 `_answer_market_review`，**不**断言 `execution_kind != continuous_episode`（owner 路径也满足这句话） |
| 3 | 残差若上场 | 其前方已有四袋收据 |
| 2a | 夹具有 `2026-07-23-daily-review.md`，daily-review 成为 owner | 仍满足 #2。锁格在公开稿，不被 md 顶掉 |
| 2b | 夹具无该 md，无 owner | 仍满足 #2。走到 `_answer_market_review` 只渲染包 |

变异：从拒收名单拿掉 `market_watch` → #1 红。汇合处调用删掉 → #2 / #2a 红。

### 7.2 站立日与 0 行

| # | 输入 | 必须 | 标注 |
|---|---|---|---|
| 4 | `2026-07-23 今天市场怎么样`，该日有行、库尖更新 | 总量袋 `served_date=2026-07-23`，不是库尖 | P0 |
| 5 | `2026-07-25 市场怎么样`（C1 原题） | 公开稿点名周六/休市；无 7/24 盘面数；`llm` 不上场 | **另一路径**回归锁，不证明本单换座 |
| 5a | `2026-07-25 今天市场怎么样` | `market_watch` 包跑完；总量袋 empty；公开稿休市句；无 7/24 成交额/涨停；`compose=False`；`result.trade_date` 不是 07-25 假有数、也不是 07-24 | **P0 本单分支** |
| 6 | 显式站立日总量袋 0 行且非休市 | 「该日无行情」；`served_date` 空；不改查邻日 | P0 |

变异：块查询仍用 `<=` 且把 07-25 当 as_of → #5a / #6 必须红（回到 07-24）。

### 7.3 四袋与锁格

| # | 输入 | 必须 |
|---|---|---|
| 7 | A1 冻结日夹具（1 行总量 + 双红 + 热度） | 四袋收据；公开稿含锁字段、双红名、热度名；`served_date=2026-07-23` |
| 8 | 主线含「半导体」、双红全在电链 | 残差不得写半导体当天加量 |
| 9 | 旧迹「只有两袋」形状 | 本单路径不得以两袋完成 |
| 12 | A1 + knowledge_anchor | 锚点 `as_of=2026-07-23` 或「该日无积累」，不按库尖扫 |

### 7.4 交付卫生

| # | 输入 | 必须 | 序 |
|---|---|---|---|
| 10 | 残差稿含 `MA20` `110–120%` 或「旗型蓄能」 | 公开稿删句，不留质检条 | P1 |
| 11 | episode 仍被接住且已有总量袋 | 不得报 `missing_mandatory_capability: market_data` | **P1 / 方案 B，不是 P0 门禁** |

### 7.5 Live（干净树，新目录）

不覆盖 `four-arm-knevo-20260823/`。

| 题 | 过线 |
|---|---|
| A1 `2026-07-23 今天市场怎么样` | 第一动作不是 `deadline_exhausted`；四袋齐；锁格数字；双红名单；无未注册阈值上桌。不锁措辞。主树有无 07-23 md 都要过 #2 |
| P0 休市 `2026-07-25 今天市场怎么样` | 休市句；无 07-24 盘面数 |
| C1 原题 | 与实施前旁路兼容（#5）。不是本单过线主证 |

Knevo 快照只对照，不纳入过线。

## 8. 落点与文件

P0 四行（v1 的三行不够）。第 3 行是洞 1，必须在竖切站立日之前落地，否则测试切在不执行的路上。

| 文件 | 职责 | 序 |
|---|---|---|
| Modify: `intelligence/runtime/continuous_turn_adapter.py` | `DETERMINISTIC_OWNER_TYPES` 加入 `market_watch` | P0-1 拒收 |
| Create: `intelligence/services/market_watch_pack.py` | `run_market_watch_pack`：显式日 `=` 查询四袋；产出 `MarketWatchPack`（每袋 `requested_date` / `served_date` / rows 或 empty） | P0-2 站立日 + P0-4 四袋 |
| Modify: `intelligence/services/ask.py` `_resolve_market_data_context` | 显式日无行不得回显问句日 | P0-2 |
| Modify: `intelligence/runtime/conversation_orchestrator.py` | **在 `if owner_output is not None` 之前**调包；休市/`empty` 则 `replace(compose=False)` 并写入公开稿首句；两分支都能读包 | P0-3 owner 分叉 |
| Modify: `intelligence/services/ask.py` `_answer_market_review` | 只渲染包，不再自己 `<= as_of` 查库 | P0-3 / P0-4 |
| Modify: `intelligence/services/ask_blocks.py` | 块改为渲染函数，或 `strict_date=True`。§6.1 选 (ii) 则块不再查库 | P0-2 / P0-4 |
| Modify: 编排器或 `_answer_market_review` 收口 | Engine B 调 `calendar_disclosure` / `with_calendar_disclosure`（一处） | P0-3 |
| Modify: `intelligence/runtime/glm_agent_runtime.py` | `market_watch` 移出 `_SYNTHESIS_HEAVY_QUESTION_TYPES` | P0 防回退 |
| Test: `intelligence/tests/test_market_watch_component_first.py` | §7.1–7.3，含 #2a/#2b/#5/#5a | P0 |
| Modify: 交付闸（先 rg） | 未注册阈值删句 | P1 |
| Modify: registry 或包收据 | `market_data` 记账 | P1（#11） |
| 收尾: `docs/prediction-ledger.md` | `R-20260824-01`…`06` | 收尾 |

不要改 `honesty_gates.py` 的判定。不要新建第二份双红口径。不要改 `lane_generation` 的 `quick_fact` 休市句（C1 旁路依赖它或 `lane_direct_answer` 的现役链，#5 锁的是行为不是函数名）。

## 9. 账本

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260824-01` | `market_watch` 进 Engine A，第一轮 0 工具 `deadline_exhausted` | `HARNESS_FIX` | P0-1 | §7.1 #1、§7.5 A1 |
| `R-20260824-02` | 显式日按 `<=` 回落邻日；`_resolve_market_data_context` 与块 `served_date` 分裂 | `HARNESS_FIX` | P0-2 | §7.2 #4/#5a/#6 |
| `R-20260824-03` | 四袋缺双红/热度 | `HARNESS_FIX` | P0-4 | §7.3 |
| `R-20260824-04` | 发明阈值上桌；`rejected_claim_indexes=[]` | `HARNESS_FIX` | P1 | §7.4 #10 |
| `R-20260824-05` | 拒收后 daily-review 抢走 owner，包根本不跑（随 md 漂） | `HARNESS_FIX` | P0-3 | §7.1 #2/#2a/#2b |
| `R-20260824-06` | 新座位上的休市题无披露、吃邻日数（休市句留在旧椅） | `HARNESS_FIX` | P0-3 | §7.2 #5a |

`R-20260824-02` 的 v1 表述「没传 as_of」保留为子因；v2 主因是 `<=` + 日期回显。结案写明这点。

#11 不单独占号。禁止覆盖 `four-arm-knevo-20260823/`。

## 10. 实施顺序

1. 从 `gitea/main` 开干净树。本脏树只许 pathspec 留 spec。
2. §7.1 #1 失败测试 → 加入拒收名单 → 绿。
3. **先落地洞 1（P0-3）**：#2a 红（有 md、owner 在、包未跑）→ 汇合处调包 → #2a/#2b 绿。**禁止**先竖切 `_answer_market_review` 传 `as_of`——那条路在有 md 时不执行。
4. 竖切站立日（P0-2）：#5a/#6 用 `<=` 夹具红 → 精确查询 + 修 `_resolve_market_data_context` → 绿。
5. 竖切四袋（P0-4）：#7/#8/#12 红 → 包齐四袋 → 绿。#5 锁 C1 旁路。
6. P1：#10。#11 只挂方案 B / 回退测试。
7. Live：A1 + P0 休市题。C1 原题只做旁路对照。合 main 等用户确认。

反向执行的代价：先传 `as_of` 再处理 owner 分叉，会得到一套只在「没有 daily-review.md」时绿的测试，A1 冻结日主树上 live 全红。先加严判官同 v1。

## 11. 合入关系

- 质量稿 P0 与本单文件冲突面小，可并行。
- 路由稿不碰。
- reading-rules / SPT：baseline 不是四袋的替代。
- `knowledge_anchor` 边界收紧与本单同 PR，不要拆出去「以后再说」——拆出去会被当成回归。

## 12. 自检

- 无 TBD。洞 1 选 (a)。查询语义选 §6.1 (ii)（包查、块渲染）。`compose` 复用，不新造开关。
- 判别变量仍是「开口前四袋是否已齐」，#2 已改成正向断言。
- 方案 A 的落点与 §5 一致：汇合处，不是 `_answer_market_review` 单点。
- C1 原题与 P0 休市题已拆开。
- #11 不进 P0 门禁。
