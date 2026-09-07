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
  "volume_level": {"basis": "amount_vs_ma20_pct", "moderate_from_pct": 100, "surge_from_pct": 120},
  "surge_in_trend": {"role": "view"},
  "breadth_min_stocks": 4000,
  "index_range_windows": [5, 10],
  "breakout_confirm_days": 3,
  "deviation_streak_min": 3,
  "leader_top": {"tie_policy": "group", "break_rule": "all_members_off_table"},
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

`volume_level` 是量能三档的尺子：**用户 2026-09-07 第十段「20 日均量，量能比吧」**——当日成交额 / 20 日均量 × 100（复盘会 `market_amount_vs_ma20_pct` 同一口径，我们的 `total_amount / amount_ma20` 与之 405 天中位差 −0.01）；「100–120 属于温和放量」「20 是一个阈值」落在这把尺子上：< 100 缩量、100–120 温和放量、> 120 暴量。此前按环比读的 `volume_surge = {threshold_pct: 20}` 作废（环比在平台八段之间分不开任何两段，骨架 §8.3）；回测层 `volume_surge`（环比 > 10）是另一个对象，不互相引用。`breadth_min_stocks` 是水位标量的覆盖门（`fact_stock_daily` 正常日 5,000+ 只，2026-06-24 只有 2,169 只），候选 4000。`index_range_windows` 是用户 09-07 第四段「区间涨幅和振幅，周均偏离度的变化」的窗口候选（5 / 10 日，沿用创始人对价板块 5 日、锐度 3 / 5 / 10 日、MA5 / MA10 的习惯窗口）；它只喂视角列，不进计分——第七段答「那一个区间就是」回归周均的那一腿，腿口径的涨幅 / 振幅另有 `tf.ma_episode_*`。`breakout_confirm_days = 3` 与 `deviation_streak_min = 3` 是第七段的两个「三天」：「上穿后三天内放量」（进计分）与「持续走高 / 逐渐走低 / 回归周均」的连续天数（暂只进收据）。`leader_top` 记录第六 / 七段的并列读法（并列成组、全员断板才算断板）。

### 3.2 旗标目录 v0（`entity_type='market'`，`entity_id='market'`，标签名前缀 `tf.`）

| 标签 | 值 | 派生（全部 `fact_market_daily`，d 日只用 ≤ d 的行） | 骨架来源 |
|---|---|---|---|
| `tf.above_week_ma` | 1/0/NULL | `sh_index_close > sh_week_ma`；任一 NULL → NULL | §1.4 |
| `tf.cross_above_week_ma` | 1/0/NULL | 昨日 `close ≤ ma` 且今日 `close > ma`；昨日缺行 → NULL | §1.4 |
| `tf.cross_below_week_ma` | 1/0/NULL | 昨日 `close > ma` 且今日 `close < ma` | §1.4 |
| `tf.gap_down_open` | 1/0/NULL | `sh_index_open < 昨日 sh_index_close` | §1.4「跳空低开」 |
| `tf.open_below_week_ma` | 1/0/NULL | `sh_index_open < ma`（下穿日上 = 缺口本身穿过了周均线） | 第十三段「跳空低开跌破周均」；只作视角与 `left_down_entry.gap_through_ma_day1` 可选读法 |
| `tf.money_losing_day` / `tf.money_losing_streak` | 1/0/NULL · num | 承接 5 日均值（`limit_premium_ma5_pct`）`< money_losing.lt_pct`（1.0，训练期 p10 取整）；连续天数 | 第十四段「亏钱效应也要可量」；只作视角与王朝链的亏钱效应计数，不进任何一段的计分 |
| `tf.amount_vs_ma20_pct` | num/NULL | `total_amount / amount_ma20 × 100`（量能比；6 位小数） | 第十段「20 日均量，量能比吧」 |
| `tf.volume_band` / `tf.volume_expanding` / `tf.volume_surge` | text / 1/0 / 1/0 | 量能比 `< moderate_from_pct` → `shrink`；`[100, 120]` → `moderate`；`> surge_from_pct` → `surge`；`volume_expanding` = 量能比 ≥ 100（「放量」= 至少温和放量，突破确认 / 放量跌破 / 残差判断用它）；`volume_surge` = > 120（暴量）。`volume_band` **只作视角写出，不进计分**（第四段：温和 / 缩量「不是某个阶段特有」） | §1.4「100–120 属于温和放量」「20 是一个阈值」+ 第十段尺子 |
| `tf.shrink_day` | 1/0/NULL | `total_amount < amount_ma20`（v0.1 基准；备选前日） | §1.5 待填 → 候选 |
| `tf.volume_shrink_streak` | n/NULL | 截至当日连续 `shrink_day` 天数 | §1.4「缩量的过程」 |
| `tf.deviation_band` | text | `sh_deviation_pct` → `oversold`(≤ −2.5) / `below`(−2.5, 0) / `above`[0, 1.5) / `overheated`(≥ 1.5) | 词表数字，软判据 |
| `tf.deviation_narrowing` | 1/0/NULL | 在周均线下方且 `sh_deviation_pct` 较昨日上升（往周均线靠） | §1.4 左底向上持续证据 |
| `tf.mainline_share_expanding.<def>` | 1/0/NULL | `def=volume_top3`：`top3_industry_ratio` 较昨日上升；`def=vendor`：供应商主线板块当日成交额占比较昨日上升（主线表覆盖 106 日，其余 NULL） | §1.4「成交占比扩大」 |
| `tf.mainline_amount_stepping_up.<def>` | 1/0/NULL | 主流板块（两口径）成交额连续 `mainline_amount_stepping_up_days` 日上升 | §1.4「逐步放量」 |
| `tf.sh_index_pct_chg_<N>d` | num/NULL | `(sh_index_close / 窗口前一日 close − 1) × 100`，`N ∈ index_range_windows`；`N + 1` 行须日历连续，否则 NULL + 缺口 `window_incomplete` | §1.4 09-07 第四段「区间涨幅」；**只作视角，不进计分**（§9.12） |
| `tf.sh_index_amplitude_<N>d` | num/NULL | `(窗口内 max(sh_index_high) − min(sh_index_low)) / 窗口前一日 close × 100`（与涨幅同一基准）；窗口内任一日高低价 NULL → NULL + `high_low_null` | 「振幅」；同上 |
| `tf.sh_deviation_change_<N>d` | num/NULL | `sh_deviation_pct − 窗口前一日 sh_deviation_pct`（百分点） | 「周均偏离度的变化」；同上 |

| `tf.up_candle` | 1/0/NULL | `sh_index_close > sh_index_open` | §1.4 09-07 第六段「上穿周均线往往就伴随放量和指数的阳线」；只作视角 |
| `tf.deviation_rising_streak` / `tf.deviation_falling_streak` / `tf.deviation_toward_ma_streak` | n/NULL | 截至当日偏离度连续上升 / 连续下降 / \|偏离度\| 连续收窄的天数；前一日缺或不相邻 → NULL | §1.3 第六段「偏离度持续走高 / 回归周均 / 逐渐走低」；几天算「持续」待拍（§9.12） |
| `tf.ma_episode_day` / `tf.ma_episode_extreme_dev` / `tf.ma_episode_retrace_pts` / `tf.ma_episode_retrace_peak_pts` | num/NULL | 自观察到的上下穿起的同侧一段（腿）：第几天 / 极值偏离度（下方最小、上方最大）/ 从极值回抽了多少（百分点，≥ 0）/ 回抽峰值；起点没看到（史前、缺口后）→ 全 NULL | §1.3 第六段流程「下穿 → 探底 → 反弹到周均线 → 又回踩」的最小统计量 |
| `tf.ma_episode_pct_chg` / `tf.ma_episode_amplitude` / `tf.ma_episode_days_since_high` | num/NULL | 本腿涨幅（收盘 / 穿越前一日收盘 − 1）/ 本腿振幅（腿内最高 − 最低，同一基准）/ 距本腿最高点几天；腿内任一日高低价缺 → 振幅与距高点天数 NULL | 第七段「那一个区间就是」：区间 = 腿 |
| `tf.days_since_cross_above` | n/NULL | 上穿当日 = 0，其后逐日 +1；下方或起点未见 → NULL | 第七段「上穿后三天内放量」的谓词输入 |
| `tf.surge_in_trend` | 1/0/NULL | `above_week_ma ∧ volume_surge ∧ ¬(days_since_cross_above ≤ breakout_confirm_days)` | 第八段「趋势中放量不代表就见顶，也可能是行情升级……有好有坏」：**只作视角，不作任何一段的证据**（参数 `surge_in_trend.role = view`）；收据 `views_by_event` 回溯其后走势 |
| `tf.cross_below_kind` | text | 下穿日写 `first` / `retest`：其前的上方一段若 ≤ `breakout_confirm_days` 天且无放量（残差触碰）→ `retest`，否则 `first`；非下穿日 NULL | 第六段「左底向下是第一次从周均线下穿」「反弹到周均线……又回踩探底」+ 第七段「一般都会触碰一下周均」「不放量的上穿基本都是回落」；**残差 = 突破窗口内无放量是 agent 的接法，待认（§9.13）** |
| `tf.below_ma_cycle_day` | n/NULL | 自 `first` 下穿起数的一轮下方周期第几天，跨残差上穿不中断；某次上穿放量或在上方待满 > `breakout_confirm_days` 天 → 周期结束（NULL） | 同上；真库 29 轮，中位 7 天 |
| `tf.index_high_not_rising_<N>d` / `tf.index_range_converging_<N>d` | 1/0/NULL | 近 N 日最高 ≤ 前 N 日最高；近 N 日（最高 − 最低）< 前 N 日；两块共 2N 日须日历连续且高低价齐 | 第七段「是的高点不抬高加收敛」= 高位震荡的区间结构；只作视角（§9.12） |

以上各组与水位四列同按 6 位小数规范化写入。

旁列（写入但**不进计分**）：供应商 `market_stage / volume_state / ice_point / sh_week_ma_source` 与 `fact_market_daily` 原值 `total_amount / limit_up / advancers`，一律以 **`src.` 前缀**写入 `history_teaching_labels`（`src.market_stage` 等），**不得**出现在 `tf.` 命名空间——否则读取方无法区分供应商阶段与教学阶段（§1.3）。`ma5_peak_confirmed / ma5_valley_confirmed` 留在 `history_labels`，不复制。

### 3.3 七段证据表与计分

证据表逐字对应骨架 §1.4「各阶段证据」，这里只写成机器可读形状（E = 进入证据，H = 持续证据）：

| `stage_coarse` | 证据 |
|---|---|
| 左底向下 | E：`cross_below_week_ma ∧ (volume_surge ∨ gap_down_open)`；H：`¬above_week_ma ∧ deviation_band ∈ {below}` |
| 左底向上 | E：`deviation_band = oversold`；H：`¬above_week_ma ∧ deviation_narrowing` |
| 缩量右底 | H：`volume_shrink_streak ≥ shrink_streak_min ∧ ¬above_week_ma` |
| 共建主线阶段 | E：`days_since_cross_above ≤ breakout_confirm_days ∧ volume_surge ∧ above_week_ma`（**用户 09-07 第七段**：「上穿要配合放量，不然很多上穿基本都是回落，或者上穿后三天内放量」；此前的「仅上穿当日」作废）；H：`above_week_ma`（第五段确认：上方无其他证据时默认此段） |
| 主流主升 | H：`above_week_ma ∧ mainline_amount_stepping_up.<任一 def> ∧ mainline_share_expanding.<同一 def>` |
| 高位震荡 | E：`deviation_band = overheated`；~~E：突破窗口之外的放量 = 盛极而衰~~（**第八段撤回**：「趋势中放量不代表就见顶，也可能是行情升级……这个放量是个因子，有好有坏」→ 改作视角 `tf.surge_in_trend`，不计分）；H：`above_week_ma ∧ ¬volume_surge`（**「量能不再扩张」是 agent 对照词表的写法，创始人未确认**，收据单列其命中天数；09-07 第四段说温和 / 缩量「不是某个阶段特有」，而 `¬volume_surge` = shrink ∪ moderate，删留见 §9.12）。**待拍**：09-07 第四段「高位震荡并不是只看周均和量能，还要看指数的形态，区间涨幅和振幅，周均偏离度的变化」——四维度的口径与门槛未定，未定前只作视角（§3.2 末三行），不计分 |
| 回踩周均线 | H：`above_week_ma ∧ deviation_band = above ∧ shrink_day`（**仅词表「缩量回落」，创始人未确认**，收据单列其命中天数） |

计分：每段得分 = 命中的 E 与 H 条目数（每条 1 分；E 只在发生日计分）。`tf.stage_coarse` = 最高分段。**并列**：取从昨日 `stage_coarse` 沿转移图可达的那个；转移图 = 词表七段循环 + 两条已知跳转（高位震荡 → 左底向下 直接；左底向上 → 缩量右底 直接）**+ 每段自环**（留在原段是合法转移：并列双方若是「留」与一个非相邻段，取「留」；若是「留」与直接后继，仍并列）；仍并列或昨日无阶段 → `ambiguous`。全部得 0 分 → `no_evidence`。两者都不猜，都进歧义率。完整有向图（含自环）随收据写出。

`tf.stage_evidence`：value_text = JSON `{scores:{段:分}, hits:[{stage, predicate}], inputs:{旗标:值}, confidence:{stage, hits, possible, missing, margin}, from:昨日段, resolution:"argmax|graph|ambiguous|no_evidence", tied:[…]}`——这就是骨架 §1.3 说的「置信档 + 证据清单」，也是投影（09-06 §4.5）将来往上下文里塞的那一小段。`confidence` 是用户 09-07「不是满足某一个条件就写死了结论」的落点：`hits/possible` 说这段有几条视角命中、`missing` 说缺哪几条、`margin` 说领先第二名几分（0 = 靠昨日阶段破并列，1 = 一条视角之差）；收据按两者报天数分布，并写出每段的全部可用视角 `stage_predicate_catalog`。环比与偏离度原始值以 `src.amount_vs_yesterday_pct` / `src.sh_deviation_pct` 旁列随行写出。

`tf.stage_fine`：coarse 内细分——缩量右底 → 首日起 `volume_shrink_streak` 仍在增长为「二次探底」、否则「缩量右底」；高位震荡 → 进入日为「见顶」、其后「高位震荡」；其余同名；「确认左底」「分歧转一致共振」两段归属未定 → 相应日子 `unassigned`（骨架 §1.1）。

转点事件（由阶段序列派生，`1/0`）：`tf.turn_up` = 当日 `stage_coarse` 首次变为共建主线且昨日为周均线下方三段之一；`tf.turn_top` = 首次变为高位震荡；`tf.turn_down` = 首次变为左底向下。

### 3.4 与供应商阶段的关系

不归一、不映射、不替代。收据出一张列联表 `tf.stage_coarse × normalize_stage(market_stage)`（用 `river_query.normalize_stage` 兜两套写法），只报计数。G-05 归一是它自己的工单；本 spec 不动 `LABEL_VERSION`。

### 3.5 存储

新表 `history_teaching_labels`，列与 `history_labels` 相同；`history_build_meta.build_kind='teaching_labels'`，`label_version = framework_version`。**不放进 `history_labels`**：v2 构建的 `reset_tables` 会整表 DROP，混放会互相冲掉。`history_data_gaps` 同样另起 `history_teaching_gaps(trade_date, missing_cols, framework_version, computed_at)`。

**参照标注表 `history_reference_stages`**（用户 09-07 第十段「当参照」）：`(source, trade_date)` 主键，逐日 `cycle_stage / external_cycle / internal_cycle / is_ice_point / ice_point_level / 量能比 / 环比 / 20 日均量 / up_rate_ma5 / up_count / limit_up_count_non_st / 申万前三占比 / 容量核心占比及上涨占比 / 领涨核心均涨与占比 / formula_version / data_version / vendor_updated_at / raw_json / pulled_at / loaded_at`。来源 `fupanhui.reviews_overview`：`scripts/fupanhui_review_overview_pull.py` 经 CDP 代理在用户已登录的复盘会标签页分页调用 `reviews/overview`（只抓不写，JSON 落 `db/vendor/`，不进仓；对 429 退避四次），`scripts/teaching_framework.py load-reference --json …` 载入。**参照只进收据**（`reference_comparison`）：标签计算不读它，标签哈希与它无关（测试锁死）；它是事后标注（`vendor_updated_at` 晚于交易日），不作 PIT 上下文。

### 3.6 PIT

标签 `computed_at` 是现在，不是历史；按 09-06 §4.2 它们是 `derivation=deterministic`，在河上作为派生对象时 `recorded_at` 取其成员事实行的 `recorded_at`（`fact_market_daily.updated_at`，只是上界——`river.py` 注记）。本 spec 不解决 PIT 上界问题（工单 #27 的事），只保证**可重算**。收据里按 `sh_week_ma_source` 分组报天数，让读者知道多少天的周均线是回填复算的。

---

### 3.7 v0.2（slice 1.5，用户 2026-09-07「开工」）：八段、共性区间证据、校准命令

§3.3 的七段证据表是 v0.1 的编码，保留作记录；v0.2 起以本节为准（骨架 §8.5）。

- **词表**：`STAGES = (左底向下, 左底向上, 二次探底, 缩量右底, 共建主线, 主流主升, 主流主升2.0, 高位震荡)` = 复盘会内层八段（承接盘反复 = 高位震荡，用户第十段）。「回踩周均线」不再是阶段。`stage_fine` 只在进入高位震荡当日写「见顶」。
- **进入证据（E）** = 创始人转点原话五条：`cross_below_kind = first` → 左底向下；`deviation_band = oversold` → 左底向上；`cross_below_kind = retest` → 二次探底；`days_since_cross_above ≤ breakout_confirm_days ∧ volume_expanding ∧ above_week_ma` → 共建主线；`deviation_band = overheated` → 高位震荡。缩量右底 / 主流主升 / 主流主升 2.0 没有创始人给的单日转点，只有持续证据。
- **持续证据（H）** = 六个视角（`BAND_VIEWS`：量能比 `amount_vs_ma20_pct`、水位 `stock_ma10_deviation_median`、情绪 `stock_up_ratio_ma5_pct`、10 日涨幅 `sh_index_pct_chg_10d`、本腿涨幅 `ma_episode_pct_chg`、周均线偏离度 `src.sh_deviation_pct`）各自落在该段共性区间 `[p25, p75]` 内计 1 分；区间来自参数文件 `stage_bands`，由 `scripts/teaching_framework.py calibrate-stages --train-until D` 从旁路库的参照标注（§3.5）与视角标签算出（nearest-rank 分位、某段某视角样本 < `min_days` 不出区间），并写 `stage_bands_derived_from`（来源、切点、各段天数、分位、方法、标签版本）与 `transition_graph`（训练期观察到的段间移动）。**周均线上下与上下穿不再是阶段前提**，只留在转点 E 里。
- **计分与并列（第二遍，用户「继续按照最优推进」）**：每条 1 分；**只有「可达的段」与「当日有进入证据的段」有资格胜出**（`transition_policy = entry_or_reachable`）——可达 = 昨日来源状态沿转移图（含自环）能到的段；不可达又无进入证据的段即使分高也不算（词表「必须回答从什么来源状态演变而来」的直译）；资格集内 argmax，唯一最高即胜（可达 → `argmax`，仅靠进入证据 → `entry`），并列取其中唯一可达者（`graph`），仍并列 `ambiguous`，资格集内全零 `no_evidence`（不可达段有分也不算——那是无转点的跳段）。**来源状态的记忆**（`ambiguity_memory = last_valid_stage`，spec §9.9 的判读按「最优推进」采纳）：歧义 / 无证据日不抹掉来源状态，只有缺口日断链；转点计数同规则。**共建主线的进入证据只在来源状态属周期下半场（左底向下 / 左底向上 / 二次探底 / 缩量右底）或无来源时成立**——第六段流程把放量上穿放在「下穿 → 探底 → 反弹 → 回踩」之后，顶部区间里每隔几天一次的上穿不是它。缩量右底加一条创始人原话的持续证据 `H:shrink_after_retest`（回踩下穿之后、周期未被放量突破结束前的缩量日）。`confidence` 分母 = 该段 E 条数 + 原话持续条数 + 有区间的视角数。证据 JSON 多两个字段：`eligible`（当日有资格的段）与 `entered`（当日有进入证据的段）。
- **校准 / 验证分离**：`--train-until` 之后的参照日不参与区间；收据 `reference_comparison` 分 `agreement_train / agreement_validate` 报一致率。用户第七 / 八段「定义可以通过真实历史数据做优化……回溯历史找共性区间」的落点；每次重校准 = 新 `framework_version`。
- **默认参数**：`index_stage_params.v0.2.json`（切点 2025-12-31，训练 251 天八段各 ≥ 11 天）；v0.1 文件保留，`--params` 可指。

## 4. 设计 D：最高标接力链 `LeaderSuccession`

### 4.1 三个事件的确定性定义（用户口述，骨架 §4）

以 `fact_theme_limit_stock_daily` 按 `(trade_date, stock_ts_code)` 折叠后的 `limit_times` 为唯一输入；交易日历取 `history_calendar`。

- **`top(d)`**：d 日 `limit_times` 最大且 `≥ 3` 的**全部**个股，成一组（**用户 2026-09-07 第六段：「最高标不要求唯一，可以并列多个」**；此前「唯一、并列 → `tie` → `unverifiable`」作废）；`max < 3` → `None`（该日无最高标）。并列策略进参数 `leader_top = {tie_policy: group, break_rule: all_members_off_table}`，改读法 = 新版本。
- **断板日 T**：`top(T−1)` 存在，且组里**没有一只**在 T 日仍在涨停表（表只收封住的，不在表 = 收盘未封 = 断板，与用户「炸板不分」一致；「前一天的市场最高连板第二天不是了」读作整组都不是了）。一只断、一只在 → **不是断板**，计 `partial_break`（真库 64 天；另一种读法「每只高标各自断板」待用户拍，§9.6）。若组里有人在表但不再是 max（被更高者超越）→ 记 `overtaken` 事件到旁表，不成节。
- **候选 `candidates(T)`**：T−1、T、T+1 三日涨停表中 `limit_times ≤ 2` 的个股并集，去重，剔除整组 `top(T−1)`。
- **下一任 `leader_next`**：满足 `d ≥ T` 且 `top(d)` 存在 且 `top(d) ∩ top(T−1) = ∅` 的最小 d 上的 `top(d)`（也是一组）；`birth_day = d`。历史尾部找不到 → 该节 `open`，不进 N。
- **`handoff`** = `leader_next ∩ candidates(T) ≠ ∅`（新组里任一只出自候选窗；`forward.handoff_members` 列出是哪几只，「全部」读法可从同一批行推出，§9.6）。注意：若 `leader_next` 在 T−1 已 ≥ 3 板（只是低于前任），它不在候选里 → `handoff = false`——这正是「低位衔接」与「高位接力」的区别，用户的假设只关于前者。
- **`gap_days`** = T 到 `birth_day` 的交易日数（可为 0：前任断板当天新任诞生）。

### 4.2 节的字段

```text
history_leader_succession
  node_id                 = sha256("A|B" 排序拼接的组, break_day)[:16]
  leader_i / leader_i_name / leader_i_peak_boards   组的 "|" 拼接文本（display）；leader_i_group_json 是组本身
  break_day
  candidates_json         [{stock, name, day, limit_times}]
  leader_next / leader_next_name / leader_next_group_json / birth_day / birth_boards
  handoff                 bool（新组任一只 ∈ candidates）；forward.handoff_members / forward.leader_next_size
  gap_days                int
  path_json               {stock: 逐日 {day, in_table, limit_times, open_times, first_limit_time, up_stat}}，新组每只一条
  shape_tags_json         {stock: 形态族 v0（§4.3）}，新组每只一份
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
- B 类（本刀顺带建，都是一列 SQL）：`tf.max_boards`（`max(limit_times)`）、`tf.promotion_rate_total`（今日 `limit_times ≥ 2` 数 / 昨日涨停数）、`tf.top100_amount_share`（`fact_stock_daily.amount` 前 100 之和 / `fact_market_daily.total_amount`；份额 > 1 判单位不一致 → NULL + 缺口）、`fact_market_daily.limit_up / advancers / total_amount / amount_vs_yesterday_pct / sh_deviation_pct` 原值（`src.` 旁列）。
- B 类「整体的水位」（用户 09-07 第三段）：`tf.stock_pct_chg_median`（全市场个股涨跌幅中位数）、`tf.stock_price_mean`（平均股价）、`tf.stock_ma5_deviation_median` / `tf.stock_ma10_deviation_median`（个股相对自身 MA5 / MA10 偏离度 % 的中位数；均线只用截至当日收盘，窗口内每个日历日都有行的股票才计入）。全部来自 `fact_stock_daily`，覆盖只数 `< breadth_min_stocks` → NULL + 缺口行；写入按 6 位小数规范化（并行 SQL `AVG` 的末位抖动不得改变内容哈希）。细分指数（上证50 / 科创50 / 创业板指 / 微盘股）库内无源，待接。**v0.1 只作视角与上下文，不进七段计分**（§9.11）。
- B 类「高位震荡四维度」（用户 09-07 第四段）：`tf.sh_index_pct_chg_{5,10}d` / `tf.sh_index_amplitude_{5,10}d` / `tf.sh_deviation_change_{5,10}d`（§3.2），随两端切片写出；「形态」无口径，未建。**只作视角与上下文，不进七段计分**（§9.12）。收据 `view_scalars_by_stage` 对每个不计分的视角标量按 `stage_coarse` 给 n / p25 / 中位 / p75，供定门槛用。
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
| 并列最高 | 真库 102/413 天并列（2 只 55 天、3 只 23、4 只 16、5 只 5、6 / 10 / 14 只各 1） | **用户 09-07 第六段：不要求唯一，并列成组**；可验证节 90 → 167；部分断板 64 天的读法待拍（§9.6） |
| `sh_week_ma_source` 四种来源，存量行 `unknown_preexisting` | 早期周均线不知从何而来 | 收据按来源分组报天数；不阻塞 |
| 供应商主线表只 106 日 | `mainline_*.vendor` 大量 NULL → 主流主升的 vendor 口径证据常缺 | 两口径分开报；`volume_top3` 全历史可算 |
| 413 个交易日 | 分阶段桶后 N < 10 常态 | 先出总体四态；分桶 `insufficient_n` 如实显示 |
| 缩量基准取 MA20 是候选 | 换成前日基准阶段序列会变 | 参数进 `framework_version`；收据可比性由版本判 |
| 「回踩周均线」证据仅来自词表 | 可能与创始人心中不同 | 收据单列该段命中天数，待确认 |

## 5.1 审查后执行补充契约

本节覆盖前述条款的执行歧义；实现、测试和收据以本节为准。

1. **两个时钟分开**：`context_break` 是 `anchor_as_of=break_day` 的即时上下文，只能读取截至断板日可见的事实；`forward` 是从断板日到 `birth_day` 的事件链；`context_birth` 是 `context_target=birth_day`，只有 `knowledge_cutoff >= birth_day` 时才可生成。`open`、`unverifiable` 和 `hindsight=true` 的记录不得进入衔接统计。§1.2 的确认日约束只适用于 `context_break` 和 A/B 标签，不适用于已明确标注为 realized 的后验字段。
2. **覆盖先于事件判定**：先建立按 `history_calendar` 的涨停表覆盖表，区分 `covered_empty` 与 `missing`。缺失日跨入断板日、候选窗或 forward 链时，整节为 `unverifiable(data_gap)`；不能用“无涨停行”直接判断断板。
3. **基准风险集固定**：baseline 只纳入 `D-1/D/D+1` 可见、`top(D-1)` 组存在且至少一只仍封住、未被超越、涨停源覆盖完整、下一任（与 `top(D-1)` 无交集的组）已到期且无 field-null 的日期；`top(D-1)=None`、尾部 open、缺口和无法确定的记录排除并在收据计数。候选和 outcome 与事件节点使用完全相同的去重和到期规则（并列成组，09-07 第六段）。按 top 任期去重，收据记录窗口重叠数。
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
| **第二刀（另单）** | C 类：量 / 价 / 锐度 / 主流两口径 板块角色标签（骨架 §3）；接力链上下文补列；第一条候选规则 `money_effect_outside_volume_top3_below_ma`（09-07 第五段「周均线下方赚钱效应往往不在成交占比前三的板块」，骨架 §3.2；「赚钱效应」口径待创始人填，可几个口径并排） | — | 本单刀 3；本单合入 main |

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
13. 收据含 `view_scalars_by_stage`：每个写出但不计分的视角标量（水位四列、区间涨幅 / 振幅 / 偏离度变化六列、腿结构与下方周期）按 `stage_coarse` 给 n / p25 / median / p75；没有任何一列进入 `stage_predicate_catalog`。
14. 收据含 `views_by_event`（用户 09-07 第八段「回溯历史来找出共性区间」）：对七类创始人定义的事件日（过热 / 超跌 / 上穿 / 确认突破 / 趋势中放量 / 第一次下穿 / 回踩下穿）给每个视角标量的四分位，以及事件后 3 / 5 / 10 日指数涨跌四分位、5 日内跌回周均线下 / 创更高收盘的次数。前瞻数只在收据里，任何标签不得读它。
15. 旁路库载有 `history_reference_stages` 时，`build-labels` 收据含 `reference_comparison`：原词表列联表、按 `REFERENCE_STAGE_ALIASES` 折算的一致率（并按参数文件的 `train_until` 分训练 / 验证两段）、按参照阶段的视角四分位与周均线上下 / 量能三档计数；载不载参照，`history_teaching_labels` 的内容哈希逐字相同。
16. v0.2：`stage_bands` 与 `transition_graph` 同时在参数文件里且格式合法（键 ⊆ 八段、视角 ⊆ `BAND_VIEWS`、`lo ≤ hi`），带 `stage_bands_derived_from`；`calibrate-stages` 对同一旁路库、同一切点两次运行写出的参数文件逐字相同；`build-labels` 收据的 `stage_predicate_catalog` 与参数文件的区间一一对应。

---

## 9. 待用户拍板（不拍按推荐执行）

1. **缩量基准** v0.1 用 `amount_ma20`（推荐：表里现成、比前日噪声小），备选前日。
2. **成交占比扩大**用 `top3_industry_ratio` 较昨日上升（推荐：最简单、可解释），备选较 5 日均。
3. **秒板阈值** `first_limit_time ≤ 09:35`（推荐候选值），**反包窗口** 5 个交易日（推荐候选值）。
4. **`overtaken`（被超越）事件**记旁表但不成节（推荐记，将来「高位接力」是另一条规则的原料）。注意：按 `limit_times` 的连板语义，在位最高标次日必然 +1 板，其他股最多追平成 `tie`，所以这张旁表在干净数据上恒为空——真库跑出 0 条不是发现，是定义使然。
5. **第二刀（C 类板块角色）**紧随本单还是等本单读数看过再说（推荐紧随——接力链上下文里价 / 锐度两列是你点名要看的）。
6. **（2026-09-07 验收后追加）「最高标」与「衔接」的操作化定义。** 真库上 89/90 个可验证节点 `gap_days = 0`，`handoff` 与 `birth_boards = 3` 完全等价：413 天里只有 3 天没有 ≥3 板的股票，前任一断板，「下一个唯一最高板」几乎总是已站在 4–7 板的在位者，按 §4.1 这是「高位接力」，天然 `false`。同时基准窗口比事件窗口相对继任者早一天，同一个继任者在基准里更容易「落进」候选窗（收据 `diagnostics` 两张表可见）。所以 `refuted` 是口径产物，不是数据在说话。推荐改为：候选规则的 outcome 定义成「候选窗内的 ≤2 板股票在 N 日内到达 ≥3 板」（不要求成为唯一最高），基准用同一 N。**「最高标」是否要求唯一——已拍（09-07 第六段）：不要求，可以并列多个**，已按并列成组落地（§4.1）：真库可验证节 90 → 167，`handoff` 40/167 vs 基准 132/213，仍 `refuted`，仍与「继任者恰好 3 板诞生」完全等价（3 板 40/40，≥ 4 板 0/127）——口径产物没有变，outcome 定义仍待拍。并列带出的两个子问题**第七段已拍**：(a) 部分断板「不算」（现实现，真库 64 天不成节）；(b) 组的衔接「任一只」（现实现）。仍待拍的只剩 outcome 定义本身——**用户第八段问「outcome 定义是什么定义」**，白话：就是「一节算不算衔接成立」的那一行。现在写的「下一任市场最高标组里有一只出自断板日前后三天的 ≤2 板股票」在数据上等价于「继任者恰好以 3 板诞生」（断板时几乎总有 4–7 板在位者立刻接任，低位股最快第三天才到 3 板），所以量到的是「市场有没有断层」而不是「低位有没有衔接」。候选改法：成功 = 候选窗内的 ≤2 板股票在 N 日内到达 ≥3 板（不要求成为最高），基准同 N。**第九段已答**：「衔接就是看看上一个高标和下一个高标的关系，一个消亡另一个诞生是怎么衔接的，但不是每次都是高低连板的衔接，也要看区间涨幅，就是这个载体的形式。也可以理解成一段区间内的涨幅高的品种和后续涨幅高的品种，他们是怎么衔接转换的。」→ 衔接是**关系描述**不是二值 outcome；高标载体有**连板**与**区间涨幅**两种。改法（骨架 §4 补注二）：`handoff` 降为读数字段；节的主体改为关系描述（消亡日 / 诞生日 / 间隔 / 继任形态 / 板块题材关系 / 继任在候选窗的位置）；加第二条链「区间涨幅高标」（窗口候选 = 平台梯队高度的 20 / 60 / 90 / 120 日或本腿，待拍）；候选规则先出「衔接形式分布」再立。本刀 §4.5 的 `leader_handoff_from_low_boards` 读数保留为历史记录，不再作为规则推进。
7. ~~**（09-07 追加）「刚突破」的窗口**~~ → **已拍（09-07 第七段）**：「上穿要配合放量，不然很多上穿基本都是回落，或者上穿后三天内放量」→ 窗口 = 上穿当日起 3 天（`breakout_confirm_days`），已进计分：突破证据命中 3 → 12 天，歧义率 69% → 65%，共建主线 18 → 38 天，高位震荡 21 → 18 天。收据 `breakout_confirmation` 核了那句「不然基本都是回落」：52 次上穿，窗口内放量 13 次，放量的 3 天内回落 1/13、5 天内 6/13；未放量的 39 次，3 天内回落 24/39（62%）、5 天内 30/39（77%）。`turn_up` 仍为 0——不是窗口的问题：上穿当日多半不放量，共建主线 H 与高位震荡 H（`¬volume_surge`）各 1 分并列，从下方三段沿转移图都到不了，当日 `ambiguous`，次日即便放量赢出也因「昨日无阶段」不计转点。旧 H 一替换（§9.12）或 §9.9 的记忆规则一改，这个 0 才会动。
8. **（09-07 追加）「量能是否维持」作为持续证据的口径**：现在高位震荡 H 写成 `¬volume_surge`（环比 ≤ 20 都算不再扩张），真库命中 225/402 天，是共建主线 / 高位震荡长期并列、歧义率 69% 的主因之一。改成「环比 ≤ 0」还是删掉这条 H？→ **第四段后并入 §9.12**：三档「不是某个阶段特有」已否定这条 H 的前提，剩下的是删的时机。
9. ~~**（09-07 追加）歧义后的记忆**~~ → **按用户「继续按照最优推进」采纳（slice 1.5 第二遍）**：歧义 / 无证据日保留最近有效阶段作来源状态，只有缺口日断链（参数 `ambiguity_memory = last_valid_stage`，§3.7）。理由：平台的阶段是持续数周的段，歧义是我们读不出来那一天，不是段结束了；第二遍第一版没有记忆时歧义日一多、转移约束就失效。
10. ~~**（09-07 第三段追加）量能三档进不进计分**~~ → **已答（09-07 第四段）**：「温和放量和缩量就是支持全周期的观察，不是某个阶段特有的观察指标」。三档不进任何一段的计分，`tf.volume_band` 维持只写出、进两端上下文；`volume_band_by_stage` 继续出，只作读数（真库：shrink 208 / moderate 175 / surge 19 天）。「换成三档里的某一档」那半问随之作废——见 §9.12。
11. **（09-07 第三段追加）水位标量进不进计分**：四列已建（§4.4），只作上下文与视角。若进七段计分，是哪一段的证据、门槛多少？MA5 / MA10 偏离度取「中位数」是 agent 选的聚合方式，备选「站上均线的个股占比」。细分指数无源待接，接哪几个？收据 `view_scalars_by_stage` 现给四列按阶段的四分位（真库：左底向上 9 天 MA10 偏离度中位数 −5.4、左底向下 −0.9、高位震荡 +1.5、共建主线 +1.6）。
12. **（09-07 第四段追加）高位震荡的持续证据怎么写**。创始人：「高位震荡并不是只看周均和量能，还要看指数的形态，区间涨幅和振幅，周均偏离度的变化。」后三样已按候选窗口 5 / 10 日建成六列视角（§3.2），不计分。真库上高位震荡 21 天 vs 共建主线 18 天 vs 左底向下 74 天：5 日涨幅中位数 3.03% / 1.64% / −0.45%，5 日振幅 3.56% / 3.13% / 2.28%，5 日偏离度变化 +1.55 / +0.73 / −0.94 个百分点（收据 `view_scalars_by_stage`）。**读这组数要知道**：现在的高位震荡主要靠 `deviation_band = overheated` 判出，涨幅与偏离度变化偏高有一部分是同一件事的两种说法，不是独立证据。三件都已答（第六 / 七段）：(a) 「区间」→ 第七段「偏离−多了，就会有回归的过程，那一个区间就是」= 回归周均的那一腿；本腿涨幅 / 振幅已建（`tf.ma_episode_pct_chg / amplitude`），固定 5 / 10 日保留作对照。真库按腿：高位震荡 18 天涨幅中位 4.1%、振幅 4.4%；共建主线 38 天 2.5% / 3.1%；左底向上 9 天 −5.5% / 8.2%。(b) 「偏离度的变化」→ 持续走高 / 回归周均 / 逐渐走低，三条连续天数已建；「持续」= 3 天（第七段「三天吧」，`deviation_streak_min`）。(c) 「形态」→ 区间结构 = **高点不抬高加收敛**（第七段），两对旗标已建（`tf.index_high_not_rising_{5,10}d` / `tf.index_range_converging_{5,10}d`）；真库现标为高位震荡的 18 天里两者同真只 4 天，因为现在的高位震荡多是 `overheated` 的进入日（还在冲高），这个形态描述的是见顶之后——旧 H 替换后才看得到。**门槛一问第八段已答**：「涨幅和振幅多少算多，是基于历史行情去对比的，我提供视角，但我不提供关键的判断数字，当有计算方法时，可以回溯历史来找出共性区间」。收据 `views_by_event` 就是共性区间的载体：真库过热日 14 天，本腿涨幅四分位 2.7% / 3.4% / 6.8%，本腿振幅 2.2% / 3.4% / 6.9%，5 日涨幅 2.65% / 3.0% / 3.5%；其后 5 日内 10/14 跌回过周均线下、11/14 又创过更高收盘——两者同时发生，正是「震荡」。替换旧 H 的方案（agent 拟，骨架 §1.5 末条）：四条独立视角——形态（高点不抬高 ∧ 收敛）、本腿涨幅 ≥ 过热日 25 分位、本腿振幅 ≥ 过热日 25 分位、偏离度回归周均 ≥ 3 天且仍在上方；分位在前半段历史上取、后半段验（§9.15）；同权。另：现有 H `above_week_ma ∧ ¬volume_surge` 的前提（¬surge = shrink ∪ moderate）已被「不是某个阶段特有」否定。实验（monkeypatch，未入树）：删掉它，歧义率 69% → 42%、共建主线 18 → 142 天、`turn_up` 0 → 12，但高位震荡 21 → 2 天（只剩两条进入证据同日命中的日子）、`turn_top` 2 → 0——它是 v0.1 里高位震荡唯一的持续证据，删了这一段就只剩进入日。**已拍（09-07 第五段）：「等四维度落成谓词后一并替换，不单删」**；同段确认实验里归到共建主线的 142 天「确实是共建主线」，即周均线上方无其他证据时默认为共建主线（`H:above_ma` 由词表推出升为创始人确认）。(a)–(c) 仍待拍。
13. **（09-07 第五段追加）周均线上下方看的东西不同**：「周均上方会比较看量能多一点，周均线下方一般都是缩量行情，市场的赚钱效应往往就不在成交占比前三的主流板块。」收据新增 `volume_by_ma_side`，真库：下方 161 天里环比 shrink 106 / moderate 52 / surge 3，成交额低于 MA20 110 天；上方 241 天里 shrink 102 / moderate 123 / surge 16，低于 MA20 96 天——与口述一致，也说明下方三段（左底向下 / 左底向上 / 缩量右底）靠量能分不开：缩量右底 的唯一证据在下方命中 87 天却 0 天胜出（左底向下 的持续证据同日命中，并列时转移图从 左底向下 到不了 缩量右底）。要拍：(a) ~~缩量右底 与 左底向下 的分界靠什么~~ → **已答（第六段流程）**：左底向下 = 第一次从周均线下穿；下穿后探底 → 反弹到周均线那一段 → 又回踩探底 = 缩量右底；不是每次都严格反弹到周均线才回落，是大致流程，中间有数据的残差；两段与主流板块 / 赚钱效应一体两面。已落同侧一段四个结构量（§3.2）。**两个容差第七段已答**：(a1) 「回抽也就是周均线回归的过程，一般都会触碰一下周均」→ 反弹到触碰为止，触碰在数据里就是一次短暂上穿；(a2) 「上穿要配合放量，不然很多上穿基本都是回落」→ 不放量、≤ 3 天跌回的上穿是残差不是转段。两句接成 `tf.cross_below_kind`（`first` / `retest`）与 `tf.below_ma_cycle_day`（§3.2）：**「≤ breakout_confirm_days 天且无放量 = 残差」是 agent 的接法，请认。** 真库：下穿 53 次里 first 28 / retest 25；54 段碎的下方运行接成 29 轮周期，中位 7 个交易日、最长 31，覆盖全部 161 个下方日加 103 个残差日。下方三段的谓词候选（agent 拟，骨架 §1.5 末条）：左底向下 E = `cross_below_kind = first`；缩量右底 E = `cross_below_kind = retest`、H = 周期内下方且缩量；左底向上 H = 下方且 `deviation_toward_ma_streak ≥ 3`。(b) ~~「赚钱效应」用什么量~~ → **已答（第六 / 七段）**：赚钱效应是市场的聚类分析，「特征聚类应该可以组合，就是要联立分析，不一定要直接锁死答案」——第二刀的板块级赚钱效应不定单一口径：板块涨停家数 / 双红 / 涨幅 / 成交占比 / 连板家数各算一维，聚类参数进参数文件，几套并排出读数，与市场级 regime（`feat/money-effect-regime-rules` 的 10 维日向量与四轴，未合 main）联立。定了就是第二刀的第一条候选规则 `money_effect_outside_volume_top3_below_ma`（骨架 §3.2），基准取周均线上方同一定义。用户同段原则：**阶段是对市场的描述，不孤立地用数据定义，也不只看周均线上下**——下方三段的证据必须带 C 类与赚钱效应，第二刀因此成为 A 类下方三段能否分开的前提。
14. ~~**（09-07 第六段追加）上穿的「放量」口径与共建主线进入证据的形状**~~ → **已拍（第七段）**：「上穿要配合放量，不然很多上穿基本都是回落，或者上穿后三天内放量」——放量是必要条件不是视角，窗口 3 天，阈值沿用环比 > 20（用户第一段「20 是一个阈值……行情刚突破的时候环比超 20 就可能是行情的开始」）。已进计分（§3.3）。环比 > 0 的读法（52 次上穿里 36 次）留在收据 `breakout_confirmation` 作对照；阳线（50/52）区分度不够作证据，只作视角。
15. **（09-07 第七、八段追加）定义在历史上优化 = 回溯历史找共性区间**：用户「包括一些定义，其实也可以通过真实历史数据做优化」「当有计算方法时，可以回溯历史来找出共性区间来判断下次的行情，这是初衷」。这是对 B 类数字的授权与方法，不是对 A 类结构（哪几段、什么算转点仍由口述定）。走法：以创始人定义的事件日为锚（过热 / 超跌 / 确认突破 / 第一次下穿 / 回踩……），取视角量在事件日上的四分位为共性区间（收据 `views_by_event`），以区间下沿为候选门槛；**前半段历史取值、后半段验**（后半段的事件日分位、由此判出的阶段天数 / 歧义率 / 其后走势与前半段一致才认，不一致标 `not_distinguishable`）；每个门槛进参数文件并带 `derived_from`；每次调整 = 新 `framework_version`。不许同一段历史既选阈值又报命中率。第一批：§9.12 的四维度门槛（替换旧 H）。
16. **（09-07 第八段追加）趋势中放量改作双向因子**：用户「趋势中放量不代表就见顶，也可能是行情升级，就是这个放量是个因子，有好有坏，出现的时候需要特殊情况特殊分析」——第一段的「很可能盛极而衰」由此修正。已落：`E:surge_in_trend_not_breakout` 撤出高位震荡证据表，改为视角 `tf.surge_in_trend`，角色进参数（`surge_in_trend.role = view`，旧收据不可比）。真库这种日子仅 4 天，`views_by_event` 回溯：其后 3 / 5 / 10 日指数中位 +1.2% / +3.5% / +2.4%，5 日内 3/4 创更高收盘、2/4 跌回过周均线下——样本太小不作结论，方向偏「升级」。影响：高位震荡 2 条可用视角（`E:overheated`、旧 H），阶段分布 高位震荡 18 天不变、共建主线 38 → 48、歧义率 65% → 62%、`turn_top` 3 → 5。「特殊情况特殊分析」的落点就是 `views_by_event` 里这一格，随历史积累自己长。
17. **（09-07 第九段追加）复盘会对照与差分——框架地基待拍**。按用户要求用 CDP 读了 fupanhui.com 的工作台 / 体系说明 / 龙头梯队 / 复盘总览与 `reviews/overview` 接口（详见骨架 §8）。三个事实：(a) 平台逐日有创始人词表的**内层阶段标注** `cycle_stage`（2021-09-13 起；八段：左底向下 / 左底向上 / 二次探底 / 缩量右底 / 共建主线 / 主流主升 / 主流主升 2.0 / 承接盘反复，套六类外层），事后写入（440 天里 435 天 `updated_at` 晚于交易日）；(b) 与本刀 `tf.stage_coarse`（`tf-v0.1+415ab066`）在 402 个重叠日上对齐词表后只有 **24/152 有阶段日一致（16%）**，250 天歧义；(c) 原因是结构性的——平台的阶段是跨周宏观段（承接盘反复中位 21 天）、**不跟周均线上下走**（左底向上 21/24 天在上方、承接盘反复 64/161 天在下方），分开它们的是 **20 日量能比**（左底向下 85% → 二次探底 90 → 缩量右底 91 → 左底向上 93 → 承接盘反复 101 → 共建主线 102 → 主流主升 2.0 120 → 主流主升 124）与 5 日上涨比例（40% → 57%），而我们用的环比在八段之间中位差不到 5 个百分点。平台自己的量能分档也在这把尺子上（60–85% 强势抱团 / 85–100 抱团 / 100–115 轮动 / 115–120 主线 / 120–150 主升）。**四件第十段已拍**（骨架 §8.4）：标注是「人机协作出的」、平台「可以作为置信度较高的来源」；「承接盘反复是高位震荡，2.0 是升级」→ 平台八段为准；「20 日均量，量能比吧」；「当参照」。本刀随即落了两件：量能维度换到量能比（§3.1 / §3.2；真库歧义率 62% → 44%，`turn_up` 0 → 13，高位震荡 18 → 4——旧 H 在新尺子上几乎恒真、被突破证据压过，本就待换）；参照标注接入（§3.5，已载 440 天，一致率仍 16%——「阶段跟周均线上下走」的前提未拆）。**事故**：拉全量历史触发平台 429（`entity_breadth`，`retry-after` ≈ 72 h），起因是同日上午探索性拉取用光额度；后续全量由创始人从数据中台导出为正路。
18. **slice 1.5 第一遍已落（用户「开工」，`tf-v0.2+905f2198`，§3.7）**：(a)–(d) 完成——八段、共性区间证据、训练期 ≤ 2025-12-31（切点改自 2025-10-31：那样 左底向上 只 6 天、缩量右底 3 天；改后八段各 ≥ 11 天，验证期 164 天八段都有）、旧 H 随重构消失。读数：歧义率 44% → 19%；与平台一致率 16% → 27.6%（训练 29% / 验证 25.4%，两半段接近）；缩量右底 0 天；承接盘反复 161 天里 50 天判成共建主线、27 天判成左底向下；主流主升 28 天里 14 天判成 2.0。原因在序列：承接盘反复与共建主线六个视角的区间大面积重叠，平台靠来源状态分它们，argmax 允许任意跳段。**第二遍已落（用户「没有异议，继续按照最优推进」，`tf-v0.2+6c00d6c2`，§3.7 计分段）**：转移约束 + 来源状态记忆 + 共建主线进入只从下半场来 + 左底向下进入要带放量 / 跳空 + 缩量右底原话持续证据。一致率 27.6% → **33.3%**（训练 32.2% / 验证 **35.3%**，验证高于训练），歧义率 21%，承接盘反复判对 27 → 48 天，八段全部有天数。中途一版没有记忆规则：一致率持平 27.5%、歧义率反升 26%、承接盘反复被判成共建主线 50 → 64 天——记忆与突破门控就是从这个读数改出来的。**剩下的错不在指数规则**（骨架 §8.6）：承接盘反复 → 左底向下 26 天是转移图允许 高位震荡 → 左底向下、顶部横盘里量能与水位一落就按区间胜出，平台靠板块侧分它们（用户第六段「一体两面」）→ 第二刀 C 类进证据；缩量右底 / 左底向上 区间窄 → 全量参照重校准；主流主升 ↔ 2.0 互判 → 「升级」怎么看出来待用户说。(e) 区间涨幅高标链（前 10，窗口 20 / 60 / 90 / 120 日）与衔接的关系描述仍在队列。
19. **（同日追加）两个试过但未采纳的杠杆**，读数在骨架 §8.6 末：申万一级前三更替率 / 占比在八段上无区分度（不进证据）；阶段切换滞回 `stage_switch_margin`（可选参数，默认 1）在训练期变差、只在验证期变好，按训练期选值的纪律不启用。分层：本刀全部改动在领域层（`intelligence/services/teaching_framework/`、`methodology_backtest/store.py`、`river_query.py`、`scripts/`、`methodology/teaching/`），`intelligence/runtime/` 零触碰，分层门禁 ERROR 0（用户 09-07 问「是不是在领域 harness 里」）。
20. **（同日追加，用户第十一段）主流主升 2.0 的进入证据**：「升级 2.0，大概率是进一步放量指数进一步走强」→ `ENTRY_PREDICATES["主流主升2.0"] = ("E:upgrade_double_volume_new_high",)`：来源 = 高位震荡（平台序列里 2.0 三次都紧跟承接盘反复；第一腿从底部起的新高不算升级）∧ 当日 `double_volume_day`（每日复盘 `daily_review._market_label` 的双量日口径：成交额环比 > `double_volume_dod_pct`(10) 且量能比 > 120——用户指回「daily full 后的 html 渲染」里的既有定义）∧ `index_new_high_{upgrade_new_high_window}d`（收盘高于前 n 个相邻交易日的最高收盘；窗口写出 `index_new_high_windows = [20, 60]` 两个，谓词取 20：平台承接盘反复中位长度 21 天，20 日新高 ≈ 越过这段横盘的区间高点）。三个新参数键进 `REQUIRED_KEYS`，版本 `tf-v0.2+785bd123`。**特征值**（骨架 §8.10）：2.0 与第一腿在量能比上分不开（122 vs 124），分得开的是 60 日新高天数占比（58% vs 14%）、一年新高家数（302 vs 161）、绝对成交额（每段 2.0 比前一段承接高 3–6 千亿）。**效果**：谓词 402 天命中 5 天，一致率 41.3% → 41.4%，2.0 判对仍 12 / 26——2025-06-25 与 08-13 两个真升级日我们的来源是共建主线（前几天的短促下穿把高位震荡的来源冲掉了），来源门开不了；n = 60 命中 2 天、一致率同。2.0 的瓶颈与 §9.18(d) 承接盘反复 → 左底向下 是同一件事，等用户拍短促下穿。另记差分：平台在 2025-02-21 / 07-11 / 07-22 三个双量新高日仍标承接盘反复，平台的 2.0 比用户这句话更严（走出一段才追认）。
21. **（同日追加，用户第十二段「这些你可以根据特征值，我给的定义不是精确的，具体还要结合特征值来看」）左底向下的进入改为参数族 `left_down_entry = {persist_days, volume}`**：首次下穿周期（`below_ma_cycle_retest_seen = False`）的第 `persist_days` 天起、仍在周均线下、当日量能满足 `volume` 口径（`expanding_or_gap` = 09-06 第三轮原话 / `shrink` / `shrink_or_gap` / `any`）的每一天都算进入证据 `E:first_cross_below`；进 `REQUIRED_KEYS`。**先量**：41 个首次下穿日里平台当天判左底向下的只有 1 个；平台 7 段左底向下的起点在下穿后第 1–3 天、量能比 84–97（全部缩量）；承接盘反复里 22 次短促下穿当天量能比中位 110、64% 带量或跳空、中位 2.5 天收回。**再建**（骨架 §8.11 全表）：缩量口径比放量或跳空高 5–6 个点（验证期高 8–9 个点），持续 1 → 3 天训练期持平、验证期 +1.4，5 天训练期掉。采纳 **{3, shrink}**：`tf-v0.2+f03ec6a0`，一致率 41.4% → **46.6%**（训练 44.9 → 50.5，验证 35.7 → 40.0），承接盘反复判对 61 → 65、左底向下 23 → 29、2.0 12 → 15（来源不再被冲掉，§9.20 的升级谓词开门）、二次探底 8 → 12。**差分记录**：用户 09-06 「放量跌破周均或者跳空低开跌破周均基本就是要开始向下继续调整了」与平台标注反向——带量的下穿多半是顶部换手；原话保留为参数可选项，不再是默认，已在骨架 §1.5 提请用户看一眼。另两件同段处理：承接定义（五种候选、现口径最分得开、不动）与锐度合成（七种、分不出优劣、维持两名次均值），读数在骨架 §8.11。
22. **（同日追加，用户「继续按照最优推进」）区间涨幅高标链落地**（§9.6 / §9.18(e) 的队列项）：`teaching_framework/range_leaders.py` + CLI `build-range-leaders`，旁路库新表 `history_range_leaders` / `history_range_leader_handoffs`（进 `TEACHING_TABLES`，收据 `build_kind = range_leaders`，两表哈希再哈希为 canonical）。参数 `range_leader_windows = [20, 60, 90, 120]`（平台梯队高度）、`range_leader_top = 10`（第十段）、`range_leader_context = 30`（判递进 / 突入的近旁名次），进 `REQUIRED_KEYS`。组 = 复合涨幅前 10（个股第 N 个前行必须正好在 N 个交易日前；并列按代码）；衔接 = 同日消亡与诞生按名次配对（容量固定，天然一一对应），只描述关系：同 / 跨申万一级（个股最近归属作静态维表，`sw_industry` 只从 2026-04 逐日全覆盖）、递进 / 突入、滑落 / 跌出、双方是否 ≥ 3 板、在位天数；两条链的交叉按连板节点计。**读数**（骨架 §8.12）：2,450 次衔接里递进 91–99%、跨申万一级 87–91%、与连板链约 1/4 重叠（166 个连板节点里前任 47 / 继任 35 个同时是 20 日区间涨幅高标）、入组门槛随阶段 64% → 111%（20 日）。入组门槛试进八段证据：训练升验证降（53.8 / 35.8），只作视角写出。用户第九段的「衔接是关系描述」到此有了数据形状；**要不要立规则**（「低位一般会有衔接」在这条链上对应哪个问法）进骨架 §1.5 待用户。个股名字里的 NUL 填充在 SQL 里剔除。分层不变：全部在 `intelligence/services/teaching_framework/`、`methodology_backtest/store.py`、`scripts/`、`methodology/teaching/`。

---
23. **（同日追加，用户第十三段）「低位衔接」的本意 = 王朝级衔接；跳空低开跌破拆开量。** 用户：「第一波的区间涨幅靠前的品种，见顶后不是锁定了区间涨幅吗，这时候低位可能就有新的品种衔接，但是你站在当时那个节点是看不出谁会是后续下一个区间涨幅靠前的品种，我们能做的就是在两个区间涨幅前列品种都走出来后，回溯去看……一个高涨幅品种往往带领的是一个旧王朝，谁能抗住旧王朝的覆灭走出来的新王朝，是怎么完成衔接的。我有个定义叫分离确认，因为旧的王朝覆灭会带来亏钱效应，而在亏钱效应下酝酿走强的，往往就有新王朝的特质。但是这个区间高涨幅品种，可以是连板形式买也可以是趋势形式等。」→ §9.22 的逐日链量的是位次轮换，不是这个对象。落 **王朝链**：`teaching_framework/dynasties.py`（`segment_waves` + `build_dynasties`）+ CLI `build-dynasties`，旁路库 `history_dynasties`（每波前 cohort：名次、波内涨幅、申万一级、波内最高连板、载体形式、自己覆灭窗里的收益与回撤）/ `history_dynasty_handoffs`（每次衔接的新王朝成员：在旧波名次、是否出自旧前 cohort、一级是否在旧前 N 集合、覆灭窗收益与分位、第一段收益、窗内是否创新高、两条分离确认旗标）；四个参数进 `REQUIRED_KEYS`：`dynasty_top = 10`（第十段）、`dynasty_cohort = 30`、`separation_percentile = 0.9`、`separation_new_high_window = 60`（后两个是 agent 候选值）。口径：波 = 平台八段里 主流主升 / 2.0 / 承接盘反复 的连续段为顶部块、起点 = 之前紧邻的 共建主线 段首日；王朝 = 波内区间涨幅前 N；覆灭窗 = 见顶后一天 → 下一波起点前一日（open 不成节）；分离确认 = 覆灭窗收益分位 ≥ 0.9（相对）∥ 窗内创 60 日新高（新高）；统计门单位 = 个股 × 覆灭窗，条件 = 相对分离，结果 = 进新王朝，基准 = 同窗全部个股，周期数另报。**读数**（骨架 §8.13）：5 波 4 次衔接；旧前 10 覆灭窗中位 −13 到 −36%（全市场 −6 到 −9%）；新前 10 分位中位 65–83、四次里三次窗内创 60 日新高 60–89%（全市场 17–43%），2025-04 关税暴跌那次没有分离；四次没有一只旧前 30 进新前 30；前 30 口径 supported（1.37% vs 0.58%）、前 10 not_distinguishable，周期只有 4 个不作周期层判定。**跳空**：用户「不是给权威定义……印象中跳空低开跌破周均的，后续往往指数是继续向下，其他的规律你可以通过特征回溯来下定义」→ 新旗标 `tf.open_below_week_ma`；`views_by_event` 加 `cross_below_{gap_down, gap_through_ma, intraday}` 三个事件、20 日前瞻、10 日内最低、5 日内收回周均线上；读数：低开本身无信息（38/53 次下穿低开，后 20 日与基准同），缺口穿过周均的 16 次 20 日后 64% 收在下方（基准 36%）但 5 日内 87% 仍收回，盘中跌破 15 次全部 5 天内收回、20 日 +3.2%。作左底向下即时进入试过（`left_down_entry.gap_through_ma_day1`）：训练 50.5 持平、验证 40.0 → 39.1，不采纳，留可选项。**分层不变**：全部在 `intelligence/services/teaching_framework/`、`methodology_backtest/store.py`、`scripts/`、`methodology/teaching/`。**新的待用户**（骨架 §1.5 末）：王朝按平台段切认不认（还是按你自己的分法）；「亏钱效应」要不要立成可量的东西而不是用阶段段落代。
24. **（同日追加，用户第十四段「认可，亏钱效应也要可量」）**：王朝按平台段切不动。亏钱效应先量再建（骨架 §8.14）：九个候选日口径对平台八段、训练 / 验证两期、四个覆灭窗 vs 顶部块量——宽度类（5 日上涨比例 < 分位、涨幅中位 < 0、跌停家数、当日上涨比例）验证期分不开（2026 窄行情顶部宽度也低），承接类两期都分得开，**承接 5 日均值 < 1.0%**（训练期 p10 = 1.045 取整）最稠：底部 vs 顶部 15.8% vs 5.1% / 27.8% vs 8.5%，主升与 2.0 为 0%，四个覆灭窗里占比是顶部块的 2–4 倍。落成 `tf.money_losing_day` / `tf.money_losing_streak`（`flags.py`，参数 `money_losing = {basis, lt_pct, derived_from}` 进 `REQUIRED_KEYS`）；`build-dynasties` 从旁路库读亏钱日（没有则 fail closed 提示先跑 build-labels），每波报顶部块 / 覆灭窗前 10 日 / 覆灭窗的亏钱日数与首个亏钱日，`history_dynasty_handoffs` 加三列 `losing_days_ret_pct / losing_days_ret_percentile / separation_on_losing_days`（新成员在亏钱日上的累计收益、分位、是否 ≥ 分位门槛）。**读数**：覆灭窗亏钱日占比 11–25%、顶部块 6–11%；亏钱效应先于平台左底向下标注（W4：05-20、06-01、06-02 已是亏钱日，平台 06-08 才判）；**亏钱日本身上新王朝没有一致的分离**（分位中位 34.5 / 66.4 / 32.1 / 54.9），被打的是旧王朝（−4 到 −11% vs 全市场 −1 到 −7%）；把覆灭窗拆成亏钱日 / 其余日子（`history_dynasty_handoffs` 再加 `other_days_ret_pct / other_days_ret_percentile / separation_on_other_days`）：常态覆灭（W0→W1、W2→W3）分离全在其余日子（81–84 vs 25–35），关税暴跌（W1→W2）反在亏钱日上抗跌（66 vs 37）——「在亏钱效应下酝酿走强」= 整个亏钱效应期间的相对强弱，日级没有一致形状；四条分离读数并排，建议定义取整窗，进骨架 §1.5 待用户认。覆灭窗仍按阶段段落定（亏钱日只占窗的 1/9–1/4，W2 只有 2 天）。两次全新重建五个构建哈希一致，一致率不变 46.6%，版本 `tf-v0.2+d3350cd1`。

25. **（同日追加，用户「继续推进」）授课框架接进时间长河读取面（G-01 (b) 的前置）。** `teaching_framework/river_objects.py::teaching_objects(labels_db, as_of)` 从旁路库读三个盘面轨对象（`__market__`）：`teaching_stage`（当日 `tf.*` 阶段读数：`STAGE_LABELS` 那 16 个标签，`stage_evidence` 只取 confidence / from / entered / eligible / resolution / tied 与命中谓词清单，不搬 scores）、`teaching_dynasty`（王朝链截至当日已知的状态——取覆灭窗已开始 ≤ as_of 的最近一波：见顶日、成员前 N、覆灭窗至今有标签天数与亏钱日数、进入这一波的那次衔接里成员的分离确认四条旗标；不写覆灭窗终点、下一波、任何候选名单——第十三段「站在当时看不出谁是新王朝」是契约，测试锁死：顶部块内的日子没有王朝对象、下一波未见顶时上一波仍是「最近一波」）、`teaching_range_leaders`（当日各窗口前 N）。`slice_river` 加 `teaching_labels_db=None` 参数与 CLI `--teaching-labels-db`：不给 → 逐字节不变（真库测试）；给 → 盘面轨追加对象；`recorded_at` = 构建时刻 → `require_strict` 滤掉（真库测试）。顺手修一处既有非确定性：资金轨聚合 `SUM(DOUBLE)` 并行求和顺序不定（2026-01-12 算力租赁 `amount_sum` 两次调用末位不同、`source_hash` 随之变），三个 SUM 改 DECIMAL 精确求和——与 slice2 spec §6 第 6 项同一条纪律。带读判读段与每日复盘接线未动（等母本；接线时按 G-03 (d) 默认关）。测试：`intelligence/tests/test_teaching_framework_river_objects.py` 4 + 1（真库）。

## 10. 对外表述

读数只在仓内与验证文档；对外一律「授课框架代码化中」，直到 G-01 验收 (a)–(d) 全过。任何对外句子里不得出现「AI 学会了看阶段」「历史上 X% 会衔接」。
