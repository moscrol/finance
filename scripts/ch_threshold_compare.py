#!/usr/bin/env python3
"""委托聚合口径多阈值对比。"""
import os
from clickhouse_driver import Client

code = "688825"
date = "2026-07-27"
client = Client(host="db.base32.cn", port=9000, user="hisdata180",
                 password=os.environ["CH_PASSWORD"])

for thr_wan in [50, 100, 200, 300, 500]:
    thr = thr_wan * 1e4
    query = """
    SELECT
        sumIf(amount, buy_no > sell_no AND buy_order_amount >= %(thr)s) AS active_buy,
        sumIf(amount, buy_order_amount >= %(thr)s) AS total_buy
    FROM (
        SELECT t, price, buy_no, sell_no, amount,
            sum(amount) OVER (PARTITION BY buy_no) AS buy_order_amount
        FROM (
            SELECT TickTime AS t, toFloat64(Price) AS price,
                   BuyNo AS buy_no, SellNo AS sell_no,
                   toFloat64(Price) * Volume AS amount
            FROM share.ngts_tick
            PREWHERE TradeDate = %(d)s AND SecurityID = %(c)s
            WHERE TickType = 'T'
        )
    )
    """
    rows = client.execute(query, {"d": date, "c": code, "thr": thr})
    ab, tb = rows[0]
    print(f"委托聚合 ≥{thr_wan:>3d}万: 主买={ab/1e8:>6.0f}亿  总买={tb/1e8:>6.0f}亿")

print(f"\n目标: 主买≈404亿  总买≈638亿")
client.disconnect()
