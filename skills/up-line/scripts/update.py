"""从飞书三张表读取股票，查询 MA26+STD26，计算 UP 线并写回。"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
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
    main()
