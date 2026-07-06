#!/usr/bin/env python3
"""大单资金流分析图

基于逐笔成交数据（深圳 share.trans / 上海 share.ngts_tick），
只统计单笔成交额 >= 阈值（默认50万）的大单：

- 红色线：主动买入净额 = 累计(主动买入金额 - 主动卖出金额)
- 紫色线：总买入净额 = 主动净额 + 被动净额
- 散点：大单买单（红）/ 卖单（绿），按时间和单笔金额绘制

主动方向判断：委托编号大的一方为主动方（后下单先成交）。
BuyNo > SellNo => 主动买入；SellNo > BuyNo => 主动卖出。

用法:
    python3 moneyflow.py <股票代码> <日期> [阈值万元]
    python3 moneyflow.py 300775 2026-07-03 50
"""
import sys
import time
import urllib.request

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from clickhouse_driver import Client

plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
plt.rcParams["axes.unicode_minus"] = False

from config import HOST, PORT, USER, PASSWORD, out_path  # noqa: E402


def make_client():
    return Client(host=HOST, port=PORT, user=USER, password=PASSWORD,
                  connect_timeout=20, send_receive_timeout=300)


def fetch_trades_retry(client, code, date, retries=3):
    """带重连重试的 fetch_trades，返回 (client, df)，服务器繁忙时退避重试"""
    for k in range(retries):
        try:
            return client, fetch_trades(client, code, date)
        except Exception:
            if k == retries - 1:
                raise
            time.sleep(10 * (k + 1))
            try:
                client.disconnect()
            except Exception:
                pass
            client = make_client()


def fetch_trades(client, code, date):
    """拉取单只股票单日逐笔成交。返回 DataFrame[time, price, volume, buy_no, sell_no]"""
    if code.startswith("6"):  # 上海
        sql = """
        SELECT TickTime AS t, toFloat64(Price) AS price, Volume AS volume,
               BuyNo AS buy_no, SellNo AS sell_no
        FROM share.ngts_tick
        WHERE SecurityID = %(code)s AND TradeDate = %(date)s AND TickType = 'T'
        ORDER BY t
        """
    else:  # 深圳
        sql = """
        SELECT TradeTime AS t, toFloat64(TradePrice) AS price, TradeVolume AS volume,
               BuyNo AS buy_no, SellNo AS sell_no
        FROM share.trans
        WHERE SecurityID = %(code)s AND TradeDate = %(date)s AND ExecType = '1'
        ORDER BY t
        """
    rows = client.execute(sql, {"code": code, "date": date})
    df = pd.DataFrame(rows, columns=["t", "price", "volume", "buy_no", "sell_no"])
    if not df.empty:
        t = pd.to_datetime(df["t"], utc=True)
        df["t"] = t.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    return df


def analyze(df, threshold_wan=50.0):
    df = df.copy()
    df["amount"] = df["price"] * df["volume"]
    df["active_buy"] = df["buy_no"] > df["sell_no"]

    # 大资金口径：同一委托单当日累计成交额 >= 阈值
    thr = threshold_wan * 1e4
    buy_order_amt = df.groupby("buy_no")["amount"].sum()
    sell_order_amt = df.groupby("sell_no")["amount"].sum()
    big_buy_orders = set(buy_order_amt[buy_order_amt >= thr].index)
    big_sell_orders = set(sell_order_amt[sell_order_amt >= thr].index)

    df["buyer_big"] = df["buy_no"].isin(big_buy_orders)
    df["seller_big"] = df["sell_no"].isin(big_sell_orders)
    big = df[df["buyer_big"] | df["seller_big"]].copy()

    # 主动买入净额 = cumsum(主动买入 - 主动卖出)，仅统计大资金一侧
    active_flow = (
        big["amount"] * (big["active_buy"] & big["buyer_big"])
        - big["amount"] * (~big["active_buy"] & big["seller_big"])
    )
    # 被动净额 = 被动买入 - 被动卖出（挂单被动成交的大资金）
    passive_flow = (
        big["amount"] * (~big["active_buy"] & big["buyer_big"])
        - big["amount"] * (big["active_buy"] & big["seller_big"])
    )
    big["active_net"] = active_flow.cumsum()
    big["total_net"] = (active_flow + passive_flow).cumsum()
    return big


def stock_info(codes):
    """通过腾讯行情接口批量获取股票名称与流通市值（亿元），
    返回 {code: {"name": str, "cap": float}}"""
    info = {}
    codes = list(codes)
    for i in range(0, len(codes), 50):
        batch = codes[i:i + 50]
        q = ",".join(("sh" if c.startswith("6") else "sz") + c for c in batch)
        try:
            raw = urllib.request.urlopen(
                f"http://qt.gtimg.cn/q={q}", timeout=10).read().decode("gbk")
            for line in raw.strip().split(";"):
                if "=" not in line:
                    continue
                _, val = line.split("=", 1)
                parts = val.strip('"').split("~")
                if len(parts) > 44:
                    cap = float(parts[44]) if parts[44] else 0.0
                    info[parts[2]] = {"name": parts[1], "cap": cap}
        except Exception as e:
            print(f"获取行情信息失败: {e}")
    return info


def stock_names(codes):
    return {c: v["name"] for c, v in stock_info(codes).items()}


def detect_quant_orders(buys, tol=0.01, min_count=10, min_amount=0.0, top_n=5):
    """规律量化单识别：金额高度相近、反复出现的大买单簇。

    按金额排序后扫描，整簇金额落在 [x, x*(1+tol)] 的窄带内且
    笔数 >= min_count 的认为是量化单。返回簇列表及命中的行。
    """
    if buys.empty:
        return [], buys.iloc[0:0]
    b = buys.sort_values("amount").reset_index(drop=True)
    clusters, start = [], 0
    for i in range(1, len(b) + 1):
        if i == len(b) or b["amount"][i] > b["amount"][start] * (1 + tol):
            if i - start >= min_count:
                clusters.append(b.iloc[start:i])
            start = i
    # 组合金额在阈值边缘的密集小单容易误判，只保留明显高于阈值的簇，
    # 并按总额取前 top_n
    clusters = [c for c in clusters if c["amount"].min() >= min_amount]
    clusters = sorted(clusters, key=lambda c: c["amount"].sum(), reverse=True)[:top_n]
    infos, hit_idx = [], []
    for c in clusters:
        infos.append({
            "lo": c["amount"].min() / 1e4, "hi": c["amount"].max() / 1e4,
            "count": len(c), "total": c["amount"].sum() / 1e4,
            "t0": c["t"].min(), "t1": c["t"].max(),
        })
        hit_idx += list(c.index)
    return infos, b.loc[hit_idx]


def plot(big, code, date, threshold_wan, out_path, name=""):
    fig, (ax0, ax1) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True,
        gridspec_kw={"height_ratios": [1, 2.6]})
    # 上方分时价格线（用逐笔成交价，便于对比背离）
    ax0.plot(big["t"], big["price"], c="black", lw=0.8)
    ax0.set_ylabel("分时价格")
    ax0.grid(alpha=0.3)

    # 每个大资金委托单聚合为一个点：时间取最后成交时间，金额为累计成交额
    buys = (big[big["buyer_big"]].groupby("buy_no")
            .agg(t=("t", "last"), amount=("amount", "sum")).reset_index())
    sells = (big[big["seller_big"]].groupby("sell_no")
             .agg(t=("t", "last"), amount=("amount", "sum")).reset_index())
    ax1.scatter(buys["t"], buys["amount"] / 1e4, s=12, c="red", label="买单")
    ax1.scatter(sells["t"], sells["amount"] / 1e4, s=12, c="green", label="卖单")
    ax1.set_ylabel("单笔成交额（万元）")
    ax1.set_xlabel("时间")

    ax2 = ax1.twinx()
    ax2.plot(big["t"], big["active_net"] / 1e4, c="red", lw=1.2, label="主动买入净额")
    ax2.plot(big["t"], big["total_net"] / 1e4, c="purple", lw=1.2, label="总买入净额")
    ax2.axhline(0, c="orange", ls="--", lw=0.8)
    ax2.set_ylabel("累计净额（万元）")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left")

    # 规律量化买单标注
    infos, hits = detect_quant_orders(buys, min_amount=threshold_wan * 1e4 * 1.5)
    if infos:
        ax1.scatter(hits["t"], hits["amount"] / 1e4, s=40,
                    facecolors="none", edgecolors="blue", lw=0.8)
        lines = [
            f"量化买单{i+1}: 金额({q['lo']:.0f}-{q['hi']:.0f}万) 笔数:{q['count']} "
            f"时间:{q['t0']:%H:%M:%S} -> {q['t1']:%H:%M:%S} 总额 {q['total']:.0f}万"
            for i, q in enumerate(infos)]
        fig.text(0.01, -0.005, "\n".join(lines), fontsize=9, va="top", c="blue")

    buy_amt = buys["amount"].sum() / 1e4
    sell_amt = sells["amount"].sum() / 1e4
    ax0.set_title(
        f"{code} {name} {date} 大单资金流（单笔≥{threshold_wan:.0f}万） "
        f"B:S={len(buys)}:{len(sells)} 主买净额:{big['active_net'].iloc[-1]/1e4:.0f}万 "
        f"总额:{buy_amt+sell_amt:.0f}万"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    print(f"saved: {out_path}  大单数: {len(big)}")


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "300775"
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-07-03"
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
    client = make_client()
    df = fetch_trades(client, code, date)
    if df.empty:
        print("无数据，请检查代码/日期")
        return
    big = analyze(df, threshold)
    if big.empty:
        print("当日无满足阈值的大单")
        return
    out = out_path(f"moneyflow_{code}_{date}.png")
    name = stock_names([code]).get(code, "")
    plot(big, code, date, threshold, out, name)


if __name__ == "__main__":
    main()
