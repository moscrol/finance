# Delta · 境内宽基指数入库（#41-hithink 的增量，不是新链路）

- 优先级：**P2**。不阻塞任何在途工作；由一次外部断言核对失败量出（`docs/learning/knevo-distill/E-008-…md` §7.3）。
- 来源：用户 2026-09-09「宽基指数可以通过同花顺的 api key 来补」。
- **本文件不新建管线、不新建表、不新建同步器。** 需要的端点、客户端、限流、钥匙串取 key、目标表全部已在工单 #41
  （`2026-09-08-hithink-finance-ingest-workorder.md`，分支 `docs/workorder-41-hithink-ingest`，PR #678）里定好。
  这里只登记 **#41 漏掉的三处增量**，落地方式是**改 #41 的清单**，不是另起一单。
- 若 PR #678 尚未合入：直接把本文 §2–§4 并进那张 PR，本文件随即删除。已合入：另开小 PR 只改那三处。

## 0. 已存在的部分（别重写）

| 项 | #41 里已定好的 | 出处 |
|---|---|---|
| 服务与鉴权 | 同花顺官方 `https://fuyao.aicubes.cn`，`X-api-key` 头；key 只从钥匙串 `security find-generic-password -s hithink-finance -a a77-api-key -w` 或环境变量 `HITHINK_FINANCE_API_KEY` 读，**不进代码 / 仓库 / 日志 / 收据 / 对话** | #41 §0 |
| 限流 | ≤ 5 QPS（0.2–0.3 s 间隔）+ 退避，**不并发** | #41 §0 |
| 端点 | `a-share-index/prices/historical`（板块 / 指数 OHLC + volume + turnover，含当日） | #41 §0 |
| 同步器 | `sync_hithink_sector_kline.py` — **已建**，在分支 `data-source/hithink-ingest`（树 `~/fwp-wt-hithink-ingest`，领先 main 3 个提交，未合）；CLI `market_feature_store.cli sync-hithink-sector-kline --full\|--incremental [--resume] [--end-date]` | 实测 2026-09-09 |
| 目标表 | `fact_sector_kline_daily`，主键 `(trade_date, sector_ts_code)` — **已建且已填** | #41 §2 |
| 历史深度 | **约 3 年**（实测库内 2022-08-02 起） | #41 §0 + 实测 |

**⚠️ 本节 2026-09-09 修正**：初稿按 #41 原文写成「同步器待建」，实测有误——**§B 那批回补早已跑过**：
`fact_sector_kline_daily` 现有 **814,305 行 / 854 个码 / 2022-08-02 ~ 2026-09-08**，
#41 列的 6 个指数码**全部已回补，各 996 行**。所以本 delta 的性质从「补一份计划」降为
**「补一个常量 + 补跑 3 个码」**，工作量比初稿估计小一个量级。

`000001.SH` 这类宽基码已经走 `fact_sector_kline_daily`，**宽基指数与 `.TI` 板块同表是 #41 已作的决定**，本文沿用，不因为「指数不是板块」另开一张表。

## 1. 缺口（2026-09-09 实测）

`db/market_feature_store.duckdb` 只读查证：

- `fact_global_index_daily` 只有 `DJI` / `IXIC` / `SPX` / `HSI` / `HKTECH` —— **全是境外**。
- `fact_market_daily` 只有上证一组列（`sh_index_close` / `sh_index_pct_chg` / …），源 `akshare:stock_zh_index_daily:sh000001`。
- **境内宽基指数除上证外，一个都没有。**

后果已量出：核对外部断言「科创50 −5.53%」时**无表可查**，只能记 `❓ 本库无法核`，无法判定对方是准确引用还是记错指标。同批七条里另有一条（跌停池封单）也因字段缺失核不动。

## 2. Delta A · 指数码清单补三个

落点是 `market_feature_store/sync/sync_hithink_sector_kline.py:27` 的 `INDEX_CODES` 元组（分支 `data-source/hithink-ingest`），现列 6 个：`000001.SH`、`399001.SZ`、`399006.SZ`、`000300.SH`、`000905.SH`、`000852.SH`——**这 6 个库里各 996 行，已回补**。补：

| 码 | 名 | 补的理由 |
|---|---|---|
| `000688.SH` | 科创50 | **本次直接缺口**；AI / 半导体主线的对标指数，本仓题材集中在电子（`fact_market_daily.industry_1` 长期为电子，占比约 32%） |
| `000016.SH` | 上证50 | 价值 / 权重风格的对照面；`regime_scope` 判定要有风格对立面才做得出（E-008 §5-3） |
| `899050.BJ` | 北证50 | 北交所独立行情，`fact_stock_daily` 已有 `.BJ` 个股（如 `920305.BJ` 云创退进过连板梯队），指数层却是空的 |

`thscode` 必带后缀，`.BJ` 在 #41 §0 的后缀白名单内。三个码合计增加 3 次 ≤1500 天窗口请求，按 5 QPS 计约 1 秒，**对 #41 的 3 分钟预算无影响**。

**执行方式**（因已有同步器且已回补过，不重跑全量）：

```bash
# 树：~/fwp-wt-broad-index @ data-source/broad-index-delta（从 hithink-ingest 开出，已建）
# 1. sync_hithink_sector_kline.py:27 的 INDEX_CODES 加三行
# 2. --skip-constituents 是必需的，理由见下
market_feature_store.cli sync-hithink-sector-kline \
    --full --resume --skip-constituents --end-date 2026-09-08
```

⚠️ **`--skip-constituents` 不可省**（2026-09-09 读源码实测）：`--resume` 只过滤 K 线的 `codes`，
成分股那段的 `member_codes` 是从**未过滤的** `catalog_rows` 重算的（`sync_hithink_sector_kline.py:586-590`），
省掉这个旗标会多打 **848 次**成分接口，并给 `fact_sector_constituent_hithink` 写一整批
`captured_at=end_day` 的新行、连带 UPDATE `dim_sector_hithink` —— 全在本 delta 范围之外。

`--resume` 的跳过判据是 `MAX(trade_date) >= end_day AND COUNT(*) >= 100`
（`_codes_already_fresh`）。实测按 `2026-09-08` 算，854 个码里 **849 个**被跳过，剩 5 个会被重拉：
`886112.TI`(28 行) / `886111.TI`(50) / `886110.TI`(51) / `883443.TI`(66) 是**行数不足 100**、
`883401.TI` 是 `max=2026-09-03` 落后。前四个是新板块，行数天然到不了 100，
**每次 `--resume` 都会被重拉，这是判据的固有行为，不是异常**。
故实际请求数 ≈ 4 次目录 + (3 新码 + 5 重拉 + 当日上游新增的 `.TI`) 次 K 线，**不是 3 次**。

回滚：`delete from fact_sector_kline_daily where sector_ts_code in ('000688.SH','000016.SH','899050.BJ')`。
注意这只回滚三个新码；上述 5 个重拉码走的是 `INSERT OR REPLACE`，同源同值覆盖，回滚脚本不涉及。

**历史深度分工（选型取舍）**：同花顺只有约 3 年，`000688.SH` 只能回到约 2022-08，而科创50 的发布日是 2020-07；`899050.BJ` 发布日 2022-11，正好在窗口内不受影响。

| 方案 | 优点 | 缺点 | 取舍 |
|---|---|---|---|
| 全走同花顺 | 持 key 正规源、限流明确、与 #41 同一条链路 | 2022-08 之前补不了 | 日更 + 近 3 年**用它** |
| 全走 akshare | 免费、全历史（`stock_zh_index_daily` 支持 `sh000688`） | 源不稳、限流不可控，正是 #41 想迁走的那类 | 不作为主源 |
| 混合 | 覆盖完整 | 两个源要对缝，接缝日必须校验 | **采用**：3 年内同花顺，3 年前 akshare 一次性回补 |

akshare 通道已存在（`market_feature_store/sync/sync_akshare_index_daily.py`），**扩它、不新建**。接缝处必须做一次跨源校验：重叠区任取 20 个交易日，`close` 相对误差 < 0.1%，否则不合。

## 3. Delta B · 跌停池封单字段核实（#41 §C 的验收补一条）

#41 §C 已规划 `sync_hithink_limit_pools.py` 收涨停 / 跌停 / 炸板三池 → `fact_limit_pool_hithink`，**管线本身不缺**。缺的是一条验收：

- 现状实测：`fact_limit_pool_hithink.seal_money` / `max_seal_money` **只在 `pool='limit_up'` 有值，`pool='limit_down'` 全 `NULL`**（2026-07-15/16/17/20 华天科技四行均为 NULL）。
- #41 §0 的字段清单只对 `special-data/limit-up-pool` 列了「封单 / 最大封单」，**跌停端点是否回同名字段未实测**。
- 补一条验收：跌停池首日回补后，抽任一跌停股核 `seal_money` 是否非空。**空 → 记进 #41「补不了的」，不要留成看起来该有值的 NULL 列**——空壳列比缺列更坑（AGENTS.md：覆盖率审计只抓行数，抓不到「行在、值全 NULL」）。
- 另注单位：`seal_money` 是**金额**。外部常见口径是「封单 X 万手」（委托量），两者不可直接比；若端点只回金额，交叉验证时必须换算或标注口径不同，不能当同一个数。

## 4. Delta C · 新消费方：外部断言交叉验证

#41 §2 给每张表列了消费方（板块角色、`build-structure`、缠论分型…）。补一个 #41 没有的：

**用本仓事实层核验外部 agent / 共享库的引用准确度。** 2026-09-09 首次实测证明这条有产出——七条断言里核出 1 条不成立、1 条描述失准，并定位到对方极可能把「连板指数涨幅」记成了「连板晋级率」。判定规则见 E-008 §7.2 三条。

这个消费方对数据的要求与其他消费方不同，需在 #41 §2 备注：**它要的是「能不能查到」，不是「查得多快」**——一个指数缺席就让整条断言变成不可判定，覆盖广度优先于新鲜度。

## 5. 验收判据

1. `fact_sector_kline_daily` 中 `000688.SH` / `000016.SH` / `899050.BJ` 三码各自 `count(*) > 0` 且 `max(trade_date)` 等于最近交易日。
2. **闭环判据**：回填后重核 Knevo 的「科创50 −5.53%」——给出该数值对应的交易日，或判定它在 2026-07 全月不成立。这条断言正是本 delta 的起因，用它验收。
3. 混合源接缝：同花顺与 akshare 重叠区 20 个交易日 `close` 相对误差 < 0.1%。
4. 非空壳：三码各抽 5 个交易日，`open/high/low/close/volume` 非 NULL（只查行数会漏空壳）。
5. `fact_sector_kline_daily` 若为新表，须过 pre-commit 第 9 道 **dataset 注册**门（注册或写明豁免，二选一）。

## 6. 坑

- **窗口 > 约 1500 天静默返回空**，不报错（#41 §0 已记）。三个新码同样受限，别把空当成「该指数没数据」。
- **`899050.BJ` 发布日 2022-11**，早于此的空是真空，不是漏抓；`000688.SH` 2022-08 之前的空是**源的深度限制**，两者成因不同，回补脚本的日志要能区分，否则下一个人会反复重试一段永远拿不到的区间。
- 宽基指数落在名为 `sector` 的表里是 #41 的既有决定，**不要因为「读着别扭」再开一张 `fact_index_daily`** —— 那会让「当时用的是哪个指数源」变成两处事实。
