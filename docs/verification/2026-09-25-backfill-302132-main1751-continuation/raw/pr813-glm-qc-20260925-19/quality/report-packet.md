# Immutable evidence packet
No reasoning transcript or other-axis results included.
Raw command output is authoritative. Prior-stage prose may contain errors: never promote a proposed correction or unsupported PASS label to an observed result. Missing evidence must remain explicit.


## inputs/claims.md
```text
# PR #813 / Workorder #83: claims to challenge, not established conclusions

C1 Fixed mutation contract: only 302132.SZ, 2026-06-15..2026-09-11; 53 INSERTs (51 parallel dates plus frozen parquet 09-09/09-10), UPDATE the 06-23 shell; preserve pinned 09-11. No widened keys or substituted source.
C2 Source guard: parallel history upper boundary is max(spec.gap_parallel), h.adjusted='none'; valid later history does not cause false refusal or enter the authorized source. Bad, partial or mismatched input refuses before publication.
C3 Acceptance oracle: preserved rows are evaluated inside the authorized window, while target rows outside it and other stocks retain ALL columns with multiset semantics. Detect amount, deletion, insertion and timestamp mutations, not just row counts. Window after apply: 64 rows, close/pct_chg/amount each 64 nonnull; technical39/window161.
C4 Parent command owns staging/publication/backup and verify-only semantics. Locks, identity, input hash, published target, refusal receipts and recovery guards must be internally coherent; no second production writer path. Assess correctness in scope, not a full unrelated security audit.
C5 Rehearsal is isolated and resource bounded: reject unsafe identity/WAL/low-space state before side effects; apply, verify, 37 acceptance checks, wrong parquet rejection, amount=1e15 negative control, restore matching baseline, production read-only/unchanged. Author's archived full-copy run is an evidence claim, NOT a fresh reviewer run.
C6 Shared OS mocks in three tests are confined to monkeypatch.context(); real open is restored before pytest cleanup. Restoring the old scope must be caught by a regression witness. Neutral temp path avoids E_STOCK_SCOPE interference, not a product fix for that separate known limitation.
C7 Evidence is bound only to clean revision ae3f812e1c1e142953b657ba41f30fce23e7c14a integrated with 1751e21e0fd30642e0b223604b64b30e38c46f41. Prior 3c5 results are not this revision's engineering receipts. Fresh author full-copy rehearsal is supplied in inputs/host-rehearsal; independently inspect command receipts and numeric checks without calling it your own full-copy execution. The separate full engineering gate has completed; its author receipts are not reviewer execution. Merge/production approvals remain false.

```


## inputs/source-contract.md
```text
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

```


## inputs/source-contract-manifest.json
```text
[
  {
    "path": "market_feature_store/sync/repair_backfill_stock_history.py",
    "file_sha256": "11a2cea136b17850efa079c8e2b7c9ced80bc278a696b3058ba56d0f4ad2f049",
    "symbols": [
      "BackfillSpec",
      "_guard",
      "_apply_main",
      "_rebuild_derived_scoped",
      "_accept",
      "run_backfill_child",
      "_code_revision",
      "_guarded_write_json"
    ]
  },
  {
    "path": "market_feature_store/cli.py",
    "file_sha256": "0f4aff9eb0aa74b10f1d777dce1c53f0ae3518870768fb175aeac75d59374e8d",
    "symbols": [
      "cmd_repair_backfill_302132"
    ]
  },
  {
    "path": "scripts/verify_302132_backfill_acceptance.py",
    "file_sha256": "11450bd814251887ac3c6995dc3c8ce2036b113fbd8226dea1eff0981dc910ad",
    "symbols": [
      "_data_checks"
    ]
  }
]

```


## explore/parsed.json
```text
{
  "claims_examined": [
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7"
  ],
  "limits": [
    "No tests or positive control observed yet."
  ],
  "next_stage_command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_earlier_fixture_adapter.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_production_contract.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer",
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_earlier_fixture_adapter.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_production_contract.py"
  ],
  "provenance": "All tests supplied. 10 prior-reviewer assertions plus 14 host-authored tests. No execution in explore.",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "baseline": "1751e21e0fd30642e0b223604b64b30e38c46f41"
}

```


## execute/parsed.json
```text
{
  "author_test_counts": null,
  "findings": [],
  "limits": [
    "Real-date fixture contains verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar, not full production.",
    "Host full-copy rehearsal is audit-only, not reviewer execution.",
    "Supplied evidence only; no newly authored tests; supplied tests unedited; no wrappers; single pytest invocation, no rerun.",
    "Claim evaluation deferred to report stage."
  ],
  "positive_control": {
    "command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/positive_control.py",
    "exit_code": 1,
    "expected_exit_code": 1,
    "observed": "AssertionError: intentional probe_bug control",
    "passed": true
  },
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_earlier_fixture_adapter.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_production_contract.py"
  ],
  "probe_provenance": {
    "c6_disclosure": "Three copied author test bodies run twice each (candidate and external scope-mutant) inside three host-authored regression witnesses; six body invocations disclosed separately; no standalone author pytest invocation.",
    "editing": "Supplied tests unedited; no wrappers added; no rerun of failed pytest (none failed).",
    "test_earlier_fixture_adapter_cases": 3,
    "test_production_contract_cases": 15,
    "test_production_contract_note": "Host-authored: real-date CLI apply/verify/rollback, source refusals, preflight, OS scope witnesses, host receipt consistency.",
    "test_seeded_c3_cases": 7,
    "total_prior_reviewer_cases_combined": 10
  },
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 25,
    "failed": 0,
    "passed": 25,
    "skipped": 0
  },
  "supplied_probe_counts": {
    "errors": 0,
    "executed": 25,
    "failed": 0,
    "passed": 25,
    "skipped": 0
  },
  "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probe-results-all.xml",
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "baseline": "1751e21e0fd30642e0b223604b64b30e38c46f41"
}

```


## work/EXPLORE.md
MISSING: not delivered by previous stage. No substitute was authored.


## work/EXECUTE.md
```text
# EXECUTE Receipt — PR813 QC (revision ae3f812e1c1e142953b657ba41f30fce23e7c14a)

## Positive control
Command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/positive_control.py
Observed: exit code 1, AssertionError "intentional probe_bug control" — as expected.

## Direct pytest batch (single invocation)
Command (as specified) run once; no rerun.
Raw output: `.........................  [100%]` — 25 passed in 17.02s
JUnit: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probe-results-all.xml

Counts (from raw output / JUnit):
- executed: 25
- passed: 25
- failed: 0
- errors: 0
- skipped: 0

## Supplied provenance
- test_seeded_c3.py: 7 prior-reviewer cases (host fixture fixes)
- test_earlier_fixture_adapter.py: 3 prior-reviewer cases (host fixture fixes)
- Combined prior-reviewer cases: 10 (not 10 each)
- test_production_contract.py: 15 host-authored cases (real-date CLI apply/verify/rollback, source refusals, preflight, OS scope witnesses, host receipt consistency)
- C6: three copied author test bodies each run twice (candidate + external scope-mutant) inside three host-authored regression witnesses → six body invocations, disclosed separately; no standalone author pytest invocation.
- Supplied evidence only; no newly authored tests by this reviewer. Supplied tests unedited; no wrappers added; no failed pytest rerun.

## Notes / limits
- Real-date fixture contains verbatim 302132.SZ and sentinel 000001.SZ history plus market calendar, not full production.
- Host full-copy rehearsal (inputs/host-rehearsal) is audit-only; not reviewer execution.
- Numeric values above come from execution only.
- This is the execution receipt stage; claim evaluation deferred to report stage.

```


## execute/commands/001-bash/output.log
```text
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/positive_control.py", line 1, in <module>
    assert 1 == 2, "intentional probe_bug control"
           ^^^^^^
AssertionError: intentional probe_bug control

```


## execute/commands/001-bash/request.json
```text
{"toolCallId":"call_c3230a6c826041c8a21b942e","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/positive_control.py"}}
```


## execute/commands/001-bash/result.json
```text
{"exitCode":1}
```


## execute/commands/002-bash/output.log
```text
.........................                                                [100%]
- generated xml file: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probe-results-all.xml -
25 passed in 17.02s

```


## execute/commands/002-bash/request.json
```text
{"toolCallId":"call_e594762c27624ccaad88af9e","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_earlier_fixture_adapter.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probes/test_production_contract.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer","timeout":1200}}
```


## execute/commands/002-bash/result.json
```text
{"exitCode":0}
```


## work/probes/probe_c3_acceptance_v2.py
```text
"""Reviewer QC probe C3 v2 (PR #813): acceptance oracle for outside-window rows.

Challenges candidate/scripts/verify_302132_backfill_acceptance.py (main ->
_data_checks). Fixture helper reused from author tests; ALL assertions are the
reviewer's own. Synthetic DuckDB inside quality/work only. No production run.

v2 fix: sys.path setup before importing the author test module (v1 import of
market_feature_store would fail without candidate root on sys.path); removed the
intentional-control test (positive control is the separate standalone script).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate")
TESTS = CAND / "tests" / "test_repair_backfill_stock_history.py"
ACCEPT = CAND / "scripts" / "verify_302132_backfill_acceptance.py"

import importlib.util

sys.path.insert(0, str(CAND))
spec = importlib.util.spec_from_file_location("t302132", TESTS)
t = importlib.util.module_from_spec(spec)
sys.modules["t302132"] = t
spec.loader.exec_module(t)

OTHER = "000001.SZ"
LATER = "2026-09-22"
LATER2 = "2026-09-23"


def _subprocess_env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(CAND),
    }


def _run(clone: Path, art: dict, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ACCEPT), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", t.APPLY_RUN, "--run-verify", t.VERIFY_RUN,
         "--expected-revision", t.E2E_REV,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=110, env=_subprocess_env())


def _base(tmp_path: Path) -> dict:
    """Author fixture + a later (outside-window) row in BOTH baseline & clone,
    receipts' backup sha rebound to the modified baseline."""
    import duckdb
    art = t._build_e2e_artifacts(tmp_path)
    for p in (art["baseline"], art["clone"]):
        with duckdb.connect(str(p)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily SELECT * REPLACE "
                "(DATE '" + LATER + "' AS trade_date) FROM fact_stock_daily "
                "WHERE stock_ts_code=? AND trade_date=?",
                [art["spec"].code, art["spec"].window_end])
    art["base_sha"] = t.mod._sha256(art["baseline"])
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        p = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        rec = json.loads(p.read_text())
        rec["backup"]["backup_sha256"] = art["base_sha"]
        p.write_text(json.dumps(rec))
    return art


def _mutated_clone(tmp_path: Path, art: dict, mutation: str) -> Path:
    import duckdb
    clone = tmp_path / "clone_mut.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    with duckdb.connect(str(clone)) as con:
        if mutation == "none":
            pass
        elif mutation == "amount":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [art["spec"].code])
        elif mutation == "timestamp":
            con.execute("UPDATE fact_stock_daily SET updated_at="
                        "TIMESTAMP '2026-09-23 12:00:00' WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "delete":
            con.execute("DELETE FROM fact_stock_daily WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "insert":
            con.execute("INSERT INTO fact_stock_daily SELECT * REPLACE "
                        "(DATE '" + LATER2 + "' AS trade_date) FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "duplicate":
            # DISCLOSURE: clone-only CTAS rebuild removes the PK constraint so
            # an exact duplicate row can exist; adversarial multiset-oracle
            # probe only — real PK would itself block duplicates.
            con.execute("BEGIN")
            con.execute("CREATE TABLE fsd_nopk AS SELECT * FROM fact_stock_daily")
            con.execute("DROP TABLE fact_stock_daily")
            con.execute("ALTER TABLE fsd_nopk RENAME TO fact_stock_daily")
            con.execute("INSERT INTO fact_stock_daily SELECT * FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
            con.execute("COMMIT")
        elif mutation == "other_stock":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [OTHER])
        else:
            raise ValueError(mutation)
    return clone


def _fail_check(res, out: Path, must_fail: str) -> dict:
    __tracebackhide__ = True
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert out.exists()
    v = json.loads(out.read_text())
    assert v["verdict"] == "FAIL", v
    assert must_fail in v["failed"], (must_fail, v["failed"])
    return v


MUTS = ["amount", "timestamp", "delete", "insert", "duplicate", "other_stock"]
EXPECT_CHECK = {"other_stock": "fact_other_stocks_allcols",
                "insert": "target_outside_window_allcols"}


@pytest.mark.parametrize("mutation", MUTS)
def test_outside_window_mutation_fails(tmp_path, mutation):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, mutation)
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    _fail_check(res, out, EXPECT_CHECK.get(
        mutation, "target_outside_window_allcols"))


def test_baseline_pass(tmp_path):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, "none")
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    assert res.returncode == 0, (res.stdout, res.stderr)
    v = json.loads(out.read_text())
    assert v["verdict"] == "PASS" and v["failed"] == [], v

```


## work/probes/test_earlier_fixture_adapter.py
```text
"""Host-only fixture repair, retaining the reviewer's two mutation assertions."""
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'quality/work/probes/test_new_c3_v1.py'
loader = importlib.util.spec_from_file_location('reviewer_earlier_original', SOURCE)
review = importlib.util.module_from_spec(loader)
sys.modules[loader.name] = review
loader.loader.exec_module(review)
original_base = review._base


def corrected_base(tmp_path):
    art = original_base(tmp_path)
    earlier = date.fromisoformat(art['spec'].window_start) - timedelta(days=1)
    for path in (art['baseline'], art['clone']):
        with duckdb.connect(str(path)) as con:
            rows = con.execute(
                'INSERT INTO fact_stock_daily SELECT * REPLACE (? AS trade_date) '
                'FROM fact_stock_daily WHERE stock_ts_code=? AND trade_date=? RETURNING trade_date',
                [earlier, art['spec'].code, art['spec'].window_end],
            ).fetchall()
            assert rows == [(earlier,)]
    art['base_sha'] = review.t.mod._sha256(art['baseline'])
    for run in (review.t.APPLY_RUN, review.t.VERIFY_RUN):
        path = Path(str(art['clone']) + f'.repair-backfill-execution.{run}.json')
        receipt = json.loads(path.read_text())
        receipt['backup']['backup_sha256'] = art['base_sha']
        path.write_text(json.dumps(receipt))
    return art


review._base = corrected_base
test_new_outside_window_mutations_fail = review.test_new_outside_window_mutations_fail


def test_baseline_with_earlier_row_pass(tmp_path):
    art = corrected_base(tmp_path)
    clone = review._clone_with_receipts(tmp_path, art)
    out = tmp_path / 'out.json'
    result = review._run(clone, art, out)
    assert result.returncode == 0, (result.stdout, result.stderr)
    verdict = json.loads(out.read_text())
    assert verdict['verdict'] == 'PASS' and not verdict['failed']

```


## work/probes/test_new_c3_v1.py
```text
"""New QC-authored C3 tests (independent of supplied suite assertions).

Provenance: fixture/_base/copy logic ADAPTED from supplied probe_c3_acceptance_v2.py
(whose setup derives from author _build_e2e_artifacts); assertions below are newly
authored this session. Targets candidate scripts/verify_302132_backfill_acceptance.py
main -> _data_checks "target_outside_window_allcols".

New cases (not covered by the supplied suite's amount/timestamp/delete/insert/
duplicate/other_stock on the later date):
  1. earlier_than_window: mutate an inside-code row strictly BEFORE window_start
     (trade_date < 2026-06-15), assert acceptance FAILs target_outside_window_allcols.
  2. null_column: set a NULL-able column (stock_name) to NULL on the outside-window
     later row; NULL-vs-nonNULL must be caught by EXCEPT ALL multiset semantics.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate")
TESTS = CAND / "tests" / "test_repair_backfill_stock_history.py"
ACCEPT = CAND / "scripts" / "verify_302132_backfill_acceptance.py"

sys.path.insert(0, str(CAND))
spec = importlib.util.spec_from_file_location("t302132_new", TESTS)
t = importlib.util.module_from_spec(spec)
sys.modules["t302132_new"] = t
spec.loader.exec_module(t)

OTHER = "000001.SZ"
LATER = "2026-09-22"


def _env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(CAND),
    }


def _base(tmp_path: Path) -> dict:
    art = t._build_e2e_artifacts(tmp_path)
    for p in (art["baseline"], art["clone"]):
        with duckdb.connect(str(p)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily SELECT * REPLACE "
                "(DATE '" + LATER + "' AS trade_date) FROM fact_stock_daily "
                "WHERE stock_ts_code=? AND trade_date=?",
                [art["spec"].code, art["spec"].window_end])
    art["base_sha"] = t.mod._sha256(art["baseline"])
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        p = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        rec = json.loads(p.read_text())
        rec["backup"]["backup_sha256"] = art["base_sha"]
        p.write_text(json.dumps(rec))
    # receipts resolved relative to clone path (host correction, same as supplied)
    clone = Path(art["clone"])
    return art


def _clone_with_receipts(tmp_path: Path, art: dict) -> Path:
    clone = tmp_path / "clone_new.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        src = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        dst = Path(str(clone) + f".repair-backfill-execution.{rid}.json")
        shutil.copyfile(src, dst)
    return clone


def _run(clone: Path, art: dict, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ACCEPT), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", t.APPLY_RUN, "--run-verify", t.VERIFY_RUN,
         "--expected-revision", t.E2E_REV,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=110, env=_env())


@pytest.mark.parametrize("mutation", ["earlier_than_window", "null_column"])
def test_new_outside_window_mutations_fail(tmp_path, mutation):
    art = _base(tmp_path)
    clone = _clone_with_receipts(tmp_path, art)
    with duckdb.connect(str(clone)) as con:
        if mutation == "earlier_than_window":
            code = art["spec"].code
            d0 = art["spec"].window_start
            rows = con.execute(
                "SELECT trade_date FROM fact_stock_daily WHERE stock_ts_code=? "
                "AND trade_date < ? ORDER BY trade_date DESC LIMIT 1",
                [code, d0]).fetchall()
            assert rows, "fixture lacks a pre-window row for target code"
            earlier = rows[0][0]
            changed = con.execute(
                "UPDATE fact_stock_daily SET amount=amount+1 WHERE "
                "stock_ts_code=? AND trade_date=? RETURNING amount",
                [code, earlier]).fetchall()
            assert len(changed) == 1, (changed, earlier)
        elif mutation == "null_column":
            changed = con.execute(
                "UPDATE fact_stock_daily SET stock_name=NULL WHERE "
                "stock_ts_code=? AND trade_date=DATE '" + LATER + "' "
                "RETURNING 1", [art["spec"].code]).fetchall()
            assert len(changed) == 1, changed
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert out.exists()
    v = json.loads(out.read_text())
    assert v["verdict"] == "FAIL", v
    assert "target_outside_window_allcols" in v["failed"], v["failed"]

```


## work/probes/test_production_contract.py
```text
"""HOST-SUPPLIED probes, not model-authored assertions or a review verdict.

Runs the real parent and external acceptance against a frozen real-data slice.
C6 embeds three author test bodies inside a new restoration/mutation witness;
those six body invocations are disclosed, not standalone author pytest runs.
"""
import ast
from argparse import Namespace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import duckdb
import pytest

BATCH = Path(__file__).resolve().parents[3]
TREE = BATCH / 'candidate'
Q = BATCH / 'quality'
INPUTS = Q / 'inputs'
sys.path.insert(0, str(TREE))
from market_feature_store.sync import repair_backfill_stock_history as mod
from market_feature_store.sync.repair_hithink_stock_day import RepairRefused
from scripts.review_probes import rehearse_302132_backfill as rehearsal

REV = json.loads((Q / 'config.json').read_text())['revision']
SOURCE = INPUTS / 'production-slice.duckdb'
PARQUET = INPUTS / 'frozen.parquet'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    with path.open('x') as stream:
        json.dump(obj, stream, indent=2, default=str)


def command(argv, cwd=TREE, extra=None):
    env = {k: os.environ[k] for k in ('HOME', 'PATH', 'LANG', 'TMPDIR') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', GIT_OPTIONAL_LOCKS='0')
    env.update(extra or {})
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)


def test_real_date_parent_rehearsal_and_numeric_contract(tmp_path):
    before = sha(SOURCE)
    manifest = json.loads((INPUTS / 'fixture-manifest.json').read_text())
    assert before == manifest['fixture_sha256']
    assert sha(PARQUET) == mod.PARQUET_SHA256
    with duckdb.connect(str(SOURCE), read_only=True) as con:
        assert str(con.execute("SELECT max(trade_date) FROM fact_stock_daily_hithink WHERE stock_ts_code='302132.SZ' AND adjusted='none'").fetchone()[0]) > max(mod.GAP_PARALLEL)
    out = tmp_path / 'real-date-rehearsal'
    argv = [sys.executable, '-B', str(TREE / 'scripts/review_probes/rehearse_302132_backfill.py'),
            '--production', str(SOURCE), '--parquet', str(PARQUET), '--output', str(out)]
    result = command(argv)
    save(tmp_path / 'rehearsal-process.json', {'argv': argv, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['ok'] and summary['production_unchanged']
    assert summary['revision'] == REV and summary['dirty'] is False
    assert summary['rollback_sha256'] == summary['baseline_sha256'] == before
    assert summary['values_before']['rows'] == 11
    assert summary['values_after']['rows'] == 64
    assert summary['values_after']['non_null'] == {'close': 64, 'pct_chg': 64, 'amount': 64}
    assert summary['values_after']['identical_adjacent_values'] == []
    assert summary['failure_did_not_publish']
    acceptance = json.loads((out / 'acceptance.json').read_text())
    assert acceptance['verdict'] == 'PASS' and acceptance['failed'] == []
    checks = {v['name']: v for v in acceptance['checks']}
    assert len(checks) == 37 and all(v['ok'] for v in checks.values())
    assert checks['window_golden_triples']['detail'] == {'actual': 161, 'golden': 161}
    assert checks['technical_exact_set']['detail'] == 39
    assert checks['expected_window_counts_match_golden']['detail']['golden'] == {'5': 59, '10': 54, '20': 44, '60': 4}
    applied = json.loads((out / f"copy.duckdb.repair-backfill-execution.{summary['runs']['apply']}.json").read_text())
    verified = json.loads((out / f"copy.duckdb.repair-backfill-execution.{summary['runs']['verify']}.json").read_text())
    for receipt, mode in ((applied, 'apply'), (verified, 'verify')):
        assert receipt['code_revision'] == REV and receipt['code_dirty'] is False
        assert receipt['child_report']['mode'] == mode
        assert receipt['child_report']['technical_rows'] == 39
        assert receipt['child_report']['window_rows'] == 161
        assert receipt['child_report']['ok'] is True
    assert applied['backup']['backup_sha256'] == before
    assert applied['run_id'] != verified['run_id']
    control = json.loads((out / 'amount-control.json').read_text())
    assert control['failed'] == ['keyset_fullfield_oracle']
    assert sha(SOURCE) == before
    save(Q / 'work/independent-real-date-observation.json', {
        'revision': REV, 'classification': 'reviewer executes host-supplied probes on frozen real-data subset; not full production copy',
        'rows': 64, 'technical': 39, 'window': 161, 'acceptance_checks': 37,
        'rehearsal_directory': str(out), 'backup_rollback_match': True,
        'source_sha256': before, 'commands': summary['commands']})


def test_exact_main_insert_and_update_keysets(tmp_path):
    target = tmp_path / 'keyset.duckdb'
    shutil.copyfile(SOURCE, target)
    result = command([sys.executable, '-B', '-m', 'market_feature_store.cli',
                      'repair-backfill-302132', '--parquet', str(PARQUET)],
                     extra={'MARKET_FEATURE_STORE_DB': str(target), 'MARKET_FEATURE_STORE_PRODUCTION_DB': str(SOURCE)})
    save(tmp_path / 'keyset-process.json', {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0, result.stdout + result.stderr
    with duckdb.connect(str(target), read_only=True) as con:
        con.execute("ATTACH '" + str(SOURCE).replace("'", "''") + "' AS baseline (READ_ONLY)")
        inserted = con.execute('SELECT stock_ts_code, trade_date FROM fact_stock_daily EXCEPT ALL SELECT stock_ts_code, trade_date FROM baseline.fact_stock_daily').fetchall()
        removed = con.execute('SELECT stock_ts_code, trade_date FROM baseline.fact_stock_daily EXCEPT ALL SELECT stock_ts_code, trade_date FROM fact_stock_daily').fetchall()
        changed_before = con.execute('SELECT stock_ts_code, trade_date FROM (SELECT * FROM baseline.fact_stock_daily EXCEPT ALL SELECT * FROM fact_stock_daily)').fetchall()
        changed_after = con.execute('SELECT stock_ts_code, trade_date FROM (SELECT * FROM fact_stock_daily EXCEPT ALL SELECT * FROM baseline.fact_stock_daily)').fetchall()
    expected = {('302132.SZ', date) for date in (*mod.GAP_PARALLEL, *mod.GAP_PARQUET)}
    normalize = lambda rows: [(code, str(day)) for code, day in rows]
    assert len(inserted) == len(expected) == 53 and set(normalize(inserted)) == expected
    assert removed == []
    assert normalize(changed_before) == [('302132.SZ', '2026-06-23')]
    assert len(changed_after) == 54
    assert set(normalize(changed_after)) == expected | {('302132.SZ', '2026-06-23')}
    save(Q / 'work/independent-keyset-observation.json', {'inserted': sorted(normalize(inserted)),
         'deleted_keys': removed, 'changed_existing': normalize(changed_before),
         'classification': 'direct bidirectional full-row comparison on real-date subset, not full production'})


@pytest.mark.parametrize('mutation', ['missing', 'null', 'adjusted'])
def test_corrupt_authorized_source_refuses_without_publish(tmp_path, mutation):
    target = tmp_path / 'input.duckdb'
    shutil.copyfile(SOURCE, target)
    with duckdb.connect(str(target)) as con:
        where = "stock_ts_code='302132.SZ' AND trade_date='2026-06-17' AND adjusted='none'"
        if mutation == 'missing':
            con.execute('DELETE FROM fact_stock_daily_hithink WHERE ' + where)
        elif mutation == 'null':
            con.execute('UPDATE fact_stock_daily_hithink SET close=NULL WHERE ' + where)
        else:
            con.execute("UPDATE fact_stock_daily_hithink SET adjusted='invalid-review-control' WHERE " + where)
    before = sha(target)
    result = command([sys.executable, '-B', '-m', 'market_feature_store.cli',
                      'repair-backfill-302132', '--parquet', str(PARQUET)],
                     extra={'MARKET_FEATURE_STORE_DB': str(target), 'MARKET_FEATURE_STORE_PRODUCTION_DB': str(SOURCE)})
    save(tmp_path / 'refusal-process.json', {'mutation': mutation, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 2, result.stdout + result.stderr
    assert sha(target) == before
    assert not list(tmp_path.glob('*.bak-*'))


class RemoveContext(ast.NodeTransformer):
    def visit_With(self, node):
        if any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Attribute)
               and i.context_expr.func.attr == 'context' for i in node.items):
            return [self.visit(child) for child in node.body]
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == 'patch':
            return ast.copy_location(ast.Name(id='monkeypatch', ctx=node.ctx), node)
        return node


@pytest.mark.parametrize('name,attribute', [
    ('test_refused_receipt_write_failure_cleans_partial', 'fdopen'),
    ('test_cli_parent_preflight_blocks_on_open_permission_error', 'open'),
    ('test_refused_receipt_eexist_race_keeps_other_writers_file', 'open'),
])
def test_context_regression_witness_rejects_degraded_scope(tmp_path, name, attribute):
    source = (TREE / 'tests/test_repair_backfill_stock_history.py').read_text()
    observations = []
    for mutated in (False, True):
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        if mutated:
            module = RemoveContext().visit(module)
        ast.fix_missing_locations(module)
        namespace = {'mod': mod, 'pytest': pytest, 'RepairRefused': RepairRefused}
        exec(compile(module, '<external-scope-witness>', 'exec'), namespace)
        folder = tmp_path / ('mutant' if mutated else 'candidate')
        folder.mkdir()
        patch = pytest.MonkeyPatch()
        before = getattr(os, attribute)
        error = None
        try:
            try:
                namespace[name](folder, patch)
            except AssertionError as exc:
                error = repr(exc)
            restored = getattr(os, attribute) is before
        finally:
            patch.undo()
        assert getattr(os, attribute) is before
        observations.append({'mutated': mutated, 'restored_before_fixture_cleanup': restored, 'body_assertion_error': error})
        if mutated:
            assert not restored or error is not None, 'degraded scope escaped the witness'
        else:
            assert restored and error is None
    save(tmp_path / 'scope-witness.json', {'copied_author_body': name, 'standalone_author_pytest_runs': 0, 'body_invocations': 2, 'observations': observations})


@pytest.mark.parametrize('case', ['existing', 'under_source', 'symlink', 'wal', 'bad_hash'])
def test_rehearsal_rejects_unsafe_input_before_copy(tmp_path, case):
    data = tmp_path / 'data'
    data.mkdir()
    source = data / 'source.duckdb'
    shutil.copyfile(SOURCE, source)
    parquet = data / 'frozen.parquet'
    shutil.copyfile(PARQUET, parquet)
    output = tmp_path / 'run'
    if case == 'existing':
        output.mkdir()
    elif case == 'under_source':
        output = data / 'run'
    elif case == 'symlink':
        alias = data / 'alias.duckdb'
        alias.symlink_to(source)
        source = alias
    elif case == 'wal':
        Path(str(source) + '.wal').write_bytes(b'WAL witness')
    else:
        parquet.write_bytes(b'bad hash witness')
    before = {p.name: sha(p) for p in data.iterdir() if p.is_file()}
    with pytest.raises(ValueError):
        rehearsal.run(Namespace(production=source, parquet=parquet, output=output))
    assert {p.name: sha(p) for p in data.iterdir() if p.is_file()} == before
    assert not output.exists() or (case == 'existing' and list(output.iterdir()) == [])


def test_low_space_refuses_before_database_copies(tmp_path, monkeypatch):
    out = tmp_path / 'low-space'
    with monkeypatch.context() as patch:
        patch.setattr(rehearsal.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
        rc = rehearsal.run(Namespace(production=SOURCE, parquet=PARQUET, output=out))
    assert rc == 2
    result = json.loads((out / 'summary.json').read_text())
    assert 'insufficient physical headroom' in result['error']
    assert not list(out.glob('*.duckdb'))


def test_host_full_copy_receipts_are_current_but_not_reviewer_execution():
    root = INPUTS / 'host-rehearsal'
    summary = json.loads((root / 'summary.json').read_text())
    assert summary['revision'] == REV and summary['dirty'] is False
    assert summary['ok'] and summary['production_unchanged']
    assert summary['production_before']['size'] > SOURCE.stat().st_size
    assert summary['rollback_sha256'] == summary['baseline_sha256']
    manifest = json.loads((root / 'manifest.json').read_text())
    for name, expected in manifest.items():
        path = root / name
        if path.is_file():
            assert sha(path) == expected
    for name, expected in [('refused-parent', 2), ('apply', 0), ('verify', 0), ('acceptance', 0), ('amount-control', 2)]:
        receipt = json.loads((root / f'{name}.command.json').read_text())
        assert receipt['exit_code'] == receipt['expected_exit'] == expected

```


## work/probes/test_seeded_c3.py
```text
"""HOST fixture correction; assertions originate in reviewer source, NOT a QC verdict."""
import importlib.util
from pathlib import Path
import shutil
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'quality/work/probes/probe_c3_acceptance_v2.py'
spec = importlib.util.spec_from_file_location('reviewer_original_for_host_diagnosis', SOURCE)
review = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = review
spec.loader.exec_module(review)
original_mutation = review._mutated_clone


def corrected_fixture(tmp_path, art, mutation):
    clone = original_mutation(tmp_path, art, mutation)
    # The CLI resolves receipts relative to the requested clone, not the fixture's old filename.
    for run in (review.t.APPLY_RUN, review.t.VERIFY_RUN):
        source = Path(str(art['clone']) + f'.repair-backfill-execution.{run}.json')
        destination = Path(str(clone) + f'.repair-backfill-execution.{run}.json')
        assert source.is_file() and not destination.exists()
        shutil.copyfile(source, destination)
    if mutation == 'other_stock':
        # The original fixture has OTHER only on CAL dates, never on LATER.
        with duckdb.connect(str(clone)) as con:
            changed = con.execute(
                'UPDATE fact_stock_daily SET amount=amount+1 WHERE stock_ts_code=? AND trade_date=? RETURNING amount',
                [review.OTHER, review.t.CAL[0]],
            ).fetchall()
            assert len(changed) == 1
    return clone


review._mutated_clone = corrected_fixture
test_outside_window_mutation_fails = review.test_outside_window_mutation_fails
test_baseline_pass = review.test_baseline_pass

```


## work/probe-results-all.xml
```text
<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="25" time="17.013" timestamp="2026-09-25T12:58:14.643777+08:00" hostname="77deMacBook-Air.local"><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[amount]" time="0.768" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[timestamp]" time="0.568" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[delete]" time="0.555" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[insert]" time="0.588" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[duplicate]" time="0.572" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[other_stock]" time="0.556" /><testcase classname="probes.test_seeded_c3" name="test_baseline_pass" time="0.535" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[earlier_than_window]" time="0.580" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[null_column]" time="0.577" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_baseline_with_earlier_row_pass" time="0.607" /><testcase classname="probes.test_production_contract" name="test_real_date_parent_rehearsal_and_numeric_contract" time="6.175" /><testcase classname="probes.test_production_contract" name="test_exact_main_insert_and_update_keysets" time="1.303" /><testcase classname="probes.test_production_contract" name="test_corrupt_authorized_source_refuses_without_publish[missing]" time="0.557" /><testcase classname="probes.test_production_contract" name="test_corrupt_authorized_source_refuses_without_publish[null]" time="0.497" /><testcase classname="probes.test_production_contract" name="test_corrupt_authorized_source_refuses_without_publish[adjusted]" time="0.524" /><testcase classname="probes.test_production_contract" name="test_context_regression_witness_rejects_degraded_scope[test_refused_receipt_write_failure_cleans_partial-fdopen]" time="0.014" /><testcase classname="probes.test_production_contract" name="test_context_regression_witness_rejects_degraded_scope[test_cli_parent_preflight_blocks_on_open_permission_error-open]" time="0.063" /><testcase classname="probes.test_production_contract" name="test_context_regression_witness_rejects_degraded_scope[test_refused_receipt_eexist_race_keeps_other_writers_file-open]" time="0.012" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[existing]" time="0.244" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[under_source]" time="0.244" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[symlink]" time="0.293" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[wal]" time="0.256" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[bad_hash]" time="0.253" /><testcase classname="probes.test_production_contract" name="test_low_space_refuses_before_database_copies" time="0.562" /><testcase classname="probes.test_production_contract" name="test_host_full_copy_receipts_are_current_but_not_reviewer_execution" time="0.007" /></testsuite></testsuites>
```


## work/independent-keyset-observation.json
```text
{
  "inserted": [
    [
      "302132.SZ",
      "2026-06-17"
    ],
    [
      "302132.SZ",
      "2026-06-24"
    ],
    [
      "302132.SZ",
      "2026-06-29"
    ],
    [
      "302132.SZ",
      "2026-06-30"
    ],
    [
      "302132.SZ",
      "2026-07-02"
    ],
    [
      "302132.SZ",
      "2026-07-03"
    ],
    [
      "302132.SZ",
      "2026-07-06"
    ],
    [
      "302132.SZ",
      "2026-07-08"
    ],
    [
      "302132.SZ",
      "2026-07-10"
    ],
    [
      "302132.SZ",
      "2026-07-13"
    ],
    [
      "302132.SZ",
      "2026-07-14"
    ],
    [
      "302132.SZ",
      "2026-07-15"
    ],
    [
      "302132.SZ",
      "2026-07-16"
    ],
    [
      "302132.SZ",
      "2026-07-17"
    ],
    [
      "302132.SZ",
      "2026-07-20"
    ],
    [
      "302132.SZ",
      "2026-07-21"
    ],
    [
      "302132.SZ",
      "2026-07-22"
    ],
    [
      "302132.SZ",
      "2026-07-23"
    ],
    [
      "302132.SZ",
      "2026-07-24"
    ],
    [
      "302132.SZ",
      "2026-07-27"
    ],
    [
      "302132.SZ",
      "2026-07-28"
    ],
    [
      "302132.SZ",
      "2026-07-29"
    ],
    [
      "302132.SZ",
      "2026-07-30"
    ],
    [
      "302132.SZ",
      "2026-07-31"
    ],
    [
      "302132.SZ",
      "2026-08-03"
    ],
    [
      "302132.SZ",
      "2026-08-04"
    ],
    [
      "302132.SZ",
      "2026-08-05"
    ],
    [
      "302132.SZ",
      "2026-08-06"
    ],
    [
      "302132.SZ",
      "2026-08-07"
    ],
    [
      "302132.SZ",
      "2026-08-10"
    ],
    [
      "302132.SZ",
      "2026-08-11"
    ],
    [
      "302132.SZ",
      "2026-08-12"
    ],
    [
      "302132.SZ",
      "2026-08-13"
    ],
    [
      "302132.SZ",
      "2026-08-14"
    ],
    [
      "302132.SZ",
      "2026-08-17"
    ],
    [
      "302132.SZ",
      "2026-08-18"
    ],
    [
      "302132.SZ",
      "2026-08-19"
    ],
    [
      "302132.SZ",
      "2026-08-20"
    ],
    [
      "302132.SZ",
      "2026-08-21"
    ],
    [
      "302132.SZ",
      "2026-08-24"
    ],
    [
      "302132.SZ",
      "2026-08-25"
    ],
    [
      "302132.SZ",
      "2026-08-26"
    ],
    [
      "302132.SZ",
      "2026-08-27"
    ],
    [
      "302132.SZ",
      "2026-08-28"
    ],
    [
      "302132.SZ",
      "2026-08-31"
    ],
    [
      "302132.SZ",
      "2026-09-01"
    ],
    [
      "302132.SZ",
      "2026-09-02"
    ],
    [
      "302132.SZ",
      "2026-09-03"
    ],
    [
      "302132.SZ",
      "2026-09-04"
    ],
    [
      "302132.SZ",
      "2026-09-07"
    ],
    [
      "302132.SZ",
      "2026-09-08"
    ],
    [
      "302132.SZ",
      "2026-09-09"
    ],
    [
      "302132.SZ",
      "2026-09-10"
    ]
  ],
  "deleted_keys": [],
  "changed_existing": [
    [
      "302132.SZ",
      "2026-06-23"
    ]
  ],
  "classification": "direct bidirectional full-row comparison on real-date subset, not full production"
}
```


## work/independent-real-date-observation.json
```text
{
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "classification": "reviewer executes host-supplied probes on frozen real-data subset; not full production copy",
  "rows": 64,
  "technical": 39,
  "window": 161,
  "acceptance_checks": 37,
  "rehearsal_directory": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal",
  "backup_rollback_match": true,
  "source_sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "commands": [
    {
      "label": "refused-parent",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/wrong.parquet"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.374
    },
    {
      "label": "apply",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.273
    },
    {
      "label": "verify",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.275
    },
    {
      "label": "acceptance",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "a496e01bfb67",
        "--run-verify",
        "ff3883c7babf",
        "--expected-revision",
        "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 0.354
    },
    {
      "label": "amount-control",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "a496e01bfb67",
        "--run-verify",
        "ff3883c7babf",
        "--expected-revision",
        "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.414
    }
  ]
}
```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/summary.json
```text
{
  "revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "dirty": false,
  "commands": [
    {
      "label": "refused-parent",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/wrong.parquet"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.374
    },
    {
      "label": "apply",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.273
    },
    {
      "label": "verify",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.275
    },
    {
      "label": "acceptance",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "a496e01bfb67",
        "--run-verify",
        "ff3883c7babf",
        "--expected-revision",
        "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 0.354
    },
    {
      "label": "amount-control",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "a496e01bfb67",
        "--run-verify",
        "ff3883c7babf",
        "--expected-revision",
        "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.414
    }
  ],
  "ok": true,
  "production_before": {
    "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/inputs/production-slice.duckdb",
    "size": 10235904,
    "mtime_ns": 1790312094648034916,
    "inode": 268857548,
    "freshness": {
      "fact_auction_hithink": "None",
      "fact_auction_stock_daily": "None",
      "fact_core_leader_daily": "None",
      "fact_core_stock_daily": "None",
      "fact_dragon_hot_money_hithink": "None",
      "fact_dragon_seat_daily": "None",
      "fact_dragon_summary_daily": "None",
      "fact_dragon_tiger_daily": "None",
      "fact_dragon_tiger_hithink": "None",
      "fact_global_index_daily": "None",
      "fact_global_stock_daily": "None",
      "fact_hot_stock_rank_hithink": "None",
      "fact_leader_height_daily": "None",
      "fact_limit_advance_daily": "None",
      "fact_limit_advance_presence": "None",
      "fact_limit_pool_hithink": "None",
      "fact_mainline_sector_daily": "None",
      "fact_mainline_stock_daily": "None",
      "fact_mainline_theme_daily": "None",
      "fact_market_daily": "2026-09-22",
      "fact_polymarket_macro_odds_daily": "None",
      "fact_sector_daily": "None",
      "fact_sector_daily_generation": "None",
      "fact_sector_kline_daily": "None",
      "fact_sector_period_rank_daily": "None",
      "fact_sector_stock_daily": "2026-09-18",
      "fact_sector_stock_daily_generation": "2026-09-18",
      "fact_sector_universe_daily": "None",
      "fact_stock_daily": "2026-09-22",
      "fact_stock_daily_hithink": "2026-09-22",
      "fact_stock_high_daily": "None",
      "fact_stock_technical_snapshot": "None",
      "fact_sw_l1_daily": "None",
      "fact_theme_flow_daily": "None",
      "fact_theme_limit_heat_daily": "None",
      "fact_theme_limit_stock_daily": "None"
    }
  },
  "free_bytes_before": 44996145152,
  "baseline_copy": {
    "method": "clonefile",
    "seconds": 0.008,
    "bytes": 10235904
  },
  "baseline_sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "parquet_sha256": "51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17",
  "target_copy": {
    "method": "clonefile",
    "seconds": 0.003,
    "bytes": 10235904
  },
  "values_before": {
    "rows": 11,
    "non_null": {
      "close": 10,
      "pct_chg": 10,
      "amount": 10
    },
    "identical_adjacent_values": [],
    "values": [
      [
        "2026-06-15",
        61.35,
        -3.86,
        8.92
      ],
      [
        "2026-06-16",
        60.9,
        -0.1,
        4.39
      ],
      [
        "2026-06-18",
        59.33,
        -1.4452,
        4.1855
      ],
      [
        "2026-06-22",
        60.25,
        1.55,
        4.97
      ],
      [
        "2026-06-23",
        null,
        null,
        null
      ],
      [
        "2026-06-25",
        57.9,
        -0.09,
        4.06
      ],
      [
        "2026-06-26",
        57.08,
        -1.42,
        4.4
      ],
      [
        "2026-07-01",
        58.5,
        0.31,
        5.65
      ],
      [
        "2026-07-07",
        56.69,
        -0.74,
        3.29
      ],
      [
        "2026-07-09",
        55.81,
        0.5,
        3.52
      ],
      [
        "2026-09-11",
        63.42,
        -1.45,
        5.9863
      ]
    ]
  },
  "failure_did_not_publish": true,
  "runs": {
    "apply": "a496e01bfb67",
    "verify": "ff3883c7babf"
  },
  "values_after": {
    "rows": 64,
    "non_null": {
      "close": 64,
      "pct_chg": 64,
      "amount": 64
    },
    "identical_adjacent_values": [],
    "values": [
      [
        "2026-06-15",
        61.35,
        -3.86,
        8.92
      ],
      [
        "2026-06-16",
        60.9,
        -0.1,
        4.39
      ],
      [
        "2026-06-17",
        60.2,
        -1.15,
        4.8761
      ],
      [
        "2026-06-18",
        59.33,
        -1.4452,
        4.1855
      ],
      [
        "2026-06-22",
        60.25,
        1.55,
        4.97
      ],
      [
        "2026-06-23",
        58.41,
        -3.05,
        4.0741
      ],
      [
        "2026-06-24",
        57.95,
        -0.79,
        3.3992
      ],
      [
        "2026-06-25",
        57.9,
        -0.09,
        4.06
      ],
      [
        "2026-06-26",
        57.08,
        -1.42,
        4.4
      ],
      [
        "2026-06-29",
        57.34,
        0.46,
        3.802
      ],
      [
        "2026-06-30",
        58.32,
        1.71,
        4.5924
      ],
      [
        "2026-07-01",
        58.5,
        0.31,
        5.65
      ],
      [
        "2026-07-02",
        56.85,
        -2.82,
        5.1207
      ],
      [
        "2026-07-03",
        58.71,
        3.27,
        6.1253
      ],
      [
        "2026-07-06",
        57.11,
        -2.73,
        4.1294
      ],
      [
        "2026-07-07",
        56.69,
        -0.74,
        3.29
      ],
      [
        "2026-07-08",
        55.53,
        -2.05,
        3.1527
      ],
      [
        "2026-07-09",
        55.81,
        0.5,
        3.52
      ],
      [
        "2026-07-10",
        57.1,
        2.31,
        6.4238
      ],
      [
        "2026-07-13",
        54.16,
        -5.15,
        4.6114
      ],
      [
        "2026-07-14",
        52.52,
        -3.03,
        3.9136
      ],
      [
        "2026-07-15",
        53.23,
        1.35,
        2.8962
      ],
      [
        "2026-07-16",
        53.37,
        0.26,
        3.6165
      ],
      [
        "2026-07-17",
        52.91,
        -0.86,
        3.8339
      ],
      [
        "2026-07-20",
        55.23,
        4.38,
        5.7983
      ],
      [
        "2026-07-21",
        55.1,
        -0.24,
        4.7251
      ],
      [
        "2026-07-22",
        56.34,
        2.25,
        5.0247
      ],
      [
        "2026-07-23",
        57.69,
        2.4,
        4.9183
      ],
      [
        "2026-07-24",
        55.69,
        -3.47,
        6.586
      ],
      [
        "2026-07-27",
        56.91,
        2.19,
        5.108
      ],
      [
        "2026-07-28",
        56.94,
        0.05,
        4.0027
      ],
      [
        "2026-07-29",
        58.43,
        2.62,
        5.0001
      ],
      [
        "2026-07-30",
        58.74,
        0.53,
        4.9278
      ],
      [
        "2026-07-31",
        58.52,
        -0.37,
        5.0936
      ],
      [
        "2026-08-03",
        57.9,
        -1.06,
        3.144
      ],
      [
        "2026-08-04",
        57.99,
        0.16,
        3.0924
      ],
      [
        "2026-08-05",
        57.97,
        -0.03,
        3.1683
      ],
      [
        "2026-08-06",
        57.85,
        -0.21,
        2.9537
      ],
      [
        "2026-08-07",
        56.96,
        -1.54,
        3.8938
      ],
      [
        "2026-08-10",
        59.78,
        4.95,
        6.7946
      ],
      [
        "2026-08-11",
        58.16,
        -2.71,
        4.8347
      ],
      [
        "2026-08-12",
        57.89,
        -0.46,
        2.4302
      ],
      [
        "2026-08-13",
        57.48,
        -0.71,
        3.9343
      ],
      [
        "2026-08-14",
        58.0,
        0.9,
        5.916
      ],
      [
        "2026-08-17",
        59.4,
        2.41,
        6.801
      ],
      [
        "2026-08-18",
        60.06,
        1.11,
        5.4282
      ],
      [
        "2026-08-19",
        57.02,
        -5.06,
        5.6508
      ],
      [
        "2026-08-20",
        57.09,
        0.12,
        2.54
      ],
      [
        "2026-08-21",
        56.84,
        -0.44,
        2.5404
      ],
      [
        "2026-08-24",
        56.7,
        -0.25,
        3.3667
      ],
      [
        "2026-08-25",
        56.08,
        -1.09,
        2.4168
      ],
      [
        "2026-08-26",
        57.67,
        2.84,
        4.4896
      ],
      [
        "2026-08-27",
        59.71,
        3.54,
        6.6239
      ],
      [
        "2026-08-28",
        60.0,
        0.49,
        4.751
      ],
      [
        "2026-08-31",
        59.7,
        -0.5,
        3.9912
      ],
      [
        "2026-09-01",
        60.76,
        1.78,
        5.9595
      ],
      [
        "2026-09-02",
        63.4,
        4.34,
        17.741
      ],
      [
        "2026-09-03",
        63.75,
        0.55,
        9.6373
      ],
      [
        "2026-09-04",
        63.3,
        -0.71,
        7.3896
      ],
      [
        "2026-09-07",
        61.33,
        -3.11,
        6.2797
      ],
      [
        "2026-09-08",
        62.21,
        1.43,
        5.0617
      ],
      [
        "2026-09-09",
        65.15,
        4.73,
        10.9634
      ],
      [
        "2026-09-10",
        64.35,
        -1.23,
        6.3409
      ],
      [
        "2026-09-11",
        63.42,
        -1.45,
        5.9863
      ]
    ]
  },
  "rollback_copy": {
    "method": "clonefile",
    "seconds": 0.004,
    "bytes": 10235904
  },
  "rollback_sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "production_after": {
    "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/inputs/production-slice.duckdb",
    "size": 10235904,
    "mtime_ns": 1790312094648034916,
    "inode": 268857548,
    "freshness": {
      "fact_auction_hithink": "None",
      "fact_auction_stock_daily": "None",
      "fact_core_leader_daily": "None",
      "fact_core_stock_daily": "None",
      "fact_dragon_hot_money_hithink": "None",
      "fact_dragon_seat_daily": "None",
      "fact_dragon_summary_daily": "None",
      "fact_dragon_tiger_daily": "None",
      "fact_dragon_tiger_hithink": "None",
      "fact_global_index_daily": "None",
      "fact_global_stock_daily": "None",
      "fact_hot_stock_rank_hithink": "None",
      "fact_leader_height_daily": "None",
      "fact_limit_advance_daily": "None",
      "fact_limit_advance_presence": "None",
      "fact_limit_pool_hithink": "None",
      "fact_mainline_sector_daily": "None",
      "fact_mainline_stock_daily": "None",
      "fact_mainline_theme_daily": "None",
      "fact_market_daily": "2026-09-22",
      "fact_polymarket_macro_odds_daily": "None",
      "fact_sector_daily": "None",
      "fact_sector_daily_generation": "None",
      "fact_sector_kline_daily": "None",
      "fact_sector_period_rank_daily": "None",
      "fact_sector_stock_daily": "2026-09-18",
      "fact_sector_stock_daily_generation": "2026-09-18",
      "fact_sector_universe_daily": "None",
      "fact_stock_daily": "2026-09-22",
      "fact_stock_daily_hithink": "2026-09-22",
      "fact_stock_high_daily": "None",
      "fact_stock_technical_snapshot": "None",
      "fact_sw_l1_daily": "None",
      "fact_theme_flow_daily": "None",
      "fact_theme_limit_heat_daily": "None",
      "fact_theme_limit_stock_daily": "None"
    }
  },
  "production_unchanged": true,
  "production_sha256_after": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "code_identity_after": [
    "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
    false
  ],
  "removed_rehearsal_copies": [
    {
      "name": "baseline.duckdb",
      "sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
      "bytes": 10235904
    },
    {
      "name": "copy.duckdb",
      "sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
      "bytes": 10235904
    },
    {
      "name": "copy.duckdb.bak-20260925T125823-a496e01bfb67",
      "sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
      "bytes": 10235904
    },
    {
      "name": "copy.duckdb.bak-20260925T125825-ff3883c7babf",
      "sha256": "087fe4d9cf3c1f6dad650976615526a2e972ea4e9652e3bcc14b6b4eb5e9cfcc",
      "bytes": 14954496
    }
  ],
  "free_bytes_after": 44999065600
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json
```text
{
  "verdict": "PASS",
  "expected_revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "runs": {
    "apply": "a496e01bfb67",
    "verify": "ff3883c7babf"
  },
  "checks": [
    {
      "name": "args_expected_revision_format",
      "ok": true,
      "detail": "ae3f812e1c1e142953b657ba41f30fce23e7c14a"
    },
    {
      "name": "args_expected_production_sha256_format",
      "ok": true,
      "detail": ""
    },
    {
      "name": "args_run_ids_distinct_nonempty",
      "ok": true,
      "detail": {
        "apply": "a496e01bfb67",
        "verify": "ff3883c7babf"
      }
    },
    {
      "name": "inputs_regular_files",
      "ok": true,
      "detail": []
    },
    {
      "name": "clone_is_not_production_alias",
      "ok": true,
      "detail": {
        "production": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "clone": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb"
      }
    },
    {
      "name": "production_sha256_before",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "receipt_apply_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipt_verify_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipts_apply_verify_present",
      "ok": true,
      "detail": [
        "apply",
        "verify"
      ]
    },
    {
      "name": "receipt_apply_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_verify_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_apply_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "receipt_verify_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "backup_apply_identity",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "backup_verify_identity",
      "ok": true,
      "detail": {
        "expected": "087fe4d9cf3c1f6d",
        "actual": "087fe4d9cf3c1f6d"
      }
    },
    {
      "name": "backup_apply_matches_baseline",
      "ok": true,
      "detail": "apply 备份 sha == 基线 sha（换库前生产身份）"
    },
    {
      "name": "spec_alignment_apply_verify",
      "ok": true,
      "detail": "apply/verify 授权 spec 深比较（同输入同合同前提）"
    },
    {
      "name": "parquet_readable",
      "ok": true,
      "detail": "51f9ee9cba1ceb4a"
    },
    {
      "name": "parquet_identity_apply",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "parquet_identity_verify",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "fact_other_stocks_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "retained_rows_full_column_identical",
      "ok": true,
      "detail": {
        "rows": 10,
        "expected": 10
      }
    },
    {
      "name": "target_outside_window_allcols",
      "ok": true,
      "detail": [
        0,
        0
      ]
    },
    {
      "name": "hithink_source_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "hithink_adjustment_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "parallel_source_md5_binding",
      "ok": true,
      "detail": {
        "recomputed": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "rows": 62,
        "apply": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "verify": "2ddb4224900b3b8e30a85ac0c9b89ffc"
      }
    },
    {
      "name": "keyset_fullfield_oracle",
      "ok": true,
      "detail": {
        "rows": 54,
        "keys": 54,
        "bad": []
      }
    },
    {
      "name": "technical_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_golden_triples",
      "ok": true,
      "detail": {
        "actual": 161,
        "golden": 161
      }
    },
    {
      "name": "expected_window_counts_match_golden",
      "ok": true,
      "detail": {
        "golden": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        },
        "spec": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        }
      }
    },
    {
      "name": "technical_exact_set",
      "ok": true,
      "detail": 39
    },
    {
      "name": "expected_technical_count_matches_calendar",
      "ok": true,
      "detail": {
        "spec": 39,
        "calendar": 39
      }
    },
    {
      "name": "pinned_technical_target_day",
      "ok": true,
      "detail": [
        59.8542,
        2.6845,
        61.9052,
        2.45
      ]
    },
    {
      "name": "pinned_windows_target_day",
      "ok": true,
      "detail": ""
    },
    {
      "name": "market_daily_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "production_sha256_after",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    }
  ],
  "failed": []
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json
```text
{
  "verdict": "FAIL",
  "expected_revision": "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
  "runs": {
    "apply": "a496e01bfb67",
    "verify": "ff3883c7babf"
  },
  "checks": [
    {
      "name": "args_expected_revision_format",
      "ok": true,
      "detail": "ae3f812e1c1e142953b657ba41f30fce23e7c14a"
    },
    {
      "name": "args_expected_production_sha256_format",
      "ok": true,
      "detail": ""
    },
    {
      "name": "args_run_ids_distinct_nonempty",
      "ok": true,
      "detail": {
        "apply": "a496e01bfb67",
        "verify": "ff3883c7babf"
      }
    },
    {
      "name": "inputs_regular_files",
      "ok": true,
      "detail": []
    },
    {
      "name": "clone_is_not_production_alias",
      "ok": true,
      "detail": {
        "production": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "clone": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb"
      }
    },
    {
      "name": "production_sha256_before",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "receipt_apply_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipt_verify_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipts_apply_verify_present",
      "ok": true,
      "detail": [
        "apply",
        "verify"
      ]
    },
    {
      "name": "receipt_apply_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_verify_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_apply_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "receipt_verify_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "backup_apply_identity",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "backup_verify_identity",
      "ok": true,
      "detail": {
        "expected": "087fe4d9cf3c1f6d",
        "actual": "087fe4d9cf3c1f6d"
      }
    },
    {
      "name": "backup_apply_matches_baseline",
      "ok": true,
      "detail": "apply 备份 sha == 基线 sha（换库前生产身份）"
    },
    {
      "name": "spec_alignment_apply_verify",
      "ok": true,
      "detail": "apply/verify 授权 spec 深比较（同输入同合同前提）"
    },
    {
      "name": "parquet_readable",
      "ok": true,
      "detail": "51f9ee9cba1ceb4a"
    },
    {
      "name": "parquet_identity_apply",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "parquet_identity_verify",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "fact_other_stocks_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "retained_rows_full_column_identical",
      "ok": true,
      "detail": {
        "rows": 10,
        "expected": 10
      }
    },
    {
      "name": "target_outside_window_allcols",
      "ok": true,
      "detail": [
        0,
        0
      ]
    },
    {
      "name": "hithink_source_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "hithink_adjustment_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "parallel_source_md5_binding",
      "ok": true,
      "detail": {
        "recomputed": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "rows": 62,
        "apply": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "verify": "2ddb4224900b3b8e30a85ac0c9b89ffc"
      }
    },
    {
      "name": "keyset_fullfield_oracle",
      "ok": false,
      "detail": {
        "rows": 54,
        "keys": 54,
        "bad": [
          "2026-06-17"
        ]
      }
    },
    {
      "name": "technical_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_golden_triples",
      "ok": true,
      "detail": {
        "actual": 161,
        "golden": 161
      }
    },
    {
      "name": "expected_window_counts_match_golden",
      "ok": true,
      "detail": {
        "golden": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        },
        "spec": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        }
      }
    },
    {
      "name": "technical_exact_set",
      "ok": true,
      "detail": 39
    },
    {
      "name": "expected_technical_count_matches_calendar",
      "ok": true,
      "detail": {
        "spec": 39,
        "calendar": 39
      }
    },
    {
      "name": "pinned_technical_target_day",
      "ok": true,
      "detail": [
        59.8542,
        2.6845,
        61.9052,
        2.45
      ]
    },
    {
      "name": "pinned_windows_target_day",
      "ok": true,
      "detail": ""
    },
    {
      "name": "market_daily_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "production_sha256_after",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    }
  ],
  "failed": [
    "keyset_fullfield_oracle"
  ]
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.command.json
```text
{
  "label": "acceptance",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate/scripts/verify_302132_backfill_acceptance.py",
    "--production",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
    "--clone",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
    "--run-apply",
    "a496e01bfb67",
    "--run-verify",
    "ff3883c7babf",
    "--expected-revision",
    "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
    "--expected-production-sha256",
    "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
    "--output",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json"
  ],
  "expected_exit": 0,
  "exit_code": 0,
  "seconds": 0.354
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.command.json
```text
{
  "label": "amount-control",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/candidate/scripts/verify_302132_backfill_acceptance.py",
    "--production",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
    "--clone",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
    "--run-apply",
    "a496e01bfb67",
    "--run-verify",
    "ff3883c7babf",
    "--expected-revision",
    "ae3f812e1c1e142953b657ba41f30fce23e7c14a",
    "--expected-production-sha256",
    "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
    "--output",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json"
  ],
  "expected_exit": 2,
  "exit_code": 2,
  "seconds": 0.414
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/apply.command.json
```text
{
  "label": "apply",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "-m",
    "market_feature_store.cli",
    "repair-backfill-302132",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
  ],
  "expected_exit": 0,
  "exit_code": 0,
  "seconds": 1.273
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/refused-parent.command.json
```text
{
  "label": "refused-parent",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "-m",
    "market_feature_store.cli",
    "repair-backfill-302132",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/wrong.parquet"
  ],
  "expected_exit": 2,
  "exit_code": 2,
  "seconds": 0.374
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/verify.command.json
```text
{
  "label": "verify",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "-m",
    "market_feature_store.cli",
    "repair-backfill-302132",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-19/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
  ],
  "expected_exit": 0,
  "exit_code": 0,
  "seconds": 1.275
}

```
