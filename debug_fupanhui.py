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

# Step 1: Try navigating directly with ?date parameter
for test_url in [
    "https://fupanhui.com/workspace/data/limit?date=2026-02-23",
    "https://fupanhui.com/workspace/data/limit?date=02-23",
    "https://fupanhui.com/workspace/data/limit?t=2026-02-23",
]:
    resp = curl("/new", [("url", test_url)])
    target = resp.get("targetId")
    if target:
        time.sleep(4)
        r = eval_js(target, """
var sel = document.querySelector('[class*="panelSelected"]');
var dateStr = sel ? sel.querySelector('[class*="panelDate"]') : null;
dateStr ? dateStr.innerText.trim() : 'no date found';
""")
        result = r.get("value", "???")
        print(f"URL {test_url}: selected={result}")
        curl("/close", [("target", target)])
        time.sleep(1)
    else:
        print(f"URL {test_url}: failed to open")

# Step 2: Try using page.evaluate to set internal state
resp2 = curl("/new", [("url", URL)])
target2 = resp2.get("targetId")
if target2:
    time.sleep(3)
    # Check if there's a global state or data object
    r = eval_js(target2, """
var keys = Object.keys(window);
var dataKeys = keys.filter(k => k.toLowerCase().includes('date') || k.toLowerCase().includes('limit') || k.toLowerCase().includes('panel'));
JSON.stringify(dataKeys.slice(0, 30));
""")
    print(f"Window keys related to date/limit/panel: {r.get('value', '???')}")

    # Check React internal fiber on calendar day 23
    eval_js(target2, "document.querySelector('._datePickerCompactBtn_1ycdg_19').click();")
    time.sleep(1)
    navs = "document.querySelectorAll('._calendarNav_1ycdg_166')"
    for i in range(3):
        eval_js(target2, f"{navs}[0].click();")
        time.sleep(0.3)
    time.sleep(1)

    r2 = eval_js(target2, """
var days = document.querySelectorAll('._calendarDay_1ycdg_332:not(._empty_1ycdg_353)');
var d23 = null;
for (var i = 0; i < days.length; i++) {
    if (parseInt(days[i].textContent.trim()) === 23) {
        d23 = days[i];
        break;
    }
}
if (!d23) return 'day not found';

// Check if day 23 has a different class (disabled/gray)
return d23.className;
""")
    print(f"Day 23 className: {r2.get('value', '???')}")

    # Check React props
    r3 = eval_js(target2, """
var days = document.querySelectorAll('._calendarDay_1ycdg_332:not(._empty_1ycdg_353)');
var d23 = null;
for (var i = 0; i < days.length; i++) {
    if (parseInt(days[i].textContent.trim()) === 23) { d23 = days[i]; break; }
}
if (!d23) return {};

// Try to find React internal key
var key = Object.keys(d23).find(k => k.startsWith('__reactInternalInstance') || k.startsWith('__reactFiber'));
if (!key) return {no_react: true};

var fiber = d23[key];
return {
    memoized_props_keys: Object.keys(fiber.memoizedProps || {}),
    memoized_state_keys: Object.keys(fiber.memoizedState || {}),
};
""")
    print(f"React fiber info: {r3.get('value', '???')}")

    curl("/close", [("target", target2)])
