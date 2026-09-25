# 工单 #41 · 同花顺官方数据源接入：个股十年日 K / 板块日 K / 涨停池六年 / 龙虎榜 / 竞价（回补 + 日更）

- 优先级：**P1**。复盘会账号被禁后，41 张事实 / 特征表里 29 张的主源断了；这个官方 API 能把最重的几块换成持 key 的正规源。
  背景与逐端点对照见 `docs/data-sources/hithink-finance-api-assessment-2026-09-08.md`（§2 对照表、§2.5 实测、§3 补不了的）。
- 来源：用户 2026-09-08「看下这个官方 api，以后我们就有数据了 …… 要回补的任务我交给其他 agent 来做」。
- 建议拆成 5 张 PR（§3 的 A–E），互不依赖，可并行给不同 agent；每张自己开 worktree，**不在主树干活**。
- 解释器一律 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；pre-commit 11 道门（层级 / 路径字面量 / 未读字段 / **dataset 注册**）会拦。

## 0. 接入事实（已实测，别再探）

| 项 | 事实 |
|---|---|
| 服务 | 同花顺官方 <https://fuyao.aicubes.cn>，REST `X-api-key` 头；契约在仓库 [HiThink-Tech/Financial-API](https://github.com/HiThink-Tech/Financial-API) `docs/api/`，机器可读版 <https://fuyao.aicubes.cn/llms-full.txt> |
| **key** | macOS 钥匙串：`security find-generic-password -s hithink-finance -a a77-api-key -w`。**不进代码 / 仓库 / 日志 / 收据 / 对话**；他们的约定环境变量名是 `HITHINK_FINANCE_API_KEY`，sync 模块读顺序：环境变量 → 钥匙串。用户说这把 key 后续会换——代码里只能有读取方式，不能有值 |
| 限流 | 无累计上限；超 QPS 返 `code=4001`。客户端 **≤ 5 QPS**（0.2–0.3 s 间隔）+ 退避重试，**不并发**。全市场必走 dump，不逐只 |
| 本机可达 | 直接通（走代理 fake-ip 但服务端正常应答）。预签名下载主机 `o.thsi.cn` 也通；**HEAD 返 403**（签名只对 GET），量大小用 `Range: bytes=0-0`；URL 5 分钟过期，拿到立刻下 |
| 时间 | `date_ms` = Asia/Shanghai 零点毫秒；`start/end` 毫秒，`date` 是 `YYYY-MM-DD`，两种不可混 |
| 代码 | `thscode` 必带后缀 `.SH/.SZ/.BJ/.TI`；指数 / 板块走 `a-share-index/*` 端点（A 股端点拒收 `000001.SH`） |
| 探测脚本 | `/tmp/hithink_probe.py`（不在仓库，可参考请求写法）；三个 dump 已下在 `/tmp/hithink_daily_k_10y.parquet`（180 MB）/ `_10d.parquet` / `_adjustment_factors.parquet`，过期就重签重下 |

各端点**实测深度**（2026-09-08）：

| 端点 | 深度 | 量 |
|---|---|---|
| `dump/market-dumps/daily-k` | 2016-09-08 → 当日（含当日，盘后就有） | 10,271,528 行 / 5,558 码（SH 2317 / SZ 2899 / BJ 342）；高低价零空；**只有今天在市的股票**（2016 年只 2,771 码有行）→ 有幸存者偏差，历史横截面读数要写明 |
| `dump/market-dumps/daily-k-10d` | 近 10 交易日 | 1.1 MB，5.5 万行 |
| `dump/market-dumps/adjustment-factors` | 1991 → 含已公告未除权 | 57,139 条 / 5,420 码 |
| `a-share-index/prices/historical`（板块 / 指数） | **约 3 年**（上证到 2022-08；`886053.TI` 从 2023-09-06 指数发布日）；窗口 > 约 1500 天**静默返回空**，不报错 → 每次窗口 ≤ 1500 天 | 字段 OHLC + volume + turnover，含当日 |
| `a-share-index/catalog/ths-index-list` | 概念 390 / 行业 320 / 地域 33 / 特色 105 = 848 个 `.TI` | 我们 `fact_sector_daily` 的 223 个 `.TI` **100% 在目录里**（24 个同码不同名）；复盘会 407 个 `.FP` 名字对上 225 / 对不上 182 |
| `a-share-index/constituents/ths-stock-list` | 只有**当前**成分 | 单码一次 |
| `special-data/limit-up-pool` | **2020 年起**（2019-09 返回空） | 每日 35–80 只，`size=200` 一页够；字段：涨停时间 / 原因 / 连板数 / 封单 / 最大封单 / ST / 次新 |
| `special-data/limit-down-pool` / `limit-break-pool` | **一年**（更早返 `1002`） | 每日个位到几十 |
| `special-data/dragon-tiger-list` | **一年**（更早返 `1003`） | 每日 50–70 条；`board_type=hot_money` 带游资席位组（每组 `name / buying / rows[]`） |
| `special-data/hot-stock-list-history` | 一年 | 每日 30 只名次 |
| `special-data/limit-up-ladder` | 固定近 30 日、每梯最多 4 只 | 只作校验，不入库 |
| `auction/short-term-benchmark` | 按日可回到 2026-01 | **每日只 6 只**（风向标集合） |
| `auction/snapshot?stage=final` | 当日终态 | 逐只字段：竞价量比 / 未匹配量 / 换手 / 昨量比 / 流通市值 |
| `special-data/anomaly-analysis-list` | **只有当日** | 231 条，标签 大涨 / 大跌 / 涨停 / 跌停 |
| `calendar/trading-days` | 近一年 | — |

## 1. 目标形状（新表，不改旧表口径）

原则：**新源新表**，`source` 列写 `hithink:<端点>`；和复盘会 / mootdx 的旧表并跑对数，对齐后再由消费方切主。每张新表进 `market_feature_store/schema.sql` + dataset 注册（门禁会查）。

| 新表 | 主键 | 来源端点 | 消费方（切主后） |
|---|---|---|---|
| `fact_stock_daily_hithink`（open/high/low/close/volume/turnover，未复权） | (trade_date, stock_ts_code) | daily-k dump + daily-k-10d | 授课框架 `build-structure` 个股层、区间涨幅、王朝、新高家数、`feature_stock_*`；替代 mootdx + 东财快照两步 |
| `fact_stock_adjustment_hithink`（分红 / 送股 / 配股事件） | (stock_ts_code, ex_date) | adjustment-factors dump | 复权因子自算（前复权序列供结构模块） |
| `fact_sector_kline_daily`（板块 / 指数 OHLCV，`.TI` 与 `000001.SH` 等） | (trade_date, sector_ts_code) | index/historical + catalog | 板块角色、`build-structure` 板块层（改吃真点位，不再 ∏(1+pct) 造）、缠论分型 / 笔到板块层；填 `fact_sector_daily` 07-27 的 `.TI` 断口 |
| `dim_sector_hithink`（848 个 `.TI` 目录 + 类别 + 当前成分快照日） | sector_ts_code | catalog + constituents | 名字对照表（`.TI` ↔ 复盘会 `.FP` 按名字，182 个对不上的记缺口） |
| `fact_limit_pool_hithink`（涨停 / 跌停 / 炸板三池，`pool` 列区分） | (trade_date, pool, stock_ts_code) | limit-up-pool（2020 起）/ limit-down / limit-break（1 年） | 承接、促进率、连板、双红、亏钱效应的历史重建；与 `fact_theme_limit_stock_daily` / `fact_limit_advance_daily` 对数 |
| `fact_dragon_tiger_hithink` + `fact_dragon_hot_money_hithink` | (trade_date, stock_ts_code) / (trade_date, hot_money_name, stock_ts_code) | dragon-tiger-list all + hot_money | `tf.dragon_*` 资金视角；与 `fact_dragon_tiger_daily` / `fact_dragon_seat_daily` 对数 |
| `fact_hot_stock_rank_hithink` | (trade_date, stock_ts_code) | hot-stock-list-history | 新视角：注意力名次（与卖方叙事、晨汇 Tier 并排） |
| `fact_auction_hithink` | (trade_date, stock_ts_code) | short-term-benchmark（历史 6 只 / 日）+ snapshot final（日更，逐只需要代码表） | `tf.auction_zt_*` 的补充；全量竞价仍要别的源 |

## 2. 要做的事

### A. 个股十年日 K（半天）

1. `market_feature_store/sync/sync_hithink_stock_daily.py`：`--full` 走 daily-k dump（签 URL → GET 到临时文件 → DuckDB `read_parquet` → `INSERT OR REPLACE`），`--incremental` 走 daily-k-10d；`date_ms` → `trade_date` 用 `CAST(to_timestamp(date_ms/1000) AT TIME ZONE 'UTC' + INTERVAL 8 HOUR AS DATE)`（Asia/Shanghai 零点）。
2. 复权事件表同一模块或 `sync_hithink_adjustments.py`。
3. 接进 `sync_daily_full.py` 作一步（放在 mootdx / 东财之后，先并跑）。
4. **验收**：全量 1027 万行 ± 当日增量；与 `fact_stock_daily` 最近 20 个交易日逐只 close 对比一致率 ≥ 99.9%（实测 09-02 是 5,546 / 5,546）；高低价空值 0；`sync_daily_full` 干跑一次不报错；receipt 写行数与日期范围。

### B. 板块 / 指数日 K 约三年（半天）

1. `sync_hithink_sector_kline.py`：先拉 4 个 tag 的目录 → `dim_sector_hithink`；对 848 个码 + 我们需要的指数码（`000001.SH`、`399001.SZ`、`399006.SZ`、`000300.SH`、`000905.SH`、`000852.SH`）各一次 ≤ 1500 天窗口（5 QPS ≈ 3 分钟）；日更只拉近 5 天窗口。
2. **验收**：223 个旧 `.TI` 全部有行且延续到当日；`886053.TI` 从 2023-09-06 起；与 `fact_sector_daily.pct_chg` 同码同日的日涨跌幅对比（用 close 算）一致率 ≥ 99%（复盘会板块涨幅口径可能略有差，写出中位相对差）；`.FP` 名字映射表落 `docs/data-sources/`（225 对上、182 记缺口），不猜。
3. 成分股：848 个码各一次（≈ 3 分钟）存当前快照，带 `captured_at`；**不要**拿它去改历史成分表 `fact_sector_stock_daily`（那张有逐日成分，更好）。

### C. 涨停池六年 + 跌停 / 炸板一年（半天）

1. `sync_hithink_limit_pools.py --start 2020-01-01`：按交易日逐日 1 次请求（`size=200`，`pagination.pages > 1` 才翻页）；跌停 / 炸板从一年前起；非交易日返回空集不报错，按 `calendar/trading-days` 或我们 `history_calendar` 只打交易日。
2. **验收**：每日涨停家数与 `fact_market_daily.limit_up`（复盘会）近一年逐日对比，写出一致率与差值分布（两边口径可能差 ST / 北交所，先量再判）；`continue_day_cnt` 与 `fact_limit_advance_daily.boards` 抽 20 日对比；2020–2024 每年行数写进收据。

### D. 龙虎榜 + 热榜 + 竞价（半天）

1. 龙虎榜一年：每日 `board_type=all` 一次 + `hot_money` 一次；热榜一年每日一次；竞价风向标 2026-01 起每日一次；竞价终态日更（需当日代码表，`meta/tickers/list` 一次 + 分批 100 个 `thscodes` ≈ 56 次请求）。
2. **验收**：龙虎榜净额与 `fact_dragon_tiger_daily.net_amount` 同日同股对比一致率；`hot_money` 组数与 `fact_dragon_seat_daily` 游资侧行数对比；写差异不硬改。

### E. 消费方切主（等 A–D 对数报告出来再做，另开单）

`build-structure` 个股 / 板块层改读新表；`tf.dragon_*` / `tf.auction_zt_*` 改读新表；新高家数从十年 K 线自算替代 `fact_stock_high_daily`。每处切主都要重跑两次全新构建哈希一致，并在骨架 §1.3 记一段。

## 3. 验收总表（每张 PR 自己的 `docs/verification/2026-09-xx-hithink-<x>.md`）

- 行数 / 日期范围 / 代码数写进收据；与旧表的对数表（一致率、差值中位、两边独有的代码数）。
- 两次全新同步结果哈希一致（同一天内）。
- `sync_daily_full` 干跑不报错；限流日志里 4001 次数为 0 或有退避记录。
- 新表全部注册；`rg 'sk-fuyao'` 全仓为 0。

## 4. 不要做

- 不要把 key 写进任何文件（含测试夹具、收据、终端输出）；不要 `print` 请求头。
- 不要并发打接口、不要逐只拉全市场日 K（有 dump）。
- 不要删 / 改复盘会那些旧表（`fact_sector_stock_daily` 的逐日成分、`fact_theme_limit_stock_daily` 等）——并跑对数才能切主，切主是 E 单的事。
- 不要用当前成分股去回算历史板块成交占比后当真：成分只有当前，回算结果只能标「近似」。
- 个股名字只进旁路库 / 分析师侧；带读、产品面照旧不出个股。
- 不要给 `.FP` 与 `.TI` 做模糊匹配，名字对不上就记缺口。
- 板块 / 指数历史请求窗口别超 1500 天——超了不是报错，是**静默空**，会让你以为没数据。

## 5. 顺带回答：`hithink-finance` Skill 能不能出看板

能，但看板不是 Skill 生成的，是**装了 Skill 的 agent** 按仓库 `examples/inspirations/` 里 16 段 Prompt 自己取数、自己写单文件 HTML（样式 / 数据 / SVG 全内联，可离线打开）。Skill 本身只是路由说明书（怎么消歧代码、走 CLI 还是 API、key 怎么读、大结果落盘）。对我们有用的三种用法：(1) 分析师侧一次性视图直接复用那几段 Prompt（04 涨停池与连板天梯、07 热度雷达、08 / 16 龙虎榜、09 行业强度矩阵、12 涨停情绪脉冲）；(2) 我们自己的 `render_cockpit.py` / 复盘看板要吃的还是入库后的表，不吃临时 HTML；(3) 13 / 15 两个「回测台」只是示例，不替代 `methodology_backtest` 的四态门与收据。
