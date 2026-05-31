"""写入后完整性检查与补全。

扫描指定日期在「每日指标」表中的记录，对白名单内的空字段尝试重新抓取并更新。

用法：
  python3 verify_and_patch.py YY-MM-DD    # 检查并补全指定日期
  python3 verify_and_patch.py --latest    # 检查表中最新日期
"""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from feishu_utils import load_config, get_token as _get_token, api

cfg = load_config()
APP_TOKEN = cfg["app_token"]
DAILY_TABLE = cfg["tables"]["daily"]
CDP_PORT = 3456

# 需要检查补全的字段（字段名 → 抓取来源页面）
PATCHABLE_FIELDS = {
    "周均线": "market",
    "偏离度": "market",
}

# 合理为空的字段（跳过检查）
OPTIONAL_FIELDS = {"冰点"}


def get_token():
    return _get_token(cfg)


def cdp_new(url):
    """CDP 新开标签页，返回 targetId。"""
    resp = urllib.request.urlopen(
        f"http://localhost:{CDP_PORT}/new?url={urllib.parse.quote(url, safe='')}",
        timeout=15,
    )
    return json.loads(resp.read())["targetId"]


def cdp_close(target_id):
    """CDP 关闭标签页。"""
    try:
        urllib.request.urlopen(
            f"http://localhost:{CDP_PORT}/close?target={target_id}", timeout=10
        )
    except Exception:
        pass


def cdp_eval(target_id, expr, retries=3):
    """CDP 执行 JS 表达式，带重试。返回 value 或 None。"""
    data = urllib.parse.urlencode({"expr": expr}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"http://localhost:{CDP_PORT}/eval?target={target_id}",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            if "value" in result:
                return result["value"]
            if "error" in result:
                time.sleep(1)
                continue
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
    return None


def fetch_review_data(target_id):
    """从 review 页面抓取均线上方家数占比。"""
    time.sleep(3)
    text = cdp_eval(target_id, "document.body.innerText")
    if not text:
        return {}

    result = {}
    # 均线上方家数占比：查找 "均线上方家数占比" 后面的百分比数字
    m = re.search(r"均线上方家数占比\s*(\d+(?:\.\d+)?%?)", text)
    if m:
        result["均线上方家数占比"] = m.group(1)
    else:
        # 有时只显示标签如 "过热"，也记录下来
        m2 = re.search(r"均线上方家数占比\s*(\S+)", text)
        if m2:
            val = m2.group(1)
            if val not in ("", "复制图片"):
                result["均线上方家数占比"] = val
    return result


def fetch_market_data(target_id):
    """从 market data 页面抓取周均线和偏离度（通过 canvas hover tooltip）。"""
    time.sleep(4)
    # 先检查 canvas 是否存在
    canvas_count = cdp_eval(target_id, "document.querySelectorAll('canvas').length")
    if canvas_count is None or canvas_count == 0:
        print("  market data 页面无 canvas，跳过 tooltip 抓取")
        return {}

    # Hover 第一个 canvas 的右端
    js_hover = """
    var canvas = document.querySelectorAll('canvas')[0];
    var rect = canvas.getBoundingClientRect();
    var x = rect.x + rect.width * 0.9;
    var y = rect.y + rect.height * 0.4;
    canvas.dispatchEvent(new PointerEvent('pointermove', {clientX: x, clientY: y, bubbles: true, pointerId: 1, pointerType: 'mouse'}));
    canvas.dispatchEvent(new MouseEvent('mousemove', {clientX: x, clientY: y, bubbles: true}));
    'done'"""
    cdp_eval(target_id, js_hover)
    time.sleep(1)

    # 读取 tooltip
    js_tooltip = """
    var overlays = document.querySelectorAll("div[style*=\\\"z-index\\\"]");
    var tooltipText = "";
    for (var i = 0; i < overlays.length; i++) {
      var st = window.getComputedStyle(overlays[i]);
      if (st.display !== "none" && parseInt(st.zIndex) > 1000) {
        var txt = overlays[i].innerText;
        if (txt && txt.indexOf("周均线") >= 0) { tooltipText = txt; break; }
      }
    }
    tooltipText;"""
    tooltip = cdp_eval(target_id, js_tooltip)
    result = {}
    if tooltip:
        m_ma = re.search(r"周均线[:：]\s*(\d+\.\d+)", tooltip)
        m_dev = re.search(r"偏离[:：]\s*([+-]?\d+\.\d+%?)", tooltip)
        if m_ma:
            result["周均线"] = m_ma.group(1)
        if m_dev:
            result["偏离度"] = m_dev.group(1)
    return result


def find_record(token, date_str):
    """按日期查找每日指标记录，返回 (record_id, fields) 或 (None, None)。"""
    # 飞书 filter 需要对引号做转义
    filter_expr = f'CurrentValue.[日期]="{date_str}"'
    result = api(
        "GET",
        "/records?filter=" + urllib.parse.quote(filter_expr),
        token,
        table_id=DAILY_TABLE,
        app_token=APP_TOKEN,
    )
    if result.get("code") != 0:
        print(f"  查询记录失败: {result.get('msg')}")
        return None, None
    items = result.get("data", {}).get("items", [])
    if not items:
        print(f"  未找到日期 {date_str} 的记录")
        return None, None
    item = items[0]
    return item["record_id"], item.get("fields", {})


def patch_record(token, record_id, fields):
    """更新单条记录。"""
    result = api(
        "PUT",
        f"/records/{record_id}",
        token,
        {"fields": fields},
        table_id=DAILY_TABLE,
        app_token=APP_TOKEN,
    )
    return result.get("code") == 0


def scrape_missing(date_str, missing_fields, max_retries=2):
    """对缺失字段进行定向重抓，返回补全的字段 dict。"""
    patches = {}
    need_review = any(PATCHABLE_FIELDS.get(f) == "review" for f in missing_fields)
    need_market = any(PATCHABLE_FIELDS.get(f) == "market" for f in missing_fields)

    review_target = None
    market_target = None

    try:
        if need_review:
            print("  → 打开 review 页面补全数据...")
            review_target = cdp_new("https://fupanhui.com/workspace/review")
            # 若需要切换日期，使用日历选择器
            js_switch = f"""
            var btn = document.querySelector('[class*=\"_datePickerCompactBtn_\"]');
            if (btn) btn.click();
            var monthEl = document.querySelector('[class*=\"_calendarMonth_\"]');
            var monthText = monthEl ? monthEl.textContent : '';
            var targetMonth = '2026年5月'; // TODO: 根据 date_str 动态计算
            var navs = document.querySelectorAll('[class*=\"_calendarNav_\"]');
            // 简化：假设当前月份正确，直接点日期
            var parts = '{date_str}'.split('-');
            var targetDay = parseInt(parts[2], 10);
            var days = document.querySelectorAll('[class*=\"_calendarDay_\"]:not([class*=\"_empty_\"])');
            for (var i = 0; i < days.length; i++) {{
                if (parseInt(days[i].textContent.trim()) === targetDay) {{
                    days[i].click(); break;
                }}
            }}
            'switched'"""
            # 对于今日数据通常不需要切换，但保留逻辑
            if date_str != "26-05-08":  # 简化处理，实际应动态判断
                cdp_eval(review_target, js_switch)
                time.sleep(2)

            review_data = fetch_review_data(review_target)
            for f in missing_fields:
                if f in review_data and review_data[f]:
                    patches[f] = review_data[f]

        if need_market:
            print("  → 打开 market data 页面补全数据...")
            market_target = cdp_new("https://fupanhui.com/workspace/data/market")
            market_data = fetch_market_data(market_target)
            for f in missing_fields:
                if f in market_data and market_data[f]:
                    patches[f] = market_data[f]

    finally:
        if review_target:
            cdp_close(review_target)
        if market_target:
            cdp_close(market_target)

    return patches


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python3 verify_and_patch.py YY-MM-DD")
        print("      python3 verify_and_patch.py --latest")
        sys.exit(1)

    if args[0] == "--latest":
        token = get_token()
        result = api("GET", "/records?page_size=1", token, table_id=DAILY_TABLE, app_token=APP_TOKEN)
        if result.get("code") != 0 or not result.get("data", {}).get("items"):
            print("无法获取最新记录")
            sys.exit(1)
        fields = result["data"]["items"][0].get("fields", {})
        date_str = fields.get("日期", "").strip()
        if not date_str:
            print("最新记录无日期字段")
            sys.exit(1)
        print(f"最新记录日期: {date_str}")
    else:
        date_str = args[0]

    token = get_token()
    record_id, fields = find_record(token, date_str)
    if record_id is None:
        sys.exit(1)

    print(f"\n检查日期 {date_str} 的记录...")

    # 检查空字段
    missing = []
    for fname, fval in fields.items():
        if fname in OPTIONAL_FIELDS:
            continue
        if fname not in PATCHABLE_FIELDS:
            continue
        if fval is None or str(fval).strip() == "":
            missing.append(fname)

    if not missing:
        print("  所有可补全字段均已填写 ✓")
        return

    print(f"  发现 {len(missing)} 个空字段: {', '.join(missing)}")

    # 尝试补全（最多重试 2 次）
    for attempt in range(2):
        print(f"\n  补全尝试 {attempt + 1}/2...")
        patches = scrape_missing(date_str, missing)
        if patches:
            print(f"  抓取到: {patches}")
            if patch_record(token, record_id, patches):
                print("  更新成功 ✓")
                # 更新缺失列表
                missing = [f for f in missing if f not in patches or not patches[f]]
            else:
                print("  更新失败")
        else:
            print("  本次未抓取到新数据")

        if not missing:
            break

    if missing:
        print(f"\n  ⚠ 以下字段仍为空: {', '.join(missing)}")
    else:
        print(f"\n  全部补全 ✓")


if __name__ == "__main__":
    main()
