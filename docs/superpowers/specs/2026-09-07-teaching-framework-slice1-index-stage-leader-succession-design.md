# 设计：授课框架第一刀——`index_stage` 标签族 + 最高标接力链

> 日期：2026-09-07
> 状态：**设计稿，待用户审**。审过后拆工单（INDEX 编号待分配；#26 已被 RAG 回预算闸预留）。不动代码。
> 上游：`docs/learning/teaching-framework/00-concept-label-skeleton.md`（母本骨架；本 spec 只编码其中已由创始人口述钉住的部分）；`2026-09-06-personal-research-calibration-endstate-design.md` §4.2 两类派生 / §4.4 区间 / §4.6 事件锚点回溯 / §7 门禁；`2026-09-05-time-river-gap-roadmap.md` G-01 (3)、G-02c；`2026-09-04-methodology-backtest-structured-history-design.md`（标签层与四态统计门，本 spec 复用不重造）。
> 红线（沿 08-19 §5）：本 spec 与后续代码**只编码创始人已说出的判读**，转录见骨架 §1.4 / §4；agent 不补判读、不定权重。所有数字阈值是 B 类候选值，进收据不进结论。
> 「[实测]」= 2026-09-06/07 在仓内 `rg` / 读 `schema.sql` / 只读查真库核到的。

---

## 0. 一句话

把创始人 2026-09-06 口述的两件事编成可重算的对象并跑出第一份历史读数：**A.** 指数阶段 `index_stage`——周均线 × 量能 × 偏离度的十条证据旗标、七段计分、三种转点事件，与供应商 `market_stage` 并存分开版本；**D.** 最高标接力链 `LeaderSuccession`——前任最高标断板 → 下一任诞生，事件到事件，两端各一个上下文切片，「高标断板日的低位一般会有衔接」作为第一条 `provenance.kind=teaching` 的候选规则过四态统计门。两件一起做，因为接力链两端的「当时指数在什么阶段」这一列没有 A 就只有供应商的词。

产出是**读数不是结论**：阶段分布、与供应商阶段的列联表、歧义率、接力链节数、衔接命中率对基准、`gap_days` 分布、诞生环境对照——给创始人看，看完纠偏比在纸上继续问快。

---

## 1. 判别变量（验收只锁这些）

1. **确定性**：同一主库快照、同一参数文件，两次重建 `history_teaching_labels` 与 `history_leader_succession` 逐行相同（表内容哈希相等）。路径上无 LLM。
2. **确认日语义**：任一旗标、阶段、接力链字段在交易日 d 上的值只依赖 d 及之前的事实。把 `fact_market_daily` 某列整体后移一天的作弊夹具必须被前视测试抓出。
3. **两套阶段并存**：`tf.stage_coarse` 与供应商 `market_stage` 是两个标签、两个版本号；任一天两者可以不同且都保留；收据里有列联表。任何读取方不得把一个当另一个用。
4. **软判据的硬计算**：阶段 = 证据计分 argmax；并列按转移图取可达者；仍并列输出 `ambiguous` 并附双方证据清单——不猜。歧义率是读数。
5. **缺口 fail-closed**：输入字段为 NULL 的日子不出阶段、不出旗标，记入缺口表；接力链任一节跨涨停表缺失日、或最高板并列 → `unverifiable`，不进 N。
6. **统计门复用**：衔接命中率只经 `methodology_backtest.stats.readout` / `stage_readouts` 出四态；N < 10 → `insufficient_n`；不出任何概率数字，不出「下次也会」。
7. **母本红线**：代码不读、不写 `docs/learning/teaching-framework/`；参数从版本化 JSON 读；`framework_version` 与 `LABEL_VERSION` 是两个命名空间。
8. **不写主库、不改 `schema.sql`**：所有产物落旁路库 `history_labels.duckdb` 的新表；旁路库任何时候可删可重建。

---

## 2. 现状盘点

### 2.1 复用（不重造）

| 层 | 实物 [实测] | 用法 |
|---|---|---|
| 事实 | `fact_market_daily` 413 日（2024-12-20 → 2026-09-02）：`sh_index_close / open`、`sh_week_ma`（= 5 日 MA，`sh_week_ma_source` 四种来源）、`sh_deviation_pct`、`total_amount / amount_vs_yesterday_pct / amount_ma20 / volume_state`、`top3_industry_ratio`、`industry_1..3 (+_ratio)`、`advancers` | A 类全部输入；B 类 `top100_amount_share` 分母 |
| 事实 | `fact_theme_limit_stock_daily`：全量涨停股（只收封住的 `limit_status='U'`），`limit_times` 连板数、`open_times`、`first_limit_time`、`up_stat`、`circ_mv`、`amount`；405 日里**缺 10 日**（`labels.py` 注记，主库 `limit_up` 显示那些天有 40–92 只涨停，是同步缺口） | D 类全部输入；缺日 = 接力链缺口 |
| 事实 | `fact_stock_daily.amount`（2.1M 行） | `top100_amount_share` 分子 |
| 标签层 | 旁路库 `history_labels.duckdb`：`history_labels` 行结构 `(entity_type, entity_id, trade_date, label, value_num, value_text, label_version, computed_at)`、`history_calendar`、`history_data_gaps`、`history_build_meta(build_kind PK)`；`LABEL_VERSION = v2`；已注册 `volume_surge`（`amount_vs_yesterday_pct > 10`）、`ma5_peak/valley_confirmed`、`market_stage`（供应商投影） | 复用 `volume_surge`；新表同结构；`ma5_*` 只作旁列 |
| 统计 | `methodology_backtest.stats.readout(successes, baseline_n, baseline_k, min_n)` → N / k / p / p0 / Wilson / 前后半段 / 四态；`stage_readouts` 按阶段分桶 + 族内 BH；`stage_matched_p0` | 衔接规则读数 |
| 河 | `river.slice_river`（板块实体六轨）、`river_window.windows_around`（按交易日取窗）、`river_query.cohort_compare`（一批日子 × 一个类别列 vs 基准，四态） | 接力链上下文与「诞生环境对照」的形状；`cohort_compare` 需接受旁路库标签（小扩展，§4.6） |
| 词表 | `UBIQUITOUS_LANGUAGE.md`：七段循环、+1.5 / −2.5、成交量决定阶段性质、转点、RPS、两种偏离度 | 阶段名与旗标语义的唯一出处 |

### 2.2 缺口（本 spec 要补的）

1. 没有按创始人规则算出的指数阶段——库里的 `market_stage` 是供应商的（且两套写法，G-05）。
2. 没有转点事件标签。
3. 没有「最高标」序列，也没有断板 / 诞生 / 衔接三个事件的确定性定义落地。
4. 「衔接」这条 knowhow 没有基准率与四态。
5. `cohort_compare` 只接受 `fact_market_daily` 的类别列，接不了旁路库标签。

---

## 3. 设计 A：`index_stage` 标签族

### 3.1 参数文件（B 类候选值的唯一落点）

`methodology/teaching/index_stage_params.v0.1.json`，与 `methodology/rules/` 平级。`framework_version = "tf-v0.1+" + sha256(参数文件)[:8]`，写进每一行 `label_version` 与 `history_build_meta`。改任何一个数字 = 新版本 = 新收据，旧收据凭版本判「不可比」。

```json
{
  "framework_version_base": "tf-v0.1",
  "week_ma_col": "sh_week_ma",
  "deviation_bands": {"oversold_le": -2.5, "overheated_ge": 1.5},
  "volume_surge": {"reuse_label": "volume_surge"},
  "shrink_day": {"basis": "amount_ma20", "alt_basis_noted": "prev_day"},
  "shrink_streak_min": 2,
  "mainline_amount_stepping_up_days": 3,
  "mainline_share_basis": "prev_day",
  "mainline_definitions": ["vendor", "volume_top3"],
  "instant_seal_time": "09:35",
  "rebound_window_days": 5,
  "high_turnover_ratio": null,
  "amount_unit_policy": "fail_closed_on_mismatch",
  "top100_n": 100,
  "min_n": 10
}
```

每个数字都在骨架 §1.5 / §6 标为待填；v0.1 取候选值只为把读数跑出来，**收据必须逐项列出它们**。

### 3.2 旗标目录 v0（`entity_type='market'`，`entity_id='market'`，标签名前缀 `tf.`）

| 标签 | 值 | 派生（全部 `fact_market_daily`，d 日只用 ≤ d 的行） | 骨架来源 |
|---|---|---|---|
| `tf.above_week_ma` | 1/0/NULL | `sh_index_close > sh_week_ma`；任一 NULL → NULL | §1.4 |
| `tf.cross_above_week_ma` | 1/0/NULL | 昨日 `close ≤ ma` 且今日 `close > ma`；昨日缺行 → NULL | §1.4 |
| `tf.cross_below_week_ma` | 1/0/NULL | 昨日 `close > ma` 且今日 `close < ma` | §1.4 |
| `tf.gap_down_open` | 1/0/NULL | `sh_index_open < 昨日 sh_index_close` | §1.4「跳空低开」 |
| `tf.shrink_day` | 1/0/NULL | `total_amount < amount_ma20`（v0.1 基准；备选前日） | §1.5 待填 → 候选 |
| `tf.volume_shrink_streak` | n/NULL | 截至当日连续 `shrink_day` 天数 | §1.4「缩量的过程」 |
| `tf.deviation_band` | text | `sh_deviation_pct` → `oversold`(≤ −2.5) / `below`(−2.5, 0) / `above`[0, 1.5) / `overheated`(≥ 1.5) | 词表数字，软判据 |
| `tf.deviation_narrowing` | 1/0/NULL | 在周均线下方且 `sh_deviation_pct` 较昨日上升（往周均线靠） | §1.4 左底向上持续证据 |
| `tf.mainline_share_expanding.<def>` | 1/0/NULL | `def=volume_top3`：`top3_industry_ratio` 较昨日上升；`def=vendor`：供应商主线板块当日成交额占比较昨日上升（主线表覆盖 106 日，其余 NULL） | §1.4「成交占比扩大」 |
| `tf.mainline_amount_stepping_up.<def>` | 1/0/NULL | 主流板块（两口径）成交额连续 `mainline_amount_stepping_up_days` 日上升 | §1.4「逐步放量」 |

旁列（写入但**不进计分**）：已注册的 `ma5_peak_confirmed / ma5_valley_confirmed`、供应商 `market_stage / volume_state / ice_point`。

### 3.3 七段证据表与计分

证据表逐字对应骨架 §1.4「各阶段证据」，这里只写成机器可读形状（E = 进入证据，H = 持续证据）：

| `stage_coarse` | 证据 |
|---|---|
| 左底向下 | E：`cross_below_week_ma ∧ (volume_surge ∨ gap_down_open)`；H：`¬above_week_ma ∧ deviation_band ∈ {below}` |
| 左底向上 | E：`deviation_band = oversold`；H：`¬above_week_ma ∧ deviation_narrowing` |
| 缩量右底 | H：`volume_shrink_streak ≥ shrink_streak_min ∧ ¬above_week_ma` |
| 共建主线阶段 | E：`cross_above_week_ma ∧ volume_surge`；H：`above_week_ma` |
| 主流主升 | H：`above_week_ma ∧ mainline_amount_stepping_up.<任一 def> ∧ mainline_share_expanding.<同一 def>` |
| 高位震荡 | E：`deviation_band = overheated`；H：`above_week_ma ∧ ¬volume_surge` |
| 回踩周均线 | H：`above_week_ma ∧ deviation_band = above ∧ shrink_day`（**仅词表「缩量回落」，创始人未确认**，收据单列其命中天数） |

计分：每段得分 = 命中的 E 与 H 条目数（每条 1 分；E 只在发生日计分）。`tf.stage_coarse` = 最高分段。**并列**：取从昨日 `stage_coarse` 沿转移图可达的那个；转移图 = 词表七段循环 + 两条已知跳转（高位震荡 → 左底向下 直接；左底向上 → 缩量右底 直接）；仍并列或昨日无阶段 → `ambiguous`。全部得 0 分 → `no_evidence`。两者都不猜，都进歧义率。

`tf.stage_evidence`：value_text = JSON `{scores:{段:分}, hits:[旗标], from:昨日段, resolution:"argmax|graph|ambiguous|no_evidence"}`——这就是骨架 §1.3 说的「置信档 + 证据清单」，也是投影（09-06 §4.5）将来往上下文里塞的那一小段。

`tf.stage_fine`：coarse 内细分——缩量右底 → 首日起 `volume_shrink_streak` 仍在增长为「二次探底」、否则「缩量右底」；高位震荡 → 进入日为「见顶」、其后「高位震荡」；其余同名；「确认左底」「分歧转一致共振」两段归属未定 → 相应日子 `unassigned`（骨架 §1.1）。

转点事件（由阶段序列派生，`1/0`）：`tf.turn_up` = 当日 `stage_coarse` 首次变为共建主线且昨日为周均线下方三段之一；`tf.turn_top` = 首次变为高位震荡；`tf.turn_down` = 首次变为左底向下。

### 3.4 与供应商阶段的关系

不归一、不映射、不替代。收据出一张列联表 `tf.stage_coarse × normalize_stage(market_stage)`（用 `river_query.normalize_stage` 兜两套写法），只报计数。G-05 归一是它自己的工单；本 spec 不动 `LABEL_VERSION`。

### 3.5 存储

新表 `history_teaching_labels`，列与 `history_labels` 相同；`history_build_meta.build_kind='teaching_labels'`，`label_version = framework_version`。**不放进 `history_labels`**：v2 构建的 `reset_tables` 会整表 DROP，混放会互相冲掉。`history_data_gaps` 同样另起 `history_teaching_gaps(trade_date, missing_cols, framework_version, computed_at)`。

### 3.6 PIT

标签 `computed_at` 是现在，不是历史；按 09-06 §4.2 它们是 `derivation=deterministic`，在河上作为派生对象时 `recorded_at` 取其成员事实行的 `recorded_at`（`fact_market_daily.updated_at`，只是上界——`river.py` 注记）。本 spec 不解决 PIT 上界问题（工单 #27 的事），只保证**可重算**。收据里按 `sh_week_ma_source` 分组报天数，让读者知道多少天的周均线是回填复算的。

---

## 4. 设计 D：最高标接力链 `LeaderSuccession`

### 4.1 三个事件的确定性定义（用户口述，骨架 §4）

以 `fact_theme_limit_stock_daily` 按 `(trade_date, stock_ts_code)` 折叠后的 `limit_times` 为唯一输入；交易日历取 `history_calendar`。

- **`top(d)`**：d 日 `limit_times` 最大且 `≥ 3` 的**唯一**个股；`max < 3` → `None`（该日无最高标）；并列 → `tie`（用户：「走到最后肯定只有一只」，出现即 `unverifiable`，不猜）。
- **断板日 T**：`top(T−1)` 存在，且 `top(T−1)` 在 T 日**不在涨停表**（表只收封住的，不在表 = 收盘未封 = 断板，与用户「炸板不分」一致）。若 `top(T−1)` 在 T 日仍在表但不再是 max（被更高者超越）→ 记 `overtaken` 事件到旁表，不是断板，不成节。
- **候选 `candidates(T)`**：T−1、T、T+1 三日涨停表中 `limit_times ≤ 2` 的个股并集，去重，剔除 `top(T−1)`。
- **下一任 `leader_next`**：满足 `d ≥ T` 且 `top(d)` 存在 且 `top(d) ≠ top(T−1)` 的最小 d 上的 `top(d)`；`birth_day = d`。历史尾部找不到 → 该节 `open`，不进 N。
- **`handoff`** = `leader_next ∈ candidates(T)`。注意：若 `leader_next` 在 T−1 已 ≥ 3 板（只是低于前任），它不在候选里 → `handoff = false`——这正是「低位衔接」与「高位接力」的区别，用户的假设只关于前者。
- **`gap_days`** = T 到 `birth_day` 的交易日数（可为 0：前任断板当天新任诞生）。

### 4.2 节的字段

```text
history_leader_succession
  node_id                 = sha256(leader_i, break_day)[:16]
  leader_i / leader_i_name / leader_i_peak_boards
  break_day
  candidates_json         [{stock, name, day, limit_times}]
  leader_next / leader_next_name / birth_day / birth_boards
  handoff                 bool
  gap_days                int
  path_json               leader_next 从首次出现在候选窗到 birth_day 的逐日 {day, in_table, limit_times, open_times, first_limit_time, up_stat}
  shape_tags_json         形态族 v0（§4.3）
  context_break_json      §4.4
  context_birth_json      §4.4
  status                  ok | unverifiable(reason) | open
  framework_version / computed_at
```

跨涨停表缺失日（10 日）的节：若缺失日落在 `[T−1, birth_day]` 内 → `unverifiable(data_gap)`。

### 4.3 形态族 v0（用户：「不用特别细化」）

对 `leader_next` 的 `path`：

| 标签 | 判据 |
|---|---|
| `rebound_after_break`（断板反包） | 窗内曾连板 ≥ 2 → 至少 1 日不在表 → 再入表 |
| `n_shape`（N 字） | 窗内曾首板 → 1–2 日不在表 → 再入表 |
| `reseal`（回封板） | `birth_day` 或其前一日 `open_times ≥ 1` |
| `one_word_or_instant`（一字 / 秒板，近似） | `open_times = 0` 且 `first_limit_time ≤ params.instant_seal_time`（候选 `09:35`） |
| `high_turnover`（换手板） | `amount / circ_mv ≥ params.high_turnover_ratio`（候选值待标，v0 只出比值不打标签） |

炸板反包无 Z 数据，并入 `rebound_after_break`（骨架 §4 已记）。窗口 `m` 取 `params.rebound_window_days`（候选 5）。

### 4.4 两端上下文

`context_break` 与 `context_birth` 同一组列，全部从旁路库与主库确定性取，缺则 `gap`：

- A 类：`tf.stage_coarse / stage_fine / deviation_band / stage_evidence`；供应商 `market_stage`（对照列）。
- B 类（本刀顺带建，都是一列 SQL）：`tf.max_boards`（`max(limit_times)`）、`tf.promotion_rate_total`（今日 `limit_times ≥ 2` 数 / 昨日涨停数）、`tf.top100_amount_share`（`fact_stock_daily.amount` 前 100 之和 / `fact_market_daily.total_amount`；两表单位不一致则改分母为个股和并记口径）、`fact_market_daily.limit_up / advancers / total_amount` 原值。
- C 类：**只带量板块**（`industry_1..3` 原值，零成本）；价板块 / 锐度 / 主流两口径是第二刀（§7），本刀这些列为 `gap{reason=slice2}`。

### 4.5 衔接规则的读数（复用统计门）

```text
候选规则  leader_handoff_from_low_boards   provenance.kind = teaching
successes  = [node.handoff for node in nodes if status == ok]  按 break_day 升序
baseline   = 对每个非断板交易日 D：candidates(D) 同定义；outcome_D = 「birth_day ≥ D 的下一任最高标（相对 top(D−1)，若无则相对 None）∈ candidates(D)」
             baseline_k / baseline_n 在全部非断板日上计
readout    = stats.readout(successes, baseline_n, baseline_k, min_n=10)
by_stage   = stats.stage_readouts({stage: successes 子序列}, {stage: (n0, k0)}, min_n=10, q=0.05)，stage = context_break.tf.stage_coarse
附读数     = gap_days 分布（分位数与直方，不做门槛）、overtaken 事件数、tie / data_gap 节数
```

基准这么定的理由：任何最高标都必然曾是首板 / 二板，所以「下一任出自某个三天窗」在随机窗上也有基线概率；只有把断板日和随机日放在同一定义下比，量到的才是「断板这个时点」有没有超额。

**本刀不把这条规则写进 `methodology/rules/*.json`**：现有编译器的 outcome 是前瞻收益，接力链的 outcome 是布尔；DSL 扩展归 G-16。这里与 `river_query.cohort_compare` 同做法——直接调 `stats`，不建第二套统计口径。

### 4.6 诞生环境对照

`cohort_compare(dates = birth_days, feature = "tf.stage_coarse")` → 每个阶段桶的诞生日占比 vs 全样本日占比 + 四态。需要 `cohort_compare` 接受旁路库标签作 `feature`（现只接受 `fact_market_daily` 三列）——小扩展：`feature` 允许 `"tf.<label>"`，从 `history_teaching_labels` 取 `value_text`。同样对 `deviation_band`、`volume_state` 各出一张。**只出表，不登记规则**（骨架 §4.1 第二段）。

---

## 5. 数据现实与风险（写在前面，读数出来别惊讶）

| 现实 [实测] | 影响 | 处置 |
|---|---|---|
| 涨停表 405 日缺 10 日 | 跨缺失日的节 `unverifiable`；N 少几节 | 收据列出缺失日与受影响节 |
| 最高标 ≥ 3 板才算 | 情绪冰点期可能连续多日无最高标；一节的 `gap_days` 可能很长 | `gap_days` 分布如实报；不设上限 |
| 并列最高 | 用户认为不会有；数据上可能有 | `tie` → `unverifiable`，计数进收据；若多到影响 N 再回来问 |
| `sh_week_ma_source` 四种来源，存量行 `unknown_preexisting` | 早期周均线不知从何而来 | 收据按来源分组报天数；不阻塞 |
| 供应商主线表只 106 日 | `mainline_*.vendor` 大量 NULL → 主流主升的 vendor 口径证据常缺 | 两口径分开报；`volume_top3` 全历史可算 |
| 413 个交易日 | 分阶段桶后 N < 10 常态 | 先出总体四态；分桶 `insufficient_n` 如实显示 |
| 缩量基准取 MA20 是候选 | 换成前日基准阶段序列会变 | 参数进 `framework_version`；收据可比性由版本判 |
| 「回踩周均线」证据仅来自词表 | 可能与创始人心中不同 | 收据单列该段命中天数，待确认 |

## 5.1 审查后执行补充契约

本节覆盖前述条款的执行歧义；实现、测试和收据以本节为准。

1. **两个时钟分开**：`context_break` 是 `anchor_as_of=break_day` 的即时上下文，只能读取截至断板日可见的事实；`forward` 是从断板日到 `birth_day` 的事件链；`context_birth` 是 `context_target=birth_day`，只有 `knowledge_cutoff >= birth_day` 时才可生成。`open`、`unverifiable` 和 `hindsight=true` 的记录不得进入衔接统计。§1.2 的确认日约束只适用于 `context_break` 和 A/B 标签，不适用于已明确标注为 realized 的后验字段。
2. **覆盖先于事件判定**：先建立按 `history_calendar` 的涨停表覆盖表，区分 `covered_empty` 与 `missing`。缺失日跨入断板日、候选窗或 forward 链时，整节为 `unverifiable(data_gap)`；不能用“无涨停行”直接判断断板。
3. **基准风险集固定**：baseline 只纳入 `D-1/D/D+1` 可见、`top(D-1)` 唯一存在、涨停源覆盖完整、下一任已到期且无 tie/field-null 的日期；`top(D-1)=None`、尾部 open、缺口和无法确定的记录排除并在收据计数。候选和 outcome 与事件节点使用完全相同的去重和到期规则。按 top 任期去重，收据记录窗口重叠数。
4. **可复现哈希与收据**：表内容 canonical hash 按主键排序并排除 `computed_at`；参数 JSON 先做 canonical JSON，再计算哈希。`history_build_meta` 只存当前指针，另建不可变 teaching receipt/build_id，保存 source fingerprint、framework_version、label_version、参数哈希、coverage、缺口和 canonical hash；旧版本收据标记 `incomparable`，不能被覆盖。
5. **输入源和版本**：vendor 主线旗标明确依赖 `fact_mainline_sector_daily`，按 `(trade_date, sector_ts_code)` 去重后再聚合；金额单位不一致直接 fail-closed，不运行时更换分母。复用 `volume_surge` 时记录其实际 `label_version`。实现不得假定 spec 中的 `LABEL_VERSION=v2`，必须从本次源快照和代码常量读取并写入 receipt。
6. **证据与转点**：`hits` 保存谓词命中（包括否定分支、文本值和连续天数），不要求值均为 1。`turn_*` 定义为每次从一个有效 coarse 阶段进入目标阶段；遇到 `ambiguous/no_evidence/gap` 断开，完整有向边和自环写入参数/receipt。`stage_fine` 对缺字段输出 `unassigned`，并验收其值属于对应 coarse 的允许集合。
7. **B 标量和形态缺失**：B 标量列入标签目录并固定 NULL/零分母/覆盖规则；`promotion_rate_total` 按去重后的股票日计数。`top100_amount_share` 固定 `top100_n=100`、单位和分母，单位或金额覆盖不足即 gap。当前 `open_times`、部分 `first_limit_time/circ_mv/limit_times` 为空时，相关形态输出 `unknown`/gap，不得当作 false；时间字段先规范化为 `HH:MM`。
8. **cohort_compare 扩展**：`tf.*` 特征显式接收旁路库路径、版本和值类型；`NULL/ambiguous/no_evidence` 的入桶规则、基准日期宇宙、重复 birth day 去重和缺口数写入 receipt，不复用会剥除“阶段”后缀的 `normalize_stage`。

---

## 6. 非目标

- 不写母本内容；不替创始人定「确认左底」「分歧转一致共振」归属；不定权重。
- 不改供应商 `market_stage`、不做 G-05 归一、不动 `LABEL_VERSION`。
- 不把衔接规则写进规则 JSON / 编译器（G-16）。
- 不接每日复盘 / 带读 / 投影（G-03 接线、G-14 另做）；不做 UI；不做 LLM 解读。
- 不做舆论 / 资金轨；不做个股 UP 线入库；不做板块 UP 线。
- 不改 BP / deck；对外仍写「授课框架代码化中」直到 G-01 验收 (a)–(d)。
- 价板块 / 锐度 / 主流两口径的 C 类标签是第二刀（§7），本刀只留列位。

---

## 7. 分刀（工单拆法，供 writing-plans 用）

| 刀 | 内容 | 产物 | 依赖 |
|---|---|---|---|
| 1 | 参数文件 + 旗标目录 v0（§3.2）+ 新表 + 前视测试夹具 | `history_teaching_labels` 全历史；单测每旗标一条 | 无 |
| 2 | 七段计分 + 转移图 + `ambiguous / no_evidence` + `stage_fine` + 转点事件 + 与供应商列联表 | `tf.stage_*`、`tf.turn_*`；收据 §8 (1)–(6) | 刀 1 |
| 3 | 接力链构建器（§4.1–4.3）+ B 类三列 + `overtaken` 旁表 | `history_leader_succession`；单测覆盖 tie / data_gap / overtaken / gap 0 / handoff 真假 | 刀 1（B 类列） |
| 4 | 衔接读数 + 基准 + 按阶段分桶（§4.5）+ `cohort_compare` 接旁路库标签 + 诞生环境对照（§4.6） | 收据 §8 (7)–(9) | 刀 2、3 |
| 5 | CLI（`scripts/teaching_framework.py build-labels / build-succession / report`）+ 自测（照 `theme-fermentation-tracer/selftest.py` 造最小库）+ 验证文档 | `docs/verification/2026-09-xx-teaching-slice1.md` | 刀 1–4 |
| **第二刀（另单）** | C 类：量 / 价 / 锐度 / 主流两口径 板块角色标签（骨架 §3）；接力链上下文补列 | — | 本单刀 3 |

模块位置建议 `intelligence/services/teaching_framework/`（`params.py / flags.py / index_stage.py / leader_succession.py / receipts.py`），只 import `methodology_backtest.{store,stats}` 与 `market_feature_store` 只读；层级门禁按现有规则。

---

## 8. 验收（能被验收会话逐条打勾）

1. 两次 `build-labels` 后 `history_teaching_labels` 内容哈希相等；`build-succession` 同理。
2. 前视夹具：把 `fact_market_daily.sh_index_close` 整体后移一天，`tf.cross_above_week_ma` 的差异只出现在被移动的日子及之后，且测试断言这一点。
3. 每个有完整输入的交易日恰有一个 `tf.stage_coarse`；输入 NULL 的日子在 `history_teaching_gaps` 有一行且无阶段行。
4. `tf.stage_coarse` 取值集合 ⊆ 七段 ∪ {`ambiguous`, `no_evidence`}；`tf.stage_evidence` 每行可解析且 `hits` 里的旗标当日均为 1。
5. 收据含 `tf.stage_coarse × normalize_stage(market_stage)` 列联表，两列都非空，且存在至少一天两者不同（否则等于抄了供应商）。
6. `tf.turn_up / turn_top / turn_down` 之和 = 阶段序列中对应段的进入次数（测试从序列重算对账）。
7. `history_leader_succession` 每个 `status=ok` 的节满足：`top(break_day−1) = leader_i` 且 `leader_i ∉ 涨停表(break_day)`；`birth_day ≥ break_day`；`handoff` 与 `leader_next ∈ candidates_json` 一致（测试重算）。
8. 衔接读数由 `stats.readout` 产出，字段含 N / k / p / p0 / Wilson / 前后半段 / 四态；N < 10 时四态为 `insufficient_n`；按阶段分桶任一桶 N < 10 显示 `insufficient_n` 而非比率。收据里**不出现**「概率」「可能性」字样与百分号后接「会」。
9. 诞生环境对照表由 `cohort_compare` 产出，`feature="tf.stage_coarse"` 与 `"tf.deviation_band"` 各一张，带四态与 BH。
10. 参数文件哈希进 `framework_version`；改动任一数字后重建，`history_build_meta.label_version` 变化且旧收据被标 `incomparable`。
11. `rg -l "teaching-framework/" intelligence/ scripts/` 对新增代码零命中（代码不读母本目录）。
12. 门禁：`.venv-workbench` 跑 pytest 与 ruff 全绿；pre-commit 11 道通过；不新增硬编码路径。

---

## 9. 待用户拍板（不拍按推荐执行）

1. **缩量基准** v0.1 用 `amount_ma20`（推荐：表里现成、比前日噪声小），备选前日。
2. **成交占比扩大**用 `top3_industry_ratio` 较昨日上升（推荐：最简单、可解释），备选较 5 日均。
3. **秒板阈值** `first_limit_time ≤ 09:35`（推荐候选值），**反包窗口** 5 个交易日（推荐候选值）。
4. **`overtaken`（被超越）事件**记旁表但不成节（推荐记，将来「高位接力」是另一条规则的原料）。
5. **第二刀（C 类板块角色）**紧随本单还是等本单读数看过再说（推荐紧随——接力链上下文里价 / 锐度两列是你点名要看的）。

---

## 10. 对外表述

读数只在仓内与验证文档；对外一律「授课框架代码化中」，直到 G-01 验收 (a)–(d) 全过。任何对外句子里不得出现「AI 学会了看阶段」「历史上 X% 会衔接」。
