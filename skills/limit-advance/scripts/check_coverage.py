"""检查飞书「连板晋级」表的日期覆盖情况。

对比表中已有的日期列与指定月份的交易日序列，找出未抓取的日期。

用法：
  python3 check_coverage.py [MM]          # 检查指定月份，默认当前月
  python3 check_coverage.py --all         # 检查所有已有日期的连续性
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import load_config, get_token as _get_token, api, fetch_all_records, list_fields

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLE_KEY = "limit_advance"

DATE_RE = re.compile(r"^\d{2}-\d{2}$")


def get_token():
    return _get_token(cfg)


def get_table_id(token):
    tid = cfg["tables"].get(TABLE_KEY)
    if tid:
        return tid
    result = api("GET", "/tables", token, app_token=APP_TOKEN)
    for t in result.get("data", {}).get("items", []):
        if t.get("name") == "连板晋级":
            return t["table_id"]
    return None


def get_weekdays(year, month):
    """Return list of weekday dates (Mon-Fri) for given month as MM-DD strings."""
    days = []
    d = datetime(year, month, 1)
    while d.month == month:
        if d.weekday() < 5:
            days.append(d.strftime("%m-%d"))
        d += timedelta(days=1)
    return days


def infer_year(date_cols):
    """从已有日期列推断年份。取最早日期的月份，如果 > 当前月则去年，否则今年。"""
    if not date_cols:
        return datetime.now().year
    earliest = sorted(date_cols)[0]
    mm = int(earliest.split("-")[0])
    now = datetime.now()
    return now.year - 1 if mm > now.month else now.year


def main():
    args = sys.argv[1:]
    check_all = "--all" in args
    month_arg = [a for a in args if a not in ("--all",)]

    # 输入校验
    if month_arg:
        try:
            month = int(month_arg[0])
            if not 1 <= month <= 12:
                print(f"月份必须在 1-12 之间，收到: {month}", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            print(f"无效的月份参数: {month_arg[0]}", file=sys.stderr)
            sys.exit(1)

    token = get_token()
    tid = get_table_id(token)
    if not tid:
        print("未找到「连板晋级」表")
        return

    # Get date columns from Feishu
    fields = list_fields(token, tid, app_token=APP_TOKEN)
    date_cols = sorted([f["field_name"] for f in fields if DATE_RE.match(f["field_name"])])

    if not date_cols:
        print("表中无日期列")
        return

    # Get records to check data density
    records = fetch_all_records(token, tid, app_token=APP_TOKEN)
    date_counts = {}
    for r in records:
        f = r.get("fields", {})
        for k, v in f.items():
            if DATE_RE.match(k) and v:
                date_counts[k] = date_counts.get(k, 0) + 1

    year = infer_year(date_cols)

    if check_all:
        # Check all dates for gaps
        print(f"表中日期列：{date_cols[0]} ~ {date_cols[-1]}，共 {len(date_cols)} 列")
        print()

        start_mm, start_dd = map(int, date_cols[0].split("-"))
        end_mm, end_dd = map(int, date_cols[-1].split("-"))
        start = datetime(year, start_mm, start_dd)
        end = datetime(year, end_mm, end_dd)

        all_weekdays = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                all_weekdays.append(d.strftime("%m-%d"))
            d += timedelta(days=1)

        date_set = set(date_cols)
        missing = [d for d in all_weekdays if d not in date_set]

        if missing:
            print(f"⚠ 缺失 {len(missing)} 个交易日（可能是节假日，也可能是未抓取）：")
            for d in missing:
                print(f"  {d}")
        else:
            print("所有工作日都有对应的日期列")

        print()
        print("各日期数据密度：")
        for d in all_weekdays:
            cnt = date_counts.get(d, 0)
            status = "✓" if cnt > 0 else "✗ 无数据"
            if d not in date_set:
                status = "⚠ 无列"
            print(f"  {d}: {cnt:2d} 只  {status}")

    else:
        if month_arg:
            month = int(month_arg[0])
        else:
            month = datetime.now().month

        weekdays = get_weekdays(year, month)
        month_prefix = f"{month:02d}-"
        existing = [d for d in date_cols if d.startswith(month_prefix)]
        existing_set = set(existing)

        missing_weekdays = [d for d in weekdays if d not in existing_set]

        print(f"{month}月检查（{year}年）：")
        print(f"  工作日：{len(weekdays)} 天")
        print(f"  已有列：{len(existing)} 天")
        print(f"  缺失：{len(missing_weekdays)} 天")

        if missing_weekdays:
            print()
            print("未覆盖的工作日：")
            for d in missing_weekdays:
                cnt = date_counts.get(d, 0)
                print(f"  {d}  {'（无数据）' if cnt == 0 else f'（{cnt} 只，需单独抓取）'}")
            print()
            print("建议抓取命令：")
            dates_str = " ".join(missing_weekdays)
            print(f"  for d in {dates_str}; do python3 scrape.py --json $d | python3 write.py; done")
        else:
            print(f"  {month}月所有工作日已覆盖 ✓")


if __name__ == "__main__":
    main()
