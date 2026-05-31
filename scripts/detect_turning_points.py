"""转折信号检测脚本。

从 DuckDB 读取数据，检测三种查边际量的触发条件：
1. 大盘放量 — 较昨日成交额增长 > 10%
2. 大盘涨幅 > 0.8%（需要补充数据，目前暂缺）
3. 峰谷次日 — MA5 大波段峰或谷的后一天

用法:
    python3 scripts/detect_turning_points.py
    python3 scripts/detect_turning_points.py --from 2026-04-01
"""
import sys
import duckdb
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent / "db" / "market.duckdb"

# 阈值
VOLUME_CHANGE_THRESHOLD = 10  # 较昨日成交额增长 > 10% 视为放量
MA5_MIN_SWING = 500           # MA5 最小波动幅度，过滤噪音


def detect(conn, start_date=None):
    # 联合查询: advancers + daily_market
    where = f"WHERE a.date >= '{start_date}'" if start_date else ""
    data = conn.execute(f"""
        SELECT a.date, a.count, a.ma5,
               m.volume, m.volume_ratio, m.volume_status,
               m.limit_up, m.limit_down, m.deviation, m.week_ma
        FROM advancers a
        LEFT JOIN daily_market m ON a.date = m.date
        {where}
        ORDER BY a.date
    """).fetchall()

    if not data:
        print("无数据")
        return []

    # 建立 MA5 序列
    ma5_series = [(row[0], row[2]) for row in data if row[2] is not None]

    # 大波段峰谷检测: zigzag 算法
    # 只保留波动幅度 > MA5_MIN_SWING 的大拐点
    turning_points = {}  # date -> 'peak'/'valley'
    if len(ma5_series) >= 3:
        pivots = [ma5_series[0]]  # (date, ma5)
        direction = None  # 1=up, -1=down

        for i in range(1, len(ma5_series)):
            cur_date, cur_ma5 = ma5_series[i]
            last_date, last_ma5 = pivots[-1]

            if direction is None:
                if cur_ma5 > last_ma5:
                    direction = 1
                elif cur_ma5 < last_ma5:
                    direction = -1
                # 更新极值
                if direction == 1 and cur_ma5 > last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)
                elif direction == -1 and cur_ma5 < last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)
                continue

            if direction == 1:
                if cur_ma5 > last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)  # 继续创新高
                elif last_ma5 - cur_ma5 >= MA5_MIN_SWING:
                    pivots.append((cur_date, cur_ma5))
                    direction = -1  # 反转
                elif cur_ma5 < last_ma5:
                    # 小幅回调，不反转，继续观察
                    pass
            else:  # direction == -1
                if cur_ma5 < last_ma5:
                    pivots[-1] = (cur_date, cur_ma5)  # 继续创新低
                elif cur_ma5 - last_ma5 >= MA5_MIN_SWING:
                    pivots.append((cur_date, cur_ma5))
                    direction = 1  # 反转
                elif cur_ma5 > last_ma5:
                    pass

        # 标记峰谷
        for i, (pdate, pma5) in enumerate(pivots):
            if i == 0:
                continue
            prev_pma5 = pivots[i - 1][1]
            if pma5 > prev_pma5:
                turning_points[pdate] = "peak"
            else:
                turning_points[pdate] = "valley"

    # 峰谷次日集合
    tp_dates = set(turning_points.keys())
    next_dates = set()
    date_list = [row[0] for row in data]
    for d in tp_dates:
        idx = date_list.index(d) if d in date_list else -1
        if idx >= 0 and idx + 1 < len(date_list):
            next_dates.add(date_list[idx + 1])

    # 生成结果
    results = []
    prev_volume = None

    for i, row in enumerate(data):
        date, count, ma5, volume, vol_ratio, vol_status, limit_up, limit_down, deviation, week_ma = row

        signals = []

        # 条件1: 大盘放量（较昨日增长 > 10%）
        if prev_volume is not None and volume is not None and prev_volume > 0:
            vol_chg = (volume - prev_volume) / prev_volume * 100
            if vol_chg > VOLUME_CHANGE_THRESHOLD:
                signals.append(("放量", f"成交额 {prev_volume:.0f}→{volume:.0f} (+{vol_chg:.1f}%)"))

        # 条件2: 峰谷次日
        if date in next_dates:
            # 找到是哪个峰谷的次日
            for d in tp_dates:
                idx = date_list.index(d) if d in date_list else -1
                if idx >= 0 and idx + 1 < len(date_list) and date_list[idx + 1] == date:
                    tp_type = "顶" if turning_points[d] == "peak" else "谷"
                    signals.append((f"{tp_type}次日", f"{d} MA5={ma5:.0f}" if ma5 else str(d)))
                    break

        prev_volume = volume

        results.append({
            "date": date,
            "count": count,
            "ma5": ma5,
            "ma5_type": turning_points.get(date),
            "volume": volume,
            "vol_ratio": vol_ratio,
            "signals": signals,
            "deviation": deviation,
        })

    return results


def print_results(results):
    # 打印表头
    print(f"{'日期':<12} {'涨家数':>6} {'MA5':>8} {'峰谷':<4} {'量能比':>7} {'偏离度':>7} {'信号'}")
    print("-" * 75)

    for r in results:
        sig_texts = [f"{s[0]}({s[1]})" for s in r["signals"]]
        ma5_label = {"peak": "▲顶", "valley": "▼谷"}.get(r["ma5_type"], "")
        dev_str = f"{r['deviation']:+.2f}%" if r["deviation"] is not None else ""
        vol_str = f"{r['vol_ratio']:.1f}%" if r["vol_ratio"] else ""

        marker = " ◀" if r["signals"] or r["ma5_type"] else ""
        print(
            f"{r['date']}  {r['count'] or '':>6} "
            f"{r['ma5'] or '':>8.1f} "
            f"{ma5_label:<4} "
            f"{vol_str:>7} "
            f"{dev_str:>7} "
            f"{'; '.join(sig_texts)}{marker}"
        )

    # 汇总
    signal_dates = [r for r in results if r["signals"]]
    peak_dates = [r for r in results if r["ma5_type"] == "peak"]
    valley_dates = [r for r in results if r["ma5_type"] == "valley"]

    print(f"\n{'='*75}")
    print(f"信号汇总:")
    print(f"  放量/剧变信号日: {len(signal_dates)} 天")
    print(f"  MA5 顶点: {', '.join(str(r['date']) for r in peak_dates)}")
    print(f"  MA5 谷底: {', '.join(str(r['date']) for r in valley_dates)}")


def main():
    start_date = None
    for arg in sys.argv[1:]:
        if arg == "--from" and sys.argv.index(arg) + 1 < len(sys.argv):
            start_date = sys.argv[sys.argv.index(arg) + 1]

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    results = detect(conn, start_date)
    print_results(results)
    conn.close()


if __name__ == "__main__":
    main()
