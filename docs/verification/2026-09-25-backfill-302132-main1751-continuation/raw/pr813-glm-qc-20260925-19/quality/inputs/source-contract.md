# Precise source excerpts, not conclusions
Full-file hashes and AST-derived line locations bind these excerpts. Unselected helper code is not included.

## market_feature_store/sync/repair_backfill_stock_history.py:1-85 (constants)
```python
"""单股历史回填 + 按股限定（scoped）派生重建——302132.SZ 专用合同。

合同来源（评审 `docs/handoffs/2026-09-14-302132-prep-review.md`，P1-1/P1-2
与「下一轮执行前合同」逐条落码）：

- **发布入口**：只经 `run_daily_full_staged` 父编排（独立 kind、pre_swap_backup=True），
  父流程自建 staging；回填、派生、验收全部在 staging 副本内完成，任何一步失败
  抛异常 → 不发布。**不新增直写 canonical 的通道**（本模块不提供 --child 直写模式）。
- **主表回填**：精确清单 53 INSERT（51 并跑表段 + 2 冻结 parquet 尾段）+
  06-23 空壳 UPDATE；UPDATE 前校验所有拟覆盖值字段全 NULL（不是只看 close）。
- **scoped 派生**：读 / DELETE / INSERT 全部限定 stock × 日期窗 × 两族
  （feature_stock_technical_daily / feature_stock_window）。「预期置缺」=已验输入
  不足（观测数对照市场历），允许 DELETE 后 INSERT 0 行；输入异常 / 源空 / 计算
  错误一律 fail closed。日更 `compute_features` 的非空保护不动。
- **存量处置**（已列入影响清单）：窗内 3 条旧 technical（06-15/16/17，稀疏史
  产物）删除置缺；4 条旧 window（06-25/06-26/07-01/07-07，旧起点）删 key 重建；
  窗外 345 条 technical（2025-01-07..2026-06-12）不动。
- **验收**：钉死集合——窗内 technical 39 行、window 5/10/20/60 = 59/54/44/4
  合计 161 行、精确日期与 start/end、每窗恰 6/11/21/61 观测且与市场历切片相等、
  09-11 四窗钉值；保护切片（他股全部行 + 目标股窗外行，含 calculated_at）前后
  指纹相等；09-11 主表钉值行全列不变。
- **指纹绑定**：每轮执行由 CLI 写出不可覆盖收据（`_guarded_write_json`，O_EXCL +
  与生产/staging/冻结输入及别名隔离），绑定代码 revision/dirty、run_id、spec、
  并跑表源行集 md5、冻结 parquet sha256、备份身份与验收摘要。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .repair_hithink_stock_day import RepairRefused

SOURCE_PARALLEL = "hithink:daily-k:backfill-302132-20260914"
SOURCE_PARQUET = "hithink:daily-k-10d:backfill-302132-20260914"

# ── 钉死的 302132 合同参数（评审确认值）────────────────────────────────
GAP_PARALLEL = (  # 并跑表段 51 日（06-15..09-08 市场历 61 日 − 生产已有 10 日）
    "2026-06-17", "2026-06-24", "2026-06-29", "2026-06-30",
    "2026-07-02", "2026-07-03", "2026-07-06", "2026-07-08", "2026-07-10",
    "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17",
    "2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24",
    "2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31",
    "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07",
    "2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
    "2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21",
    "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
    "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
    "2026-09-07", "2026-09-08",
)
GAP_PARQUET = ("2026-09-09", "2026-09-10")
SHELL_DATE = "2026-06-23"
# 窗内既有、须删除置缺 / 删 key 重建的存量（评审盘点值）
STALE_TECHNICAL_DATES = ("2026-06-15", "2026-06-16", "2026-06-17")
STALE_WINDOW_KEYS = (  # (as_of, start)
    ("2026-06-25", "2026-06-15"), ("2026-06-26", "2026-06-16"),
    ("2026-07-01", "2026-06-18"), ("2026-07-07", "2026-06-22"),
)
PINNED_0911 = {  # 09-11 主表钉值行（updated_at 除外）
    "stock_name": "中航成飞", "close": 63.42, "pre_close": 64.35,
    "pct_chg": -1.45, "amount": 5.9863, "turnover": None,
    "source": "hithink:daily-k-10d", "open": 64.01, "high": 64.66,
    "low": 62.82, "volume": 94471.0,
}
# 09-11 派生钉值（评审独立核验值）
PINNED_TECHNICAL_0911 = {"ma26": 59.8542, "std26": 2.6845,
                         "up_value": 61.9052, "deviation_pct": 2.45}
PINNED_WINDOWS_0911 = (  # (start, gain, avg_amount) 按 period 60/20/10/5
    ("2026-06-18", 6.89, 5.0148), ("2026-08-14", 9.34, 6.198),
    ("2026-08-28", 5.7, 7.9351), ("2026-09-04", 0.19, 6.9264),
)
EXPECTED_TECHNICAL_COUNT = 39
EXPECTED_WINDOW_COUNTS = {5: 59, 10: 54, 20: 44, 60: 4}
PARQUET_SHA256 = (  # 与 prod-repair-report-20260914.json / gate-report.json 记录一致
    "51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17")
_CODE_RE = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")



```

## market_feature_store/sync/repair_backfill_stock_history.py:87-107 (BackfillSpec)
```python
class BackfillSpec:
    """单股历史回填合同。所有期望值钉死；任何一项与实况不符即拒绝。"""

    code: str = "302132.SZ"
    name: str = "中航成飞"
    window_start: str = "2026-06-15"   # 派生重建窗口（含既有 10 旧行日）
    window_end: str = "2026-09-11"     # 含目标日（主表行已存在，仅派生重建）
    main_fill_end: str = "2026-09-10"  # 主表回填到此为止
    shell_date: str = SHELL_DATE
    gap_parallel: tuple[str, ...] = GAP_PARALLEL
    gap_parquet: tuple[str, ...] = GAP_PARQUET
    expected_total_rows: int = 64
    stale_technical_dates: tuple[str, ...] = STALE_TECHNICAL_DATES
    stale_window_keys: tuple[tuple[str, str], ...] = STALE_WINDOW_KEYS
    pinned_0911: dict = field(default_factory=lambda: dict(PINNED_0911))
    pinned_technical_0911: dict = field(default_factory=lambda: dict(PINNED_TECHNICAL_0911))
    pinned_windows_0911: tuple = PINNED_WINDOWS_0911
    expected_technical_count: int = EXPECTED_TECHNICAL_COUNT
    expected_window_counts: dict = field(default_factory=lambda: dict(EXPECTED_WINDOW_COUNTS))
    parquet_sha256: str = PARQUET_SHA256
    spec_version: str = "302132-backfill-2026-09-14-v1"

```

## market_feature_store/sync/repair_backfill_stock_history.py:239-381 (_guard)
```python
def _guard(con, spec: BackfillSpec, parquet_path: Path) -> dict:
    if not _CODE_RE.match(spec.code):
        _fail("非法股票代码", spec.code)
    if not spec.gap_parallel or not spec.gap_parquet:
        _fail("空回填清单拒绝（不得回退全市场）", spec.code)
    if spec.window_start >= spec.window_end or spec.main_fill_end >= spec.window_end:
        _fail("窗口日期序非法", (spec.window_start, spec.main_fill_end, spec.window_end))
    actual_sha = _sha256(parquet_path)
    if actual_sha != spec.parquet_sha256:
        _fail("冻结 parquet 哈希不符", actual_sha)
    cal = {str(r[0]) for r in con.execute(
        "SELECT trade_date FROM fact_market_daily WHERE trade_date BETWEEN ? AND ?",
        [spec.window_start, spec.window_end]).fetchall()}
    for d in (spec.window_start, spec.main_fill_end, spec.window_end):
        if d not in cal:
            _fail("窗口边界不是市场交易日", d)
    prev_day_row = con.execute(
        "SELECT MAX(trade_date) FROM fact_market_daily WHERE trade_date < ?",
        [spec.window_start]).fetchone()
    if not prev_day_row or prev_day_row[0] is None:
        _fail("窗口首日前无市场交易日（pre_close 链无起点）", spec.window_start)
    prev_day = str(prev_day_row[0])
    # 缺口清单实况：恰为 spec（apply）或已应用完毕（verify，重跑幂等）；
    # 部分态 = 异常，fail closed。
    live_parallel = [str(r[0]) for r in con.execute(
        "SELECT h.trade_date FROM fact_stock_daily_hithink h "
        "WHERE h.stock_ts_code=? AND h.adjusted='none' "
        "AND h.trade_date BETWEEN ? AND ? "
        "AND h.trade_date NOT IN (SELECT trade_date FROM fact_stock_daily "
        " WHERE stock_ts_code=?) ORDER BY 1",
        [spec.code, spec.window_start, max(spec.gap_parallel), spec.code]).fetchall()]
    live_pq = [str(r[0]) for r in con.execute(
        "SELECT CAST(to_timestamp(date_ms/1000) AS DATE) FROM read_parquet(?) "
        "WHERE thscode=? AND CAST(to_timestamp(date_ms/1000) AS DATE) BETWEEN ? AND ? "
        "AND CAST(to_timestamp(date_ms/1000) AS DATE) NOT IN "
        "(SELECT trade_date FROM fact_stock_daily WHERE stock_ts_code=?) "
        "AND CAST(to_timestamp(date_ms/1000) AS DATE) > ? ORDER BY 1",
        [str(parquet_path), spec.code, spec.window_start, spec.main_fill_end,
         spec.code, max(spec.gap_parallel)]).fetchall()]
    if tuple(live_parallel) == spec.gap_parallel and tuple(live_pq) == spec.gap_parquet:
        mode = "apply"
    elif not live_parallel and not live_pq:
        applied = con.execute(
            "SELECT COUNT(*) FROM fact_stock_daily WHERE stock_ts_code=? "
            "AND trade_date BETWEEN ? AND ? AND source IN (?, ?)",
            [spec.code, spec.window_start, spec.main_fill_end,
             SOURCE_PARALLEL, SOURCE_PARQUET]).fetchone()[0]
        if applied != len(spec.gap_parallel) + len(spec.gap_parquet) + 1:
            _fail("缺口已闭但回填行数不符（部分态，拒绝）", applied)
        mode = "verify"
    else:
        _fail("缺口实况 ≠ spec 且非已应用态（部分态，拒绝）",
              (len(live_parallel), len(live_pq)))
    # 空壳行：apply 模式要求所有拟覆盖值字段全 NULL；verify 模式由验收 oracle 复核
    shell = con.execute(
        "SELECT open, high, low, close, pre_close, pct_chg, amount, volume "
        "FROM fact_stock_daily WHERE stock_ts_code=? AND trade_date=?",
        [spec.code, spec.shell_date]).fetchone()
    if shell is None:
        _fail("空壳行不存在", spec.shell_date)
    if mode == "apply" and any(v is not None for v in shell):
        _fail("空壳行拟覆盖字段存在非 NULL 值（拒绝臆断整行为空）", shell)
    # 目标日主表钉值行写前快照（写后必须逐列相等）
    pinned_before = con.execute(
        "SELECT stock_name, close, pre_close, pct_chg, amount, turnover, source,"
        " open, high, low, volume FROM fact_stock_daily "
        "WHERE stock_ts_code=? AND trade_date=?",
        [spec.code, spec.window_end]).fetchone()
    if pinned_before is None:
        _fail("目标日主表行不存在", spec.window_end)
    # 回填/填充日不得落在除息事件上（pre_close=昨日 close 语义前提）；
    # 窗口内非回填日的事件（如 06-16 纯现金除息，生产旧行）不在此约束内。
    marks = ",".join(f"'{d}'" for d in (*spec.gap_parallel, *spec.gap_parquet,
                                        spec.shell_date))
    adj = con.execute(
        f"SELECT ex_date FROM fact_stock_adjustment_hithink WHERE stock_ts_code=? "
        f"AND ex_date IN ({marks})",
        [spec.code]).fetchall()
    if adj:
        _fail("回填窗口内存在除权事件，pre_close 口径不覆盖", adj)
    # 存量盘点：apply 模式窗内旧 technical / window 必须恰为 spec 登记集合；
    # verify 模式窗内已是上轮重建结果，由派生验收的精确集合断言兜底。
    if mode == "apply":
        stale_t = tuple(str(r[0]) for r in con.execute(
            "SELECT trade_date FROM feature_stock_technical_daily WHERE stock_ts_code=? "
            "AND trade_date BETWEEN ? AND ? ORDER BY 1",
            [spec.code, spec.window_start, spec.window_end]).fetchall())
        if stale_t != spec.stale_technical_dates:
            _fail("窗内既有 technical ≠ spec 登记的删除清单", stale_t)
        stale_w = tuple((str(r[0]), str(r[1])) for r in con.execute(
            "SELECT as_of_date, start_date FROM feature_stock_window WHERE stock_ts_code=? "
            "AND as_of_date BETWEEN ? AND ? ORDER BY 1, 2",
            [spec.code, spec.window_start, spec.window_end]).fetchall())
        if stale_w != spec.stale_window_keys:
            _fail("窗内既有 window ≠ spec 登记的删 key 清单", stale_w)
    # ── 源依赖完整性（评审 P1-2）：参与 LAG 的源日期集合必须与市场历逐日相等，
    # 缺日/非历日都会让 LAG 前驱错位；逐回填日证明前驱身份；源值有限且必填非空。
    cal_full = [str(r[0]) for r in con.execute(
        "SELECT DISTINCT trade_date FROM fact_market_daily WHERE trade_date BETWEEN ? "
        "AND ? ORDER BY 1", [prev_day, spec.window_end]).fetchall()]
    seg_a_end = max(spec.gap_parallel)
    cal_a = [d for d in cal_full if d <= seg_a_end]
    src_a = {str(r[0]): r[1:] for r in con.execute(
        "SELECT trade_date, open, high, low, close, volume, turnover "
        "FROM fact_stock_daily_hithink WHERE stock_ts_code=? AND adjusted='none' "
        "AND trade_date BETWEEN ? AND ? ORDER BY 1",
        [spec.code, prev_day, seg_a_end]).fetchall()}
    if sorted(src_a) != cal_a:
        _fail("并跑表源日期集合 ≠ 市场历（缺日/多日将使 LAG 前驱错位）",
              {"missing": sorted(set(cal_a) - set(src_a))[:5],
               "extra": sorted(set(src_a) - set(cal_a))[:5]})
    first_b, last_b = min(spec.gap_parquet), max(spec.gap_parquet)
    pred_b = cal_full[cal_full.index(first_b) - 1]
    cal_b = [d for d in cal_full if pred_b <= d <= last_b]
    src_b = {str(r[0]): r[1:] for r in con.execute(
        "SELECT CAST(to_timestamp(date_ms/1000) AS DATE), open_price, high_price, "
        "low_price, close_price, volume, turnover FROM read_parquet(?) "
        "WHERE thscode=? AND currency='CNY' AND interval='1d' AND adjusted='none' "
        "AND CAST(to_timestamp(date_ms/1000) AS DATE) BETWEEN ? AND ? ORDER BY 1",
        [str(parquet_path), spec.code, pred_b, last_b]).fetchall()}
    if sorted(src_b) != cal_b:
        _fail("冻结 parquet 源日期集合 ≠ 市场历（缺日/多日将使 LAG 前驱错位）",
              {"missing": sorted(set(cal_b) - set(src_b))[:5],
               "extra": sorted(set(src_b) - set(cal_b))[:5]})
    write_days = set(spec.gap_parallel) | set(spec.gap_parquet) | {spec.shell_date}
    merged = {**src_a, **src_b}
    for d in sorted(write_days):
        pred = cal_full[cal_full.index(d) - 1]  # 逐日证明：前驱 = 前一市场交易日
        if pred not in merged:
            _fail("回填日的前驱市场日缺源行", (d, pred))
    for label, src in (("并跑表", src_a), ("parquet", src_b)):
        for d, r in src.items():
            if not _finite(r[3]):  # close 全区间必填（pre_close/pct/均线链）
                _fail(f"{label}源行 close 空/非有限", d)
            if d in write_days and not all(_finite(v) for v in r):
                _fail(f"{label}源行必填字段空/非有限（回填日）", (d, r))
    # 目标股未授权修改行（保留行，含 09-11）全列快照（含 updated_at）——写后必须逐列相等
    retained = con.execute(
        f"SELECT * FROM fact_stock_daily WHERE stock_ts_code=? "
        f"AND trade_date NOT IN ({marks}) ORDER BY trade_date",
        [spec.code]).fetchall()
    return {"calendar": cal, "calendar_full": cal_full, "pinned_0911_before": pinned_before,
            "prev_day": prev_day, "mode": mode, "retained_rows": retained}

```

## market_feature_store/sync/repair_backfill_stock_history.py:385-480 (_apply_main)
```python
def _apply_main(con, spec: BackfillSpec, parquet_path: Path, prev_day: str,
                mode: str) -> dict:
    # 并跑表源行（含窗口前一交易日以供首日 pre_close 链）——口径探测 + 源指纹
    con.execute(
        "CREATE OR REPLACE TEMP TABLE bf_src AS "
        "SELECT h.trade_date, h.open, h.high, h.low, h.close, h.volume, h.turnover, "
        "       lag(h.close) OVER (ORDER BY h.trade_date) AS prev_close "
        "FROM fact_stock_daily_hithink h "
        "WHERE h.stock_ts_code=? AND h.trade_date BETWEEN ? AND ? "
        "  AND h.adjusted='none'",
        [spec.code, prev_day, max(spec.gap_parallel)],
    )
    src_rows = con.execute(
        "SELECT trade_date, open, high, low, close, volume, turnover FROM bf_src "
        "ORDER BY trade_date").fetchall()
    src_md5 = hashlib.md5(
        json.dumps([tuple(str(c) for c in r) for r in src_rows]).encode()).hexdigest()
    src_dates = {str(r[0]) for r in src_rows}
    if prev_day not in src_dates:
        _fail("并跑表缺窗口前一交易日（pre_close 链断）", prev_day)
    missing = [d for d in spec.gap_parallel if d not in src_dates]
    if missing:
        _fail("并跑表缺口源行缺失（源空 ≠ 预期置缺，拒绝）", missing)
    # 并跑表段 INSERT：映射表达式与修复模块同构，验收另用 python oracle 独立复核
    con.execute(
        """
        INSERT INTO fact_stock_daily
        SELECT s.trade_date, ?, ?, s.close,
               CAST(CAST(s.prev_close AS DECIMAL(18,2)) AS DOUBLE) AS pre_close,
               CAST(round(CAST((CAST(s.close AS DECIMAL(18,4))
                    / CAST(s.prev_close AS DECIMAL(18,2)) - 1) * 100
                    AS DECIMAL(38,12)), 2) AS DOUBLE) AS pct_chg,
               CAST(round(CAST(s.turnover AS DECIMAL(38,2)) / 100000000, 4) AS DOUBLE)
                    AS amount,
               NULL AS turnover, ?, current_timestamp, s.open, s.high, s.low,
               CAST(round(CAST(s.volume AS DECIMAL(38,0)) / 100, 0) AS DOUBLE) AS volume
        FROM bf_src s
        WHERE s.trade_date BETWEEN ? AND ?
          AND s.trade_date NOT IN (SELECT trade_date FROM fact_stock_daily
                                   WHERE stock_ts_code=?)
        """,
        [spec.code, spec.name, SOURCE_PARALLEL, spec.window_start,
         spec.main_fill_end, spec.code],
    ) if mode == "apply" else None
    # parquet 尾段（09-09/09-10）：pre_close = parquet 内 lag
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE bf_pq AS
        SELECT CAST(to_timestamp(date_ms/1000) AS DATE) AS trade_date,
               open_price AS open, high_price AS high, low_price AS low,
               close_price AS close, volume, turnover,
               lag(close_price) OVER (ORDER BY date_ms) AS prev_close
        FROM read_parquet(?) WHERE thscode=? AND currency='CNY' AND interval='1d'
          AND adjusted='none'
        """,
        [str(parquet_path), spec.code],
    )
    pq_n = con.execute("SELECT COUNT(*) FROM bf_pq").fetchone()[0]
    if pq_n < 3:
        _fail("冻结 parquet 源行不足（源空 ≠ 预期置缺，拒绝）", pq_n)
    con.execute(
        """
        INSERT INTO fact_stock_daily
        SELECT p.trade_date, ?, ?, p.close,
               CAST(CAST(p.prev_close AS DECIMAL(18,2)) AS DOUBLE),
               CAST(round(CAST((CAST(p.close AS DECIMAL(18,4))
                    / CAST(p.prev_close AS DECIMAL(18,2)) - 1) * 100
                    AS DECIMAL(38,12)), 2) AS DOUBLE),
               CAST(round(CAST(p.turnover AS DECIMAL(38,2)) / 100000000, 4) AS DOUBLE),
               NULL, ?, current_timestamp, p.open, p.high, p.low,
               CAST(round(CAST(p.volume AS DECIMAL(38,0)) / 100, 0) AS DOUBLE)
        FROM bf_pq p WHERE p.trade_date BETWEEN ? AND ?
        """,
        [spec.code, spec.name, SOURCE_PARQUET,
         min(spec.gap_parquet), max(spec.gap_parquet)],
    ) if mode == "apply" else None
    # 06-23 空壳填充（护栏已验 8 个值字段全 NULL）
    con.execute(
        """
        UPDATE fact_stock_daily SET
          open = s.open, high = s.high, low = s.low, close = s.close,
          pre_close = CAST(CAST(s.prev_close AS DECIMAL(18,2)) AS DOUBLE),
          pct_chg = CAST(round(CAST((CAST(s.close AS DECIMAL(18,4))
                     / CAST(s.prev_close AS DECIMAL(18,2)) - 1) * 100
                     AS DECIMAL(38,12)), 2) AS DOUBLE),
          amount = CAST(round(CAST(s.turnover AS DECIMAL(38,2)) / 100000000, 4)
                   AS DOUBLE),
          volume = CAST(round(CAST(s.volume AS DECIMAL(38,0)) / 100, 0) AS DOUBLE),
          source = ?, updated_at = current_timestamp
        FROM bf_src s
        WHERE fact_stock_daily.stock_ts_code = ?
          AND fact_stock_daily.trade_date = ? AND s.trade_date = ?
        """,
        [SOURCE_PARALLEL, spec.code, spec.shell_date, spec.shell_date],
    ) if mode == "apply" else None
    return {"parallel_source_md5": src_md5, "mode": mode}

```

## market_feature_store/sync/repair_backfill_stock_history.py:484-589 (_rebuild_derived_scoped)
```python
def _rebuild_derived_scoped(con, spec: BackfillSpec, mode: str = "apply") -> dict:
    code, d0, d1 = spec.code, spec.window_start, spec.window_end
    # 2a. scoped 读 + stage（单股一次算全窗，与 compute_features 同公式）
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE bf_tech AS
        WITH tech AS (
            SELECT trade_date, stock_ts_code, stock_name, close,
                   AVG(close) OVER w AS ma26, STDDEV_POP(close) OVER w AS std26,
                   COUNT(*) OVER w AS wc
            FROM fact_stock_daily
            WHERE stock_ts_code = ? AND trade_date <= ?
            WINDOW w AS (ORDER BY trade_date ROWS BETWEEN 25 PRECEDING AND CURRENT ROW)
        )
        SELECT trade_date, stock_ts_code, stock_name, close,
               ROUND(ma26, 4) AS ma26, ROUND(std26, 4) AS std26,
               ROUND(ma26 + 0.764 * std26, 4) AS up_value,
               ROUND((close / NULLIF(ma26 + 0.764 * std26, 0) - 1) * 100, 2)
                   AS deviation_pct,
               CURRENT_TIMESTAMP AS calculated_at
        FROM tech WHERE trade_date BETWEEN ? AND ? AND wc = 26
        """,
        [code, d1, d0, d1],
    )
    con.execute("CREATE OR REPLACE TEMP TABLE bf_win AS "
                "SELECT * FROM feature_stock_window WHERE FALSE")
    for p in (5, 10, 20, 60):
        con.execute(
            f"""
            INSERT INTO bf_win
            WITH base AS (
                SELECT trade_date, stock_ts_code, stock_name, close, amount,
                       LAG(close, {p}) OVER w AS close_start,
                       LAG(trade_date, {p}) OVER w AS start_date,
                       AVG(amount) OVER w2 AS avg_amt, COUNT(*) OVER w2 AS wc
                FROM fact_stock_daily
                WHERE stock_ts_code = ? AND trade_date <= ?
                WINDOW w AS (ORDER BY trade_date),
                      w2 AS (ORDER BY trade_date
                             ROWS BETWEEN {p - 1} PRECEDING AND CURRENT ROW)
            ),
            gains AS (
                SELECT trade_date AS as_of_date, start_date, trade_date AS end_date,
                       stock_ts_code, stock_name,
                       ROUND((close / NULLIF(close_start, 0) - 1) * 100, 2) AS gain,
                       ROUND(avg_amt, 4) AS avg_amount
                FROM base
                WHERE trade_date BETWEEN ? AND ? AND close_start > 0 AND wc >= {p}
            ),
            sectors AS (
                SELECT trade_date, stock_ts_code,
                       COUNT(DISTINCT sector_name) AS cnt,
                       STRING_AGG(DISTINCT sector_name, ',' ORDER BY sector_name) AS names,
                       STRING_AGG(DISTINCT sw_l1, ',' ORDER BY sw_l1) AS sw1
                FROM fact_sector_stock_daily
                WHERE stock_ts_code = ? AND trade_date BETWEEN ? AND ?
                GROUP BY trade_date, stock_ts_code
            )
            SELECT g.as_of_date, g.start_date, g.end_date, g.stock_ts_code, g.stock_name,
                   g.gain, g.avg_amount, ROUND(g.avg_amount * g.gain / 100, 4),
                   COALESCE(s.cnt, 0), s.names, s.sw1, CURRENT_TIMESTAMP
            FROM gains g
            LEFT JOIN sectors s ON s.stock_ts_code = g.stock_ts_code
                               AND s.trade_date = g.as_of_date
            """,
            [code, d1, d0, d1, code, d0, d1],
        )
    # 2b. 「预期置缺」校验：置缺日必须确实输入不足（观测数对照市场历）
    obs = {str(r[0]): r[1] for r in con.execute(
        "SELECT trade_date, row_number() OVER (ORDER BY trade_date) "
        "FROM fact_stock_daily WHERE stock_ts_code=? AND trade_date BETWEEN ? AND ?",
        [code, d0, d1]).fetchall()}
    tech_dates = {str(r[0]) for r in con.execute("SELECT trade_date FROM bf_tech").fetchall()}
    for d, rn in obs.items():
        expected = rn >= 26
        if (d in tech_dates) != expected:
            _fail("technical 置缺/物化与观测数不符（输入异常或计算错误）",
                  (d, rn, d in tech_dates))
    # 2c. scoped DELETE（同边界）+ INSERT；空 stage 合法（预期置缺已验）
    # verify 模式（重跑幂等）：零写入，只证「既有行 == 新鲜计算」（值列双向 EXCEPT ALL）
    if mode == "verify":
        for stage, table, dcol in (
                ("bf_tech", "feature_stock_technical_daily", "trade_date"),
                ("bf_win", "feature_stock_window", "as_of_date")):
            cols = [r[1] for r in con.execute(
                f"PRAGMA table_info('{table}')").fetchall() if r[1] != "calculated_at"]
            sel = ", ".join(cols)
            scope = f"stock_ts_code='{code}' AND {dcol} BETWEEN '{d0}' AND '{d1}'"
            diff = con.execute(
                f"SELECT COUNT(*) FROM ((SELECT {sel} FROM {stage}) EXCEPT ALL "
                f"(SELECT {sel} FROM {table} WHERE {scope}))").fetchone()[0]
            diff += con.execute(
                f"SELECT COUNT(*) FROM ((SELECT {sel} FROM {table} WHERE {scope}) "
                f"EXCEPT ALL (SELECT {sel} FROM {stage}))").fetchone()[0]
            if diff:
                _fail(f"verify 模式：{table} 既有行 ≠ 新鲜计算（值列）", diff)
        return {"technical_staged": len(tech_dates)}
    con.execute(
        "DELETE FROM feature_stock_technical_daily WHERE stock_ts_code=? "
        "AND trade_date BETWEEN ? AND ?", [code, d0, d1])
    con.execute("INSERT INTO feature_stock_technical_daily SELECT * FROM bf_tech")
    con.execute(
        "DELETE FROM feature_stock_window WHERE stock_ts_code=? "
        "AND as_of_date BETWEEN ? AND ?", [code, d0, d1])
    con.execute("INSERT INTO feature_stock_window SELECT * FROM bf_win")
    return {"technical_staged": len(tech_dates)}

```

## market_feature_store/sync/repair_backfill_stock_history.py:593-722 (_accept)
```python
def _accept(con, spec: BackfillSpec, pre: dict) -> dict:
    code, d0, d1 = spec.code, spec.window_start, spec.window_end
    # 3a. 主表：64 日精确集合 + 54 行验收（分母 = spec 精确键集，不按输出 source 筛）
    dates = [str(r[0]) for r in con.execute(
        "SELECT trade_date FROM fact_stock_daily WHERE stock_ts_code=? "
        "AND trade_date BETWEEN ? AND ? ORDER BY 1", [code, d0, d1]).fetchall()]
    if len(dates) != spec.expected_total_rows or set(dates) != pre["calendar"]:
        _fail("回填后窗口日期集合 ≠ 市场历", (len(dates), len(pre["calendar"])))
    write_keys = list(spec.gap_parallel) + list(spec.gap_parquet) + [spec.shell_date]
    marks = ",".join(f"'{d}'" for d in write_keys)
    rows = con.execute(
        f"SELECT trade_date, stock_name, open, high, low, close, pre_close, pct_chg,"
        f" amount, turnover, volume, source FROM fact_stock_daily "
        f"WHERE stock_ts_code=? AND trade_date IN ({marks})", [code]).fetchall()
    if len(rows) != len(write_keys):
        _fail("回填键集行数 ≠ spec（验收分母必须来自授权键集）",
              (len(rows), len(write_keys)))
    src_a = {str(r[0]): r[1:] for r in con.execute(
        "SELECT trade_date, open, high, low, close, volume, turnover FROM bf_src").fetchall()}
    src_b = {str(r[0]): r[1:] for r in con.execute(
        "SELECT trade_date, open, high, low, close, volume, turnover FROM bf_pq").fetchall()}
    merged = {**src_a, **src_b}
    cal_full = pre["calendar_full"]
    expected_label = ({d: SOURCE_PARALLEL for d in spec.gap_parallel}
                      | {spec.shell_date: SOURCE_PARALLEL}
                      | {d: SOURCE_PARQUET for d in spec.gap_parquet})
    bad = []
    for r in rows:
        d = str(r[0])
        src = src_b.get(d) if d in spec.gap_parquet else src_a.get(d)
        if src is None:
            bad.append((d, "源行缺失"))
            continue
        pred = cal_full[cal_full.index(d) - 1]  # oracle 前驱 = 市场历前一日（护栏已证身份）
        pred_close = merged[pred][3]
        exp_pre = float(Decimal(str(pred_close)).quantize(Decimal("0.01")))
        exp_pct = _oracle_pct(r[5], exp_pre)
        exp_amt = _oracle_amount(src[5])
        exp_vol = _oracle_volume(src[4])
        ok = (r[1] == spec.name and r[2] == float(src[0]) and r[3] == float(src[1])
              and r[4] == float(src[2]) and r[5] == float(src[3])
              and r[6] is not None and abs(r[6] - exp_pre) <= 1e-9
              and r[7] is not None and abs(r[7] - exp_pct) <= 1e-9
              and r[8] is not None and abs(r[8] - exp_amt) <= 1e-9
              and r[9] is None and r[10] is not None and abs(r[10] - exp_vol) <= 1e-9
              and r[11] == expected_label[d]
              and all(_finite(v) for v in (r[2], r[3], r[4], r[5])))
        if not ok:
            bad.append((d, tuple(r[1:]), tuple(src)))
    if bad:
        _fail("回填行全字段验收 ≠ 独立 oracle（含 OHLC/昨收/来源标签）", bad[:3])
    # 副查：带回填标签的总行数恰为 54（标签错标/漏标都会破坏守恒）
    labeled = con.execute(
        "SELECT COUNT(*) FROM fact_stock_daily WHERE stock_ts_code=? "
        "AND source IN (?, ?)", [code, SOURCE_PARALLEL, SOURCE_PARQUET]).fetchone()[0]
    if labeled != len(write_keys):
        _fail("回填标签行数 ≠ 键集（来源标签守恒破坏）", labeled)
    # 目标股未授权修改行（含 09-11，全列含 updated_at）必须与写前快照逐列相等
    retained_after = con.execute(
        f"SELECT * FROM fact_stock_daily WHERE stock_ts_code=? "
        f"AND trade_date NOT IN ({marks}) ORDER BY trade_date", [code]).fetchall()
    if retained_after != pre["retained_rows"]:
        _fail("目标股保留行（含 09-11 updated_at）被改动",
              (len(pre["retained_rows"]), len(retained_after)))
    # 3b. 09-11 钉值行逐列不变
    pinned_after = con.execute(
        "SELECT stock_name, close, pre_close, pct_chg, amount, turnover, source,"
        " open, high, low, volume FROM fact_stock_daily "
        "WHERE stock_ts_code=? AND trade_date=?", [code, d1]).fetchone()
    if pinned_after != pre["pinned_0911_before"]:
        _fail("09-11 钉值行被改动", (pre["pinned_0911_before"], pinned_after))
    spec_pinned = spec.pinned_0911
    if tuple(spec_pinned[k] for k in (
            "stock_name", "close", "pre_close", "pct_chg", "amount", "turnover",
            "source", "open", "high", "low", "volume")) != pinned_after:
        _fail("09-11 钉值行 ≠ spec 钉值", pinned_after)
    # 3c. 派生精确集合
    tech = con.execute(
        "SELECT trade_date, ma26, std26, up_value, deviation_pct "
        "FROM feature_stock_technical_daily WHERE stock_ts_code=? "
        "AND trade_date BETWEEN ? AND ? ORDER BY 1", [code, d0, d1]).fetchall()
    if len(tech) != spec.expected_technical_count:
        _fail("technical 行数 ≠ 钉值", (len(tech), spec.expected_technical_count))
    for d in spec.stale_technical_dates:
        if any(str(r[0]) == d for r in tech):
            _fail("应置缺旧 technical 行残留", d)
    win = con.execute(
        "SELECT as_of_date, start_date, end_date, interval_gain_pct, avg_amount "
        "FROM feature_stock_window WHERE stock_ts_code=? "
        "AND as_of_date BETWEEN ? AND ? ORDER BY 1, 2", [code, d0, d1]).fetchall()
    for key in spec.stale_window_keys:
        if any((str(r[0]), str(r[1])) == key for r in win):
            _fail("应删旧 window key 残留", key)
    # 黄金三元组（评审 P2-2）：按市场历索引构造全部合法 (as_of, start, end)，双向集合相等；
    # start 必须是市场日、跨度必须恰为 p+1 观测，由构造保证，不靠计数推断。
    cal_sorted = sorted(pre["calendar"])
    golden = set()
    for i, a in enumerate(cal_sorted):
        for p in (5, 10, 20, 60):
            if i >= p:  # 观测数 i+1 >= p+1
                golden.add((a, cal_sorted[i - p], a))
    actual = {(str(r[0]), str(r[1]), str(r[2])) for r in win}
    if len(actual) != len(win) or actual != golden:
        _fail("window (as_of,start,end) 集合 ≠ 市场历黄金三元组",
              {"only_actual": sorted(actual - golden)[:3],
               "only_golden": sorted(golden - actual)[:3]})
    idx = {d: i for i, d in enumerate(cal_sorted)}
    counts = {5: 0, 10: 0, 20: 0, 60: 0}
    for a, s, _e in actual:
        counts[idx[a] - idx[s]] += 1
    if counts != spec.expected_window_counts:
        _fail("window 各期计数 ≠ 钉值", (counts, spec.expected_window_counts))
    # 3d. 09-11 派生钉值
    t9 = [r for r in tech if str(r[0]) == d1]
    if len(t9) != 1:
        _fail("09-11 technical 未物化", t9)
    tp = spec.pinned_technical_0911
    if (abs(t9[0][1] - tp["ma26"]) > 1e-9 or abs(t9[0][2] - tp["std26"]) > 1e-9
            or abs(t9[0][3] - tp["up_value"]) > 1e-9
            or abs(t9[0][4] - tp["deviation_pct"]) > 1e-9):
        _fail("09-11 technical ≠ 钉值", t9[0])
    w9 = sorted([r for r in win if str(r[0]) == d1], key=lambda r: str(r[1]))
    got = tuple((str(r[1]), r[3], r[4]) for r in w9)
    if len(got) != len(spec.pinned_windows_0911):
        _fail("目标日 window 窗数 ≠ spec 钉值（缺窗/多窗都拒绝）", got)
    for g, p in zip(got, spec.pinned_windows_0911):
        if g[0] != p[0] or abs(g[1] - p[1]) > 1e-9 or abs(g[2] - p[2]) > 1e-9:
            _fail("09-11 window ≠ 钉值", (g, p))
    return {"technical_rows": len(tech), "window_rows": len(win),
            "window_counts": counts}

```

## market_feature_store/sync/repair_backfill_stock_history.py:725-776 (run_backfill_child)
```python
def run_backfill_child(con, spec: BackfillSpec, parquet_path: Path) -> dict:
    """在父流程 staging 副本内执行：护栏 → 主表 → scoped 派生 → 验收。

    任何一步失败抛 RepairRefused（或底层异常），父流程不发布。
    """
    pre = _guard(con, spec, parquet_path)
    # 保护切片指纹（写前）：他股全量 + 目标股窗外行，含 calculated_at
    fp_before = {
        "fact_other": _slice_fingerprint(
            con, "fact_stock_daily", "trade_date",
            f"stock_ts_code <> '{spec.code}'"),
        "tech_protected": _slice_fingerprint(
            con, "feature_stock_technical_daily", "trade_date",
            f"stock_ts_code <> '{spec.code}' OR trade_date NOT BETWEEN "
            f"'{spec.window_start}' AND '{spec.window_end}'"),
        "win_protected": _slice_fingerprint(
            con, "feature_stock_window", "as_of_date",
            f"stock_ts_code <> '{spec.code}' OR as_of_date NOT BETWEEN "
            f"'{spec.window_start}' AND '{spec.window_end}'"),
    }
    facts = _apply_main(con, spec, parquet_path, pre["prev_day"], pre["mode"])
    derived = _rebuild_derived_scoped(con, spec, pre["mode"])
    accepted = _accept(con, spec, pre)
    accepted.update(derived)
    fp_after = {
        "fact_other": _slice_fingerprint(
            con, "fact_stock_daily", "trade_date",
            f"stock_ts_code <> '{spec.code}'"),
        "tech_protected": _slice_fingerprint(
            con, "feature_stock_technical_daily", "trade_date",
            f"stock_ts_code <> '{spec.code}' OR trade_date NOT BETWEEN "
                  f"'{spec.window_start}' AND '{spec.window_end}'"),
        "win_protected": _slice_fingerprint(
            con, "feature_stock_window", "as_of_date",
            f"stock_ts_code <> '{spec.code}' OR as_of_date NOT BETWEEN "
                  f"'{spec.window_start}' AND '{spec.window_end}'"),
    }
    for k in fp_before:
        if fp_before[k] != fp_after[k]:
            _fail(f"保护切片被改动（{k}，含 calculated_at）",
                  (len(fp_before[k]), len(fp_after[k])))
    revision, dirty = _code_revision()
    return {
        "spec_version": spec.spec_version,
        "code": spec.code,
        "parquet_sha256": spec.parquet_sha256,
        "code_revision": revision,
        "code_dirty": dirty,
        "interpreter": sys.executable,
        **facts, **accepted,
        "protected_slices": {k: len(v) for k, v in fp_after.items()},
    }

```

## market_feature_store/sync/repair_backfill_stock_history.py:117-129 (_code_revision)
```python
def _code_revision() -> tuple[str, bool]:
    """运行代码的 git revision 与 dirty 标志；解析不出即拒绝（收据不许无绑定）。"""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(PROJECT_DIR),
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(PROJECT_DIR),
            capture_output=True, text=True, check=True).stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise RepairRefused(f"代码 revision 绑定失败（非 git 检出或 git 不可用）: {exc}")
    if not head:
        raise RepairRefused("代码 revision 绑定失败: HEAD 为空")
    return head, dirty

```

## market_feature_store/sync/repair_backfill_stock_history.py:152-183 (_guarded_write_json)
```python
def _guarded_write_json(path: Path, payload: dict,
                        protected: set[Path] | frozenset | None = None) -> Path:
    """收据/报告的唯一写出通道：O_EXCL 不可覆盖 + 别名隔离 + 全阶段 fail-closed。

    半成品清理严格限于「本轮 os.open 成功创建、且清理时 (st_dev, st_ino) 仍是
    同一个 inode」的文件——EEXIST 竞争失败或未取得所有权时绝不 unlink。
    """
    p = _validate_receipt_path(path, protected)
    fd = None
    created: tuple[int, int] | None = None
    try:
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        st = os.fstat(fd)
        created = (st.st_dev, st.st_ino)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = None  # 所有权移交 fh；异常时由 with 负责关闭
            fh.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str)
                     + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        if created is not None:
            try:  # 仅清理本轮自己创建且仍是同一 inode 的文件
                cur = p.lstat()
                if (cur.st_dev, cur.st_ino) == created:
                    p.unlink()
            except OSError:
                pass
        _fail("收据写出失败", f"{type(exc).__name__}: {exc}")
    return p

```

## market_feature_store/cli.py:1561-1742 (cmd_repair_backfill_302132)
```python
def cmd_repair_backfill_302132(args) -> int:
    """302132.SZ 历史回填父命令：staging 回填 + scoped 派生重建 + 验收 + 原子换库。

    合同 `docs/handoffs/2026-09-14-302132-prep-review.md`（P1-1/P1-2/执行前合同）：
    复用 run_daily_full_staged 的锁/克隆/第三方守卫/同轮状态/备份/原子发布；
    独立 kind=repair-backfill-302132；pre_swap_backup=True；回填、scoped 派生与
    验收全部在父流程创建的 staging 副本内完成，失败不发布。普通 daily-full 会
    重新克隆并跑全管道，不能用来发布已验 staging（评审退回草案第六节的根因）。
    --child 是 staging 子进程模式：写 MARKET_FEATURE_STORE_DB（或 --db）指向的
    副本，直写 canonical 生产库被 write_path 闸门拦死——不新增直写 canonical
    的通道。
    """
    from .sync.repair_backfill_stock_history import BackfillSpec, run_backfill_child
    from .sync.repair_hithink_stock_day import RepairRefused
    from .sync.sync_daily_full import run_daily_full_staged

    if args.db is not None and not args.child:
        print("--db 仅供内部 --child 使用；父命令目标由 MARKET_FEATURE_STORE_DB 解析，拒绝忽略显式目标。")
        return 2

    parquet = Path(args.parquet)
    if not parquet.exists():
        print(f"parquet 不存在: {parquet}")
        return 2
    spec = BackfillSpec()

    if args.child:
        # 目标解析与 run_repair 同一顺序：--db > MARKET_FEATURE_STORE_DB > 包默认。
        env_db = os.environ.get("MARKET_FEATURE_STORE_DB")
        target = Path(args.db or env_db) if (args.db or env_db) else None
        if target is None:
            print("--child 需要 --db 或 MARKET_FEATURE_STORE_DB（收据必须有主）")
            return 2
        refused = _refuse_production_write_direct(target)
        if refused is not None:
            return refused
        import duckdb

        status_json = Path(str(target) + ".status.json")
        try:
            con = duckdb.connect(str(target))
            try:
                report = run_backfill_child(con, spec, parquet)
            finally:
                con.close()
        except RepairRefused as exc:
            print(f"回填护栏/验收不通过，未发布: {exc}")
            return 2
        from datetime import datetime, timezone

        from .sync.repair_backfill_stock_history import _guarded_write_json
        from .write_path import canonical_production_candidates

        run_id = (os.environ.get("MARKET_FEATURE_STORE_RUN_ID")
                  or "norun-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                  + f"-{os.getpid()}")
        report["run_id"] = run_id
        report["trade_date"] = spec.window_end
        report["kind"] = "repair-backfill-302132"
        report["ok"] = True
        protected = {target, parquet, *canonical_production_candidates()}
        report_path = (
            Path(args.report_path)
            if args.report_path
            else Path(str(target) + f".backfill-report.{run_id}.json")
        )
        try:
            _guarded_write_json(report_path, report, protected)
        except RepairRefused as exc:
            print(f"报告路径护栏不通过，未发布: {exc}")
            return 2
        status_json.write_text(
            json.dumps({
                "trade_date": spec.window_end,
                "ok": True,
                "run_id": run_id,
                "steps": [{"name": "repair-backfill-302132", "ok": True,
                           "technical_rows": report["technical_rows"],
                           "window_rows": report["window_rows"]}],
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            f"回填完成: {report['code']} 窗内 {report['technical_rows']} technical / "
            f"{report['window_rows']} window，保护切片指纹不变，报告 {report_path}"
        )
        return 0

    child_argv = [
        sys.executable, "-m", "market_feature_store.cli",
        "repair-backfill-302132", "--child",
        "--parquet", str(parquet),
    ]
    if args.report_path:
        child_argv += ["--report-path", args.report_path]
    # 换库前预校验本轮收据可写（评审：收据在换库后才发现不可写 = 数据已发布、
    # 证据缺失的窗口）。两条铁律：用户传入路径只纯校验（不创建、不删除——绝不
    # 触碰用户已有文件）；可写性探针用独立 pid 命名，且仅本轮成功创建才删除。
    from .sync.repair_backfill_stock_history import (
        _code_revision, _guarded_write_json, _validate_receipt_path)
    from .write_path import canonical_production_candidates

    env_db = os.environ.get("MARKET_FEATURE_STORE_DB")
    from . import db as _dbmod_pre
    pre_target = Path(env_db) if env_db else _dbmod_pre.DB_PATH
    protected = {pre_target, parquet, *canonical_production_candidates()}
    if args.report_path:
        try:
            _validate_receipt_path(Path(args.report_path), protected)
        except RepairRefused as exc:
            print(f"报告路径预校验不通过（换库前拦截）: {exc}")
            return 2
    probe = Path(str(pre_target)
                 + f".repair-backfill-execution.probe-{os.getpid()}.json")
    probe_created = False
    try:
        _guarded_write_json(probe, {"probe": True}, protected)
        probe_created = True
    except RepairRefused as exc:
        print(f"执行收据路径预校验不通过（换库前拦截）: {exc}")
        return 2
    finally:
        if probe_created:  # 只清理本轮自己成功创建的探针
            probe.unlink(missing_ok=True)
    result = run_daily_full_staged(
        trade_date=spec.window_end,
        child_argv=child_argv,
        kind="repair-backfill-302132",
        pre_swap_backup=True,
    )
    if result["swapped"]:
        print(f"回填状态: {'OK' if result['rc'] == 0 else 'CHECK'} | 已原子换库")
        if result.get("backup"):
            print(
                f"换库前备份: {result['backup']['backup_path']} "
                f"(sha256={result['backup']['backup_sha256'][:16]}…, "
                "恢复步骤见同级 .receipt.json)"
            )
        # 每轮不可覆盖执行收据（评审 P2-3）：绑定 revision/dirty、run_id、spec、
        # 两源指纹、备份身份与验收摘要。
        from dataclasses import asdict

        from . import db as _dbmod

        run_id = result.get("run_id")
        target = pre_target if pre_target is not None else _dbmod.DB_PATH
        child_report, child_err = None, None
        cand = (Path(args.report_path) if args.report_path else (
            Path(str(_dbmod.staging_path(target))
                 + f".backfill-report.{run_id}.json") if run_id else None))
        if cand is not None:
            try:
                child_report = json.loads(cand.read_text(encoding="utf-8"))
            except OSError as exc:
                child_err = f"{type(exc).__name__}: {exc}"
        revision, dirty = _code_revision()
        receipt = {
            "kind": "repair-backfill-302132",
            "trade_date": spec.window_end,
            "run_id": run_id,
            "code_revision": revision,
            "code_dirty": dirty,
            "interpreter": sys.executable,
            "spec": asdict(spec),
            "child_report_path": str(cand) if cand else None,
            "child_report": child_report,
            "child_report_error": child_err,
            "backup": result.get("backup"),
            "parent": {"swapped": result["swapped"], "rc": result["rc"],
                       "run_id": run_id},
        }
        try:
            receipt_path = _guarded_write_json(
                Path(str(target) + f".repair-backfill-execution.{run_id}.json"),
                receipt, {target, parquet, *canonical_production_candidates()})
        except RepairRefused as exc:
            print(f"执行收据写出失败（数据已换库；子报告与 ops 台账仍在）: {exc}")
            return 2
        print(f"执行收据: {receipt_path}")
    else:
        print(f"回填状态: BLOCKED | 生产库未动 | {result['reason']}")
    return result["rc"]

```

## scripts/verify_302132_backfill_acceptance.py:540-728 (_data_checks)
```python
def _data_checks(check, prod: Path, clone: Path, pq: Path,
                 spec: dict, receipts: dict) -> None:
    """数据合同。入口前结构已过深 schema，所有嵌套访问安全。

    oracle 输入纪律（六轮 P1-1）：并跑源行与源指纹一律从基线（prod.）读；
    结果库中的源表另做整表禁止变更比较——输出与源一起坏不能自证通过。
    """
    con = duckdb.connect(str(clone), read_only=True)
    try:
        con.execute(f"ATTACH '{prod}' AS prod (READ_ONLY)")

        def xa(table: str, where: str) -> list[int]:
            cols = [r[1] for r in con.execute(
                f"PRAGMA table_info('{table}')").fetchall()]
            sel = ", ".join(cols)
            fwd = con.execute(
                f"SELECT COUNT(*) FROM (SELECT {sel} FROM prod.{table} {where} "
                f"EXCEPT ALL SELECT {sel} FROM {table} {where})").fetchone()[0]
            rev = con.execute(
                f"SELECT COUNT(*) FROM (SELECT {sel} FROM {table} {where} "
                f"EXCEPT ALL SELECT {sel} FROM prod.{table} {where})"
            ).fetchone()[0]
            return [fwd, rev]

        d0, d1 = spec["window_start"], spec["window_end"]
        write_keys = sorted(set(spec["gap_parallel"]) | set(spec["gap_parquet"])
                            | {spec["shell_date"]})
        marks = ",".join(f"'{d}'" for d in write_keys)
        check("fact_other_stocks_allcols",
              xa("fact_stock_daily", f"WHERE stock_ts_code <> '{CODE}'")
              == [0, 0])
        expected_retained = spec["expected_total_rows"] - len(write_keys)
        before = con.execute(
            f"SELECT * FROM prod.fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date BETWEEN '{d0}' AND '{d1}' "
            f"AND trade_date NOT IN ({marks}) ORDER BY trade_date").fetchall()
        after = con.execute(
            f"SELECT * FROM fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date BETWEEN '{d0}' AND '{d1}' "
            f"AND trade_date NOT IN ({marks}) ORDER BY trade_date").fetchall()
        check("retained_rows_full_column_identical",
              before == after and len(after) == expected_retained,
              {"rows": len(after), "expected": expected_retained})
        outside_diff = xa(
            "fact_stock_daily", f"WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT BETWEEN '{d0}' AND '{d1}'")
        check("target_outside_window_allcols", outside_diff == [0, 0],
              outside_diff)

        # 源表禁止变更（整表；合同承诺写入器不触碰这两张输入表）
        check("hithink_source_untouched",
              xa("fact_stock_daily_hithink", "") == [0, 0])
        check("hithink_adjustment_untouched",
              xa("fact_stock_adjustment_hithink", "") == [0, 0])

        # 源指纹：从基线重算（与写入器同查询同序列化），绑定两轮子报告记录值
        prev_row = con.execute(
            "SELECT MAX(trade_date) FROM prod.fact_market_daily "
            "WHERE trade_date < ?", [d0]).fetchone()
        prev_day = str(prev_row[0]) if prev_row and prev_row[0] else None
        if prev_day is None:
            check("parallel_source_md5_binding", False,
                  "基线市场历缺窗口前交易日")
        else:
            src_rows = con.execute(
                "SELECT trade_date, open, high, low, close, volume, turnover "
                "FROM prod.fact_stock_daily_hithink WHERE stock_ts_code=? "
                "AND adjusted='none' AND trade_date BETWEEN ? AND ? "
                "ORDER BY 1",
                [CODE, prev_day, max(spec["gap_parallel"])]).fetchall()
            recomputed = hashlib.md5(json.dumps(
                [tuple(str(c) for c in r) for r in src_rows]).encode()
            ).hexdigest()
            md5s = {t: receipts[t]["child_report"].get("parallel_source_md5")
                    for t in ("apply", "verify")}
            check("parallel_source_md5_binding",
                  recomputed == md5s["apply"] == md5s["verify"],
                  {"recomputed": recomputed, "rows": len(src_rows),
                   "apply": md5s["apply"], "verify": md5s["verify"]})

        # 授权键集全字段 oracle：并跑源行从基线（prod.）读，parquet 段从冻结文件读
        src = {str(r[0]): r[1:] for r in con.execute(f"""
          SELECT trade_date, open, high, low, close, volume, turnover
          FROM prod.fact_stock_daily_hithink
          WHERE stock_ts_code='{CODE}' AND adjusted='none'
          UNION ALL
          SELECT CAST(to_timestamp(date_ms/1000) AS DATE), open_price, high_price,
                 low_price, close_price, volume, turnover
          FROM read_parquet('{pq}')
          WHERE thscode='{CODE}' AND currency='CNY' AND interval='1d'
            AND adjusted='none'""").fetchall()}
        cal = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT trade_date FROM prod.fact_market_daily "
            "WHERE trade_date BETWEEN '2026-06-01' AND ? ORDER BY 1",
            [d1]).fetchall()]
        rows = con.execute(
            f"SELECT trade_date, stock_name, open, high, low, close, pre_close,"
            f" pct_chg, amount, turnover, volume, source FROM fact_stock_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date IN ({marks})").fetchall()
        bad = []
        for r in rows:
            d = str(r[0])
            s = src[d]
            pred = cal[cal.index(d) - 1]
            pre = float(Decimal(str(float(src[pred][3]))).quantize(
                Decimal("0.01")))
            pct = float(((Decimal(str(r[5])).quantize(Decimal("0.0001"))
                          / Decimal(str(pre)).quantize(Decimal("0.01")) - 1) * 100
                         ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            amt = float((Decimal(str(float(s[5]))).quantize(Decimal("0.01"))
                         / Decimal(10**8)).quantize(Decimal("0.0001"),
                                                   rounding=ROUND_HALF_UP))
            vol = float((Decimal(str(float(s[4]))).quantize(Decimal("1"))
                         / Decimal(100)).quantize(Decimal("1"),
                                                 rounding=ROUND_HALF_UP))
            exp_label = ("hithink:daily-k-10d:backfill-302132-20260914"
                         if d in spec["gap_parquet"]
                         else "hithink:daily-k:backfill-302132-20260914")
            ok = (r[1] == spec["name"] and r[2] == float(s[0])
                  and r[3] == float(s[1]) and r[4] == float(s[2])
                  and r[5] == float(s[3]) and abs(r[6] - pre) < 1e-9
                  and abs(r[7] - pct) < 1e-9 and abs(r[8] - amt) < 1e-9
                  and r[9] is None and abs(r[10] - vol) < 1e-9
                  and r[11] == exp_label
                  and all(math.isfinite(float(v)) for v in r[2:6]))
            if not ok:
                bad.append(d)
        check("keyset_fullfield_oracle",
              len(rows) == len(write_keys) and not bad,
              {"rows": len(rows), "keys": len(write_keys), "bad": bad[:5]})

        w_t = (f"WHERE stock_ts_code <> '{CODE}' OR trade_date NOT BETWEEN "
               f"'{d0}' AND '{d1}'")
        w_w = (f"WHERE stock_ts_code <> '{CODE}' OR as_of_date NOT BETWEEN "
               f"'{d0}' AND '{d1}'")
        check("technical_protected_allcols",
              xa("feature_stock_technical_daily", w_t) == [0, 0])
        check("window_protected_allcols",
              xa("feature_stock_window", w_w) == [0, 0])
        cal64 = [d for d in cal if d >= d0]
        golden = set()
        for i, a in enumerate(cal64):
            for p_ in (5, 10, 20, 60):
                if i >= p_:
                    golden.add((a, cal64[i - p_], a))
        actual = {(str(r[0]), str(r[1]), str(r[2])) for r in con.execute(
            f"SELECT as_of_date, start_date, end_date FROM feature_stock_window "
            f"WHERE stock_ts_code='{CODE}' AND as_of_date BETWEEN '{d0}' "
            f"AND '{d1}'").fetchall()}
        check("window_golden_triples", actual == golden,
              {"actual": len(actual), "golden": len(golden)})
        idx = {d: i for i, d in enumerate(cal64)}
        golden_counts = {p: 0 for p in WINDOW_PERIODS}
        for a, s, _e in golden:
            golden_counts[str(idx[a] - idx[s])] += 1
        check("expected_window_counts_match_golden",
              golden_counts == spec["expected_window_counts"],
              {"golden": golden_counts, "spec": spec["expected_window_counts"]})
        tech_dates = [str(r[0]) for r in con.execute(
            f"SELECT trade_date FROM feature_stock_technical_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date BETWEEN '{d0}' "
            f"AND '{d1}' ORDER BY 1").fetchall()]
        check("technical_exact_set", tech_dates == cal64[25:], len(tech_dates))
        check("expected_technical_count_matches_calendar",
              spec["expected_technical_count"] == len(cal64[25:]),
              {"spec": spec["expected_technical_count"],
               "calendar": len(cal64[25:])})
        tp = spec["pinned_technical_0911"]
        t9 = con.execute(
            f"SELECT ma26, std26, up_value, deviation_pct "
            f"FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date='{d1}'").fetchone()
        check("pinned_technical_target_day",
              t9 is not None and all(
                  abs(a - b) < 1e-9 for a, b in zip(
                      t9, (tp["ma26"], tp["std26"], tp["up_value"],
                           tp["deviation_pct"]))), t9)
        w9 = con.execute(
            f"SELECT start_date, interval_gain_pct, avg_amount "
            f"FROM feature_stock_window WHERE stock_ts_code='{CODE}' "
            f"AND as_of_date='{d1}' ORDER BY start_date").fetchall()
        pins = spec["pinned_windows_0911"]
        check("pinned_windows_target_day",
              len(w9) == len(pins) and all(
                  str(r[0]) == p[0] and abs(r[1] - p[1]) < 1e-9
                  and abs(r[2] - p[2]) < 1e-9 for r, p in zip(w9, pins)))
        check("market_daily_untouched", xa("fact_market_daily", "") == [0, 0])
    finally:
        con.close()

```
