# #46 历史 stock_name NUL：2026-09-29 预检与受控迁移方案

状态：**已迁移（2026-09-29 23:08:28 CST，候选库发布，见文末「迁移执行记录」）；生产闸已绿。** 以下预检与方案原文保留。原状态：未迁移；生产闸预期为红。 本文件仅是工单实施前的只读基线和隔离演练；不得把测试通过当成生产修复。源码合并、生产库 UPDATE、夜跑窗口均需分别安排。工单：`docs/superpowers/specs/2026-09-11-stock-name-nul-padding-workorder.md`。

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


## 迁移执行记录（2026-09-29 23:08，Claude Code 云端会话 `session_01CBRwJztt4t57Zzr8VMeZZM`）

授权：用户 09-29 约 23:00「这些也是你来推进，按照最优方案」（三项数据遗留之一即本单）。

- **执行方式与本文方案的偏差**：
  - 没有在生产库上直接 UPDATE，走的是候选库路径：`clone_to_staging` → 候选上单事务改写 → 验收 → 守卫换库。守卫包括 run mutex、写者探针、换库锁、身份与版本复查、ops 补差 = 0、换库前备份和原子换名。
  - 本文的 UPDATE 语句原样执行，没有加 `trim`。
- **范围扩到派生表**：重新读数发现 NUL 名字已抄进 10 张派生表。它们的主键都不含名字列，同一条 `replace(stock_name, chr(0), '')` 一并执行。

| 表 | 改写行数 |
|---|---:|
| fact_stock_daily | 298,718 |
| feature_stock_window | 1,118,529 |
| feature_stock_technical_daily | 2,831 |
| fact_sector_stock_daily_generation | 2,830 |
| fact_stock_high_daily | 208 |
| fact_theme_limit_stock_daily | 126 |
| fact_mainline_stock_daily | 14 |
| fact_core_stock_daily | 9 |
| fact_core_leader_daily | 3 |
| fact_limit_advance_daily | 2 |

- 事务内逐表核对：行数不变、非名字列的 `sum(hash(row(...)))` 不变、名字列指纹等于「旧值去 NUL」、NUL = 0；逐代码的不同名字数等于迁移前的 `clean_count`。任何一项不符就 ROLLBACK。
- **`feature_limit_advance_window` 另行处理**：它的主键含 `stock_name`，NUL 把 002403.SZ（爱仕达）、603823.SH（百合花）拆成了「同股同窗两行」，共 61 组。
  - 源表清理后，只对这 2 只股票、在受影响的 17 个 as_of 日内，用 `compute_features._build_limit_advance` 的原公式重算：删 159 行、插 102 行。
  - 表内其余 230,927 行逐字节不变，连 `calculated_at` 也没动。
  - 被否方案：整日重算。那样会把其他股票的窗口行换成用今天源数据重算的值（期间有过回补），等于借修 NUL 改写历史。
- 同一次发布还带了一项：300211.SZ 在 2026-09-29 的名字「*ST亿通」改为「亿通科技」，涉及 4 张表 11 行。依据是当日收盘后封存的腾讯报价和东财现名，两源一致。
- **验收**：
  - 候选库和生产上各跑一遍：`check_daily_review_data 2026-09-29 --plan local` 为 COMPLETE，`check-daily --plan local` 为 PASS；
  - 本 PR 的 `tests/test_stock_name_nul_history.py` 以真库跑，候选库和生产各 3 passed；
  - 整库 69 张表逐表比对，只有上述 11 张不同，行数只有窗口表 −57（即合并掉的分裂行）。
- **收据**：
  - `db/candidate-namefix-0929b/publish-receipt-namefix0929-230828.json`；
  - 换库前备份 `db/market_feature_store.duckdb.bak-20260929T230828-namefix0929-230828`（sha256 前缀 `e0db156c19b5b9f3`）；
  - 构建报告 `db/candidate-namefix-0929b/build-report.json`；
  - 第一次构建用了整日重算，被自检拦下，未发布，报告留在 `db/candidate-namefix-0929.failed-1/`。
- **遗留**：
  - mootdx 名字里带空格或全角字母的 26,558 行不在本单范围；
  - 本 PR 的真库测试在夜跑持写锁时按设计会红，建议不在 18:30–21:00 手动跑。
