#!/usr/bin/env python3
"""生成复盘/答卷日历页 calendar.html —— 按月日历排开，每天列出当日产物链接。

扫描范围（都在本机 Mac）：
- forecast-review-ledger/：<date>.md/.html、answer.<agent>.json、manifest、verdict
- 知识库 wiki/briefings/<date>.md（晨汇）
- 知识库 wiki/synthesis/卖方观点交叉-*（两种日期格式）
- 金融仓 复盘/daily/<date>/（每日复盘目录）

用法：python3 build_calendar.py   （输出 calendar.html 到本目录）
"""
from __future__ import annotations
import calendar as cal
import datetime as dt
import html
import json
import re
from collections import defaultdict
from pathlib import Path

LEDGER = Path(__file__).resolve().parent
FIN = LEDGER.parents[2]                      # finance-workspace-private
KB = FIN.parent / "knowledge-base-private"   # 知识库仓
e = html.escape

def norm(s: str) -> str | None:
    m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

days: dict[str, list[tuple[str, str, str]]] = defaultdict(list)  # date -> [(kind, label, url)]

def add(date: str | None, kind: str, label: str, path: Path) -> None:
    if date and path.exists():
        days[date].append((kind, label, path.as_uri()))

# 1) forecast-review-ledger
for p in sorted(LEDGER.glob("*")):
    d = norm(p.name)
    if not d:
        continue
    n = p.name
    if n.endswith(".html"):
        add(d, "forecast", "并排页", p)
    elif n.endswith(".md"):
        add(d, "forecast", "台账md", p)
    elif ".answer." in n:
        suffix = n.split(".answer.")[1].rsplit(".json", 1)[0]
        parts = suffix.split(".")
        label = f"答卷·{parts[0]}" + (f"·{parts[1]}" if len(parts) > 1 else "")
        add(d, "answer", label, p)
    elif n.endswith(".verdict.json"):
        add(d, "verdict", "verdict", p)
    elif n.endswith(".manifest.json"):
        add(d, "meta", "manifest", p)

# 2) 晨汇
for p in sorted((KB / "wiki" / "briefings").glob("20*.md")):
    add(norm(p.name), "briefing", "晨汇", p)

# 3) 卖方观点交叉
for p in sorted((KB / "wiki" / "synthesis").glob("卖方观点交叉-*.md")):
    add(norm(p.name), "sellside", "卖方交叉", p)

# 4) 每日复盘目录
daily = FIN / "复盘" / "daily"
if daily.exists():
    for p in sorted(daily.iterdir()):
        if p.is_dir():
            add(norm(p.name), "review", "复盘", p)

KIND_CSS = {"forecast": "k-fc", "answer": "k-an", "verdict": "k-vd",
            "briefing": "k-br", "sellside": "k-ss", "review": "k-rv", "meta": "k-mt"}

months = sorted({d[:7] for d in days}, reverse=True)
blocks = []
for ym in months:
    y, m = int(ym[:4]), int(ym[5:7])
    weeks = cal.Calendar(firstweekday=0).monthdayscalendar(y, m)
    rows = []
    for wk in weeks:
        cells = []
        for day in wk:
            if day == 0:
                cells.append('<td class="empty"></td>')
                continue
            d = f"{y}-{m:02d}-{day:02d}"
            items = days.get(d, [])
            links = "".join(
                f'<a class="tag {KIND_CSS.get(k, "")}" href="{u}" title="{e(lb)}">{e(lb)}</a>'
                for k, lb, u in sorted(items))
            cls = "has" if items else "none"
            cells.append(f'<td class="{cls}"><div class="dn">{day}</div><div class="tags">{links}</div></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    blocks.append(f"<section><h2>{y} 年 {m} 月</h2><table>"
                  "<thead><tr><th>一</th><th>二</th><th>三</th><th>四</th><th>五</th>"
                  "<th class='we'>六</th><th class='we'>日</th></tr></thead>"
                  f"<tbody>{''.join(rows)}</tbody></table></section>")

generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>复盘 · 答卷 · 晨汇 · 卖方 —— 日历</title>
<style>
:root {{ --bg:#f7f8fa; --line:#d9dee7; --panel:#fff; --muted:#64748b; --blue:#2563eb; }}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:#1f2933;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
header{{background:#111827;color:#fff;padding:22px 32px}}
header h1{{margin:0 0 4px;font-size:22px}} header p{{margin:0;color:#cbd5e1;font-size:13px}}
main{{max-width:1100px;margin:0 auto;padding:20px}}
section{{margin-bottom:28px}} h2{{font-size:17px;border-bottom:2px solid var(--blue);padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;table-layout:fixed}}
th{{font-size:12px;color:var(--muted);padding:4px}} th.we{{color:#b45309}}
td{{border:1px solid var(--line);vertical-align:top;height:78px;padding:4px;background:var(--panel)}}
td.empty{{background:transparent;border:none}} td.none .dn{{color:#c2c9d4}}
.dn{{font-size:12px;font-weight:600;margin-bottom:3px}}
.tags{{display:flex;flex-wrap:wrap;gap:3px}}
.tag{{font-size:10.5px;padding:1px 5px;border-radius:8px;text-decoration:none;color:#fff;white-space:nowrap}}
.k-fc{{background:#2563eb}} .k-an{{background:#7c3aed}} .k-vd{{background:#0f8b5f}}
.k-br{{background:#d97706}} .k-ss{{background:#be185d}} .k-rv{{background:#0e7490}} .k-mt{{background:#94a3b8}}
.legend{{margin:10px 0 18px;font-size:12px;color:var(--muted)}} .legend .tag{{margin-right:6px}}
</style>
</head>
<body>
<header><h1>研究产物日历</h1>
<p>点标签直达当日文件（md 在浏览器为纯文本，建议 Obsidian 打开）。重跑：python3 build_calendar.py · 生成于 {generated}</p></header>
<main>
<div class="legend">
<a class="tag k-fc">并排页/台账</a><a class="tag k-an">答卷</a><a class="tag k-vd">verdict</a>
<a class="tag k-br">晨汇</a><a class="tag k-ss">卖方交叉</a><a class="tag k-rv">复盘</a><a class="tag k-mt">manifest</a>
</div>
{''.join(blocks)}
</main>
</body></html>"""
out = LEDGER / "calendar.html"
out.write_text(page, encoding="utf-8")
print(f"written: {out}  dates={len(days)} months={len(months)}")
