"""同花顺 dump 重建 canonical ``fact_stock_daily`` 单日（2026-09-11 东财快照修复）。

背景与审查：仓外运行目录 ``~/.finance-runtime/db-repair/hithink-20260911/``
的 ``review.md``（QC 修订要求）与 ``repair-plan.md``（处置表与干跑证据）。
东财快照 09-11 缺口由同花顺官方 ``daily-k-10d`` dump 重建；本模块只做
build（构造 + 断言）与 apply（单事务写入），落库走
``sync_daily_full.run_daily_full_staged`` 的 staging 原子换库，不直写生产。

字段映射（dump → canonical，全量真实数据验证过）：

- ``open/high/low/close`` = dump 直给（共同行 5,549/5,549 精确一致）
- ``pre_close`` = dump 昨日 close；除息日改用
  ``round(DECIMAL 昨裸收 − dividend_per_share, 2)``（复权事件表，
  纯现金分红才允许；送转/配股非 0 拒跑）
- ``pct_chg`` = ``round_half_up((close/pre_close − 1)*100, 2)``，DECIMAL 链路
  （二进制浮点 round 会在 .xx5 边界错 0.01：688218/688450/300127/603300/600733
  五行实测，DECIMAL 半进后 5,530/5,530 复现旧值）
- ``amount``（亿）= ``round_half_up(turnover / 1e8, 4)``，列约定四位小数
- ``volume``（手）= ``round_half_up(volume / 100, 0)``，列约定整数手
- ``stock_name`` / ``turnover``（换手率）dump 不提供 → 从旧行保留，不清空；
  新增票 name 取库内历史名并与 spec 交叉断言，turnover=NULL 并在报告声明
- ``source``：重建行 ``hithink:daily-k-10d``；保留行维持 ``eastmoney:snapshot``
  （不改标签冒充换源）

2026-09-11 差异处置表（SPEC_20260911，每条都有审查依据）：

- 3 只北交所量额双差异（920045/920161/920375）：原因未核实，整行保留 + 声明
- 3 只旧独有（688291/688432/688496）：停牌形态（close=pre_close、amount NULL），
  dump 正确地不含；保留原行 + 声明
- 688801.SH：09-11 上市新股，dump 窗口内无昨日 bar；pre_close=142.18 /
  pct_chg=179.22 保留发行价口径，OHLCV/amount 用 dump（已验证一致）
- 302132.SZ（中航成飞）：东财快照漏收（dump 08-31~09-11 连续 10 根 bar、
  旧表 07-09 后无行、09-11 无除息事件）；新增行，pre_close=dump 09-10 close 64.35
- 600176.SH：amount 两源差 5,000.42 元（万元级），换源后取 dump 值
  round4=113.6006；列进白名单，不与北交所三只同级
- 18 条除息行：pre_close/pct_chg 用 dump + 复权事件表重建，断言逐行 == 旧值

断言全部 fail closed：名单、计数、逐字段 diff 超出白名单即抛 ``RepairRefused``，
不进入写入。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from .sync_hithink_stock_daily import TRADE_DATE_SQL

SOURCE_REBUILD = "hithink:daily-k-10d"


class RepairRefused(RuntimeError):
    """构建期断言不通过：拒跑，未写入。消息必须带可追的明细。"""


_CODE_RE = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")


def _check_codes(codes: tuple[str, ...], what: str) -> None:
    for c in codes:
        if not _CODE_RE.match(c):
            raise RepairRefused(f"{what} 含非法代码 {c!r}")


@dataclass(frozen=True)
class RepairSpec:
    """单日修复的名单与期望值。每个交易日一份，防止脚本被误用到别的日期。"""

    trade_date: date
    keep_codes: tuple[str, ...]          # 量额双差异，整行保留
    suspended_keep: tuple[str, ...]      # dump 不含的旧行（停牌），保留
    issue_price_codes: tuple[str, ...]   # pre_close/pct_chg 保留发行价口径（IPO）
    new_code_names: dict[str, str]       # dump 有旧表无 → 新增行 {code: name}
    exdiv_codes: tuple[str, ...]         # 当日除息（事件表）应命中的代码集合
    amount_drift_ok: dict[str, float]    # 换源可接受的 amount 漂移上限（亿）
    expected: dict[str, int]             # dump_rows / old_rows / common_rows / written_rows / final_rows
    parquet_sha256: str = ""             # 审查钉住的 dump 哈希；空串=不校验（仅测试夹具）

    def validate(self) -> None:
        _check_codes(self.keep_codes, "keep_codes")
        _check_codes(self.suspended_keep, "suspended_keep")
        _check_codes(self.issue_price_codes, "issue_price_codes")
        _check_codes(tuple(self.new_code_names), "new_code_names")
        _check_codes(self.exdiv_codes, "exdiv_codes")
        _check_codes(tuple(self.amount_drift_ok), "amount_drift_ok")


SPEC_20260911 = RepairSpec(
    trade_date=date(2026, 9, 11),
    keep_codes=("920045.BJ", "920161.BJ", "920375.BJ"),
    suspended_keep=("688291.SH", "688432.SH", "688496.SH"),
    issue_price_codes=("688801.SH",),
    new_code_names={"302132.SZ": "中航成飞"},
    exdiv_codes=(
        "001267.SZ", "002353.SZ", "300286.SZ", "301108.SZ", "301239.SZ",
        "600309.SH", "600750.SH", "601016.SH", "601058.SH", "603456.SH",
        "603520.SH", "603600.SH", "603697.SH", "603868.SH", "603998.SH",
        "605118.SH", "605305.SH", "920096.BJ",
    ),
    amount_drift_ok={"600176.SH": 0.0001},
    expected={
        "dump_rows": 5550,
        "old_rows": 5552,
        "common_rows": 5549,
        "written_rows": 5547,   # 5549 共同 − 3 整行保留 + 1 新增
        "final_rows": 5553,     # 5552 − 5546 被替换 + 5547 写入
    },
    parquet_sha256="51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17",
)


def _load_whitelists(con: duckdb.DuckDBPyConnection, spec: RepairSpec) -> None:
    """白名单落 TEMP TABLE，SQL 里不拼字面量。"""

    con.execute("CREATE TEMP TABLE wl_keep (code VARCHAR)")
    con.executemany("INSERT INTO wl_keep VALUES (?)", [(c,) for c in spec.keep_codes])
    con.execute("CREATE TEMP TABLE wl_issue (code VARCHAR)")
    con.executemany(
        "INSERT INTO wl_issue VALUES (?)", [(c,) for c in spec.issue_price_codes]
    )
    con.execute("CREATE TEMP TABLE wl_new (code VARCHAR, name VARCHAR)")
    con.executemany(
        "INSERT INTO wl_new VALUES (?, ?)", sorted(spec.new_code_names.items())
    )


def _fail(what: str, rows: list, limit: int = 20) -> None:
    shown = rows[:limit]
    raise RepairRefused(
        f"{what}: {len(rows)} 行"
        + (f"，样本: {shown}" if shown else "")
        + ("…" if len(rows) > limit else "")
    )


def build_plan(
    con: duckdb.DuckDBPyConnection,
    spec: RepairSpec,
    parquet_path: Path,
) -> dict[str, Any]:
    """在 con（staging/克隆库）上构建修复行，全部断言过了才返回。

    产出 TEMP 表 ``repair_rows``（待写入）与证据 dict。
    任何名单/计数/字段 diff 越白名单 → RepairRefused，未写入。
    """

    spec.validate()
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        raise RepairRefused(f"parquet 不存在: {parquet_path}")
    sha = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    if spec.parquet_sha256 and sha != spec.parquet_sha256:
        raise RepairRefused(
            f"parquet 哈希与审查钉住值不符: {sha} != {spec.parquet_sha256}"
        )

    td = spec.trade_date.isoformat()
    _load_whitelists(con, spec)
    con.execute(
        f"""
        CREATE TEMP TABLE repair_inc AS
        SELECT {TRADE_DATE_SQL} AS trade_date, *
        FROM read_parquet(?)
        WHERE currency = 'CNY' AND interval = '1d'
        """,
        [str(parquet_path)],
    )
    # 复权口径探测：adjusted 只能是 none（否则 pre_close 校准语义整套不成立）。
    adjusted = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT adjusted FROM repair_inc WHERE trade_date = ?", [td]
        ).fetchall()
    ]
    if adjusted != ["none"]:
        raise RepairRefused(f"dump adjusted 口径不是 none: {adjusted}")

    con.execute(
        """
        CREATE TEMP TABLE repair_lag AS
        SELECT *, lag(close_price) OVER (
            PARTITION BY thscode ORDER BY trade_date
        ) AS prev_close_dump
        FROM repair_inc
        """
    )
    con.execute(
        "CREATE TEMP TABLE repair_old AS "
        "SELECT * FROM fact_stock_daily WHERE trade_date = ?",
        [td],
    )
    # 除息必须纯现金：当日事件表里有、但送转/配股非 0 的代码 → 拒跑。
    non_cash = [
        r[0]
        for r in con.execute(
            """
            SELECT stock_ts_code FROM fact_stock_adjustment_hithink
            WHERE ex_date = ?
              AND (coalesce(per_share_bonus, 0) <> 0
                   OR coalesce(allotment_ratio, 0) <> 0)
            """,
            [td],
        ).fetchall()
    ]
    if non_cash:
        raise RepairRefused(f"当日存在非纯现金除权事件, 校准公式不覆盖: {non_cash}")
    con.execute(
        """
        CREATE TEMP TABLE repair_adj AS
        SELECT stock_ts_code, dividend_per_share
        FROM fact_stock_adjustment_hithink
        WHERE ex_date = ?
        """,
        [td],
    )

    counts = con.execute(
        """
        WITH d AS (SELECT * FROM repair_lag WHERE trade_date = ?)
        SELECT
          (SELECT count(*) FROM d) AS dump_rows,
          (SELECT count(*) FROM repair_old) AS old_rows,
          (SELECT count(*) FROM d JOIN repair_old o ON o.stock_ts_code = d.thscode)
            AS common_rows
        """,
        [td],
    ).fetchone()
    exp = spec.expected
    for got, want, name in (
        (counts[0], exp["dump_rows"], "dump_rows"),
        (counts[1], exp["old_rows"], "old_rows"),
        (counts[2], exp["common_rows"], "common_rows"),
    ):
        if got != want:
            raise RepairRefused(f"{name}={got} ≠ 期望 {want}——名单漂移，拒跑")

    old_only = sorted(
        r[0]
        for r in con.execute(
            """
            SELECT o.stock_ts_code FROM repair_old o
            WHERE o.stock_ts_code NOT IN (
                SELECT thscode FROM repair_lag WHERE trade_date = ?)
            ORDER BY 1
            """,
            [td],
        ).fetchall()
    )
    if old_only != sorted(spec.suspended_keep):
        _fail("旧独有名单 ≠ 停牌保留白名单", [(c,) for c in old_only])
    new_only = sorted(
        r[0]
        for r in con.execute(
            """
            SELECT d.thscode FROM repair_lag d
            WHERE d.trade_date = ? AND d.thscode NOT IN (
                SELECT stock_ts_code FROM repair_old)
            ORDER BY 1
            """,
            [td],
        ).fetchall()
    )
    if new_only != sorted(spec.new_code_names):
        _fail("dump 独有名单 ≠ 新增白名单", [(c,) for c in new_only])
    keep_not_common = [
        r[0]
        for r in con.execute(
            """
            SELECT code FROM wl_keep
            WHERE code NOT IN (
                SELECT d.thscode FROM repair_lag d
                JOIN repair_old o ON o.stock_ts_code = d.thscode
                WHERE d.trade_date = ?)
            """,
            [td],
        ).fetchall()
    ]
    if keep_not_common:
        raise RepairRefused(f"整行保留白名单不在共同行里: {keep_not_common}")

    # 除息名单断言：当日事件 ∩ 共同行 == spec.exdiv_codes。
    exdiv_hit = sorted(
        r[0]
        for r in con.execute(
            """
            SELECT a.stock_ts_code FROM repair_adj a
            WHERE a.stock_ts_code IN (
                SELECT d.thscode FROM repair_lag d
                JOIN repair_old o ON o.stock_ts_code = d.thscode
                WHERE d.trade_date = ?)
            ORDER BY 1
            """,
            [td],
        ).fetchall()
    )
    if exdiv_hit != sorted(spec.exdiv_codes):
        _fail("除息名单与 spec 不符", [(c,) for c in exdiv_hit])

    # dump 窗口内无昨日 bar 的共同行 == 发行价口径白名单（IPO）。
    no_prev = sorted(
        r[0]
        for r in con.execute(
            """
            SELECT d.thscode FROM repair_lag d
            JOIN repair_old o ON o.stock_ts_code = d.thscode
            WHERE d.trade_date = ? AND d.prev_close_dump IS NULL
            ORDER BY 1
            """,
            [td],
        ).fetchall()
    )
    if no_prev != sorted(spec.issue_price_codes):
        _fail("dump 无昨日 bar 的共同行 ≠ 发行价口径白名单", [(c,) for c in no_prev])

    # 新增票名字交叉断言：库内历史有名字则必须等于 spec。
    hist_name_bad = [
        (r[0], r[1], spec.new_code_names.get(r[0]))
        for r in con.execute(
            """
            SELECT n.code,
                   (SELECT o.stock_name FROM fact_stock_daily o
                    WHERE o.stock_ts_code = n.code AND o.stock_name IS NOT NULL
                    ORDER BY o.trade_date DESC LIMIT 1) AS hist_name
            FROM wl_new n
            """
        ).fetchall()
        if r[1] is not None and r[1] != spec.new_code_names.get(r[0])
    ]
    if hist_name_bad:
        _fail("新增票 spec 名字 ≠ 库内历史名", hist_name_bad)

    # 构造待写入行。pre_close/pct_chg 全 DECIMAL 链（半进），与旧口径逐行相等才算过。
    con.execute(
        """
        CREATE TEMP TABLE repair_rows AS
        WITH d AS (
            SELECT * FROM repair_lag WHERE trade_date = ?
        ),
        base AS (
            SELECT
                d.thscode AS code,
                d.close_price AS close_d,
                d.open_price AS open_d,
                d.high_price AS high_d,
                d.low_price AS low_d,
                d.volume AS volume_shares,
                d.turnover AS turnover_yuan,
                o.stock_name AS old_name,
                o.turnover AS old_turnover_rate,
                o.pre_close AS old_pre_close,
                o.pct_chg AS old_pct_chg,
                CASE
                    WHEN ip.code IS NOT NULL THEN CAST(o.pre_close AS DECIMAL(18,2))
                    WHEN a.stock_ts_code IS NOT NULL THEN round(
                        CAST(d.prev_close_dump AS DECIMAL(18,2))
                        - CAST(a.dividend_per_share AS DECIMAL(38,10)), 2)
                    ELSE CAST(d.prev_close_dump AS DECIMAL(18,2))
                END AS pre_close_dec
            FROM d
            LEFT JOIN repair_old o ON o.stock_ts_code = d.thscode
            LEFT JOIN repair_adj a ON a.stock_ts_code = d.thscode
            LEFT JOIN wl_issue ip ON ip.code = d.thscode
            WHERE d.thscode NOT IN (SELECT code FROM wl_keep)
        )
        SELECT
            CAST(? AS DATE) AS trade_date,
            base.code AS stock_ts_code,
            coalesce(old_name, n.name) AS stock_name,
            close_d AS close,
            CAST(pre_close_dec AS DOUBLE) AS pre_close,
            CASE
                WHEN pre_close_dec IS NULL THEN old_pct_chg  -- 发行价口径: pct 保留旧值
                ELSE CAST(round(CAST(
                    (CAST(close_d AS DECIMAL(18,4)) / pre_close_dec - 1) * 100
                    AS DECIMAL(38,12)), 2) AS DOUBLE)
            END AS pct_chg,
            CAST(round(CAST(turnover_yuan AS DECIMAL(38,2)) / 100000000, 4) AS DOUBLE)
                AS amount,
            old_turnover_rate AS turnover,
            ? AS source,
            current_timestamp AS updated_at,
            open_d AS open,
            high_d AS high,
            low_d AS low,
            CAST(round(CAST(volume_shares AS DECIMAL(38,0)) / 100, 0) AS DOUBLE)
                AS volume
        FROM base
        LEFT JOIN wl_new n ON n.code = base.code
        """,
        [td, td, SOURCE_REBUILD],
    )

    # ---- 逐字段 diff 断言（重建行 vs 旧行，共同行部分）----
    diff_sql = """
        WITH cmp AS (
            SELECT r.stock_ts_code AS code, r.close AS new_close, o.close AS old_close,
                   r.open AS new_open, o.open AS old_open,
                   r.high AS new_high, o.high AS old_high,
                   r.low AS new_low, o.low AS old_low,
                   r.pre_close AS new_pre, o.pre_close AS old_pre,
                   r.pct_chg AS new_pct, o.pct_chg AS old_pct,
                   r.amount AS new_amt, o.amount AS old_amt,
                   r.volume AS new_vol, o.volume AS old_vol,
                   r.stock_name AS new_name, o.stock_name AS old_name,
                   r.turnover AS new_rate, o.turnover AS old_rate
            FROM repair_rows r JOIN repair_old o ON o.stock_ts_code = r.stock_ts_code
        )
        SELECT * FROM cmp WHERE {cond}
    """
    checks = {
        "ohlc": "new_close IS DISTINCT FROM old_close"
                " OR new_open IS DISTINCT FROM old_open"
                " OR new_high IS DISTINCT FROM old_high"
                " OR new_low IS DISTINCT FROM old_low",
        "pre_close": "new_pre IS DISTINCT FROM old_pre",
        "pct_chg": "new_pct IS DISTINCT FROM old_pct",
        "preserved": "new_name IS DISTINCT FROM old_name"
                     " OR new_rate IS DISTINCT FROM old_rate",
        # volume 换源单位换算后应逐行相等（北交所三只已整行保留在外）。
        "volume": "new_vol IS DISTINCT FROM old_vol",
    }
    evidence: dict[str, Any] = {"field_diffs": {}}
    for name, cond in checks.items():
        rows = con.execute(diff_sql.format(cond=cond)).fetchall()
        if rows:
            _fail(f"字段 {name} 重建值 ≠ 旧值", rows)
        evidence["field_diffs"][name] = 0

    drift_rows = con.execute(
        """
        SELECT r.stock_ts_code, o.amount AS old_amt, r.amount AS new_amt,
               CAST(r.amount AS DECIMAL(38,10)) - CAST(o.amount AS DECIMAL(38,10))
                   AS drift_dec
        FROM repair_rows r JOIN repair_old o ON o.stock_ts_code = r.stock_ts_code
        WHERE r.amount IS DISTINCT FROM o.amount
        """
    ).fetchall()
    allowed = spec.amount_drift_ok
    bad = [
        (c, old, new) for c, old, new, drift in drift_rows
        if c not in allowed or abs(drift) > Decimal(str(allowed[c]))
    ]
    if bad:
        _fail("amount 漂移越白名单", bad)
    evidence["field_diffs"]["amount"] = {
        c: {"old": old, "new": new} for c, old, new, _ in sorted(drift_rows)
    }

    written = con.execute("SELECT count(*) FROM repair_rows").fetchone()[0]
    if written != exp["written_rows"]:
        raise RepairRefused(f"written_rows={written} ≠ 期望 {exp['written_rows']}")

    evidence.update(
        {
            "parquet_sha256": sha,
            "trade_date": td,
            "counts": {
                "dump_rows": counts[0],
                "old_rows": counts[1],
                "common_rows": counts[2],
                "written_rows": written,
            },
            "old_only_kept": old_only,
            "new_inserted": new_only,
            "keep_codes_untouched": sorted(spec.keep_codes),
            "issue_price_kept": no_prev,
            "exdiv_rebuilt_equal_old": exdiv_hit,
        }
    )
    return evidence


# ---------------------------------------------------------------------------
# 指纹与写入
# ---------------------------------------------------------------------------

_FP_EXPR = (
    "coalesce(stock_ts_code, '∅') || '|' || coalesce(cast(close AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(pre_close AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(pct_chg AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(amount AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(turnover AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(volume AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(open AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(high AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(low AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(stock_name AS VARCHAR), '∅')"
    " || '|' || coalesce(cast(source AS VARCHAR), '∅')"
)


def fingerprint(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, Any]]:
    """fact_stock_daily 按日 行数 + 顺序无关哈希——「其他日期未动」的证据。"""

    rows = con.execute(
        f"""
        SELECT trade_date, count(*) AS n, sum(hash({_FP_EXPR})) AS h
        FROM fact_stock_daily GROUP BY trade_date ORDER BY 1
        """
    ).fetchall()
    return {str(r[0]): {"rows": r[1], "hash": str(r[2])} for r in rows}


def _kept_row_images(
    con: duckdb.DuckDBPyConnection, spec: RepairSpec
) -> dict[str, tuple]:
    codes = sorted(set(spec.keep_codes) | set(spec.suspended_keep))
    if not codes:
        return {}
    marks = ",".join("?" for _ in codes)
    rows = con.execute(
        f"""
        SELECT stock_ts_code, stock_name, close, pre_close, pct_chg, amount,
               turnover, source, open, high, low, volume
        FROM fact_stock_daily
        WHERE trade_date = ? AND stock_ts_code IN ({marks})
        ORDER BY stock_ts_code
        """,
        [spec.trade_date.isoformat(), *codes],
    ).fetchall()
    return {r[0]: r for r in rows}


def apply_plan(con: duckdb.DuckDBPyConnection, spec: RepairSpec) -> dict[str, Any]:
    """单事务落 repair_rows。保留行不在 repair_rows 里，天然不动。"""

    td = spec.trade_date.isoformat()
    con.execute("BEGIN TRANSACTION")
    try:
        deleted = con.execute(
            "DELETE FROM fact_stock_daily WHERE trade_date = ? "
            "AND stock_ts_code IN (SELECT stock_ts_code FROM repair_rows) "
            "RETURNING stock_ts_code",
            [td],
        ).fetchall()
        con.execute(
            """
            INSERT INTO fact_stock_daily
                (trade_date, stock_ts_code, stock_name, close, pre_close,
                 pct_chg, amount, turnover, source, updated_at,
                 open, high, low, volume)
            SELECT trade_date, stock_ts_code, stock_name, close, pre_close,
                   pct_chg, amount, turnover, source, updated_at,
                   open, high, low, volume
            FROM repair_rows
            """
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"deleted_replaced": len(deleted)}


def verify_post(
    con: duckdb.DuckDBPyConnection,
    spec: RepairSpec,
    before_fp: dict[str, dict[str, Any]],
    after_fp: dict[str, dict[str, Any]],
    kept_before: dict[str, tuple],
) -> dict[str, Any]:
    """写入后闸：其他日期指纹逐日相等；保留行逐字段相等；当日行数达标。"""

    td = spec.trade_date.isoformat()
    drift = sorted(
        d for d in before_fp if d != td and before_fp[d] != after_fp.get(d)
    )
    gone = sorted(d for d in before_fp if d not in after_fp)
    born = sorted(d for d in after_fp if d not in before_fp)
    if drift or gone or born:
        raise RepairRefused(
            f"其他日期被改动: drift={drift[:10]} gone={gone[:10]} born={born[:10]}"
        )
    kept_after = _kept_row_images(con, spec)
    if kept_before != kept_after:
        changed = sorted(
            c for c in kept_before if kept_before[c] != kept_after.get(c)
        )
        raise RepairRefused(f"保留行被改动: {changed}")
    final_rows = after_fp.get(td, {}).get("rows")
    if final_rows != spec.expected["final_rows"]:
        raise RepairRefused(
            f"当日行数={final_rows} ≠ 期望 {spec.expected['final_rows']}"
        )
    empty = con.execute(
        "SELECT count(*) FROM fact_stock_daily "
        "WHERE trade_date = ? AND (stock_name IS NULL OR close IS NULL)",
        [td],
    ).fetchone()[0]
    if empty:
        raise RepairRefused(f"当日存在 name/close 为空的行: {empty}")
    return {
        "other_dates_unchanged": True,
        "kept_rows_identical": sorted(kept_before),
        "final_rows": final_rows,
    }


def run_repair(
    spec: RepairSpec,
    parquet_path: Path,
    *,
    db_path: Path | str | None = None,
    status_json: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """修复子进程入口：连目标库（staging 或显式克隆），build → apply → verify。

    目标解析顺序：显式 db_path > MARKET_FEATURE_STORE_DB > 包默认 DB_PATH。
    生产库直写由调用方（cli 子命令）的 write_path 闸门拦；函数层保持可在
    测试里直用。
    """

    from ..db import DB_PATH

    target = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB") or DB_PATH)
    started = datetime.now()
    con = duckdb.connect(str(target))
    try:
        before_fp = fingerprint(con)
        kept_before = _kept_row_images(con, spec)
        evidence = build_plan(con, spec, Path(parquet_path))
        applied = apply_plan(con, spec)
        after_fp = fingerprint(con)
        post = verify_post(con, spec, before_fp, after_fp, kept_before)
    finally:
        con.close()

    report: dict[str, Any] = {
        "kind": "repair-stock-daily-hithink",
        "trade_date": spec.trade_date.isoformat(),
        "target_db": str(target),
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "ok": True,
        "evidence": evidence,
        "applied": applied,
        "post": post,
        "fingerprint_target_date": after_fp.get(spec.trade_date.isoformat()),
    }
    if report_path is not None:
        Path(report_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    if status_json is not None:
        Path(status_json).write_text(
            json.dumps(
                {
                    "trade_date": spec.trade_date.isoformat(),
                    "ok": True,
                    "steps": [
                        {
                            "name": "repair-stock-daily-hithink",
                            "ok": True,
                            "elapsed_s": None,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return report
