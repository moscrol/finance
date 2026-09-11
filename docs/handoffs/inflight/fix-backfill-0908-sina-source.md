# 2026-09-08 缺失交易日回补（新浪源）

分支 `fix/backfill-0908-sina-source`｜基线 `11a274e8`｜执行 2026-09-11 14:00~17:30｜生产库直写

## 结论

2026-09-08 从「几乎整日缺失」补到与邻日同级，验收四件全绿。同时发现并修掉一个会**静默**
把全部 403 个板块判死的白名单缺口（`status=ok code=0` 但 `stitched=0/403`）。

## 回补前的实际缺口（不是清单上写的那样）

`audit_coverage.py` 原先**看不见** 09-08：`fact_market_daily` 无 09-08 行 → 它进不了
`calendar_with_amount` → 其余每张表的 missing 列表里都不出现它。逐表实查才看到：

| 表 | 回补前 | 回补后 | 09-07 | 09-09 |
| --- | --- | --- | --- | --- |
| `fact_stock_daily` | 930 | **5549** | 5557 | 5551 |
| `fact_sw_l1_daily` | 0 | **31** | 31 | 31 |
| `fact_sector_daily` | 0 | **403** | 403 | 403 |
| `fact_sector_stock_daily` | 0 | **52802** | 52842 | 52808 |
| `fact_sector_universe_daily` | 0 | **403** | 403 | 403 |
| `fact_market_daily` | 0 | **1** | 1 | 1 |
| `fact_stock_high_daily` | 0 | **645** | 373 | 774 |
| `fact_theme_limit_heat_daily` | 0 | **225** | 239 | 166 |
| `fact_theme_limit_stock_daily` | 0 | **632** | 1003 | 366 |
| `fact_limit_advance_daily` | 0 | **19** | 13 | 8 |
| `fact_sector_period_rank_daily` | 0 | **40** | 40 | 40 |
| `feature_stock_technical_daily` | 0 | **5527** | 5534 | 5527 |

## 那 930 行没有覆盖，是刻意保留的

`source='ifind:get_stock_performance'`，2026-09-09 19:25:57 写入，属 2026-06-22~09-08 八天
ifind 试验（工单 #41，2249 行）。判定为**真 09-08 数据**而非次日复制：与邻日收盘只有
2.0%/2.2% 相同，且 `pre_close == 09-07 close` 达 928/930（99.8%）。它的 `pre_close` 是除息
调整基，比新浪的裸价基更好 → 保留，只补缺的 4619 只。`qa_backfill_align` 对混源只 INFO
（先例：09-07 本身就是 `eastmoney:snapshot` 5549 + `mootdx` 8）。

## 取数源：文档里记的三条在本机全死了

详见 runbook 新增的「第三条路径」表。摘要：mootdx 14 台 HQ 服务器**全部 0 根**（本机 TCP 出口
`198.18.0.1`，TUN 代理吞掉 TDX 7709 二进制协议，跑 51 分钟 0 行）；东财 `push2his` 头 12 个
请求后**整站级 IP 拒连**（但生产快照用的 `push2` 实测仍 200，未受影响）；iFinD 无 token。
腾讯/新浪 CN_MarketData 通但**无成交额**；网易 502。

→ 换成 `akshare.stock_zh_a_daily`（新浪），已参数化收进
`skills/duckdb-backfill/scripts/backfill_stock_daily_sina.py`（fetch/validate/write 三段）。
取数 4629 只 / 1898s：ok 4619、停牌 9、失败 1（`689009.SH` CDR，新浪不支持，缺失率 0.018%）。
取数阶段全程不持库连接，写入是单次短事务（避开「长事务饿死生产端只读连接」）。

## 代码改动（两处，都有钉子）

1. `VALUE_SOURCE_PREFIXES` 加 `"sina"`（`sync_local_sector_members.py`）。
   不加的后果是**静默失败**：`stitch-sector-stocks` 报 `status=ok code=0`、3.4s、
   `stitched=0/403 skipped[shortfall=403]`，而 `sector-daily-local` / `mainline` /
   `core-leader` / `features` 全部连坐 FAIL。辨识特征是输出里 `基线日期分布: {}`。
   新用例 `test_stitch_accepts_sina_value_source`（照 iFinD 进白名单时的
   `test_stitch_accepts_ifind_value_source` 写），去掉 `"sina"` 即红，已变异验证。
   **没有**为了过门禁去改行的 `source` 标签——那是伪造出处。
2. runbook：新增坑⑦（白名单静默判死）、「第三条路径：新浪」、模块清单第 2 行改为指向新脚本。

## 绕开的两个红线坑

- **坑⑤**：`--plan local` 的 `stock-daily` 步调的是 `sync-stock-daily-snapshot`（「取最新」语义），
  对历史日会写成今天的价 → 全链改从 `--from-step`/`--only` 跑，跳过该步。
- **坑①**：`sync_akshare_sw_l1_daily` 抓完 hist 后**无条件**调 `index_realtime_sw` 覆写 end 日
  31 行，CLI 无开关可关（`:283-297`）。改为复用其 `_fetch_sw_l1_codes` / `_fetch_hist_by_code`
  只走 hist 分支写入（脚本 `/tmp/bf0908/sw_l1_0908.py`，一次性，未收仓）。
  验收 `pre_close(D) == close(D-1)` 31/31。
- **坑④**：`fact_market_daily` 日历行是在 `index-daily` 步建的，建了就必须当晚把 GAP_TABLES 补齐，
  否则 cross-day-gate 连坐 → S7 不换名。本次一口气跑完，`cross-day-gate status=ok`。

## 验收原始输出

```
① python3 scripts/check_daily_review_data.py 2026-09-08 --phase data --plan local
   feature_stock_window: rows=21805 max=2026-09-10
   feature_stock_technical_daily: rows=5527 max=2026-09-10
   fact_sector_daily 名称连续性: 402/402 = 100.00% (前一交易日 2026-09-07)
   fact_stock_daily 覆盖率: 5537/5537 = 100.00%
   fact_stock_daily 与前一交易日 2026-09-07 逐股相同: 0/5547 = 0.00%
   RESULT: COMPLETE

② python3 -m market_feature_store.cli check-daily --trade-date 2026-09-08 --plan local
   跨日质检 @2026-09-08 (日历窗口=20, plan=local)
   RESULT: PASS | 通过        （json ok=true, issues 无）

③ python3 skills/duckdb-backfill/scripts/qa_backfill_align.py 2026-09-08 --plan local
   [PASS] market: fact_market_daily 字段齐全
   [INFO] source: fact_stock_daily sina:stock_zh_a_daily=4619, ifind:get_stock_performance=930
   [PASS] source: fact_sector_daily local:agg/pct=eqw=403
   [PASS] source: fact_sw_l1_daily akshare:index_hist_sw
   [PASS] source: fact_sector_stock_daily local:stitch=52802
   [PASS] stock-chain: pre_close 链 2/5549 不等（基线同量级），pct_chg 重算 0 不符
   [PASS] sw-l1: 31 行业链式一致
   [PASS] index-chain: 上证 3940.551 (+0.20%) 与前收链一致
   [PASS] amount-basis: 全A合计/申万合计 = 1.0097（基线 1.0075~1.0177）
   [PASS] amount-basis: 市场总额/全A合计 = 0.9908（基线 0.9848~0.9933）
   [WARN] nulls: fact_stock_daily turnover 81%→0%
   [WARN] nulls: fact_sector_stock_daily fund_flow_1d 50%→100%, fund_flow_5d 50%→100%
   [PASS] sectors: 板块日线 403 / 成分覆盖 403 板块 52802 行，宇宙 403
   [INFO] double-red: 严格双红 14 个（基线各日 [30,13,2,6,41,12]）
   RESULT: PASS | FAIL 0 / WARN 2 / 检查项 22

④ 严格双红 14 个：乡村振兴(1.61%/22.6/1459.8亿)、化工(1.57%/16.41/1211.5亿)、
   毫米波雷达(0.02%/11.7/1193.1亿)、医药医疗、有色、6G概念、医药、创新药、碳中和、
   黄金概念、工业金属、合成生物、动力电池回收、养老概念
```

两条 WARN 逐条说明：① `turnover` 空值率 81%→0% 是**我补满了**（新浪带换手率，基线里 mootdx/
东财快照都留空），比基线更全，不是缺；② `fund_flow_1d/5d` 100% 空是 fupanhui 独有字段，
`local` 计划本就不产（`--plan local` 下不算缺表，但空值率检查仍会 WARN）。

另：`--plan local` 是 SKILL 规定的门禁形态。不带这个参数时会多出 6 条 FAIL
（`fact_theme_flow_daily` / 龙虎榜三张 / 全球指数两张 = fupanhui 及其他计划档位才产的表）
和 1 条 calendar FAIL，都是口径问题不是缺口 —— 别被它吓到去乱补。

## 顺手修的与发现但**没**修的

- 修了：09-08 的 164 行 `stock_name` 带 `\x00`（来自那 930 行 ifind），用邻日东财权威名替换，
  兜底 `rtrim(chr(0))`。新脚本 write 段也内置了这步。
- **没**修（存量，另开票）：同样的 `\x00` 填充存在于 **2025-01-02 ~ 2026-09-04 的几百个交易日、
  每日约 840 行**，`source='mootdx'`。即 runbook 坑③ 记的「写入前需 `rstrip('\x00')`」至今没在
  `sync_mootdx_stock_daily.py` 里实现。这是一次性数据迁移 + 一行写入端修复，范围远超本次回补，
  未擅自动别人的历史数据。
- `689009.SH`（CDR）新浪不支持，09-08 仍缺 1 只。

## 复现命令

```bash
S=skills/duckdb-backfill/scripts/backfill_stock_daily_sina.py
python3 $S fetch --trade-date D && python3 $S validate --trade-date D && python3 $S write --trade-date D
python3 skills/daily-full-review/scripts/run_review_sync.py --date D --plan local --only index-daily
python3 skills/daily-full-review/scripts/run_review_sync.py --date D --plan local --from-step carry-forward-universe
```
