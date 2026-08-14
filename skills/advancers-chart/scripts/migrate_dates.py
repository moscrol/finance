"""批量更新三个飞书表格的日期字段：MM-DD → YY-MM-DD（使用批量API）"""
import json
import sys
import urllib.request
import urllib.parse
from datetime import date as date_cls
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import load_config, get_token as _get_token

cfg = load_config()
APP_TOKEN = cfg["app_token"]

TABLES = {
    "每日指标": "tbljGvjtl1IC44hb",
    "板块趋势": "tblshRMmRnQYrM4K",
    "涨家数走势": "tblqehYBeoYd2n2k",
}

def get_token():
    return _get_token(cfg)


def fetch_all_records(token, table_id):
    base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {token}"}
    all_items = []
    page_token = None
    while True:
        params = {"page_size": "500"}
        if page_token:
            params["page_token"] = page_token
        url = base_url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        items = result.get("data", {}).get("items", [])
        if not items:
            break
        all_items.extend(items)
        page_token = result.get("data", {}).get("page_token")
        if not page_token or not result.get("data", {}).get("has_more"):
            break
    return all_items


def mmdd_to_yymmdd(date_str):
    """Convert MM-DD to YY-MM-DD. Skip if already in YY-MM-DD format."""
    parts = date_str.split("-")
    if len(parts) == 3:
        return None
    m = int(parts[0])
    current_month = date_cls.today().month
    year = date_cls.today().year if m <= current_month else date_cls.today().year - 1
    yy = str(year)[2:]
    return f"{yy}-{parts[0]}-{parts[1]}"


def batch_update(token, table_id, updates):
    """Batch update records. updates = [(record_id, new_date), ...]"""
    base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records/batch_update"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Feishu batch_update supports max 500 per call
    batch_size = 500
    total_updated = 0
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        records = [{"record_id": rid, "fields": {"日期": new_date}} for rid, new_date in batch]
        body = json.dumps({"records": records}).encode()
        req = urllib.request.Request(base_url, data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        if result.get("code") == 0:
            count = len(result.get("data", {}).get("records", []))
            total_updated += count
        else:
            print(f"  批量更新失败: {result.get('msg', 'unknown error')}")
    return total_updated


def main():
    print("获取 token...")
    token = get_token()

    for table_name, table_id in TABLES.items():
        print(f"\n处理表: {table_name}")
        items = fetch_all_records(token, table_id)
        print(f"共 {len(items)} 条记录")

        updates = []
        skipped = 0
        for item in items:
            fields = item.get("fields", {})
            date_str = fields.get("日期", "")
            if not date_str:
                skipped += 1
                continue
            new_date = mmdd_to_yymmdd(date_str)
            if new_date is None:
                skipped += 1
                continue
            updates.append((item["record_id"], new_date))

        if updates:
            count = batch_update(token, table_id, updates)
            print(f"更新 {count} 条, 跳过 {skipped} 条")
        else:
            print(f"无需更新, 跳过 {skipped} 条")


if __name__ == "__main__":
    main()
