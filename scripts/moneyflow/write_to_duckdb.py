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
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from market_feature_store.db import connect, init_db  # noqa: E402
from config import to_ts_code  # noqa: E402

SOURCE = "clickhouse:share(level2逐笔)"


def write_capital_flow(date, scan_type, res, big_thr, prev_limitup_date=None):
    """res 列: code,name,主买净额(万),总买净额(万),流通市值(亿),综合得分,当日涨幅%"""
    df = res.sort_values("综合得分", ascending=False).reset_index(drop=True)
    now = datetime.now()
    rows = [(date, scan_type, r["code"], to_ts_code(r["code"]), r["name"],
             float(r["主买净额(万)"]), float(r["总买净额(万)"]),
             float(r["流通市值(亿)"]),
             None if pd.isna(r["综合得分"]) else float(r["综合得分"]),
             float(r["当日涨幅%"]), float(big_thr), i + 1,
             prev_limitup_date, SOURCE, now)
            for i, r in df.iterrows()]
    con = connect()
    try:
        init_db(con)
        con.execute(
            "DELETE FROM feature_l2_capital_flow_daily "
            "WHERE trade_date = ? AND scan_type = ?", [date, scan_type])
        con.executemany(
            "INSERT INTO feature_l2_capital_flow_daily VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    finally:
        con.close()
    print(f"DuckDB: feature_l2_capital_flow_daily {scan_type} {date} 写入 {len(rows)} 行")


def write_quant_orders(date, res, big_thr, quant_thr):
    """res 列: code,name,量化单总额(万),占大单买入%,簇数,笔数,最大簇,当日涨幅%"""
    df = res.sort_values("占大单买入%", ascending=False).reset_index(drop=True)
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
        con.execute(
            "DELETE FROM feature_l2_quant_orders_daily WHERE trade_date = ?",
            [date])
        con.executemany(
            "INSERT INTO feature_l2_quant_orders_daily VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    finally:
        con.close()
    print(f"DuckDB: feature_l2_quant_orders_daily {date} 写入 {len(rows)} 行")


def main():
    if len(sys.argv) < 4:
        print("用法: python3 write_to_duckdb.py <csv路径> <limitup|top100|quant> <日期>")
        return
    csv_path, scan_type, date = sys.argv[1], sys.argv[2], sys.argv[3]
    res = pd.read_csv(csv_path, dtype={"code": str})
    if scan_type == "quant":
        write_quant_orders(date, res, big_thr=50.0, quant_thr=200.0)
    else:
        write_capital_flow(date, scan_type, res, big_thr=50.0)


if __name__ == "__main__":
    main()
