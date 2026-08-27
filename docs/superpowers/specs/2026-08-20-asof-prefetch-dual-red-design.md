# 设计：问句日预取 + 双红戳记（对齐分析师第一刀）

- 日期：2026-08-20
- 状态：Draft v1 已接线（实现中）。树 `/Users/a77/fwp-wt-asof-prefetch`（`docs/asof-prefetch-dual-red`，从 `gitea/main` @ `6a54f995`）。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改。
- 对照现场（Cursor SQL vs Workbench `events[].payload.arguments`）：
  - 次日研判：`run_20260820_185829_952511`（路由对，没点双红）
  - 锂矿发酵切后：`run_20260820_194838_293183`（T1 已保 7/23 数字；预取仍是 8.19 大盘；稿里双红 0 次）
- 父稿：`docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`（P0 传达室：T1/T2/T3 已合 `6a54f995`）。**本单在 P0 之后、P1 之前。** 不重做截断/资讯滤空/单位标签。
- 相邻：`docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`（已合 #283）。本单不改 `market_cause` 入口。
- 引擎：**A**（`continuous_episode`）。预取发生在模型第一轮 tool call 之前。

## 0. 一句话

T1 修好了「问到了、袋子把锚定日挤掉」。剩下和 Cursor 不像，是因为 **进场桌上的菜不是分析师的第一刀查询**：历史题被塞进「今天」的 `market_data`/`mainline_context`，次日研判不预取双红个数，发酵题用 `contains 锂` 而不是 `sector_name='锂矿'`，观察值里没有「是否双红」布尔字段。

本单不换写手、不开放 Shell/任意 SQL、不新开 `question_type`。把分析师动笔前那几条确定性 SQL **收成 harness 预取**，并在行上盖双红章。

人话：不要让学徒变成熟手。熟手进门前已经称好菜。店要把同一盘称好的菜摆上桌，再让学徒炒。

**判别变量**（验收只锁这些，不锁文笔）：

1. 问句带历史日历日时，预取观察值的交易日 = 该日（或声明缺口），**不得**把 runtime 最新交易日当成主证据。
2. `market_forecast` 预取含问句日及前两个交易日的 **双红个数**（口径与 strategy1 一致）。
3. 发酵/回溯触发词 + 能锚定的板块名：预取该名逐日涨幅/成交额亿/边际量/`双红=是|否`，窗口覆盖问句日；不得用 `contains` 近义板块灌满 25 格来冒充。
4. 预取出来的 `market_data` / `mainline_context` / 双红序列，必须能满足对应必填能力——禁止「桌上已有、判官仍报 missing_mandatory_capability」。

---

## 1. 要不要给 Workbench「写 SQL / 开 Shell」的元能力

**不要。** 这是本单最容易走错的分叉，单独写死。

### 1.1 两边实际都在打同一份库

| | Cursor（分析师侧） | Workbench 生产 episode |
|---|---|---|
| 数据 | 同一份 `db/market_feature_store.duckdb` | 同一份 |
| 取数通道 | Cursor 的 **Shell**：`python` + `duckdb.connect` + 任意 `SELECT` | 合同内工具：`finance_query` / `market_data` / `mainline_context` … |
| 限制 | 无行数硬帽、可算派生列、可 JOIN | `finance_query` 限定 dataset/维度/指标/filter，agent 路径 `_AGENT_FINANCE_QUERY_MAX_ROWS = 25` |
| 谁决定查什么 | 读了 SKILL 的写手（我） | GLM 填 JSON；另有 **harness 预取**（今日总览那套） |

所以不是「Workbench 没有查库能力、Cursor 有」。`finance_query` 已经是 **参数化 SQL**：dataset 映射到 `fact_*` 表，filter 变成 `WHERE`，metrics 变成 `SELECT` 列。它是查询构建器，不是没有查询。

缺的是两样：

1. **分析师会写、模型经常不点** 的那几条 SQL（双红计数、精确板块名 + 窗口）。
2. **预取日历钉在问句日**。现在 `conversation_orchestrator` / `runtime_capabilities_for_frame` 把 `freshness` **写死成 `"current"`**，再叠加 `is_current_market_query`：问句里出现 `2026-07-23` 算「有显式日期」，历史发酵题会被当成「需要同日市场事实」，然后同日被理解成 **runtime 今天**（现场 8.19），不是 7/23。

### 1.2 若给模型 Shell 或 `run_sql` 会发生什么

这是「元能力」的三种候选，对比如下。

| 做法 | 像不像 Cursor | 代价 | 本单 |
|---|---|---|---|
| **A. agent 可调 Shell / 任意 SQL** | 最像我的通道 | 破只读红线（可写盘、可外呼视环境）；schema 试探；JOIN 打爆上下文；证据没有 caliber/provenance；25 行帽形同虚设；评测无法钉查询形状 | **禁止** |
| **B. 新工具 `run_sql`，只读、白名单表** | 像我写 SQL | 仍要模型想起正确 SQL；写错 `contains 锂` 和今天一样；和现有 `finance_query` 双通道；判官更难对账 | **不做** |
| **C. 扩 `finance_query` 数据集**（如 `dual_red_daily`） | 模型仍可能不点（8.19 已有 `sector_daily` 仍去查了龙头高度） | 菜单更长；不解决预取日期 | 可作后续，**不是本单主路径** |
| **D. harness 预取 = 跑分析师第一刀 SQL** | 对齐的是 **桌上的事实**，不是通道 | 板块名解析失败必须 fail closed | **本单** |

原理（RAG / agent 面试也是这句）：生成器换强模型替代不了检索器。8.19 现场合同已含 `finance_query`，模型点了 `leader_height_daily`。把 SQL 通道再放开，只是让它有更多方式点错菜。

**内置的应是「确定性预取」这种元能力，不是「模型可以 exec」这种元能力。** 预取是 harness 的 Shell：Python 进程里跑 `is_double_red` / `load_theme_daily_rows`，观察值写进 episode，模型只读。和 Cursor 的差别从「谁拿着 Shell」变成「Shell 在进场前跑完」。

### 1.3 和技能桥红线的关系

`theme-fermentation-tracer` 的 `trace.py` 只读 DuckDB + 知识库，**可以**成为第 13 个工具，但会碰到「技能桥刻意只开一个」和「模型仍可能不调」。本单不挂 skill。盘面时间轴用已在仓内、未进 episode 的 `theme_lifecycle_timeline.py`（`is_double_red` / `load_theme_daily_rows` / `resolve_theme_alias`）。消息面×起涨股完整链路另开单。

---

## 2. 范围

### 2.1 做

四刀，顺序固定（后刀依赖前刀的日期）：

1. **预取日历**：有问句 `as_of` / 显式交易日 → 预取该日；无日期才 `current`。`freshness="current"` 不得再写死。
2. **`market_forecast` 预取双红个数序列**：问句日 + 向前两个已有数据的交易日。口径：`pct_chg>0 AND diff_ratio>10 AND amount>500`，与 strategy1 / `theme_lifecycle_timeline.DOUBLE_RED_*` 同一套常量。
3. **发酵/回溯预取精确板块日频 + 双红戳记**：触发词见 §4.3。锚定名用 `resolve_theme_alias`，取数用 `load_theme_daily_rows` 再逐行 `is_double_red`。窗口默认问句日起回溯到窗口起点（问句有 `start` 用 start，否则 end 往前 20 个交易日，可配置，测试锁 锂矿 7/1–7/23 形）。预取 **不受** agent 25 行帽约束。
4. **预取计入必填能力**： satisfiability / `missing_mandatory_capability` 必须认预取观察值。锂矿切后现场：预取了 `market_data` 与 `mainline_context`，gate 仍报缺这两项。

### 2.2 不做

- 不把 Grok / Cursor Shell 引进 8792。
- 不新增 `question_type=fermentation`。发酵仍可落在 `theme_analysis`；换的是预取内容。
- 不调大 `_AGENT_FINANCE_QUERY_MAX_ROWS`（`R-20260816-07`）。
- 不把 `reading_baseline` 当主修（规则出现在观察值字段里，不靠提示词让模型背公式）。该模块若另单 live，不得替代本单第 2/3 刀。
- 不修 P1（质检进公开稿、残稿回退）。
- 不收「铝为什么涨」无板块（商品歧义，路由稿已标故意不修）。
- 不把 8.19 没查双红当成 T1 回归；那是本单第 2 刀。
- 不在本单挂 `trace.py`、不改技能桥只开一个的决定。

---

## 3. 现役接缝（实施时点查，不要抄行号当真理）

| 现象 | 函数 / 模块 | 含义 |
|---|---|---|
| 历史题仍预取「今天」 | `conversation_orchestrator` 组 contract 时 `freshness="current"`；`runtime_capabilities_for_frame` 同样写死 | 问句日进不了证据计划 |
| 有显式日期就被当成要「同日盘面」 | `is_current_market_query`：`has_subject and dated` → True。`_HISTORICAL_MARKERS` 只有 2024/2025/「历史上」等，**不含 2026-07-23** | 锂矿发酵题会走进「需要市场事实」 |
| 走进之后预的是 runtime 今日 | `presentation_profile == "mainline_current"` 时 `ask.py` 预取 `market_data`「当前市场最新总览」+ `mainline_context`「当前市场主线」 | 现场 8.19 总览进了 7 月题 |
| 双红公式已存在、episode 没用 | `theme_lifecycle_timeline.is_double_red` / `DOUBLE_RED_PCT|DIFF|AMOUNT` | 不要再抄一套阈值 |
| 口语名→板块名已存在 | `resolve_theme_alias` → `resolve_query_themes`；失败返回 None | 失败则缺口，禁止臆配「锂」 |
| 精确名逐日行已存在 | `load_theme_daily_rows(con, theme)`：`where sector_name = ?` | 这就是 Cursor 那条 SQL 的仓内版 |
| 模型补查仍 25 行 | `episode_tools._AGENT_FINANCE_QUERY_MAX_ROWS` | 预取绕开；后续 `finance_query` 仍戴帽 |

连续 episode 的预取入口以 Engine A 实际调用链为准（`generic_research_owner` / `ask.py` 预取循环或 runtime 等价物）。实施时用一条 `rg prefetch` 钉住 **8792 走的那条**，不要只改 Engine B。

---

## 4. 行为规格

### 4.1 预取日历（第 1 刀）

输入优先级：

1. `task_frame` / `research_context.information_cutoff.as_of_date` 若来源是问句（`requested`）→ 用它。
2. 否则问句里 `has_explicit_date` 的日历日，落到最近 **不晚于该日** 的交易日。
3. 否则才 `current` = 库内 `max(trade_date)`。

`is_current_market_query` 可以继续为 True（历史日也需要盘面）。变的是 **freshness 绑定那个日期**，不是绑定进程日历。

失败：该日库无 `fact_market_daily` 行 → 观察值写「问句日 YYYY-MM-DD 无市场总览」，**不得**回退塞最新一日而不声明。

回归形：问句含 `2026-07-23` 且题型 `theme_analysis` 发酵触发 → 预取 `market_data` 若仍发生，其观察值日期必须是 2026-07-23（或显式缺口），不得出现「市场数据截至：2026-08-19」且无「非问句日」标注。更干净的做法：发酵预取 **替换** 今日主线预取，不双份。

### 4.2 双红个数序列（第 2 刀）

触发：`question_type == market_forecast`，或次日研判合同（现役 `presentation_profile == "forecast"`）。

观察值形状（字段名实施可微调，测试锁语义）：

```
双红个数（口径 pct_chg>0 且 diff_ratio>10 且 amount>500）：
2026-08-17=75；2026-08-18=21；2026-08-19=0
```

计数对象：`fact_sector_daily` 当日所有板块行（与 Cursor `GROUP BY trade_date` 一致），不是只数主线表。

缺日：该日无板块行 → 该日写 `缺数`，不得把 0 和缺数混成一个「0」。

判官：正文写「双红 0 个」且预取为 0，不得当无证据扩写。

### 4.3 发酵精确名时间轴（第 3 刀）

触发词（问句归一化后，任一命中即可；不要新题型）：

`发酵` / `回溯` / `链路` / `怎么走到` / `怎么走过来` / `起涨` / `补涨`

与主题解析：优先 `task_frame.subject`；否则 `resolve_theme_alias(问句题材跨度)`。解析不到 → 观察值「未锚定板块，双红序列未预取」，模型再走 `finance_query`。禁止用 `contains 锂` 做预取。

窗口：问句同时出现两个日历日则用闭区间；只出现终点日则 `[end-N 交易日, end]`，N 默认 20 个交易日（锂矿 7/1–7/23 验收可把 N 提到覆盖该窗，或问句已含「这波」时用终点往前到上一次连续无双红之前——**v1 先锁「终点日往前 20 个交易日」**，避免状态机范围膨胀。锂矿对照题问句含 7/23 不含 7/1：20 个交易日从 7/23 往前 **够到 7/1** 才算过线；若 20 不够，把默认改成 30 并在测试里写死。不要在 v1 做「自动找到本轮发酵起点」。）

每行至少：`trade_date, pct_chg, amount, diff_ratio, 双红=是|否`。单位标签与 T3 一致（成交额亿）。

预取全文可以长过 25 行。截断策略若必须有：按日期 **保窗口末端（问句日）**，与 T1b 同一方向，并写请求窗口。这是预取自己的帽，不是 `_AGENT_FINANCE_QUERY_MAX_ROWS`。

### 4.4 预取满足必填能力（第 4 刀）

若某 capability 已有成功预取观察值（非空、非「预取失败」），structural / semantic 前置的 `missing_mandatory_capability` 不得再因「模型没再调同名工具」而红。

模型后来又调了同名工具：以工具结果为准追加，不删预取。

---

## 5. 失败形状（认不出来就 fail closed）

| 输入 | 必须发生 | 禁止 |
|---|---|---|
| 问句日库无盘 | 缺口句 | 用昨天/今天顶上且不说 |
| `resolve_theme_alias` 空 | 「未锚定板块」 | 预取 `contains` 近义名 |
| 双红计数当日 0 行 | `缺数` | 写成 0 个双红 |
| 发酵触发但 subject 是公司名 | 不走板块日频预取，或落到个股通道（本单可先缺口） | 把公司名当 `sector_name` 查 0 行却声称「无发酵」 |

---

## 6. 测试（离线先于 live）

新测试文件建议：`intelligence/tests/test_asof_prefetch_dual_red.py`。用假连接或最小 DuckDB，不要打生产库。

1. `freshness` 不再写死：`decide_turn`/`build contract` 对「锂矿…发酵到 2026-07-23」得到 as_of=2026-07-23 的预取日历，而不是 `current`。
2. 双红序列：插入 8.17 两行合格双红、8.18 一行、8.19 零行 → 观察值 2/1/0（测计数逻辑；不必 75/21/0 全量）。
3. 精确名：`sector_name='锂矿'` 7/23 行 `pct_chg=4.4, diff_ratio=11.73, amount=628.5` → `双红=是`；同日「锂电池」amount=300 即使涨也不进这条预取。
4. 必填能力：仅预取、模型 0 次 `market_data` call → 不得发 `missing_mandatory_capability subject=market_data`。
5. 负例：无发酵触发词的「固态电池有什么新进展」不强制双红窗口预取（仍可走今日主线，若问句无历史日）。

`theme_lifecycle_timeline` 已有双红单测，本单不要复制公式测试，只测 **接线**。

---

## 7. Live 验收（对照 Cursor，不是新旧店互比）

8792 须已含本单。看 `arguments` 与预取观察值（`events[]` 里无 `arguments` 的那几段预取）。

| 题 | 过线 |
|---|---|
| 站在 2026-08-19 收盘看 2026-08-20（只用 8.19 及以前） | 预取含双红个数 8.17/8.18/8.19；公开稿主轴用这组数。不要求文笔像 Cursor。 |
| 锂矿发酵到 2026-07-23，逐步涨幅/成交额/环比 | 预取板块名为锂矿（或解析后的库内名）；7/23 行双红=是、4.4、628.5；**不得**把 8.19 全市场总览当作主证据。T1 的 25 行提示仍可在后续 `finance_query` 上出现。 |

旧 run 仅作对照，不重跑不能当本单绿。

---

## 8. 合入顺序

```
已合：质量 P0 T1/T2/T3 + market_cause 路由  →  6a54f995
本单：问句日预取 + 双红戳记
之后：质量稿 P1（残稿回退 / 质检进公开稿）
再后（可选）：finance_query 增加 dual_red_daily 数据集；或只读挂 fermentation tracer
```

本单不依赖 P1。P1 依赖本单不是硬的，但本单会减少「判官因 missing capability 超时」。

---

## 9. 实施约束

- 新树从 `gitea/main` 开，pathspec 提交。主脏树不动。
- 双红阈值只从 `theme_lifecycle_timeline` 引用，禁止第三份字面量。
- 预取 SQL 写在服务层函数里（可测），不要写进 prompt。
- 不改 12 个工具的对外名字；可以新增 **内部** 预取函数，不必注册为 agent 工具。

---

## 10. 台账

占号建议 `R-20260820-12`（问句日预取日历）、`-13`（forecast 双红序列）、`-14`（发酵精确名+戳记）、`-15`（预取满足必填能力）。以 `docs/prediction-ledger.md` 当时空号为准，写行时再钉。
