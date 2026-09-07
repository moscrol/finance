# Teaching Framework Slice 2 验收记录（第一步：板块侧市场级视角）

分支 `feat/teaching-framework-slice2`，从合入 #627 后的 main（`b594a5e7`）开出；主库只读，教学产物写旁路 DuckDB。设计见 `docs/superpowers/specs/2026-09-07-teaching-framework-slice2-sector-side-design.md`。

## 1. 定向检查

```text
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_teaching_framework_*.py
73 passed（71 + 2：板块侧四列的逐列 / 逐日 fail-closed；CLI 夹具加三张板块表并手推新高 / 双红 / ≥3 涨停题材的逐日值与缺口）

.venv-workbench/bin/python -m ruff check .
All checks passed
```

## 2. 先量再建

对平台八段（440 天参照标注）量了八个板块侧市场级候选（spec §1.1 表）。有区分度的只有 **1 年以上新高家数**（底部 60–119 vs 顶部 176，区间 高位震荡 131–217 / 缩量右底 65–122 / 左底向下 47–76）；严格双红题材数中位分得开（底部 13–15 vs 顶部 5）但区间太宽；申万一级前三更替率、前三 / 第一占比、热门板块在前三之外的比例、第一题材份额在八段上都平。

## 3. 真实数据回放（主库 414 日 / 2024-12-20 → 2026-09-03；参照 440 天已载）

```text
calibrate-stages --train-until 2025-12-31（v0.1 视角 → v0.2 区间）
  新增区间：new_high_1y_count  左底向下 47–76 · 左底向上 57–74 · 二次探底 65–86 · 缩量右底 65–122 ·
            共建主线 72–119 · 主流主升 111–147 · 主流主升2.0 223–307 · 高位震荡 131–217

采纳版 framework_version = tf-v0.2+d2cc528d
  build-labels rows=28542（59 个 tf.* + 10 个 src.* × 403 天）gap_rows=136（板块侧：limit_* 当日缺 10 ×2）
  labels     canonical_hash=b37922a767ee5c4634bf32d7e089bbb29ca5f120727e8848c1a5ee82440dedc5（两次一致）
  succession canonical_hash=d3c5687c87c46c1895ae048537fe39f0a0161604358ee85e13f6880c38e939db（两次一致）
  stage_coarse: 共建主线 83 · 高位震荡 65 · 左底向下 62 · 主流主升2.0 38 · 二次探底 36 · 主流主升 22 ·
                左底向上 11 · 缩量右底 5 · ambiguous 78 · no_evidence 2   歧义率 20%
  turns: up 25 · top 18 · down 28
```

| 版本 | 进区间的板块侧视角 | 全期 | 训练期 | 验证期 | 歧义率 | 承接盘反复判对 |
|---|---|---|---|---|---|---|
| slice 1.5 末 `6c00d6c2` | 无 | 33.3% | 32.2% | 35.3% | 21% | 48 |
| `55fae114` | 新高 + 双红 + ≥3 涨停题材 | 32.7% | 35.4% | 28.1% | 15% | 46 |
| **`d2cc528d`（采纳）** | 新高 | **34.5%** | **34.5%** | 34.5% | 20% | **51** |

三条都进时验证期掉 7 个点（36 / 128 对 42 / 119）——等权区间隶属计分里区间宽的段多得分，容量一涨就过拟合。按「训练期选值、验证期不得明显变差」只采纳新高家数：训练期 +2.3 个点、验证期 −0.8 个点（1 天，噪声内）。

列联表（采纳版，行 = 平台）：承接盘反复 161 → 高位震荡 51 · 共建主线 36 · 左底向下 25 · 二次探底 12 · 2.0 17 · ambiguous 18；共建主线 46 → 共建主线 20 · 主流主升 12；左底向下 51 → 左底向下 15 · ambiguous 22；缩量右底 33 → 1 判对。

## 4. 第一步结论

板块侧在市场级能拿到的增量是新高家数这一条（宽度维度），把顶部的水位抬了一档；承接盘反复 → 共建主线 36 天、→ 左底向下 25 天没动——要到题材层。

## 5. 第二至四步：C 类角色标签、赚钱效应并排集合、候选规则四态（`tf-v0.2+5bf7d66b`）

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 78 passed（73 + 5：sector_roles 模块四条 + build-sector-roles 端到端）
ruff check .                                             → All checks passed

build-sector-roles（真库）
  rows=1,273,548（12 个 tf.* 板块标签 × 403 板块 × 411 天，CSV + COPY，8.2 s）  days: ok 411 · sector_rows_absent 3
  canonical_hash=0e7ea7d727a97a63e0a1c6aac3e1f2e0eba8a76b9f5e53a7877db25b38417019（两次一致）
  build-labels 只删 / 只哈希 entity_type='market' 行：板块标签写入后重跑 build-labels，市场标签哈希不变（测试锁死）
```

候选规则 `money_effect_outside_volume_top3_below_ma`（条件 = 周均线下方，outcome = 集合里 `sw_l1` 已知的板块过半不在当日前三申万，基准 = 上方同定义，min_n 10）：

| 赚钱效应定义 | 下方 n / k / p | 上方 p0 | lift | Wilson | 前 / 后半段 | 四态 |
|---|---|---|---|---|---|---|
| 涨停家数前 10 | 157 / 57 / 0.363 | 0.289 | +0.074 | [0.29, 0.44] | 0.33 / 0.39 | supported |
| 严格双红 | 115 / 37 / 0.322 | 0.411 | −0.089 | [0.24, 0.41] | 0.18 / 0.47 | not_distinguishable |
| **5 日涨幅前 10** | **161 / 96 / 0.596** | **0.456** | **+0.140** | **[0.52, 0.67]** | **0.61 / 0.58** | **supported** |
| 三名次均值前 10 | 157 / 47 / 0.299 | 0.217 | +0.082 | [0.23, 0.38] | 0.36 / 0.24 | supported |

这是第一条 `provenance.kind = teaching` 的规则在四态门里 supported，且前后半段一致。按平台八段看「5 日涨幅前 10 在前三之外的比例」：左底向下 0.70 · 缩量右底 0.70 · 二次探底 0.60 · 共建主线 0.40 · 承接盘反复 0.50 · 主升 0.60。

把这个比例做成市场级视角 `tf.rps5_outside_top3_pct`（SQL 里按日历连续 5 日复合涨幅排名）进 `BAND_VIEWS`，重校准 v0.2：

| 版本 | 进区间的板块侧视角 | 全期 | 训练期 | 验证期 | 歧义率 | 承接盘反复判对 |
|---|---|---|---|---|---|---|
| `d2cc528d`（第一步） | 新高 | 34.5% | 34.5% | 34.5% | 20% | 51 |
| **`5bf7d66b`（采纳）** | 新高 + 赚钱效应在前三之外的比例 | **40.2%** | **42.6%** | **36.1%** | 20% | **57** |

两期都涨（验证 +1.6 个点，43 / 119 对 41 / 119），采纳。主流主升判对 4 → 10、左底向上 0 → 4。两次重建：labels `aee9474d23b4f1db6d1530e0c1abe404197122e7e8023e2528afe20271b06534`、sector `0e7ea7d7…`、succession 均一致。

## 6. 第二至四步结论

第二刀落了三样：板块侧市场级视角（新高家数、赚钱效应在前三之外的比例）进八段证据，一致率 33.3% → 40.2%（验证 35.3 → 36.1）；C 类板块角色逐日标签 127 万行；第一条教学来源的候选规则四态 supported。全部改动在领域层，`intelligence/runtime/` 不动。

## 7. 第三步 (v) + 第五步：k-means 并排、宽度 / 主流两口径 / 锐度合成、题材层先量再建（`tf-v0.2+28a900ad`）

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 80 passed（78 + 2：kmeans 确定性 / 最热簇；宽度 · 供应商主流 · 锐度合成 · kmeans 标签 · 5 日 Jaccard）
pytest intelligence/tests/test_methodology_backtest*.py → 67 passed
ruff check .                                             → All checks passed
scripts/layer_audit.py                                   → ERROR 0 条 == 基线；git diff 不含 intelligence/runtime/；services 内无 runtime import
```

源库这一小时里被另一会话回填（`fact_stock_daily` 2,111,255 → 3,732,054 行，`fact_market_daily` 加了 2026-09-03），宽度类视角随之变，一致率在 ±0.3 个点上漂。为了对照成立，把库连 WAL 拷到 `/tmp/mfs-snap2.duckdb`（18:24），下面所有数字都出自这份快照；参数文件 `stage_bands_derived_from` 新增 `labels_canonical_hash = 7744b342…` / `labels_source_fingerprint = fa2e2096…` / `labels_source_max_trade_date = 2026-09-03`，钉住区间读自哪次构建。

```text
calibrate-stages --train-until 2025-12-31（v0.1 → v0.2，视角 9 条，新增 limit_premium_ma5_pct）
  framework_version = tf-v0.2+28a900ad
  limit_premium_ma5_pct 区间：左底向下 0.93–2.10 · 左底向上 1.59–1.96 · 二次探底 1.44–3.08 · 共建主线 1.05–2.33 ·
                              主流主升 2.13–2.94 · 高位震荡 1.54–2.52；缩量右底 / 2.0 训练期 <10 天不出区间

三次全新重建（--computed-at 11:00 / 12:00 / 13:00Z），逐份哈希：
  labels     fd23aab89a89c857…  identical ×3   rows=31356（68 个 tf.* + 10 个 src.* × 402 个可用日；414 日里 12 日缺）gap_rows=323
  sector     f9720d98d8dfd6d0…  identical ×3   rows=1,910,322（18 个 tf.* 板块标签 × 106,129 个（日, 板块）行，411 天，15.5 s）
  succession 764760e171cb3f7c…  identical ×3
  stage_coarse: 共建主线 80 · 高位震荡 77 · 左底向下 68 · 二次探底 43 · 主流主升 34 · 主流主升2.0 27 · 左底向上 5 · ambiguous 68   未决率 16.9%
  turns: up 26 · top 19 · down 25
```

第一轮两次重建 labels / succession **不一致**：`tf.limit_premium_pct` 在 2025-02-27（0.6590625）与 2025-03-19（1.4765625）两天 6 位小数进位不同——`AVG(DOUBLE)` 在 DuckDB 并行哈希聚合里求和顺序不定，落在进位边界上就翻。改成 `SUM(CAST(pct_chg AS DECIMAL(18,6))) / COUNT(*)`（整数精确求和、与顺序无关），`price_mean` 同法预防，之后三次一致。这条进 spec §6 验收第 6 项。

| 版本 | 进区间的板块 / 题材侧视角 | 全期 | 训练期 | 验证期 | 未决日 | 承接盘反复判对 |
|---|---|---|---|---|---|---|
| `5bf7d66b`（#633，当时的库） | 新高 + 赚钱效应在前三之外 | 40.2% | 42.6% | 36.1% | 80 | 57 |
| 同视角，快照重标定 `e94eeb22` | 同上 | 40.0% | 42.6% | 35.6% | 82 | 57 |
| **`28a900ad`（采纳）** | 同上 + 承接 5 日均值 | **41.3%** | **44.9%** | 35.4% | **68** | **61** |

试过没进的（spec §5.2 全表）：承接当日值 / 负溢价天数 / 翻转次数 单条验证期掉 1.8–3.4 个点；两条以上合并训练期冲到 51% 而验证期掉到 26%（典型过拟合）；双红申万一级数单看过门但对源数据不稳（回填前后验证期 32.0 / 35.5）；涨停前 10 持续度训练期掉 3.5。

赚钱效应第五套（确定性 k-means，k=3、五特征当日 z 分、分位点初始化、≤20 轮）：集合中位 17–29 个板块；候选规则四态 **not_distinguishable**（下方 157 / 75 / 0.478 vs 上方 0.443，前 / 后半段 0.38 / 0.57）。前四套读数与 §5 不变。

新板块标签（`entity_type='sector'`）：`tf.sharpness_rank_mean` / `tf.role_sharpness_top10`（两名次均值前 10，候选合成）、`tf.role_breadth_top_l1`（1 年以上新高最多的申万一级）、`tf.mainline_vendor` / `tf.mainline_volume_top3`（主流两口径并排；供应商表 113 日，其余 NULL）、`tf.money_effect.kmeans_hot`。新市场级视角标签：`tf.dual_red_l1_distinct`、`tf.limit_top10_persist_5d_pct`、`tf.limit_premium_pct / _ma5_pct / _neg_5d / _flips_5d`（缺口分别 68 / 25 / 11 / 35 / 35 / 35 天，按列记）。

## 8. 第五步结论

第二刀到此五步全落：一致率 33.3% → 41.3%（验证 35.3 → 35.4 持平），承接盘反复判对 48 → 61，未决日 80 → 68。剩下的瓶颈不在数据在定义（spec §5.3 的 25 天短促下穿、主升 vs 2.0 的「升级」），已列进 spec §7 待创始人。全部改动在领域层，`intelligence/runtime/` 不动。

## 9. 第十一段：前三 = 申万一级；升级 2.0 的进入证据（`tf-v0.2+785bd123`）

用户答复两件：「前三是申万一级本身」（现有口径不改，spec §7 划掉）；「升级 2.0，大概率是进一步放量指数进一步走强，你可以看看之前定义的这个行情，特征值是怎么样的」，并指回每日复盘 HTML 里的既有定义。

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 82 passed（80 + 2：新高窗口 / 双量日旗标；升级进入谓词的来源门与窗口参数）
ruff check . / layer_audit.py                           → 通过 / ERROR 0；diff 不含 intelligence/runtime/

每日复盘既有口径（market_feature_store/reports/daily_review.py::_market_label）：
  价日 = 偏离度由负转正；量日 = 环比 > 10 且量能比 < 120；双量日 = 环比 > 10 且量能比 > 120；
  市场性质：价日 + 双量日 = 共振日、价日 + 量日 = 转点日、其余普通交易日
  → 新旗标 double_volume_day（参数 double_volume_dod_pct = 10）、index_new_high_20d / 60d（参数 index_new_high_windows）
  → 2.0 进入谓词 E:upgrade_double_volume_new_high = 来源高位震荡 ∧ 双量日 ∧ 前 upgrade_new_high_window(20) 日新高

calibrate-stages（v0.1 → v0.2，快照 /tmp/mfs-snap2.duckdb）  framework_version = tf-v0.2+785bd123
三次全新重建（11:00 / 12:00 / 13:00Z）：labels 3369bd06efe42c70… · sector 4e9883c2ccf0d658… · succession bc90f8cbe5145f44…  均 identical ×3
  labels rows=32562（71 个 tf.* + 10 个 src.* × 402 天；+3 旗标）
  一致率 41.44%（训练 44.93 / 验证 35.71）  未决 69  stage_coarse 分布不变  turns up 26 · top 19 · down 25
  E:upgrade_double_volume_new_high 命中 5 天（2025-02-21、07-11、2026-01-05、01-06、05-06）；双量新高日（不看来源）17 天
```

特征值（平台八段，p25 / 中位 / p75，全表在骨架 §8.10）：2.0 与第一腿的量能比几乎一样（122 vs 124，都在暴量档），分得开的是 **60 日新高天数占比 58% vs 14%**、**一年新高家数 302 vs 161**、双量日占比 23% vs 21%（承接盘反复 4%）、绝对成交额每段 2.0 比前一段承接盘反复高 3–6 千亿（11625 → 15619、15845 → 21974、25899 → 32331）、指数区间高点三段都越过前一段承接的高点（3421 → 3456、3616 → 3884、4112 → 4243）。创始人的话在数据上成立。

| 版本 | 变化 | 全期 | 训练期 | 验证期 | 未决日 | 2.0 判对 |
|---|---|---|---|---|---|---|
| `28a900ad` | — | 41.3% | 44.9% | 35.4% | 68 | 12 / 26 |
| **`785bd123`（采纳，n = 20）** | + 2.0 进入证据 | **41.4%** | 44.9% | 35.7% | 69 | 12 / 26 |
| n = 60（试） | 同上，谓词取 60 日新高 | 41.4% | 44.9% | 35.7% | 69 | 12 / 26 |

一致率基本不动、2.0 判对不动：三段 2.0 里只有 2026-05 那段（本来就对）来源是高位震荡；2025-06-25 与 08-13 两个真升级日我们的来源是共建主线（06-19/20、07-31 的短促下穿先被判左底向下、随后的放量上穿又判成共建主线），来源门开不了。**2.0 的瓶颈与 §5.3 那 25 天是同一件事**，等创始人拍「短促下穿」。谓词按原话落、版本记下，是为了来源一旦修好它立刻起作用，而不是为今天的分数。差分另记：平台在 2025-02-21 / 07-11 / 07-22 三个双量新高日仍标承接盘反复，平台的 2.0 比原话更严。

## 10. 第十一段结论

第二刀五步 + 第十一段两问：一致率 33.3% → 41.4%，承接盘反复判对 48 → 61，18 个板块标签 191 万行，第一条教学来源规则 supported，2.0 有了原话进入证据。待创始人三件：短促下穿算不算左底向下（同时卡着 25 天与 2.0 的两个升级日）、「承接」这维认不认、锐度合成式。

## 11. 第十二段：三件按特征值定（`tf-v0.2+f03ec6a0`）

创始人：「这些你可以根据特征值，我给的定义不是精确的，具体还要结合特征值来看」。三件都按「先量再建、训练期选、验证期验」处理，全部读数在骨架 §8.11。

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 82 passed（左底向下进入口径改参数族后，stage 测试补：持续天数 / 缩量 / 回到线上 / 见过回踩 各自不触发）
ruff check . / layer_audit.py                           → 通过 / ERROR 0；diff 不含 intelligence/runtime/

左底向下进入 left_down_entry（新必需键）：首次下穿周期第 persist_days 天起、仍在线下、量能满足 volume 口径
  先量：41 个首次下穿日，平台当天判左底向下 1 个；平台 7 段左底向下起点 = 下穿后第 1–3 天、量能比 84–97（全缩量）
        承接盘反复里 22 次短促下穿：当天量能比中位 110、64% 带量或跳空、中位 2.5 天收回
  再建（12 个变体，全期 / 训练 / 验证 %）：
    {1, expanding_or_gap} 40.5 / 46.7 / 30.5   {1, shrink} 46.1 / 50.7 / 38.6   {1, any} 40.7 / 47.1 / 29.9
    {2, expanding_or_gap} 43.0 / 50.0 / 31.5   {2, shrink} 46.3 / 50.5 / 39.4   {2, shrink_or_gap} 46.0 / 50.5 / 38.6   {2, any} 43.2 / 50.5 / 31.3
    {3, expanding_or_gap} 42.9 / 49.8 / 31.5   {3, shrink} 46.6 / 50.5 / 40.0   {3, shrink_or_gap} 46.1 / 50.5 / 38.9   {3, any} 43.3 / 50.5 / 31.5
    {5, shrink} 46.4 / 50.0 / 40.5
  采纳 {3, shrink}：训练期与 {1,2, shrink} 持平（差半天）、验证期最好、3 = 创始人第六段的「持续」尺子

calibrate-stages（v0.1 → v0.2，快照）  framework_version = tf-v0.2+f03ec6a0
三次全新重建：labels 7bc9c6278762d044… · sector 34eb520c7a1a7a31… · succession 8f30dcc6c78653e5…  均 identical ×3
  一致率 46.57%（训练 50.48 / 验证 40.00）  未决 67  turns up 24 · top 22 · down 25
  stage_coarse：高位震荡 84 · 左底向下 71 · 共建主线 70 · 二次探底 40 · 主流主升 34 · 2.0 30 · 左底向上 6 · ambiguous 67
  E 命中天数：first_cross_below 40 · breakout 17 · overheated 14 · retest 13 · oversold 8 · upgrade 5
  板块侧规则读数不变（rps5_top10 supported 0.596 vs 0.456；kmeans_hot not_distinguishable）
```

| 版本 | 变化 | 全期 | 训练期 | 验证期 | 承接盘反复判对 | 左底向下判对 | 2.0 判对 |
|---|---|---|---|---|---|---|---|
| `785bd123` | — | 41.4% | 44.9% | 35.7% | 61 | 23 | 12 |
| **`f03ec6a0`（采纳）** | 左底向下 = 第 3 天起 + 缩量 | **46.6%** | **50.5%** | **40.0%** | **65** | **29** | **15** |

列联表：承接盘反复 161 → 高位震荡 65 · 共建主线 25 · 左底向下 23 · ambiguous 21 · 2.0 13 · 二次探底 11；左底向下 56 → 左底向下 29 · ambiguous 11 · 二次探底 5 · 共建主线 4；主流主升2.0 26 → 2.0 15 · 高位震荡 6 · 主升 3；二次探底 判对 8 → 12；缩量右底 仍 0（训练期 8 天）。

承接定义：五种候选（平均涨幅 / 中位涨幅 / 上涨比例 / 再涨停比例 / 只看连板股）的 5 日均值按八段比，现口径「平均涨幅」底部 → 主升跨度最大（1.19 → 2.65）、四分位重叠最少，其余要么压平主升、要么全段平、要么次序乱——不动。锐度合成：七种合成用「前 10 其后 5 日仍在涨幅前 30 的比例」与「前 10 的 5 日前瞻超额」比，除只看涨停家数（0.23，低于随机 0.26）外都在 0.33 / 0.38–0.40、超额 ±0.2 个点内，分不出优劣——维持两名次均值。

**差分提请创始人**：09-06 第三轮「放量跌破周均或者跳空低开跌破周均基本就是要开始向下继续调整了」与平台标注反向（平台的左底向下全部从缩量下穿起，带量的下穿多半是顶部换手、几天收回）。已按数据落成缩量，原话保留为 `left_down_entry.volume = expanding_or_gap` 可选项。

## 12. 第十二段结论

一致率 33.3% → **46.6%**（训练 50.5 / 验证 40.0），承接盘反复判对 48 → 65，左底向下 15 → 29，2.0 9 → 15。三件待拍按创始人授权用特征值定完；新的一条差分（放量跌破 vs 缩量下穿）请创始人过目。

## 13. 区间涨幅高标链（用户「继续按照最优推进」，`tf-v0.2+cb32613f`）

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 86 passed（82 + 4：range_leaders 建组 / 配对 / 形式 / 交叉三条 + CLI 端到端）
pytest intelligence/tests/test_methodology_backtest*.py → 67 passed；ruff 通过；layer_audit ERROR 0；diff 不含 intelligence/runtime/

build-range-leaders（快照，窗口 20 / 60 / 90 / 120，前 10，近旁 30）  5.0 s
  history_range_leaders 13,660 行 · history_range_leader_handoffs 2,450 行
  三次全新重建（11:00 / 12:00 / 13:00Z）：labels 00935baa03200983… · sector 143d20a05e05fe92… · succession dd98ded8f83fe71d… ·
                                        range_leaders d08898fc78a3a3ae…  均 identical ×3
  labels rows=33366（+2 视角：range_leader_entry_gain_20d/60d_pct）  一致率不变 46.57%（训练 50.48 / 验证 40.00）
  个股 → 申万一级：fact_sector_stock_daily.sw_industry 逐日全覆盖只从 2026-04 起（更早只有 2025-01 两天、2026-01 八天），
    取每只最近一天的归属作静态维表（5574 只 / 97 只在覆盖期内换过一级）；改法前 L1未知 65–85%，改法后 0
  个股名字里的 NUL 填充（如「宝丽迪\0\0」）在 SQL 里剔除，两表哈希随之变、三次一致
```

| 窗口 | 有组天数 | 衔接 | 诞生 / 天 | 在位天数 中位 / p75 | 入组门槛 p25 / 中位 / p75 | 递进 | 跨L1 | 诞生者 ≥3 板 | 消亡者跌出前 30 |
|---|---|---|---|---|---|---|---|---|---|
| 20 日 | 394 | 1041 | 2.64 | 2 / 4 | 72 / 86 / 98 % | 90.7% | 90.1% | 10.5% | 10.2% |
| 60 日 | 354 | 556 | 1.57 | 2 / 6 | 132 / 159 / 194 % | 97.7% | 90.1% | 4.1% | 5.2% |
| 90 日 | 324 | 479 | 1.48 | 2 / 6 | 169 / 205 / 246 % | 98.7% | 90.0% | 1.9% | 4.6% |
| 120 日 | 294 | 374 | 1.27 | 3 / 8 | 213 / 260 / 292 % | 98.4% | 86.6% | 2.4% | 4.3% |

交叉：连板链 166 个 ok 节点里，前任在断板日同时是区间涨幅高标的 20 / 60 / 90 / 120 日各 47 / 10 / 4 / 3 个，继任在诞生日各 35 / 6 / 5 / 6 个。入组门槛按平台阶段（20 日中位）：2.0 111 · 主升 100 · 承接盘反复 92 · 共建主线 79 · 左底向下 78 · 左底向上 76 · 缩量右底 67 · 二次探底 64。门槛试进带区：+20 日 训练 50.5 → 53.8 / 验证 40.0 → 35.8，+60 日 训练掉到 49.1，两个一起 54.6 / 37.1——都不进，只作视角。

## 14. 结论

第二刀之外的两条链现在都在旁路库里：连板高标链（166 节点）与区间涨幅高标链（四窗口 2,450 次衔接），交叉与形式分布进收据。衔接在数据上是「连续位次挪动、跨行业、与连板链各走各的」；要不要以及怎样立规则，进骨架 §1.5 待创始人。一致率维持 46.6%。全部改动在领域层，`intelligence/runtime/` 不动。

## 15. 王朝链与跳空低开跌破（用户第十三段，`tf-v0.2+d86570ba`）

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 90 passed（86 + 4：dynasties 切波 / 成员·衔接·分离 / 无覆灭行三条 + CLI 端到端）
pytest intelligence/tests/test_methodology_backtest*.py → 67 passed；ruff 通过；layer_audit ERROR 0（== 基线）；diff 不含 intelligence/runtime/

build-dynasties（快照，参照 440 日，前 10 / 宽队列 30，分位 0.9，新高窗 60）  2.2 s
  history_dynasties 150 行（5 波 × 30）· history_dynasty_handoffs 120 行（4 次衔接 × 30）
  两次全新重建（15:00 / 16:00Z，load-reference → labels → succession → sector-roles → range-leaders → dynasties）：
    labels e1b46994f6a391af… · succession 6652b25fb6934618… · sector 185c92a1b49fb1e0… · range_leaders a6895a2f3dd33576… ·
    dynasties c34351a01089e40b…  均 identical ×2
  labels 多一列旗标 tf.open_below_week_ma；一致率不变 46.57%（训练 50.48 / 验证 40.00）；参数文件多四键 → 版本 d86570ba
  波：W0 截断（2024-11-15 → 11-21，起点在标注之前）· W1 02-06 → 03-19 · W2 04-25 → 11-17 · W3 12-12 → 01-30 · W4 04-08 → 06-05（open）
  跳空实验 left_down_entry.gap_through_ma_day1 = true：一致率 46.57 → 46.15，训练 50.48 持平，验证 40.00 → 39.06；左底向下 71 → 75 天
    多出的 4 天平台标 承接盘反复 1 · 缩量右底 1 · 二次探底 2 → 不采纳，留可选项
```

| 衔接 | 覆灭窗 | 全市场中位 | 旧前 10 中位 / 回撤 | 新前 10 分位中位 / 上半区 | 新前 10 窗内创 60 日新高（全市场） | 出自旧前 30 | 提升（前 10 / 前 30） |
|---|---|---|---|---|---|---|---|
| W0→W1 | 2024-11-22 → 2025-02-05 | −7.4% | −32%（5 日波不可比）/ −42% | 82.7 / 67% | 89%（43%） | 0 | 2.0× / 1.67× |
| W1→W2 | 2025-03-20 → 04-24 | −9.3% | −27% / −35% | 65.3 / 60% | 0%（24%） | 0 | 0 / 0.67× |
| W2→W3 | 2025-11-18 → 12-11 | −5.8% | −13% / −17% | 75.6 / 70% | 60%（17%） | 0 | 2.0× / 3.0× |
| W3→W4 | 2026-02-02 → 04-07 | −9.3% | −36% / −38% | 48.9 / 44% | 67%（39%） | 0 | 3.0× / 4.0× |

统计门（个股 × 覆灭窗，条件 = 收益分位 ≥ 0.9，结果 = 进新王朝）：前 30 supported（28/2,040 = 1.37% vs 118/20,412 = 0.58%，Wilson [0.95%, 1.98%]，前后半段 0.69% / 2.06%，p = 4.6e-5）；前 10 not_distinguishable（7/2,040 = 0.34% vs 0.19%，Wilson 下沿 0.17%）。周期 4 个（1 个旧王朝截断），周期层不判。

下穿按开盘方式（收据 `views_by_event`）：全部 53 次 20 日后 34% 收在下方；低开 38 次 40%；开盘已在周均之下 16 次 **64%**（10 日后 47% 在底部四段）；盘中跌破 15 次 21%（100% 5 日内收回）；全部交易日基准 36%。

## 16. 第十三段结论

「低位一般会有衔接」的载体定下来了：不是逐日前 10 的位次轮换（§13，接近恒真），是王朝级的「旧王朝覆灭 → 亏钱效应 → 分离确认 → 新王朝」，只能事后回溯。4 次完整衔接里 3 次分离确认成立、关税暴跌那次不成立，旧王朝无一延续；前 30 口径过统计门但周期只有 4 个，规则等全量参照历史。跳空低开跌破拆开后，低开本身无信息、缺口穿过周均的在 20 日尺度有倾向、作进入证据验证期反降，留可选项。一致率维持 46.6%。全部改动在领域层，`intelligence/runtime/` 不动。待创始人的两件（王朝怎么切、亏钱效应怎么量）在骨架 §1.5 末。

## 17. 亏钱效应可量（用户第十四段「认可，亏钱效应也要可量」，`tf-v0.2+d3350cd1`）

```text
pytest intelligence/tests/test_teaching_framework_*.py  → 90 passed（王朝链单测与 CLI 端到端加亏钱日断言；build-dynasties 无 tf.money_losing_day 时 fail closed）
pytest intelligence/tests/test_methodology_backtest*.py → 67 passed；ruff 通过；layer_audit ERROR 0（== 基线）；diff 不含 intelligence/runtime/

先量（旁路库 402 个有标签日 × 平台八段，训练 ≤ 2025-12-31）：九个候选亏钱效应日口径
  宽度类（5 日上涨比例 < p25 / < 50、涨幅中位 < 0、跌停家数 ≥ p75、当日上涨比例 < p25）验证期底部 vs 顶部分不开（34 vs 37、62 vs 60、52 vs 52、43 vs 50）
  承接类两期都分得开；承接 5 日均值 < 1.0（训练 p10 = 1.045）最稠：15.8 vs 5.1 / 27.8 vs 8.5，主升 / 2.0 0%，覆灭窗 vs 顶部块 20/11/18/25 vs 10/4/4/11
  门槛扫描 1.0 / 1.2 / 1.5 / p25 / p50 → 3.1×·3.3× / 2.3×·2.2× / 1.9×·1.5× / 1.8×·1.5× / 1.3×·1.4×，取 1.0；加 5 日上涨比例 < 50 验证期不变（8.5%），不加
再建：flags tf.money_losing_day / tf.money_losing_streak（参数 money_losing 进 REQUIRED_KEYS，两份参数文件带 derived_from）
  labels rows 33366 → 34572（+open_below_week_ma / money_losing_day / money_losing_streak）；一致率不变 46.57%（训练 50.48 / 验证 40.00）
  build-dynasties 读旁路库亏钱日：每波 顶部块 / 覆灭窗前 10 日 / 覆灭窗 计数；handoffs 表 +3 列（亏钱日累计收益 / 分位 / 是否分离）
  两次全新重建（17:00 / 18:00Z）：labels edb401f13040f3d0… · succession 84921e827a4285b4… · sector 102ae4fc4c1aec5a… ·
                                range_leaders 25dd6d6c91199a84… · dynasties ae9b523e6a5ae1d6…  均 identical ×2
```

| 波 | 顶部块亏钱日 | 覆灭窗前 10 日 | 覆灭窗亏钱日 | 首个亏钱日 | 新前 10 亏钱日累计收益 分位中位 / 上半区 | 旧前 10 亏钱日累计收益 中位 |
|---|---|---|---|---|---|---|
| W0→W1 | — | — | 2 / 14 | 2025-01-23 | 34.5 / 22% | −4.3% |
| W1→W2 | 3 / 30 | 0 / 10 | 5 / 25 | 2025-03-27 | 66.4 / 80% | −6.6% |
| W2→W3 | 7 / 112 | 0 / 10 | 2 / 18 | 2025-11-21 | 32.1 / 40% | −8.7% |
| W3→W4 | 2 / 34 | 1 / 10 | 7 / 40 | 2026-03-18 | 54.9 / 56% | −10.6% |
| W4（open） | 4 / 35 | 2 / 7 | 15 / 59 | 2026-07-07 | — | — |

## 18. 结论

亏钱效应量出来了：承接 5 日均值 < 1% 是两期都分得开的唯一一维，覆灭窗里的亏钱日占比是顶部块的 2–4 倍，且先于平台的左底向下标注出现。它同时改了一句话的含义——新王朝在亏钱日本身上没有一致的分离（分位中位 34–66），被打的是旧王朝。

补：把覆灭窗拆成亏钱日 / 其余日子再看（`history_dynasty_handoffs` +3 列 `other_days_*`，dynasties 哈希 31f82b769e45255a…，两次重建一致）——新前 10 分位中位 整窗 / 亏钱日 / 其余日子：W0→W1 82.7 / 34.5 / 83.4，W1→W2 65.3 / 66.4 / 36.9，W2→W3 75.6 / 32.1 / 81.4，W3→W4 48.9 / 54.9 / 46.6。常态覆灭的分离全在其余日子，关税暴跌那次反在亏钱日上抗跌，日级没有一致形状；「在亏钱效应下酝酿走强」= 整个亏钱效应期间的相对强弱，建议定义取整窗（现口径），待创始人认（骨架 §8.14 (4)）。覆灭窗仍按阶段段落定。一致率维持 46.6%。全部改动在领域层，`intelligence/runtime/` 不动。

## 19. 授课框架接进时间长河读取面（用户「继续推进」，G-01 (b) 前置）

```text
pytest intelligence/tests/test_teaching_framework_river_objects.py → 4 passed + 1（真库：临时链接 db/market_feature_store.duckdb 跑过，之后清理）
  真库用例：slice_river 不给 teaching_labels_db 与给 None 逐字节相同；给旁路库 → 盘面轨追加 teaching_stage / teaching_dynasty /
           teaching_range_leaders；pit_grade 降为 trade_date_only（构建时刻 09-07 晚于 as_of）；require_strict 把三者全部滤掉
tests/test_river_*.py 29 passed（真库）；intelligence/tests/test_guided_reading*.py 32 passed（带读默认路径不动）
teaching 90 + methodology 67 passed；ruff 通过；layer_audit ERROR 0 == 基线；intelligence/runtime/ 零触碰

顺手修：river 资金轨聚合 SUM(DOUBLE) 并行求和顺序不定——2026-01-12 算力租赁 amount_sum 两次调用 2413.130000000001 vs 2413.1299999999997，
       source_hash 随之变，破「同一入参两次调用逐字段相同」；三个 SUM 改 DECIMAL(24,6) 精确求和后一致
王朝对象的无前视契约（测试锁死）：顶部块内的日子没有王朝对象；下一波未见顶时上一波仍是「最近一波」、不写覆灭窗终点；
       进入这一波的那次衔接（分离确认旗标）只在这一波见顶后出现；永不出现候选新王朝名单
```

## 20. 带读接授课框架读数 + 上证卡片（用户「接线」，默认关）

```text
pytest intelligence/tests/test_teaching_framework_reading.py → 6 passed（读数句 / 衔接句 / SVG 卡片 / 带读分段 / 开关解析 / 卡片写盘）
pytest intelligence/tests/test_guided_reading*.py → 32 passed（老用户默认关的接缝不动）；test_teaching_framework_river_objects.py 4 + 1（真库）
teaching 90 + methodology 67 passed；ruff 通过；layer_audit ERROR 0 == 基线；intelligence/runtime/ 零触碰

产品面边界（测试锁死）：读数句不出个股名字与代码（夹具 8 个名字 / 代码零出现）；compliance_gate.lint_output 零命中；
  无教学对象时 GuidedReading.teaching == []、渲染无「授课框架读数」段、卡片名不挂；teaching_card 只在有读数时写
真库试渲染（/tmp/tf15-full-A.duckdb，2026-09-02）：
  阶段：歧义（证据并列，当日未判）｜来源状态：共建主线
  量能：shrink（量能比 81）｜偏离度带：below｜周均线下方第 1 天（首次下穿周期）
  亏钱效应：否｜承接 5 日均值 1.54%
  王朝链：最近见顶的王朝 W4（2026-04-08 → 2026-06-05），覆灭窗自 2026-06-08 起，至今有标签 59 天、亏钱效应日 15 天；其前 10：申万一级 3 个（电子 6、机械设备 3、电力设备 1）；载体 趋势 9，连板 1｜进入这一波的衔接：上一王朝 W3 覆灭窗 2026-02-02 → 2026-04-07，本波前 10 里 3 只相对分离、6 只窗内创新高
  区间涨幅高标：20 日前 10：申万一级 6 个（农林牧渔 3、机械设备 2、电子 2），连板高标 0 只，在位天数中位 4，入组门槛 88%；…
  SVG 7.2 KB，高度随读数行数走（636 px），qlmanage 转 PNG 预览可读
```
