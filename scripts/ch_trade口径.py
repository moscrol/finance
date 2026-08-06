#!/usr/bin/env python3
"""对比逐笔口径 vs 委托聚合口径的大单资金。"""
import os, time

def main():
    from clickhouse_driver import Client
    code = "688825"
    date = "2026-07-27"
    client = Client(host="db.base32.cn", port=9000, user="hisdata180",
                     password=os.environ["CH_PASSWORD"])

    for thr_wan in [50, 100]:
        thr = thr_wan * 1e4
        # 逐笔口径：每笔成交独立判定
        query = f"""
        SELECT
            sumIf(amount, buy_no > sell_no AND amount >= %(thr)s) AS active_buy,
            sumIf(amount, buy_no < sell_no AND amount >= %(thr)s) AS active_sell,
            sumIf(amount, amount >= %(thr)s) AS total_buy,
            sumIf(amount, amount >= %(thr)s) AS total_sell
        FROM (
            SELECT BuyNo AS buy_no, SellNo AS sell_no,
                   toFloat64(Price) * Volume AS amount
            FROM share.ngts_tick
            PREWHERE TradeDate = %(d)s AND SecurityID = %(c)s
            WHERE TickType = 'T'
        )
        """
        rows = client.execute(query, {"d": date, "c": code, "thr": thr})
        ab, asg, tb, tsg = rows[0]
        print(f"逐笔口径 ≥{thr_wan}万: "
              f"主买={ab/1e8:.0f}亿 主卖={asg/1e8:.0f}亿 净={(ab-asg)/1e8:+.0f}亿 | "
              f"总买={tb/1e8:.0f}亿 总卖={tsg/1e8:.0f}亿 净={(tb-tsg)/1e8:+.0f}亿")

    client.disconnect()

if __name__ == "__main__":
    main()
