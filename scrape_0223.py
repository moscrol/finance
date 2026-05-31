import json, subprocess, time, re, sys

PROXY = "http://localhost:3456"
URL = "https://fupanhui.com/workspace/data/limit"

def curl(path, params=None):
    cmd = ["curl", "-s", "-G", f"{PROXY}{path}"]
    if params:
        for k, v in params:
            cmd += ["--data-urlencode", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout.strip() else {}

def eval_js(target, expr):
    return curl("/eval", [("target", target), ("expr", expr)])

resp = curl("/new", [("url", URL)])
target = resp.get("targetId")
if not target:
    print("无法打开页面", file=sys.stderr)
    sys.exit(1)

time.sleep(4)

# Open calendar
eval_js(target, "document.querySelector('._datePickerCompactBtn_1ycdg_19').click();")
time.sleep(1.5)

# Navigate to Feb
navs = "document.querySelectorAll('._calendarNav_1ycdg_166')"
for i in range(3):
    eval_js(target, f"{navs}[0].click();")
    time.sleep(1.5)
time.sleep(1.5)

# Check current month
mt = eval_js(target, "document.querySelector('._calendarMonth_1ycdg_184').textContent;")
print(f"Calendar month: {mt.get('value', '???')}", file=sys.stderr)

# Try clicking day 23 via different event types
result = eval_js(target, """
var days = document.querySelectorAll('._calendarDay_1ycdg_332:not(._empty_1ycdg_353)');
var found = null;
for (var i = 0; i < days.length; i++) {
    if (parseInt(days[i].textContent.trim()) === 23) {
        found = days[i];
        break;
    }
}
if (!found) return 'NOT_FOUND';

// Method 1: try native click
found.click();
return 'CLICKED';
""")
print(f"Click result: {result.get('value', '???')}", file=sys.stderr)

time.sleep(5)

# Check selected date panel
r = eval_js(target, """
var sel = document.querySelector('[class*="panelSelected"]');
var dateStr = sel ? sel.querySelector('[class*="panelDate"]') : null;
JSON.stringify({date: dateStr ? dateStr.innerText.trim() : '', url: window.location.href});
""")
info = json.loads(r.get("value", "{}"))
print(f"After 5s: date={info.get('date')}, url={info.get('url')}", file=sys.stderr)

# Now scrape like normal
# Click 今日晋级
je = eval_js(target, """
var btns = document.querySelectorAll('button');
for (var i = 0; i < btns.length; i++) {
    if (btns[i].textContent.trim() === '今日晋级') { btns[i].click(); break; }
}
""")
time.sleep(2.5)

# Extract data
r2 = eval_js(target, """
var sel = document.querySelector('[class*="panelSelected"]');
var dateStr = sel ? sel.querySelector('[class*="panelDate"]') : null;
dateStr = dateStr ? dateStr.innerText.trim() : '';
var panels = document.querySelectorAll("[class*='_panel_']");
var days = [];
for (var i = 0; i < panels.length; i++) {
    var ds = panels[i].querySelector("[class*='panelDate']");
    if (ds) days.push(ds.innerText.trim());
}
JSON.stringify({date: dateStr, days: days, text: document.body.innerText});
""")
raw = json.loads(r2.get("value", "{}"))
print(f"Scraped date: {raw.get('date')}", file=sys.stderr)

# Parse
idx = raw.get("text", "").find("连板高度")
section = raw.get("text", "")[idx:] if idx >= 0 else ""
end = section.find("板块分布")
section = section[:end] if end > 0 else section

board_pat = re.compile(r"(\d+)连板\t\n(\d+/\d+=\d+%)\n\t\n(.*?)(?=\d+连板\t|首板\t)", re.DOTALL)
stocks = []
for m in board_pat.finditer(section):
    n = int(m.group(1))
    if n < 3: continue
    lines = [l.strip() for l in m.group(3).split("\n") if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"\d{6}\.[A-Z]{2}", line) or re.match(r"[+-]?\d", line):
            i += 1; continue
        if i + 1 < len(lines) and lines[i+1] == "晋":
            name = line
            i += 2
            theme = ""; code = ""; change = ""
            while i < len(lines):
                if re.match(r"\d{6}\.[A-Z]{2}", lines[i]):
                    code = lines[i]; i += 1
                elif re.match(r"[+-]\d+\.\d+%$", lines[i]):
                    change = lines[i]; i += 1; break
                elif not theme and lines[i] != "晋":
                    theme = lines[i]; i += 1
                else:
                    i += 1
            if name and code:
                stocks.append({"boards": n, "name": name, "theme": theme, "code": code, "change": change, "rate": m.group(2)})
        else:
            i += 1

date_str = raw.get("date", "??").split("\n")[0].strip()
trading_days = [d.split("\n")[0].strip() for d in raw.get("days", [])]
current_idx = trading_days.index(date_str) if date_str in trading_days else -1
for s in stocks:
    fi = current_idx - (s["boards"] - 1)
    s["first_date"] = trading_days[fi] if 0 <= fi < len(trading_days) else "??"

earliest = min((s["first_date"] for s in stocks), default="??")
ei = trading_days.index(earliest) if earliest in trading_days else 0
ci = trading_days.index(date_str) if date_str in trading_days else len(trading_days) - 1
relevant = trading_days[ei:ci+1]

curl("/close", [("target", target)])
output = {"date": date_str, "trading_days": relevant, "stocks": stocks}
print(json.dumps(output, ensure_ascii=False))
