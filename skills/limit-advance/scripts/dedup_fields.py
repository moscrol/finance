"""One-shot script: deduplicate date fields in 连板晋级 table.

For each date name with multiple fields:
1. Keep the first field (by field_id order)
2. Merge any data from duplicate fields into the kept field
3. Delete the duplicate fields
"""
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import (
    load_config, get_token as _get_token, list_fields, delete_field,
    fetch_all_records, batch_update, get_table_id,
)

cfg = load_config()
APP_TOKEN = cfg["app_token"]
DATE_RE = re.compile(r"^\d{2}-\d{2}$")


def main():
    token = _get_token(cfg)
    tid = get_table_id(token, "limit_advance", "连板晋级", app_token=APP_TOKEN)
    if not tid:
        print("无法获取表格 ID", file=sys.stderr)
        return

    fields = list_fields(token, tid, app_token=APP_TOKEN)
    groups = defaultdict(list)
    for f in fields:
        if DATE_RE.match(f["field_name"]):
            groups[f["field_name"]].append(f)

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    if not dupes:
        print("无重复字段，无需处理")
        return

    print(f"发现 {len(dupes)} 个重复日期字段名")

    # Fetch all records once
    records = fetch_all_records(token, tid, app_token=APP_TOKEN)
    print(f"共 {len(records)} 条记录")

    # For each duplicate group: keep first, merge data from others, delete others
    updates = []
    fields_to_delete = []

    for name, flds in sorted(dupes.items()):
        keep = flds[0]
        extras = flds[1:]

        # Check records for data in extra fields
        for r in records:
            rf = r["fields"]
            has_data_in_extra = any(rf.get(ef["field_id"]) or rf.get(name) for ef in extras)
            if has_data_in_extra and not rf.get(name):
                # Data is only in a duplicate field — need to copy it
                for ef in extras:
                    val = rf.get(ef["field_id"])
                    if val:
                        # We'll update using the field name (which maps to the kept field)
                        updates.append({
                            "record_id": r["record_id"],
                            "fields": {name: val},
                        })
                        break

        fields_to_delete.extend(extras)
        print(f"  {name}: 保留 {keep['field_id']}, 删除 {len(extras)} 个重复")

    # Apply updates (merge data from duplicate fields into kept field)
    if updates:
        batch_update(token, tid, updates, app_token=APP_TOKEN, chunk_size=500)
        print(f"合并 {len(updates)} 条记录的数据")

    # Delete duplicate fields
    for f in fields_to_delete:
        try:
            delete_field(token, tid, f["field_id"], app_token=APP_TOKEN)
            time.sleep(0.1)
        except Exception as e:
            print(f"  删除 {f['field_name']} ({f['field_id']}) 失败: {e}")

    print(f"已删除 {len(fields_to_delete)} 个重复字段")

    # Verify
    fields_after = list_fields(token, tid, app_token=APP_TOKEN)
    date_fields_after = [f for f in fields_after if DATE_RE.match(f["field_name"])]
    after_groups = defaultdict(list)
    for f in date_fields_after:
        after_groups[f["field_name"]].append(f)
    remaining_dupes = {k: v for k, v in after_groups.items() if len(v) > 1}
    if remaining_dupes:
        print(f"警告：仍有 {len(remaining_dupes)} 个重复: {list(remaining_dupes.keys())}")
    else:
        print(f"验证通过：{len(date_fields_after)} 个唯一日期字段")


if __name__ == "__main__":
    main()
