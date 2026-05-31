"""检查飞书「每日指标」表的日期覆盖情况。

对比表中已有的日期与指定月份的交易日序列，找出未写入的日期。

用法：
  python3 check_coverage.py [MM]          # 检查指定月份，默认当前月
  python3 check_coverage.py --all         # 检查所有已有日期的连续性
"""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import load_config, get_token as _get_token, api, fetch_all_records

cfg = load_config()
APP_TOKEN = cfg["app_token"]
TABLE_ID = cfg["tables"]["daily"]

DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{2}$")  # YY-MM-DD
MMDD_RE = re.compile(r"^\d{2}-\d{2}$")  # MM-DD


def get_token():
    return _get_token(cfg)


def get_weekdays(year, month):
    days = []
    d = datetime(year, month, 1)
    while d.month == month:
        if d.weekday() < 5:
            days.append(d.strftime("%m-%d"))
        d += timedelta(days=1)
    return days


def infer_year(existing_dates):
    """从已有日期推断年份。"""
    if not existing_dates:
        return datetime.now().year
    # 取最早的 MM-DD，如果月份 > 当前月则去年
    earliest = sorted(existing_dates)[0]
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
    records = fetch_all_records(token, TABLE_ID, app_token=APP_TOKEN)

    if not records:
        print("表中无记录")
        return

    # Extract dates from records (format: YY-MM-DD → convert to MM-DD)
    existing_dates = set()
    for r in records:
        f = r.get("fields", {})
        d = f.get("日期", "").strip()
        if DATE_RE.match(d):
            existing_dates.add(d[3:])
        elif MMDD_RE.match(d):
            existing_dates.add(d)

    if not existing_dates:
        print("表中无日期记录")
        return

    sorted_dates = sorted(existing_dates)
    year = infer_year(existing_dates)

    if check_all:
        print(f"表中日期：{sorted_dates[0]} ~ {sorted_dates[-1]}，共 {len(sorted_dates)} 天")
        print()

        start_mm, start_dd = map(int, sorted_dates[0].split("-"))
        end_mm, end_dd = map(int, sorted_dates[-1].split("-"))
        start = datetime(year, start_mm, start_dd)
        end = datetime(year, end_mm, end_dd)

        all_weekdays = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                all_weekdays.append(d.strftime("%m-%d"))
            d += timedelta(days=1)

        missing = [d for d in all_weekdays if d not in existing_dates]

        if missing:
            print(f"⚠ 缺失 {len(missing)} 个工作日（可能是节假日，也可能是未写入）：")
            for d in missing:
                print(f"  {d}")
        else:
            print("所有工作日已覆盖 ✓")

    else:
        if month_arg:
            month = int(month_arg[0])
        else:
            month = datetime.now().month

        weekdays = get_weekdays(year, month)
        month_prefix = f"{month:02d}-"
        existing_in_month = [d for d in sorted_dates if d.startswith(month_prefix)]
        missing = [d for d in weekdays if d not in existing_dates]

        print(f"{month}月检查（{year}年）：")
        print(f"  工作日：{len(weekdays)} 天")
        print(f"  已写入：{len(existing_in_month)} 天")
        print(f"  缺失：{len(missing)} 天")

        if missing:
            print()
            print("未覆盖的工作日：")
            for d in missing:
                print(f"  {d}")
        else:
            print(f"  {month}月所有工作日已覆盖 ✓")


if __name__ == "__main__":
    main()
