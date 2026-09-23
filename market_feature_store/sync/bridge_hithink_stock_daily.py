"""桥：``fact_stock_daily_hithink`` → canonical ``fact_stock_daily``（整日 0 行的日子）。

为什么需要这座桥（2026-09-22 复盘）
------------------------------------
``fact_stock_daily`` 的喂给源在 2026-09-07 之后塌了：mootdx 被供应商停供，
东财快照与 fallback 时好时坏。而它一旦缺当日行，夜跑的 13 个下游步骤会全塌
（``feature_stock_window`` 算出空表 → RuntimeError）→ 夜跑 rc=2 → 不换名 →
**当晚已经成功抓到的 6 类同花顺数据一并被丢弃** → 次日重演。
09-21 与 09-22 的夜跑日志一字不差，生产库的同花顺表因此停在 09-08。

同花顺自己的日线表反而是最健康的源（十年历史、当晚 6 个步骤全绿）。
缺的只是把它搬进 canonical 表的通道。

与 ``repair_hithink_stock_day`` 的分工（别用错）
------------------------------------------------
- repair：该日**已有行**但有缺口 → 逐字段 diff + 白名单，``stock_name``/
  ``turnover`` 从旧行继承。整日 0 行时它不成立（5553 只会全部落进
  ``new_code_names``，而 ``new_code_expect`` 要求逐票钉死 8 个字段预期值）。
- bridge（本模块）：该日**整日 0 行** → 从零构造。默认拒绝覆盖已有行。

口径政策（POLICY_VERSION，每项都是显式决定，没有隐式默认）
----------------------------------------------------------
- 算术全部委托 ``hithink_stock_preview.preview_stock_calculation``，本模块
  **不自己做除息/舍入**：那套 DECIMAL 半进逻辑已在 09-11 修复中验证过，
  重写一次就多一次错的机会。
- ``turnover``（换手率）：同花顺不提供 → NULL，并在报告里声明。
  注意同花顺表里那个 ``turnover`` 列是**成交额（元）**，与本列不是一回事。
- ``stock_name``：取库内该股最近一条非空历史名，标 ``unverified``；查不到留 NULL。
- 停牌股：同花顺不含其 bar，本模块**不造 K 线**；它们不进 ``rows``，
  也不从市场统计分母里被抹掉（分母口径由下游决定，这里只如实报告）。
- ``source``：逐行沿用 bar 自己的 ``hithink:daily-k`` / ``hithink:daily-k-10d``，
  不新造标签冒充换源。

验证依据（tmp/mootdx-unblock-20260922/）
----------------------------------------
09-18 回测（该日有东财权威行可对答案）：5553 只全算通，OHLC 5552/5552 逐位
一致，``pre_close``/``pct_chg``/``amount``/``volume`` 5550/5552 相等；当日 30 只
除息股中 28 只 ``pre_close`` 完全一致。09-21/09-22 全市场算通 99.96%/99.95%。
已知具名例外见 ``exdiv-agreement-0918.json`` 与 ``bridge-backtest-0918.json``。

写入走单事务；落库由调用方经 ``run_daily_full_staged`` 的 staging 原子换库，
本模块不直写生产（``cli`` 侧另有 ``write_path`` 闸门）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import duckdb

from ..hithink_stock_preview import preview_stock_calculation

POLICY_VERSION = "hithink-bridge-policy-v1"

#: 算通率下限。低于它说明源当天不完整，宁可不写也不写半个市场。
#: 实测 09-18/09-21/09-22 分别为 100%/99.96%/99.95%。
MIN_COVERAGE = 0.99
#: 当日代码数相对参照日的允许波动。A 股每日新增退市是个位数，
#: 超过 3% 说明范围解析出了问题（例如只取到某个板块）。
MAX_UNIVERSE_DRIFT = 0.03


class BridgeRefused(RuntimeError):
    """构建期或写入期断言不通过：拒跑，未写入。消息必须带可追的明细。"""


@dataclass(frozen=True)
class BridgePolicy:
    """口径政策。改这里等于改数据口径，必须同步更新 POLICY_VERSION 与交接。"""

    turnover: str = "null_not_provided_by_vendor"
    stock_name: str = "db_history_latest_unverified"
    nontrading: str = "absent_from_rows_not_removed_from_denominator"
    price_adjustment: str = "none_raw_close"
    min_coverage: float = MIN_COVERAGE
    max_universe_drift: float = MAX_UNIVERSE_DRIFT
    allow_replace_existing: bool = False

    def as_dict(self) -> dict:
        return {"policy_version": POLICY_VERSION, **self.__dict__}


def resolve_universe(con: duckdb.DuckDBPyConnection, trade_date: str) -> list[str]:
    """当日有 bar 的代码全集。

    这是**供应商口径**的范围，不是官方上市名册——停牌股不在其中。
    调用方若需要「声明范围」（含停牌）另取，本函数不冒充上市全集。
    """
    return [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT stock_ts_code FROM fact_stock_daily_hithink "
            "WHERE trade_date = ? ORDER BY 1",
            [trade_date],
        ).fetchall()
    ]


def _resolve_names(con: duckdb.DuckDBPyConnection, codes: list[str],
                   before: str) -> dict[str, str]:
    """取库内每只股最近一条非空历史名。查不到的留给调用方置 NULL。"""
    if not codes:
        return {}
    rows = con.execute(
        """
        SELECT stock_ts_code, stock_name FROM (
            SELECT stock_ts_code, stock_name,
                   row_number() OVER (PARTITION BY stock_ts_code
                                      ORDER BY trade_date DESC) AS rn
            FROM fact_stock_daily
            WHERE stock_ts_code IN (SELECT unnest(?::VARCHAR[]))
              AND stock_name IS NOT NULL AND trade_date < ?
        ) WHERE rn = 1
        """,
        [codes, before],
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _absent_codes(con: duckdb.DuckDBPyConnection, trade_date: str,
                  codes: list[str]) -> list[str]:
    """上一个 canonical 交易日在、今日供应商未给 bar 的代码。

    这就是 `BridgePolicy.nontrading` 说的那批：它们不进 `rows`（不造 K 线），
    但必须被**如实报出**，否则停牌与“供应商漏收”在下游看起来一模一样。
    实例：09-18 的 688496.SH 就是停牌形态（close=pre_close、amount 为 NULL）。
    """
    return [
        r[0]
        for r in con.execute(
            "SELECT stock_ts_code FROM fact_stock_daily WHERE trade_date = ("
            "  SELECT max(trade_date) FROM fact_stock_daily WHERE trade_date < ?)"
            "  AND stock_ts_code NOT IN (SELECT unnest(?::VARCHAR[])) ORDER BY 1",
            [trade_date, codes],
        ).fetchall()
    ]


def _reference_universe(con: duckdb.DuckDBPyConnection, trade_date: str) -> int:
    """参照日代码数：canonical 表里此日之前最近一个有行的交易日。"""
    row = con.execute(
        "SELECT count(*) FROM fact_stock_daily WHERE trade_date = ("
        "  SELECT max(trade_date) FROM fact_stock_daily WHERE trade_date < ?)",
        [trade_date],
    ).fetchone()
    return int(row[0]) if row and row[0] else 0


def build_bridge_day(con: duckdb.DuckDBPyConnection, trade_date: str, *,
                     policy: BridgePolicy | None = None,
                     stock_codes: list[str] | None = None) -> dict[str, Any]:
    """只读构造当日 canonical 行。不写库、不改状态；断言不过直接抛。"""
    policy = policy or BridgePolicy()
    codes = list(stock_codes) if stock_codes is not None else resolve_universe(con, trade_date)
    if not codes:
        raise BridgeRefused(
            f"{trade_date} 在 fact_stock_daily_hithink 无任何 bar，拒跑"
            "（先确认同花顺同步是否跑过该日）"
        )

    existing = int(con.execute(
        "SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?", [trade_date],
    ).fetchone()[0])
    if existing and not policy.allow_replace_existing:
        raise BridgeRefused(
            f"{trade_date} 在 fact_stock_daily 已有 {existing} 行——bridge 只负责"
            "整日 0 行的日子；有旧行请走 repair_hithink_stock_day（逐字段 diff + 白名单）"
        )

    ref_n = _reference_universe(con, trade_date)
    if ref_n:
        drift = abs(len(codes) - ref_n) / ref_n
        if drift > policy.max_universe_drift:
            raise BridgeRefused(
                f"范围异常：{trade_date} 取到 {len(codes)} 只，参照日 {ref_n} 只，"
                f"偏离 {drift:.2%} > {policy.max_universe_drift:.2%}"
            )

    preview = preview_stock_calculation(con, trade_date, stock_codes=codes)
    calculated = preview["calculated_stock_count"]
    coverage = calculated / len(codes)
    if coverage < policy.min_coverage:
        raise BridgeRefused(
            f"算通率 {coverage:.4f} < {policy.min_coverage}："
            f"{calculated}/{len(codes)}，缺口原因见 gaps，拒写半个市场"
        )

    if policy.nontrading != "absent_from_rows_not_removed_from_denominator":
        raise BridgeRefused(f"未知停牌政策 {policy.nontrading!r}：本模块只实现了一种")
    absent = _absent_codes(con, trade_date, codes)

    names = _resolve_names(con, [r["stock_ts_code"] for r in preview["rows"]], trade_date)
    now = datetime.now()
    rows = []
    for r in preview["rows"]:
        code = r["stock_ts_code"]
        rows.append((
            trade_date, code, names.get(code),
            r["close"], r["pre_close"], r["pct_chg"], r["amount"],
            None,                       # turnover: 换手率同花顺不提供
            r["bar_source"], now,
            r["open"], r["high"], r["low"], r["volume"],
        ))

    return {
        "trade_date": trade_date,
        "policy": policy.as_dict(),
        "requested": len(codes),
        "calculated": calculated,
        "coverage": round(coverage, 6),
        "rows": rows,
        "gaps": preview["gaps"],
        "named_rows": sum(1 for r in rows if r[2] is not None),
        "unnamed_codes": sorted(r[1] for r in rows if r[2] is None),
        # 停牌/供应商未给：不造 K 线，但如实报出供下游判分母。
        "absent_from_vendor": absent,
        "absent_count": len(absent),
        "reference_universe": ref_n,
        "existing_rows_before": existing,
        "scope_fingerprint": preview["scope_fingerprint"],
        "input_fingerprint": preview["input_fingerprint"],
        "previous_trade_date": preview["previous_trade_date"],
        "basis": preview["basis"],
        "production_ready": False,   # 构造通过 ≠ 可发布；换库另需授权
    }


def _day_fingerprints(con: duckdb.DuckDBPyConnection) -> dict[str, tuple]:
    """按交易日取 (行数, 内容指纹)。写入后逐日比对，确保只动了目标日。

    指纹用**整数 hash 求和**，不用浮点求和。浮点加法不满足结合律，
    而 DuckDB 会把聚合并行切给多线程、分片和的合并顺序每次不同——
    实测同一连接同一份未改动数据连跑 5 次 sum(close) 得到 3 个不同值
    （114825.50219999999 / 114825.5022 / 114825.50220000005）。
    用它当“没变”断言会随机误报。整行 hash 的整数和与顺序无关，
    覆盖所有列，保留 NULL 与真实值的区别；新增列也自动纳入。
    这是事务内的误写探测，不是无碰撞证明或可跨 DuckDB 版本的计划签名。
    """
    return {
        str(r[0]): (r[1], r[2])
        for r in con.execute(
            "SELECT trade_date, count(*), sum(hash(d)::HUGEINT) "
            "FROM fact_stock_daily AS d GROUP BY 1"
        ).fetchall()
    }


def apply_bridge_day(con: duckdb.DuckDBPyConnection, plan: dict[str, Any]) -> dict[str, Any]:
    """单事务写入当日行，并校验其他日期未被触碰。不负责换库。"""
    td = plan["trade_date"]
    rows = plan["rows"]
    if not rows:
        raise BridgeRefused(f"{td} 无可写行")

    # 计划可能已过期；覆盖授权与目标状态必须在写入事务内重新核验。
    con.execute("BEGIN TRANSACTION")
    try:
        before = _day_fingerprints(con)
        existing = before.get(td, (0,))[0]
        if existing and plan.get("policy", {}).get("allow_replace_existing") is not True:
            raise BridgeRefused(f"{td} 已有 {existing} 行，默认桥接拒绝覆盖")
        deleted = con.execute(
            "DELETE FROM fact_stock_daily WHERE trade_date = ? RETURNING stock_ts_code",
            [td],
        ).fetchall()
        con.executemany(
            "INSERT INTO fact_stock_daily "
            "(trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg, "
            " amount, turnover, source, updated_at, open, high, low, volume) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        after = _day_fingerprints(con)
        drift = sorted(d for d in before.keys() | after.keys()
                       if d != td and before.get(d) != after.get(d))
        if drift:
            raise BridgeRefused(f"写入越界：其他日期被改动 drift={drift[:10]}")
        final = int(con.execute(
            "SELECT count(*) FROM fact_stock_daily WHERE trade_date = ?", [td]).fetchone()[0])
        if final != len(rows):
            raise BridgeRefused(f"写入后当日行数 {final} != 计划 {len(rows)}")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    return {
        "trade_date": td,
        "deleted_replaced": len(deleted),
        "written_rows": len(rows),
        "final_rows": final,
        "other_days_unchanged": True,
    }
