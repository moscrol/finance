# 工单 #46：`fact_stock_daily.stock_name` 的 `\x00` 历史积压 —— 一码两名

> 单类型：一次性数据迁移（小单，半小时）+ 一道回归闸。
> 主仓：金融。优先级 **P1**（不是事故，但它在静默地劈开同一只票）。

## 0. 一句话

TDX 定长字段的 `\x00` 填充在 2026-09-07 之前被原样写进了 `fact_stock_daily.stock_name`，
**298,718 行**至今带着它；写入侧早已修好，只剩历史积压没人清。

## 1. 读数（2026-09-11 实测，可复跑）

```sql
SELECT count(*), count(DISTINCT trade_date), min(trade_date), max(trade_date)
FROM fact_stock_daily WHERE stock_name LIKE '%' || chr(0) || '%';
```

| 项 | 值 |
|---|---|
| 带 NUL 的行 | **298,718** |
| 涉及交易日 | 359（2025-01-02 … 2026-09-04） |
| 受影响股票 | 893 只 |
| 来源 | `mootdx` 298,553 + `mootdx+derived:close_ratio` 165 |

样例：`'TCL科技\x00'`、`'全新好\x00\x00'`、`'深科技\x00\x00'`、`'柳 工\x00\x00\x00'`
（TDX 定长字段按字节补齐，名字越短补得越多）。

## 2. 危害：一码两名

不是「难看」，是**同一只票在库里有两个名字**：

```
002193.SZ  不同 stock_name 2 个  →  rtrim(chr(0)) 后 1 个
002399.SZ  不同 stock_name 2 个  →  rtrim(chr(0)) 后 1 个
002305.SZ  不同 stock_name 2 个  →  rtrim(chr(0)) 后 1 个
```

任何 `GROUP BY stock_name` / `DISTINCT stock_name` / 按名字关联的路径都会被静默劈成两半。
仓内确有按 `stock_name` 过滤或关联的读者（`intelligence/services/honesty_gates.py`、
`market_moneyflow.py`、`market_feature_store/sync/sync_fupanhui_limit_advance_daily.py`、
`sync_akshare_dragon_seats.py` 等）——它们不会报错，只会少算。

## 3. 写入侧**已经修好了**，别重复修

`market_feature_store/sync/sync_mootdx_stock_daily.py:121-122`：

```python
def _clean_name(name) -> str:
    """TDX 定长字段的 \x00 填充 + 首尾空白。"""
    return str(name or "").replace("\x00", "").strip()
```

模块 docstring 第 12 行也已写明「写入前剥掉（2026-09-07 之前 29.9 万行带 NUL）」——
与本次实测的 298,718 吻合。**所以本单只做历史迁移 + 加闸，不动写入侧。**

## 4. 做什么

### 刀 1｜一次性迁移（单条事务，秒级）

在**干净窗口**（非夜间全量复盘时段）按 `skills/duckdb-backfill` 的规矩先取写锁
（`scripts/check_db_lock.py`），然后：

```sql
BEGIN;
UPDATE fact_stock_daily
   SET stock_name = replace(stock_name, chr(0), '')
 WHERE stock_name LIKE '%' || chr(0) || '%';
COMMIT;
```

验收**读回值、不数行数**：

```sql
-- ① 应为 0
SELECT count(*) FROM fact_stock_daily WHERE stock_name LIKE '%'||chr(0)||'%';
-- ② 抽 3 只，确认名字与相邻日期的东财行一致（不是被截短）
SELECT trade_date, stock_ts_code, stock_name, source
FROM fact_stock_daily WHERE stock_ts_code IN ('002193.SZ','002305.SZ','000100.SZ')
  AND trade_date BETWEEN DATE '2026-09-03' AND DATE '2026-09-09' ORDER BY 1,2;
-- ③ 一码两名应消失
SELECT stock_ts_code, count(DISTINCT stock_name) c FROM fact_stock_daily
GROUP BY 1 HAVING c > 1 ORDER BY c DESC LIMIT 10;
```

③ 迁移前后都要跑：**迁移前的基线可能本来就有合法的一码两名**（改名、ST 摘帽），
所以判据是「差集里不再有仅因 NUL 而分裂的那些」，不是「结果为 0」。

### 刀 2｜回归闸（防止再长回来）

加一条数据质量断言，挂进现有的 `tests/test_db_delta.py` 一类只读检查：
`fact_stock_daily.stock_name` 不得含 `chr(0)`。没有真库时 skip，有库时必红。

## 5. 红线

- 只 `replace(stock_name, chr(0), '')`，**不碰任何别的列**，不改 `source`。
- 迁移必须在单条事务里，失败即整体回滚。
- 写锁不得带进夜间全量复盘窗口。
- 不要顺手「规范化」名字（去空格、繁简、ST 前缀）——那是另一件事，会改变语义。
  `'柳 工'` 中间那个空格是它的真名，只剥尾部 NUL。

## 6. 为什么现在才立单

2026-09-11 补 09-08 缺口时，在 09-08 的 164 行 ifind 数据里撞见同样的 NUL，
就地修掉了那 164 行；顺手一查才发现前面还压着 29.8 万行。当时的判断是
「一次性数据迁移 + 写入侧一行，远超那次回补的范围」，故只记下不动手——本单即那笔记账。
（写入侧后来查明**早已修好**，所以本单比当时预估的更小。）
