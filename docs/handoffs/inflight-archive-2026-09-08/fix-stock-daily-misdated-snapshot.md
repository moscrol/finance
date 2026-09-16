# fix/stock-daily-misdated-snapshot（工单 #32）

叠在 `gitea/main@bf61a6ed`（#647 批次之后）上。

## 这个分支做什么

`fact_stock_daily` 有五天坏数据，成因一个：东财快照只有「最新」语义，事后拿它补历史日会把当时的截面贴到历史日期上，
而这条警告只写在文档里、代码不拦、文档声称的 QA 检查也从未实现。本单修数 + 三层拦截 + 下游重算。
工单正文与执行状态：`docs/superpowers/specs/2026-09-07-stock-daily-misdated-snapshot-workorder.md` §0。

## 五天各是什么病

| 日 | 病 | 修法 |
|---|---|---|
| 06-22 / 06-23 | `fupanhui:sector_stock_daily:fallback` 占位行 close/amount 全空（45% / 78% 的行） | mootdx 重抓覆盖；北交所待补 |
| 07-20 / 08-06 | 整天是次日收盘的复制（写于 07-22 00:36 / 08-09 23:05） | 删掉残留 snapshot 行 + mootdx 重抓；北交所待补 |
| 08-13（本单新发现） | 北交所 335 行是 08-14 10:50 **盘中**截面（成交额 = 终盘 51%） | 删掉；北交所待补 |

## 代码改动

- `sync_eastmoney_stock_snapshot.py`：多请求 `f297`（行情自身交易日），过半日期 ≠ `trade_date` 或认不出 → `SnapshotMisdated` 拒写；
  `allow_misdated=True` 才写且 source 标 `-misdated`。`snapshot_trade_date()` 单独可测。CLI `--allow-misdated`。
- `qa_local_vs_fupanhui.py`：新增 `snapshot_written_after_next_session`（快照行写入时刻 > 下一交易日 09:30 → FAIL）。
  与 #647 加的 `stock_daily_dup_days` 一起构成全历史扫描。
- `check_daily_review_data.py`：`_check_stock_daily_not_copied`，当日与前一交易日逐股 close+amount 相同 >5% 报缺。
- 测试：`tests/test_snapshot_date_gate.py`（7）、`tests/test_stock_daily_copy_gate.py`（4）；两份既有快照测试的假响应补了 `f297`。
- runbook 坑⑤改写。

## 生产库已做的事（不在 PR 里，写这儿）

- 备份两份 parquet 在 `~/.finance-runtime/db-repair/`。
- mootdx 重抓四天（各 ~5190 行）；删除 07-20 / 08-06 残留 snapshot 行（330 / 335）与 08-13 北交所 335 行。
- `technical` / `stock` 特征族 06-22 ~ 09-07 重算两遍（第二遍在删 08-13 北交所行之后）。
- 周期阶段模型在修好的数据上重训（产物在 PR 里），`compute-market-stage-local` 重写 09-03 / 09-04 / 09-07。
- `/tmp/wo32_bj_after_unblock.py` 在跑：等 push2his 解封 → `/tmp/wo32_bj_hist.py` 补五天北交所 → 再重算特征。日志同名 `.log`。

## 验收读数（非北交所部分，2026-09-07 23:20）

- 与次日逐股相同：06-22 0/5295、06-23 0/5186、07-20 0/5196、08-06 0/5199。
- 沪深成交额合计 / `fact_market_daily.total_amount`：1.0000 / 0.9999 / 0.9998 / 0.9999。
- fupanhui 核心个股 50 行真值：四天 50/50 有行且复刻前 50 命中 50/50；amount 相对差中位 1.3e-5 / 1.4e-5 / 2.1e-5 / 2.2e-5，close 逐只相等。
- 填充率：非北交所 99.8% / 99.8% / 100% / 100%；全部（含北交所空位）96.1% / 94.1% / —— / ——。**≥98% 那条要等北交所补完。**
- QA：核心个股复刻 99.82%（剩 37 行全是「没有该股的行」）；`stock_daily_dup_days=[]`；坏底数据日无。
  越门的 `advancers` 0.78 / `sector_limit_up` 0.936 / `leader_height` 0.861 是 6~8 月窗口本来的读数——修数日涨家数差 34~223 只，
  来源是北交所未补（各 ~330 只）+ mootdx 裸前收在分红日的口径差（坑③）；修前这四天差得更多。
- 日门禁真库：07-21 / 09-07 逐股相同 0.00%，无误报。

## 没做 / 待拍

- **北交所五天**等解封（轮询在跑）。若 24 小时不解封，轮询放弃，需换 IP 或等次日再跑 `/tmp/wo32_bj_hist.py`。
- ~~周期阶段模型产物没换~~ → 用户拍「换」：`market_stage_lr_v1.json` 已在修好的数据上重训替换（CV 43.7% → 41.6% / 55.1% → 53.0%，
  权重漂 21.7%），生产 09-03/04/07 三天重写（标签不变，置信 0.681/0.631/0.545）。旧产物留在 `/tmp/wo32_market_stage_old.json`，
  也在 git 历史里（`bec62bdd` 之前）。
- 东财 hist kline 收进 `market_feature_store/sync/` 做正式 CLI（runbook 早有的待办）。
- 06-22 / 06-23 各 8 / 10 只退市股仍是空 close 占位行，那是真没数据。

## 验收标准（工单 §4）

1. §2.2 四条读数：上面「验收读数」节逐条有数；北交所填充率一条待补完后由轮询日志给出。
2. `tests/test_snapshot_date_gate.py`：禁掉 raise 转红 2 条（已做）。
3. `qa_local_vs_fupanhui.py` 对生产库 `stock_daily_dup_days == []` 且 `snapshot_written_after_next_session == []`（后者在删 08-13 后为空）。
