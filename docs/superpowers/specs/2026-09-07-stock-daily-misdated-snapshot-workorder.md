# 工单 #32 · 个股日线存量缺口：两天整份是次日复制 + 两天 amount 大面积为空

- 优先级：**P1**（小到中单，半天到一天）。数据错位污染一切读 `fact_stock_daily` 的派生：前瞻收益、gain_5d/10d、
  周期阶段训练集、双轨对账。
- 来源：2026-09-07 核心个股一单（PR #647）反推 fupanhui 口径时量出来，质检确诊。本单**只修数与拦截**，不碰核心个股。
- 分支：`fix/stock-daily-misdated-snapshot`。

## 0. 执行状态（2026-09-07 深夜，同一 session 做完）

| 项 | 状态 |
|---|---|
| 修数：四天沪深个股（mootdx）| ✅ 与次日重复 0 行；沪深总额 / `fact_market_daily` = 1.0000 / 0.9999 / 0.9998 / 0.9999；fupanhui 核心 50 只四天全部 50/50 命中，amount 相对差中位 1.3e-5 ~ 2.2e-5、close 逐只相等 |
| 修数：北交所（东财 hist kline）| ⏳ **push2his 全族主机对本机拒连**（白天几版回补打进限流），334 只等解封；轮询 `/tmp/wo32_bj_after_unblock.py`（10 分钟一探、24 小时上限），通了自动回补并重算特征。当前 07-20 / 08-06 / 08-13 零北交所行，06-22 109/316、06-23 0/316 |
| **第五天**：08-13 北交所 335 行 | 新 QA 规则量出来的：写于 08-14 10:50 **盘中**，成交额只有 08-14 终盘的 51%——盘中截面贴了前一日。已备份、删除、纳入回补目标 |
| 拦截 (a)：快照 `f297` 日期闸 | ✅ `SnapshotMisdated` + `--allow-misdated`；测试 7 条，变异（禁掉 raise）转红 2 条 |
| 拦截 (b)：QA 全历史扫描 | ✅ 「相邻日复制」（#647 已加）+ 「快照写入时刻晚于下一交易日开盘」两族，命中判 FAIL；备份回放确认能抓到修前两天 |
| 拦截 (c)：日门禁 | ✅ `check_daily_review_data` 比当日与前一交易日逐股相同 >5% 报缺；真库 07-21 / 09-07 均 0.00% 无误报；测试 4 条 |
| 下游：特征层 | ✅ `technical` / `stock` 两族 06-22 ~ 09-07 全部 56 天重算，0 失败（北交所补进来后轮询会再算一遍） |
| 下游：周期阶段模型 | ✅ **用户拍「换」，产物已替换**：修好的数据上重训 → 特征 μ/σ 漂移 ≤0.11%，LR 权重最大漂移 21.7%，分块 CV 精确 43.7% → 41.6%、粗粒度 55.1% → 53.0%（四天占训练集 1.2% 就让权重动这么多——模型对样本敏感，读数按 ±2pp 抖动看）。训练确定：删 08-13 北交所行前后两次重训只差 0.28%。生产 09-03/04/07 三天用新产物重写，标签不变（下跌阶段 1/2/3 天），置信 0.681/0.631/0.545。SKILL.md / runbook / #644 交接里引用的旧读数已更正 |
| 下游：核心个股复刻 | ✅ QA 命中 99.50% → **99.82%**，剩 37 行全是「没有该股的行」（退市/改名股），空 amount 与「值偏小」两桶归零 |
| runbook 坑⑤ | ✅ 更正：原文声称的 QA 检查从未实现；改写为三层拦截的真实形状，并说明为什么不能按「`updated_at` 日期 ≠ `trade_date`」判（凌晨/周末补前一日的 8 天是对的） |

备份：`~/.finance-runtime/db-repair/fact_stock_daily-wo32-pre-20260907T225843.parquet`（四天 22089 行原样）、
`…-pre-0813bj-20260907T233414.parquet`（08-13 北交所 335 行）。回滚 = 从 parquet upsert 回去。

## 1. 病灶（生产库 `db/market_feature_store.duckdb`，2026-09-07 实测）

### 1a. 2026-07-20 / 2026-08-06：整天是**次日**数据的复制

| 日 | 与次日逐股 close+amount+pct_chg 相同 | 行 `source` | 行 `updated_at` |
|---|---|---|---|
| 2026-07-20 | 5524 / 5526 | `eastmoney:snapshot` | 2026-07-22 00:36（事后补写） |
| 2026-08-06 | 5534 / 5534 | `eastmoney:snapshot` | 2026-08-09 23:05（事后补写） |

旁证：07-20 我们个股成交额合计 29737 亿，对上 `fact_market_daily.total_amount` 07-21 的 29569，不是 07-20 的 27019；
08-06 同型（26830 vs 08-07 的 26642 / 08-06 的 25286）。全历史相邻交易日扫描只有这两对。

成因：`sync_eastmoney_stock_snapshot.sync_fact_stock_daily_snapshot(trade_date=...)` 是「取最新截面、贴所传日期」语义
（模块 docstring 与 `skills/duckdb-backfill/references/backfill-runbook.md` 坑⑤都写了「非交易日/事后调用会把上一交易日写到所传日期」），
**但代码不拦**——事后补历史日时它照写。两次都是补数时用了快路径。

现有防线为什么没抓到：

- `qa_local_vs_fupanhui.py` 的「坏底数据日」按沪深总额与 fupanhui 差 >10% 判，这两天只差 9.1% / 5.8%。
- 同脚本坑⑤的「`eastmoney:snapshot` 且 `updated_at` 日期 ≠ `trade_date` → FAIL」只在被抽到的对账日上跑，默认最近 15 日。
- `check_daily_review_data` 当天跑时这两天还没有行（报缺），补写发生在两天后，没人重跑门禁。

PR #647 已把「相邻日逐股相同 >50%」的全历史扫描加进 `qa_local_vs_fupanhui.py` 并判 FAIL；修好前该脚本对生产库是红的，**这是对的**。

### 1b. 2026-06-22 / 06-23：`amount` 大面积为空

填充率 55.2% / 21.9%（06-24 起 100%；全历史只有这两天低于 95%）。fupanhui 核心个股 57 行因此对不上。成因未查，
mootdx 重抓即可覆盖。

## 2. 要做的事

1. **修数**（四天）：`python3 -m market_feature_store.cli sync-stock-daily --start-date D --end-date D --refresh`
   （mootdx 历史路径；北交所缺口按 runbook 用东财 hist kline 临时脚本）。注意 runbook 坑③：mootdx `pre_close` 是裸前收、
   `stock_name` 带 `\x00`；`turnover` 留 NULL 是来源差异。
2. **验收修数**：
   - 07-20 / 08-06 与次日逐股相同比例回到 ~0；四天 `SUM(amount)` 与 `fact_market_daily.total_amount` 差 <3%；
   - 用 fupanhui `fact_core_stock_daily` 那四天各 50 行当真值：我们的 amount 与它相对差中位 <0.1%（正常日是 0.0035%）；
   - `qa_local_vs_fupanhui.py --start 2026-06-20 --end 2026-08-10` 的 `stock_daily_dup_days` 为空、核心个股复刻三桶归零；
   - 06-22 / 06-23 amount 填充率 ≥98%。
3. **拦截**：`sync_fact_stock_daily_snapshot` 在 `trade_date` 不是**最近一个交易日**时拒写（交易日历用库内 `fact_market_daily`
   或 `fact_stock_daily` 的 max(trade_date) 判；显式 `--allow-misdated` 才放行并把 source 标成 `eastmoney:snapshot-misdated`）。
   写一条测试：传历史日 → 抛；传当日 → 写。
4. **补门禁**：`check_daily_review_data` 的 data 阶段加「当日个股日线与前一交易日逐股相同 >50% → 报缺」；
   或在 `daily-full` 补数路径结束后自动跑一次 `qa_local_vs_fupanhui.py --start D --end D`。二选一，写清理由。
5. **回填下游**：四天修好后重跑受污染的派生——`compute-core-stock-local`（若那四天有 local 行）、
   `scripts/eval_core_leader_authenticity.py`（交接里的读数注明「07-20/08-06 修好后重跑」）、
   #644 周期阶段模型若训练集含这四天则重训并比对权重 JSON 的漂移。

## 3. 不在本单

- fupanhui 侧 07-20 / 08-06 的 amount 与我们的差异方向不一致（有大有小）——两天我们的数据整体是错的，不值得再分析。
- `fact_stock_daily` 其他质量维度（OHLC 缺失、北交所覆盖）另议。

## 4. 验收标准

1. §2.2 四条读数各有一行实测数字写进交接。
2. `tests/` 里有「历史日拒写」测试，且变异（去掉拦截）转红。
3. `qa_local_vs_fupanhui.py` 对生产库全历史 `stock_daily_dup_days == []`。
