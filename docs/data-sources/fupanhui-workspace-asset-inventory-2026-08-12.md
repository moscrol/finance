# 复盘会（fupanhui）数据资产盘点

> 探测日：2026-08-12（站点 `latest_date`）
> 入口页：https://fupanhui.com/workspace/review
> 方法：前端 SPA bundle 逆向 + 公开 API 实测（无登录）
> 结论用途：决定「还能进 DuckDB / 知识库什么」，不是立刻写同步脚本

---

## 0. 怎么盘的（原理 + 选型）

`/workspace/review` 是 **SPA（单页应用）**：HTML 只有一个空 `<div id="root">`，真正的页面和接口合同都在 JS bundle 里。

本次做法：

1. 抓 `https://fupanhui.com/workspace/review` → 得到 `/assets/index-D7RicXfN.js`（约 8.2MB）
2. 定位 axios 实例：`baseURL: "/api/v1/client"`
3. 抽出全部 `nt.get/post/put/delete` 相对路径（约 170 条）
4. 抽出导航 `title/desc/link`（站点功能地图）
5. 对候选 GET 接口直连探测：看 HTTP 状态、是否要 `trade_date`、返回字段形状

**为什么用 bundle 逆向，而不是打开网页点菜单？**

| 方案 | 是什么 | 优点 | 缺点 | 适用 |
|---|---|---|---|---|
| **JS bundle 静态逆向（本次）** | 从打包后的前端代码抽出路由和 API | 不需登录、一次看到全站合同、能发现已下线接口 | 压缩变量难读；看不到鉴权后的字段细节 | 盘点「还有什么」 |
| CDP 登录后看 Network | 浏览器里真实 XHR | 带 token、能看完整 payload | 依赖本机 Chrome；一次只能看到点到的页 | 写同步脚本时核对字段 |
| DOM 抓取 | 解析渲染后的 HTML | 实现简单 | 页面改版即碎；拿不到历史/分页 | 已淘汰（本仓 2026-05 已切 REST） |
| 官方 OpenAPI | 若站点提供 swagger | 最稳 | 复盘会没有公开文档 | 无 |

可迁移点：任何「看起来是网站、其实是 React/Vue SPA」的数据源，都是同一套路——**先找 `baseURL`，再枚举相对路径，再按 200 / 401 / 422 分类**。这和写爬虫前先画 sitemap 是同一思想。

仓内没有独立的 `reverse` skill；本盘点复用的是 `.claude/lessons_learned.md` 里 2026-05-13 那条：「fupanhui 有内部 REST，用 bundle/XHR 替代 DOM」。

---

## 1. 站点功能地图（导航即产品）

从 bundle 抽出的工作台导航。`/workspace/review` 只是「复盘」分组的工作台，同一套 API 还服务题材 / 板块 / 个股 / 研报。

### 复盘

| 页面 | 路径 | 一句话 |
|---|---|---|
| 复盘工作台 | `/workspace/review` | 量能、情绪、结构、行业聚散、周期、冰点 |
| 美股外盘 | `/workspace/review/global-market` | 美股指数 + 海外核心产业链公司 |
| 港股恒生 | `/workspace/review/hk-hang-seng` | 同一套 global-market，过滤 `marketGroup=hk` |
| 市场日历 | `/workspace/review/calendar` | 按月回顾量能/涨跌家/冰点/热点 |
| 每日题材 | `/workspace/review/theme` | 当日主线题材脉络 |
| 题材挖掘 | `/workspace/review/theme-fundamentals` | AI 产业全景报告（产业链/催化/公司） |
| 题材图谱 | `/workspace/review/theme-panorama` | 板块的 recap / 产业链 / 事件 / 关联研报 |
| 监管异动 | `/workspace/review/regulation` | 监管窗口与「安全空间」池 |

### 数据中台

| 页面 | 路径 | 一句话 |
|---|---|---|
| 市场行业 | `/workspace/data/industry` | 行业×日期矩阵（量能/尖锐度/宽度/资金） |
| 板块统计 | `/workspace/data/sector-cycle` | 板块 K 线 + 成分股（已入库） |
| 板块特征 | `/workspace/data/sector-features` | **需登录**，重要节点识别 |
| 龙头梯队 | `/workspace/data/limit` | 连板晋级（已入库）+ 高度趋势图 |
| 竞价统计 | `/workspace/data/auction` | 集合竞价一字/热门板块 |
| 新高汇总 | `/workspace/data/high` | 多周期新高（已入库 counts） |
| 核心个股 | `/workspace/data/core-stocks` | 市场核心 TOP50 |
| 龙虎榜 | `/workspace/data/dragon` | 席位买卖、净额 |
| 热点个股 | `/workspace/data/hot` | 多平台热门关注 |

### 研报 / 新闻

| 页面 | 路径 | 一句话 |
|---|---|---|
| 题材研报 | `/workspace/research` | 复盘会自有研报库（探测日 457 篇） |
| 话题事件 | `/workspace/news/topics` | legacy 热点话题（探测日为空） |
| 热点事件 | `/workspace/news/events` | 事件日历 + 未来事件 + 当日时间线 |

### 不建议当数据资产的

自选 / 盯盘 / 交易计划 / 因子选股 / 策略工厂 / 学院测验 / 盘盘 AI 会话 / 功能投票 —— 这些是**用户私有状态或产品交互**，不是可复用的市场事实。

---

## 2. 我们已经在吃的（不要重复建设）

`daily-full` 已经从复盘会写入 DuckDB 的：

| 接口 | 落点 | 覆盖 |
|---|---|---|
| `/reviews/market` + `/summary` + `/cycle` | `fact_market_daily` | 量能、涨跌家、涨停、行业集中度、周期阶段、冰点、AI 摘要（`note`） |
| `/reviews/sectors/search` + `sector-cycle/*/kline` | `dim_sector` / `fact_sector_daily` | 板块日行情 |
| `sector-cycle/*/stocks` | `fact_sector_stock_daily` | 板块成分股 |
| `/watchlist/limit-distribution` | `fact_theme_limit_heat_daily` | 题材涨停热度（**需登录/CDP**） |
| `/data-high/stocks` + `period-counts` | `fact_stock_high_daily` | 新高个股 |
| `/limit/ladder` | `fact_limit_advance_daily` | 连板晋级 |
| `/topics/mainline-themes` + `mainline-stocks` | `fact_mainline_*_daily` | 主线题材/个股 |
| `/topics/mainline-sectors` | `fact_mainline_sector_daily` | 主线对应板块 |
| `/data/theme/panels` | `fact_theme_flow_daily` | 题材资金面板 |

另外：问答编排会**实时读** `/reviews/global-market`（外盘双源），但**不落库**。
`fact_historical_mapping` **表已建、helper 已写，daily-full 没接**——这是成本最低的缺口。

已下线、不要再接：`/reviews/sector-rotation`、`/reviews/sector-rotation-view`（返回 `code=-1`「板块周期判断已下线」）。

---

## 3. 建议入库的缺口（按价值排序）

分类原则（和 theme-radar 证据层对齐）：

- **DuckDB**：带交易日、可回测、字段稳定的结构化事实（L2/L4 市场信号）
- **知识库**：有论点、产业链、催化、公司映射的文档（L1 产业翻译；硬事实仍要过门）
- **不要进实体正文**：研报二手判断、名单、市占率叙事 → `graph_only` / `report_context`

### P0 — 知识库（theme-radar 最缺的「为什么」）

#### A. 题材挖掘 `/topics/fundamentals`（公开，详情也公开）

探测日 **36 篇**产业全景。详情字段已经是知识库想要的形状：

- `core_judgement`：核心主题 + 验证点 + 判断正文
- `industry_overview`：规模、`chain_segments`（上下游/毛利率/代表公司）、特征矩阵、象限
- `companies[]`：`company_name` / `stock_code` / `chain_segment` / `industry_relation`
- `catalyst_timeline[]`：预期日期、事件、影响、观察指标
- `linked_themes` / `linked_sectors`：直接对上我们的题材/板块代码

样例：`可持续航空燃油（SAF）产业链全景分析报告`（pk=439），含「民航局 SAF 强制加注比例」等可证伪点。

**落点建议**：知识库仓 `wiki/raw/` 源笔记 + `report_contexts`；公司名单默认 `graph_only`；只有公告/订单级才升实体正文。这比我们自己从 PDF OCR 抽产业链便宜一个数量级。

**替代**：继续只靠卖方 PDF ingest。PDF 覆盖面更广、但结构差、证据层要人工守门；fundamentals 是复盘会已经结构化好的「产业翻译」，更适合当 theme-radar 的 L1 骨架。

#### B. 题材研报 `/reports/list`（列表公开，正文 401）

探测日 **457 篇**，近两个月仍在更新（抽样 2026-06-11 ~ 2026-08-12）。列表已带：

- `title` / `report_date` / `sector_tags` / `concept_tags` / `stocks[]`

正文 `/reports/{id}` **要登录**（CDP）。另有公开的 `/reports/stock-logic?stock_codes=`：按股票返回「这篇研报里它的核心逻辑」——适合 `graph_only` 线索，不适合直接写实体页。

**落点建议**：

1. 先把 list 元数据当目录（哪些题材最近被复盘会覆盖）
2. 登录后抓正文，走现有 pdf-ingest / concept-ingest 门（`review_candidate`，不写 `## 边际变化`）
3. `stock-logic` 进 evidence_index，供 theme-radar 排序

这和同花顺问财 `report-search` skill **不是同一源**：问财是全市场卖方检索；这里是复盘会自己生产的、已打好板块/个股标签的库。两者互补。

#### C. 事件日历 `/news/events/*`（公开）

- `/news/events/calendar`：月内每天事件数 + 最高重要性
- `/news/events/timeline?date=`：当日事件（标题/正文/重要性/类型/关联板块）
- `/news/events/future`：未来催化（探测日有中芯国际业绩、油价窗口、光通信大会等）

**落点建议**：知识库「事件/催化」层，或一张很瘦的 `fact_event_daily`（id, date, title, importance, sectors）。晨汇和 foresight 都缺「未来 3 天有什么可对齐的事件」。

`/news/hot/legacy`、`/news/topics/legacy` 探测日为空，先忽略。

---

### P0 — DuckDB（表已在或日更成本低）

| 接口 | 探测形状 | 建议落点 | 为什么现在就该接 |
|---|---|---|---|
| `/reviews/historical-mapping` | 2 个相似日 + 后续 3 日摘要 | **已有** `fact_historical_mapping` | helper 写了但 daily-full 没跑；接上即可服务「像哪一天」 |
| `/reviews/leader-ladder` | 近 5 日板块涨停分布 + **120 日高度趋势** + 窗口对比 | 新表 `fact_leader_height_daily` 或扩 `fact_limit_advance_daily` | 我们有连板个股，没有「今天高度=7、龙头=百花医药」这条市场结构序列 |
| `/reviews/global-market` | 5 个市场指数 + 194 只海外核心股（含业务/研报动作） | `fact_global_index_daily` + 可选 `fact_global_stock_daily` | 编排层每次现拉，无法回测「隔夜纳指 vs 次日主线」 |
| `/reviews/global-market/us-analysis` | 美股主题观察（热度、方向、核心股、大市值异动） | 知识库源笔记 **或** 薄事实表 | 已经是「隔夜主线翻译」，和 A 股题材雷达可对齐 |
| `/data/dragon/list` | 当日 46 只龙虎榜（买卖席位、净额、理由） | `fact_dragon_tiger_daily` | 主力席位是 L4；现有资金流是 L2 逐笔，口径不同、可交叉 |
| `/core-stocks/list` | TOP50（形态 120 日、板块、资金、3/5/10 日涨幅） | `fact_core_stock_daily` | 复盘会的「核心」定义 ≠ 我们涨幅榜；可当策略一的对照宇宙 |
| `/regulation/logs` + `/pool` | 监管事件 5 条；安全池 58 / 等待 14 | `fact_regulation_daily` | 短线交易硬约束；问「能不能碰」现在要临时查网页 |
| `/data/auction/dashboard` | 7 个竞价面板（一字、热门等） | `fact_auction_daily` | 只在盘前有独特信息；日终快照仍值得留作次日对照 |
| `/reviews/sector` | 概念 1/3/5 日涨幅 Top5 + 涨停数 | 可并入现有行业字段或新 `fact_review_concept_rank_daily` | 工作台「行业聚散」的官方 Top，和 `fact_sector_daily` 全量排序互补 |
| `/calendar/month` | 每日涨跌家、量能状态、冰点、top_sectors | 可回填 `fact_market_daily` 历史缺口 | 日历是 market 的月度投影，补洞便宜 |

### P1 — 有价值，但先别进 daily-full

| 接口 | 形状 | 备注 |
|---|---|---|
| `/data/industry/matrix` | 20 行业 × 21 日（volume/sharp/width/fund） | 和 `fact_sw_l1_daily` 部分重叠；若口径是复盘会自有行业，值得单独表 |
| `/reviews/sector-strength` | 12 板块 × 240 个分钟点 | 盘中强度曲线，日终只要 `latest_strength` 即可，别把 240 点全进事实表 |
| `/data/hot-stocks` | 188 只、多平台排名 | 关注度 L4；和核心个股、涨幅榜三重对照才有意义 |
| `/new-high-dashboard/list` | 新高/近新高分面板 | 与已入库 `fact_stock_high_daily` 重叠，先 diff 再决定 |
| `/limit/charts` | 7 日涨停结构/溢价/封单 | 可从 `fact_limit_advance_daily` 自己算；先对账再决定要不要存官方图 |
| `/topics/sector-extras` | recap / chain / events / reports | 题材图谱页的拼装接口；chain+reports 适合知识库，recap 探测日为空 |
| `/topics/sector-barometer` + `sector-stock-ladder` | 单板块气压计、个股梯队 | 按需查询即可，不必日更全市场 |
| `/reviews/global-market/theme-heat` | 29 个海外主题 × 120 日热度 | 大（~700KB/日）；适合单独主题表，不要塞进 market_daily |
| `/data/sector/panels` | 板块资金面板 | 与 theme/panels、sector_daily 三角重叠，先定口径 |

### 明确不要当仓内资产

| 类型 | 例子 | 原因 |
|---|---|---|
| 用户私有 | `/watchlist/*`、`/trading-plans/*`、`/selection/condition/strategies` | 跟登录用户走，不是共享事实 |
| 产品交互 | `/feature-requests`、学院测验、盘盘 session | 不是市场数据 |
| 实时流 | 所有 `*/stream` SSE | 架构是推送不是日终事实；要盯盘另做，不要进 DuckDB |
| 需登录的选股/特征 | `/prime-stocks`、`/sector-features`、`/features/visibility` | 401；即便登录也偏产品功能 |
| 已空/已下线 | news legacy、sector-rotation | 探测日无数据 |

---

## 4. 复盘工作台本身还缺什么

`/workspace/review` 当天实际打的公开接口，对照我们的库：

| 工作台模块 | 接口 | 我们 |
|---|---|---|
| 量能 / 情绪 / 行业聚散 / 强度 | `/reviews/market` | 已入库（情绪分布只取了涨跌停，11 档分布未存） |
| AI 一句话 + 关键词 | `/reviews/summary` | `note` 存了正文，**keywords 未存**（探测日：光纤光缆 等 5 个） |
| 周期阶段 / 冰点理由 | `/reviews/cycle` | 阶段+冰点已入库；`reason_sum` / `cycle_feature` 未存 |
| 概念涨幅榜 | `/reviews/sector` | 未单独存 |
| 历史相似日 | `/reviews/historical-mapping` | 表空 |
| 龙头高度 | `/reviews/leader-ladder` | 未存 |
| 板块分钟强度 | `/reviews/sector-strength` | 未存 |

最小增量（改动面小、复盘当天就能用）：

1. `summary.keywords` → `fact_market_daily` 新列或旁表
2. 接通已有 `fact_historical_mapping`
3. `leader-ladder.height_trend` 日终一行（高度 + 龙头代码）

---

## 5. 推荐落地顺序（等你确认再写代码）

按「先解决问题再优化」：先补**现在问答/复盘会问却要现爬的**，再补锦上添花。

1. **DuckDB 三件套（公开 API，可进 daily-full）**  
   historical-mapping 接通 + leader height 日终一行 + summary.keywords
2. **知识库：fundamentals 36 篇**  
   当 L1 产业骨架，公司默认 graph_only；和 theme-radar 的 `linked_themes` 直接对齐
3. **知识库：reports/list 目录 + 登录后正文**  
   走现有 ingest 门，不另开写入实体的捷径
4. **事件 future/timeline**  
   给晨汇/foresight 做催化日历
5. **global-market 落库**  
   让「隔夜外盘」从现拉变成可回测
6. 龙虎榜 / 监管池 / 核心个股 / 竞价 —— 按你最常问的那条再开

配额提醒：复盘会有周/月调用上限。P0 那几条都是**每个交易日 1 次、payload 小**；不要把 theme-heat 700KB 和 sector-strength 分钟序列塞进同一天的 daily-full。

---

## 6. 探测收据（成立条件）

- 前端 bundle：`/assets/index-D7RicXfN.js`（hash 会随发版变；路径合同以当时 bundle 为准）
- 鉴权分类以 **无 Cookie 直连** 为准：200/`code=0` = 公开；401 = 要登录；422 = 公开但缺 query
- `/reports/{id}` 正文 401，列表 200 —— 「有目录无正文」是当前事实，不是猜的
- 交易日 `2026-08-12`；外盘 `source_trade_date=2026-08-11`（和编排层已有的双源口径一致）
- 未在本机 Chrome 登录，故 **未实测** 需 CDP 的：`/sector-features`、`/prime-stocks`、研报正文、自选流

下次发版后若要复盘这份清单：重新下 bundle，diff `nt.get("/...")` 路径集合即可，不必重读页面。

---

## 7. 落地状态（2026-08-12）

已实现并接入 `daily-full` 一步 `sync-fupanhui-public-assets`（公开 API，不依赖 CDP）：

| 子任务 | 落点 | 备注 |
|---|---|---|
| `summary.keywords` | `fact_market_daily.summary_keywords` | 写在既有 `sync-market-overview` |
| historical-mapping | `fact_historical_mapping` | 接通已有空表 |
| leader-height | `fact_leader_height_daily` | 一次写入 height_trend 全序列 |
| global-market | `fact_global_index_daily` / `fact_global_stock_daily` | 保留 `source_trade_date` |
| dragon | `fact_dragon_tiger_daily` | |
| regulation | `fact_regulation_event_daily` / `fact_regulation_pool_daily` | |
| core-stocks | `fact_core_stock_daily` | 不存 120 日形态数组 |
| auction | `fact_auction_stock_daily` | |
| events | `fact_event_daily` | timeline + future |
| research catalog | `fact_research_report_catalog` | 列表元数据；正文仍 401 |
| fundamentals | `fact_theme_fundamental_doc` + `wiki/raw/fupanhui-fundamentals/` | 需 `KNOWLEDGE_BASE_ROOT`；`graph_only` |

手动入口：`python3 -m market_feature_store.cli sync-fupanhui-public-assets --trade-date YYYY-MM-DD`

未进 `check_daily` 断档表：历史为空，进了会天天误报。正文研报仍要登录后再走 ingest 门。

