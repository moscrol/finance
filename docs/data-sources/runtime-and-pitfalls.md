# 数据源、本地工具链与回填坑

> 从 `CLAUDE.md` 迁出的按需参考（2026-09）。写入契约与退役清单在 `AGENTS.md`「数据契约」；
> schema SSOT 是 `market_feature_store/schema.sql`（`db/schema.sql` 是早期雏形）；库的新鲜度检查见 `docs/learning/current-duckdb-source.md`。

## 数据源

| 源 | 用途 | 接法 |
|---|---|---|
| fupanhui.com | 市场数据、AI 摘要、板块、连板梯队（内部 REST API） | 浏览器内 XHR，经 CDP proxy 携带登录态；有周 / 月调用上限（429），大批量回填分批 |
| iFinD | 个股查询、行业、概念板块 | Node.js `call-node.js`（`skills/ifind`） |
| AKShare | 板块历史涨幅、申万一级 | Python |
| 飞书 Bitable | 连板晋级、强势股等 skill 的写入（复盘数据的 Bitable 写入已废弃） | `~/.claude/shared/feishu_config.json` |
| ClickHouse | Level2 逐笔成交（已退役，夜跑不再打） | 旧 `scan_*.py` 仍能连；凭证走环境变量。2026-08 鉴权挂掉后改闲鱼日包 |
| 百度分享（闲鱼 L2 日包） | 夜跑 L2 正源：按日 `.7z` 逐笔成交 | 分享 URL 在 gitignore 的 `state/l2-baidu-share.json`（每日更新）；本机百度网盘客户端登录后转存 `/L2-inbox`，PCS 分片下载，算完删本地副本。入口 `scripts/moneyflow/run_l2_pipeline.sh` |

## 本地工具链

- DuckDB `db/market_feature_store.duckdb`：列存、零配置、单文件，同一时间只有一个写入连接；起新任务前 `ps aux | grep market_feature_store` 确认旧进程已释放锁。
- CDP proxy `localhost:3456`：`node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs`，需要 Chrome 开 remote debugging（检查 `~/Library/Application Support/Google/Chrome/DevToolsActivePort`）。CDP eval 用 IIFE `(function(){...})()` 包裹并 try/catch，避免页面 JS 异常中断。
- 联网操作统一经 `web-access` skill。
- 日常复盘用默认东财快照（`--stock-source snapshot`）；`--stock-source mootdx` 只用于首次建库或多日历史回填，慢且当日值与快照一致。

## 飞书（2026-09-11 已整体退役）

自建应用连同仓内所有飞书代码于 2026-09-11 删除。**这一节保留是为了回答「那些数据去哪了」，不是操作指南。**

退役理由（先量后删，不是凭印象）：8 张表最后一次写入全部停在 2026-05 ~ 06-18（大成交 05-08、
强势股 05-20、连板晋级 06-03、板块趋势 05-19、板块涨幅成交额 06-03、涨家数走势 06-18、每日指标 06-18），
距退役日已 3 个月无人写；唯一还在跑的 `notify_feishu` 每次都 HTTP 400（缺 `im:chat` 权限），
即告警从未送达。凭证 `app_id/app_secret` 曾明文写进 `migrate_dates.py`，
`26446460`（2026-07-02）只从工作树删、历史里仍在——删应用同时作废了那把钥匙。

退役前已把 8 张表只读导出到 `~/.finance-runtime/feishu-export-20260911/`（板块趋势 1875 行、
每日指标 159、涨家数走势 160、自选股 13、强势股 62、连板晋级 214、大成交 60、板块涨幅成交额 228）。
本地 DuckDB 是超集（例：`fact_market_daily` 404 行 > 飞书「每日指标」159 行），
唯一没有本地副本的是**自选股那 13 只**——它只在飞书里由人手维护，需要时从导出文件取。

原飞书能力的本地去处：

| 原飞书链路 | 现在用什么 |
|---|---|
| 每日指标 / 市场总览 | `daily-full` → `fact_market_daily`；skill `market-overview`（仅飞书写入部分删了） |
| 板块趋势 / 板块涨幅成交额 / 边际量电子表格 | `sync_fupanhui_sector_daily` → `fact_sector_daily`；双红筛选直接查库 |
| 连板晋级 | `sync-fupanhui-limit-advance-daily` → `fact_limit_advance_presence` |
| 涨家数走势图 | `daily-review --chart-output`（本地 PNG，早就是它在出图） |
| 强势股 / 大成交排行 | CLI `interval-gainers` / `weighted-gainers`（本地算，含 UP 偏离列） |
| UP 线与偏离度 | `market_feature_store/query.py` 的 `ma26 + 0.764*std26`，与原 skill 同一公式 |
| 运维告警 | `scripts/notify_ops.py`：`~/.finance-runtime/alerts.log` + 桌面通知 |

### fupanhui 板块抓取的坑（原 sector-data skill 的遗产，与飞书无关）

- CDP eval 里用 `fetch()`（返回 Promise），不要用 `XMLHttpRequest`；长 JS 先落文件再 `curl -d "$(cat /tmp/x.js)"`，省得被 shell 转义咬。
- `sectors/search` 的 `strength` **不是成交额**，amount 只能从 kline API 取。
- 板块 universe 必须以当日 `sectors/search` 返回的 `ts_code` 为准。硬编码列表会漏：历史回填曾因列表里缺 `886063.TI`，让 `PEEK材料` 多个日期空档。

## 字段与口径

- 板块边际量三字段（fupanhui → `fact_sector_daily`）：`diff_ratio`（边际量 %）、`amount`（成交额，亿）、`pct_chg`（涨幅 %）。
- 严格双红（strategy1-matrix 口径）：`pct_chg>0 且 diff_ratio>10 且 amount>500`。
- 周均线 / 偏离度经 hover K 线 tooltip 获取后，用上证日收盘价交叉验证偏离符号。

### 数据边界：这些已经没有数了，别再当指标

- **北向资金净流入：分两阶段停发，现在只剩季度口径。** 2024-05-13 起停盘中实时；
  2024-08-19 起连日终净流入/净流出也停了。每日收盘后只剩成交总额与总笔数、ETF 成交额、
  成交额前十大活跃证券；**净买入改为每季度披露**（不是彻底没有，是季度滞后）。
  本库 schema 里**0 张北向表**，「北向净流入多少」没有任何本地数据可答。
  注意 `intelligence/services/evidence_capabilities.py` 的 `_MARKET_STATE_MARKERS` 收了
  「北向」，问句带这两个字会被判成「需要盘面证据」——那只是路由，不代表查得到，
  下游靠缺口声明兜底。
- **`fact_sector_daily.strength` 与 `fact_sector_daily_generation.strength` 是空壳列。**
  2026-09-11 实测：107,895 行 / 109,361 行**全部为 NULL**。但 strength 这一族没死——
  `fact_mainline_sector_daily.strength` 1,595 行里 1,356 非空、
  `fact_core_leader_daily.kb_strength` 100 行里 58 非空。所以是「这两列死」不是
  「这个字段名死」，按列点名复算：`select count(*), count(strength) from fact_sector_daily`。
- **拥挤度分位的真实回看窗口 < 名义 60 日。** `market_midterm._fetch_theme_trend` 取的是
  「最近 60 **行**」，而 `fact_sector_daily` 同一天同一板块存在重复行（实测「芯片」最近
  60 行只覆盖 47 个不同交易日）。读数仍可用（都是同口径自比），但别把它当成严格 60 日。

## 回填坑

- Kline API `diff_ratio` 偶发全零：fupanhui sector-cycle kline 偶尔对所有板块返回 0。绕法：用相邻交易日 `amount` 手算 `(today_amt - prev_amt) / prev_amt * 100`。
- 板块名称双口径：早期数据用 `.TI` 代码存储，后期用中文名。查询双路查找（中文名 → 代码 → 模糊匹配）。板块 universe 以当日 `sectors/search` 返回的 `ts_code` 为准，不依赖硬编码列表（曾因缺 `886063.TI` 漏填多日）。
- 早期日期（2025 年 10–11 月）只有 212 个板块有数据，后期扩到 227 个；比较覆盖率时先对齐分母。
- 覆盖率审计（`COUNT(*)`）抓不到「行在、值全 NULL」的空壳，重要回填后抽 `price / pct_chg / amount` 非空或做跨日期 diff（`fast_daily_sync.py` 停用的直接原因）。
- 历史回填按每批 4–7 天，抓取可并行、写 DuckDB 串行。

## 只读分析入口

- `python3 scripts/detect_turning_points.py [--from YYYY-MM-DD]`：读 `fact_market_daily` / `fact_sector_daily`，三种触发（大盘放量 >10%、MA5 峰确认、MA5 谷确认），峰谷只在确认日输出、不用未来数据；`scripts/archive/compute_features.py` 仅历史复现。
- `python3 scripts/backtest_sector.py [--scan | --top 5 --hold 3 --min-marginal 8]`：读 `fact_sector_daily` / `fact_market_daily`。
- `render_daily_review_template.py` 是现役日报渲染入口。

## 换源恢复：计算逻辑一致，不要求复刻供应商名单

2026-09-15 用户明确：**复盘会的池子不是权威，允许改用同花顺板块与成员；名单不同不构成失败。**
验收分三层，不再用「是不是编辑产品」一刀切：

1. 输入：目标交易日、单位、复权、窗口和成员版本有依据；不要求与旧源成员集合相同。
2. 计算：成交额求和、边际量、连板、新高等规则分别对账。同一输入应得相同结果；
   换池后结果不同可以成立。等权涨幅与指数加权、两种资金净额定义仍是**算法/字段口径差异**，不能归因于名单。
3. 产物：在新池上用同一阈值生成双红、队列和矩阵；不以与复盘会入选集合一致为硬门。
   跨日名单变化须有记录，不能拿旧池昨额与新池今额混算而不说明。

| 内容 | 现有实现与恢复边界 |
|---|---|
| 板块与成员 | 同花顺目录/K线/当前成员已有独立表。local 的 canonical 复盘表目前仍走 carry/stitch；要换池须接通发布快照与成员投影，不要求先映射 `.FP`。当前成员必须保留真实采集日，不能回标成历史名单。 |
| 板块成交额、边际量、双红 | `sync_local_sector_daily.py` 已有成分聚合；严格双红统一引用 `signals.py`。允许同花顺池，需保证单位、跨日分母和涨幅定义明确。 |
| 核心股、主线、周期 | `compute_local_stats.py` 已有成交额核心股与主线等生产者，不能笼统说不可还原。核心股排名、主线算法与周期算法分开验；已有自算不等于复刻原标签。 |
| 题材资金面板 | 池子可换，但个股资金定义仍须明确。本轮不新增篮子资金兜底；local registry 不认领 `fact_theme_flow_daily`。不能为过门把别种净额写成原面板。 |
| L2 大单与竞价 | L2 日包独立处理；同花顺竞价另有独立表同步器，不把两条线或其完成状态混为一谈。 |

### 分步夜跑接线（本分支代码，未部署）

`build_local_plan` 已列入同花顺个股、板块 K 线、涨跌停池、龙虎榜/热榜/竞价四步，
独立子进程继承 staging 库环境。仍为并跑表，不自动覆盖旧复盘表。
有日期参数的三个端点显式接收目标交易日；个股近十日 dump 无历史日期参数。
local 分步暂不自动抓当前成员；成员抓取与采集日期修复见下节，尚未接入生产切源。

缺 key 记 `skip/no-key`，**不等于已更新**。有 key 执行失败在原位按预算重试，
未恢复则停止下游/导出/换名；不能到末尾只补 dump，让涨停池沿用旧交易日历。
已失败后重试变成缺 key 也不能洗成成功。

步骤的成功仅是执行收据，不是字段完整性/目标日覆盖验收：同花顺原同步器可能接受合法空池或上游空响应；
正式切主源之前还需请求回执、非空关键字段、目标日覆盖与新池计算的隔离库验收。
计划/表归属以 `market_feature_store/consumption_registry.yaml` 为准。
生产仍走现有 staging + 原子换库入口，不直接运行写库子命令。

### 同花顺名单只读验算（本分支代码，未部署）

入口 `python3 -m market_feature_store.cli hithink-sector-preview`，只读由
`MARKET_FEATURE_STORE_DB` 指定的隔离库；要求显式给 `--trade-date`、`--member-date`、
`--category` 和 `--pct-basis`。不调用 provider、不读取密钥、不初始化缺失库，也不发布快照。

- `--pct-basis member_equal_weight`：选定成员当日涨幅的等权均值，保留 canonical 的日涨幅口径。
- `--pct-basis index_close_return`：同花顺指数目标日与前一计划交易日收盘比值的收益。
  **两者不是等价算法**，不得自动互补或把结果差异归因于换池；这两个选项只用于对照，
  正式切源还要按原板块算法确定映射政策。
- 成交额从 canonical `fact_stock_daily.amount`（亿元）求和；边际量用**同一选定名单**
  在相邻交易日的成交额计算，复用 `sync_local_sector_daily.diff_ratio` 与 `signals.is_double_red`。
  这是明示的同篮子比较，不是把新池今额与旧池昨额拼接；也不认证旧供应商全序列等价。
- 默认名单/目录年龄为 0；承接旧名单必须同时指定 `--member-date` 与
  `--max-member-age-days N`（自然日）。前一交易日由统一休市表判定，不能拿「库中最近有行」替代。
- 缺目录、名单计数/时刻不符、任一成员缺日线/关键值、非法数字、错误来源、重复身份或
  指数模式缺相邻 bar 时，`calculation_ready=false`、exit 2；部分可算行仅供诊断，
  不给全池 `double_red_codes`。输入齐全 exit 0 也**只表示本次所选输入可计算**。
  `production_ready` 始终 false，不能拿这个命令当生产质量门或产物恢复证据。

当前成员接口没有历史日期参数。同步器将每个响应的真实上海接收时刻写为 `updated_at`，
日期写为 `captured_at`；K 线的 `end_date` 不再影响名单日期。同一天同板块更新采用
事务内整批替换＋目录计数更新，避免普通 upsert 残留已退出成员；目录标签重复只请求一次。
空/坏/重复成员响应明确失败，不刷新完整快照。跨午夜可产生多个真实采集日，不回标到一个目标日。

边界：目录表仍只有最新单一 category/元数据（标签重叠按既有写入顺序覆盖）；成员表是每日最新批次，
不是盘中多版本历史。计数来自有效响应自身，**不是供应商独立声明的完整分母**，合法但截短的响应仍需
请求级完整性验收。预览会拒绝与当前目录头不符的历史名单；未增加目录/成员请求审计代际。
尚未把 dump 的元/股换算成 canonical 的亿元/手并接入日更投影，也未替换 canonical 板块宇宙。
单日修复器 `repair_hithink_stock_day.py` 有日期特定合同，不能直接当通用日更器使用。
