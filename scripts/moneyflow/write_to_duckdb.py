#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把每日榜单计算结果写入 DuckDB 特征库（market_feature_store）。

分工原则：原始逐笔 tick 留在 ClickHouse（列存海量明细），DuckDB 只落
每日计算结果（feature_* 层，可删除重算），供与其它特征表 join 分析。

写入表：
- feature_l2_capital_flow_daily   涨停榜/前100榜的主买、总买、得分
- feature_l2_quant_orders_daily   量化单榜

用法（也可被 scan_*.py 直接 import 调用）：
    python3 write_to_duckdb.py <csv路径> <limitup|top100|quant> <日期>
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from market_feature_store.db import connect, init_db  # noqa: E402
from config import to_ts_code  # noqa: E402
from market_feature_store.trading_days import is_trading_day  # noqa: E402

SOURCE = "clickhouse:share(level2服务端聚合)"
STEPS = ("limitup", "top100", "quant")


def begin_l2_run(date):
    con = connect()
    try:
        init_db(con)
        con.execute("BEGIN TRANSACTION")
        for step in STEPS:
            row = con.execute(
                "SELECT status FROM ops_pipeline_run_daily "
                "WHERE trade_date = ? AND pipeline = 'l2-moneyflow' AND step = ?",
                [date, step],
            ).fetchone()
            if row is not None and row[0] == "complete":
                # 已完成步骤不得被重跑降级：保留完整状态与统计，避免失败覆写历史成功
                print(f"DuckDB: l2-moneyflow/{step} {date} 已 complete，跳过 begin 降级", flush=True)
                continue
            con.execute(
                """
                INSERT INTO ops_pipeline_run_daily
                    (trade_date, pipeline, step, status, row_count,
                     input_count, processed_count, failed_count, message, source, finished_at)
                VALUES (?, 'l2-moneyflow', ?, 'running', NULL, NULL, NULL, NULL, NULL, ?, NULL)
                ON CONFLICT (trade_date, pipeline, step) DO UPDATE SET
                    status = excluded.status,
                    row_count = excluded.row_count,
                    input_count = excluded.input_count,
                    processed_count = excluded.processed_count,
                    failed_count = excluded.failed_count,
                    message = excluded.message,
                    source = excluded.source,
                    finished_at = excluded.finished_at
                """,
                [date, step, SOURCE],
            )
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()


def _format_message(message, stats):
    parts = []
    if message:
        parts.append(str(message))
    shared = (stats or {}).get("shared_cache")
    if isinstance(shared, dict):
        parts.append(
            "shared_cache "
            f"hits={shared.get('hits', 0)} misses={shared.get('misses', 0)} "
            f"queries={shared.get('queries', 0)} writes={shared.get('writes', 0)} "
            f"entries={shared.get('entries', 0)} "
            f"path={shared.get('path', '')}"
        )
    if (stats or {}).get("nonempty_count") is not None:
        parts.append(
            f"nonempty={(stats or {}).get('nonempty_count')} "
            f"empty={(stats or {}).get('empty_count', 0)}"
        )
    return " | ".join(parts) if parts else None


def _mark_status(con, date, step, status, row_count, stats, message):
    stats = stats or {}
    message = _format_message(message, stats)
    con.execute(
        """
        INSERT INTO ops_pipeline_run_daily
            (trade_date, pipeline, step, status, row_count,
             input_count, processed_count, failed_count, message, source, finished_at)
        VALUES (?, 'l2-moneyflow', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (trade_date, pipeline, step) DO UPDATE SET
            status = excluded.status,
            row_count = excluded.row_count,
            input_count = excluded.input_count,
            processed_count = excluded.processed_count,
            failed_count = excluded.failed_count,
            message = excluded.message,
            source = excluded.source,
            finished_at = excluded.finished_at
        """,
        [date, step, status, row_count,
         stats.get("input_count"), stats.get("processed_count"),
         stats.get("failed_count"), message, SOURCE],
    )


def _stats_problem(stats):
    """完整处理统计才能标 complete：缺统计/零输入/处理不全/有失败都不合法。"""
    if not stats:
        return "missing scan stats"
    inp = stats.get("input_count")
    proc = stats.get("processed_count")
    fail = stats.get("failed_count")
    if inp is None or proc is None or fail is None:
        return f"incomplete scan stats: {stats}"
    if inp <= 0:
        return f"input_count={inp}, no candidates scanned"
    if fail:
        return f"failed_count={fail}"
    if proc != inp:
        return f"processed_count={proc} != input_count={inp}"
    return None


def _zero_result_problem(scan_type, row_count, stats):
    """capital 榜（limitup/top100）在有候选却 0 行时拒绝 complete。

    这是 VPN 假连 / 全空缓存最常见的落库形态；quant 允许 0（当日可能无量化簇）。
    确认真无数据时设 L2_ALLOW_ALL_EMPTY=1。
    """
    if os.environ.get("L2_ALLOW_ALL_EMPTY", "").strip() in {"1", "true", "yes"}:
        return None
    if scan_type not in {"limitup", "top100"}:
        return None
    inp = (stats or {}).get("input_count") or 0
    if row_count == 0 and inp > 0:
        return (
            f"zero rows for {scan_type} with input_count={inp} "
            "(likely CH empty/VPN); refuse complete"
        )
    return None


def _require_valid_stats(date, step, stats):
    """统计不合法时单独事务标 failed 并抛错，不写结果行。"""
    problem = _stats_problem(stats)
    if not problem:
        return
    con = connect()
    try:
        init_db(con)
        _mark_status(con, date, step, "failed", None, stats, problem)
    finally:
        con.close()
    raise RuntimeError(f"l2-moneyflow/{step} {date} 统计不完整，标记 failed: {problem}")


def _mark_complete(con, date, step, row_count, stats):
    _mark_status(con, date, step, "complete", row_count, stats, None)


def mark_failed(date, message, steps=STEPS, only_running=True):
    """把步骤标记为 failed（默认只覆盖仍处于 running 的步骤）。"""
    con = connect()
    try:
        init_db(con)
        con.execute("BEGIN TRANSACTION")
        if not is_trading_day(date):
            # 非交易日：不允许落 failed，避免把历史 complete 或空跑降级成失败
            print(
                f"DuckDB: {date} 非交易日，跳过 mark_failed（不写 failed）",
                flush=True,
            )
            con.execute("COMMIT")
            return
        for step in steps:
            if only_running:
                row = con.execute(
                    "SELECT status FROM ops_pipeline_run_daily "
                    "WHERE trade_date = ? AND pipeline = 'l2-moneyflow' AND step = ?",
                    [date, step],
                ).fetchone()
                if row is not None and row[0] == "complete":
                    continue
            _mark_status(con, date, step, "failed", None, None, message)
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()


def write_capital_flow(date, scan_type, res, big_thr, prev_limitup_date=None, stats=None):
    """res 列: code,name,主买净额(万),总买净额(万),流通市值(亿),综合得分,当日涨幅%"""
    _require_valid_stats(date, scan_type, stats)
    df = (
        res.sort_values("综合得分", ascending=False).reset_index(drop=True)
        if not res.empty
        else res
    )
    now = datetime.now()
    rows = [(date, scan_type, r["code"], to_ts_code(r["code"]), r["name"],
             float(r["主买净额(万)"]), float(r["总买净额(万)"]),
             float(r["流通市值(亿)"]),
             None if pd.isna(r["综合得分"]) else float(r["综合得分"]),
             float(r["当日涨幅%"]), float(big_thr), i + 1,
             prev_limitup_date, SOURCE, now)
            for i, r in df.iterrows()]
    zero_problem = _zero_result_problem(scan_type, len(rows), stats)
    if zero_problem:
        con = connect()
        try:
            init_db(con)
            _mark_status(con, date, scan_type, "failed", 0, stats, zero_problem)
        finally:
            con.close()
        raise RuntimeError(
            f"l2-moneyflow/{scan_type} {date} 拒绝 complete: {zero_problem}"
        )
    con = connect()
    try:
        init_db(con)
        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM feature_l2_capital_flow_daily "
            "WHERE trade_date = ? AND scan_type = ? AND big_order_threshold_wan = ?",
            [date, scan_type, big_thr])
        if rows:
            con.executemany(
                "INSERT INTO feature_l2_capital_flow_daily VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        _mark_complete(con, date, scan_type, len(rows), stats)
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()
    print(f"DuckDB: feature_l2_capital_flow_daily {scan_type} {date} 写入 {len(rows)} 行")


def write_quant_orders(date, res, big_thr, quant_thr, stats=None):
    """res 列: code,name,量化单总额(万),占大单买入%,簇数,笔数,最大簇,当日涨幅%"""
    _require_valid_stats(date, "quant", stats)
    df = (
        res.sort_values("占大单买入%", ascending=False).reset_index(drop=True)
        if not res.empty
        else res
    )
    now = datetime.now()
    rows = [(date, r["code"], to_ts_code(r["code"]), r["name"],
             float(r["量化单总额(万)"]), float(r["占大单买入%"]),
             int(r["簇数"]), int(r["笔数"]), str(r["最大簇"]),
             float(r["当日涨幅%"]), float(quant_thr), float(big_thr),
             i + 1, SOURCE, now)
            for i, r in df.iterrows()]
    con = connect()
    try:
        init_db(con)
        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM feature_l2_quant_orders_daily "
            "WHERE trade_date = ? AND big_order_threshold_wan = ?",
            [date, big_thr])
        if rows:
            con.executemany(
                "INSERT INTO feature_l2_quant_orders_daily VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        _mark_complete(con, date, "quant", len(rows), stats)
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()
    print(f"DuckDB: feature_l2_quant_orders_daily {date} 写入 {len(rows)} 行")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--begin":
        begin_l2_run(sys.argv[2])
        print(f"DuckDB: l2-moneyflow {sys.argv[2]} 标记为 running")
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "--fail":
        message = sys.argv[3] if len(sys.argv) > 3 else "pipeline failed"
        mark_failed(sys.argv[2], message)
        print(f"DuckDB: l2-moneyflow {sys.argv[2]} 未完成步骤标记为 failed")
        return
    if len(sys.argv) < 4:
        print(
            "用法: python3 write_to_duckdb.py --begin <日期> | --fail <日期> [原因] | "
            "<csv路径> <limitup|top100|quant> <日期>"
        )
        return
    csv_path, scan_type, date = sys.argv[1], sys.argv[2], sys.argv[3]
    res = pd.read_csv(csv_path, dtype={"code": str})
    stats = {"input_count": len(res), "processed_count": len(res), "failed_count": 0}
    if scan_type == "quant":
        write_quant_orders(date, res, big_thr=100.0, quant_thr=200.0, stats=stats)
    else:
        write_capital_flow(date, scan_type, res, big_thr=100.0, stats=stats)


if __name__ == "__main__":
    main()
