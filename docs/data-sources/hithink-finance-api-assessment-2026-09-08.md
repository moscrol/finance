# 同花顺金融数据服务（hithink-finance）× 我们的数据：能补什么、补不了什么、先接哪个

> 2026-09-08，用户「看下这个官方 api，以后我们就有数据了 …… 还有哪些数据可以给我们做补充的，可以优化我们的数据或者说给我们更多的消费源的」。
> 看的是仓库 [HiThink-Tech/Financial-API](https://github.com/HiThink-Tech/Financial-API)（monorepo：`docs/api/` 59 个 REST 端点契约、`python/` SDK + 本地 marketdb、`skills/`、Node CLI），
> 上游是 fuyao.aicubes.cn（同花顺官方）。**本文只对照契约与我们的表，没有 key，没拉过一条真数据**；深度、权限、限流实感要拿到 key 后再补。

## 0. 一句话

我们 41 张事实 / 特征表里 **29 张的唯一或主要来源是复盘会（fupanhui）**（按快照库逐表 `source` 列数的），账号现在是封的。这个 API 能用**一把官方 key** 把其中最重的几块换成正规源：全 A 十年日 K（开高低收量额 + 复权事件）、板块日 K（同花顺 `.TI`，带高低价）与成分股、涨跌停 / 炸板 / 连板池、龙虎榜（含游资席位）、集合竞价、热榜。**换不掉的**是复盘会里「人」标的东西（八段 / 主线 / 核心股 / 事件日历 / 龙头高度）和它的题材资金流，以及**分钟级 K 线**——文档明写「分钟 K、tick 不在公开能力范围」，30 分钟线那条还是要靠本机代理放行东财 / 腾讯的 K 线主机。

## 1. 这个服务是什么

- 官方：同花顺面向 Agent / 量化 / 开发者的 A 股数据服务；REST、托管 MCP（四个端点）、Node CLI、Python SDK、本地 DuckDB（marketdb）共用**一个 API Key**（`X-api-key` 头）。Key 在 <https://fuyao.aicubes.cn/admin/> 用同花顺账号登录后签发，与账号绑定；能力按账号授权（无权返回 `2003`）。
- 限流：「不设累计调用次数上限」，超 QPS 返回 `4001`；他们自己 SDK 的客户端默认 **5 QPS**（`marketdb/providers/rest.py`：0.2 s 间隔 + 退避）。全市场必须走 Parquet 导出（3 次请求），不许逐只拉。
- 本机可达：`fuyao.aicubes.cn` 走代理 fake-ip 但服务端正常应答（无 key 请求返回 `code=2003 Missing X-api-key`），不像东财 / 腾讯 K 线主机那样被掐。
- 时间线（CHANGELOG）：07-01 起对外，07-10 monorepo，07-17 基金，07-24 估值，08-17 竞价 / 跌停 / 炸板，09-08 最新一版。是个**两个月大的新服务**，接口在快速加，字段契约有 `llms-full.txt`（276 KB）机器可读版。
- 收费：仓库与在线契约里都没有价格 / 套餐字样，看起来是登录即用；以官网为准。
- 数据口径：日 K 未复权（`adjusted=none`）+ 复权事件流（现金分红 / 送股 / 配股）自己推因子，或逐只接口传 `adjust=forward|backward`；毫秒时间戳按 Asia/Shanghai 零点；板块 / 指数无复权语义；`thscode` 必须带后缀（`.SH/.SZ/.BJ/.TI`）。

## 2. 端点 × 我们的表（能补什么）

「现状源」按 2026-09-08 快照库（`/tmp/mfs-snap2.duckdb`）逐表数出来的；「优先级」是我的建议，A = 有 key 第一周就接，B = 第二批，C = 有余力。

| 同花顺端点 | 我们的表 / 消费方 | 现状源与短板 | 接上后的收益 | 优先级 |
|---|---|---|---|---|
| **全市场 10 年日 K Parquet**（`dump/market-dumps/daily-k`，~945 万行 OHLCV）+ 近 10 日增量 + 全市场复权事件 | `fact_stock_daily`（373 万行，2023-09 起） → 授课框架个股层（`build-structure` 背离、区间涨幅、王朝）、新高家数、`feature_stock_*` | 四个源拼的：mootdx 344 万（通达信逐只 TCP，慢）、东财快照 23 万、复盘会兜底 5 万、本地复权 4 千；只有 3 年；没有统一复权 | 十年深度、单一官方源、复权事件；**日增量 3 次请求替代 mootdx + 东财快照两步**；`fact_stock_high_daily`（新高家数，现全靠复盘会）可以自己从十年 K 线算 | **A** |
| **板块日 K**（`a-share-index/prices/historical`，`.TI` 概念 / 行业 / 地域 / 特色，OHLCV，单码 ≤ 10 年）+ 板块目录 + 当前成分股 | `fact_sector_daily`（10.6 万行，只有 pct_chg / amount）、`fact_sector_universe_daily`、`fact_sector_stock_daily`（389 万行成分×日） → 板块角色、赚钱效应、`build-structure` 板块层、ev 板块锚点 | 复盘会；**没有板块高低价**（缠论分型做不了板块层）；07-27 宇宙从 630 个 `.TI` 换成 403 个 `.FP`，序列断成两截、要按名字接 | 真板块指数（不用 ∏(1+pct) 造点位）、有高低价、`.TI` 与我们 07-27 之前的代码是同一套（`886053.TI` = BC电池）——**那个断口能用官方序列填回去**；成分股表可替代复盘会成分（只有当前，见 §3） | **A** |
| 指数日 K（同上端点，`000001.SH` 等） | `fact_market_daily.sh_index_*`（复盘会 / 飞书 / akshare 补洞） | 三个源拼；08-17 等日期有洞（#668 补过） | 官方指数 K 线作洞的兜底源 | B |
| **涨停股票池**（`special-data/limit-up-pool`，按日：涨停时间 / 原因 / 连板数 / 封单 / 最大封单，`page/size`） | `fact_theme_limit_stock_daily`（15 万行）、`fact_limit_advance_daily`（连板）、`fact_theme_limit_heat_daily`（板块涨停热度 4.7 万行） → 承接、促进率、双红、龙头 | 全部复盘会 | 涨停池按日可回补（深度未知，要试）；配合成分股能自己算板块涨停热度；「涨停原因」是复盘会没给结构化的字段 | **A** |
| 跌停池、炸板池（`limit-down-pool` / `limit-break-pool`，含开板次数） | `fact_theme_limit_stock_daily.open_times` 有炸板痕迹；跌停没有专表 → 亏钱效应、情绪 | 复盘会里散在涨停表里 | 亏钱效应多一个直接量（跌停家数 / 炸板率） | B |
| 连板天梯（`limit-up-ladder`，固定近 30 日、每梯队最多 4 只） | `fact_limit_advance_daily` / `feature_limit_advance_window` | 复盘会 ladder 全量 | **比我们现有的弱**（只 30 天、每梯 4 只），只作校验 | C |
| **龙虎榜**（`dragon-tiger-list`，全部 / 机构 / 游资，游资维度带席位行，近一年按日） | `fact_dragon_tiger_daily`（2.8 万）、`fact_dragon_seat_daily`（17 万）、`fact_dragon_summary_daily` → 资金视角 `tf.dragon_*` | 复盘会 | 一年可回补、字段对得上（净额 / 机构净额 / 游资净额 / 上榜天数 / 概念） | **A** |
| **集合竞价**（`auction/snapshot` 实时 / 终态，`short-term-benchmark` 按日） | `fact_auction_stock_daily`（1 万行，2026-01 起） → `tf.auction_zt_*` | 复盘会竞价看板 | 终态快照每天 9:25 后拉一次；短线风向标按 `date` 查，能不能回补看实测 | **A**（日更）/ B（回补） |
| 热股榜 / 飙升榜 / 历史热股榜（近一年按日）/ 单股热度趋势 | 没有对应表 → 新视角：注意力 × 价格（仓库 examples 第 11 个就是这个题） | — | 新消费源：热度名次作「舆论热度」的机器版，与卖方叙事、晨汇 Tier 三条并排 | B |
| 个股异动原因（`anomaly-analysis-*`，**仅当日**） | 没有 → 盘中 / 盘后异动归因 | — | 只能每天存当天，不能回补；接了就从第一天开始累 | C |
| 交易日历（近一年） | `history_calendar` 从行情行派生 | — | 官方日历兜底（假日顺延判断） | C |
| 标的检索 / 代码表（`meta/tickers/*`） | 个股名（`stock_name` 里有 `chr(0)` 要洗）、板块名 → 代码 | — | 干净的名字与代码表 | B |
| 财务三表 / 财务指标 / 估值快照（PE TTM/MRQ、PB、PS、PCF） | 不在特征库；`stock-deep-dive` 一类分析师侧 skill | — | 产品 / BP 面有用，授课框架不用 | C |
| 公募基金 28 个端点（ETF 快照 / 日线、持仓、净值…） | §1.5 那条「两融余额 / ETF 份额变动库里没有」 | — | **没有份额**，只有价格 / 净值 / 定期持仓，填不上那条 | C |

## 3. 补不了的（写清楚免得再问）

- **分钟 K / tick / Level-2**：契约与 README 都明写不在公开范围。30 分钟线仍走东财（`push2his.eastmoney.com`）/ 腾讯（`web3.ifzq.gtimg.cn`），本机代理要给这几个域名加 DIRECT；L2 大单仍靠 ClickHouse 鉴权那条。
- **板块成分股只有当前**，没有历史调入调出——回算历史「板块成交占比」只能拿当前成分近似；我们 `fact_sector_stock_daily` 里复盘会给的逐日成分（389 万行）在这点上反而更好，别删。
- **异动只有当日**，不能回补。
- **复盘会的人工层**：八段 `market_stage`、主线（`fact_mainline_*`）、核心股、事件日历（`fact_event_daily`，ev 的编辑源）、龙头高度、题材资金流面板、监管池 / 监管事件、研报目录、全球市场——这些没有替代，要么继续靠账号恢复后的 CDP 页面读取，要么用我们自己的框架（授课框架就是八段的自家版）。
- **两融余额、ETF 份额**：没有。

## 4. 有 key 之后怎么接（顺序）

1. **探测**（半小时）：`meta/tickers/search` 一条、`prices/snapshot?thscodes=000001.SH` 一条确认 key；`limit-up-pool?date_ms=<一年前>` 与 `dragon-tiger-list?date=<一年前>` 探回补深度；`a-share-index/catalog/ths-index-list` 四个 tag 拉目录，与我们 `.TI` 代码 / `.FP` 名字对一次（预期：名字对上 500+）。
2. **个股十年日 K**：三个 dump → 新表 `fact_stock_daily_hithink`（或 `fact_stock_daily` 加 `source='hithink:dump'` 行——建议新表，过 `dataset-registration` 门禁，别和 mootdx 混口径）；复权事件另一张；日增量用 `daily-k-10d` 按 `(thscode, date_ms)` UPSERT。
3. **板块 `.TI` 日 K 十年**：630 个代码逐只拉（5 QPS ≈ 2–3 分钟）→ `fact_sector_kline_daily`；把 `fact_sector_daily` 07-27 的断口用官方序列接回；`build-structure` 板块层改吃真点位；缠论分型 / 笔套到板块。
4. **涨停池 / 龙虎榜 / 竞价终态**：各一个 `sync_hithink_*.py`，先跟复盘会表并跑一个月对数（同一天两边的涨停家数、龙虎榜净额差多少），再决定切主。
5. **热榜**：新表，每天一次，从第一天开始累。
6. 全部走 `HITHINK_FINANCE_API_KEY` 用户级环境变量（他们的约定），不进代码、不进仓库、不进日志；客户端 5 QPS + 退避；大结果落盘只报路径与行数。

## 5. 纪律

- 这是**持 key 的正规接口**，与复盘会那种页面爬取不是一回事；按他们的节奏（5 QPS、批量走 dump）不会有封号那种事，但「服务可能动态调整限流」——4001 就退避，不并发重放。
- 名字合规不变：个股名只进旁路库 / 分析师侧；带读、产品面照旧不出个股。
- 两套板块体系（同花顺 `.TI` vs 复盘会 `.FP`）按**名字**对，对不上的记缺口，不猜；以后授课框架的板块层以 `.TI` 官方序列为主，复盘会成分为辅。
- 该服务两个月大，字段可能变：接入时把 `docs/api/` 契约版本（commit）写进 sync 模块头，测试用契约里的字段名做断言。
