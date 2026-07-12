#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全市场成交额前100股票大单资金流扫描（盘后运行）。

流程:
    1. 用一条聚合SQL从 share.level2 取当日全市场成交额前100的股票（只返回代码，负担小）
    2. 逐只拉逐笔成交，用自有大单口径计算主买/总买净额（同一委托单累计成交额>=阈值）
    3. 筛选主买、总买均>0，按综合得分排序取前20
       综合得分 = (0.7*主买净额 + 0.3*总买净额) / 流通市值，即净流入强度(%)

用法:
    CH_PASSWORD=... python3 scan_top100.py <日期> [大单阈值万元]
    CH_PASSWORD=... python3 scan_top100.py 2026-07-03 50

注意：请仅在盘后运行，脚本对每只股票逐一查询并有间隔，避免占用数据库资源。
"""
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from moneyflow import (make_client, fetch_trades_retry, analyze, stock_info,
                       run_scan, duck_top_turnover_codes)
from config import out_path
from write_to_duckdb import write_capital_flow

plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False


def top_turnover_stocks(client, date, n=50):
    """当日成交额前 n 的股票（用 level2 收盘快照的累计成交额）。

    按代码前缀分4批查询再合并，单批负担小；每批失败自动重试。
    结果缓存到 codes_<date>.txt，存在则直接读取（避免重复跑聚合）。
    """
    cache = out_path(f"codes_{date}.txt")
    if os.path.exists(cache):
        with open(cache) as f:
            codes = [ln.strip() for ln in f if ln.strip()]
        if codes:
            print(f"读取缓存名单 {cache}: {len(codes)} 只")
            return codes[:n]
    try:
        codes = duck_top_turnover_codes(date, n)
        if codes:
            print(f"DuckDB 取成交额前{n}名单: {len(codes)} 只")
            with open(cache, "w") as f:
                f.write("\n".join(codes))
            return codes
    except Exception as e:
        print(f"DuckDB 取名单失败({e})，回退 ClickHouse 聚合")
    sql = """
    SELECT SecurityID, argMax(TotalValueTrade, TradeTime) AS val
    FROM share.level2
    WHERE TradeDate = %(d)s
      AND TradeTime >= toDateTime(%(d)s) + INTERVAL 14 HOUR + INTERVAL 59 MINUTE
      AND SecurityID LIKE %(pfx)s
    GROUP BY SecurityID
    ORDER BY val DESC
    LIMIT %(n)s
    """
    rows = []
    for pfx in ("00%", "30%", "60%", "68%"):
        for k in range(3):
            try:
                rows += client.execute(sql, {"d": date, "pfx": pfx, "n": n})
                break
            except Exception as e:
                if k == 2:
                    raise
                print(f"前缀{pfx}查询失败({e})，{15 * (k + 1)}秒后重试...")
                time.sleep(15 * (k + 1))
                try:
                    client.disconnect()
                except Exception:
                    pass
                client.connect()
        time.sleep(1)
    rows.sort(key=lambda r: r[1], reverse=True)
    codes = [r[0] for r in rows[:n]]
    with open(cache, "w") as f:
        f.write("\n".join(codes))
    return codes


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scan_top100.py <日期> [大单阈值万]")
        return
    date = sys.argv[1]
    big_thr = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    client = make_client()

    codes = top_turnover_stocks(client, date)
    print(f"{date} 成交额前{len(codes)}股票，开始逐只计算大单资金流...")

    def compute(client, code):
        client, df = fetch_trades_retry(client, code, date)
        if df.empty:
            return client, None
        big = analyze(df, big_thr)
        if big.empty:
            return client, None
        active = big["active_net"].iloc[-1] / 1e4
        total = big["total_net"].iloc[-1] / 1e4
        chg = (df["price"].iloc[-1] / df["price"].iloc[0] - 1) * 100
        print(f"{code} 主买:{active:.0f}万 总买:{total:.0f}万")
        return client, {"code": code, "主买净额(万)": round(active),
                        "总买净额(万)": round(total), "当日涨幅%": round(chg, 2)}

    client, results = run_scan(client, codes, date, "top100", compute)

    res = pd.DataFrame(results)
    if res.empty:
        print("无结果")
        write_capital_flow(date, "top100", res, big_thr)
        return
    info = stock_info(res["code"])
    res["name"] = res["code"].map(lambda c: info.get(c, {}).get("name", ""))
    res["流通市值(亿)"] = res["code"].map(lambda c: info.get(c, {}).get("cap", 0.0))
    weighted = 0.7 * res["主买净额(万)"] + 0.3 * res["总买净额(万)"]
    res["综合得分"] = (weighted / (res["流通市值(亿)"] * 1e4).replace(0, float("nan")) * 100).round(3)
    res = res[["code", "name", "主买净额(万)", "总买净额(万)", "流通市值(亿)",
               "综合得分", "当日涨幅%"]]

    csv_path = out_path(f"top100_scan_{date}.csv")
    res.sort_values("综合得分", ascending=False).to_csv(csv_path, index=False)
    write_capital_flow(date, "top100", res, big_thr)

    sel = res[(res["主买净额(万)"] > 0) & (res["总买净额(万)"] > 0)]
    top = sel.sort_values("综合得分", ascending=False).head(20).reset_index(drop=True)
    print("\n== 综合得分前20（(0.7主买+0.3总买)/流通市值） ==")
    print(top.to_string())

    fig, ax = plt.subplots(figsize=(12, max(4, 0.45 * len(top))))
    y = range(len(top))[::-1]
    ax.barh(y, top["主买净额(万)"], height=0.38, color="red", label="主买净额")
    ax.barh([v - 0.4 for v in y], top["总买净额(万)"], height=0.38,
            color="purple", label="总买净额")
    ax.set_yticks([v - 0.2 for v in y])
    ax.set_yticklabels(top["code"] + " " + top["name"])
    ax.set_xlabel("净额（万元）")
    ax.legend()
    for yi, v, cap in zip(y, top["综合得分"], top["流通市值(亿)"]):
        ax.text(ax.get_xlim()[1], yi - 0.2, f"得分 {v:.2f}  市值 {cap:.0f}亿",
                va="center", fontsize=8)
    ax.set_title(f"{date} 全市场成交额前100大单资金流综合得分前20"
                 f"（得分=(0.7主买+0.3总买)/流通市值%，主买、总买均>0，大单阈值{big_thr:.0f}万）")
    fig.tight_layout()
    png_path = out_path(f"top100_scan_{date}.png")
    fig.savefig(png_path, dpi=120)
    print(f"saved: {csv_path}, {png_path}")


if __name__ == "__main__":
    main()
