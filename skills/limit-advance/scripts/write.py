"""将连板晋级数据写入飞书 Bitable。

策略：MERGE 模式——按股票名称查重，已存在则合并日期列，不存在则新增。
日期从旧到新串行写入，列自然按时间排列，无需 reorder。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, api, fetch_all_records,
    list_fields, create_field, delete_field, get_table_id,
    batch_update, batch_delete,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLE_KEY = "limit_advance"

DATE_RE = re.compile(r"^\d{2}-\d{2}$")
REMOVE_FIELDS = {"连板", "题材", "代码", "首板日期", "涨幅", "晋级率"}


def get_token():
    return _get_token(cfg)


def _require_complete(operation: str, requested: int, completed: int) -> None:
    if completed == requested:
        return
    print(
        f"{operation}部分失败：请求 {requested} 条，实际成功 {completed} 条",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError) as e:
        print(f"stdin JSON 解析失败: {e}", file=sys.stderr)
        print("请检查上游 scrape.py 的输出", file=sys.stderr)
        sys.exit(1)

    stocks = data.get("stocks", [])
    trading_days = data.get("trading_days", [])
    date_str = data.get("date", "")

    if not stocks:
        print("无数据需要写入")
        return

    token = get_token()
    tid = get_table_id(token, TABLE_KEY, "连板晋级", app_token=APP_TOKEN)
    if not tid:
        print("无法获取表格 ID", file=sys.stderr)
        return

    # Clean up unwanted fixed fields
    for f in list_fields(token, tid, app_token=APP_TOKEN):
        if f["field_name"] in REMOVE_FIELDS:
            delete_field(token, tid, f["field_id"], app_token=APP_TOKEN)

    # Ensure 序号 and date fields exist
    existing = {f["field_name"] for f in list_fields(token, tid, app_token=APP_TOKEN)}
    if "序号" not in existing:
        create_field(token, tid, "序号", 2, app_token=APP_TOKEN)
    for day in trading_days:
        if day not in existing:
            create_field(token, tid, day, app_token=APP_TOKEN)

    # Build current batch: stock_name → fields
    batch_map = {}
    for s in stocks:
        fd = s["first_date"]
        fields_data = {"股票简称": s["name"]}
        if fd in trading_days and date_str in trading_days:
            fi = trading_days.index(fd)
            ci = trading_days.index(date_str)
            for i in range(fi, ci + 1):
                fields_data[trading_days[i]] = s["name"]
        batch_map[s["name"]] = fields_data

    # Read existing records and dedup: keep only the FIRST record per name
    all_records = fetch_all_records(token, tid, app_token=APP_TOKEN)
    name_to_record = {}
    duplicate_ids = []
    for r in all_records:
        name = str(r["fields"].get("股票简称", "")).strip()
        if name in name_to_record:
            duplicate_ids.append(r["record_id"])
        elif name:
            name_to_record[name] = r

    # Delete duplicates
    batch_delete(token, tid, duplicate_ids, app_token=APP_TOKEN, chunk_size=500)
    if duplicate_ids:
        print(f"清理 {len(duplicate_ids)} 条重复记录")

    # Classify: update vs create
    to_update = []
    to_create = []
    for name, new_fields in batch_map.items():
        if name in name_to_record:
            old_fields = name_to_record[name]["fields"]
            merged = dict(old_fields)
            merged.update(new_fields)
            merged.pop("序号", None)
            to_update.append({
                "record_id": name_to_record[name]["record_id"],
                "fields": merged,
            })
        else:
            to_create.append(new_fields)

    # Batch update existing records
    updated = batch_update(token, tid, to_update, app_token=APP_TOKEN, chunk_size=500)
    _require_complete("更新", len(to_update), updated)

    # Batch create new records
    created = 0
    for i in range(0, len(to_create), 500):
        batch = [{"fields": f} for f in to_create[i:i + 500]]
        result = api("POST", "/records/batch_create", token, {"records": batch},
                     table_id=tid, app_token=APP_TOKEN)
        created += len(result.get("data", {}).get("records", []))

    _require_complete("新增", len(to_create), created)
    print(f"更新 {updated} 条，新增 {created} 条")

    # Reassign 序号 by first appearance date (正序), then by name
    all_records = fetch_all_records(token, tid, app_token=APP_TOKEN)
    scored = []
    for r in all_records:
        f = r["fields"]
        dates = sorted(k for k in f if DATE_RE.match(k) and f.get(k))
        first_date = dates[0] if dates else "99-99"
        name = str(f.get("股票简称", "")).strip()
        scored.append((first_date, name, r["record_id"]))
    scored.sort()
    updates = []
    for i, (_, _, rid) in enumerate(scored, 1):
        updates.append({"record_id": rid, "fields": {"序号": i}})
    reordered = batch_update(token, tid, updates, app_token=APP_TOKEN, chunk_size=500)
    _require_complete("序号重排", len(updates), reordered)
    print(f"序号已按首板日期重排（{reordered} 条）")

    # Verify write
    verify_records = fetch_all_records(token, tid, app_token=APP_TOKEN)
    empty_report = {}
    for r in verify_records:
        fields = r["fields"]
        name = str(fields.get("股票简称", "")).strip()
        label = name or r["record_id"]
        if not name:
            empty_report.setdefault(label, []).append("股票简称")
        date_fields = [k for k in fields if DATE_RE.match(k) and str(fields.get(k, "")).strip()]
        if not date_fields:
            empty_report.setdefault(label, []).append("无日期列数据")
    if empty_report:
        print(f"⚠ {len(empty_report)} 条记录有空字段:")
        for label, fields_list in empty_report.items():
            print(f"  {label}: {', '.join(fields_list)}")
    else:
        print(f"写入验证通过 ({len(verify_records)} 条) ✓")


if __name__ == "__main__":
    main()
