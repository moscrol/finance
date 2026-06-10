from __future__ import annotations

import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
STYLE = """
:root{--paper:#f6f0e6;--paper-2:#fffaf1;--ink:#17140f;--muted:#746b5d;--line:#d8cbbb;--line-strong:#18140f;--accent:#0057ff;--accent-2:#ff5a1f;--card:#fffdf8;--shadow:0 18px 45px rgba(38,28,13,.08)}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:linear-gradient(90deg,rgba(23,20,15,.045) 1px,transparent 1px),linear-gradient(rgba(23,20,15,.035) 1px,transparent 1px),var(--paper);background-size:28px 28px;color:var(--ink);font-family:'Avenir Next','PingFang SC','Hiragino Sans GB',sans-serif}.skip{position:absolute;left:-999px;top:12px;background:var(--accent);color:#fff;padding:10px 14px;border-radius:999px;z-index:10}.skip:focus{left:16px}.shell{display:grid;grid-template-columns:320px minmax(0,1fr);gap:28px;max-width:1760px;margin:0 auto;padding:24px}.rail{position:sticky;top:24px;height:calc(100dvh - 48px);overflow:auto;border:1px solid var(--line-strong);background:rgba(255,250,241,.88);backdrop-filter:blur(14px);box-shadow:var(--shadow);padding:22px}.mark{font-family:'Bodoni 72','Songti SC',serif;font-size:42px;line-height:.86;letter-spacing:-.06em}.date-card{margin:22px 0;padding:18px;border:1px solid var(--line);background:var(--card)}.date-card .label{font-size:11px;letter-spacing:.18em;color:var(--muted);font-weight:900}.date-card .date{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;font-size:38px;font-weight:900;margin-top:6px}.tools{display:flex;gap:8px;margin:18px 0}.tools button{min-height:44px;border:1px solid var(--line-strong);background:var(--ink);color:var(--paper-2);padding:9px 12px;font-weight:800;cursor:pointer}.tools button:nth-child(2){background:var(--paper-2);color:var(--ink)}.toc{display:flex;flex-direction:column;gap:6px}.toc a{display:grid;grid-template-columns:36px 1fr;gap:8px;align-items:start;color:var(--muted);text-decoration:none;padding:8px 0;border-top:1px solid var(--line);font-size:13px;line-height:1.35}.toc a:hover,.toc a:focus{color:var(--ink)}.toc span{font-family:'DIN Condensed','Avenir Next Condensed',sans-serif;color:var(--accent);font-size:18px;line-height:1}.content{min-width:0}.hero{position:relative;border:1px solid var(--line-strong);background:var(--paper-2);padding:34px 38px 30px;margin-bottom:28px;box-shadow:var(--shadow);overflow:hidden}.hero:before{content:'';position:absolute;right:32px;top:28px;width:120px;height:120px;border:18px solid var(--accent);border-left-color:transparent;border-radius:50%;opacity:.9}.kicker{font-size:12px;letter-spacing:.28em;font-weight:900;color:var(--accent);text-transform:uppercase}.hero h1{font-family:'Bodoni 72','Songti SC',serif;font-size:72px;line-height:.92;letter-spacing:-.07em;margin:14px 0 20px;max-width:780px}.hero .summary{max-width:760px;color:var(--muted);font-size:17px;line-height:1.7}.content>h1{display:none}h2{display:flex;align-items:baseline;gap:12px;margin:42px 0 14px;padding-top:18px;border-top:3px solid var(--line-strong);font-family:'Songti SC','Noto Serif SC',serif;font-size:30px;line-height:1.2;letter-spacing:-.02em}h2:before{content:'§';color:var(--accent-2);font-family:'Bodoni 72',serif}h3{margin:28px 0 12px;font-size:18px;padding:10px 12px;border-left:5px solid var(--accent);background:#eef3ff}p,li{font-size:16px;line-height:1.85;color:#352f27}blockquote{margin:16px 0;padding:16px 18px;border-left:6px solid var(--accent-2);background:#fff4e9;color:#3b2b1e}blockquote p{margin:0}code{font-family:'SF Mono','Menlo',monospace;background:#eee4d5;border:1px solid var(--line);padding:2px 6px;border-radius:6px;color:#1b3b7a}.table-card{overflow:auto;border:1px solid var(--line-strong);background:var(--card);margin:14px 0 28px;box-shadow:var(--shadow)}table{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:13px}th,td{padding:10px 12px;border-bottom:1px solid var(--line);border-right:1px solid var(--line);white-space:nowrap;vertical-align:top}th{position:sticky;top:0;background:var(--ink);color:var(--paper-2);z-index:1;font-weight:900}td:first-child,th:first-child{position:sticky;left:0;z-index:2}td:first-child{background:#fff7eb;font-weight:900;color:#2a2118}tr:hover td{background:#f4f7ff}.board{border-width:2px}.board table{font-size:15px}.board td{white-space:normal}.board td:first-child{min-width:150px;background:#101010;color:#fff}.board td:last-child{min-width:520px;font-weight:700}.chart-frame{border:1px solid var(--line-strong);background:var(--card);padding:16px;box-shadow:var(--shadow);margin:18px 0 30px}.chart-frame img,.content img{display:block;width:100%;max-height:640px;object-fit:contain;background:#fff}.compact th,.compact td{padding:6px 8px;font-size:12px}.focus .rail{display:none}.focus .shell{display:block;max-width:1280px}.focus .hero h1{font-size:64px}@media(max-width:980px){.shell{display:block;padding:14px}.rail{position:relative;height:auto;margin-bottom:16px}.hero{padding:26px 22px}.hero:before{width:72px;height:72px;border-width:12px;right:18px;top:18px}.hero h1{font-size:44px}.table-card{max-height:70dvh}h2{font-size:24px}.board td:last-child{min-width:320px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""


def slug(title: str) -> str:
    value = re.sub(r"[`*_#>|]", "", title).strip().lower()
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", value).strip("-")
    return value or "section"


def add_heading_ids(body: str, ids: list[str]) -> str:
    idx = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal idx
        level, title = match.group(1), match.group(2)
        value = ids[idx] if idx < len(ids) else slug(re.sub(r"<.*?>", "", title))
        idx += 1
        return f'<h{level} id="{value}">{title}</h{level}>'

    return re.sub(r"<h([23])>(.*?)</h\1>", replace, body)


def enhance_body(body: str, ids: list[str]) -> str:
    body = add_heading_ids(body, ids)
    body = re.sub(r"(<table>.*?</table>)", r'<div class="table-card">\1</div>', body, flags=re.S)
    body = body.replace('class="table-card"', 'class="table-card board"', 1)
    body = re.sub(r'<p><img([^>]*) /></p>', r'<figure class="chart-frame"><img\1 /></figure>', body)
    return body


def main() -> int:
    trade_date = sys.argv[1]
    gate = subprocess.run([sys.executable, str(ROOT / "scripts/check_daily_review_data.py"), trade_date])
    if gate.returncode:
        return gate.returncode

    md_path = ROOT / f"market_feature_store/exports/{trade_date}-daily-review.md"
    chart_path = ROOT / f"market_feature_store/exports/{trade_date}-advancers-ma5.png"
    out_dir = ROOT / f"复盘/daily/{trade_date}"
    out_path = out_dir / f"{trade_date}-daily-review.html"

    text = md_path.read_text(encoding="utf-8").replace(str(chart_path), chart_path.name)
    heads = [(title, slug(title)) for _, title in re.findall(r"^(##+)\s+(.+)$", text, re.M)]
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    body = enhance_body(body, [item[1] for item in heads])
    toc = "".join(f'<a href="#{sid}"><span>{i:02d}</span>{escape(title)}</a>' for i, (title, sid) in enumerate(heads, 1))
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{trade_date} 复盘可视化</title><style>{STYLE}</style></head><body><a class="skip" href="#main">跳到正文</a><div class="shell"><aside class="rail"><div class="mark">Market<br>Brief</div><div class="date-card"><div class="label">TRADE DATE</div><div class="date">{trade_date}</div></div><div class="tools"><button id="compact" type="button">紧凑表格</button><button id="focus" type="button">专注阅读</button></div><nav class="toc" aria-label="复盘目录">{toc}</nav></aside><main class="content" id="main"><section class="hero"><div class="kicker">Daily Market Review</div><h1>{trade_date}<br>市场复盘</h1><div class="summary">同一份复盘内容，重新排版为浅色投研 briefing：左侧目录定位，右侧按模块阅读；核心看板、情绪、行业、题材、强度和数据覆盖保持原始模块顺序。</div></section>{body}</main></div><script>document.getElementById("compact").onclick=()=>document.body.classList.toggle("compact");document.getElementById("focus").onclick=()=>document.body.classList.toggle("focus");</script></body></html>'''

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    shutil.copy2(chart_path, out_dir / chart_path.name)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
