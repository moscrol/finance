#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全市场成交额前100股票规律量化买单扫描（盘后运行）。

流程:
    1. 从 share.level2 取当日成交额前100股票（单条聚合查询）
    2. 逐只拉逐笔成交，识别规律量化买单簇：
       大买单（同一委托单累计>=阈值）中金额落在±1%窄带、反复出现>=10笔，
       且簇内单笔金额 >= 量化单阈值（默认200万）
    3. 按 量化单总额占该股大单总买入比例 排序取前20

用法:
    CH_PASSWORD=... python3 scan_quant.py <日期> [大单阈值万元] [量化单阈值万元]
    CH_PASSWORD=... python3 scan_quant.py 2026-07-03 50 200
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from moneyflow import (make_client, fetch_trades_retry, analyze,
                       detect_quant_orders, stock_info, run_scan)
from scan_top100 import top_turnover_stocks
from config import out_path
from write_to_duckdb import write_quant_orders

plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scan_quant.py <日期> [大单阈值万]")
        return
    date = sys.argv[1]
    big_thr = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    quant_thr = float(sys.argv[3]) if len(sys.argv) > 3 else 200.0
    client = make_client()

    codes = top_turnover_stocks(client, date)
    print(f"{date} 成交额前{len(codes)}股票，开始逐只识别规律量化买单...")

    def compute(client, code):
        client, df = fetch_trades_retry(client, code, date)
        if df.empty:
            return client, None
        big = analyze(df, big_thr)
        if big.empty:
            return client, None
        buys = (big[big["buyer_big"]].groupby("buy_no")
                .agg(t=("t", "last"), amount=("amount", "sum")).reset_index())
        infos, _ = detect_quant_orders(
            buys, min_amount=quant_thr * 1e4, top_n=100)
        if not infos:
            return client, None
        quant_total = sum(q["total"] for q in infos)  # 万元
        quant_count = sum(q["count"] for q in infos)
        buy_total = buys["amount"].sum() / 1e4
        biggest = max(infos, key=lambda q: q["total"])
        print(f"{code} 量化单:{quant_total:.0f}万 "
              f"占比:{quant_total / buy_total * 100:.1f}% 簇:{len(infos)}")
        return client, {
            "code": code,
            "量化单总额(万)": round(quant_total),
            "占大单买入%": round(quant_total / buy_total * 100, 2),
            "簇数": len(infos), "笔数": quant_count,
            "最大簇": f"{biggest['lo']:.0f}-{biggest['hi']:.0f}万x{biggest['count']}笔"
                      f"={biggest['total']:.0f}万",
            "当日涨幅%": round((df["price"].iloc[-1] / df["price"].iloc[0] - 1) * 100, 2),
        }

    client, results = run_scan(client, codes, date, "quant", compute)

    res = pd.DataFrame(results)
    if res.empty:
        print("无结果")
        return
    info = stock_info(res["code"])
    res["name"] = res["code"].map(lambda c: info.get(c, {}).get("name", ""))
    res = res[["code", "name", "量化单总额(万)", "占大单买入%", "簇数", "笔数",
               "最大簇", "当日涨幅%"]]

    csv_path = out_path(f"quant_scan_{date}.csv")
    res.sort_values("占大单买入%", ascending=False).to_csv(csv_path, index=False)
    try:
        write_quant_orders(date, res, big_thr, quant_thr)
    except Exception as e:
        print(f"写入 DuckDB 失败（榜单不受影响）: {e}")

    top = res.sort_values("占大单买入%", ascending=False).head(20).reset_index(drop=True)
    print("\n== 量化买单占比前20 ==")
    print(top.to_string())

    fig, ax = plt.subplots(figsize=(12, max(4, 0.45 * len(top))))
    y = range(len(top))[::-1]
    ax.barh(y, top["占大单买入%"], color="blue")
    ax.set_yticks(list(y))
    ax.set_yticklabels(top["code"] + " " + top["name"])
    ax.set_xlabel("量化买单总额占大单买入比例（%）")
    for yi, (pct, amt, n) in zip(y, zip(top["占大单买入%"], top["量化单总额(万)"], top["笔数"])):
        ax.text(pct, yi, f" {pct:.1f}%  {amt:,.0f}万/{n}笔", va="center", fontsize=8)
    ax.set_title(f"{date} 全市场成交额前100规律量化买单排行前20"
                 f"（单笔≥{quant_thr:.0f}万，簇口径:金额±1%窄带且≥10笔）")
    fig.tight_layout()
    png_path = out_path(f"quant_scan_{date}.png")
    fig.savefig(png_path, dpi=120)
    print(f"saved: {csv_path}, {png_path}")


if __name__ == "__main__":
    main()
