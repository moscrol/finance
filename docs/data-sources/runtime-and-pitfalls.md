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

## 飞书表

| 用途 | 表 | ID |
|---|---|---|
| 每日市场指标 | Bitable 每日指标 | `tbljGvjtl1IC44hb` |
| 板块趋势 | Bitable 板块趋势 | `tblshRMmRnQYrM4K` |
| 连板晋级 | Bitable 连板晋级 | limit-advance skill 管理；写入必须串行（从旧到新），不并行写 |
| 板块每日涨跌幅 + 成交额 | Bitable sector_daily | `tblXqyf9Av1rGg0n` |
| 板块每日边际量 | 电子表格 sector_marginal_sheet | sheet `e8a204`；spreadsheet token 取自 `~/.claude/shared/feishu_config.json`，不写进仓 |

### 飞书的退役边界与凭证（2026-09-11 实测）

「飞书退役了」只对一半，写清楚免得下一个人拿它当死链路：

| 链路 | 状态 | 证据 |
|---|---|---|
| IM 问答入口 `intelligence.cli feishu-bot` | 已退役（exit 2，不读凭证） | `709d0e6e` |
| `sync-market-daily`（飞书「每日指标」表） | 已退役，已从日链拿掉 | `cc5d2e4e`；日志里最后一次「飞书拉取: 159 条」在 2026-08-20 |
| `scripts/notify_feishu.py`（运维告警） | **仍在跑** | 夜跑链 `~/.local/bin/nightly-full-review-s7.sh:75`；`intelligence/workflows/daily_review.py` 与 `scripts/check_db_lock.py` 都 import；2026-09-10 还调过（拿到 token，卡在 `im:chat` 权限 400） |
| `skills/advancers-chart/scripts/feishu_chart.py` | 代码活着，当前链路未调 | `sync_daily_full.py:298` 的 `with_chart` 步；近期 `-advancers-ma5.png` 都是本地 DuckDB 的 `daily-review` 生成的 |
| CLI `sync-limit-advance-feishu` | 仍注册 | `market_feature_store/cli.py:1643` |

**凭证：不要把 token 当密钥，也不要把密钥当已死。**
`tblXxx` / spreadsheet token 是**文档标识符**，单独拿到访问不了；真正的钥匙是
`~/.claude/shared/feishu_config.json` 里的 `app_id`/`app_secret`。这把钥匙曾以明文写在
`skills/advancers-chart/scripts/migrate_dates.py`，`26446460`（2026-07-02）从工作树删除，
**git 历史里仍在且至今未轮换**（2026-09-11 比对：当前配置与历史值逐字相同，
换 tenant_access_token 返回 `code=0`，可枚举「复盘数据」 base 下 8 张表、含自选股）。
删当前副本不解决问题；要么轮换并同步上表三处消费方，要么直接删自建应用并拆掉告警依赖。

Bitable base：`pcnyt9i9lfme.feishu.cn/base/RnRfbT9F1asuFFsQpAyccMmHn2b`。电子表格新日期写到最右侧空列，列排序由用户手动完成，不自动插入或移位。条件格式公式用 `$A1` 引用板块名，每 15 个板块一条 `=OR()` 规则，单条过长会静默失效（汇总见根目录 `条件格式公式.md`）。

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

## 复盘会缺了怎么替（抓住本质，不抄他们的格子）

复盘会是别人的加工结果。同一盘面，篮子划法不同，数字对不上，但问的问题可以自己做。

| 他们有的 | 本质在问什么 | 我们怎么做 | 对得上他们的表吗 |
|---|---|---|---|
| `/data/theme/panels` → `fact_theme_flow_daily` | 这组股票今天钱进了还是出了 | 当日板块成分 `fund_flow_1d` 加总，source=`local:sector-basket:fund_flow_1d`；复盘会面板能抓到仍优先用 | 否（50 来个编辑格子 vs ~400 个板块） |
| 个股/涨停大单 | 主动大单净流入 | L2 日包 → `feature_l2_*` | 从未用他们的 tick |
| 主线、核心股、监管池、龙头高度 | 产品判断（谁是主线、谁该进池） | 仍打复盘会；没有公开盘面公式可还原 | 不能用加总冒充 |
| 板块成分 / 涨停题材成员 | 谁在这个篮子里 | `fact_sector_stock_daily` / `fact_theme_limit_*`（登录同步） | 可以，这是原料不是加工 |
| 竞价异动 | 集合竞价谁在动 | 日包里有集合竞价 csv，尚未接夜跑 | 暂缺 |

质检门仍要求 `fact_theme_flow_daily` 当日有行：复盘会空了就写入篮子加总，门才能过。09-08 那种个股/板块整日空壳，加总也做不出来，还得先把同步段跑绿。
