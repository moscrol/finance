# 设计：盘面题由组件包当第一执行者

- 日期：2026-08-24
- 状态：Draft v1
- 来源：Knevo 四臂 A1/C1（2026-08-23）agent-run / trace-diff。人话结论：和天花板的差距是接线，不是模型不够聪明。
- 实测目录：`~/.finance-runtime/four-arm-knevo-20260823/`
  - A1：`A1-market-overview/workbench-8792|8796|codex-component|live-toolkit/`
  - C1：`C1-future-date-no-data/` 同结构
  - 网页真源是 `continuous-episode.json` + `trace.jsonl`，不是 UI 的 `trace.json`
- 代码树：从 `gitea/main` 开干净树 `feat/market-watch-component-first`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`（丢数 / 截断 / 单位标签）
  - `docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`（板块「为什么涨」）
  - `intelligence/services/honesty_gates.py`（休市句前置；C1 已走通）

## 0. 一句话

`market_watch` 已经认出「该走模板」，也已经有总览块、主线块、严格双红 SQL、涨停热度适配器。卡住的是 **Engine A（`continuous_glm`）抢了成文权**：第一轮 0 工具空转到 `deadline_exhausted`，修复轮再补两袋，然后自由写。本单把第一执行者换成已经存在的盘面组件包；模型只写格与格冲突的残差。

**判别变量**（验收只锁这一条）：冻结题「2026-07-23 今天市场怎么样」在模型开口之前，必须已经跑完四袋规定查询（总量 / 主线 / 严格双红 / 涨停热度），格内数字进公开稿且不可被模型改口径。不是「多调一次工具」，不是「把稿子写得像 ReAct」。

人话：厨房里菜谱和食材都在。点菜员写了「要套餐」，后厨却让厨师先空等一分钟再随便抓两样。本单让套餐先出锅，厨师只解释两盘对不上的地方。

### 0.1 不是加法悖论

四臂里得分高的一侧（天花板 / 现场写）**没有多长新组件**。`FinanceQuery`、`fact_market_daily`、`DOUBLE_RED_SQL`、`get_limit_heat_themes` 产品里都有。8792/8796 修复轮也打到了其中两袋。分差来自谁先动手。

因此本单禁止用这些当「追上」手段：加 prompt「请先查双红」、加一轮 repair、加更严质检条、在产品里嵌完整 ReAct agent。那些是在「模型当老板」的环上叠层，和目标态相反。

追上天花板（供数）= 换座位。追上现场写多出来的那半档（「主线有半导体、双红全在电链」）= 残差写手看两张表。Knevo 的外盘叙事不追。

## 1. 范围

### 1.1 做

- 让 `question_type=market_watch` 走与 `dated_market_review` / `quick_fact` / `external_market` 同一类 **确定性 owner 拒收 Engine A** 的门，把取数交给已有 Engine B 盘面块。
- 把问句日 / cutoff 传进总览块和主线块（函数已经收 `as_of`，现役调用没传）。
- 在同一组件包里**规定**打齐四袋：总量、主线、严格双红名单、涨停热度。口径用现役 `DOUBLE_RED_SQL`（`pct_chg > 0 AND diff_ratio > 10 AND amount > 500`），不新发明阈值。
- 0 行或休市：停，公开稿只留日历/无行情句。不改查邻日。C1 形状已经对，本单只锁死，不重写 `honesty_gates`。
- 模型若还上场，只能写格外解释；格内数字只许填空。主线 ∩ 双红为空时必须写缺口，不许把「名单上有某题材」写成「该题材当天在加量」。
- 未注册方法语言（MA20 区间、旗型、未在 reading baseline / 组件口径登记的支撑压力位）不得留在公开稿。质检条本身也不上桌。

### 1.2 不做

- 不把 A1 改路由成 `dated_market_review`。题面「2026-07-23 今天市场怎么样」按现役正则就是 `market_watch`（有日期但没有复盘/双红等专有词）。改路由会碰 daily-review 工作流，超出本单。
- 不把 `market_cause` / `market_forecast` / 个股深挖收进这个包。
- 不在产品里做完整 ReAct loop（自选下一工具、自评、多轮修理）。
- 不追 Knevo 的谷歌财报 / 铜价 / 邻日午盘叙事。
- 不改生产超时数字、不改 8792/8796 在跑实例、不在脏树 rebase。
- 不重做质量稿的截断 / 时点滤空 / 单位标签。那些丢数路径与本单「谁先跑」正交。
- 不把「写得像研报」或「像我现场那篇」写成验收。

## 2. 术语

| 词 | 含义 |
|---|---|
| **Engine A** | `continuous_episode` / `continuous_glm`。模型自选工具。生产默认。 |
| **Engine B** | `ask.answer_query` 写死流程。今日已接 `quick_fact` / `external_market` / `dated_market_review`。盘面成文入口是 `_answer_market_review`。 |
| **拒收** | `continuous_turn_adapter` 见 `DETERMINISTIC_OWNER_TYPES` 就 `_declined_result()`，把题还给编排器走 Engine B。 |
| **组件包** | 模型开口前必须跑完的确定性查询集合。本单四袋：总量、主线、严格双红、涨停热度。 |
| **格** | 组件包产出的锁死字段（成交额、环比、涨停、跌停、上证涨跌、双红名单、热度名单、行数）。公开稿必须带这些值或显式「本袋 0 行」。 |
| **残差写手** | 只解释格与格冲突、或声明「未开某袋」。不许改格内数字，不许发明未注册阈值。 |
| **严格双红** | 单一真本源 `market_feature_store.signals.DOUBLE_RED_SQL`。与 strategy1-matrix / D0 `double_red_count` 同一句。 |
| **synthesis-heavy** | `glm_agent_runtime._SYNTHESIS_HEAVY_QUESTION_TYPES` 现含 `market_watch`，预留约 60s 给成文。本单若 P0 拒收成功，这条对盘面题失效；若有人把盘面题再送回 A，必须同时移出该集合。 |

## 3. 已核实事实（实施时不要再探一遍）

均为 2026-08-23 四臂冻结迹，或同日读过的源码。行号以主仓当时工作树为准，导航用符号名。

1. A1 / C1 信封：`question_type=market_watch`，subject 空，operators 空。控制器 `lane=workflow`，`needs_template=true`，`decision_diverged_from_legacy=true`。
2. `route_table.market_watch`：`needs_template=True`，`answer_owner=None`，capabilities 仍是 `memory, market_quote, graph`（不是 `market_data` / `finance_query`）。
3. `DETERMINISTIC_OWNER_TYPES`（`continuous_turn_adapter`）= `{external_market, quick_fact, dated_market_review}`。**没有 `market_watch`**。命中则拒收；未命中则进 Engine A。这是 A1 进 `continuous_glm` 的直接原因。
4. `needs_template=true` 在 `conversation_orchestrator` 收口处只用来记 `llm_unavailable_template_answer` 降级，**不是**组件包执行入口。
5. A1 8792/8796 第一轮 `tool_calls=[]`、content 空，`stop_reason=deadline_exhausted`（约 72s）。然后 repair 各补 2 次工具：8792 = `finance_query/market_daily` + `mainline_context`；8796 = `finance_query/market_daily` + `theme_limit_heat_daily`。**两边都没有 `sector_daily` 严格双红**。
6. 结构闸仍报 `missing_mandatory_capability: market_data`，尽管 `finance_query(market_daily)` 已成功且公开稿有总量数字。`satisfiability.enforced=false`。`finance_query.produces` 含 `supporting_evidence` 等，**不含** `market_summary` / `current_baseline`；那两格写在 `market_data` 工具上。
7. `market_watch` 在 `_SYNTHESIS_HEAVY_QUESTION_TYPES` 里。这与「先成文、后取数」的空转同形。
8. Engine B 已有 `_answer_market_review` → `_daily_market_overview_block_for_llm` + `_market_review_mainline_context_block_for_llm`。两函数都收 `as_of`。现役 `_answer_market_review` **没传 `as_of`**。编排器 `AskOptions.date` 只在 daily-review skill 给出 `as_of` 时有值，A1 这种题是 `None`。
9. 严格双红 SQL 已在 `market_feature_store.signals`；涨停热度已在 `MarketAdapter.get_limit_heat_themes`。不需要新数据源。
10. C1 四臂公开稿（产品 / 天花板）已是同一句周六无行情；`llm.used=false`。Knevo 那份把 7/27 午盘和 7/24 写进来，提问日与 cutoff 不对等，**不当产品缺口**。
11. A1 天花板 / 现场写在库尖是 `2026-08-21` 的前提下，用 cutoff=`2026-07-23` 仍能打到 1 行。验收**不许**要求 `db_max == cutoff`。

## 4. 方案对比

| 方案 | 做法 | 追上什么 | 追不上 / 代价 |
|---|---|---|---|
| **A. 拒收 A，Engine B 当 owner（推荐）** | `market_watch` 加入 `DETERMINISTIC_OWNER_TYPES`；编排器把问句日写入 `AskOptions.date`；`_answer_market_review` 先跑四袋再决定要不要残差 LLM | 天花板供数；C1 形状保持；第一轮空转消失 | Engine B 现役 `compose=True` 仍会叫模型写人话，必须加「格锁死」才不会再发明阈值 |
| B. 留在 A，episode 前先跑包 | 在 `agent_episode` 第一轮前注入四袋观察 | 供数能齐 | 仍受 synthesis-heavy、repair、capability 错账、判官贴条；和「换座位」目标相反 |
| C. 产品内嵌 ReAct | 模型自己决定下一查 | 偶尔写出冲突句 | 贵、不稳、现场写 5/5 自评偏斜；本单明确不做 |

选 A。B 是给「暂时改不了拒收名单」的退路，不得当默认。C 出局。

## 5. 目标态

```
intent（已有：is_market_watch_query → question_type=market_watch）
  → 解析站立日：问句日期或 information_cutoff；无日期则用库内 ≤ cutoff 的最新交易日
  → 休市 / 日历披露已在 task_frame.assumptions：公开稿只出该句，停
  → 组件包（同步、确定性、计入 traces）：
        1. fact_market_daily 总量（1 行或 0 行）
        2. 主线（fact_mainline_* ，允许「该日无主线表」缺口）
        3. fact_sector_daily 严格双红名单
        4. fact_theme_limit_heat_daily 热度
  → 0 行：公开稿 = 无该日行情。禁止改查邻日
  → 有行：把四袋渲染成锁死格，写入将送给残差写手的材料，并直接进入公开稿骨架
  → 残差写手（可关）：只解释冲突 / 人话连接；格内数字原样出现
  → 交付闸：未注册方法语言删除；质检内部码不上桌
```

Engine A 对 `market_watch` 的第一动作必须是拒收，而不是开 `continuous_glm`。

## 6. 契约

### 6.1 站立日

优先级（先命中先用，禁止「库尖覆盖问句日」）：

1. `market_review_requested_date(query)`（A1 = `2026-07-23`）
2. 任务上的 `information_cutoff.as_of` / 评测 cutoff
3. 库内 `max(trade_date)` 且 `<=` 上面两者之中已有的上界

`AskOptions.date` 必须带上这个站立日。禁止继续只靠 daily-review skill 的 `as_of`。

`_daily_market_overview_block_for_llm(..., as_of=站立日)` 与主线块同样传 `as_of`。标题写「指定日盘面」，不写「最新」——除非站立日确实等于库尖。

### 6.2 四袋规定查询

| 袋 | 源 | 0 行时公开稿必须 |
|---|---|---|
| 总量 | `fact_market_daily` 该站立日 1 行 | 「该日无行情数据」（休市句优先） |
| 主线 | 现役 `_market_review_mainline_context_block_for_llm` | 写「主线表该日无行 / 仅有题材汇总」，不得用邻日主线冒充当日 |
| 严格双红 | `fact_sector_daily` + `DOUBLE_RED_SQL`，按成交或涨幅排序列出名称 | 写「严格双红 0 个」；不得改口径放宽 |
| 涨停热度 | `MarketAdapter.get_limit_heat_themes(站立日)` 或等价 `fact_theme_limit_heat_daily` | 写「涨停热度该日无行」 |

四袋都要有收据（成功或 empty）。缺收据 = 包没跑完 = 结构未完成，不能靠模型补一袋。

总量格至少锁这些字段（有则原样，无则显式缺）：`total_amount`、`amount_vs_yesterday_pct`、`limit_up`、`limit_down`、`sh_index_pct_chg`、`volume_state`、`market_stage` + `stage_day`。A1 冻结日对照：`21949.97`、`-17.27`、`116`、`2`、`+0.25`、缩量、反弹阶段。验收锁「这些数来自该日行」，不锁措辞。

### 6.3 残差写手

残差是可选的。包齐且 0 行时不上模型（C1）。

有行时允许一轮成文，输入 = 锁死格 + 已授权视角 / reading baseline。输出约束：

1. 格内数字必须在公开稿出现，数值与收据一致。
2. 若主线名单含某题材、该题材不在双红名单：必须写缺口或并列，禁止写成该题材「当天加量 / 主升」。
3. 禁止输出未在组件口径或已注入 reading baseline 登记过的方法阈值。现场已出现、必须删的形状：`MA20` 的 `110–120%`、旗型蓄能、未登记支撑/压力位、缩量新高需降权（若基线未注册）。
4. `rejected_claim_indexes=[]` 但语义已标 invent 的句子，本单视为交付失败。删句，不要贴「【质检存疑】」上桌。
5. 公开稿不含 `## 输出质检`、内部 gate code。

### 6.4 能力记账（仅当题仍可能进 A）

P0 拒收成功后，盘面题不应再撞 `missing_mandatory_capability: market_data`。若测试或回退路径仍进 episode：

- `finance_query` 且 `dataset=market_daily` 的成功迹，视为满足 `market_data` 对 `market_summary` / `data_date` 的贡献；**或**
- 组件包自己记 `capability=market_data`。

禁止只改文案、不改账。仪表红、料其实在，比缺料更危险。

同时：`market_watch` 移出 `_SYNTHESIS_HEAVY_QUESTION_TYPES`。盘面题不是先写综述再补数。

## 7. 验收

离线单测必须红→绿。Live 只在干净树、不覆盖四臂旧迹。

### 7.1 拒收

| # | 输入 | 必须 |
|---|---|---|
| 1 | `TaskFrame.question_type=market_watch` 进 `ContinuousTurnAdapter` | `handled=False`（与 `dated_market_review` 同形） |
| 2 | 同题在编排器 | 走到 `_answer_market_review`，`execution_kind` 不是 `continuous_episode` |
| 3 | 第一轮模型 | 不存在；若残差上场，其前方 traces 已有四袋 |

变异：从 `DETERMINISTIC_OWNER_TYPES` 拿掉 `market_watch` → #1 必须红。

### 7.2 站立日与 0 行

| # | 输入 | 必须 |
|---|---|---|
| 4 | 问句 `2026-07-23 今天市场怎么样`，库里该日有行、库尖更新 | 总量袋 `served_date=2026-07-23`，不是库尖 |
| 5 | 问句 `2026-07-25 市场怎么样`（周六），库 0 行 | 公开稿点名周六/休市；无 7/24 成交额/涨停数；`llm` 不上场 |
| 6 | 总量袋 0 行且非休市 | 「该日无行情」；不改查邻日 |

### 7.3 四袋与锁格

| # | 输入 | 必须 |
|---|---|---|
| 7 | A1 冻结日夹具（1 行总量 + 若干双红 + 热度） | 四袋都有收据；公开稿含总量锁字段与双红名、热度名 |
| 8 | 主线含「半导体」、双红全在电链 | 残差不得写半导体当天加量；必须能看到并列或缺口 |
| 9 | 修复轮只打了总量+主线的旧迹形状 | 本单路径下不得再出现「只有两袋」的完成态 |

### 7.4 交付卫生

| # | 输入 | 必须 |
|---|---|---|
| 10 | 残差稿含 `MA20` `110–120%` 或「旗型蓄能」 | 公开稿删除该句，不留质检条 |
| 11 | 结构核验 | 不得在已有总量袋收据时报 `missing_mandatory_capability: market_data` |

### 7.5 Live（干净树，新目录）

复跑 A1/C1 网页臂各一次，对照四臂旧迹，不覆盖。

A1 过线：第一动作不是 `deadline_exhausted`；公开稿有锁格数字；有双红名单；无未注册阈值上桌。不要求追齐现场写的全部措辞。

C1 过线：与天花板同形（周六 + 无行情），与本单实施前产品句兼容。

Knevo 快照只作对照，不纳入过线。

## 8. 落点与文件

| 文件 | 职责 | 序 |
|---|---|---|
| Modify: `intelligence/runtime/continuous_turn_adapter.py` | `DETERMINISTIC_OWNER_TYPES` 加入 `market_watch` | P0 |
| Modify: `intelligence/runtime/conversation_orchestrator.py` | `AskOptions.date` = 问句日 / cutoff，不单靠 daily-review skill | P0 |
| Modify: `intelligence/services/ask.py` `_answer_market_review` | 传入 `as_of`；先跑四袋；0 行停；再决定残差 | P0 |
| Modify: `intelligence/services/ask_blocks.py`（或紧邻新纯函数） | 双红名单块 + 热度块，只调现役 SQL/适配器 | P0 |
| Modify: `intelligence/runtime/glm_agent_runtime.py` | `market_watch` 移出 `_SYNTHESIS_HEAVY_QUESTION_TYPES` | P0（防回退进 A） |
| Modify: `intelligence/services/research_tool_registry.py` 或包收据 | `finance_query(market_daily)` 或组件包记入 `market_data` | P1 |
| Modify: 交付闸（现役 semantic verifier / honesty 卫生，**先 rg 再改**） | 未注册阈值删句；质检不上桌 | P1 |
| Test: `intelligence/tests/test_market_watch_component_first.py`（新） | §7.1–7.4 夹具 | P0/P1 |
| 收尾: `docs/prediction-ledger.md` | `R-20260824-01`…`04` | 收尾 |

不要改 `honesty_gates.py` 的休市判定。C1 只加回归锁。

不要新建第二份双红口径。引用 `DOUBLE_RED_SQL`。

## 9. 账本

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260824-01` | `market_watch` 进 Engine A，第一轮 0 工具 `deadline_exhausted` | `HARNESS_FIX` | P0 | §7.1、§7.5 A1 |
| `R-20260824-02` | 问句日有数仍可能打到库尖；`as_of` 没传到总览块 | `HARNESS_FIX` | P0 | §7.2 #4 |
| `R-20260824-03` | 规定四袋缺双红/热度，修复轮各补两袋且不一致 | `HARNESS_FIX` | P0 | §7.3 |
| `R-20260824-04` | 发明阈值上桌；`rejected_claim_indexes=[]`；`market_data` 假缺口 | `HARNESS_FIX` | P1 | §7.4 |

结案：单测绿不够，A1/C1 live 收据要进新目录。禁止覆盖 `four-arm-knevo-20260823/`。

## 10. 实施顺序

1. 从 `gitea/main` 开干净树。本脏树只许 pathspec 留下这份 spec。
2. 先写 §7.1 #1 失败测试（`market_watch` 今日会被 A 接住）→ 加入拒收名单 → 绿。
3. 竖切站立日：#4 红（不传 `as_of` 打到库尖）→ 编排器 + `_answer_market_review` 传日 → 绿。
4. 竖切四袋：#7/#8 红 → 双红/热度块进包 → 绿。0 行 #5/#6 锁 C1。
5. P1：删句闸 + 能力记账。#10/#11。
6. 干净树 live A1/C1。合 main 等用户确认。

反向执行的代价：先加 prompt / 先加严判官，会留下「模型仍是第一执行者」的绿测试，P0 换座位时还得拆掉。先做 P1 记账、不做拒收，A1 还会先空转 70s。

## 11. 合入关系

- 质量稿 P0（截断 / 滤空 / 单位）与本单文件冲突面小，可并行。本单不依赖那些修才换座位。
- 路由稿改的是 `market_cause` 入口，本单不碰。
- reading-rules / SPT 注入：残差写手可以读已注入的 baseline，但 **baseline 不是四袋的替代**。没跑双红袋，不许用视角句子补一张双红表。

## 12. 自检

- 无 TBD。四袋、站立日优先级、拒收名单、验收题面均已钉死。
- 方案 A 与 §5 目标态一致；B/C 只作对照。
- 范围只有 `market_watch` 的第一执行者与四袋，不拆成第二份 spec。
- 「追上 ReAct」在本文 = 组件包 + 冲突残差，不是产品内 ReAct agent。
