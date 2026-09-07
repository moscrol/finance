# 设计：事件定价第一刀——事件锚点日历 + `EventReaction` 事件反应回溯

> 日期：2026-09-07
> 状态：**已执行（2026-09-07 晚，用户「执行」，§9 六条按推荐）**。代码 `intelligence/services/event_pricing/`、CLI `scripts/event_reaction.py`、29 条单测；真库已跑出第一份读数。验收逐条与真库数据现实见 `docs/verification/2026-09-07-event-pricing-slice1.md`。执行中对设计的三处修正：编辑日历 FOMC 记北京日期 → 参数加 `editorial.reaction_rule`；同所属期两日不同日期且无官方仲裁 → `editorial_ambiguous` 不入锚点（fail-closed，§1 第 5 条的延伸）；六形状作一族做族内 BH（§4.5 补）。工单编号待 INDEX 分配。
> 上游：`2026-09-06-personal-research-calibration-endstate-design.md` §4.6 事件锚点回溯（本 spec 是 `anchor_windows` 的**第二个实例**，第一个是 `LeaderSuccession`）、§4.2 两类派生、§4.4 区间；`2026-09-05-time-river-gap-roadmap.md` G-02c；`2026-08-23-event-calendar-quality-layers-design.md`（`fact_event_daily` 双时点语义与 P2「官方确认级另一张源」）；`2026-09-07-teaching-framework-slice1-index-stage-leader-succession-design.md`（表结构、统计门复用、基准设计照抄不重造）；`2026-09-04-methodology-backtest-structured-history-design.md`。
> 触发：2026-09-07 对话——用户问「事件的冲击和定价是不是我们缺的」；仓内自诊 `valuation_gap.py`「缺定价程度判断：不知道市场已经 price in 多少」；Knevo 宏观探针 E-007 P8 显示对手连「LPR 下调后 5/10/20 日指数与涨停家数」都报不出，而这正是我们数据能算的形状。
> 红线：本 spec 不含任何判读。事件反应的**形状**用描述词命名（事前涨事后跌），不用结论词（利好出尽）；结论词只作口语别名进词表。所有数字阈值是 B 类候选值，进收据不进结论。不给概率。
> 「[实测]」= 2026-09-07 只读查主库 / 旁路库、`rg`、读 `schema.sql` 核到的。

---

## 0. 一句话

把「一个事件发生前后市场留下的脚印」编成可重算对象并跑出第一份历史读数：**事件锚点日历**（编辑日历 + 官方日程合成、每类事件一个确定性的**反应日**、能答「站在 T 日已知最新一期是哪期 / 尚未发布」）→ **`EventReaction`**（锚点日前 m 日 / 当日 / 后 k 日，指数与板块两层，横截面并排，形状标签对非事件日基准过四态统计门）→ **「已定价」三代理并排**（事前超额、拥挤度分位、舆论认同度阶段），不合成一个数。

产出是**读数不是结论**：每类事件的 N 与来源等级、反应日映射自检、指数 / 板块反应分布、形状分布对基准的四态、每个事件日的板块横截面、三代理表、`latest_known` 对 E-007 P3 / P4 两题的自测——给用户看历史上事件是怎么被定价的，不给「下次会怎样」。

日历知道**何时**，不知道**多少**：宏观数值（CPI 是几、社融是几）仍是 G4 缺口，本 spec 不碰。

---

## 1. 判别变量（验收只锁这些）

1. **确定性**：同一主库快照、同一官方日程文件、同一参数文件，两次重建 `history_event_calendar / history_event_anchors / history_event_reaction` 逐行相同。路径上无 LLM；标题→事件类的分类是白名单正则，不匹配即 `unparsed`，不猜。
2. **反应日映射**：每类事件有且只有一条确定性规则把「事件日期」映射到「A 股首个可反应交易日」（§3.3）。北京时间收盘后或美国时段发生的事件，反应日是**下一个**交易日。映射错 = 把反应记到错的日子，比缺一天更糟，故单独验收。
3. **前视**：事后窗从反应日 +1 起算（复用 `history_outcomes` 的 `WINDOW_START_OFFSET = 1`）；事前窗止于反应日 −1；锚点日 ≤ `knowledge_cutoff`。把价格列整体后移一天的作弊夹具必须被抓出。
4. **预期内 / 非预期分开**：只有「日程在事前窗开始前已公开」的事件（`scheduled=true` 且 `schedule_published_at ≤ 反应日 − m`），事前窗才能读作「预期 / 抢跑」；其余事前窗只是「事前状态」，两类读数**不合并、不同表**。这是本对象与「拿事前涨幅当抢跑证据」这种散文的分界线。
5. **缺口 fail-closed**：窗口内任一价格行缺 → 该记录 `missing`（照 outcomes）；板块代码映射不上 → `gap{unmapped_sector}`；编辑日期与官方日程冲突 → 官方为准并计数；缺官方日程的类不得冒充 `official`。
6. **统计门复用**：形状命中率只经 `methodology_backtest.stats.readout / stage_readouts` 出四态；N < 10 → `insufficient_n`；收据里不出现概率、可能性、「会」。
7. **知道何时不知多少**：`latest_known(indicator, as_of)` 只返回 `{period, release_date, source_grade}` 或 `not_yet_released{next_release_date}`，**永不返回数值**。
8. **到板块不到个股**：横截面只到 `fact_sector_daily` 实体（板块 / 题材）；不产出个股名单——与观察剧本 `scope ∈ {index, sector, theme}` 硬门一致。
9. **不写主库、不改 `schema.sql`**：产物全部落旁路库 `history_labels.duckdb` 新表；旁路库任何时候可删可重建。官方日程是仓内版本化 JSON，不是抓取器。

---

## 2. 现状盘点

### 2.1 复用（不重造）

| 层 | 实物 [实测] | 用法 |
|---|---|---|
| 事件 | `fact_event_daily`：2627 行，`event_date` 2026-01-05 → 2026-09-03；`event_type` 数据发布 954 / 会议 748 / 行业事件 420 / 企业动态 214 / 政策 122 / NULL 77；1964 行带 `sectors`（JSON：`ts_code` 如 `990105.FP`、`name`、`type ∈ {I, N}`）；`importance` 1–3 为主（5/6 共 66 行）；`is_future` 68 行但其 `event_date` 全 ≤ 09-03——**是 sync 时点的旧标记，不维护**（08-23 §5.1）；`updated_at` 是 last-touch 不是 first-seen（08-23 §5.3） | 编辑日历源；`sectors` 给板块级锚点；`is_future` / `updated_at` **不用作 PIT 判据** |
| 价格·指数 | `fact_market_daily`：416 行 2024-12-20 → 2026-09-07，`sh_index_pct_chg` 414 非空、`sh_index_close / open / high / low`、`total_amount / amount_ma20 / volume_state`、`limit_up / limit_down / advancers`、`market_stage` | 指数层反应；涨停家数（市场）；量 |
| 价格·板块 | `fact_sector_daily`（视图）：106,283 行、411 日、630 个 `sector_ts_code`（FP 407 / TI 223）、`pct_chg / amount / diff_ratio / strength`；`fact_sw_l1_daily` 31 个申万一级、410 日 | 板块层反应与横截面；申万一级作粗横截面 |
| 涨停·板块 | `fact_theme_limit_heat_daily` 399 日（2025-01-02 起）：`limit_up_count / market_limit_up_count / rank`，取 labels 同一 `heat_tier`（`dimension=sector, scope=all, data_stage=final, is_realtime=false`） | 板块涨停家数 |
| 资金 | `fact_sector_stock_daily.fund_flow_1d`（个股级，可按板块聚合）；`fact_theme_flow_daily` 仅 51 日（2026-06-23 起） | v0 只留列位，`gap{reason=v0_scope}` |
| 事后窗 | 旁路库 `history_outcomes`：sector 423,520 / theme 187,184 / stock 1,046,664 行；`fwd_return / max_return / days_to_peak / drawdown_after_peak / status ∈ {ok, pending, missing}`；horizons **[3, 5, 7, 10]**，`WINDOW_START_OFFSET = 1`，收益按 `pct_chg` 复利 | 板块事后窗**直接读**，不重算；指数无 outcomes 行，按同一公式算 |
| 标签层 | 旁路库 `history_labels`：`LABEL_VERSION = v3-heat_sector_all_final_nonrt-stock_limit_high_union-market_stage_normalized`（**第一刀 spec 写的 v2 已过期**）；已注册 `market_stage`（归一投影）、`volume_surge`、`dual_red_strict / dual_red_streak`、`limit_heat_rank(_jump)`、`amount_rank_top10`、`mainline_flag`、`ma5_peak/valley_confirmed`…；`history_calendar` 413 日（2024-12-20 → 2026-09-02） | 交易日历；分桶对照列；`cohort_compare` 的 feature |
| 统计 | `stats.readout(successes, baseline_n, baseline_k, min_n)` → 四态；`stage_readouts` 按阶段桶 + BH | 形状命中率读数 |
| 河 | `river_window.windows_around`（按交易日取窗，市场级六维）、`river_query.cohort_compare`（一批日子 × 类别列 vs 基准）、`river_query.range_aggregate` | 锚点上下文形状；「事件日 × 阶段」对照 |
| 拥挤度 | `market_midterm.py` D6：最新成交额在自身 trailing-60 日分布的百分位 `crowding_pct` | 「已定价」代理之一，同公式重算到反应日 −1 |
| 舆论 | `skills/opinion-cross/scripts/consensus_staging.py`：认同度阶段（下限语义，只升不降） | 「已定价」代理之二；v0 接线状态见 §5 |
| 日历契约 | `finance_query` 的 `event_daily` 数据集（`allow_future_time_range / cutoff_column=updated_at`，08-23 P0） | 不改；本 spec 的日历是**另一张**旁路表 |

### 2.2 缺口（本 spec 要补的）

1. 事件没有成为注册的 point 标签，`anchor_windows` 没有外生事件实例。
2. 编辑日历对宏观类**不完整也不干净** [实测]：LPR 8 个月只 5 个不同日（应 8）；社融 / 金融数据 0 行；政治局 0 行；官方 PMI 9 日但同日重复（08-31 有 3 行）；「CPI」57 行 26 日里混着香港 / 新加坡；「FOMC」13 行 6 日里混着纪要与讲话；非农 3 日。没有官方日程，宏观类 N 到不了 10。
3. 事件表从 2026-01-05 起，价格从 2024-12-25 起：**2025 年的锚点只能来自官方日程**。
4. 没有「反应日」概念——美国时段事件今天会被记到事件当天。
5. 没有事前窗（`history_outcomes` 只向前）；没有相对指数的超额；没有横截面并排。
6. 「已定价」没有度量，只有 prompt 里的话（`valuation_gap.py` 自诊；`red_team.py` 固定一句「价格可能已抢跑」）。
7. 「站在 T 日已知最新一期」答不了——E-007 P3 / P4 的形状在本仓没有对象。
8. 创业板无表 → 指数层只有上证，创业板 `gap`。

---

## 3. 设计 A：事件锚点日历

### 3.1 两个源，一张表，来源等级分明

```text
history_event_calendar                         每 (event_class, reaction_day) 一行
  event_class            §3.2 白名单
  event_date             事件发生 / 发布的自然日（可为非交易日、可为美国日期）
  reaction_day           §3.3 映射后的 A 股交易日（history_calendar 内）
  scheduled              bool：该类是否「日程可提前知道」
  source_grade           official | editorial | both（两源同日）| conflict（两源日期不同，取 official，记 editorial_date）
  schedule_published_at  官方日程文件的公布日（该年日程何时公开）；editorial-only → NULL
  indicator / period     数据发布类：指标名与所属期（如 cn_cpi / 2026-05）；由正则从标题或日程条目取；取不到 → unparsed
  event_ids_json         合并进来的 fact_event_daily.event_id 列表（同日多行去重成一条锚点）
  sectors_json           编辑日历带的板块（去重后的 ts_code 列表；映射不上的另计）
  title_sample           一条代表性标题（只作人读）
  ev_version / computed_at
```

**官方日程文件** `references/calendars/official_release_schedule.<year>.json`（与 `references/sector_shenwan_l1_mapping.json` 平级）：每条 `{event_class, event_date, time_local, tz, source_url, entered_at}`，文件头 `{year, schedule_published_at, sources:[…]}`。来源：国家统计局年度「主要统计信息发布日程表」（PMI / CPI-PPI / GDP）、全国银行间同业拆借中心 LPR 报价规则（每月 20 日，遇节假日顺延，按实际报价日录）、美联储 FOMC 年度日程；没有官方日程的类（社融 / 金融数据央行不预告）按**实际发布日**回填并标 `source_grade=editorial` 或 `backfilled`，不得标 official。**一次性录入、带 URL 与录入日期，不做抓取器**；每年 12 月更新一次。谁录：推荐 agent 录、人抽查（§9）。

### 3.2 事件类白名单 v0（分类只靠正则 + `event_type` + 排除词，不靠 LLM）

| `event_class` | 范围 | `scheduled` | 源 | 正则要点 | [实测] 编辑日历现状 |
|---|---|---|---|---|---|
| `cn_lpr` | market | 是 | official + editorial | `LPR` | 5 日 / 8 月，缺 3 |
| `cn_pmi_official` | market | 是 | official + editorial | `PMI` ∧ ¬`财新` ∧ ¬`RatingDog` | 9 日，同日重复 |
| `cn_cpi_ppi` | market | 是 | official + editorial | `CPI`∨`PPI` ∧ ¬(`香港`∨`新加坡`∨`美国`∨`欧元区`∨`日本`∨`英国`) | 26 日含境外，需排除 |
| `cn_credit_data` | market | 否（央行不预告） | backfilled + editorial | `社融`∨`金融数据`∨`M2`∨`新增贷款` | 社融 0、M2 5 |
| `fomc_decision` | market | 是 | official + editorial | `FOMC`∨`美联储` ∧ (`决议`∨`利率决定`∨`议息`) ∧ ¬(`纪要`∨`讲话`∨`听证`) | 6 日含纪要，需排除 |
| `policy_release` | sector | 否 | editorial | `event_type='政策'` ∧ `sectors` 非空 | 122 行 |
| `industry_event` | sector | 否 | editorial | `event_type='行业事件'` ∧ `sectors` 非空 | 420 行 |

不进 v0（列出以免重辩）：`cn_gdp`（两年 8 次，N 永远不够，等有别的季度类再一起做）、`us_cpi / us_nfp`（编辑只 3 日，且需美国官方日程另录）、`politburo / state_council`（0–1 行，会议日期需人工录）、`conference`（会议 / 展会 ~770 行，反应日语义不清）、`corporate_event`（企业动态 214 行，多为个股级）。

**去重**：同一 `(event_class, reaction_day)` 只一条锚点，`event_ids_json` 保留全部；板块类事件的板块并集。

### 3.3 反应日映射（每类一条规则，参数文件里写死）

| 类 | 发布 / 发生时刻 | 规则 |
|---|---|---|
| `cn_lpr` | 09:00 北京 | 同日若为交易日则同日，否则下一交易日 |
| `cn_pmi_official` | 09:30 北京（月末或次月 1 日） | 同日 / 下一交易日 |
| `cn_cpi_ppi` | 09:30 北京 | 同日 / 下一交易日 |
| `cn_credit_data` | 多在 16:00 后北京 | **下一交易日**（当日收盘后发布） |
| `fomc_decision` | 14:00 ET = 次日 02:00 / 03:00 北京 | `event_date`（美国日期）**+1 自然日** 起的首个交易日 |
| `policy_release / industry_event` | 编辑日历不给时刻 | 同日 / 下一交易日；`reaction_day_confidence=low` 单列 |

`cn_credit_data` 若某月央行在盘中发布（历史上有），该条按实际时刻改映射并在文件里注明——这是为什么日程文件要带 `time_local`。映射规则版本化进 `ev_version`。

### 3.4 `latest_known(indicator, as_of)`（E-007 P3 / P4 的对象化）

```text
输入   indicator ∈ {cn_cpi, cn_ppi, cn_pmi_official, cn_lpr, cn_credit_data}, as_of 交易日
取数   history_event_calendar 中 indicator 匹配、scheduled 或 backfilled、period 已解析的行
输出   已发布：{indicator, period, release_date = event_date, source_grade}，取 event_date ≤ as_of 的最大 period
       未发布：{status: not_yet_released, next_release_date}，取 event_date > as_of 的最小 event_date（无则 unknown_schedule）
禁止   返回任何数值；数值是 G4
```

自测夹具直接用 E-007 两题：`latest_known(cn_cpi, 2026-07-08)` 应给 `period=2026-05`（6 月 CPI 若日程为 07-09 及以后）；`latest_known(cn_cpi, 2026-09-07)` 应给 `not_yet_released, next_release_date=2026-09-09`（以日程文件为准，不以 Knevo 说法为准）。**发布日以录入的官方日程为真值，本 spec 不核 Knevo。**

### 3.5 锚点标签

`history_event_anchors`，列与 `history_labels` 相同（`entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at`）：

- market 类：`entity_type='market'`, `entity_id='market'`, `trade_date=reaction_day`, `label='ev.<event_class>'`, `value_num=1`, `value_text` = JSON `{event_date, source_grade, scheduled, indicator, period}`。
- sector 类：每个映射成功的 `sector_ts_code` 一行，`entity_type='sector'`；映射失败的进 `history_event_gaps(reason=unmapped_sector)`。

不放进 `history_labels`（v3 构建的 `reset_tables` 会整表 DROP，第一刀 §3.5 同理）。`history_build_meta.build_kind='event_calendar' / 'event_anchors'`，`label_version = ev_version`。

---

## 4. 设计 B：`EventReaction`

### 4.1 记录（每 锚点 × 实体 一条）

```text
history_event_reaction
  node_id              = sha256(event_class, reaction_day, entity_type, entity_id)[:16]
  event_class / reaction_day / event_date / scheduled / source_grade
  entity_type          market | sector
  entity_id            'market' | sector_ts_code
  pre_window_semantics expectation（scheduled ∧ schedule_published_at ≤ reaction_day − m）| state_only
  pre_return_m         [reaction_day − m, reaction_day − 1] 复利累计 pct_chg（m 取 params.pre_days，候选 5）
  d0_return            reaction_day 当日 pct_chg
  d0_amount_ratio      当日 amount / 前 20 日均（市场层用 total_amount / amount_ma20）
  d0_limit_up          当日涨停家数（市场：fact_market_daily.limit_up；板块：limit_heat.limit_up_count）
  d0_limit_up_delta    与前一日之差
  fwd_return_{3,5,10}  板块：直接读 history_outcomes（同 entity、trade_date=reaction_day）；市场：同公式算
  max_return_10 / days_to_peak_10 / drawdown_after_peak_10   同 outcomes
  excess_pre_m / excess_d0 / excess_fwd_{3,5,10}   板块减上证同窗（简单差，不做 beta）；市场层为 NULL
  shape_tag            §4.2
  priced_in_proxies    §4.3 三列
  status               ok | pending | missing | gap(reason)
  ev_version / computed_at
```

指数层 20 日窗不进 v0：`history_outcomes` 只有 3 / 5 / 7 / 10，扩 horizons 会改共享表版本（§9 拍板）。

### 4.2 形状标签（描述词，不是结论词；阈值是候选值）

对 `(pre_return_m, fwd_return_5)`（板块用 `excess_*`，市场用原值），`x = params.shape_threshold_pct`（候选：板块 2.0、指数 1.0）：

| `shape_tag` | 判据 |
|---|---|
| `pre_up_post_down` | pre > +x ∧ fwd < −x |
| `pre_down_post_up` | pre < −x ∧ fwd > +x |
| `continuation_up` | pre > +x ∧ fwd > +x |
| `continuation_down` | pre < −x ∧ fwd < −x |
| `flat` | \|pre\| ≤ x ∧ \|fwd\| ≤ x |
| `mixed` | 其余 |

`pre_window_semantics=state_only` 的记录，形状照打，但**另表汇总**——它们不能读成「预期兑现 / 出尽」。词表登记口语别名：用户说「利好出尽」→ 查 `pre_up_post_down` 在 `expectation` 表里的分布，仅此而已。

### 4.3 「已定价」三代理（并排，不合成）

| 列 | 定义 | 源 | v0 状态 |
|---|---|---|---|
| `pre_excess_m` | 事前 m 日板块超额累计（市场层为 `pre_return_m`） | 本表 | 有 |
| `crowding_pct_dm1` | 反应日 −1 的成交额在自身 trailing-60 日分布的百分位（D6 同公式） | `fact_sector_daily.amount` / `fact_market_daily.total_amount` | 有 |
| `consensus_stage_dm1` | 反应日 −1 该板块 / 题材的认同度阶段下限 | `consensus_staging` | **`gap{reason=not_wired}`**：它是技能脚本、读观点事件库，接成确定性列属 G-02b 舆论轨 provider；本刀只留列 |

三列各自与 `shape_tag` 交叉出计数表；不做回归、不做加权。

### 4.4 横截面（market 类事件）

每个 market 类锚点日：全部 `fact_sector_daily` 实体的 `excess_d0` 与 `excess_fwd_5` 排序，出前 / 后 5 名（板块名 + 数值，事实）；`dispersion_d0` = 全部板块 `d0_return` 的 IQR。同时按申万一级（`fact_sw_l1_daily`）出一张 31 行粗表。**只出表**——哪个板块历史上对 LPR 日最敏感是读数，不是规则。

### 4.5 读数（复用统计门）

```text
对每 (event_class, entity_type, pre_window_semantics=expectation) 、每个 shape_tag S：
  successes   = [r.shape_tag == S for r in records if status == ok]  按 reaction_day 升序
  baseline    = 同实体集合、全部非锚点交易日上按同定义打 shape_tag；baseline_k / baseline_n
  readout     = stats.readout(successes, baseline_n, baseline_k, min_n=10)
  by_stage    = stats.stage_readouts({stage: 子序列}, {stage: (n0, k0)}, min_n=10, q=0.05)
                stage = 旁路库 market_stage（归一投影）于 reaction_day − 1；tf.stage_coarse 落地后加一列
附读数        pre / d0 / fwd 分布（分位数），横截面表，三代理 × shape 计数表，gap 与 conflict 计数
```

基准这么定的理由与第一刀 §4.5 相同：任一交易日都能打出形状，只有把事件日与随机日放在同一定义下比，量到的才是「事件这个时点」有没有超额形状。按阶段分桶依赖 `market_stage` 归一（G-05 / F5）——分桶读数标 caveat，不作结论。

「事件日 × 阶段」另用 `cohort_compare(dates=reaction_days, feature="market_stage")` 出一张对照（第一刀 §4.6 的旁路库标签扩展落地后可切 `tf.stage_coarse`）。

### 4.6 与 `anchor_windows` 契约的关系

本刀是 09-06 §4.6 的第二个实例，但 `river.window` / 段级 `pit_grade` 尚未落（G-02c）。处置同第一刀：直接用 `history_calendar` + 表内窗口算，**不等契约**；契约落地后 `EventReaction` 的 pre / fwd 两段改走 `river.window(..., knowledge_cutoff)` 并带 `pit_grade`，这是迁移义务写进 G-02c 验收，不是本刀阻塞。`pending` 状态照 outcomes：`reaction_day + k` 超出日历 → `pending`，不进 N。

---

## 5. 数据现实与风险（写在前面，读数出来别惊讶）

| 现实 [实测] | 影响 | 处置 |
|---|---|---|
| 编辑日历宏观类不全（LPR 5/8、社融 0、政治局 0） | 只靠编辑日历，每类 N < 10 | 官方日程文件是 N 的来源，不是可选项；`source_grade` 让读者知道每条锚点从哪来 |
| 事件表 2026-01-05 起，价格 2024-12-25 起 | 2025 年锚点全部 `official`-only；无 `sectors` | market 类两年 N ≈ 20；sector 类只有 2026（8 个月） |
| 同日多行（08-31 三条 PMI） | 不去重会重复计 | `(event_class, reaction_day)` 唯一 |
| CPI 行混境外、FOMC 行混纪要 | 分错类 = 反应日全错 | 排除词进正则；分类结果全部落 `history_event_gaps(reason=unparsed)` 或表，收据报 unparsed 数 |
| `is_future` 不维护、`updated_at` last-touch | 无法从表内证明「事前已知」 | 「事前已知」只由官方日程文件的 `schedule_published_at` 判；编辑日历一律不算 expectation |
| 央行金融数据无固定日程、时刻不定 | `cn_credit_data` 反应日可能错一天 | 按实际时刻逐条录；无时刻 → `reaction_day_confidence=low` |
| `history_outcomes` 只有 3/5/7/10 | 无 20 日窗 | v0 不做 20 日；§9 拍板是否扩 |
| 创业板无表 | 指数层只有上证 | `gap`；不从别的表推 |
| `fact_theme_flow_daily` 51 日 | 资金列几乎全空 | v0 不出资金列，留位 |
| `consensus_staging` 未接成列 | 三代理只有两列有值 | 如实 `gap{not_wired}`，依赖 G-02b |
| 413 个交易日、每类 ≈ 20 事件 | 总体四态勉强过 N；分阶段桶必 `insufficient_n` | 先出总体；分桶如实显示 |
| `policy_release` 反应日无时刻 | 政策多在晚间发布，同日映射会漏掉真正反应日 | 该类 `reaction_day_confidence=low`；收据同时给「同日」与「次日」两套 d0 读数供对照，不选 |

---

## 6. 非目标

- 不做 LLM 解读、不给概率、不给「下次会怎样」；形状标签不用结论词命名。
- 不接宏观数值（CPI 几、社融几）——G4 另议；`latest_known` 不返回数值。
- 不做共识 / 预期值源（没有源）、不做 surprise = 实际 − 预期；不接 Polymarket。
- 不做个股层反应、不产出个股名单。
- 不做 `us_cpi / us_nfp / cn_gdp / politburo / conference / corporate_event`（§3.2 列了理由）。
- 不做抓取器：官方日程是手录 JSON。
- 不改 `fact_event_daily` writer、不改 `finance_query` 的 `event_daily` 数据集、不做 08-23 P2 的「空日程不得 complete」（那是回答层的事；本表可作它的官方源，但接线另单）。
- 不接每日复盘 / 带读 / 投影（G-03 / G-14）、不接情景树（G-15；`event_class` 留作将来情景树的根键）。
- 不动 `LABEL_VERSION`、不写 `history_labels`、不写规则 JSON / 编译器（G-16）。
- 不改 BP / deck。

---

## 7. 分刀（工单拆法，供 writing-plans 用）

| 刀 | 内容 | 产物 | 依赖 |
|---|---|---|---|
| 1 | 官方日程文件 2025 / 2026（§3.1）+ 白名单分类器与排除词（§3.2）+ 反应日映射（§3.3）+ `history_event_calendar` + `latest_known`（§3.4）| 表 + CLI `latest-known`；单测：每类正则正反例、FOMC 跨日映射、节假日顺延、P3 / P4 两题夹具 | 无 |
| 2 | `history_event_anchors`（market / sector 两层）+ 板块代码映射 + `history_event_gaps` | 标签表；单测覆盖去重 / unmapped / conflict | 刀 1 |
| 3 | `history_event_reaction`：事前窗、当日、事后窗（读 outcomes）、超额、形状标签、`crowding_pct_dm1`、横截面（§4.1–4.4）| 记录表；前视变异测试（价格后移一天）；`consensus_stage_dm1` 列位 | 刀 2；旁路库 `history_outcomes` 已构建 |
| 4 | 读数：形状 × 基准四态、按阶段分桶（caveat）、`cohort_compare` 事件日 × 阶段、三代理 × 形状计数、收据 | 收据 §8 (6)–(9) | 刀 3；第一刀刀 4 的 `cohort_compare` 旁路库标签扩展（可选，未落则用 `market_stage`）|
| 5 | CLI（`scripts/event_reaction.py build-calendar / build-anchors / build-reaction / report / latest-known`）+ 自测（照 `theme-fermentation-tracer/selftest.py` 造最小库）+ 验证文档 | `docs/verification/2026-09-xx-event-pricing-slice1.md` | 刀 1–4 |
| **第二刀（另单）** | 资金列（板块聚合 `fund_flow_1d`）、`consensus_stage_dm1` 接线（随 G-02b）、20 日窗（若 §9 拍扩 horizons）、`EventReaction` 改走 `river.window`（随 G-02c）| — | 本单 |

模块位置建议 `intelligence/services/event_pricing/`（`calendar.py / classify.py / reaction_day.py / anchors.py / reaction.py / receipts.py`），只 import `methodology_backtest.{store, stats, outcomes}` 与 `market_feature_store` 只读；层级门禁按现有规则。参数文件 `methodology/events/event_reaction_params.v0.1.json`，`ev_version = "ev-v0.1+" + sha256(参数文件 ⊕ 日程文件)[:8]`。

---

## 8. 验收（能被验收会话逐条打勾）

1. 两次 `build-calendar / build-anchors / build-reaction` 后三张表内容哈希相等。
2. 分类器：每个 v0 类至少一条正例、一条排除例（`财新 PMI`、`香港 CPI`、`FOMC 纪要`）的单测；未匹配标题 100% 落 `history_event_gaps(reason=unparsed)`，表里无「猜」出来的类。
3. 反应日：夹具 FOMC `event_date` = 周三（美国）→ `reaction_day` = 周四 A 股交易日；周五盘后发布的 `cn_credit_data` → 下周一；节假日顺延测试通过。
4. `latest_known(cn_cpi, 2026-07-08)` 返回 `period=2026-05`；`latest_known(cn_cpi, 2026-09-07)` 返回 `not_yet_released` 且 `next_release_date` 等于日程文件里 8 月 CPI 的发布日；任一返回值里无数值字段（测试断言 schema）。
5. 前视夹具：`fact_sector_daily.pct_chg` 整体后移一天，`fwd_return_*` 与 `pre_return_m` 的差异只出现在被移动日子相关的记录；`d0_return` 不含 D0+1。
6. 每条 `status=ok` 的板块记录满足 `fwd_return_5` 与 `history_outcomes` 同键行相等（测试重算对账）。
7. 形状读数由 `stats.readout` 产出，含 N / k / p / p0 / Wilson / 前后半段 / 四态；N < 10 → `insufficient_n`；`expectation` 与 `state_only` 两套表分开；收据里**不出现**「概率」「可能性」「%后接会」「利好出尽」。
8. 横截面表每个 market 类锚点日各一张，只含板块 / 申万一级实体，`rg` 收据无个股代码（`\d{6}\.(SZ|SH|BJ)`）。
9. 三代理表：`pre_excess_m` 与 `crowding_pct_dm1` 有值率 ≥ 90%（ok 记录内），`consensus_stage_dm1` 100% 为 `gap{not_wired}`（v0 如实）。
10. `source_grade` 分布进收据；`conflict` 条数与 `editorial_date` 列可查；无官方日程的类 0 条 `official`。
11. 参数文件或日程文件任一改动后重建，`history_build_meta.label_version` 变化且旧收据标 `incomparable`。
12. 门禁：`.venv-workbench` 跑 pytest 与 ruff 全绿；pre-commit 11 道通过；不新增硬编码路径；代码不读 `docs/`。

---

## 9. 待用户拍板（不拍按推荐执行）

1. **v0 事件类**：推荐 §3.2 的 7 类（5 个 market 日程类 + 2 个 sector 编辑类）。备选：去掉 `policy_release / industry_event` 只做宏观——不推荐，横截面和 N 主要靠它们。
2. **官方日程谁录**：推荐 agent 从官方页一次性录入（带 URL、录入日），你抽查 10 条；备选你录。
3. **事前窗 m**：推荐 5 个交易日，备选 3；**形状阈值**：板块 2.0% / 指数 1.0% 为候选值，进参数文件。
4. **20 日窗**：推荐 v0 不做（不改共享 `history_outcomes` 的 horizons）；备选把 20 加进 outcomes 重建（版本变、所有已出收据 `incomparable`）。
5. **`policy_release` 反应日**：推荐同日映射 + 收据并列次日读数（§5 最后一行）；备选一律次日。
6. **词表**：推荐新增「事件反应」「事件锚点日历」「反应日」「预期内事件 / 非预期事件」「已定价代理」「形状标签」六条，口语「利好出尽」「抢跑」登记为形状别名；歧义登记「定价」（估值定价 vs 事件定价）、「事件」（编辑催化 / 官方发布 / 盘面内生事件如 `LeaderSuccession`）。审过后再写 `UBIQUITOUS_LANGUAGE.md`。

---

## 10. 对外表述

读数只在仓内与验证文档。对外一律不说「AI 会算事件定价」「历史上 X% 的降息日板块会涨」；不点名任何决策型 Agent 产品（F7）。若要提，只能是「事件日历与事件前后盘面回溯代码化中」，直到 §8 全过。
