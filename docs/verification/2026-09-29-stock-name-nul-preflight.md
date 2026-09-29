# #46 历史 stock_name NUL：2026-09-29 预检与受控迁移方案

状态：**未迁移；生产闸预期为红。** 本文件仅是工单实施前的只读基线和隔离演练；不得把测试通过当成生产修复。源码合并、生产库 UPDATE、夜跑窗口均需分别安排。工单：`docs/superpowers/specs/2026-09-11-stock-name-nul-padding-workorder.md`。

## 生产库只读预检（2026-09-29）

在 canonical `/Users/a77/finance-workspace-private/db/market_feature_store.duckdb` 用 DuckDB `read_only=True` 复测：

| 指标 | 结果 |
| --- | ---: |
| 含 `chr(0)` 的行 | 298,718 |
| 日期 | 359 个交易日，2025-01-02～2026-09-04 |
| 股票 | 893 只 |
| 来源 | `mootdx` 298,553；`mootdx+derived:close_ratio` 165 |
| 非尾部嵌入 NUL | 0 |
| `002193.SZ`、`002305.SZ`、`002399.SZ` 各自不同名数 | 原值 2，去 NUL 后 1 |

**未取生产写连接、未改生产库。** 以上计数是预期迁移批次快照，不是无条件永久断言；真正开工时必须重新读数，确认是否有漂移。

隔离演练：从生产只读附着表复制 **298,718 条脏行 + 四只样本的其他行**，共 300,268 行到自动清理的临时 DuckDB；仅在副本执行同一条 `UPDATE`。实测回滚后脏行恢复 298,718；提交后 0，重复执行仍 0；副本逐代码不同名数与迁移前 `replace` 预期完全一致，四只样本在此子集发生去 NUL 名称折叠（三只指定样本均 2→1），其他列的行数与聚合哈希保持不变。副本范围**不是全表**，哈希核对不是生产逐行验收；夹具测试另对所有列做逐行精确对照。

## 提交前条件（未经批准不得执行）

1. 由维护者确定生产写库授权和安静窗口；执行 `MARKET_FEATURE_STORE_DB=<canonical绝对路径> python3 scripts/check_db_lock.py`，确认无夜间任务，保证写锁在 18:30 前释放。`check_db_lock.py` 会短暂申请写连接，故**只在获批迁移窗口**运行，不属于上面的只读预检。
2. 记录生产 DB 路径、执行者、时间、回滚用备份/快照的路径与校验、迁移前行数、NUL 行数、股票名单/名称分裂基线；取得不会被夜跑覆盖的备份。备份不能替代读回值。生产库与 `db/incident-20260928/` 保全件不可互相覆盖。
3. 重新只读预检：

```sql
SELECT count(*) AS nul_rows, count(DISTINCT trade_date) AS days,
       count(DISTINCT stock_ts_code) AS codes,
       min(trade_date) AS first_day, max(trade_date) AS last_day
FROM fact_stock_daily WHERE stock_name LIKE '%' || chr(0) || '%';

SELECT stock_ts_code, count(DISTINCT stock_name) AS raw_count,
       count(DISTINCT replace(stock_name, chr(0), '')) AS clean_count
FROM fact_stock_daily GROUP BY stock_ts_code ORDER BY stock_ts_code;
```

将第二张完整映射存到**仓外**验收记录；其 `raw_count > clean_count` 的子集就是仅因 NUL 分裂的候选。不要把已有合法改名的 `raw_count > 1` 全部当脏数据。另存股票样本 `002193.SZ`、`002305.SZ`、`000100.SZ` 的逐日值，包含来源及日期。

## 迁移（仅在获批、备份和读数复核后）

只执行工单指定的一条 UPDATE，包裹于一条事务；同一写连接、同一事务里检查 NUL 数为 0 后才 `COMMIT`，否则 `ROLLBACK`。**不得加 `trim`、改来源或任何别的列**：

```sql
BEGIN;
UPDATE fact_stock_daily
   SET stock_name = replace(stock_name, chr(0), '')
 WHERE stock_name LIKE '%' || chr(0) || '%';
-- 在同一连接读回：若非 0，执行 ROLLBACK 而不是 COMMIT。
SELECT count(*) FROM fact_stock_daily WHERE stock_name LIKE '%' || chr(0) || '%';
COMMIT;
```

若有异常同连接 `ROLLBACK`；写锁不可带进夜间全量窗口。**不要将上述代码块作为无条件批处理**（人工确认查询结果是 `COMMIT` 前的必要门槛）。隔离库测试已演练失败后回滚、幂等及仅名称受影响，但不代替生产备份。

## 生产验收（独立只读连接）

1. NUL 行数严格等于 0；读取 `002193.SZ`、`002305.SZ`、`000100.SZ` 在 2026-09-03～09-09 的 `trade_date,stock_ts_code,stock_name,source`，与相邻东财行逐值比对，不得截短；`'柳 工'` 中间空格必须保留。
2. 重跑全量逐代码不同名映射：**每只股票后值必须等于迁移前的 `clean_count`**；对照前后 `raw_count > 1` 集合，差集只应是 NUL 引起的分裂，合法改名可仍然 >1。不要宣称所有一码两名都消失。
3. `MARKET_FEATURE_STORE_DB=<canonical绝对路径> /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest tests/test_stock_name_nul_history.py -q`：有真库必须执行（红转绿），无真库 skip 不算生产验收；留存读回 SQL 和命令原始输出及迁移收据。**PR 合并仍由用户统一处理。**
