# feat/stock-daily-ohlc-and-dual-track

## 这个分支做什么
用户决策（2026-09-07 17:05）：fupanhui 降为「参照源」，能自算的加工字段全部自算。本分支落两件：
1. **双轨切换门** `skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py`：用自己的底数据按公开规则重算 fupanhui 的加工
   字段，逐日比，十个族各一道门。规则是对着 08-14～09-02 十四个干净日实测出来的（见 runbook「自算口径」）：
   沪深总额不含北交所；涨停价沪深四舍五入、**北交所向下取整到分**（40/40）；**ST 不计**（fupanhui 明细 0 只 ST）；
   MA20 含当日；前三行业 = 申万一级份额。十族全部过门：涨家数 92.9%、总额 100%、涨停 100%、跌停 85.7%、量能三项 100%、
   前三行业 100%、板块涨停数 97.9%、涨停明细召回 99.7%、连板 boards 100%、龙头高度 100%。
   只出读数不设门：新高（要 OHLC）、市场强度 top5（定义未知）。脚本会把「底数据坏日」单列剔出统计（发现 08-13 是半日量）。
2. **`fact_stock_daily` 加 open/high/low/volume**：schema.sql 声明 + `ensure_stock_daily_columns` 给老库补列；mootdx 与东财
   快照两条写入器都落（东财 `f17/f15/f16/f5`，"请求了就必须接住"契约测试自动覆盖）；写入改显式列清单（老库 ALTER 追加
   的列序与新建库不同，`SELECT *` 会串位）；`fill_stock_daily_fallback` 的位置插入改显式列。顺手修掉 mootdx 名字
   `\x00` 填充（`clean_name`），docstring 改成实情（默认裸价、除息缺口）。
   CLI `sync-stock-daily` 新增 `--end-date`（单日重写）与 `--ohlc-only`（只填 OHLC，不碰东财行）。
3. `merge_stock_ohlc_shadow.py`：把影子库合进生产（只填 OHLC + 指定日期整行覆盖），默认 dry-run。

## 为什么走影子库
3 年 OHLC 回拉是几十分钟的 mootdx TCP；更要紧的是**第一个新写入器一跑就给生产表加 4 列，而主树还在跑老代码**——
老 `INSERT INTO fact_stock_daily SELECT * FROM _buf_df` 是位置插入，表变 14 列它当场炸，夜跑 stock-daily 步就断。
所以回拉先落 `~/.finance-runtime/stock-ohlc-shadow.duckdb`（`MARKET_FEATURE_STORE_DB` 指过去，零接触生产），
等本 PR 合入、主树更新到含新写入器之后，再跑 merge 一次合入。**合入顺序不能反。**

## 当前状态
- 分支基于 `72d77fda`（#629 已合入 main），干净 worktree `~/fwp-wt-backfill-qa-gate`。
- 门禁读数（干净树，`env -i`）：ruff 绿；pytest **8090 passed / 76 skipped / 1 xfailed**（新增 11 条：`test_stock_daily_ohlc.py` 8、
  `test_qa_local_vs_fupanhui.py` 3）；`build_registry.py check` 一致（沙盒映射后扫）。
- 影子库作业 `/tmp/ohlc_shadow_job.py` 17:42 起在跑（日志 `/tmp/ohlc_shadow_job.log`）：先 08-13 整日重抓（`--end-date` + `--refresh`），
  再 3 年 OHLC 分批 `--limit 400` 续跑。冒烟：3 只 × 730 日，OHLC/volume 齐，NUL 名 0。mootdx 宇宙 5331 只（北交所仍缺 ~190，
  东财 hist kline 收 CLI 是另一单）。

## 验收标准（验收方独立复算）
1. `qa_local_vs_fupanhui.py --start 2026-08-13 --end 2026-09-02` → `RESULT: PASS`，坏底数据日列出 `2026-08-13`。
2. `pytest tests/test_stock_daily_ohlc.py tests/test_qa_local_vs_fupanhui.py` 11 passed。
3. `rg "SELECT \* FROM _buf_df" market_feature_store` 无命中（位置插入已清）。
4. 合入生产后：`SELECT COUNT(high) FROM fact_stock_daily WHERE trade_date >= '2026-06-29'` 接近全A行数；
   `qa_local_vs_fupanhui.py` 的新高段自动切到 `high` 口径（脚本探测列存在且非空 >90%）。

## 合入后的动作（按序）
1. 主树更新到含本 PR（他人在途改动需认领，见 AGENTS.md 开工前必查）。
2. `merge_stock_ohlc_shadow.py --shadow ~/.finance-runtime/stock-ohlc-shadow.duckdb --refresh-dates 2026-08-13`（先 dry-run 看行数）
   → 加 `--apply`。18:30 前或 20:40 后跑，别撞 S7 写锁。
3. 再跑一遍 `qa_local_vs_fupanhui.py`：新高段读数（high 口径）决定要不要给它设门；08-13 不再是坏日。

## 不在本单
北交所历史 K 线 CLI（东财 push2his）；`sync_fupanhui_market_daily` 空响应守卫 + COALESCE；`sync_akshare_sw_l1_daily` realtime 拒写
非当天；市场强度 top5 逆向；名单换源（东财/同花顺）与别名对照；编辑层（周期阶段/主线/keywords/核心个股）低频参照读取。
