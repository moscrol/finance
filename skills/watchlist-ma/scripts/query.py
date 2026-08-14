"""从飞书自选股表读取股票，查询iFinD获取价格和均线，筛选回踩股"""
import json
import sys
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, fetch_all_records,
    ifind_query, parse_md_table,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
WATCHLIST_TABLE = cfg["tables"]["watchlist"]


def get_token():
    return _get_token(cfg)


def read_watchlist(token):
    items = fetch_all_records(token, WATCHLIST_TABLE, app_token=APP_TOKEN)
    stocks = []
    for item in items:
        fields = item.get("fields", {})
        code = str(fields.get("股票代码", "")).strip()
        name = str(fields.get("股票名称", "")).strip()
        if name and code:
            stocks.append({"code": code, "name": name})
    return stocks


def query_batch(batch, query_template):
    """查询一批股票的指定指标，返回 {名称: 数值}"""
    names = "、".join(s["name"] for s in batch)
    data = ifind_query(query_template.format(names=names), timeout=60)
    return parse_md_table(data.get("answer", "") if data else "")


def main():
    print("读取自选股...", file=sys.stderr)
    token = get_token()
    stocks = read_watchlist(token)
    if not stocks:
        print("自选股表为空")
        return

    print(f"共 {len(stocks)} 只股票", file=sys.stderr)

    batch_size = 5
    all_prices = {}
    all_ma10 = {}
    all_ma20 = {}

    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i + batch_size]
        names = "、".join(s["name"] for s in batch)
        print(f"  查询 {names}...", file=sys.stderr)

        # 并行查询 3 个指标
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_price = executor.submit(query_batch, batch, "{names}的最新收盘价")
            f_ma10 = executor.submit(query_batch, batch, "{names}的MA简单移动平均，周期10日")
            f_ma20 = executor.submit(query_batch, batch, "{names}的MA简单移动平均，周期20日")
            all_prices.update(f_price.result())
            all_ma10.update(f_ma10.result())
            all_ma20.update(f_ma20.result())

    filtered = []
    missing = []
    for s in stocks:
        name = s["name"]
        price = all_prices.get(name)
        ma10 = all_ma10.get(name)
        ma20 = all_ma20.get(name)
        if price is None or ma10 is None or ma20 is None:
            missing.append(name)
            continue
        if ma20 < price < ma10:
            pct = round((price - ma20) / ma20 * 100, 2) if ma20 != 0 else 0
            filtered.append({
                "code": s["code"],
                "name": name,
                "price": price,
                "ma10": ma10,
                "ma20": ma20,
                "above_ma20_pct": pct,
            })

    output = {
        "date": date.today().isoformat(),
        "total": len(stocks),
        "filtered": filtered,
    }
    if missing:
        output["missing"] = missing
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
