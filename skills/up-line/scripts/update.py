"""从飞书三张表读取股票，查询 MA26+STD26，计算 UP 线并写回。"""
import argparse
import math
import sys
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, fetch_all_records,
    batch_update, list_fields, create_field,
    ifind_query, parse_md_table, pad, fmt,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLES = {
    "自选股": cfg["tables"]["watchlist"],
    "强势股": cfg["tables"]["top_gainers"],
    "大成交": cfg["tables"]["high_volume_gainers"],
}


def get_token():
    return _get_token(cfg)


def ensure_fields(token, table_id):
    fields = list_fields(token, table_id, app_token=APP_TOKEN)
    existing = {f["field_name"] for f in fields}
    for name in ("UP", "偏离度"):
        if name not in existing:
            create_field(token, table_id, name, field_type=2, app_token=APP_TOKEN)


def read_table(token, table_id, label):
    items = fetch_all_records(token, table_id, app_token=APP_TOKEN)
    records = []
    for item in items:
        fields = item.get("fields", {})
        name = str(fields.get("股票简称", "") or fields.get("股票名称", "")).strip()
        code = str(fields.get("股票代码", "")).strip()
        if not name:
            continue
        if "ST" in name:
            continue
        if code.endswith(".BJ"):
            continue
        records.append({
            "record_id": item["record_id"],
            "table_id": table_id,
            "name": name,
            "code": code or name,
            "source": label,
            "date": str(fields.get("日期", "")),
        })
    return records


def filter_latest(records):
    by_date = {}
    for r in records:
        by_date.setdefault(r["date"], []).append(r)
    if not by_date:
        return []
    latest = sorted(by_date.keys())[-1]
    return by_date[latest]


def field_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("name") or item.get("value") or ""))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    return str(value).strip()


def query_one_with_anchor(name, anchor, indicator):
    query = f"{anchor}、{name}的{indicator}，周期26日"
    data = ifind_query(query, timeout=60)
    if not data:
        return None
    parsed = parse_md_table(data.get("answer", ""))
    return parsed.get(name)


def _parse_combined(answer, ma_dict, std_dict):
    """解析同时包含 STD标准差 和 MA简单移动平均 两列的表格。"""
    if not answer:
        return
    lines = [line for line in answer.strip().split("\n") if line.strip()]
    if len(lines) < 3:
        return
    headers = [h.strip() for h in lines[0].split("|") if h.strip()]
    name_col = None
    ma_col = None
    std_col = None
    for i, h in enumerate(headers):
        if "简称" in h or "名称" in h:
            name_col = i
        if "MA" in h and "移动" in h:
            ma_col = i
        if "STD" in h or "标准差" in h:
            std_col = i
    if name_col is None:
        return
    for line in lines[1:]:
        if "---" in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) <= max(name_col or 0, ma_col or 0, std_col or 0):
            continue
        name = cells[name_col]
        if name in ma_dict:
            continue
        try:
            if ma_col is not None and cells[ma_col]:
                ma_dict[name] = float(cells[ma_col].replace(",", ""))
        except (ValueError, IndexError):
            pass
        try:
            if std_col is not None and cells[std_col]:
                std_dict[name] = float(cells[std_col].replace(",", ""))
        except (ValueError, IndexError):
            pass


def batch_query(stocks):
    all_ma26 = {}
    all_std26 = {}
    all_prices = {}
    batch_size = 5

    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i + batch_size]
        names = "、".join(s["name"] for s in batch)

        # MA 和 STD 合并为一次查询
        data = ifind_query(f"{names}的MA简单移动平均和STD标准差，周期26日", timeout=60)
        if data:
            _parse_combined(data.get("answer", ""), all_ma26, all_std26)

        # 收盘价
        data = ifind_query(f"{names}今日收盘价", timeout=60)
        if data:
            all_prices.update(parse_md_table(data.get("answer", "")))

    # 对缺失数据逐只重试
    missing = [s for s in stocks
               if s["name"] not in all_ma26 or s["name"] not in all_std26 or s["name"] not in all_prices]
    if missing and all_ma26:
        anchor = next(n for n in all_ma26 if all_ma26[n])
        for s in missing:
            if s["name"] not in all_ma26 or s["name"] not in all_std26:
                data = ifind_query(f"{anchor}、{s['name']}的MA简单移动平均和STD标准差，周期26日", timeout=60)
                if data:
                    _parse_combined(data.get("answer", ""), all_ma26, all_std26)
            if s["name"] not in all_prices:
                data = ifind_query(f"{anchor}、{s['name']}今日收盘价", timeout=60)
                if data:
                    parsed = parse_md_table(data.get("answer", ""))
                    if s["name"] in parsed:
                        all_prices[s["name"]] = parsed[s["name"]]

    return all_ma26, all_std26, all_prices


def local_query(stocks):
    from market_feature_store.db import connect
    all_ma26 = {}
    all_std26 = {}
    all_prices = {}
    con = connect(read_only=True)
    try:
        for s in stocks:
            term = s["name"]
            code = s["code"]
            plain = str(code).split(".")[0]
            rows = con.execute(
                """
                SELECT trade_date, stock_ts_code, stock_name, close
                FROM fact_stock_daily
                WHERE stock_name = ? OR stock_ts_code = ? OR split_part(stock_ts_code, '.', 1) = ?
                ORDER BY trade_date DESC
                LIMIT 26
                """,
                [term, code, plain],
            ).fetchall()
            if len(rows) < 26:
                continue
            name = rows[0][2]
            closes = [float(r[3]) for r in rows if r[3] is not None]
            if len(closes) < 26:
                continue
            ma26 = sum(closes) / len(closes)
            std26 = math.sqrt(sum((x - ma26) ** 2 for x in closes) / len(closes))
            s["name"] = name
            s["code"] = rows[0][1]
            s["data_source"] = "本地行情"
            all_ma26[name] = ma26
            all_std26[name] = std26
            all_prices[name] = closes[0]
    finally:
        con.close()
    return all_ma26, all_std26, all_prices


def find_records(token, terms):
    found = []
    normalized = [str(t).strip() for t in terms if str(t).strip()]
    for label, table_id in TABLES.items():
        for item in fetch_all_records(token, table_id, app_token=APP_TOKEN):
            fields = item.get("fields", {})
            name = field_text(fields.get("股票简称") or fields.get("股票名称"))
            code = field_text(fields.get("股票代码"))
            if not name and not code:
                continue
            for term in normalized:
                if term == name or term == code or term in name:
                    found.append({
                        "record_id": item["record_id"],
                        "table_id": table_id,
                        "name": name or term,
                        "code": code or term,
                        "source": label,
                        "stored_up": fields.get("UP"),
                        "stored_dev": fields.get("偏离度"),
                    })
                    break
    return found


def query_main(argv):
    parser = argparse.ArgumentParser(description="查询个股 UP 和偏离度，不写回飞书")
    parser.add_argument("stocks", nargs="+", help="股票简称或代码，可一次输入多个")
    args = parser.parse_args(argv)
    token = get_token()
    matches = find_records(token, args.stocks)
    unique = {}
    matched_terms = set()
    for r in matches:
        key = r["code"] or r["name"]
        unique.setdefault(key, {"name": r["name"], "code": r["code"], "records": []})
        unique[key]["records"].append(r)
        matched_terms.add(r["name"])
        matched_terms.add(r["code"])
    for term in args.stocks:
        if term not in matched_terms and term not in unique:
            unique[term] = {"name": term, "code": term, "records": []}
    stocks = list(unique.values())
    print(f"查询 {len(stocks)} 只，获取 MA26/STD26/收盘价中...")
    all_ma26, all_std26, all_prices = local_query(stocks)
    missing_stocks = [
        s for s in stocks
        if s["name"] not in all_ma26 or s["name"] not in all_std26 or s["name"] not in all_prices
    ]
    if missing_stocks:
        ma2, std2, price2 = batch_query(missing_stocks)
        for s in missing_stocks:
            if s["name"] in ma2 or s["name"] in std2 or s["name"] in price2:
                s["data_source"] = "iFinD"
        all_ma26.update(ma2)
        all_std26.update(std2)
        all_prices.update(price2)
    W = 96
    print()
    print("═" * W)
    print("  个股 UP / 偏离度查询")
    print("═" * W)
    header = (
        f" {pad('股票', 10)}  {pad('最新价', 8, 'right')}  {pad('MA26', 8, 'right')}  "
        f"{pad('STD26', 8, 'right')}  {pad('UP', 8, 'right')}  {pad('偏离度', 8, 'right')}  "
        f"{pad('状态', 8)}  来源"
    )
    print(header)
    print(" " + "─" * (W - 1))
    missing = []
    for s in stocks:
        name = s["name"]
        ma26 = all_ma26.get(name)
        std26 = all_std26.get(name)
        price = all_prices.get(name)
        if ma26 is None or std26 is None:
            missing.append(name)
            up_val = None
            dev = None
            status = "缺数据"
        else:
            up_val = round(ma26 + 0.764 * std26, 2)
            dev = round((price / up_val - 1) * 100, 2) if price and up_val else None
            if dev is None:
                status = "缺价格"
            elif dev >= 0:
                status = "站上UP"
            else:
                status = "低于UP"
        sources = sorted({r["source"] for r in s.get("records", [])}) or [s.get("data_source", "实时查询")]
        row = (
            f" {pad(name, 10)}  {pad(fmt(price), 8, 'right')}  {pad(fmt(ma26), 8, 'right')}  "
            f"{pad(fmt(std26), 8, 'right')}  {pad(fmt(up_val), 8, 'right')}  "
            f"{pad((f'{dev}%' if dev is not None else '—'), 8, 'right')}  "
            f"{pad(status, 8)}  {','.join(sources)}"
        )
        print(row)
    print()
    if missing:
        print(f"⚠ {len(missing)} 只 MA26/STD26 缺失: {', '.join(missing)}")


def main():
    token = get_token()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 确保每张表有 UP/偏离度 字段
    for table_id in TABLES.values():
        ensure_fields(token, table_id)

    # 2. 读取三张表
    all_records = []
    for label, table_id in TABLES.items():
        records = read_table(token, table_id, label)
        all_records.extend(records)
        print(f"  {label}: {len(records)} 只")

    if not all_records:
        print("无股票数据")
        return

    # 3. 去重并汇总
    unique = {}
    for r in all_records:
        key = r["code"]
        if key not in unique:
            unique[key] = {"name": r["name"], "code": r["code"], "records": []}
        unique[key]["records"].append(r)
    stocks = list(unique.values())
    print(f"  去重后: {len(stocks)} 只，查询 MA26/STD26 中...")

    # 4. 批量查询
    all_ma26, all_std26, all_prices = batch_query(stocks)

    # 5. 计算 UP/偏离度 并更新（偏离度用收盘价）
    table_updates = {}  # table_id -> [records]
    results = []

    for s in stocks:
        name = s["name"]
        ma26 = all_ma26.get(name)
        std26 = all_std26.get(name)
        price = all_prices.get(name)
        if ma26 is None or std26 is None:
            results.append((name, "—", "—", "—"))
            continue
        up_val = round(ma26 + 0.764 * std26, 2)
        dev = round((price / up_val - 1) * 100, 2) if price and up_val else None
        results.append((name, fmt(price), fmt(up_val), f"{dev}%" if dev is not None else "—"))

        for r in s["records"]:
            tid = r["table_id"]
            table_updates.setdefault(tid, []).append({
                "record_id": r["record_id"],
                "fields": {"UP": up_val, "偏离度": dev if dev is not None else 0},
            })

    # 6. 批量写入飞书
    total_updated = 0
    for tid, recs in table_updates.items():
        n = batch_update(token, tid, recs, app_token=APP_TOKEN)
        total_updated += n

    # 7. 写入验证
    for tid, recs in table_updates.items():
        record_ids = {r["record_id"] for r in recs}
        written = fetch_all_records(token, tid, app_token=APP_TOKEN)
        label = next((l for l, t in TABLES.items() if t == tid), tid)
        empty_count = 0
        for r in written:
            if r["record_id"] not in record_ids:
                continue
            f = r["fields"]
            name = str(f.get("股票简称", "") or f.get("股票名称", "")).strip()
            up_val = f.get("UP")
            dev_val = f.get("偏离度")
            if up_val is None or str(up_val).strip() == "":
                print(f"  ⚠ [{label}] {name}: UP 为空")
                empty_count += 1
            if dev_val is None or str(dev_val).strip() == "":
                print(f"  ⚠ [{label}] {name}: 偏离度为空")
                empty_count += 1
        if empty_count == 0:
            checked = sum(1 for r in written if r["record_id"] in record_ids)
            print(f"  [{label}] 写入验证通过 ({checked} 条) ✓")

    # 8. 输出表格
    W = 60
    print()
    print("═" * W)
    print(f"  UP 线更新  {today}  共{len(stocks)}只  更新{total_updated}条")
    print("═" * W)
    print()
    header = f" {pad('股票简称', 10)}  {pad('最新价', 8, 'right')}  {pad('UP', 8, 'right')}  {pad('偏离度', 8, 'right')}"
    print(header)
    print(" " + "─" * (W - 1))
    for name, price_s, up_s, dev_s in results:
        row = f" {pad(name, 10)}  {pad(price_s, 8, 'right')}  {pad(up_s, 8, 'right')}  {pad(dev_s, 8, 'right')}"
        print(row)
    print()

    missing = [r[0] for r in results if r[3] == "—"]
    if missing:
        print(f"⚠ {len(missing)} 只数据缺失: {', '.join(missing)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"query", "查", "lookup"}:
        query_main(sys.argv[2:])
    else:
        main()
