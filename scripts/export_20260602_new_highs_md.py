from pathlib import Path
import json
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_feature_store.db import connect

TD = "2026-06-02"
out = Path("market_feature_store/exports/2026-06-02-20d-plus-new-highs.md")
out.parent.mkdir(parents=True, exist_ok=True)

period_order = ["history", "3y", "2y", "1y", "120d", "60d", "20d"]
period_labels = {
    "history": "历史新高",
    "3y": "3年新高",
    "2y": "2年新高",
    "1y": "1年新高",
    "120d": "120日新高",
    "60d": "60日新高",
    "20d": "20日新高",
}


def fmt(x, digits=2):
    if x is None:
        return "-"
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)


def load_periods(raw):
    try:
        arr = json.loads(raw or "[]")
    except Exception:
        arr = []
    got = []
    for item in arr:
        if isinstance(item, dict) and item.get("period"):
            got.append(item["period"])
    return [p for p in period_order if p in got]


def load_names(raw):
    try:
        arr = json.loads(raw or "[]")
    except Exception:
        return []
    names = []
    for item in arr:
        if isinstance(item, dict):
            name = item.get("name") or item.get("sector_name") or item.get("label")
        else:
            name = str(item)
        if name:
            names.append(name)
    return names


con = connect(read_only=True)
try:
    counts = con.execute(
        """
        select stock_high_count_history, stock_high_count_3y, stock_high_count_2y,
               stock_high_count_1y, stock_high_count_120d, stock_high_count_60d,
               stock_high_count_20d
        from fact_market_daily where trade_date = ?
        """,
        [TD],
    ).fetchone()
    rows = con.execute(
        """
        select stock_ts_code, stock_name, high_periods_json, pct_chg, pct_chg_10d,
               amount, market_cap, sw_l1, sw_l2, plate, whitelist_sectors_json
        from fact_stock_high_daily
        where trade_date = ? and high_periods_json like '%20d%'
        order by amount desc nulls last, market_cap desc nulls last
        """,
        [TD],
    ).fetchall()
finally:
    con.close()

items = []
for row in rows:
    code, name, periods_raw, pct_chg, pct_chg_10d, amount, market_cap, sw_l1, sw_l2, plate, sectors_raw = row
    periods = load_periods(periods_raw)
    sectors = load_names(sectors_raw)[:6]
    items.append({
        "code": code,
        "name": name,
        "periods": periods,
        "period_label": "、".join(period_labels[p] for p in periods),
        "pct_chg": pct_chg,
        "pct_chg_10d": pct_chg_10d,
        "amount": amount,
        "market_cap": market_cap,
        "sw_l1": sw_l1 or "未映射",
        "sw_l2": sw_l2 or "-",
        "plate": plate or "-",
        "sectors": sectors,
    })

by_industry = defaultdict(list)
for item in items:
    by_industry[item["sw_l1"]].append(item)

industry_summary = []
for sw_l1, stocks in by_industry.items():
    history = sum(1 for x in stocks if "history" in x["periods"])
    amount_sum = sum(float(x["amount"] or 0) for x in stocks)
    industry_summary.append((sw_l1, len(stocks), history, amount_sum))
industry_summary.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

lines = [f"# {TD} 20日及以上新高个股", "", "## 摘要", ""]
lines.append("- **样本口径**：命中 20日新高及以上任一周期的个股")
lines.append(f"- **个股数量**：{len(items)} 只")
if counts:
    labels = ["历史新高", "3年新高", "2年新高", "1年新高", "120日新高", "60日新高", "20日新高"]
    lines.append("- **周期家数**：" + "；".join(f"{label} {val}只" for label, val in zip(labels, counts)))
lines.extend(["", "## 一级行业分布", ""])
lines.append("| 一级行业 | 新高数 | 历史新高数 | 合计成交额(亿) |")
lines.append("|---|---:|---:|---:|")
for sw_l1, cnt, history, amount_sum in industry_summary:
    lines.append(f"| {sw_l1} | {cnt} | {history} | {fmt(amount_sum)} |")
lines.extend(["", "## 全量明细", ""])
for sw_l1, cnt, history, _amount in industry_summary:
    stocks = sorted(by_industry[sw_l1], key=lambda x: (x["amount"] is not None, x["amount"] or 0), reverse=True)
    lines.append(f"### {sw_l1}（{cnt}只，历史新高{history}只）")
    lines.append("")
    lines.append("| 股票 | 代码 | 命中周期 | 涨幅% | 10日涨幅% | 成交额(亿) | 市值(亿) | 二级行业 | 代表板块 |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|---|")
    for x in stocks:
        sectors = "、".join(x["sectors"]) if x["sectors"] else x["plate"]
        lines.append(
            f"| {x['name']} | {x['code']} | {x['period_label']} | {fmt(x['pct_chg'])} | "
            f"{fmt(x['pct_chg_10d'])} | {fmt(x['amount'])} | {fmt(x['market_cap'])} | "
            f"{x['sw_l2']} | {sectors} |"
        )
    lines.append("")

out.write_text("\n".join(lines), encoding="utf-8")
print(out)
print(f"rows={len(items)} industries={len(industry_summary)}")
