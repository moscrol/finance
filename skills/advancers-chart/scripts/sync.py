"""从飞书每日指标表读取涨家数，增量同步到涨家数走势表"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, fetch_all_records,
    batch_create, batch_update, parse_date_str,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
DAILY_TABLE = cfg["tables"]["daily"]
CHART_TABLE = cfg["tables"]["chart"]


def get_token():
    return _get_token(cfg)


def build_df(items):
    records = []
    for item in items:
        fields = item.get("fields", {})
        date_str = fields.get("日期", "")
        adv = fields.get("涨", "")
        if date_str and adv:
            try:
                dt = parse_date_str(date_str)
                records.append({"日期": dt, "涨家数": int(adv)})
            except (ValueError, TypeError):
                continue
    records.sort(key=lambda r: r["日期"])
    # MA5 — 使用 pandas rolling 保持与 feishu_chart.py 一致
    for i, r in enumerate(records):
        window = [records[j]["涨家数"] for j in range(max(0, i - 4), i + 1)]
        r["MA5"] = round(sum(window) / len(window), 2)
    return records


def sync(token, records):
    existing = fetch_all_records(token, CHART_TABLE, app_token=APP_TOKEN)
    existing_dates = set()
    existing_map = {}
    for item in existing:
        d = item.get("fields", {}).get("日期", "")
        if d:
            existing_dates.add(d)
            existing_map[d] = item["record_id"]

    # 新增
    new_records = []
    for r in records:
        date_key = r["日期"].strftime("%y-%m-%d")
        if date_key not in existing_dates:
            new_records.append({"fields": {"日期": date_key, "涨家数": r["涨家数"], "MA5": r["MA5"]}})

    added = 0
    if new_records:
        added = batch_create(token, CHART_TABLE, new_records, app_token=APP_TOKEN, chunk_size=500)
        print(f"新增 {added} 条")

    # 更新最近 5 条 MA5
    updates = []
    for r in records[-5:]:
        date_key = r["日期"].strftime("%y-%m-%d")
        if date_key in existing_map:
            updates.append({"record_id": existing_map[date_key], "fields": {"MA5": r["MA5"]}})
    updated = 0
    if updates:
        updated = batch_update(token, CHART_TABLE, updates, app_token=APP_TOKEN)
    if updated:
        print(f"更新 {updated} 条 MA5")

    if not added and not updated:
        print("涨家数走势数据已是最新")


def main():
    print("同步涨家数...")
    token = get_token()
    items = fetch_all_records(token, DAILY_TABLE, app_token=APP_TOKEN)
    print(f"读取 {len(items)} 条每日指标")
    records = build_df(items)
    print(f"解析 {len(records)} 个交易日")
    sync(token, records)


if __name__ == "__main__":
    main()
