#!/usr/bin/env python3
"""昨日涨停股盘后扫描

流程：
1. 从 share.level2 找出昨日（前一交易日）收盘价 = 涨停价的股票
2. 对每只股票用今日逐笔成交计算大单主买净额 / 总买净额
3. 筛选 主买或总买 > 阈值（默认2000万），按主买金额从高到低排序输出汇总图和CSV

用法:
    CH_PASSWORD=... python3 scan_limitup.py <今日日期> [昨日日期] [净额阈值万元] [大单阈值万元]
    CH_PASSWORD=... python3 scan_limitup.py 2026-07-03 2026-07-02 2000 50

注意：请仅在盘后运行，脚本对每只股票逐一查询并有间隔，避免占用数据库资源。
"""
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from moneyflow import make_client, fetch_trades_retry, analyze, stock_info
from config import out_path
from write_to_duckdb import write_capital_flow

plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False


def prev_trading_date(client, date):
    """取 date 之前最近一个有数据的交易日"""
    rows = client.execute(
        "SELECT max(TradeDate) FROM share.trans WHERE TradeDate < %(d)s", {"d": date})
    return str(rows[0][0])


def limit_up_stocks(client, date):
    """昨日收盘 = 涨停价的股票（排除ST无法区分，按代码前缀限定股票）"""
    # 深圳 level2 带 UpperLimitPrice；上海该字段为0，用昨收*涨幅比例推算
    # （主板10%，创业板30/科创板68为20%，未区分ST）
    sql = """
    SELECT SecurityID,
           argMax(LastPrice, TradeTime) AS last_px,
           argMax(toFloat64(UpperLimitPrice), TradeTime) AS up_px_raw,
           argMax(PreClosePrice, TradeTime) AS pre_close,
           multiIf(up_px_raw > 0, up_px_raw,
                   SecurityID LIKE '68%%', round(pre_close * 1.2, 2),
                   round(pre_close * 1.1, 2)) AS up_px
    FROM share.level2
    WHERE TradeDate = %(d)s AND TradeTime >= toDateTime(%(d)s) + INTERVAL 14 HOUR + INTERVAL 50 MINUTE
      AND (SecurityID LIKE '00%%' OR SecurityID LIKE '30%%'
           OR SecurityID LIKE '60%%' OR SecurityID LIKE '68%%')
    GROUP BY SecurityID
    HAVING abs(last_px - up_px) < 0.005 AND up_px > 0 AND pre_close > 0
    ORDER BY SecurityID
    """
    return [r[0] for r in client.execute(sql, {"d": date})]


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        print("用法: python3 scan_limitup.py <今日日期> [昨日日期] [净额阈值万] [大单阈值万]")
        return
    client = make_client()
    prev = sys.argv[2] if len(sys.argv) > 2 else prev_trading_date(client, date)
    net_thr = float(sys.argv[3]) if len(sys.argv) > 3 else 2000.0
    big_thr = float(sys.argv[4]) if len(sys.argv) > 4 else 50.0

    codes = limit_up_stocks(client, prev)
    print(f"昨日({prev})涨停股: {len(codes)} 只，开始逐只计算 {date} 大单资金流...")

    results = []
    for i, code in enumerate(codes, 1):
        try:
            client, df = fetch_trades_retry(client, code, date)
            if df.empty:
                continue
            big = analyze(df, big_thr)
            if big.empty:
                continue
            active = big["active_net"].iloc[-1] / 1e4
            total = big["total_net"].iloc[-1] / 1e4
            last_px = df["price"].iloc[-1]
            first_px = df["price"].iloc[0]
            chg = (last_px / first_px - 1) * 100
            results.append({"code": code, "主买净额(万)": round(active),
                            "总买净额(万)": round(total), "当日涨幅%": round(chg, 2)})
            print(f"[{i}/{len(codes)}] {code} 主买:{active:.0f}万 总买:{total:.0f}万")
        except Exception as e:
            print(f"[{i}/{len(codes)}] {code} 失败: {e}")
        time.sleep(0.3)  # 限速，避免占用数据库资源

    res = pd.DataFrame(results)
    if res.empty:
        print("无结果")
        return
    info = stock_info(res["code"])
    res["name"] = res["code"].map(lambda c: info.get(c, {}).get("name", ""))
    res["流通市值(亿)"] = res["code"].map(lambda c: info.get(c, {}).get("cap", 0.0))
    # 综合得分 = (0.7*主买 + 0.3*总买) / 流通市值，即大单净流入占流通盘的强度(%)
    weighted = 0.7 * res["主买净额(万)"] + 0.3 * res["总买净额(万)"]
    res["综合得分"] = (weighted / (res["流通市值(亿)"] * 1e4).replace(0, float("nan")) * 100).round(3)
    res = res[["code", "name", "主买净额(万)", "总买净额(万)", "流通市值(亿)",
               "综合得分", "当日涨幅%"]]

    csv_path = out_path(f"limitup_scan_{date}.csv")
    res.sort_values("综合得分", ascending=False).to_csv(csv_path, index=False)
    try:
        write_capital_flow(date, "limitup", res, big_thr, prev_limitup_date=prev)
    except Exception as e:
        print(f"写入 DuckDB 失败（榜单不受影响）: {e}")

    sel = res[(res["主买净额(万)"] > 0) & (res["总买净额(万)"] > 0)
              & ((res["主买净额(万)"] > net_thr) | (res["总买净额(万)"] > net_thr))]
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
    ax.set_title(f"{date} 昨日涨停股大单资金流综合得分前20（得分=(0.7主买+0.3总买)/流通市值%，"
                 f"主买、总买均>0且任一>{net_thr:.0f}万，昨日涨停日:{prev}）")
    fig.tight_layout()
    png_path = out_path(f"limitup_scan_{date}.png")
    fig.savefig(png_path, dpi=120)
    print(f"saved: {csv_path}, {png_path}")


if __name__ == "__main__":
    main()
