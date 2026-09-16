# D6 接 as_of：历史日期的方向排序不再拿今天的板块回答

分支：`fix/d6-as-of-truncation`（叠在 `docs/recheck-pit-and-feishu` 上，父分支只改文档/注释）
日期：2026-09-11

## 一句话

D6 此前整条链路取库尾，`「2026-07-10 最值得关注的三个方向是哪三个」`拿回的是
2026-08-13 ~ 2026-09-10 的窗口；本分支把截止日接上，同一问句现在回 2026-06-29 ~ 2026-07-10。

## 为什么是「没接线」而不是「没有」

开关一直在，只有 D6 一个没用：

| 现成件 | 位置 | 谁在用 |
|---|---|---|
| `resolve_query_themes(..., as_of=)` | `market_midterm.py:211` | D8/D11 截断那轮加的，判例 `test_analog_as_of_truncation` |
| `market_review_requested_date(query)` | `query_understanding.py` | D0 锚日 |
| `standing_iso_from_query(query)` | `asof_prefetch.py` | Engine-A 预取 |
| `options.date` | `ask.py`（`bind_market_watch_pack` 写入） | D9 `as_of_date` / D12 `as_of` |

上一轮清单里我把它写成「D6 全链路没有 as_of 管道」，并补了一句「触发条件只有前瞻性
排序题，与今天一致，暂不影响」——**两句都错**。`is_direction_ranking_query` 是纯词面门
（`_RANKING_SUBJECT_TERMS` × `_RANKING_ACTION_TERMS`），带日期的历史问句照样命中。

## 改了什么

1. `_fetch_theme_trend(con, theme, window, as_of=None)`：**三条查询一起截**——趋势窗、
   拥挤度 trailing 分布、涨停热度。只截趋势窗的话，分位的分母会带上未来成交额，
   数字看着正常，实际是拿后来的分布给当时排名（M7 变异专门盯这个）。
2. `top_board_themes(con, limit, as_of=None)`：基准日从「库尾」改成「≤ as_of 的最后一个
   交易日」。候选池本身就是一次排序，拿库尾成交额榜回答历史问句 = 把「后来谁大」当成
   「当时该看谁」。这一面是上一轮兜底新引入的，历史问句最容易在这里被喂错。
3. `load_midterm_trend_artifact` / `midterm_trend_block_for_llm`：透传 `as_of`。
4. `ask.d6_as_of_for(query, options_date)`：`options.date` 优先，否则用 D0 同一个解析器。
   D6 provider 调它。`as_of=None` = 库尾 = 旧行为。
5. 块口径行在有 as_of 时多一句「截至 2026-07-10（不含之后的行情）」。历史问句下，
   这行是模型分辨「当时/今天」的唯一依据。
6. 「覆盖天数」列改成**不同交易日个数**（原来是行数）。见下面的遗留项。

## 实测（真库 `db/market_feature_store.duckdb`）

| 问句 | as_of | 窗口 | 首位题材拥挤度 |
|---|---|---|---|
| 明天最值得关注的三个方向 | None | 2026-08-13 ~ 2026-09-10 | 芯片 1.7% |
| 2026-07-10 最值得关注的三个方向是哪三个 | 2026-07-10 | 2026-06-29 ~ 2026-07-10 | 芯片 90.0% |
| 站在2026-07-10，当时最值得关注的三个方向怎么排序 | 2026-07-10 | 同上 | 同上 |

修复前这三行的结果**完全相同**（都是第一行）。差的不是一点：提示词里的规则是
「拥挤度 ≥80% 说明是短期脉冲，中期赔率应下调」——穿越把一个 90% 的拥挤读数换成了
1.7%，等于把当天该触发的那条警告整个抹掉，方向还是反的。候选池也换了人
（`储能` → `机器人`）。

前瞻问句（`as_of=None`）逐格不变，只有表体之外的口径行不同。

## 测试

新文件 `intelligence/tests/test_midterm_as_of_truncation.py`，11 条。每条都过了变异：

| 变异 | 变红 |
|---|---|
| M1 题材名录不截（只截取数） | `test_theme_absent_at_as_of_does_not_resolve` |
| M2 趋势窗不截 | 日期断言 + 拥挤度断言 |
| M3 候选池不截（兜底回库尾 top6） | `test_board_fallback_uses_as_of_day_ranking` |
| M4 ask 侧不传 as_of | `test_builder_passes_as_of_into_d6` |
| M5 覆盖天数回退成行数 | `test_coverage_days_counts_distinct_dates_not_rows` |
| M6 口径行不写截止日 | `test_as_of_none_keeps_tail_numbers_...` |
| M7 拥挤度分母不截 | `test_crowding_denominator_is_truncated_too` |

M1 是初版**没照出来**的：只问「光模块」时，漏截名录也只是得到一个空块（题材解析出来了
但取数为空，渲染层直接返回空串），`assertNotIn` 恒绿。改成问句同时点名一个截止日前就
存在的题材后才照出来——夹具形状同理，「截止日后成交额恒定」会让按 `<=` 计数的分位
落在 98.3%，M7 也照不出来。两处都写进了测试 docstring。

全量：**9163 passed, 77 skipped, 1 xfailed**（319s），ruff 干净。

## 明确没做的（下一件事，别混进来）

**行窗口 ≠ 交易日窗口。** 同一板块名挂两套供应商代码（`885756.TI` / `990325.FP`，全库
3,206 组重复），所以 `limit 20` 在有重复的区段上只覆盖 10 个交易日。实测 2026-07-10：

| 题材 | 行-60 分位 | 去重日-60 分位 | 20 行覆盖天数 |
|---|---|---|---|
| 芯片 | 88.3% | 93.3% | 10 |
| 数据中心 | 86.7% | 90.0% | 10 |
| 机器人 | 15.0% | **0.0%** | 10 |
| 电子 / 机器人概念 / 新能源车 | 与去重版相同 | — | 无重复 |

库尾侧两种算法一致（芯片 1.7%/1.7%，电子 1.8%/1.8%）——这正是上一轮「量过，不改」
的依据，那次只量了库尾。接上 as_of 之后，历史区段的差异浮出水面。

本分支只把**渲染出来的「覆盖天数」**改成真话（20 → 10），**没动窗口算法**：改成去重日
窗口会改动库尾既有答案的双红天数/成交额趋势，那需要单独一轮测量与评审。

## 其他

- `hindsight` 标记仍不覆盖 D 块：river 的 `knowledge_cutoff > as_of` 拒绝只管 river 读取面，
  ask 的 D 块不经过它。历史问句下 D6 现在是诚实的，但「这是事后视角」这面旗还是靠
  observation/checkpoint 层调用方手动传。
- D8/D10/D11 在 ask provider 路径上同样没传 as_of（as_of 只长在 `asof_prefetch` 那条路上）。
  D6 先修是因为上一轮给它加了兜底、让排序题必出块，把沉默的洞变成了每次都出的洞。
  其余三个块要不要同样接，建议按同一形状另起一轮。
