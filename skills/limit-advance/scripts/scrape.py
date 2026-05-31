"""抓取 fupanhui.com 连板梯队数据（通过内部 API）。"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime

PROXY = os.environ.get("CDP_PROXY_URL", "http://localhost:3456")


def cdp_get(path, params=None):
    cmd = ["curl", "-s", "-G", f"{PROXY}{path}"]
    if params:
        for k, v in params:
            cmd += ["--data-urlencode", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def cdp_eval(target, expr):
    cmd = ["curl", "-s", "-X", "POST", f"{PROXY}/eval?target={target}",
           "-d", f"expr={expr}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def fetch_api(target, api_path):
    js = ("(function(){var x=new XMLHttpRequest();"
          "x.open('GET','" + api_path + "',false);"
          "x.send();return x.responseText;})()")
    r = cdp_eval(target, js)
    try:
        return json.loads(r.get("value", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}


def get_trading_days(target, trade_date, span=30):
    year = int(trade_date[:4])
    month = int(trade_date[5:7])
    all_days = []
    for offset in range((span // 20) + 2):
        m = month - offset
        y = year
        while m <= 0:
            m += 12
            y -= 1
        cal = fetch_api(target, f"/api/v1/client/calendar/month?year={y}&month={m}")
        for day in cal.get("data", {}).get("days", []):
            if day.get("is_trading_day"):
                all_days.append(day["trade_date"])
    all_days = sorted(set(all_days))
    return [d for d in all_days if d <= trade_date]


def main():
    args = [a for a in sys.argv[1:] if a not in ("--json",) and not a.startswith("--min-boards")]
    json_mode = "--json" in sys.argv
    min_boards = 3
    for a in sys.argv[1:]:
        if a.startswith("--min-boards="):
            min_boards = int(a.split("=")[1])
    date_arg = args[0] if args else None

    resp = cdp_get("/new", [("url", "https://fupanhui.com")])
    target = resp.get("targetId")
    if not target:
        print("无法连接 CDP 代理")
        return
    try:
        time.sleep(2)

        if date_arg:
            today = datetime.now()
            parts = date_arg.split("-")
            if len(parts) == 2:
                m, d = int(parts[0]), int(parts[1])
                api_date = f"{today.year}-{m:02d}-{d:02d}"
                if api_date > today.strftime("%Y-%m-%d"):
                    api_date = f"{today.year - 1}-{m:02d}-{d:02d}"
            else:
                api_date = date_arg
        else:
            latest = fetch_api(target, "/api/v1/client/reviews/latest-date?mode=auto")
            api_date = latest.get("data", {}).get("latest_date", "")
            if not api_date:
                print("无法获取最新交易日")
                return

        ladder = fetch_api(target, f"/api/v1/client/limit/ladder?trade_date={api_date}")
        data = ladder.get("data", {})
        if not data:
            print(f"日期 {api_date}: 无连板数据")
            return

        trade_date = data.get("trade_date", api_date)
        max_level = data.get("max_limit_days", 0)
        levels = data.get("levels", [])
        date_str = trade_date[5:]

        trading_days_full = get_trading_days(target, trade_date, max_level + 5)
        trading_days = [d[5:] for d in trading_days_full]

        stocks = []
        for level_data in levels:
            level = level_data["level"]
            if level < min_boards:
                continue
            promoted = level_data["promoted_count"]
            total = level_data["total_count"]
            rate = f"{promoted}/{total}={level_data['promotion_rate']:.0f}%"

            for stock in level_data["stocks"]:
                if stock["status_type"] != "U":
                    continue
                pct = stock["pct_chg"]
                change = f"+{pct:.2f}%" if pct >= 0 else f"{pct:.2f}%"
                theme = stock.get("leader_sub_plate") or stock.get("leader_plate", "")
                stocks.append({
                    "boards": level,
                    "name": stock["name"],
                    "theme": theme,
                    "code": stock["ts_code"],
                    "change": change,
                    "rate": rate,
                })

        if not stocks:
            print(f"日期 {date_str}: 无{min_boards}板以上晋级成功的个股")
            return

        current_idx = trading_days.index(date_str) if date_str in trading_days else -1
        for s in stocks:
            first_idx = current_idx - (s["boards"] - 1)
            s["first_date"] = trading_days[first_idx] if 0 <= first_idx < len(trading_days) else "??"

        earliest = min(s["first_date"] for s in stocks)
        ei = trading_days.index(earliest) if earliest in trading_days else 0
        ci = trading_days.index(date_str) if date_str in trading_days else len(trading_days) - 1
        relevant_days = trading_days[ei:ci + 1]

        if json_mode:
            json.dump({
                "date": date_str,
                "trading_days": relevant_days,
                "stocks": stocks,
            }, sys.stdout, ensure_ascii=False)
            return

        def dw(s):
            w = 0
            for c in s:
                if unicodedata.east_asian_width(c) in ('W', 'F'):
                    w += 2
                else:
                    w += 1
            return w

        def pad(s, width, align='left'):
            s = str(s)
            space = width - dw(s)
            if space <= 0:
                return s
            return ' ' * space + s if align == 'right' else s + ' ' * space

        W = 80
        print()
        print("═" * W)
        print(f"  连板晋级（{min_boards}板以上）  {date_str}  共{len(stocks)}只")
        print("═" * W)
        print()

        by_level = {}
        for s in stocks:
            by_level.setdefault(s["boards"], []).append(s)

        header = (f" {pad('连板', 4, 'right')}  {pad('股票简称', 8)}  "
                  f"{pad('题材', 16)}  {pad('代码', 11)}  "
                  f"{pad('涨幅', 8, 'right')}  {pad('首板', 5)}  晋级率")
        print(header)
        print(" " + "─" * (W - 1))

        for level in sorted(by_level.keys(), reverse=True):
            level_stocks = by_level[level]
            for j, s in enumerate(level_stocks):
                rate_str = s["rate"] if j == 0 else ""
                row = (f" {pad(str(level) + '板', 4, 'right')}  {pad(s['name'], 8)}  "
                       f"{pad(s['theme'] or '—', 16)}  {pad(s['code'], 11)}  "
                       f"{pad(s['change'], 8, 'right')}  {pad(s['first_date'], 5)}  {rate_str}")
                print(row)

        print()

        if relevant_days:
            col_w = 6
            label_w = 10
            total = label_w + col_w * len(relevant_days)
            print("【连板时间轴】")
            print()
            hdr = " " * label_w
            for d in relevant_days:
                hdr += pad(d, col_w, 'right')
            print(hdr)
            print("─" * total)

            for level in sorted(by_level.keys(), reverse=True):
                for s in by_level[level]:
                    row = pad(f"{s['boards']}板 {s['name']}", label_w - 1)
                    fd = s["first_date"]
                    for d in relevant_days:
                        if fd <= d <= date_str and d in trading_days:
                            di = trading_days.index(d)
                            fi = trading_days.index(fd) if fd in trading_days else -1
                            if fi >= 0 and di >= fi:
                                row += pad("■", col_w, 'right')
                                continue
                        row += " " * col_w
                    print(row)
            print()

        themes = {}
        for s in stocks:
            t = s["theme"]
            if t:
                themes.setdefault(t, []).append(s["name"])
        if themes:
            sorted_themes = sorted(themes.items(), key=lambda x: -len(x[1]))
            print("【题材分布】")
            for t, names in sorted_themes:
                print(f"  {t}({len(names)}只)：{'、'.join(names)}")
            print()

    finally:
        cdp_get("/close", [("target", target)])


if __name__ == "__main__":
    main()
