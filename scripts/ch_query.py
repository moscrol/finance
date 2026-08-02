#!/usr/bin/env python3
"""ClickHouse 轻量查询工具——单股单日大单总额/净额。

用法:
  python scripts/ch_query.py 688825 2026-07-27
  python scripts/ch_query.py 688825 2026-07-27 --threshold 100   # 100万大单

后台跑:
  nohup python scripts/ch_query.py 688825 2026-07-27 > /tmp/ch_out.txt 2>&1 &
"""
import os, sys, time

def main():
    if len(sys.argv) < 3:
        print("Usage: ch_query.py <code> <date> [--threshold N]")
        sys.exit(1)
    code = sys.argv[1]
    date = sys.argv[2]
    threshold_wan = 50.0
    if "--threshold" in sys.argv:
        idx = sys.argv.index("--threshold")
        threshold_wan = float(sys.argv[idx + 1])
    threshold = threshold_wan * 1e4

    try:
        from clickhouse_driver import Client
    except ImportError:
        print("ERROR: clickhouse_driver not installed")
        sys.exit(2)

    pw = os.environ.get("CH_PASSWORD", "")
    t0 = time.time()
    client = Client(host="db.base32.cn", port=9000, user="hisdata180", password=pw)

    # 先确认数据量（快查）
    cnt = client.execute(
        "SELECT count() FROM share.ngts_tick WHERE TradeDate = %(d)s AND SecurityID = %(c)s AND TickType = 'T'",
        {"d": date, "c": code},
    )[0][0]
    print(f"逐笔成交笔数: {cnt:,}")
    if cnt == 0:
        print("无数据"); client.disconnect(); return

    # 上交所走 ngts_tick
    source = {
        "table": "share.ngts_tick" if code.startswith("6") else "share.trans",
        "time_col": "TickTime" if code.startswith("6") else "TradeTime",
        "price_col": "Price" if code.startswith("6") else "TradePrice",
        "vol_col": "Volume" if code.startswith("6") else "TradeVolume",
        "type_col": "TickType" if code.startswith("6") else "ExecType",
        "type_val": "T" if code.startswith("6") else "1",
    }

    query = f"""
    SELECT
        sumIf(amount, buy_no > sell_no AND buy_order_amount >= %(thr)s) AS active_buy_gross,
        sumIf(amount, buy_no < sell_no AND sell_order_amount >= %(thr)s) AS active_sell_gross,
        sumIf(amount, buy_order_amount >= %(thr)s) AS total_buy_gross,
        sumIf(amount, sell_order_amount >= %(thr)s) AS total_sell_gross
    FROM (
        SELECT
            t, price, buy_no, sell_no, amount,
            sum(amount) OVER (PARTITION BY buy_no) AS buy_order_amount,
            sum(amount) OVER (PARTITION BY sell_no) AS sell_order_amount
        FROM (
            SELECT
                {source['time_col']} AS t,
                toFloat64({source['price_col']}) AS price,
                BuyNo AS buy_no,
                SellNo AS sell_no,
                toFloat64({source['price_col']}) * {source['vol_col']} AS amount
            FROM {source['table']}
            PREWHERE TradeDate = %(d)s AND SecurityID = %(c)s
            WHERE {source['type_col']} = %(tv)s
        )
    )
    """
    rows = client.execute(query, {"d": date, "c": code, "thr": threshold, "tv": source["type_val"]})
    elapsed = time.time() - t0
    client.disconnect()

    ab, asg, tb, tsg = rows[0]
    print(f"\n=== {code} {date} 大单(≥{threshold_wan:.0f}万) 资金明细 ===")
    print(f"主买总额: {ab/1e8:.2f} 亿  |  主卖总额: {asg/1e8:.2f} 亿  |  主买净额: {(ab-asg)/1e8:+.2f} 亿")
    print(f"总买总额: {tb/1e8:.2f} 亿  |  总卖总额: {tsg/1e8:.2f} 亿  |  总买净额: {(tb-tsg)/1e8:+.2f} 亿")
    print(f"耗时: {elapsed:.1f}s")

if __name__ == "__main__":
    main()
