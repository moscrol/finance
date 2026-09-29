# 发布回执 · 2026-09-29 23:08：历史名 NUL 清理（#968，扩至派生表）+ 300211.SZ 09-29 改名

执行者：Claude Code 云端会话 `session_01CBRwJztt4t57Zzr8VMeZZM`，经 exec 隧道操作 Mac。
授权：用户 09-29 约 23:00「这些也是你来推进，按照最优方案」。这句话回复的是本会话列出的三项数据遗留：300211 名、09-29 申万一级前收、#968 NUL。

## 1. 做了什么

走候选库路径（`clone_to_staging` → 候选上改写 → 验收 → 守卫换库），没有直连生产写。代码从干净的 main 检出（`f02fbaa7`）import。

**第一步：清 NUL。** 同一条 `replace(stock_name, chr(0), '')`（不加 trim），单事务执行。范围从 `fact_stock_daily` 扩到 10 张派生表，它们的主键都不含名字列：

| 表 | 行数 |
|---|---:|
| fact_stock_daily | 298,718 |
| feature_stock_window | 1,118,529 |
| feature_stock_technical_daily | 2,831 |
| fact_sector_stock_daily_generation | 2,830 |
| fact_stock_high_daily | 208 |
| fact_theme_limit_stock_daily | 126 |
| fact_mainline_stock_daily | 14 |
| fact_core_stock_daily | 9 |
| fact_core_leader_daily | 3 |
| fact_limit_advance_daily | 2 |

**第二步：300211.SZ 改名。** 2026-09-29 那天的「*ST亿通」改为「亿通科技」，涉及 4 张表共 11 行（日线 1、板块成分 8、新高 1、技术特征 1）。
- 依据：09-29 收盘后封存的腾讯报价与东财现名两源一致。它 09-28 停牌一天、09-29 复牌（09-25 是中秋休市），符合撤销退市风险警示时「停一天、复牌改名」的形态。
- 创业板 ST 与否涨跌幅限制都是 ±20%，涨跌停统计不受影响，所以不重算派生表。
- 为什么急：桥的名称政策是「库内最近一条非空名」。不改的话，09-30 起会继续把「*ST亿通」抄下去。

**第三步：`feature_limit_advance_window`。** 它的主键含 `stock_name`，NUL 把 002403.SZ 和 603823.SH 拆成「同股同窗两行」，共 61 组。
- 做法：源表清理后，只对这 2 只股票、在受影响的 17 个 as_of 日内，用 `compute_features._build_limit_advance` 的原公式重算。删 159 行、插 102 行，其余 230,927 行逐字节不变（含 `calculated_at`）。
- 第一次构建用的是整日 `compute_features --only limit-advance`，被自检拦下，没有发布，报告在 `db/candidate-namefix-0929.failed-1/`。拦下原因：整日重算会把其他股票的窗口行也换成用今天源数据重算的值（期间有过回补），等于借修 NUL 改写历史。

## 2. 验收

事务内逐表核对，任一项不符即 ROLLBACK：
- 行数不变；
- 非名字列的 `sum(hash(row(...)))` 不变；
- 名字列指纹等于「按规则变换后的旧值」；
- NUL 为 0；
- 逐代码的不同名字数等于迁移前的 `clean_count`（300211 单独核）。

| 检查 | 候选库 | 生产（发布后） |
|---|---|---|
| `check_daily_review_data 2026-09-29 --plan local` | COMPLETE | COMPLETE |
| `check-daily --plan local` | PASS | PASS |
| #968 `tests/test_stock_name_nul_history.py`（真库） | 3 passed | 3 passed |
| 整库 69 张表逐表 `count + sum(hash)` 对比生产 | 只有上述 11 张不同，行数只有窗口表 −57（合并掉的分裂行） | — |

8792：发布后 health 仍为 `e6237489d799` / 干净 / 代码与仓库一致，readiness 13/13。

## 3. 发布与回滚

- 23:08:28 由 `db/candidate-namefix-0929b/publish_namefix.py` 执行，守卫与 `publish_candidate_gapfill.py` 相同：
  - run mutex → 写者探针 → 换库锁；
  - 生产身份（ino / mtime_ns）必须等于克隆时；
  - ops 补差为 0；
  - 换库前备份，原子换名；
  - 18:00–21:30 夜跑窗口内拒绝执行。
- 收据：`db/candidate-namefix-0929b/publish-receipt-namefix0929-230828.json`。
- 回滚：用换库前备份 `db/market_feature_store.duckdb.bak-20260929T230828-namefix0929-230828`（sha256 前缀 `e0db156c19b5b9f3`）按原子换库换回。要避开夜跑窗口，并由用户确认。

## 4. 这次没改的：09-29 申万一级前收

- 现象：`fact_sw_l1_daily` 的 09-28 行来自 09-28 晚的**实时**接口（例如 801010 收盘 2538.76），而 09-29 实时接口给的昨收是 2538.89。31 个行业全都差一点，平均 1.6 点。
- 为什么没手工改：申万**历史**接口（`index_hist_sw`）23:00 仍只到 09-24，没有权威来源。拿实时的「昨收」去改历史日，正是「取最新写历史日」那条红线。
- 自愈路径：夜跑 `sync-sw-l1-daily --days 20` 每晚对窗口内历史接口已有的日期用历史值覆盖（`sync_akshare_sw_l1_daily.py`）。历史接口一发布 09-28，当晚就会纠正。派生表偏差在万分之一量级。
- 核对：09-30 夜跑后查 09-28 行的 `source` 是否已变成 `akshare:index_hist_sw:*`，以及 09-29 的 pre_close 是否等于 09-28 的 close。

## 5. 遗留与建议

- mootdx 名字里带空格或全角字母（例如「全 聚 德」）的 26,558 行不在 #968 范围内，仍是一码两名。
- **桥名称政策的结构性缺口**：同花顺桥只用「库内最近一条非空名」，戴帽摘帽等改名永远跟不上，300211 就是一例。建议把当晚封存报价的名字作为桥接行名称的覆盖来源（对「非空但与报价不同」的名字）。
  - 这是合同 1 的范围扩展：合同 1 目前只接受封存报价给**空名**补名。需要用户另行接受，本次没做。
  - 在那之前，主板股改名会影响 ST 的 ±5% 判定，可能错算涨跌停。
