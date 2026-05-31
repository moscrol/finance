"""从飞书「强势股」表读取最新一批股票，查询均线并输出对齐表格。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, fetch_all_records,
    ifind_query, parse_md_table, dw, pad, fmt,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLE_ID = cfg["tables"]["top_gainers"]


def get_token():
    return _get_token(cfg)


def read_latest_stocks(token):
    items = fetch_all_records(token, TABLE_ID, app_token=APP_TOKEN)
    if not items:
        return [], ""
    by_date = {}
    for item in items:
        fields = item.get("fields", {})
        d = fields.get("日期", "")
        name = str(fields.get("股票简称", "")).strip()
        code = str(fields.get("股票代码", "")).strip()
        if not (d and name):
            continue
        # 剔除ST
        if "ST" in name:
            continue
        # 剔除北交所
        if code.endswith(".BJ"):
            continue
        by_date.setdefault(d, []).append({
            "name": name,
            "code": code,
            "gain": fields.get("区间涨幅", ""),
            "industry": fields.get("申万行业", ""),
        })
    if not by_date:
        return [], ""
    latest_date = sorted(by_date.keys())[-1]
    return by_date[latest_date], latest_date


def main():
    token = get_token()
    stocks, date_str = read_latest_stocks(token)
    if not stocks:
        print("强势股表为空")
        return

    print(f"日期: {date_str}  共 {len(stocks)} 只，查询均线中...")

    batch_size = 5
    all_prices = {}
    all_ma5 = {}
    all_ma10 = {}
    all_ma20 = {}
    all_ma26 = {}
    all_std26 = {}

    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i + batch_size]
        names = "、".join(s["name"] for s in batch)

        data = ifind_query(f"{names}的最新收盘价", timeout=60)
        all_prices.update(parse_md_table(data.get("answer", "") if data else ""))

        data = ifind_query(f"{names}的MA简单移动平均，周期5日", timeout=60)
        all_ma5.update(parse_md_table(data.get("answer", "") if data else ""))

        data = ifind_query(f"{names}的MA简单移动平均，周期10日", timeout=60)
        all_ma10.update(parse_md_table(data.get("answer", "") if data else ""))

        data = ifind_query(f"{names}的MA简单移动平均，周期20日", timeout=60)
        all_ma20.update(parse_md_table(data.get("answer", "") if data else ""))

        data = ifind_query(f"{names}的MA简单移动平均，周期26日", timeout=60)
        all_ma26.update(parse_md_table(data.get("answer", "") if data else ""))

        data = ifind_query(f"{names}的STD标准差，周期26日", timeout=60)
        all_std26.update(parse_md_table(data.get("answer", "") if data else ""))

    W = 110
    print()
    print("═" * W)
    print(f"  强势股均线分析  {date_str}  共{len(stocks)}只")
    print("═" * W)
    print()

    header = (f" {pad('代码', 10)}  {pad('股票简称', 10)}  {pad('申万行业', 8)}  "
              f"{pad('涨幅(%)', 9, 'right')}  {pad('最新价', 8, 'right')}  "
              f"{pad('MA5', 8, 'right')}  {pad('MA10', 8, 'right')}  {pad('MA20', 8, 'right')}  "
              f"{pad('UP', 8, 'right')}  短回")
    print(header)
    print(" " + "─" * (W - 1))

    filtered_pullback = []
    filtered_short = []
    missing = []
    for s in stocks:
        name = s["name"]
        price = all_prices.get(name)
        ma5 = all_ma5.get(name)
        ma10 = all_ma10.get(name)
        ma20 = all_ma20.get(name)
        ma26 = all_ma26.get(name)
        std26 = all_std26.get(name)

        # UP = MA26 + 0.764 * STD26
        up_val = round(ma26 + 0.764 * std26, 2) if ma26 is not None and std26 is not None else None

        if price is None or ma10 is None or ma20 is None:
            missing.append(name)

        pullback = (price is not None and ma10 is not None and ma20 is not None
                    and ma20 < price < ma10)
        pct_pb = round((price - ma20) / ma20 * 100, 2) if pullback and ma20 != 0 else None
        if pullback:
            filtered_pullback.append((name, price, ma10, ma20, pct_pb))

        short_pullback = (price is not None and ma5 is not None and ma10 is not None
                          and ma10 < price < ma5)
        pct_sp = round((price - ma10) / ma10 * 100, 2) if short_pullback and ma10 != 0 else None
        if short_pullback:
            filtered_short.append((name, price, ma5, ma10, pct_sp))

        row = (f" {pad(s['code'], 10)}  {pad(name, 10)}  {pad(s['industry'], 8)}  "
               f"{pad(s['gain'], 9, 'right')}  {pad(fmt(price), 8, 'right')}  "
               f"{pad(fmt(ma5), 8, 'right')}  {pad(fmt(ma10), 8, 'right')}  {pad(fmt(ma20), 8, 'right')}  "
               f"{pad(fmt(up_val), 8, 'right')}  "
               f"{'✔' if short_pullback else '—'}")
        print(row)

    print()
    if filtered_pullback:
        print("【均线回踩】（MA20 < 价 < MA10）")
        for name, price, ma10, ma20, pct in filtered_pullback:
            print(f"  {name}  {fmt(price)}（高于MA20 {pct}%）")
    else:
        print("【均线回踩】无")

    if filtered_short:
        print("【短线回踩】（MA10 < 价 < MA5）")
        for name, price, ma5, ma10, pct in filtered_short:
            print(f"  {name}  {fmt(price)}（高于MA10 {pct}%）")
    else:
        print("【短线回踩】无")

    if missing:
        print(f"\n⚠ {len(missing)} 只股票数据缺失: {', '.join(missing)}")


if __name__ == "__main__":
    main()
