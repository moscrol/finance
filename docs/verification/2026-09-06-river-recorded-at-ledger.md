# 时间长河记录时刻改从快照台账取：可严格重放 1 天 → 16 天

> 日期：2026-09-06
> 分支：`feat/river-recorded-at-ledger`（栈在 `feat/observation-script` 上，再上是 `feat/river-slice-v0`）
> 状态：**未合并、未切 8792**。不改数据、不改同步管线，只改读取面怎么解释已有的列。

## 0. 结论

六轨联立可 `pit_grade=strict` 重放的天数：**1 天 → 16 天**（2026-07-30 ~ 2026-09-02）。
`fact_sector_daily` 自身 1 → 20 天，`fact_sector_stock_daily` 47 → 49 天。
**没有新增任何数据采集**——用的是库里已经躺着的 `ops_sector_universe_snapshot_daily.captured_at`。

## 1. 先纠正一个错判

本线最初的建议是「给 `fact_sector_daily` 加一列 `first_seen_at`，能把可重放长度从 1 天拉到 34 天」。
**两处都错**：

- 加列只对**以后**写入的行诚实，过去 410 天的首次写入时刻已经丢了，新列不会追溯。
- 「34 天」是审计里「**去掉** `fact_sector_daily` 之后其余三轨的交集」，不是「修好它之后」的读数。
  修好它之后的交集受它自己的上限约束，实测是 16 天。

真正的问题不是「值没记」，而是「值记在别处、读取面没去读」。

## 2. 值在哪

`ops_sector_universe_snapshot_daily`（27 行，2026-07-27 ~ 09-02）带 `captured_at`，是那一版板块宇宙的
**真实抓取时刻**，且不随重发布移动。实测它诚实：

- 绝大多数是当日 18:30（launchd 夜跑）；
- 2026-07-27 / 07-28 两天的 `captured_at` 是 **07-30**——补抓，如实记成迟到，没有伪装成当日；
- 2026-08-25 有两版：18:39 `superseded` + 22:27 `published`——供应商换名单那天的取代关系也留着。

对照组：`fact_sector_daily` 里 08-20 与 08-31 两天的 `updated_at` **同为 `2026-09-02 18:39:10.487750`**
——被同一次重发布推平，从时间上再也证明不了这两行当时已存在。

## 3. 规则：两个来源取较早，不是换源

```
recorded_at = LEAST(updated_at, snapshot.captured_at)     -- LEAST 在 DuckDB 里忽略 NULL（实测）
```

两个来源都是「这行在那时已存在」的**合法证据**：

- `updated_at` 是刷新时间，只会**被推晚、不会变早**。所以 `updated_at <= 交易日` 是充分证据（可信）；
  而 `updated_at > 交易日` **不是**「当时不存在」的证据（不可信）。
- `captured_at` 是抓取时刻，同样是存在性证据，且不随重发布移动。

⚠ **不要整轨换成 `captured_at`**：实测资金轨 `fact_sector_stock_daily` 会从 47 天 strict **掉到 20 天**
——台账 07-27 才开始，之前的行都是 `snapshot_id='legacy'`，而它们的 `updated_at` 里有一批是诚实的。
换源不是升级，取较早才是。这条方向已被测试钉死（见 §5）。

## 4. 改了什么

| 文件 | 改动 |
|---|---|
| `intelligence/services/river.py` | 新增 `SECTOR_LEDGER_TABLE` / `sector_recorded_at_sql()` / `sector_ledger_join()` / `_has_table()`；`_market_track` 的板块量价行与 `_capital_track` 的成分股聚合改用该规则取 `recorded_at` |
| `scripts/river_pit_audit.py` | **从 river 导入同一对函数**，不自己另写 SQL |
| `tests/test_river_recorded_at.py` | 新增 8 条 |

聚合对象（`_capital_track`）用 `MAX(逐行取较早)`，不是 `取较早(MAX)`：整份聚合要等最后一条成分股落地
才算可知；反过来会把某一行的早时刻安到整份聚合上，等于宣称聚合比它的成分先存在。

**审计与读取面共用一份 SQL** 是刻意的：两处口径必漂，而漂的时候审计会替河说谎——报出来的 strict 天数
不是河真能给出的那些天。`test_audit_uses_the_same_rule` 钉住这条。

## 5. 验收

真库端到端（`slice_river`）：

| 日子 | 库里 `updated_at` | 河的 `recorded_at` | 整片 `pit_grade` |
|---|---|---|---|
| 2026-08-20 | 2026-09-02 18:39（被推走） | **2026-08-20 22:47**（台账真值） | `strict`（原为 `trade_date_only`） |
| 2026-08-31 | 2026-09-02 18:39 | 2026-09-01 00:22（夜跑滑过午夜） | `trade_date_only`——**照实保留，不粉饰** |

审计重跑：`逐日轨联立可 strict 重放：16 天`（改前 1 天）。

单测 8 条覆盖：脏 `updated_at` 被台账救回、聚合同样救回、**`updated_at` 更早时用它**（方向）、
`legacy` 行回退、老库无台账表不报错、解析结果不晚于任何来源（不变量）、无台账时表达式不含 `snap.`、
审计从 river 取规则。

变异测试：把 `LEAST` 改成 `GREATEST` → **4 条红**（方向是真的被钉住的）。

全量（同一隔离壳）：`4 failed, 7874 passed, 8 skipped, 1 xfailed in 422s`。
通过数 7866 → 7874，**恰好 +8 = 本刀新增的 8 条**；4 条红与本刀前同一组，归因见
`2026-09-06-observation-script-g03.md` §7（三条在基线 `8e3383c8` 复现，一条读的是早于本线的预建 graph.db）。
`ruff check` 两个改动文件：All checks passed。

## 6. 边界

- **384 天仍然拿不回来**：`fact_sector_daily` 里 384 天是 `snapshot_id='legacy'`（台账机制上线前），
  记录时刻确实丢了。不猜、不填、继续走 `trade_date_only`。
- **16 天不是 34 天**：新的卡脖子仍是盘面轨自身的 20 天（台账只有 27 行）。要再长，只能靠台账继续积累，
  或给其余表也找到各自的「上游真时刻」。
- **夜跑滑过午夜的日子会掉出 strict**（08-04 / 08-13 / 08-14 / 08-31 四天）。这不是 bug：当前口径下
  回放的 `knowledge_cutoff <= T 日收盘`，T+1 00:22 写下的行在 T 日收盘时确实还不存在。
  但产品的日常带读其实用的是「T+1 开盘前」这个截止线——**两个截止线是两回事**，
  哪天要给回放放宽到「次日开盘前」，必须显式改口径并单独出读数，不能顺手混用。
- 本刀**不动同步管线、不加列、不回填**。给未来的行补一个只写不改的 `first_seen_at` 仍然值得做，
  但它是另一件事：它让**以后**的每一天都诚实，而本刀是把**已经存在的**证据接上。
